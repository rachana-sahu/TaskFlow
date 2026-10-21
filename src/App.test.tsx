import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import App from "./App";

describe("sign-in state", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ detail: "Sign in required" }), { status: 401 }),
    ));
  });

  it("shows the real sign-in form when there is no authenticated session", async () => {
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(<QueryClientProvider client={client}><MemoryRouter><App /></MemoryRouter></QueryClientProvider>);
    expect(await screen.findByRole("heading", { name: "Sign in to focus" })).toBeInTheDocument();
    expect(screen.getByLabelText("Email address")).toBeInTheDocument();
    expect(screen.getByLabelText("Password")).toBeInTheDocument();
  });

  it("marks a persisted notification read and refreshes the unread count", async () => {
    let isRead = false;
    const notification = {
      id: "notice-1",
      notification_type: "upcoming_deadline",
      title: "Study task deadline",
      body: '"Review graphs" is approaching its deadline.',
      related_resource_type: "task",
      related_resource_id: "task-1",
      scheduled_at: "2026-10-14T10:00:00Z",
      created_at: "2026-10-14T10:00:00Z",
      read_at: null,
      status: "created",
    };
    vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo | URL) => {
      const path = String(input).replace("/api/v1", "");
      if (path === "/auth/me") return new Response(JSON.stringify({ id: "user-1", email: "dev@example.com", timezone: "Asia/Kolkata" }));
      if (path === "/auth/csrf") return new Response(JSON.stringify({ csrf_token: "csrf" }));
      if (path === "/notifications/unread-count") return new Response(JSON.stringify({ count: isRead ? 0 : 1 }));
      if (path === "/notifications") return new Response(JSON.stringify([{ ...notification, read_at: isRead ? "2026-10-14T10:01:00Z" : null }]));
      if (path === "/notifications/notice-1/read") {
        isRead = true;
        return new Response(JSON.stringify({ ...notification, read_at: "2026-10-14T10:01:00Z" }));
      }
      return new Response(JSON.stringify({ detail: "Not found" }), { status: 404 });
    }));
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(<QueryClientProvider client={client}><MemoryRouter initialEntries={["/notifications"]}><App /></MemoryRouter></QueryClientProvider>);
    expect(await screen.findByRole("heading", { name: "1 unread" })).toBeInTheDocument();
    fireEvent.click(await screen.findByRole("button", { name: "Mark read" }));
    await waitFor(() => expect(screen.queryByRole("button", { name: "Mark read" })).not.toBeInTheDocument());
    expect(await screen.findByRole("heading", { name: "0 unread" })).toBeInTheDocument();
  });
});
