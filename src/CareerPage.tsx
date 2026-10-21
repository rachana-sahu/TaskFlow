import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  BriefcaseBusiness,
  ExternalLink,
  FileText,
  Plus,
  Search,
  ShieldCheck,
  Star,
  Trash2,
  Upload,
} from "lucide-react";
import {
  api,
  type ApplicationStatus,
  type JobApplication,
  type JobListing,
  type JobSearchFilters,
  type JobSource,
  type PracticeQuestion,
} from "./api";

const emptyFilters: JobSearchFilters = {
  keywords: "",
  location: "",
  work_mode: "any",
  minimum_match: 0,
};

const statusOptions: { value: ApplicationStatus; label: string }[] = [
  { value: "saved", label: "Saved" },
  { value: "applying", label: "Preparing to apply" },
  { value: "applied", label: "Applied" },
  { value: "interview", label: "Interview" },
  { value: "offer", label: "Offer" },
  { value: "rejected", label: "Not moving forward" },
  { value: "withdrawn", label: "Withdrawn" },
];

export default function CareerPage() {
  const queryClient = useQueryClient();
  const sourcesQuery = useQuery({ queryKey: ["job-sources"], queryFn: api.jobSources });
  const filtersQuery = useQuery({
    queryKey: ["job-search-filters"],
    queryFn: api.jobSearchFilters,
  });
  const resumeQuery = useQuery({ queryKey: ["resume"], queryFn: api.resume, retry: false });
  const applicationsQuery = useQuery({
    queryKey: ["job-applications"],
    queryFn: api.applications,
  });
  const searchQuery = useQuery({
    queryKey: ["job-search"],
    queryFn: api.searchJobs,
    enabled: false,
  });
  const [filters, setFilters] = useState<JobSearchFilters>(emptyFilters);
  const [sourceProvider, setSourceProvider] = useState<JobSource["provider"]>("greenhouse");
  const [companyName, setCompanyName] = useState("");
  const [boardSlug, setBoardSlug] = useState("");
  const [searchUrl, setSearchUrl] = useState("");
  const [selectedResume, setSelectedResume] = useState<File | null>(null);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  useEffect(() => {
    if (filtersQuery.data) setFilters(filtersQuery.data);
  }, [filtersQuery.data]);

  const refresh = () => {
    void queryClient.invalidateQueries({ queryKey: ["job-sources"] });
    void queryClient.invalidateQueries({ queryKey: ["job-applications"] });
    void queryClient.invalidateQueries({ queryKey: ["resume"] });
    void queryClient.invalidateQueries({ queryKey: ["job-search"] });
  };
  const addSource = useMutation({
    mutationFn: api.createJobSource,
    onSuccess: () => {
      setCompanyName("");
      setBoardSlug("");
      setSearchUrl("");
      setError("");
      refresh();
    },
    onError: (caught) => setError(caught.message),
  });
  const removeSource = useMutation({
    mutationFn: api.deleteJobSource,
    onSuccess: refresh,
    onError: (caught) => setError(caught.message),
  });
  const saveFilters = useMutation({
    mutationFn: api.updateJobSearchFilters,
    onSuccess: async () => {
      setError("");
      setNotice("Your search filters are saved.");
      await queryClient.invalidateQueries({ queryKey: ["job-search-filters"] });
      await queryClient.invalidateQueries({ queryKey: ["job-search"] });
    },
    onError: (caught) => setError(caught.message),
  });
  const uploadResume = useMutation({
    mutationFn: api.uploadResume,
    onSuccess: () => {
      setSelectedResume(null);
      setError("");
      setNotice("Resume stored privately and ready for matching.");
      refresh();
    },
    onError: (caught) => setError(caught.message),
  });
  const deleteResume = useMutation({
    mutationFn: api.deleteResume,
    onSuccess: () => {
      setNotice("Resume removed. Job matches no longer use it.");
      refresh();
    },
    onError: (caught) => setError(caught.message),
  });
  const saveJob = useMutation({
    mutationFn: api.createApplication,
    onSuccess: () => {
      setNotice("Job saved to your application tracker.");
      setError("");
      refresh();
    },
    onError: (caught) => setError(caught.message),
  });
  const updateApplication = useMutation({
    mutationFn: ({ id, fields }: {
      id: string;
      fields: Partial<Pick<JobApplication, "status" | "company_rating" | "company_notes" | "company_review_url">>;
    }) => api.updateApplication(id, fields),
    onSuccess: () => {
      setError("");
      refresh();
    },
    onError: (caught) => setError(caught.message),
  });
  const deleteApplication = useMutation({
    mutationFn: api.deleteApplication,
    onSuccess: refresh,
    onError: (caught) => setError(caught.message),
  });

  const submitSource = (event: React.FormEvent) => {
    event.preventDefault();
    setError("");
    addSource.mutate({
      provider: sourceProvider,
      company_name: companyName.trim(),
      board_slug: sourceProvider === "link_only" ? null : boardSlug.trim(),
      search_url: sourceProvider === "link_only" ? searchUrl.trim() : null,
    });
  };
  const applications = applicationsQuery.data ?? [];
  const sources = sourcesQuery.data ?? [];
  const resume = resumeQuery.data;

  return <>
    <div className="page-heading">
      <div><span className="eyebrow">YOUR NEXT OPPORTUNITY</span><h1>Find your <em>fit.</em></h1>
        <p>Search connected company boards, compare role keywords, and keep each application ready.</p></div>
      <span className="live-pill"><span /> ACCOUNT-SCOPED</span>
    </div>
    {error && <div className="error-banner" role="alert"><span />{error}</div>}
    {notice && <div className="success-banner" role="status">{notice}<button aria-label="Dismiss notice" onClick={() => setNotice("")}>×</button></div>}

    <section className="panel career-resume">
      <div className="career-panel-title"><span className="career-icon"><FileText size={18} /></span>
        <div><span className="eyebrow">PRIVATE RESUME MATCHING</span><h2>Bring your experience.</h2></div>
      </div>
      <div className="resume-upload-row">
        <div className="resume-file-summary">
          {resumeQuery.isPending ? <span className="muted">Checking saved resume…</span> : resume ?
            <><b>{resume.filename}</b><small>{resume.extracted_characters.toLocaleString()} readable characters · saved privately to your account</small></> :
            resumeQuery.isError ?
              <span className="field-error">Saved resume could not be checked.</span> :
              <span className="muted">No resume uploaded. Add a PDF, DOCX, or text resume to see keyword overlap.</span>}
        </div>
        <label className="button button-secondary resume-picker"><Upload size={15} />{resume ? "Replace resume" : "Choose resume"}
          <input type="file" accept=".pdf,.docx,.txt" onChange={(event) => setSelectedResume(event.target.files?.[0] ?? null)} />
        </label>
        {selectedResume && <button className="button button-primary" disabled={uploadResume.isPending} onClick={() => uploadResume.mutate(selectedResume)}>{uploadResume.isPending ? "Reading…" : "Upload securely"}</button>}
        {resume && <button className="text-link danger-link" disabled={deleteResume.isPending} onClick={() => deleteResume.mutate()}>Remove</button>}
      </div>
      <p className="privacy-note"><ShieldCheck size={13} /> Only your account can access the stored file. Matching is a local keyword comparison, not a hiring prediction.</p>
    </section>

    <div className="career-layout">
      <section className="career-main">
        <section className="panel full-panel">
          <div className="panel-heading">
            <div><span className="eyebrow">CUSTOMIZABLE SEARCH</span><h2>What are you looking for?</h2></div>
            <button className="button button-secondary" disabled={searchQuery.isFetching || sources.length === 0} onClick={() => { setError(""); void searchQuery.refetch(); }}>
              <Search size={14} />{searchQuery.isFetching ? "Searching…" : "Search boards"}
            </button>
          </div>
          <form className="career-filter-form" onSubmit={(event) => { event.preventDefault(); saveFilters.mutate(filters); }}>
            <label>Keywords <small>comma-separated</small><input value={filters.keywords} placeholder="Python, platform engineer" onChange={(event) => setFilters({ ...filters, keywords: event.target.value })} /></label>
            <label>Location<input value={filters.location} placeholder="Remote, India, Bengaluru…" onChange={(event) => setFilters({ ...filters, location: event.target.value })} /></label>
            <label>Work mode<select value={filters.work_mode} onChange={(event) => setFilters({ ...filters, work_mode: event.target.value as JobSearchFilters["work_mode"] })}>
              <option value="any">Any work mode</option><option value="remote">Remote</option><option value="hybrid">Hybrid</option><option value="onsite">On-site</option>
            </select></label>
            <label>Minimum resume match <small>{filters.minimum_match}%</small><input type="range" min="0" max="100" step="5" value={filters.minimum_match} onChange={(event) => setFilters({ ...filters, minimum_match: Number(event.target.value) })} /></label>
            <button className="button button-primary" disabled={saveFilters.isPending}>{saveFilters.isPending ? "Saving…" : "Save filters"}</button>
          </form>
          {filtersQuery.isError && <p className="field-error">Saved search filters could not be loaded.</p>}
        </section>

        <section className="panel full-panel">
          <div className="panel-heading"><div><span className="eyebrow">LIVE BOARD RESULTS</span><h2>{searchQuery.data ? `${searchQuery.data.listing_count} matching roles` : "Connected listings"}</h2></div></div>
          {searchQuery.isError && <div className="error-banner" role="alert"><span />Listings could not be loaded. Check the configured public board IDs and try again.</div>}
          {searchQuery.data?.source_errors.map((message) => <div className="source-warning" role="status" key={message}>{message}</div>)}
          {searchQuery.data?.results.length ? <div className="listing-list">{searchQuery.data.results.map((listing) =>
            <ListingCard key={`${listing.provider}-${listing.job_url}`} listing={listing}
              onSave={() => saveJob.mutate({
                provider: listing.provider,
                title: listing.title,
                company_name: listing.company_name,
                location: listing.location,
                job_url: listing.job_url,
                description: listing.description,
              })} saving={saveJob.isPending} />,
          )}</div> : searchQuery.isFetching ? <div className="skeleton-stack" aria-label="Loading listings"><i /><i /><i /></div> :
            <div className="career-empty"><span><BriefcaseBusiness size={19} /></span><b>No search results yet.</b><p>Add one or more company boards, choose your filters, then search. Custom platform links open on their source site.</p></div>}
        </section>
      </section>

      <aside className="career-aside">
        <section className="panel source-panel">
          <div className="panel-heading"><div><span className="eyebrow">JOB PLATFORMS</span><h2>Connect a source</h2></div></div>
          <p className="muted">Live listings are available for public Greenhouse and Lever boards. Other platforms are saved as search links.</p>
          <form className="source-form" onSubmit={submitSource}>
            <label>Platform<select value={sourceProvider} onChange={(event) => setSourceProvider(event.target.value as JobSource["provider"])}>
              <option value="greenhouse">Greenhouse public board</option><option value="lever">Lever public board</option><option value="link_only">Custom platform link</option>
            </select></label>
            <label>Company / source name<input required maxLength={120} value={companyName} onChange={(event) => setCompanyName(event.target.value)} placeholder="e.g. Example Labs" /></label>
            {sourceProvider === "link_only" ?
              <label>Job search URL<input required type="url" value={searchUrl} onChange={(event) => setSearchUrl(event.target.value)} placeholder="https://…" /></label> :
              <label>Public board ID<input required maxLength={120} value={boardSlug} onChange={(event) => setBoardSlug(event.target.value)} placeholder={sourceProvider === "greenhouse" ? "company-board-slug" : "company-site-name"} /></label>}
            <button className="button button-secondary" disabled={addSource.isPending}><Plus size={14} />{addSource.isPending ? "Connecting…" : "Add source"}</button>
          </form>
          {sourcesQuery.isError && <p className="field-error">Connected job sources could not be loaded.</p>}
          <div className="source-list">{sources.map((source) => <div className="source-row" key={source.id}>
            <span className={`provider-mark provider-${source.provider}`}>{source.provider === "link_only" ? "↗" : source.provider.slice(0, 1).toUpperCase()}</span>
            <span><b>{source.company_name}</b><small>{source.provider === "link_only" ? "External search link only" : `${source.provider} · ${source.board_slug}`}</small></span>
            {source.search_url && <a className="icon-button" href={source.search_url} target="_blank" rel="noreferrer" aria-label={`Open ${source.company_name} job search`}><ExternalLink size={13} /></a>}
            <button className="icon-button" aria-label={`Remove ${source.company_name}`} title="Remove source" disabled={removeSource.isPending} onClick={() => removeSource.mutate(source.id)}><Trash2 size={13} /></button>
          </div>)}</div>
        </section>
      </aside>
    </div>

    <section className="panel full-panel applications-panel">
      <div className="panel-heading"><div><span className="eyebrow">APPLICATION PIPELINE</span><h2>{applications.length} saved {applications.length === 1 ? "role" : "roles"}</h2></div></div>
      {applicationsQuery.isPending ? <div className="skeleton-stack" aria-label="Loading saved applications"><i /><i /></div> :
        applicationsQuery.isError ? <div className="career-empty"><b>Application tracker unavailable.</b><p>Saved roles could not be loaded. Refresh to try again.</p></div> :
          applications.length ? <div className="application-grid">{applications.map((application) =>
            <ApplicationCard key={application.id} application={application}
              onUpdate={(fields) => updateApplication.mutate({ id: application.id, fields })}
              onDelete={() => deleteApplication.mutate(application.id)} />,
          )}</div> :
            <div className="career-empty"><span><BriefcaseBusiness size={19} /></span><b>Your application tracker is ready.</b><p>Save a listing to track its status, practice for the interview, and keep your own company notes and rating.</p></div>}
    </section>
  </>;
}

function ListingCard({ listing, onSave, saving }: { listing: JobListing; onSave: () => void; saving: boolean }) {
  return <article className="listing-card">
    <div className="listing-title-row"><div><span className="listing-company">{listing.company_name} · {listing.provider}</span><h3>{listing.title}</h3><small>{listing.location || "Location not listed"} · {listing.workplace}</small></div>
      {listing.match_score !== null && <span className="match-score"><b>{listing.match_score}%</b><small>keyword match</small></span>}</div>
    {listing.match_score !== null && <MatchMatrix matched={listing.matched_keywords} missing={listing.missing_keywords} />}
    <div className="listing-actions"><a className="text-link" href={listing.job_url} target="_blank" rel="noreferrer">View listing <ExternalLink size={13} /></a>
      <button className="button button-secondary" disabled={listing.saved || saving} onClick={onSave}>{listing.saved ? "Saved" : <><Plus size={14} /> Save role</>}</button></div>
  </article>;
}

function MatchMatrix({ matched, missing }: { matched: string[]; missing: string[] }) {
  if (!matched.length && !missing.length) return null;
  return <div className="match-matrix" aria-label="Resume keyword comparison">
    <span>RESUME MATCH MATRIX</span><div className="match-keywords">
      {matched.map((term) => <span className="keyword-present" key={`match-${term}`}>✓ {term}</span>)}
      {missing.map((term) => <span className="keyword-gap" key={`gap-${term}`}>+ {term}</span>)}
    </div>
  </div>;
}

function ApplicationCard({ application, onUpdate, onDelete }: {
  application: JobApplication;
  onUpdate: (fields: Partial<Pick<JobApplication, "status" | "company_rating" | "company_notes" | "company_review_url">>) => void;
  onDelete: () => void;
}) {
  const [notes, setNotes] = useState(application.company_notes ?? "");
  const [reviewUrl, setReviewUrl] = useState(application.company_review_url ?? "");
  const [practiceOpen, setPracticeOpen] = useState(false);
  const questionsQuery = useQuery({
    queryKey: ["practice", application.id],
    queryFn: () => api.practiceQuestions(application.id),
    enabled: practiceOpen,
  });
  useEffect(() => {
    setNotes(application.company_notes ?? "");
    setReviewUrl(application.company_review_url ?? "");
  }, [application.id, application.company_notes, application.company_review_url]);
  return <article className="application-card">
    <div className="application-card-head"><div><span className="listing-company">{application.company_name} · {application.location || "Location not listed"}</span><h3>{application.title}</h3></div>
      {application.match_score !== null && <span className="application-match">{application.match_score}% match</span>}</div>
    {application.match_score !== null && <MatchMatrix matched={application.matched_keywords} missing={application.missing_keywords} />}
    <div className="application-controls">
      <label>Application status<select aria-label={`Status for ${application.title}`} value={application.status} onChange={(event) => onUpdate({ status: event.target.value as ApplicationStatus })}>
        {statusOptions.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}
      </select></label>
      <label>Company rating<select aria-label={`Company rating for ${application.company_name}`} value={application.company_rating ?? ""} onChange={(event) => onUpdate({ company_rating: event.target.value ? Number(event.target.value) : null })}>
        <option value="">Not rated</option>{[1, 2, 3, 4, 5].map((rating) => <option key={rating} value={rating}>{rating} / 5</option>)}
      </select></label>
      <a className="text-link" href={application.job_url} target="_blank" rel="noreferrer">Open listing <ExternalLink size={12} /></a>
    </div>
    <details className="company-review">
      <summary><Star size={13} /> Company notes &amp; review link</summary>
      <label>Your own notes<textarea value={notes} maxLength={10000} onChange={(event) => setNotes(event.target.value)} onBlur={() => { if (notes !== (application.company_notes ?? "")) onUpdate({ company_notes: notes }); }} placeholder="Add your own interview or company notes…" /></label>
      <label>AmbitionBox review URL<input type="url" value={reviewUrl} onChange={(event) => setReviewUrl(event.target.value)} onBlur={() => { if (reviewUrl !== (application.company_review_url ?? "")) onUpdate({ company_review_url: reviewUrl || null }); }} placeholder="https://www.ambitionbox.com/…" /></label>
      {application.company_review_url && <a className="text-link" href={application.company_review_url} target="_blank" rel="noreferrer">Open your linked review <ExternalLink size={12} /></a>}
    </details>
    <div className="practice-header"><div><span className="eyebrow">ROLE-SPECIFIC PREP</span><h4>Interview practice</h4></div>
      <button className="text-link" aria-expanded={practiceOpen} onClick={() => setPracticeOpen(!practiceOpen)}>{practiceOpen ? "Hide practice" : "Open practice"}</button></div>
    {practiceOpen && <PracticePanel applicationId={application.id} questions={questionsQuery.data ?? []} loading={questionsQuery.isPending} error={questionsQuery.isError} />}
    <div className="application-footer"><span>Questions, ratings, and notes you add are private and user-authored.</span><button className="text-link danger-link" onClick={onDelete}>Remove role</button></div>
  </article>;
}

function PracticePanel({ applicationId, questions, loading, error }: {
  applicationId: string;
  questions: PracticeQuestion[];
  loading: boolean;
  error: boolean;
}) {
  const queryClient = useQueryClient();
  const [year, setYear] = useState("");
  const [category, setCategory] = useState("Technical");
  const [prompt, setPrompt] = useState("");
  const [sourceUrl, setSourceUrl] = useState("");
  const [formError, setFormError] = useState("");
  const create = useMutation({
    mutationFn: ({ body }: { body: Parameters<typeof api.createPracticeQuestion>[1] }) =>
      api.createPracticeQuestion(applicationId, body),
    onSuccess: async () => {
      setPrompt("");
      setSourceUrl("");
      setFormError("");
      await queryClient.invalidateQueries({ queryKey: ["practice", applicationId] });
    },
    onError: (caught) => setFormError(caught.message),
  });
  const update = useMutation({
    mutationFn: ({ id, fields }: { id: string; fields: Partial<PracticeQuestion> }) =>
      api.updatePracticeQuestion(applicationId, id, fields),
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: ["practice", applicationId] }),
    onError: (caught) => setFormError(caught.message),
  });
  const remove = useMutation({
    mutationFn: (id: string) => api.deletePracticeQuestion(applicationId, id),
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: ["practice", applicationId] }),
    onError: (caught) => setFormError(caught.message),
  });
  return <div className="practice-panel">
    <p className="practice-disclaimer">Add questions in your own words or save a link to the original source. We do not import or reproduce AmbitionBox question/review content.</p>
    <form className="practice-form" onSubmit={(event) => {
      event.preventDefault();
      create.mutate({
        body: {
          year: year ? Number(year) : null,
          category,
          prompt: prompt.trim(),
          review_notes: null,
          rating: null,
          source_url: sourceUrl.trim() || null,
        },
      });
    }}>
      <label>Year<input type="number" min="1900" max="2200" value={year} onChange={(event) => setYear(event.target.value)} placeholder="Previous year" /></label>
      <label>Topic<input maxLength={100} value={category} onChange={(event) => setCategory(event.target.value)} /></label>
      <label className="practice-prompt">Question or prompt<textarea required maxLength={10000} value={prompt} onChange={(event) => setPrompt(event.target.value)} placeholder="Write a practice question in your own words…" /></label>
      <label className="practice-prompt">AmbitionBox source link<input type="url" value={sourceUrl} onChange={(event) => setSourceUrl(event.target.value)} placeholder="Optional link to the source page" /></label>
      {formError && <span className="field-error">{formError}</span>}
      <button className="button button-secondary" disabled={create.isPending || !prompt.trim()}><Plus size={13} />{create.isPending ? "Adding…" : "Add practice question"}</button>
    </form>
    {loading ? <div className="skeleton-stack" aria-label="Loading interview practice"><i /><i /></div> : error ? <p className="field-error">Practice questions could not be loaded.</p> :
      questions.length ? <div className="practice-list">{questions.map((question) => <PracticeCard key={question.id} question={question} onUpdate={(fields) => update.mutate({ id: question.id, fields })} onDelete={() => remove.mutate(question.id)} />)}</div> :
        <p className="practice-empty">No practice questions saved for this role yet.</p>}
  </div>;
}

function PracticeCard({ question, onUpdate, onDelete }: {
  question: PracticeQuestion;
  onUpdate: (fields: Partial<PracticeQuestion>) => void;
  onDelete: () => void;
}) {
  const [notes, setNotes] = useState(question.review_notes ?? "");
  useEffect(() => setNotes(question.review_notes ?? ""), [question.id, question.review_notes]);
  return <article className="practice-question">
    <div className="practice-question-title"><span>{question.year ?? "Practice"} · {question.category}</span><button className="icon-button" aria-label="Remove practice question" onClick={onDelete}><Trash2 size={13} /></button></div>
    <p>{question.prompt}</p>
    {question.source_url && <a className="text-link" href={question.source_url} target="_blank" rel="noreferrer">Open original AmbitionBox page <ExternalLink size={12} /></a>}
    <div className="practice-review-fields">
      <label>Your review / answer notes<textarea value={notes} onChange={(event) => setNotes(event.target.value)} onBlur={() => { if (notes !== (question.review_notes ?? "")) onUpdate({ review_notes: notes }); }} maxLength={10000} placeholder="How did your answer go?" /></label>
      <label>Practice rating<select aria-label={`Rating for ${question.category} question`} value={question.rating ?? ""} onChange={(event) => onUpdate({ rating: event.target.value ? Number(event.target.value) : null })}>
        <option value="">Rate later</option>{[1, 2, 3, 4, 5].map((rating) => <option key={rating} value={rating}>{rating} / 5</option>)}
      </select></label>
    </div>
  </article>;
}
