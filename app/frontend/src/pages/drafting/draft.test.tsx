import { FluentProvider, webLightTheme } from "@fluentui/react-components";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";
import { Api, ApiError, type Draft as DraftT, type DraftingStatus, type DraftThread } from "../../api/client";
import { ApiTestProvider } from "../../api/context";
import { draftErrorText, sortChecks } from "../../drafting/DraftView";
import { Draft, parseRecipients } from "./Draft";

function wrap(api: Api) {
  return render(
    <FluentProvider theme={webLightTheme}>
      <ApiTestProvider api={api}>
        <MemoryRouter>
          <Draft />
        </MemoryRouter>
      </ApiTestProvider>
    </FluentProvider>,
  );
}

const STATUS: DraftingStatus = {
  generator: "offline", label: "Offline stand-in", defaultModel: "anthropic.claude-haiku-5-5",
  premiumModel: "anthropic.claude-sonnet-5-5", premiumLeftToday: 20, reviewDone: true, learnedItems: 70, sourceKind: "sample",
}; // prettier-ignore

const THREADS: DraftThread[] = [
  { conversationId: "c-bec", subject: "Updated bank details", sender: { email: "tom@c1oudnest.example", name: "Tom Becker" },
    receivedAt: "2026-10-13T10:00:00Z", excluded: false, excludedBy: null, reasons: [] },
  { conversationId: "c-acme", subject: "Acme go-live date?", sender: { email: "john@acmeretail.example", name: "John Miller" },
    receivedAt: "2026-10-12T10:00:00Z", excluded: true, excludedBy: "you", reasons: ["person"] },
]; // prettier-ignore

const DRAFT: DraftT = {
  id: "d1", text: "Dear Tom,\n\nThanks, noted.\n\nBest regards,\nSiddharth", generator: "offline", label: "Offline stand-in",
  modelId: "anthropic.claude-haiku-5-5", tier: "default", routeReason: "default",
  audience: { relationship: "external", label: "someone outside your organisation", to: [{ email: "tom@c1oudnest.example", name: "Tom Becker" }], cc: [], internal: 0, external: 1 },
  styleSlice: "external|email|english|*", learned: true, basedOn: 31, exemplars: 1,
  checks: [
    { code: "fill_in", severity: "info", message: "Fill in [x] yourself." },
    { code: "payment_change", severity: "block", message: "This email asks to change payment details." },
  ],
  insertAllowed: false, oneOff: false, timing: { totalMs: 40, modelMs: null },
}; // prettier-ignore

function api() {
  const a = new Api("", async () => "t");
  vi.spyOn(a, "draftingStatus").mockResolvedValue(STATUS);
  vi.spyOn(a, "draftingThreads").mockResolvedValue(THREADS);
  vi.spyOn(a, "drafts").mockResolvedValue([]);
  vi.spyOn(a, "draftingThread").mockResolvedValue({
    conversationId: "c-bec", subject: "Updated bank details", participants: [],
    messages: [{ sender: { email: "tom@c1oudnest.example", name: "Tom Becker" }, sentAt: "2026-10-13T10:00:00Z", fromMe: false, text: "Our bank details have changed." }],
  }); // prettier-ignore
  return a;
}

describe("helpers", () => {
  it("parses recipients and reports bad ones", () => {
    expect(parseRecipients('a@x.com, "Bob B" <B@Y.com>; nope')).toEqual({
      people: [
        { email: "a@x.com", name: null },
        { email: "b@y.com", name: "Bob B" },
      ],
      invalid: ["nope"],
    });
  });

  it("orders checks by severity and explains errors without content", () => {
    expect(sortChecks(DRAFT.checks).map((c) => c.code)).toEqual(["payment_change", "fill_in"]);
    expect(draftErrorText(new ApiError(409, "conversation_excluded", { by: "organisation" }))).toMatch(/organisation/);
    expect(draftErrorText(new ApiError(429, "too_many_drafts"))).toMatch(/Wait a minute/);
  });
});

describe("Draft page", () => {
  it("drafts a reply, shows who it's for and keeps Copy off until a blocking check is confirmed", async () => {
    const a = api();
    const create = vi.spyOn(a, "createDraft").mockResolvedValue(DRAFT);
    vi.spyOn(a, "draftFeedback").mockResolvedValue(undefined);
    const user = userEvent.setup();
    wrap(a);
    expect(await screen.findByText("Offline stand-in")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /Updated bank details/ }));
    expect(await screen.findByText("Our bank details have changed.")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Draft" }));
    await waitFor(() => expect(create).toHaveBeenCalled());
    expect(create.mock.calls[0]![0]).toMatchObject({ mode: "reply", conversationId: "c-bec", surface: "web", oneOff: false });
    expect(await screen.findByText("Writing to: someone outside your organisation")).toBeInTheDocument();
    expect(screen.getByLabelText("Draft")).toHaveValue(DRAFT.text);
    const copy = screen.getByRole("button", { name: "Copy" });
    expect(copy).toBeDisabled();
    await user.click(screen.getByRole("checkbox"));
    expect(copy).toBeEnabled();

    // Re-checking your edits keeps the block found in the thread.
    vi.spyOn(a, "checkText").mockResolvedValue({ checks: [], insertAllowed: true });
    await user.click(screen.getByRole("button", { name: "Check my edits" }));
    expect(await screen.findByText("This email asks to change payment details.")).toBeInTheDocument();
  });

  it("offers a one-off draft in a conversation you excluded", async () => {
    const a = api();
    const create = vi
      .spyOn(a, "createDraft")
      .mockRejectedValueOnce(new ApiError(409, "conversation_excluded", { by: "you", oneOffAllowed: true }))
      .mockResolvedValueOnce({ ...DRAFT, id: null, oneOff: true, checks: [] });
    const user = userEvent.setup();
    wrap(a);
    await user.click(await screen.findByRole("button", { name: /Acme go-live/ }));
    await user.click(screen.getByRole("button", { name: "Draft" }));
    await user.click(await screen.findByRole("button", { name: "Draft once without saving" }));
    await waitFor(() => expect(create).toHaveBeenCalledTimes(2));
    expect(create.mock.calls[1]![0]).toMatchObject({ oneOff: true });
    expect(await screen.findByText("One-off, not saved")).toBeInTheDocument();
  });

  it("needs a recipient and an instruction for a new email", async () => {
    const a = api();
    const create = vi.spyOn(a, "createDraft").mockResolvedValue({ ...DRAFT, checks: [] });
    const user = userEvent.setup();
    wrap(a);
    await user.click(await screen.findByRole("button", { name: "New email" }));
    await user.type(screen.getByRole("textbox", { name: /To/ }), "bad-address");
    await user.click(screen.getByRole("button", { name: "Draft" }));
    expect(await screen.findByText(/Not an email address: bad-address/)).toBeInTheDocument();
    expect(create).not.toHaveBeenCalled();
  });
});

describe("Draft page: Teams chats (M5)", () => {
  it("drafts a reply in a Teams chat and opens it in Teams only when allowed", async () => {
    const a = api();
    vi.spyOn(a, "draftingChats").mockResolvedValue([
      { chatId: "smp-chat-002", chatType: "oneOnOne", label: "Rahul Verma", members: 2, lastActivityAt: null, excluded: false, excludedBy: null, reasons: [] },
    ]); // prettier-ignore
    vi.spyOn(a, "draftingChat").mockResolvedValue({
      chatId: "smp-chat-002", label: "Rahul Verma",
      messages: [{ sender: { email: "rahul.verma@kestrel.example", name: "Rahul Verma" }, sentAt: "2026-10-13T10:00:00Z", fromMe: false, text: "Done, it's on UAT now." }],
    }); // prettier-ignore
    vi.spyOn(a, "teamsConfig").mockResolvedValue({ prefill: true, appId: null });
    const create = vi.spyOn(a, "createDraft").mockResolvedValue({
      ...DRAFT, checks: [], insertAllowed: true, text: "great, thanks!", channel: "chat", chatUsers: ["rahul.verma@kestrel.example"],
    }); // prettier-ignore
    const user = userEvent.setup();
    wrap(a);
    await user.click(await screen.findByRole("tab", { name: /Teams/ }));
    await user.click(await screen.findByText("Rahul Verma"));
    expect(await screen.findByText("Done, it's on UAT now.")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Draft" }));
    await waitFor(() =>
      expect(create).toHaveBeenCalledWith(expect.objectContaining({ mode: "reply", channel: "chat", conversationId: "smp-chat-002" })),
    );
    expect(await screen.findByRole("button", { name: "Open in Teams with this text" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Check my edits" })).toBeInTheDocument(); // chat edits are checked too
    expect(screen.queryByRole("button", { name: "Put in my Drafts folder" })).toBeNull();
  });
});
