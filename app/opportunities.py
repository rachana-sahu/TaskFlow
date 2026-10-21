import logging
import os
import re
import zipfile
from datetime import UTC, date, datetime, time, timedelta
from html.parser import HTMLParser
from io import BytesIO
from pathlib import Path
from typing import Annotated, Literal
from urllib.parse import urlparse
from uuid import uuid4
from xml.etree.ElementTree import ParseError
from zoneinfo import ZoneInfo

import httpx
from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from pydantic import BaseModel, ConfigDict, Field, field_validator
from pypdf import PdfReader
from pypdf.errors import PdfReadError
from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import (
    InterviewPractice,
    JobApplication,
    JobBoardSource,
    JobSearchFilter,
    ResumeDocument,
    Task,
    TaskHistory,
    User,
)
from app.security import current_user, require_csrf

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1", tags=["career"])
Db = Annotated[Session, Depends(get_db)]
AuthenticatedUser = Annotated[User, Depends(current_user)]
MAX_RESUME_BYTES = 8 * 1024 * 1024
MAX_RESUME_TEXT = 500_000
BOARD_SLUG = re.compile(r"^[A-Za-z0-9_-]{1,120}$")
SKILL_TERMS = (
    "algorithms",
    "aws",
    "azure",
    "c++",
    "c#",
    "css",
    "data analysis",
    "data structures",
    "django",
    "docker",
    "fastapi",
    "flask",
    "gcp",
    "git",
    "go",
    "graphql",
    "html",
    "java",
    "javascript",
    "kafka",
    "kubernetes",
    "linux",
    "machine learning",
    "mongodb",
    "mysql",
    "node.js",
    "postgresql",
    "python",
    "react",
    "redis",
    "rest",
    "rust",
    "sql",
    "system design",
    "typescript",
)
STOP_WORDS = {
    "about",
    "across",
    "also",
    "and",
    "are",
    "been",
    "being",
    "build",
    "candidate",
    "company",
    "experience",
    "from",
    "have",
    "into",
    "including",
    "looking",
    "more",
    "must",
    "our",
    "role",
    "should",
    "team",
    "that",
    "their",
    "this",
    "with",
    "work",
    "working",
    "years",
    "your",
}


class HTMLText(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []

    def handle_data(self, data: str) -> None:
        if data.strip():
            self.parts.append(data.strip())


def plain_text(value: str | None) -> str:
    parser = HTMLText()
    parser.feed(value or "")
    return " ".join(parser.parts)[:MAX_RESUME_TEXT]


def validate_http_url(value: str, *, ambitionbox_only: bool = False) -> str:
    parsed = urlparse(value)
    if (
        parsed.scheme not in {"http", "https"}
        or not parsed.hostname
        or parsed.username
        or parsed.password
    ):
        raise ValueError("Use a valid http or https URL")
    if ambitionbox_only and not (
        parsed.hostname == "ambitionbox.com" or parsed.hostname.endswith(".ambitionbox.com")
    ):
        raise ValueError("Use a link from ambitionbox.com")
    return value


class BoardCreate(BaseModel):
    provider: Literal["greenhouse", "lever", "link_only"]
    company_name: str = Field(min_length=1, max_length=120)
    board_slug: str | None = Field(default=None, max_length=120)
    search_url: str | None = Field(default=None, max_length=1000)

    @field_validator("board_slug")
    @classmethod
    def valid_slug(cls, value: str | None) -> str | None:
        if value is not None and not BOARD_SLUG.fullmatch(value):
            raise ValueError("Board ID may contain only letters, digits, underscores, and hyphens")
        return value

    @field_validator("search_url")
    @classmethod
    def valid_search_url(cls, value: str | None) -> str | None:
        if value is not None:
            return validate_http_url(value)
        return value

    def validate_provider_fields(self):
        if self.provider == "link_only" and not self.search_url:
            raise ValueError("Custom job platforms require a search URL")
        if self.provider in {"greenhouse", "lever"} and not self.board_slug:
            raise ValueError("Greenhouse and Lever sources require a public board ID")


class BoardResponse(BaseModel):
    id: str
    provider: str
    company_name: str
    board_slug: str | None
    search_url: str | None
    active: bool
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class SearchFilterUpdate(BaseModel):
    keywords: str = Field(default="", max_length=300)
    location: str = Field(default="", max_length=180)
    work_mode: Literal["any", "remote", "hybrid", "onsite"] = "any"
    minimum_match: int = Field(default=0, ge=0, le=100)


class SearchFilterResponse(SearchFilterUpdate):
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


class JobResult(BaseModel):
    provider: str
    company_name: str
    title: str
    location: str
    job_url: str
    description: str
    workplace: str
    matched_keywords: list[str]
    missing_keywords: list[str]
    match_score: int | None
    saved: bool = False


class SearchResponse(BaseModel):
    results: list[JobResult]
    source_errors: list[str]
    resume_uploaded: bool
    listing_count: int


class ApplicationCreate(BaseModel):
    provider: str = Field(max_length=20)
    title: str = Field(min_length=1, max_length=200)
    company_name: str = Field(min_length=1, max_length=180)
    location: str = Field(default="", max_length=180)
    job_url: str = Field(min_length=1, max_length=1000)
    description: str = Field(default="", max_length=MAX_RESUME_TEXT)

    @field_validator("job_url")
    @classmethod
    def valid_job_url(cls, value: str) -> str:
        return validate_http_url(value)


class ApplicationUpdate(BaseModel):
    status: (
        Literal["saved", "applying", "applied", "interview", "offer", "rejected", "withdrawn"]
        | None
    ) = None
    company_rating: int | None = Field(default=None, ge=1, le=5)
    company_notes: str | None = Field(default=None, max_length=10000)
    company_review_url: str | None = Field(default=None, max_length=1000)

    @field_validator("company_review_url")
    @classmethod
    def valid_review_url(cls, value: str | None) -> str | None:
        if value:
            return validate_http_url(value, ambitionbox_only=True)
        return value


class ApplicationResponse(BaseModel):
    id: str
    provider: str
    title: str
    company_name: str
    location: str
    job_url: str
    description: str
    status: str
    company_rating: int | None
    company_notes: str | None
    company_review_url: str | None
    created_at: datetime
    updated_at: datetime
    match_score: int | None = None
    matched_keywords: list[str] = []
    missing_keywords: list[str] = []
    model_config = ConfigDict(from_attributes=True)


class PracticeCreate(BaseModel):
    year: int | None = Field(default=None, ge=1900, le=2200)
    category: str = Field(default="Interview question", min_length=1, max_length=100)
    prompt: str = Field(min_length=1, max_length=10000)
    review_notes: str | None = Field(default=None, max_length=10000)
    rating: int | None = Field(default=None, ge=1, le=5)
    source_url: str | None = Field(default=None, max_length=1000)

    @field_validator("source_url")
    @classmethod
    def valid_source_url(cls, value: str | None) -> str | None:
        if value:
            return validate_http_url(value, ambitionbox_only=True)
        return value


class PracticeUpdate(PracticeCreate):
    year: int | None = Field(default=None, ge=1900, le=2200)
    category: str | None = Field(default=None, min_length=1, max_length=100)
    prompt: str | None = Field(default=None, min_length=1, max_length=10000)
    review_notes: str | None = Field(default=None, max_length=10000)
    rating: int | None = Field(default=None, ge=1, le=5)
    source_url: str | None = Field(default=None, max_length=1000)

    @field_validator("source_url")
    @classmethod
    def valid_source_url(cls, value: str | None) -> str | None:
        if value:
            return validate_http_url(value, ambitionbox_only=True)
        return value


class PracticeResponse(BaseModel):
    id: str
    application_id: str
    year: int | None
    category: str
    prompt: str
    review_notes: str | None
    rating: int | None
    source_url: str | None
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


class ResumeResponse(BaseModel):
    id: str
    filename: str
    uploaded_at: datetime
    extracted_characters: int


class ActivityResponse(BaseModel):
    year: int
    month: int
    active_days: dict[str, int]
    current_streak: int
    longest_streak: int
    completed_tasks: int


def ensure_search_filter(db: Session, user_id: str) -> JobSearchFilter:
    filters = db.get(JobSearchFilter, user_id)
    if filters is None:
        filters = JobSearchFilter(user_id=user_id)
        db.add(filters)
        db.commit()
        db.refresh(filters)
    return filters


def _resume_for_user(db: Session, user_id: str) -> ResumeDocument | None:
    return db.scalar(select(ResumeDocument).where(ResumeDocument.user_id == user_id))


def _contains_term(text: str, term: str) -> bool:
    return re.search(rf"(?<![a-z0-9]){re.escape(term)}(?![a-z0-9])", text) is not None


def _match_keywords(resume_text: str, description: str, title: str, location: str) -> dict:
    description = f"{title} {description}".lower()
    resume = resume_text.lower()
    workplace_text = f"{location} {description}".lower()
    required = [term for term in SKILL_TERMS if _contains_term(description, term)]
    if not required:
        required = sorted(
            {
                word
                for word in re.findall(r"[a-z][a-z0-9+#.]{2,}", description)
                if word not in STOP_WORDS
            }
        )[:15]
    found = [term for term in required if _contains_term(resume, term)]
    missing = [term for term in required if term not in resume]
    score = round(len(found) * 100 / len(required)) if required else 0
    return {
        "matched_keywords": found,
        "missing_keywords": missing,
        "match_score": score,
        "workplace": (
            "hybrid"
            if "hybrid" in workplace_text
            else "remote"
            if "remote" in workplace_text
            else "onsite"
        ),
    }


def _matches_filters(job: dict, filters: JobSearchFilter, match_score: int | None) -> bool:
    if filters.keywords:
        terms = [part.lower() for part in filters.keywords.split(",") if part.strip()]
        searchable = f"{job['title']} {job['description']} {job['company_name']}".lower()
        if terms and not all(term in searchable for term in terms):
            return False
    if filters.location and filters.location.lower() not in job["location"].lower():
        return False
    if filters.work_mode == "remote" and job["workplace"] != "remote":
        return False
    if filters.work_mode == "onsite" and job["workplace"] != "onsite":
        return False
    if filters.work_mode == "hybrid" and job["workplace"] != "hybrid":
        return False
    return not (
        match_score is not None and filters.minimum_match and match_score < filters.minimum_match
    )


def _greenhouse_jobs(board: JobBoardSource) -> list[dict]:
    response = httpx.get(
        f"https://boards-api.greenhouse.io/v1/boards/{board.board_slug}/jobs",
        params={"content": "true"},
        timeout=8.0,
        follow_redirects=False,
    )
    response.raise_for_status()
    payload = response.json()
    rows = payload.get("jobs", []) if isinstance(payload, dict) else []
    return [
        {
            "provider": "greenhouse",
            "company_name": board.company_name,
            "title": row["title"],
            "location": (row.get("location") or {}).get("name", ""),
            "job_url": row["absolute_url"],
            "description": plain_text(row.get("content")),
        }
        for row in rows
        if isinstance(row, dict) and row.get("title") and row.get("absolute_url")
    ]


def _lever_jobs(board: JobBoardSource) -> list[dict]:
    response = httpx.get(
        f"https://api.lever.co/v0/postings/{board.board_slug}",
        params={"mode": "json"},
        timeout=8.0,
        follow_redirects=False,
    )
    response.raise_for_status()
    payload = response.json()
    if not isinstance(payload, list):
        raise ValueError("Unexpected Lever board response")
    jobs = []
    for row in payload:
        if not isinstance(row, dict):
            continue
        categories = row.get("categories") or {}
        if not row.get("text") or not row.get("hostedUrl"):
            continue
        jobs.append(
            {
                "provider": "lever",
                "company_name": board.company_name,
                "title": row["text"],
                "location": categories.get("location") or "",
                "job_url": row["hostedUrl"],
                "description": row.get("descriptionPlain") or plain_text(row.get("description")),
            }
        )
    return jobs


def application_response(
    application: JobApplication, resume: ResumeDocument | None
) -> ApplicationResponse:
    values = {
        column.name: getattr(application, column.name)
        for column in JobApplication.__table__.columns
    }
    if resume:
        values.update(
            _match_keywords(
                resume.extracted_text,
                application.description,
                application.title,
                application.location,
            )
        )
    else:
        values.update(match_score=None, matched_keywords=[], missing_keywords=[])
    return ApplicationResponse.model_validate(values)


def _application(db: Session, user_id: str, application_id: str) -> JobApplication:
    application = db.scalar(
        select(JobApplication).where(
            JobApplication.id == application_id,
            JobApplication.user_id == user_id,
        )
    )
    if application is None:
        raise HTTPException(status_code=404, detail="Job application not found")
    return application


@router.get("/job-sources", response_model=list[BoardResponse])
def list_job_sources(user: AuthenticatedUser, db: Db):
    return list(
        db.scalars(
            select(JobBoardSource)
            .where(JobBoardSource.user_id == user.id)
            .order_by(JobBoardSource.created_at)
        )
    )


@router.post(
    "/job-sources",
    response_model=BoardResponse,
    status_code=201,
    dependencies=[Depends(require_csrf)],
)
def create_job_source(body: BoardCreate, user: AuthenticatedUser, db: Db):
    try:
        body.validate_provider_fields()
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    count = db.scalar(
        select(func.count(JobBoardSource.id)).where(JobBoardSource.user_id == user.id)
    )
    if count and count >= 12:
        raise HTTPException(status_code=422, detail="A maximum of 12 job sources is allowed")
    duplicate_query = select(JobBoardSource.id).where(
        JobBoardSource.user_id == user.id,
        JobBoardSource.provider == body.provider,
        JobBoardSource.board_slug == body.board_slug,
        JobBoardSource.search_url == body.search_url,
    )
    if db.scalar(duplicate_query):
        raise HTTPException(status_code=409, detail="That job source is already connected")
    source = JobBoardSource(
        user_id=user.id,
        provider=body.provider,
        company_name=body.company_name.strip(),
        board_slug=body.board_slug,
        search_url=body.search_url,
    )
    db.add(source)
    db.commit()
    db.refresh(source)
    return source


@router.delete(
    "/job-sources/{source_id}",
    status_code=204,
    dependencies=[Depends(require_csrf)],
)
def delete_job_source(source_id: str, user: AuthenticatedUser, db: Db):
    source = db.scalar(
        select(JobBoardSource).where(
            JobBoardSource.id == source_id, JobBoardSource.user_id == user.id
        )
    )
    if source is None:
        raise HTTPException(status_code=404, detail="Job source not found")
    db.delete(source)
    db.commit()


@router.get("/job-search/filters", response_model=SearchFilterResponse)
def get_search_filters(user: AuthenticatedUser, db: Db):
    return ensure_search_filter(db, user.id)


@router.put(
    "/job-search/filters",
    response_model=SearchFilterResponse,
    dependencies=[Depends(require_csrf)],
)
def update_search_filters(body: SearchFilterUpdate, user: AuthenticatedUser, db: Db):
    filters = ensure_search_filter(db, user.id)
    for key, value in body.model_dump().items():
        setattr(filters, key, value.strip() if isinstance(value, str) else value)
    db.commit()
    db.refresh(filters)
    return filters


@router.get("/job-search", response_model=SearchResponse)
def search_jobs(user: AuthenticatedUser, db: Db):
    filters = ensure_search_filter(db, user.id)
    resume = _resume_for_user(db, user.id)
    saved_urls = set(
        db.scalars(select(JobApplication.job_url).where(JobApplication.user_id == user.id))
    )
    sources = list(
        db.scalars(
            select(JobBoardSource)
            .where(JobBoardSource.user_id == user.id, JobBoardSource.active.is_(True))
            .limit(12)
        )
    )
    results: list[dict] = []
    source_errors = []
    for source in sources:
        if source.provider == "link_only":
            continue
        try:
            jobs = (
                _greenhouse_jobs(source) if source.provider == "greenhouse" else _lever_jobs(source)
            )
        except (httpx.HTTPError, ValueError, KeyError) as exc:
            logger.warning("Job source %s failed: %s", source.id, exc)
            source_errors.append(f"{source.company_name} ({source.provider}) could not be reached.")
            continue
        for job in jobs:
            match = (
                _match_keywords(
                    resume.extracted_text,
                    job["description"],
                    job["title"],
                    job["location"],
                )
                if resume
                else {
                    "matched_keywords": [],
                    "missing_keywords": [],
                    "match_score": None,
                    "workplace": _match_keywords("", "", "", job["location"])["workplace"],
                }
            )
            job.update(match)
            if _matches_filters(job, filters, match["match_score"]):
                job["saved"] = job["job_url"] in saved_urls
                results.append(job)
    results.sort(key=lambda item: (item["match_score"] or 0, item["title"].lower()), reverse=True)
    return SearchResponse(
        results=results[:250],
        source_errors=source_errors,
        resume_uploaded=resume is not None,
        listing_count=len(results),
    )


@router.post(
    "/resume",
    response_model=ResumeResponse,
    dependencies=[Depends(require_csrf)],
)
async def upload_resume(
    request: Request,
    user: AuthenticatedUser,
    db: Db,
    file: Annotated[UploadFile, File()],
):
    filename = Path(file.filename or "").name
    suffix = Path(filename).suffix.lower()
    if suffix not in {".pdf", ".docx", ".txt"}:
        raise HTTPException(status_code=415, detail="Upload a PDF, DOCX, or TXT resume")
    content = await file.read(MAX_RESUME_BYTES + 1)
    if not content or len(content) > MAX_RESUME_BYTES:
        raise HTTPException(status_code=413, detail="Resume must be between 1 byte and 8 MB")
    try:
        if suffix == ".pdf":
            reader = PdfReader(BytesIO(content), strict=False)
            if len(reader.pages) > 100:
                raise ValueError("Resume has too many pages")
            text = "\n".join(page.extract_text() or "" for page in reader.pages)
        elif suffix == ".docx":
            with zipfile.ZipFile(BytesIO(content)) as document:
                info = document.getinfo("word/document.xml")
                if info.file_size > MAX_RESUME_BYTES:
                    raise ValueError("Document contents are too large")
                from xml.etree import ElementTree

                root = ElementTree.fromstring(document.read(info))
                text = " ".join(node.text or "" for node in root.iter() if node.tag.endswith("}t"))
        else:
            text = content.decode("utf-8")
    except (
        ValueError,
        KeyError,
        OSError,
        zipfile.BadZipFile,
        UnicodeDecodeError,
        ParseError,
        PdfReadError,
    ) as exc:
        raise HTTPException(
            status_code=422, detail="Resume could not be read; check the file format"
        ) from exc
    extracted_text = text.strip()[:MAX_RESUME_TEXT]
    if not extracted_text:
        raise HTTPException(status_code=422, detail="No readable text was found in the resume")

    storage_dir = Path(request.app.state.upload_dir)
    storage_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
    storage_dir.chmod(0o700)
    storage_key = f"{uuid4().hex}{suffix}"
    file_path = storage_dir / storage_key
    descriptor = os.open(file_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(descriptor, "wb") as stored_file:
            stored_file.write(content)
    except OSError:
        file_path.unlink(missing_ok=True)
        raise
    existing = _resume_for_user(db, user.id)
    old_path = storage_dir / existing.storage_key if existing else None
    if existing:
        db.delete(existing)
    resume = ResumeDocument(
        user_id=user.id,
        filename=filename[:255],
        storage_key=storage_key,
        extracted_text=extracted_text,
    )
    db.add(resume)
    try:
        db.commit()
    except SQLAlchemyError:
        db.rollback()
        file_path.unlink(missing_ok=True)
        raise
    db.refresh(resume)
    if old_path:
        try:
            old_path.unlink(missing_ok=True)
        except OSError:
            logger.exception("Could not remove replaced resume file")
    return ResumeResponse(
        id=resume.id,
        filename=resume.filename,
        uploaded_at=resume.uploaded_at,
        extracted_characters=len(extracted_text),
    )


@router.get("/resume", response_model=ResumeResponse)
def get_resume(user: AuthenticatedUser, db: Db):
    resume = _resume_for_user(db, user.id)
    if resume is None:
        raise HTTPException(status_code=404, detail="No resume uploaded")
    return ResumeResponse(
        id=resume.id,
        filename=resume.filename,
        uploaded_at=resume.uploaded_at,
        extracted_characters=len(resume.extracted_text),
    )


@router.delete("/resume", status_code=204, dependencies=[Depends(require_csrf)])
def delete_resume(request: Request, user: AuthenticatedUser, db: Db):
    resume = _resume_for_user(db, user.id)
    if resume is None:
        raise HTTPException(status_code=404, detail="No resume uploaded")
    file_path = Path(request.app.state.upload_dir) / resume.storage_key
    db.delete(resume)
    db.commit()
    try:
        file_path.unlink(missing_ok=True)
    except OSError as exc:
        logger.exception("Could not remove resume file after deletion")
        raise HTTPException(
            status_code=500, detail="Resume record deleted, but file cleanup failed"
        ) from exc


@router.get("/job-applications", response_model=list[ApplicationResponse])
def list_applications(user: AuthenticatedUser, db: Db):
    resume = _resume_for_user(db, user.id)
    applications = db.scalars(
        select(JobApplication)
        .where(JobApplication.user_id == user.id)
        .order_by(JobApplication.updated_at.desc())
    )
    return [application_response(item, resume) for item in applications]


@router.post(
    "/job-applications",
    response_model=ApplicationResponse,
    status_code=201,
    dependencies=[Depends(require_csrf)],
)
def create_application(body: ApplicationCreate, user: AuthenticatedUser, db: Db):
    existing = db.scalar(
        select(JobApplication.id).where(
            JobApplication.user_id == user.id,
            JobApplication.job_url == body.job_url,
        )
    )
    if existing:
        raise HTTPException(status_code=409, detail="This listing is already saved")
    application = JobApplication(
        user_id=user.id,
        provider=body.provider,
        title=body.title.strip(),
        company_name=body.company_name.strip(),
        location=body.location.strip(),
        job_url=body.job_url,
        description=body.description,
    )
    db.add(application)
    db.commit()
    db.refresh(application)
    return application_response(application, _resume_for_user(db, user.id))


@router.patch(
    "/job-applications/{application_id}",
    response_model=ApplicationResponse,
    dependencies=[Depends(require_csrf)],
)
def update_application(
    application_id: str, body: ApplicationUpdate, user: AuthenticatedUser, db: Db
):
    application = _application(db, user.id, application_id)
    changes = body.model_dump(exclude_unset=True)
    if not changes:
        raise HTTPException(status_code=422, detail="Provide at least one application field")
    for field, value in changes.items():
        setattr(application, field, value)
    db.commit()
    db.refresh(application)
    return application_response(application, _resume_for_user(db, user.id))


@router.delete(
    "/job-applications/{application_id}",
    status_code=204,
    dependencies=[Depends(require_csrf)],
)
def delete_application(application_id: str, user: AuthenticatedUser, db: Db):
    db.delete(_application(db, user.id, application_id))
    db.commit()


@router.get(
    "/job-applications/{application_id}/practice",
    response_model=list[PracticeResponse],
)
def list_practice(application_id: str, user: AuthenticatedUser, db: Db):
    _application(db, user.id, application_id)
    return list(
        db.scalars(
            select(InterviewPractice)
            .join(JobApplication)
            .where(
                InterviewPractice.application_id == application_id,
                JobApplication.user_id == user.id,
            )
            .order_by(InterviewPractice.year.desc(), InterviewPractice.created_at.desc())
        )
    )


@router.post(
    "/job-applications/{application_id}/practice",
    response_model=PracticeResponse,
    status_code=201,
    dependencies=[Depends(require_csrf)],
)
def create_practice(application_id: str, body: PracticeCreate, user: AuthenticatedUser, db: Db):
    _application(db, user.id, application_id)
    practice = InterviewPractice(
        application_id=application_id,
        **body.model_dump(),
    )
    db.add(practice)
    db.commit()
    db.refresh(practice)
    return practice


@router.patch(
    "/job-applications/{application_id}/practice/{practice_id}",
    response_model=PracticeResponse,
    dependencies=[Depends(require_csrf)],
)
def update_practice(
    application_id: str,
    practice_id: str,
    body: PracticeUpdate,
    user: AuthenticatedUser,
    db: Db,
):
    _application(db, user.id, application_id)
    practice = db.scalar(
        select(InterviewPractice)
        .join(JobApplication)
        .where(
            InterviewPractice.id == practice_id,
            InterviewPractice.application_id == application_id,
            JobApplication.user_id == user.id,
        )
    )
    if practice is None:
        raise HTTPException(status_code=404, detail="Practice question not found")
    changes = body.model_dump(exclude_unset=True)
    if not changes:
        raise HTTPException(status_code=422, detail="Provide at least one practice field")
    if any(changes.get(field) is None for field in ("category", "prompt") if field in changes):
        raise HTTPException(status_code=422, detail="Question category and prompt cannot be null")
    for field, value in changes.items():
        setattr(practice, field, value)
    db.commit()
    db.refresh(practice)
    return practice


@router.delete(
    "/job-applications/{application_id}/practice/{practice_id}",
    status_code=204,
    dependencies=[Depends(require_csrf)],
)
def delete_practice(application_id: str, practice_id: str, user: AuthenticatedUser, db: Db):
    _application(db, user.id, application_id)
    practice = db.scalar(
        select(InterviewPractice)
        .join(JobApplication)
        .where(
            InterviewPractice.id == practice_id,
            InterviewPractice.application_id == application_id,
            JobApplication.user_id == user.id,
        )
    )
    if practice is None:
        raise HTTPException(status_code=404, detail="Practice question not found")
    db.delete(practice)
    db.commit()


@router.get("/calendar/activity", response_model=ActivityResponse)
def calendar_activity(user: AuthenticatedUser, db: Db, year: int, month: int):
    if year < 1900 or year > 2200 or month < 1 or month > 12:
        raise HTTPException(status_code=422, detail="Choose a valid calendar month")
    timezone = ZoneInfo(user.timezone)
    start_local = datetime.combine(date(year, month, 1), time.min, tzinfo=timezone)
    next_month = date(year + (month == 12), (month % 12) + 1, 1)
    end_local = datetime.combine(next_month, time.min, tzinfo=timezone)
    task_ids = select(Task.id).where(Task.user_id == user.id)
    entries = db.scalars(
        select(TaskHistory).where(
            TaskHistory.task_id.in_(task_ids),
            TaskHistory.new_status == "completed",
            TaskHistory.occurred_at >= start_local.astimezone(UTC),
            TaskHistory.occurred_at < end_local.astimezone(UTC),
        )
    )
    completed_by_day: dict[str, set[str]] = {}
    for entry in entries:
        occurred_at = entry.occurred_at
        if occurred_at.tzinfo is None:
            occurred_at = occurred_at.replace(tzinfo=UTC)
        local_day = occurred_at.astimezone(timezone).date().isoformat()
        completed_by_day.setdefault(local_day, set()).add(entry.task_id)
    counts = {local_day: len(task_ids) for local_day, task_ids in completed_by_day.items()}

    today = datetime.now(timezone).date()
    streak_end = end_local.astimezone(UTC)
    streak_start = start_local.astimezone(UTC) - timedelta(days=366)
    history = db.scalars(
        select(TaskHistory).where(
            TaskHistory.task_id.in_(task_ids),
            TaskHistory.new_status == "completed",
            TaskHistory.occurred_at >= streak_start,
            TaskHistory.occurred_at < streak_end,
        )
    )
    streak_dates = set()
    for entry in history:
        occurred_at = entry.occurred_at
        if occurred_at.tzinfo is None:
            occurred_at = occurred_at.replace(tzinfo=UTC)
        streak_dates.add(occurred_at.astimezone(timezone).date())
    current_streak = 0
    cursor = today if today in streak_dates else today - timedelta(days=1)
    while cursor in streak_dates:
        current_streak += 1
        cursor -= timedelta(days=1)
    longest = 0
    streak = 0
    previous = None
    for active_day in sorted(streak_dates):
        streak = streak + 1 if previous and active_day == previous + timedelta(days=1) else 1
        longest = max(longest, streak)
        previous = active_day
    return ActivityResponse(
        year=year,
        month=month,
        active_days=counts,
        current_streak=current_streak,
        longest_streak=longest,
        completed_tasks=len(set().union(*completed_by_day.values())) if completed_by_day else 0,
    )
