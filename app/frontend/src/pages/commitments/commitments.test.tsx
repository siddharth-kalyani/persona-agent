import { FluentProvider, webLightTheme } from "@fluentui/react-components";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ReactElement } from "react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";
import { Api, type Commitment, type Draft, type Ledger } from "../../api/client";
import { ApiTestProvider } from "../../api/context";
import { NotificationBell } from "../NotificationBell";
import { bucket, Commitments } from "./Commitments";

function wrap(api: Api, ui: ReactElement, path = "/") {
  return render(
    <FluentProvider theme={webLightTheme}>
      <ApiTestProvider api={api}>
        <MemoryRouter initialEntries={[path]}>
          <Routes>
            <Route path="/" element={ui} />
            <Route path="/commitments" element={<p>Commitments page</p>} />
          </Routes>
        </MemoryRouter>
      </ApiTestProvider>
    </FluentProvider>,
  );
}

const HOUR = 3_600_000;
const iso = (ms: number) => new Date(Date.now() + ms).toISOString();

const PROMISE: Commitment = {
  id: "c1", channel: "chat", what: "Share the metrics", sentence: "Will share the metrics by Friday evening.",
  duePhrase: "by Friday evening", dueAt: iso(-2 * HOUR), madeAt: iso(-48 * HOUR), relationship: "external",
  status: "open", statusAt: null, snoozedUntil: null, looksDoneAt: null, extractor: "offline",
}; // prettier-ignore

const LEDGER: Ledger = {
  items: [
    PROMISE,
    { ...PROMISE, id: "c2", channel: "email", what: "Send you the onboarding checklist", dueAt: iso(5 * HOUR), relationship: "report" },
    { ...PROMISE, id: "c3", what: "Share the update after", dueAt: null, duePhrase: null, looksDoneAt: iso(-HOUR) },
  ],
  open: 3, overdue: 1, dueSoon: 1, capturedThisWeek: 3, precision: 0.8, decided: 5,
  label: "Offline stand-in, no AI model: rule-based promise finder", hidden: 0,
}; // prettier-ignore

const DRAFT = {
  id: "d1", text: "Hi Karan, sorry for the delay on the metrics. I'll have them by Monday.", generator: "offline",
  label: "Offline stand-in", modelId: "m", tier: "default", routeReason: "default",
  audience: { relationship: "external", label: "someone outside your organisation", to: [], cc: [], internal: 0, external: 1 },
  styleSlice: null, learned: true, basedOn: 4, exemplars: 0, checks: [], insertAllowed: true, oneOff: false,
  timing: { totalMs: 10, modelMs: null }, channel: "chat", chatUsers: ["karan.malhotra@bluefinbank.example"],
} as Draft; // prettier-ignore

function api() {
  const a = new Api("", async () => "t");
  vi.spyOn(a, "commitments").mockResolvedValue(LEDGER);
  vi.spyOn(a, "scanCommitments").mockResolvedValue({ found: 1, hints: 0, read: 3, excluded: 0, pending: false, skipped: false });
  return a;
}

describe("Commitments", () => {
  it("groups promises by when they're due", () => {
    expect(bucket(LEDGER.items[0]!)).toBe("overdue");
    expect(bucket(LEDGER.items[1]!)).toBe("soon");
    expect(bucket(LEDGER.items[2]!)).toBe("undated");
  });

  it("scans for new promises, lists them and marks one done", async () => {
    const a = api();
    const decide = vi.spyOn(a, "decideCommitment").mockResolvedValue(undefined);
    const user = userEvent.setup();
    wrap(a, <Commitments />);
    expect(await screen.findByText("Share the metrics")).toBeInTheDocument();
    expect(screen.getByText("Overdue")).toBeInTheDocument();
    expect(screen.getByText("No date given")).toBeInTheDocument();
    expect(screen.getByText("Looks done")).toBeInTheDocument();
    expect(await screen.findByText("1 new promise found")).toBeInTheDocument();
    expect(screen.getByText(/80% of the 5 you decided on were real promises/)).toBeInTheDocument();
    // Row actions are icon buttons; the tooltip is the accessible name (was: a "Done" text button).
    await user.click(screen.getAllByRole("button", { name: "Mark done" })[0]!);
    await waitFor(() => expect(decide).toHaveBeenCalledWith("c1", "done"));
  });

  it("drafts a follow-up and offers Teams prefill only when allowed", async () => {
    const a = api();
    const follow = vi.spyOn(a, "followUp").mockResolvedValue(DRAFT);
    const user = userEvent.setup();
    const { unmount } = wrap(a, <Commitments />);
    await screen.findByText("Share the metrics");
    await user.click(screen.getAllByRole("button", { name: "Draft a follow-up" })[0]!);
    await user.click(await screen.findByRole("menuitem", { name: /Running late/ }));
    await user.type(screen.getByPlaceholderText(/Monday/), "Monday");
    await user.click(screen.getByRole("button", { name: "Draft it" }));
    await waitFor(() => expect(follow).toHaveBeenCalledWith("c1", "late", "Monday"));
    expect(await screen.findByDisplayValue(/by Monday/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Open in Teams with this text" })).toBeNull();
    unmount();

    wrap(a, <Commitments prefill />);
    await screen.findByText("Share the metrics");
    await user.click(screen.getAllByRole("button", { name: "Draft a follow-up" })[0]!);
    await user.click(await screen.findByRole("menuitem", { name: /It's done/ }));
    expect(await screen.findByRole("button", { name: "Open in Teams with this text" })).toBeInTheDocument();
  });
});

describe("Notifications", () => {
  it("shows unread counts and opens the page a notification is about", async () => {
    const a = new Api("", async () => "t");
    vi.spyOn(a, "notifications").mockResolvedValue({
      unread: 1,
      items: [
        { id: "n1", kind: "commitments_due", count: 2, text: "2 promises due soon or overdue", createdAt: iso(-HOUR), read: false, teams: "off" },
      ],
    });
    const read = vi.spyOn(a, "markNotificationsRead").mockResolvedValue(undefined);
    const user = userEvent.setup();
    wrap(a, <NotificationBell />);
    await user.click(await screen.findByRole("button", { name: "Notifications, 1 unread" }));
    await user.click(await screen.findByText("2 promises due soon or overdue"));
    await waitFor(() => expect(read).toHaveBeenCalledWith("n1"));
    expect(await screen.findByText("Commitments page")).toBeInTheDocument();
  });
});
