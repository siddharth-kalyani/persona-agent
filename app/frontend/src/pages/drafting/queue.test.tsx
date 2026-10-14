import { FluentProvider, webLightTheme } from "@fluentui/react-components";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ReactElement } from "react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";
import { Api, type LearnedRule, type QueueView } from "../../api/client";
import { ApiTestProvider } from "../../api/context";
import { EditsCard, ruleLabel } from "../learning/EditsCard";
import { Queue } from "./Queue";

function wrap(api: Api, ui: ReactElement) {
  return render(
    <FluentProvider theme={webLightTheme}>
      <ApiTestProvider api={api}>
        <MemoryRouter>{ui}</MemoryRouter>
      </ApiTestProvider>
    </FluentProvider>,
  );
}

const VIEW: QueueView = {
  sourceKind: "sample",
  settings: { outlookDrafts: false, staleDays: 3, allowedByOrganisation: true },
  items: [
    { conversationId: "c1", subject: "Q4 plan", sender: { email: "meera@kestrel.example", name: "Meera Iyer" },
      receivedAt: "2026-10-13T10:00:00Z", needsReply: true, reason: "asks a question", excluded: false, excludedBy: null,
      ccOnly: false, draft: null },
    { conversationId: "c2", subject: "Newsletter", sender: { email: "noreply@x.example", name: null },
      receivedAt: "2026-10-12T10:00:00Z", needsReply: false, reason: "automated sender", excluded: false, excludedBy: null,
      ccOnly: false, draft: null },
  ],
}; // prettier-ignore

function api() {
  const a = new Api("", async () => "t");
  vi.spyOn(a, "tidy").mockResolvedValue({});
  vi.spyOn(a, "syncEdits").mockResolvedValue({ matched: 0, unmatched: 0, excluded: 0, superseded: 0, pending: 0, skipped: false });
  vi.spyOn(a, "queue").mockResolvedValue(VIEW);
  return a;
}

describe("Drafts queue", () => {
  it("tidies and syncs first, lists what's waiting and prepares a draft", async () => {
    const a = api();
    const prepare = vi.spyOn(a, "prepare").mockResolvedValue({
      draft: {} as never,
      placed: false,
      webLink: null,
      notPlacedReason: "off",
    });
    const user = userEvent.setup();
    wrap(a, <Queue />);
    expect(await screen.findByText("1 waiting for your reply")).toBeInTheDocument();
    expect(a.tidy).toHaveBeenCalled();
    expect(a.syncEdits).toHaveBeenCalled();
    expect(screen.getByText("Needs a reply")).toBeInTheDocument();
    expect(screen.getByText("For your information")).toBeInTheDocument();
    await user.click(screen.getAllByRole("button", { name: "Prepare draft" })[0]!);
    await waitFor(() => expect(prepare).toHaveBeenCalledWith("c1"));
    expect(await screen.findByText(/Turn on “Put drafts in my Outlook Drafts folder”/)).toBeInTheDocument();
  });

  it("saves the opt-in to drafts in Outlook", async () => {
    const a = api();
    const save = vi
      .spyOn(a, "saveDraftingSettings")
      .mockResolvedValue({ outlookDrafts: true, staleDays: 3, allowedByOrganisation: true });
    const user = userEvent.setup();
    wrap(a, <Queue />);
    await user.click(await screen.findByRole("switch", { name: /Put drafts in my Outlook Drafts folder/ }));
    await waitFor(() => expect(save).toHaveBeenCalledWith(true, 3));
  });
});

const RULE: LearnedRule = {
  id: "r1", scope: "report", kind: "avoid", value: "hope you are having a great week",
  text: 'Don\'t write "hope you are having a great week"', status: "active", evidence: 3, contradictions: 0,
  support: 1, lastSeen: "2026-10-14T10:00:00Z",
}; // prettier-ignore

describe("Learned from your edits", () => {
  it("shows the send-without-edit rate and lets you keep a rule", async () => {
    const a = new Api("", async () => "t");
    vi.spyOn(a, "syncEdits").mockResolvedValue({ matched: 1, unmatched: 0, excluded: 0, superseded: 0, pending: 0, skipped: false });
    vi.spyOn(a, "learnedRules").mockResolvedValue([RULE]);
    vi.spyOn(a, "editSummary").mockResolvedValue({ matched: 4, sendWithoutEditRate: 0.25, lightEditRate: 0.75, drafts: {} });
    const decide = vi.spyOn(a, "decideRule").mockResolvedValue({ ...RULE, status: "confirmed" });
    const user = userEvent.setup();
    wrap(a, <EditsCard />);
    expect(await screen.findByText("25% sent without edits")).toBeInTheDocument();
    expect(screen.getByText(/to your direct reports · seen 3 times/)).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Keep" }));
    await waitFor(() => expect(decide).toHaveBeenCalledWith("r1", "keep"));
  });

  it("labels greeting rules with readable placeholders", () => {
    expect(ruleLabel({ ...RULE, kind: "greeting", text: 'Greeting: "Hi {first},"' })).toBe('Greeting: "Hi ‹first name›,"');
  });
});
