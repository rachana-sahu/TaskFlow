import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { ReactNode } from "react";
import CareerPage from "./CareerPage";
import CalendarPage from "./CalendarPage";

function renderQuery(component: ReactNode) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={client}>{component}</QueryClientProvider>);
}

describe("career and consistency views", () => {
  afterEach(() => {
    cleanup();
    vi.unstubAllGlobals();
  });

  beforeEach(() => {
    vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url.includes("/job-sources")) return new Response(JSON.stringify([]));
      if (url.includes("/job-search/filters")) return new Response(JSON.stringify({
        keywords: "", location: "", work_mode: "any", minimum_match: 0,
        updated_at: "2026-10-14T00:00:00Z",
      }));
      if (url.endsWith("/resume")) return new Response(JSON.stringify({ detail: "No resume uploaded" }), { status: 404 });
      if (url.includes("/job-applications")) return new Response(JSON.stringify([]));
      if (url.includes("/calendar/activity")) {
        const parsed = new URL(url, "http://localhost");
        const year = Number(parsed.searchParams.get("year"));
        const month = Number(parsed.searchParams.get("month"));
        const dateKey = `${year}-${String(month).padStart(2, "0")}-01`;
        return new Response(JSON.stringify({
          year,
          month,
          active_days: { [dateKey]: 2 },
          current_streak: 2,
          longest_streak: 5,
          completed_tasks: 2,
        }));
      }
      return new Response(JSON.stringify({ detail: "Not found" }), { status: 404 });
    }));
  });

  it("shows supported job sources and link-only custom platforms", async () => {
    renderQuery(<CareerPage />);
    expect(await screen.findByRole("heading", { name: "Find your fit." })).toBeInTheDocument();
    expect(screen.getByRole("option", { name: "Greenhouse public board" })).toBeInTheDocument();
    expect(screen.getByRole("option", { name: "Lever public board" })).toBeInTheDocument();
    expect(screen.getByRole("option", { name: "Custom platform link" })).toBeInTheDocument();
    expect(await screen.findByText(/No resume uploaded/)).toBeInTheDocument();
  });

  it("clears cached resume metadata after deletion", async () => {
    let resumeExists = true;
    vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url.endsWith("/auth/csrf")) {
        return new Response(JSON.stringify({ csrf_token: "test-csrf" }));
      }
      if (url.endsWith("/resume") && init?.method === "DELETE") {
        resumeExists = false;
        return new Response(null, { status: 204 });
      }
      if (url.endsWith("/resume")) {
        if (resumeExists) {
          return new Response(JSON.stringify({
            id: "resume-1",
            filename: "resume.txt",
            uploaded_at: "2026-10-14T00:00:00Z",
            extracted_characters: 42,
          }));
        }
        return new Response(JSON.stringify({ detail: "No resume uploaded" }), { status: 404 });
      }
      if (url.includes("/job-sources")) return new Response(JSON.stringify([]));
      if (url.includes("/job-search/filters")) return new Response(JSON.stringify({
        keywords: "", location: "", work_mode: "any", minimum_match: 0,
        updated_at: "2026-10-14T00:00:00Z",
      }));
      if (url.includes("/job-applications")) return new Response(JSON.stringify([]));
      return new Response(JSON.stringify({ detail: "Not found" }), { status: 404 });
    }));

    renderQuery(<CareerPage />);
    expect(await screen.findByText("resume.txt", { exact: true })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Remove" }));
    expect(await screen.findByText(/No resume uploaded/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Remove" })).not.toBeInTheDocument();
  });

  it("renders completion activity and the user’s streak", async () => {
    const today = new Date();
    const dateKey = `${today.getFullYear()}-${String(today.getMonth() + 1).padStart(2, "0")}-01`;
    renderQuery(<CalendarPage />);
    expect(await screen.findByRole("gridcell", { name: `${dateKey}: 2 completed tasks` })).toBeInTheDocument();
    expect(screen.getByText("LONGEST STREAK").parentElement).toHaveTextContent("5 days");
    expect(screen.getByText(/highlighted day includes/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Previous month" }));
    const previousMonth = new Date(today.getFullYear(), today.getMonth() - 1, 1);
    expect(await screen.findByRole("heading", {
      name: previousMonth.toLocaleDateString(undefined, { month: "long", year: "numeric" }),
    })).toBeInTheDocument();
  });
});
