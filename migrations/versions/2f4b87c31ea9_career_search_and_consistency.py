"""Career search, resume matching, practice reviews, and calendar activity.

Revision ID: 2f4b87c31ea9
Revises: bd9de18f412d
Create Date: 2026-10-14
"""

import sqlalchemy as sa
from alembic import op

revision = "2f4b87c31ea9"
down_revision = "bd9de18f412d"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "job_board_sources",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("provider", sa.String(length=20), nullable=False),
        sa.Column("company_name", sa.String(length=120), nullable=False),
        sa.Column("board_slug", sa.String(length=120), nullable=True),
        sa.Column("search_url", sa.String(length=1000), nullable=True),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "provider IN ('greenhouse', 'lever', 'link_only')",
            name="ck_job_board_sources_provider",
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_job_board_sources_user_id"), "job_board_sources", ["user_id"], unique=False
    )
    op.create_table(
        "job_search_filters",
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("keywords", sa.String(length=300), nullable=False),
        sa.Column("location", sa.String(length=180), nullable=False),
        sa.Column("work_mode", sa.String(length=20), nullable=False),
        sa.Column("minimum_match", sa.Integer(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("user_id"),
    )
    op.create_table(
        "resume_documents",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("filename", sa.String(length=255), nullable=False),
        sa.Column("storage_key", sa.String(length=80), nullable=False),
        sa.Column("extracted_text", sa.Text(), nullable=False),
        sa.Column("uploaded_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("storage_key"),
        sa.UniqueConstraint("user_id", name="uq_resume_documents_user"),
    )
    op.create_index(
        op.f("ix_resume_documents_user_id"), "resume_documents", ["user_id"], unique=False
    )
    op.create_table(
        "job_applications",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("provider", sa.String(length=20), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("company_name", sa.String(length=180), nullable=False),
        sa.Column("location", sa.String(length=180), nullable=False),
        sa.Column("job_url", sa.String(length=1000), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("company_rating", sa.Integer(), nullable=True),
        sa.Column("company_notes", sa.Text(), nullable=True),
        sa.Column("company_review_url", sa.String(length=1000), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "status IN "
            "('saved', 'applying', 'applied', 'interview', 'offer', 'rejected', 'withdrawn')",
            name="ck_job_applications_status",
        ),
        sa.CheckConstraint(
            "company_rating IS NULL OR company_rating BETWEEN 1 AND 5",
            name="ck_job_applications_company_rating",
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "job_url", name="uq_job_applications_user_url"),
    )
    op.create_index(
        op.f("ix_job_applications_user_id"), "job_applications", ["user_id"], unique=False
    )
    op.create_table(
        "interview_practice",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("application_id", sa.String(length=36), nullable=False),
        sa.Column("year", sa.Integer(), nullable=True),
        sa.Column("category", sa.String(length=100), nullable=False),
        sa.Column("prompt", sa.Text(), nullable=False),
        sa.Column("review_notes", sa.Text(), nullable=True),
        sa.Column("rating", sa.Integer(), nullable=True),
        sa.Column("source_url", sa.String(length=1000), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "rating IS NULL OR rating BETWEEN 1 AND 5",
            name="ck_interview_practice_rating",
        ),
        sa.CheckConstraint(
            "year IS NULL OR year BETWEEN 1900 AND 2200", name="ck_interview_practice_year"
        ),
        sa.ForeignKeyConstraint(["application_id"], ["job_applications.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_interview_practice_application_id"),
        "interview_practice",
        ["application_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_interview_practice_application_id"), table_name="interview_practice")
    op.drop_table("interview_practice")
    op.drop_index(op.f("ix_job_applications_user_id"), table_name="job_applications")
    op.drop_table("job_applications")
    op.drop_index(op.f("ix_resume_documents_user_id"), table_name="resume_documents")
    op.drop_table("resume_documents")
    op.drop_table("job_search_filters")
    op.drop_index(op.f("ix_job_board_sources_user_id"), table_name="job_board_sources")
    op.drop_table("job_board_sources")
