export interface User {
  id: string;
  email: string;
  timezone: string;
}

export interface StudyTask {
  id: string;
  track_id: string | null;
  title: string;
  due_at: string;
  status: "pending" | "in_progress" | "completed" | "blocked" | "archived";
  priority: "low" | "normal" | "high";
  estimated_duration_minutes: number | null;
  notes: string | null;
  completed_at: string | null;
}

export interface PreparationTrack {
  id: string;
  name: string;
  description: string;
  sort_order: number;
  archived_at: string | null;
  created_at: string;
}

export interface TaskHistoryEntry {
  id: string;
  event_type: string;
  previous_status: string | null;
  new_status: string | null;
  details: string | null;
  occurred_at: string;
}

export interface Notification {
  id: string;
  notification_type: string;
  title: string;
  body: string;
  related_resource_type: string | null;
  related_resource_id: string | null;
  scheduled_at: string;
  created_at: string;
  read_at: string | null;
  status: string;
}

export interface Job {
  id: string;
  task_type: string;
  status: string;
  attempt_count: number;
  max_attempts: number;
  scheduled_at: string;
  completed_at: string | null;
  error_message: string | null;
}

export interface JobSource {
  id: string;
  provider: "greenhouse" | "lever" | "link_only";
  company_name: string;
  board_slug: string | null;
  search_url: string | null;
  active: boolean;
  created_at: string;
}

export interface JobSearchFilters {
  keywords: string;
  location: string;
  work_mode: "any" | "remote" | "hybrid" | "onsite";
  minimum_match: number;
}

export interface JobListing {
  provider: string;
  company_name: string;
  title: string;
  location: string;
  job_url: string;
  description: string;
  workplace: string;
  matched_keywords: string[];
  missing_keywords: string[];
  match_score: number | null;
  saved: boolean;
}

export interface JobSearchResponse {
  results: JobListing[];
  source_errors: string[];
  resume_uploaded: boolean;
  listing_count: number;
}

export interface Resume {
  id: string;
  filename: string;
  uploaded_at: string;
  extracted_characters: number;
}

export type ApplicationStatus =
  | "saved"
  | "applying"
  | "applied"
  | "interview"
  | "offer"
  | "rejected"
  | "withdrawn";

export interface JobApplication {
  id: string;
  provider: string;
  title: string;
  company_name: string;
  location: string;
  job_url: string;
  description: string;
  status: ApplicationStatus;
  company_rating: number | null;
  company_notes: string | null;
  company_review_url: string | null;
  created_at: string;
  updated_at: string;
  match_score: number | null;
  matched_keywords: string[];
  missing_keywords: string[];
}

export interface PracticeQuestion {
  id: string;
  application_id: string;
  year: number | null;
  category: string;
  prompt: string;
  review_notes: string | null;
  rating: number | null;
  source_url: string | null;
  created_at: string;
  updated_at: string;
}

export interface CalendarActivity {
  year: number;
  month: number;
  active_days: Record<string, number>;
  current_streak: number;
  longest_streak: number;
  completed_tasks: number;
}

export class ApiError extends Error {
  constructor(message: string, readonly status: number) {
    super(message);
    this.name = "ApiError";
  }
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const isFormData = init.body instanceof FormData;
  const response = await fetch(`/api/v1${path}`, {
    ...init,
    credentials: "include",
    headers: { ...(isFormData ? {} : { "Content-Type": "application/json" }), ...init.headers },
  });
  if (!response.ok) {
    const payload = (await response.json().catch(() => null)) as { detail?: unknown } | null;
    throw new ApiError(readErrorMessage(payload?.detail, response.status), response.status);
  }
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

function readErrorMessage(detail: unknown, status: number): string {
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    const messages = detail.flatMap((issue) => {
      if (typeof issue !== "object" || issue === null) return [];
      const value = issue as { loc?: unknown[]; msg?: unknown };
      if (typeof value.msg !== "string") return [];
      const location = Array.isArray(value.loc) ? value.loc.join(".") : "";
      return [location ? `${location}: ${value.msg}` : value.msg];
    });
    if (messages.length) return messages.join("; ");
  }
  return `Request failed (${status})`;
}

async function csrfHeaders(): Promise<Record<string, string>> {
  const { csrf_token } = await request<{ csrf_token: string }>("/auth/csrf");
  return { "X-CSRF-Token": csrf_token };
}

export const api = {
  me: () => request<User>("/auth/me"),
  login: (email: string, password: string) =>
    request<User>("/auth/login", { method: "POST", body: JSON.stringify({ email, password }) }),
  register: (email: string, password: string, timezone: string) =>
    request<User>("/auth/register", {
      method: "POST",
      body: JSON.stringify({ email, password, timezone }),
    }),
  logout: async () =>
    request<void>("/auth/logout", { method: "POST", headers: await csrfHeaders() }),
  tasks: () => request<StudyTask[]>("/tasks"),
  createTask: async (body: {
    title: string;
    due_at: string;
    remind_before_minutes: number;
    track_id: string | null;
    priority: StudyTask["priority"];
    estimated_duration_minutes: number | null;
    notes: string | null;
  }) =>
    request<StudyTask>("/tasks", {
      method: "POST",
      body: JSON.stringify(body),
      headers: await csrfHeaders(),
    }),
  completeTask: async (id: string) =>
    request<StudyTask>(`/tasks/${id}/complete`, {
      method: "PATCH",
      headers: await csrfHeaders(),
    }),
  updateTask: async (id: string, body: Partial<Pick<StudyTask, "status" | "priority" | "notes" | "track_id" | "estimated_duration_minutes">>) =>
    request<StudyTask>(`/tasks/${id}`, {
      method: "PATCH",
      body: JSON.stringify(body),
      headers: await csrfHeaders(),
    }),
  tracks: (includeArchived = false) =>
    request<PreparationTrack[]>(`/tracks${includeArchived ? "?include_archived=true" : ""}`),
  createTrack: async (body: { name: string; description: string }) =>
    request<PreparationTrack>("/tracks", {
      method: "POST",
      body: JSON.stringify(body),
      headers: await csrfHeaders(),
    }),
  updateTrack: async (id: string, body: Partial<Pick<PreparationTrack, "name" | "description" | "sort_order">>) =>
    request<PreparationTrack>(`/tracks/${id}`, {
      method: "PATCH",
      body: JSON.stringify(body),
      headers: await csrfHeaders(),
    }),
  archiveTrack: async (id: string) =>
    request<PreparationTrack>(`/tracks/${id}/archive`, {
      method: "POST",
      headers: await csrfHeaders(),
    }),
  restoreTrack: async (id: string) =>
    request<PreparationTrack>(`/tracks/${id}/restore`, {
      method: "POST",
      headers: await csrfHeaders(),
    }),
  taskHistory: (id: string) => request<TaskHistoryEntry[]>(`/tasks/${id}/history`),
  notifications: () => request<Notification[]>("/notifications"),
  unreadCount: () => request<{ count: number }>("/notifications/unread-count"),
  markRead: async (id: string) =>
    request<Notification>(`/notifications/${id}/read`, {
      method: "POST",
      headers: await csrfHeaders(),
    }),
  markAllRead: async () =>
    request<void>("/notifications/read-all", {
      method: "POST",
      headers: await csrfHeaders(),
    }),
  jobs: () => request<Job[]>("/jobs"),
  jobSources: () => request<JobSource[]>("/job-sources"),
  createJobSource: async (body: {
    provider: JobSource["provider"];
    company_name: string;
    board_slug: string | null;
    search_url: string | null;
  }) =>
    request<JobSource>("/job-sources", {
      method: "POST",
      body: JSON.stringify(body),
      headers: await csrfHeaders(),
    }),
  deleteJobSource: async (id: string) =>
    request<void>(`/job-sources/${encodeURIComponent(id)}`, {
      method: "DELETE",
      headers: await csrfHeaders(),
    }),
  jobSearchFilters: () => request<JobSearchFilters>("/job-search/filters"),
  updateJobSearchFilters: async (body: JobSearchFilters) =>
    request<JobSearchFilters>("/job-search/filters", {
      method: "PUT",
      body: JSON.stringify(body),
      headers: await csrfHeaders(),
    }),
  searchJobs: () => request<JobSearchResponse>("/job-search"),
  resume: async (): Promise<Resume | null> => {
    try {
      return await request<Resume>("/resume");
    } catch (error) {
      if (error instanceof ApiError && error.status === 404) return null;
      throw error;
    }
  },
  uploadResume: async (file: File) => {
    const body = new FormData();
    body.append("file", file);
    return request<Resume>("/resume", {
      method: "POST",
      body,
      headers: await csrfHeaders(),
    });
  },
  deleteResume: async () =>
    request<void>("/resume", { method: "DELETE", headers: await csrfHeaders() }),
  applications: () => request<JobApplication[]>("/job-applications"),
  createApplication: async (body: Pick<
    JobApplication,
    "provider" | "title" | "company_name" | "location" | "job_url" | "description"
  >) =>
    request<JobApplication>("/job-applications", {
      method: "POST",
      body: JSON.stringify(body),
      headers: await csrfHeaders(),
    }),
  updateApplication: async (
    id: string,
    body: Partial<Pick<
      JobApplication,
      "status" | "company_rating" | "company_notes" | "company_review_url"
    >>,
  ) =>
    request<JobApplication>(`/job-applications/${encodeURIComponent(id)}`, {
      method: "PATCH",
      body: JSON.stringify(body),
      headers: await csrfHeaders(),
    }),
  deleteApplication: async (id: string) =>
    request<void>(`/job-applications/${encodeURIComponent(id)}`, {
      method: "DELETE",
      headers: await csrfHeaders(),
    }),
  practiceQuestions: (applicationId: string) =>
    request<PracticeQuestion[]>(
      `/job-applications/${encodeURIComponent(applicationId)}/practice`,
    ),
  createPracticeQuestion: async (
    applicationId: string,
    body: Pick<PracticeQuestion, "year" | "category" | "prompt" | "review_notes" | "rating" | "source_url">,
  ) =>
    request<PracticeQuestion>(
      `/job-applications/${encodeURIComponent(applicationId)}/practice`,
      {
        method: "POST",
        body: JSON.stringify(body),
        headers: await csrfHeaders(),
      },
    ),
  updatePracticeQuestion: async (
    applicationId: string,
    questionId: string,
    body: Partial<
      Pick<PracticeQuestion, "year" | "category" | "prompt" | "review_notes" | "rating" | "source_url">
    >,
  ) =>
    request<PracticeQuestion>(
      `/job-applications/${encodeURIComponent(applicationId)}/practice/${encodeURIComponent(questionId)}`,
      {
        method: "PATCH",
        body: JSON.stringify(body),
        headers: await csrfHeaders(),
      },
    ),
  deletePracticeQuestion: async (applicationId: string, questionId: string) =>
    request<void>(
      `/job-applications/${encodeURIComponent(applicationId)}/practice/${encodeURIComponent(questionId)}`,
      { method: "DELETE", headers: await csrfHeaders() },
    ),
  calendarActivity: (year: number, month: number) =>
    request<CalendarActivity>(`/calendar/activity?year=${year}&month=${month}`),
};
