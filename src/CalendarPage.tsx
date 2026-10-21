import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { ArrowLeft, ArrowRight, CalendarDays, Flame, Target } from "lucide-react";
import { api } from "./api";

const weekdays = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];

export default function CalendarPage() {
  const [displayMonth, setDisplayMonth] = useState(() => {
    const now = new Date();
    return new Date(now.getFullYear(), now.getMonth(), 1);
  });
  const year = displayMonth.getFullYear();
  const month = displayMonth.getMonth() + 1;
  const activityQuery = useQuery({
    queryKey: ["calendar-activity", year, month],
    queryFn: () => api.calendarActivity(year, month),
  });
  const activity = activityQuery.data;
  const leadingBlankDays = (displayMonth.getDay() + 6) % 7;
  const numberOfDays = new Date(year, month, 0).getDate();
  const trailingBlankDays = (7 - ((leadingBlankDays + numberOfDays) % 7)) % 7;
  const days = [
    ...Array.from({ length: leadingBlankDays }, () => null),
    ...Array.from({ length: numberOfDays }, (_, index) => index + 1),
    ...Array.from({ length: trailingBlankDays }, () => null),
  ];
  const today = new Date();
  const isCurrentMonth = today.getFullYear() === year && today.getMonth() + 1 === month;
  const activityDays = Object.keys(activity?.active_days ?? {}).length;

  return <>
    <div className="page-heading">
      <div><span className="eyebrow">SHOWING UP ADDS UP</span><h1>Your steady <em>rhythm.</em></h1>
        <p>Each day with a completed task becomes a mark in your preparation story.</p></div>
      <span className="live-pill"><span /> SAVED ACTIVITY</span>
    </div>
    {activityQuery.isError && <div className="error-banner" role="alert"><span />Calendar activity could not be loaded. Please try again.</div>}
    <div className="calendar-stats">
      <div className="panel calendar-stat"><span className="calendar-stat-icon"><Flame size={17} /></span><div><small>CURRENT STREAK</small><b>{activityQuery.isPending ? "…" : activity?.current_streak ?? 0} <i>days</i></b></div><span className="calendar-stat-note">Keep your momentum</span></div>
      <div className="panel calendar-stat"><span className="calendar-stat-icon"><Target size={17} /></span><div><small>LONGEST STREAK</small><b>{activityQuery.isPending ? "…" : activity?.longest_streak ?? 0} <i>days</i></b></div><span className="calendar-stat-note">Your personal best</span></div>
      <div className="panel calendar-stat"><span className="calendar-stat-icon"><CalendarDays size={17} /></span><div><small>COMPLETED THIS MONTH</small><b>{activityQuery.isPending ? "…" : activity?.completed_tasks ?? 0} <i>tasks</i></b></div><span className="calendar-stat-note">{activityDays} active {activityDays === 1 ? "day" : "days"}</span></div>
    </div>

    <section className="panel calendar-panel">
      <div className="calendar-heading">
        <div><span className="eyebrow">CONSISTENCY CALENDAR</span><h2>{displayMonth.toLocaleDateString(undefined, { month: "long", year: "numeric" })}</h2></div>
        <div className="calendar-controls">
          <button className="icon-button" aria-label="Previous month" onClick={() => setDisplayMonth(new Date(year, month - 2, 1))}><ArrowLeft size={16} /></button>
          <button className="button button-secondary" onClick={() => setDisplayMonth(new Date(today.getFullYear(), today.getMonth(), 1))}>Today</button>
          <button className="icon-button" aria-label="Next month" onClick={() => setDisplayMonth(new Date(year, month, 1))}><ArrowRight size={16} /></button>
        </div>
      </div>
      <div className="calendar-grid" role="grid" aria-label="Task completion activity calendar">
        {weekdays.map((weekday) => <div className="calendar-weekday" role="columnheader" key={weekday}>{weekday}</div>)}
        {days.map((day, index) => {
          if (day === null) return <div className="calendar-day calendar-day-blank" role="gridcell" aria-hidden="true" key={`blank-${index}`} />;
          const dateKey = `${year}-${String(month).padStart(2, "0")}-${String(day).padStart(2, "0")}`;
          const count = activity?.active_days[dateKey] ?? 0;
          const isToday = isCurrentMonth && today.getDate() === day;
          return <div className={`calendar-day ${count ? `calendar-active activity-${Math.min(count, 4)}` : ""} ${isToday ? "calendar-today" : ""}`}
            role="gridcell" aria-label={`${dateKey}: ${count} completed ${count === 1 ? "task" : "tasks"}`} key={dateKey}>
            <span>{day}</span>{count > 0 && <small>{count} done</small>}
          </div>;
        })}
      </div>
      {activityQuery.isPending ? <div className="skeleton-stack calendar-loading" aria-label="Loading consistency calendar"><i /></div> :
        activityDays ? <p className="calendar-caption">Lovely work — every highlighted day includes at least one completed study task.</p> :
          <div className="career-empty calendar-empty"><span><CalendarDays size={20} /></span><b>A fresh month to fill.</b><p>Mark a study task complete and it will appear here. Your calendar updates from saved task history.</p></div>}
      <div className="calendar-legend"><span>Less</span><i /><i /><i /><i /><span>More</span></div>
    </section>
  </>;
}
