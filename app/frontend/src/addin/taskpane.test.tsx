import { FluentProvider, webLightTheme } from "@fluentui/react-components";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { Api, type Draft, type DraftingStatus, type Me } from "../api/client";
import { TaskPane } from "./TaskPane";

const setSelectedDataAsync = vi.fn((_t: string, _o: unknown, cb: (r: unknown) => void) => cb({ status: "succeeded" }));
const ok = (value: unknown) => (cb: (r: unknown) => void) => cb({ status: "succeeded", value });

beforeEach(() => {
  setSelectedDataAsync.mockClear();
  vi.stubGlobal("Office", {
    CoercionType: { Text: "text" },
    AsyncResultStatus: { Succeeded: "succeeded", Failed: "failed" },
    context: {
      diagnostics: { platform: "OfficeOnline", version: "16" },
      requirements: { isSetSupported: (_: string, v: string) => v === "1.10" },
      mailbox: {
        item: {
          subject: { getAsync: ok("Re: Q4 plan") },
          to: { getAsync: ok([{ emailAddress: "meera@contoso.example", displayName: "Meera Iyer" }]) },
          cc: { getAsync: ok([]) },
          getComposeTypeAsync: ok({ composeType: "reply" }),
          conversationId: "conv-1",
          body: { setSelectedDataAsync, getAsync: vi.fn() },
        },
      },
    },
  });
});

const ME: Me = {
  user: { displayName: "Me", jobTitle: null }, manager: null, recentSent: [], roles: [], onboardingState: "review_done",
  signInMethod: "entra", dataSource: "graph", microsoft365Connected: true,
}; // prettier-ignore
const STATUS: DraftingStatus = {
  generator: "bedrock", label: "Claude", defaultModel: "haiku", premiumModel: "sonnet", premiumLeftToday: 3,
  reviewDone: true, learnedItems: 10, sourceKind: "graph", learned: true, learningRunning: false, learningOutdated: false,
}; // prettier-ignore
const DRAFT: Draft = {
  id: "d1", text: "Hi Meera,\n\nWill do.\n\nThanks,\nMe", generator: "bedrock", label: "Claude", modelId: "haiku",
  tier: "default", routeReason: "default",
  audience: { relationship: "manager", label: "your manager", to: [], cc: [], internal: 1, external: 0 },
  styleSlice: null, learned: true, basedOn: 20, exemplars: 2, checks: [], insertAllowed: true, oneOff: false,
  timing: { totalMs: 900, modelMs: 800 },
}; // prettier-ignore

describe("Outlook task pane", () => {
  it("drafts a reply from the compose window and inserts it at the cursor", async () => {
    const api = new Api("", async () => "t");
    vi.spyOn(api, "me").mockResolvedValue(ME);
    vi.spyOn(api, "draftingStatus").mockResolvedValue(STATUS);
    const create = vi.spyOn(api, "createDraft").mockResolvedValue(DRAFT);
    const feedback = vi.spyOn(api, "draftFeedback").mockResolvedValue(undefined);
    const user = userEvent.setup();
    render(
      <FluentProvider theme={webLightTheme}>
        <TaskPane api={api} />
      </FluentProvider>,
    );
    expect(await screen.findByText(/Drafting a reply/)).toBeInTheDocument();
    await user.type(screen.getByRole("textbox"), "tell her it's done");
    await user.click(screen.getByRole("button", { name: "Draft" }));
    await waitFor(() => expect(create).toHaveBeenCalled());
    expect(create.mock.calls[0]![0]).toEqual({
      mode: "reply",
      surface: "outlook",
      instruction: "tell her it's done",
      quality: "auto",
      oneOff: false,
      conversationId: "conv-1",
      to: [{ email: "meera@contoso.example", name: "Meera Iyer" }],
      cc: [],
    });
    expect(await screen.findByText("Writing to: your manager")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Insert at cursor" }));
    await waitFor(() => expect(setSelectedDataAsync).toHaveBeenCalledWith(DRAFT.text, { coercionType: "text" }, expect.any(Function)));
    expect(feedback).toHaveBeenCalledWith("d1", { outcome: "inserted" });
  });

  it("keeps insert off while a blocking check stands", async () => {
    const api = new Api("", async () => "t");
    vi.spyOn(api, "me").mockResolvedValue(ME);
    vi.spyOn(api, "draftingStatus").mockResolvedValue(STATUS);
    vi.spyOn(api, "createDraft").mockResolvedValue({
      ...DRAFT,
      insertAllowed: false,
      checks: [{ code: "lookalike_domain", severity: "block", message: "Looks like a phishing domain." }],
    });
    const user = userEvent.setup();
    render(
      <FluentProvider theme={webLightTheme}>
        <TaskPane api={api} />
      </FluentProvider>,
    );
    await user.click(await screen.findByRole("button", { name: "Draft" }));
    const insert = await screen.findByRole("button", { name: "Insert at cursor" });
    expect(insert).toBeDisabled();
    expect(screen.getByText("Looks like a phishing domain.")).toBeInTheDocument();
    await user.click(screen.getByRole("checkbox"));
    expect(insert).toBeEnabled();
  });
});

describe("reading a message", () => {
  it("addresses the reply to that message's sender, as Outlook's reply form will", async () => {
    vi.stubGlobal("Office", {
      CoercionType: { Text: "text" },
      AsyncResultStatus: { Succeeded: "succeeded", Failed: "failed" },
      context: {
        diagnostics: { platform: "OfficeOnline", version: "16" },
        requirements: { isSetSupported: () => true },
        mailbox: {
          item: {
            subject: "Q4 plan",
            from: { emailAddress: "ann@contoso.example", displayName: "Ann" },
            to: [{ emailAddress: "me@contoso.example", displayName: "Me" }],
            cc: [{ emailAddress: "bob@contoso.example", displayName: "Bob" }],
            conversationId: "conv-9",
          },
        },
      },
    });
    const api = new Api("", async () => "t");
    vi.spyOn(api, "me").mockResolvedValue(ME);
    vi.spyOn(api, "draftingStatus").mockResolvedValue(STATUS);
    const create = vi.spyOn(api, "createDraft").mockResolvedValue(DRAFT);
    const user = userEvent.setup();
    render(
      <FluentProvider theme={webLightTheme}>
        <TaskPane api={api} />
      </FluentProvider>,
    );
    await user.click(await screen.findByRole("switch", { name: "Reply all" }));
    await user.click(screen.getByRole("button", { name: "Draft" }));
    await waitFor(() => expect(create).toHaveBeenCalled());
    expect(create.mock.calls[0]![0]).toMatchObject({
      mode: "reply",
      conversationId: "conv-9",
      to: [{ email: "ann@contoso.example", name: "Ann" }],
      cc: [
        { email: "me@contoso.example", name: "Me" },
        { email: "bob@contoso.example", name: "Bob" },
      ],
    });
    expect(await screen.findByRole("button", { name: "Reply with this" })).toBeInTheDocument();
  });
});
