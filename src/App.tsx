import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { zodResolver } from "@hookform/resolvers/zod";
import {
  Bell,
  BookOpen,
  Check,
  CheckCheck,
  ChevronRight,
  CircleHelp,
  Clock3,
  Command,
  CornerUpLeft,
  ArrowDown,
  ArrowUp,
  BriefcaseBusiness,
  CalendarDays,
  Flame,
  LayoutDashboard,
  ListTodo,
  LogOut,
  Menu,
  Pencil,
  Plus,
  Radio,
  Archive,
  Sparkles,
  X,
} from "lucide-react";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { api, ApiError, type Job, type Notification as AppNotification, type PreparationTrack, type StudyTask, type User } from "./api";
import CareerPage from "./CareerPage";
import CalendarPage from "./CalendarPage";
import { getRegistrationTimezone } from "./timezone";

type Page = "overview" | "tracks" | "tasks" | "career" | "calendar" | "notifications" | "jobs";
const taskSchema = z.object({
  title: z.string().trim().min(1, "Add a short title").max(180),
  due_at: z.string().min(1, "Choose a deadline"),
  remind_before_minutes: z.coerce.number().int().min(0).max(10080),
  track_id: z.string(),
  priority: z.enum(["low", "normal", "high"]),
  estimated_duration_minutes: z.coerce.number().int().min(0).max(1440),
  notes: z.string().max(10000),
});
type TaskFields = z.infer<typeof taskSchema>;

function App() {
  const queryClient = useQueryClient();
  const location = useLocation();
  const navigate = useNavigate();
  const [page, setPage] = useState<Page>(pageFromPath(location.pathname));
  const [menuOpen, setMenuOpen] = useState(false);
  const [taskFormOpen, setTaskFormOpen] = useState(false);
  const userQuery = useQuery({ queryKey: ["me"], queryFn: api.me, retry: false });
  const logout = useMutation({ mutationFn: api.logout, onSuccess: () => {
    queryClient.clear();
    navigate("/");
  } });
  const user = userQuery.data;

  useEffect(() => setPage(pageFromPath(location.pathname)), [location.pathname]);
  const navigateTo = (next: Page) => {
    setPage(next);
    navigate(next === "overview" ? "/" : `/${next}`);
    setMenuOpen(false);
  };

  const refresh = () => {
    void queryClient.invalidateQueries();
  };

  if (userQuery.isPending) {
    return <div className="launch-state"><BrandMark /><span>Opening your workspace</span></div>;
  }
  if (userQuery.isError && !(userQuery.error instanceof ApiError && userQuery.error.status === 401)) {
    return <div className="connection-state"><BrandMark /><h1>Workspace unavailable</h1><p>{userQuery.error.message}</p><button className="button button-secondary" onClick={() => void userQuery.refetch()}>Try again</button></div>;
  }
  if (!user) {
    return <AuthScreen onAuthenticated={() => void queryClient.invalidateQueries({ queryKey: ["me"] })} />;
  }

  return (
    <div className="app-shell">
      <aside className={`sidebar ${menuOpen ? "sidebar-open" : ""}`}>
        <Link className="brand" to="/" onClick={() => navigateTo("overview")}>
          <BrandMark />
          <span>taskflow<span className="brand-sub">PREP</span></span>
        </Link>
        <div className="workspace-label">YOUR WORKSPACE</div>
        <nav className="side-nav" aria-label="Main navigation">
          <NavItem active={page === "overview"} icon={<LayoutDashboard size={17} />} label="Overview" onClick={() => navigateTo("overview")} />
          <NavItem active={page === "tracks"} icon={<BookOpen size={17} />} label="Preparation tracks" onClick={() => navigateTo("tracks")} />
          <NavItem active={page === "tasks"} icon={<ListTodo size={17} />} label="Study tasks" onClick={() => navigateTo("tasks")} />
          <NavItem active={page === "career"} icon={<BriefcaseBusiness size={17} />} label="Job search" onClick={() => navigateTo("career")} />
          <NavItem active={page === "calendar"} icon={<CalendarDays size={17} />} label="Consistency" onClick={() => navigateTo("calendar")} />
          <NavItem active={page === "notifications"} icon={<Bell size={17} />} label="Notifications" badge onClick={() => navigateTo("notifications")} />
          <NavItem active={page === "jobs"} icon={<Radio size={17} />} label="Job runs" onClick={() => navigateTo("jobs")} />
        </nav>
        <div className="sidebar-spacer" />
        <div className="sidebar-note">
          <span className="note-icon"><Sparkles size={15} /></span>
          <p>Small, focused sessions add up.</p>
          <span className="note-caption">One task at a time.</span>
        </div>
        <button className="profile-row" disabled={logout.isPending} onClick={() => logout.mutate()}>
          <span className="avatar">{user.email.slice(0, 1).toUpperCase()}</span>
          <span className="profile-copy"><b>{user.email}</b><small>Personal workspace</small></span>
          <LogOut size={16} />
        </button>
      </aside>
      {menuOpen && <button className="scrim" aria-label="Close navigation" onClick={() => setMenuOpen(false)} />}
      <main className="main-shell">
        <header className="topbar">
          <button className="icon-button mobile-menu" aria-label="Open navigation" onClick={() => setMenuOpen(true)}><Menu size={19} /></button>
          <div className="breadcrumb"><span>Workspace</span><ChevronRight size={13} /><b>{pageTitle(page)}</b></div>
          <div className="top-actions">
            <span className="live-pill"><span /> API CONNECTED</span>
            <button className="icon-button notification-trigger" aria-label="Open notifications" onClick={() => navigateTo("notifications")}><Bell size={18} /><UnreadBadge /></button>
            <span className="top-avatar">{user.email.slice(0, 1).toUpperCase()}</span>
          </div>
        </header>
        <div className="content-wrap">
          {logout.isError && <ErrorBanner message={logout.error.message} />}
          {page === "overview" && <OverviewPage user={user} onAdd={() => setTaskFormOpen(true)} onNavigate={navigateTo} />}
          {page === "tracks" && <TracksPage />}
          {page === "tasks" && <TasksPage onAdd={() => setTaskFormOpen(true)} />}
          {page === "career" && <CareerPage />}
          {page === "calendar" && <CalendarPage />}
          {page === "notifications" && <NotificationsPage />}
          {page === "jobs" && <JobsPage />}
        </div>
        <footer className="app-footer"><span>© TaskFlow Prep</span><span><CircleHelp size={13} /> Built for steady progress</span></footer>
      </main>
      {taskFormOpen && <TaskDialog onClose={() => setTaskFormOpen(false)} onCreated={() => {
        setTaskFormOpen(false);
        refresh();
      }} />}
    </div>
  );
}

function pageFromPath(path: string): Page {
  if (path.startsWith("/tracks")) return "tracks";
  if (path.startsWith("/tasks")) return "tasks";
  if (path.startsWith("/career")) return "career";
  if (path.startsWith("/calendar")) return "calendar";
  if (path.startsWith("/notifications")) return "notifications";
  if (path.startsWith("/jobs")) return "jobs";
  return "overview";
}

function pageTitle(page: Page) {
  return { overview: "Overview", tracks: "Preparation tracks", tasks: "Study tasks", career: "Job search", calendar: "Consistency", notifications: "Notifications", jobs: "Job runs" }[page];
}

function BrandMark() {
  return <span className="brand-mark" aria-hidden="true"><svg viewBox="0 0 36 36" fill="none">
    <path d="M8 12.2c3.8-1.9 7-.8 10 1.3 3-2.1 6.2-3.2 10-1.3v12.3c-3.8-1.8-7-1-10 1.2-3-2.2-6.2-3-10-1.2V12.2Z" fill="white" fillOpacity=".17" stroke="white" strokeWidth="1.55" strokeLinejoin="round" />
    <path d="M18 13.6v12" stroke="white" strokeOpacity=".8" strokeWidth="1.35" />
    <circle cx="14.1" cy="18.3" r="1" fill="white" /><circle cx="21.9" cy="18.3" r="1" fill="white" />
    <path d="M14.8 21.2c1.9 1.5 4.5 1.5 6.4 0" stroke="white" strokeWidth="1.35" strokeLinecap="round" />
    <path d="m8 7 .7 1.8 1.8.7-1.8.7L8 12l-.7-1.8-1.8-.7 1.8-.7L8 7Z" fill="#FFE2A8" />
  </svg></span>;
}

function NavItem({ active, icon, label, badge, onClick }: { active: boolean; icon: React.ReactNode; label: string; badge?: boolean; onClick: () => void }) {
  return <button className={`nav-item ${active ? "nav-active" : ""}`} onClick={onClick}>{icon}<span>{label}</span>{badge && <UnreadBadge />}</button>;
}

function UnreadBadge() {
  const { data, isError } = useQuery({
    queryKey: ["unread-count"],
    queryFn: api.unreadCount,
    retry: false,
    refetchInterval: 15_000,
    refetchOnWindowFocus: true,
  });
  if (isError) return <span className="unread-error" title="Unread count unavailable" aria-label="Unread count unavailable">!</span>;
  if (!data?.count) return null;
  return <span className="unread-badge">{data.count > 99 ? "99+" : data.count}</span>;
}

function AuthScreen({ onAuthenticated }: { onAuthenticated: () => void }) {
  const [isRegister, setIsRegister] = useState(false);
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);
  async function submit(form: FormData) {
    setError("");
    setSubmitting(true);
    const email = String(form.get("email"));
    const password = String(form.get("password"));
    try {
      if (isRegister) await api.register(email, password, getRegistrationTimezone());
      else await api.login(email, password);
      onAuthenticated();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Unable to sign in");
    } finally {
      setSubmitting(false);
    }
  }
  return (
    <div className="auth-layout">
      <section className="auth-story">
        <Link to="/" className="brand auth-brand"><BrandMark /><span>taskflow<span className="brand-sub">PREP</span></span></Link>
        <div className="story-content">
          <span className="eyebrow"><span className="eyebrow-dot" /> A clearer way forward</span>
          <h1>Prepare with<br /><em>purpose.</em></h1>
          <p>Your study plan, deadlines, and reminders—together in one calm workspace.</p>
          <div className="story-proof"><span><Check size={14} /></span> Built around the work you actually plan to do</div>
          <div className="story-lines" aria-hidden="true"><i /><i /><i /><i /></div>
        </div>
        <span className="auth-legal">Your progress is private and yours.</span>
      </section>
      <section className="auth-panel">
        <div className="auth-form-wrap">
          <div className="auth-mobile-brand"><BrandMark /><span>taskflow<span className="brand-sub">PREP</span></span></div>
          <span className="eyebrow">{isRegister ? "START YOUR WORKSPACE" : "WELCOME BACK"}</span>
          <h2>{isRegister ? "Create your account" : "Sign in to focus"}</h2>
          <p className="muted">{isRegister ? "A little structure. A lot more momentum." : "Pick up where your preparation left off."}</p>
          <form onSubmit={(event) => { event.preventDefault(); void submit(new FormData(event.currentTarget)); }} className="auth-form">
            <label>Email address<input name="email" type="email" autoComplete="email" placeholder="you@example.com" required /></label>
            <label>Password<input name="password" type="password" autoComplete={isRegister ? "new-password" : "current-password"} minLength={10} placeholder="At least 10 characters" required /></label>
            {error && <div className="form-error" role="alert">{error}</div>}
            <button className="button button-primary auth-submit" disabled={submitting}>{submitting ? "Please wait…" : isRegister ? "Create account" : "Sign in"}<ChevronRight size={17} /></button>
          </form>
          <p className="auth-switch">{isRegister ? "Already have an account?" : "New to TaskFlow Prep?"} <button onClick={() => { setIsRegister(!isRegister); setError(""); }}>{isRegister ? "Sign in" : "Create account"}</button></p>
          <p className="auth-hint"><Command size={13} /> Your data is scoped to your account.</p>
        </div>
      </section>
    </div>
  );
}

function OverviewPage({ user, onAdd, onNavigate }: { user: User; onAdd: () => void; onNavigate: (page: Page) => void }) {
  const tasksQuery = useQuery({ queryKey: ["tasks"], queryFn: api.tasks });
  const tracksQuery = useQuery({ queryKey: ["tracks", "all"], queryFn: () => api.tracks(true) });
  const notificationsQuery = useQuery({ queryKey: ["notifications"], queryFn: api.notifications });
  const jobsQuery = useQuery({ queryKey: ["jobs"], queryFn: api.jobs, refetchInterval: 10_000 });
  const tasks = tasksQuery.data ?? [];
  const pending = tasks.filter((task) => task.status !== "completed" && task.status !== "archived");
  const complete = tasks.filter((task) => task.status === "completed");
  const nextTask = [...pending].sort((a, b) => Date.parse(a.due_at) - Date.parse(b.due_at))[0];
  const localTime = useMemo(() => new Intl.DateTimeFormat("en", { weekday: "long", month: "long", day: "numeric", timeZone: user.timezone }).format(new Date()), [user.timezone]);
  return (
    <>
      <div className="page-heading">
        <div><span className="eyebrow">{localTime.toUpperCase()} <span className="heading-divider">/</span> YOUR FOCUS, IN VIEW</span><h1>Make today <em>count.</em></h1><p>Good preparation isn't a sprint. It's showing up for the next small step.</p></div>
        <button className="button button-primary" onClick={onAdd}><Plus size={16} /> Add a study task</button>
      </div>
      {(tasksQuery.isError || notificationsQuery.isError || jobsQuery.isError) && <ErrorBanner message="Some workspace data could not be loaded. Check your connection and try again." />}
      <section className="summary-grid" aria-label="Study summary">
        <MetricCard label="OPEN TASKS" value={tasksQuery.isPending || tasksQuery.isError ? "—" : String(pending.length)} detail="Ready when you are" icon={<ListTodo />} accent="red" />
        <MetricCard label="COMPLETED" value={tasksQuery.isPending || tasksQuery.isError ? "—" : String(complete.length)} detail="All-time in this workspace" icon={<CheckCheck />} />
        <MetricCard label="UNREAD REMINDERS" value={notificationsQuery.isPending || notificationsQuery.isError ? "—" : String((notificationsQuery.data ?? []).filter((item) => !item.read_at).length)} detail="Stored in your account" icon={<Bell />} accent="amber" />
        <MetricCard label="JOB RUNS" value={jobsQuery.isPending || jobsQuery.isError ? "—" : String((jobsQuery.data ?? []).length)} detail={jobsQuery.isPending || jobsQuery.isError ? "Queue state unavailable" : `${(jobsQuery.data ?? []).filter((job) => job.status === "succeeded").length} completed successfully`} icon={<Radio />} />
      </section>
      <section className="dashboard-grid">
        <div className="panel task-panel">
          <div className="panel-heading"><div><span className="eyebrow">YOUR NEXT STEPS</span><h2>Study tasks</h2></div><button className="text-link" onClick={() => onNavigate("tasks")}>View all <ChevronRight size={14} /></button></div>
          {tasksQuery.isPending ? <TaskSkeleton /> : tasksQuery.isError ? <EmptyState icon={<ListTodo />} title="Tasks unavailable." copy="Reconnect and refresh to load your saved tasks." /> : pending.length ? <div className="task-list">{pending.slice(0, 4).map((task) => <TaskRow key={task.id} task={task} trackName={tracksQuery.data?.find((track) => track.id === task.track_id)?.name} />)}</div> : <EmptyState icon={<CheckCheck />} title="A clean slate." copy="Add one small task to make a start." action={<button className="text-link" onClick={onAdd}>Create a task <ChevronRight size={14} /></button>} />}
        </div>
        <div className="panel focus-panel">
          <div className="panel-heading"><div><span className="eyebrow">UP NEXT</span><h2>Keep the rhythm</h2></div><span className="panel-orbit"><Flame size={17} /></span></div>
          {tasksQuery.isPending ? <TaskSkeleton /> : tasksQuery.isError ? <EmptyState icon={<ListTodo />} title="Task details unavailable." copy="Your saved plan could not be retrieved." /> : nextTask ? <><div className="focus-task"><span className="focus-dot" /><h3>{nextTask.title}</h3><p>Deadline {formatDate(nextTask.due_at)}</p></div><div className="focus-foot"><Clock3 size={14} /><span>Your reminder is scheduled with the job engine.</span></div><button className="button button-secondary full-button" onClick={() => onNavigate("tasks")}>Open task list <ChevronRight size={15} /></button></> : <EmptyState icon={<Sparkles />} title="Room to plan." copy="Your next task will show up here." action={<button className="text-link" onClick={onAdd}>Plan your first task <ChevronRight size={14} /></button>} />}
        </div>
      </section>
      <section className="bottom-grid">
        <div className="panel activity-panel"><div className="panel-heading"><div><span className="eyebrow">RELIABLE BY DESIGN</span><h2>Reminder activity</h2></div><button className="text-link" onClick={() => onNavigate("jobs")}>View job runs <ChevronRight size={14} /></button></div><ReminderActivity jobs={jobsQuery.data ?? []} loading={jobsQuery.isPending} error={jobsQuery.isError} /></div>
        <div className="quote-panel"><span className="quote-mark">“</span><p>Consistency is built one completed session at a time.</p><span className="quote-caption">YOUR PREPARATION, YOUR PACE</span><div className="quote-lines"><i /><i /><i /></div></div>
      </section>
    </>
  );
}

function TracksPage() {
  const queryClient = useQueryClient();
  const tracksQuery = useQuery({ queryKey: ["tracks", "all"], queryFn: () => api.tracks(true) });
  const tasksQuery = useQuery({ queryKey: ["tasks"], queryFn: api.tasks });
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [error, setError] = useState("");
  const create = useMutation({
    mutationFn: api.createTrack,
    onSuccess: () => {
      setName("");
      setDescription("");
      setError("");
      void queryClient.invalidateQueries({ queryKey: ["tracks"] });
    },
    onError: (caught) => setError(caught.message),
  });
  const changeTrack = useMutation({
    mutationFn: ({ id, action }: { id: string; action: "archive" | "restore" }) =>
      action === "archive" ? api.archiveTrack(id) : api.restoreTrack(id),
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: ["tracks"] }),
    onError: (caught) => setError(caught.message),
  });
  const tracks = tracksQuery.data ?? [];
  const tasks = tasksQuery.data ?? [];
  const activeTracks = tracks.filter((track) => !track.archived_at);
  const submit = (event: React.FormEvent) => {
    event.preventDefault();
    setError("");
    create.mutate({ name, description });
  };
  return <>
    <div className="page-heading">
      <div><span className="eyebrow">YOUR LEARNING PATHS</span><h1>Build your <em>foundation.</em></h1><p>Group study tasks by focus area. Archive a track to keep its history without cluttering your plan.</p></div>
      <span className="track-count">{activeTracks.length} ACTIVE TRACKS</span>
    </div>
    {error && <ErrorBanner message={error} />}
    {(tracksQuery.isError || tasksQuery.isError) && <ErrorBanner message="Track or task data could not be loaded." />}
    <form className="track-create panel" onSubmit={submit}>
      <div className="track-create-copy"><span className="eyebrow">MAKE IT YOURS</span><h2>Add a custom track</h2><p>Keep a specific subject or goal organized.</p></div>
      <label>Track name<input value={name} onChange={(event) => setName(event.target.value)} maxLength={100} placeholder="e.g. Distributed systems" required /></label>
      <label>Description <span className="optional-label">OPTIONAL</span><input value={description} onChange={(event) => setDescription(event.target.value)} maxLength={500} placeholder="What are you focusing on?" /></label>
      <button className="button button-primary" disabled={create.isPending}><Plus size={15} />{create.isPending ? "Adding…" : "Add track"}</button>
    </form>
    {tracksQuery.isPending || tasksQuery.isPending ? <div className="panel full-panel"><TaskSkeleton /></div> : tracksQuery.isError || tasksQuery.isError ? null : tracks.length ? <div className="track-grid">
      {tracks.map((track, index) => {
        const trackTasks = tasks.filter((task) => task.track_id === track.id && task.status !== "archived");
        const completed = trackTasks.filter((task) => task.status === "completed").length;
        return <TrackCard
          key={track.id}
          track={track}
          taskCount={trackTasks.length}
          completedCount={completed}
          position={activeTracks.findIndex((item) => item.id === track.id)}
          activeCount={activeTracks.length}
          onMove={(direction) => {
            const currentIndex = activeTracks.findIndex((item) => item.id === track.id);
            const swapIndex = currentIndex + direction;
            const target = activeTracks[swapIndex];
            if (!target) return;
            void Promise.all([
              api.updateTrack(track.id, { sort_order: target.sort_order }),
              api.updateTrack(target.id, { sort_order: track.sort_order }),
            ]).then(() => queryClient.invalidateQueries({ queryKey: ["tracks"] })).catch((caught: unknown) => setError(caught instanceof Error ? caught.message : "Track order could not be saved"));
          }}
          onSave={async (values) => {
            await api.updateTrack(track.id, values);
            await queryClient.invalidateQueries({ queryKey: ["tracks"] });
          }}
          onArchive={() => {
            if (window.confirm(`Archive "${track.name}"? Its tasks and history will be kept.`)) {
              changeTrack.mutate({ id: track.id, action: "archive" });
            }
          }}
          onRestore={() => changeTrack.mutate({ id: track.id, action: "restore" })}
        />;
      })}
    </div> : <EmptyState icon={<BookOpen />} title="No tracks to show." copy="Your saved learning tracks will appear here." />}
  </>;
}

function TrackCard({
  track,
  taskCount,
  completedCount,
  position,
  activeCount,
  onMove,
  onSave,
  onArchive,
  onRestore,
}: {
  track: PreparationTrack;
  taskCount: number;
  completedCount: number;
  position: number;
  activeCount: number;
  onMove: (direction: -1 | 1) => void;
  onSave: (values: { name: string; description: string }) => Promise<void>;
  onArchive: () => void;
  onRestore: () => void;
}) {
  const [editing, setEditing] = useState(false);
  const [name, setName] = useState(track.name);
  const [description, setDescription] = useState(track.description);
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);
  const percent = taskCount ? Math.round((completedCount / taskCount) * 100) : 0;
  async function save(event: React.FormEvent) {
    event.preventDefault();
    setSaving(true);
    setError("");
    try {
      await onSave({ name, description });
      setEditing(false);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Track could not be saved");
    } finally {
      setSaving(false);
    }
  }
  return <article className={`track-card panel ${track.archived_at ? "track-archived" : ""}`}>
    <div className="track-card-heading"><span className="track-icon"><BookOpen size={17} /></span><span className="track-order">TRACK {String(track.sort_order + 1).padStart(2, "0")}</span>
      {track.archived_at ? <span className="status-chip">ARCHIVED</span> : <div className="track-actions">
        <button className="icon-button track-action" aria-label={`Move ${track.name} up`} title="Move up" disabled={position <= 0} onClick={() => onMove(-1)}><ArrowUp size={14} /></button>
        <button className="icon-button track-action" aria-label={`Move ${track.name} down`} title="Move down" disabled={position < 0 || position >= activeCount - 1} onClick={() => onMove(1)}><ArrowDown size={14} /></button>
        <button className="icon-button track-action" aria-label={`Edit ${track.name}`} title="Edit track" onClick={() => setEditing(!editing)}><Pencil size={14} /></button>
      </div>}
    </div>
    {editing ? <form className="track-edit-form" onSubmit={(event) => void save(event)}>
      <label>Track name<input value={name} onChange={(event) => setName(event.target.value)} maxLength={100} required /></label>
      <label>Description<input value={description} onChange={(event) => setDescription(event.target.value)} maxLength={500} /></label>
      {error && <small className="field-error">{error}</small>}
      <div className="track-edit-actions"><button type="button" className="text-link" onClick={() => setEditing(false)}>Cancel</button><button className="button button-secondary" disabled={saving}>{saving ? "Saving…" : "Save track"}</button></div>
    </form> : <>
      <h2>{track.name}</h2><p className="track-description">{track.description || "A focused space for your preparation."}</p>
      <div className="track-progress"><span><b>{completedCount}</b> of {taskCount} tasks completed</span><b>{percent}%</b></div>
      <div className="progress-rail"><span style={{ width: `${percent}%` }} /></div>
      <div className="track-card-footer">{track.archived_at ? <button className="text-link" onClick={onRestore}><CornerUpLeft size={13} /> Restore track</button> : <><span>{taskCount ? "Progress stays with the track" : "Ready for a first task"}</span><button className="text-link archive-action" onClick={onArchive}><Archive size={13} /> Archive</button></>}</div>
    </>}
  </article>;
}

function MetricCard({ label, value, detail, icon, accent }: { label: string; value: string; detail: string; icon: React.ReactNode; accent?: string }) {
  return <div className={`metric-card ${accent ? `metric-${accent}` : ""}`}><div className="metric-top"><span>{label}</span><span className="metric-icon">{icon}</span></div><strong>{value}</strong><small>{detail}</small></div>;
}

function TasksPage({ onAdd }: { onAdd: () => void }) {
  const queryClient = useQueryClient();
  const tasksQuery = useQuery({ queryKey: ["tasks"], queryFn: api.tasks });
  const tracksQuery = useQuery({ queryKey: ["tracks", "all"], queryFn: () => api.tracks(true) });
  const complete = useMutation({ mutationFn: api.completeTask, onSuccess: () => void queryClient.invalidateQueries() });
  const update = useMutation({ mutationFn: ({ id, status }: { id: string; status: StudyTask["status"] }) => api.updateTask(id, { status }), onSuccess: () => void queryClient.invalidateQueries() });
  const tasks = tasksQuery.data ?? [];
  return <><div className="page-heading"><div><span className="eyebrow">YOUR PLAN</span><h1>Study <em>tasks.</em></h1><p>Deadlines stay connected to persistent reminders, even when you're away.</p></div><button className="button button-primary" onClick={onAdd}><Plus size={16} /> New task</button></div>
    {tasksQuery.isError && <ErrorBanner message="Tasks could not be loaded. Please try again." />}
    <div className="panel full-panel"><div className="panel-heading"><div><span className="eyebrow">ALL STUDY TASKS</span><h2>{tasksQuery.isPending ? "Loading…" : `${tasks.length} ${tasks.length === 1 ? "task" : "tasks"}`}</h2></div></div>
      {tasksQuery.isPending ? <TaskSkeleton /> : tasksQuery.isError ? <EmptyState icon={<ListTodo />} title="Tasks unavailable." copy="Your saved study plan could not be loaded." /> : tasks.length ? <div className="task-list">{tasks.map((task) => <TaskRow
        key={task.id}
        task={task}
        trackName={tracksQuery.data?.find((track) => track.id === task.track_id)?.name}
        showHistory
        onComplete={task.status !== "completed" && task.status !== "archived" ? () => complete.mutate(task.id) : undefined}
        onStatus={(status) => update.mutate({ id: task.id, status })}
        isCompleting={complete.isPending && complete.variables === task.id}
      />)}</div> : <EmptyState icon={<ListTodo />} title="Your plan starts here." copy="Choose one useful thing to work on next." action={<button className="button button-secondary" onClick={onAdd}><Plus size={15} /> Add a task</button>} />}
      {complete.isError && <ErrorBanner message={complete.error.message} />}
      {update.isError && <ErrorBanner message={update.error.message} />}
    </div>
  </>;
}

function TaskRow({
  task,
  trackName,
  onComplete,
  onStatus,
  isCompleting,
  showHistory = false,
}: {
  task: StudyTask;
  trackName?: string;
  onComplete?: () => void;
  onStatus?: (status: StudyTask["status"]) => void;
  isCompleting?: boolean;
  showHistory?: boolean;
}) {
  const [historyOpen, setHistoryOpen] = useState(false);
  const historyQuery = useQuery({
    queryKey: ["task-history", task.id],
    queryFn: () => api.taskHistory(task.id),
    enabled: showHistory && historyOpen,
  });
  const isDone = task.status === "completed";
  const statusLabel = { pending: "Not started", in_progress: "In progress", completed: "Completed", blocked: "Blocked", archived: "Archived" }[task.status];
  return <div className={`task-entry ${isDone ? "task-done" : ""}`}>
    <div className="task-row"><span className={`task-check ${isDone ? "checked" : ""}`}>{isDone && <Check size={13} />}</span><div className="task-copy"><b>{task.title}</b><span><Clock3 size={12} /> Due {formatDate(task.due_at)}{task.estimated_duration_minutes ? ` · ${task.estimated_duration_minutes} min` : ""}</span></div>
      <span className={`priority-chip priority-${task.priority}`}>{task.priority}</span>
      {showHistory && onStatus && task.status !== "completed" && task.status !== "archived" && <select className="task-status-select" aria-label={`Status for ${task.title}`} value={task.status} onChange={(event) => onStatus(event.target.value as StudyTask["status"])}><option value="pending">Not started</option><option value="in_progress">In progress</option><option value="blocked">Blocked</option></select>}
      {isDone ? <span className="status-chip status-done">COMPLETED</span> : onComplete && <button className="complete-button" disabled={isCompleting} onClick={onComplete}>{isCompleting ? "Saving…" : "Mark done"}</button>}
      {showHistory && <button className="text-link history-toggle" aria-expanded={historyOpen} onClick={() => setHistoryOpen(!historyOpen)}>{historyOpen ? "Hide history" : "History"}</button>}
    </div>
    <div className="task-subline">{trackName && <span className="task-track-label"><BookOpen size={11} />{trackName}</span>}<span>{statusLabel}</span></div>
    {task.notes && <p className="task-notes">{task.notes}</p>}
    {showHistory && historyOpen && <div className="task-history">
      {historyQuery.isPending ? <TaskSkeleton /> : historyQuery.isError ? <span className="field-error">Task history could not be loaded.</span> : historyQuery.data?.length ? historyQuery.data.map((entry) => <div className="history-entry" key={entry.id}><span className="history-dot" /><div><b>{entry.event_type === "status_changed" ? `${entry.previous_status ?? "created"} → ${entry.new_status}` : entry.event_type.replaceAll("_", " ")}</b><small>{entry.details || formatDate(entry.occurred_at)} · {entry.details ? formatDate(entry.occurred_at) : ""}</small></div></div>) : <span className="muted">No history recorded yet.</span>}
    </div>}
  </div>;
}

function NotificationsPage() {
  const queryClient = useQueryClient();
  const notificationsQuery = useQuery({
    queryKey: ["notifications"],
    queryFn: api.notifications,
    refetchInterval: 15_000,
    refetchOnWindowFocus: true,
  });
  const markRead = useMutation({ mutationFn: api.markRead, onSuccess: () => void queryClient.invalidateQueries() });
  const markAll = useMutation({ mutationFn: api.markAllRead, onSuccess: () => void queryClient.invalidateQueries() });
  const notifications = notificationsQuery.data ?? [];
  return <><div className="page-heading"><div><span className="eyebrow">YOUR INBOX</span><h1>Never miss <em>the moment.</em></h1><p>Reminders created from your study plan and stored in your account.</p></div><button className="button button-secondary" disabled={!notifications.some((n) => !n.read_at) || markAll.isPending} onClick={() => markAll.mutate()}><CheckCheck size={15} /> Mark all read</button></div>
    {notificationsQuery.isError && <ErrorBanner message="Notifications could not be loaded. Please try again." />}
    <div className="panel full-panel notification-list-panel"><div className="panel-heading"><div><span className="eyebrow">RECENT ACTIVITY</span><h2>{notificationsQuery.isPending ? "Loading…" : `${notifications.filter((n) => !n.read_at).length} unread`}</h2></div></div>
      {notificationsQuery.isPending ? <TaskSkeleton /> : notificationsQuery.isError ? <EmptyState icon={<Bell />} title="Inbox unavailable." copy="Your saved notifications could not be loaded." /> : notifications.length ? <div className="notification-list">{notifications.map((item) => <NotificationRow key={item.id} item={item} onRead={() => markRead.mutate(item.id)} isSaving={markRead.isPending && markRead.variables === item.id} />)}</div> : <EmptyState icon={<Bell />} title="Nothing to catch up on." copy="When a task reminder is due, it will arrive here." />}
      {markRead.isError && <ErrorBanner message={markRead.error.message} />}
      {markAll.isError && <ErrorBanner message={markAll.error.message} />}
    </div>
  </>;
}

function NotificationRow({ item, onRead, isSaving }: { item: AppNotification; onRead: () => void; isSaving: boolean }) {
  return <div className={`notification-row ${item.read_at ? "notification-read" : ""}`}><span className={`notification-icon ${item.read_at ? "" : "notification-unread"}`}><Bell size={16} /></span><div className="notification-copy"><div><b>{item.title}</b>{!item.read_at && <span className="unread-dot" />}</div><p>{item.body}</p><small>{formatDate(item.created_at)}</small></div>{!item.read_at && <button className="text-link mark-read" disabled={isSaving} onClick={onRead}>{isSaving ? "Saving…" : "Mark read"}</button>}</div>;
}

function JobsPage() {
  const jobsQuery = useQuery({ queryKey: ["jobs"], queryFn: api.jobs, refetchInterval: 10_000 });
  const jobs = jobsQuery.data ?? [];
  return <><div className="page-heading"><div><span className="eyebrow">PERSISTENT QUEUE</span><h1>Behind the <em>reminders.</em></h1><p>Every reminder is a durable job with a visible state and retry history.</p></div><span className="live-pill"><span /> LIVE DATA</span></div>
    {jobsQuery.isError && <ErrorBanner message="Job status could not be loaded. Please try again." />}
    <div className="panel full-panel"><div className="panel-heading"><div><span className="eyebrow">YOUR JOB RUNS</span><h2>{jobsQuery.isPending ? "Loading…" : `${jobs.length} scheduled jobs`}</h2></div></div>
      {jobsQuery.isPending ? <TaskSkeleton /> : jobsQuery.isError ? <EmptyState icon={<Radio />} title="Job data unavailable." copy="The queue state could not be retrieved." /> : jobs.length ? <div className="job-list">{jobs.map((job) => <JobRow key={job.id} job={job} />)}</div> : <EmptyState icon={<Radio />} title="No jobs yet." copy="Create a task with a deadline and its reminder will appear here." />}
    </div>
  </>;
}

function JobRow({ job }: { job: Job }) {
  return <div className="job-row"><span className={`job-status status-${job.status}`}><i />{job.status}</span><div className="job-copy"><b>Study deadline reminder</b><small>{job.task_type} · {formatDate(job.scheduled_at)}</small></div><span className="job-attempt">Attempt {job.attempt_count}/{job.max_attempts}</span></div>;
}

function ReminderActivity({ jobs, loading, error }: { jobs: Job[]; loading: boolean; error: boolean }) {
  if (loading) return <TaskSkeleton />;
  if (error) return <EmptyState icon={<Radio />} title="Queue data unavailable." copy="Try refreshing the dashboard to check reminder activity." />;
  if (!jobs.length) return <EmptyState icon={<Radio />} title="Nothing queued yet." copy="Create a task with a deadline to schedule a reminder." />;
  return <div className="activity-list">{jobs.slice(0, 3).map((job) => <div className="activity-row" key={job.id}><span className={`activity-status status-${job.status}`}><i /></span><span><b>Deadline reminder</b><small>{formatDate(job.scheduled_at)}</small></span><span className={`status-chip status-${job.status}`}>{job.status}</span></div>)}</div>;
}

function TaskDialog({ onClose, onCreated }: { onClose: () => void; onCreated: () => void }) {
  const queryClient = useQueryClient();
  const tracksQuery = useQuery({ queryKey: ["tracks"], queryFn: () => api.tracks() });
  const { register, handleSubmit, formState: { errors, isSubmitting } } = useForm<TaskFields>({
    resolver: zodResolver(taskSchema),
    defaultValues: {
      remind_before_minutes: 60,
      track_id: "",
      priority: "normal",
      estimated_duration_minutes: 0,
      notes: "",
    },
  });
  const [error, setError] = useState("");
  const submit = handleSubmit(async (values) => {
    setError("");
    try {
      await api.createTask({
        title: values.title,
        due_at: new Date(values.due_at).toISOString(),
        remind_before_minutes: values.remind_before_minutes,
        track_id: values.track_id || null,
        priority: values.priority,
        estimated_duration_minutes: values.estimated_duration_minutes || null,
        notes: values.notes.trim() || null,
      });
      await queryClient.invalidateQueries();
      onCreated();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Task could not be created");
    }
  });
  return <div className="modal-backdrop" role="presentation" onMouseDown={(event) => { if (event.target === event.currentTarget) onClose(); }}><section className="task-dialog" role="dialog" aria-modal="true" aria-labelledby="dialog-title"><div className="dialog-heading"><span className="eyebrow">MAKE A PLAN</span><button className="icon-button" aria-label="Close dialog" onClick={onClose}><X size={18} /></button></div><h2 id="dialog-title">Add a study task</h2><p className="muted">Your reminder will be scheduled in the persistent job queue.</p>
    <form onSubmit={(event) => void submit(event)} className="task-form">
      <label>What will you work on?<input autoFocus placeholder="e.g. Review graph traversal" {...register("title")} />{errors.title && <small className="field-error">{errors.title.message}</small>}</label>
      <label>Deadline<input type="datetime-local" {...register("due_at")} />{errors.due_at && <small className="field-error">{errors.due_at.message}</small>}</label>
      <label>Remind me before<select {...register("remind_before_minutes", { valueAsNumber: true })}><option value={0}>At the deadline</option><option value={60}>1 hour</option><option value={1440}>24 hours</option></select>{errors.remind_before_minutes && <small className="field-error">Choose up to 7 days before.</small>}</label>
      <div className="task-form-row">
        <label>Preparation track<select {...register("track_id")} disabled={tracksQuery.isPending || tracksQuery.isError}><option value="">Unassigned</option>{(tracksQuery.data ?? []).map((track) => <option key={track.id} value={track.id}>{track.name}</option>)}</select>{tracksQuery.isError && <small className="field-error">Tracks could not be loaded.</small>}</label>
        <label>Priority<select {...register("priority")}><option value="low">Low</option><option value="normal">Normal</option><option value="high">High</option></select></label>
      </div>
      <div className="task-form-row">
        <label>Estimate (minutes)<input type="number" min="0" max="1440" placeholder="Optional" {...register("estimated_duration_minutes", { valueAsNumber: true })} /></label>
        <label>Notes<input maxLength={10000} placeholder="Optional context" {...register("notes")} /></label>
      </div>
      {error && <div className="form-error" role="alert">{error}</div>}
      <div className="dialog-actions"><button type="button" className="button button-secondary" onClick={onClose}>Cancel</button><button className="button button-primary" disabled={isSubmitting}>{isSubmitting ? "Saving…" : "Create task"}<ChevronRight size={15} /></button></div>
    </form>
  </section></div>;
}

function EmptyState({ icon, title, copy, action }: { icon: React.ReactNode; title: string; copy: string; action?: React.ReactNode }) {
  return <div className="empty-state"><span className="empty-icon">{icon}</span><h3>{title}</h3><p>{copy}</p>{action}</div>;
}

function ErrorBanner({ message }: { message: string }) {
  return <div className="error-banner" role="alert"><span />{message}</div>;
}

function TaskSkeleton() {
  return <div className="skeleton-stack" aria-label="Loading"><i /><i /><i /></div>;
}

function formatDate(value: string) {
  return new Intl.DateTimeFormat(undefined, { month: "short", day: "numeric", hour: "numeric", minute: "2-digit" }).format(new Date(value));
}

export default App;
