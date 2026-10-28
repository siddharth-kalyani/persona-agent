import { FluentProvider, webLightTheme } from "@fluentui/react-components";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";
import { Api, type LearningStatus, type PersonaSnapshot, type SampleWorkspace as Ws, type StoredItem } from "../../api/client";
import { ApiTestProvider } from "../../api/context";
import { SampleWorkspace } from "../sample/SampleWorkspace";
import { Learning, runSummary } from "./Learning";
import { formLabel, Persona } from "./Persona";

function wrap(api: Api, ui: React.ReactElement) {
  return render(
    <FluentProvider theme={webLightTheme}>
      <ApiTestProvider api={api}>
        <MemoryRouter>{ui}</MemoryRouter>
      </ApiTestProvider>
    </FluentProvider>,
  );
}

const STATUS: LearningStatus = {
  onboardingState: "review_done",
  sourceKind: "sample",
  run: null,
  stored: { email: 0, chat: 0, total: 0 },
  styleCards: 0,
  learned: false,
  outdated: false,
};

const ITEM: StoredItem = {
  id: "i1", channel: "email", sentAt: "2026-10-01T10:00:00Z", relationship: "external", intent: "update",
  language: "english", wordCount: 30, bucket: "email", tone: "formal", situations: ["update"],
  heldOut: false, suspicious: false, subject: "Acme invoice",
  stored: "Dear ⟦PERSON_1a2b3c4d⟧,\nOur GSTIN is [GSTIN].\nBest regards,\n⟦ME.full⟧",
  display: "Dear John,\nOur GSTIN is [GSTIN].\nBest regards,\nSiddharth Kalyani",
  contextStored: null, contextDisplay: null,
}; // prettier-ignore

describe("helpers", () => {
  it("summarises run counts in plain words, without eval numbers", () => {
    expect(runSummary({ email_learned: 40, chat_excluded: 2, blocked_residue_tier_r: 1, stored: 41, eval_n_eval: 5 })).toEqual([
      "40 emails learned",
      "2 chats skipped (excluded)",
      "1 blocked by the privacy check (residue tier r)",
    ]);
    expect(formLabel("Best regards,\n{me_full}")).toBe("Best regards,\n‹your full name›");
  });
});

describe("Learning", () => {
  it("first asks for the review, as the one next step", async () => {
    const api = new Api("", async () => "t");
    vi.spyOn(api, "learning").mockResolvedValue({ ...STATUS, onboardingState: "review_pending" });
    wrap(api, <Learning />);
    expect(await screen.findByText("First, choose what Vanimo may learn from")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Choose sources" })).toBeEnabled();
    expect(screen.queryByRole("button", { name: "Learn my style" })).toBeNull();
  });

  it("starts learning, shows what's stored and can switch to your view", async () => {
    const api = new Api("", async () => "t");
    const learned: LearningStatus = {
      ...STATUS,
      run: { id: "r1", status: "done", sourceKind: "sample", startedAt: "2026-10-13T10:00:00Z", finishedAt: null,
             counts: { email_learned: 1, conversations: 4 }, errorCode: null },
      stored: { email: 1, chat: 0, total: 1 },
      styleCards: 3,
      learned: true,
    }; // prettier-ignore
    const learning = vi.spyOn(api, "learning").mockResolvedValueOnce(STATUS).mockResolvedValue(learned);
    const start = vi.spyOn(api, "startLearning").mockResolvedValue(learned);
    vi.spyOn(api, "storedItems").mockResolvedValue({ items: [ITEM], total: 1 });
    wrap(api, <Learning />);
    // Nothing learned yet: one card that explains learning and starts it, no counters full of zeros.
    expect(await screen.findByText("Vanimo needs to learn your style first")).toBeInTheDocument();
    expect(screen.queryByText("Emails stored")).toBeNull();
    await userEvent.click(screen.getByRole("button", { name: "Learn my style" }));
    expect(start).toHaveBeenCalled();
    expect(await screen.findByText("People and group chats given a tone")).toBeInTheDocument();
    // What's stored is one click away, folded.
    await userEvent.click(screen.getByRole("button", { name: "Show what Vanimo stored (1)" }));
    expect(await screen.findByText(/Our GSTIN is \[GSTIN\]/)).toBeInTheDocument();
    expect(screen.getByText("Formal · Email")).toBeInTheDocument();
    expect(screen.getByText(/⟦ME.full⟧/)).toBeInTheDocument();
    // The stored/shown view is a segmented control (tabs), no longer a switch.
    await userEvent.click(screen.getByRole("tab", { name: "As shown to you" }));
    expect(screen.getByText(/Siddharth Kalyani/)).toBeInTheDocument();
    expect(screen.queryByText(/⟦ME.full⟧/)).toBeNull();
    expect(learning).toHaveBeenCalledTimes(2);
  });

  it("deletes what was learned after confirming and shows the receipt", async () => {
    const api = new Api("", async () => "t");
    vi.spyOn(api, "learning").mockResolvedValue({ ...STATUS, stored: { email: 1, chat: 0, total: 1 }, learned: true });
    vi.spyOn(api, "storedItems").mockResolvedValue({ items: [ITEM], total: 1 });
    const del = vi.spyOn(api, "deleteLearning").mockResolvedValue({ jobId: "abcdef1234", status: "done", counts: {} });
    wrap(api, <Learning />);
    await userEvent.click(await screen.findByRole("button", { name: "Delete what Vanimo learned" }));
    const dialog = await screen.findByRole("dialog", { hidden: true });
    // Fluent's open animation leaves jsdom treating the dialog as not yet visible.
    await userEvent.click(within(dialog).getByRole("button", { name: "Delete", hidden: true }));
    await waitFor(() => expect(del).toHaveBeenCalled());
    expect(await screen.findByText(/Deleted\. Receipt abcdef12\./)).toBeInTheDocument();
  });
});

const CARD = {
  n: 12, greetings: [["Dear {first},", 0.8], ["(none)", 0.2]] as [string, number][],
  sign_offs: [["Best regards,\n{me_full}", 0.9]] as [string, number][],
  length: { median: 40, p25: 25, p75: 60 }, formality: 0.8, exclamation_rate: 0, question_rate: 0.1,
  emoji_rate: 0, phrases: ["kindly review"], keep_list: ["pfa", "kindly"], languages: { english: 1 },
  intents: { update: 0.5 },
}; // prettier-ignore

describe("Persona", () => {
  const SETTINGS = { formality: 0, length: 0, warmth: 0, emoji: false, polish: "light" as const, phrases_do: [], phrases_dont: ["Hope this finds you well"] };
  const person = (key: string, label: string, tone: "formal" | "friendly" | "casual", bucket: "email" | "dm" | "group" = "email") => ({
    key, bucket, tone, judged: tone, override: null, basis: "your_messages" as const, judgedBy: "rules" as const,
    mine: 5, theirs: 2, label, email: `${key}@kestrel.example`, members: null, learned: 5, updatedAt: "",
  }); // prettier-ignore
  const SNAP: PersonaSnapshot = {
    source: "sample", learned_items: 12,
    by: { channel: { email: 12 }, bucket: { email: 10, dm: 2 }, tone: { formal: 8, casual: 4 }, language: { english: 12 } },
    overall: CARD, tone_cards: { formal: CARD }, bucket_cards: { email: CARD }, tone_bucket_cards: { "formal|email": CARD },
    conversations: [person("karan", "Karan Malhotra", "formal"), person("vikram", "Vikram Shah", "casual", "dm")],
    vocabulary: {
      tones: { formal: { request: [{ phrase: "kindly revert", uses: 4, conversations: 3, channels: ["email"] }] } },
      spellings: [{ use: "pls", instead_of: "please", share: 0.8, uses: 6 }],
      labels: { request: "Asking for something" },
    },
    cards: 4, settings: SETTINGS,
    evaluation: { metrics: { n_eval: 3, greeting_match: 0.67, sign_off_match: 1, length_ratio: 0.5, bigram_overlap: 0.2 }, at: "" },
  }; // prettier-ignore

  it("shows tone groups, lets you move someone, and shows your words", async () => {
    const api = new Api("", async () => "t");
    vi.spyOn(api, "persona").mockResolvedValue(SNAP);
    vi.spyOn(api, "learning").mockResolvedValue({ ...STATUS, learned: true, stored: { email: 12, chat: 0, total: 12 } });
    const setTone = vi.spyOn(api, "setTone").mockResolvedValue(undefined);
    wrap(api, <Persona />);
    const formal = await screen.findByRole("region", { name: "Formal tone" });
    expect(within(formal).getByText("Karan Malhotra")).toBeInTheDocument();
    const casual = screen.getByRole("region", { name: "Casual tone" });
    expect(within(casual).getByText("Vikram Shah")).toBeInTheDocument();
    expect(within(screen.getByRole("region", { name: "Friendly tone" })).getByText("Nobody yet.")).toBeInTheDocument();
    // Vanimo got Karan wrong: move him.
    await userEvent.click(within(formal).getByRole("button", { name: "Change the tone for Karan Malhotra" }));
    await userEvent.click(await screen.findByRole("menuitem", { name: "Move to friendly" }));
    await waitFor(() => expect(setTone).toHaveBeenCalledWith("email", "karan", "friendly"));
    // Your words, per tone, and your spellings and never-use phrases.
    expect(screen.getByText("kindly revert")).toBeInTheDocument();
    expect(screen.getByText("pls (not please)")).toBeInTheDocument();
    // Never-use phrases show as pills too (not only in the settings box below).
    expect(screen.getAllByText("Hope this finds you well").some((el) => el.tagName !== "TEXTAREA")).toBe(true);
    // Greetings and sign-offs per channel are one click away.
    expect(screen.queryByText("Dear ‹first name›,")).toBeNull();
    await userEvent.click(screen.getByRole("button", { name: "Show greetings, sign-offs and length per channel" }));
    expect(screen.getByText("Dear ‹first name›,")).toBeInTheDocument();
    expect(within(screen.getByRole("group", { name: "Greeting match" })).getByText("67%")).toBeInTheDocument();
  });

  it("saves studio settings", async () => {
    const api = new Api("", async () => "t");
    vi.spyOn(api, "persona").mockResolvedValue(SNAP);
    vi.spyOn(api, "learning").mockResolvedValue({ ...STATUS, learned: true, stored: { email: 12, chat: 0, total: 12 } });
    const save = vi
      .spyOn(api, "savePersonaSettings")
      .mockImplementation(async (s) => ({ ...s, phrases_do: ["Project ⟦NS_ab12cd34⟧ update"] }));
    wrap(api, <Persona />);
    await userEvent.type(await screen.findByLabelText("Phrases to use (one per line)"), "Project Falcon update");
    await userEvent.click(screen.getByRole("button", { name: "Save" }));
    await waitFor(() => expect(save).toHaveBeenCalled());
    expect(save.mock.calls[0]?.[0].phrases_do).toEqual(["Project Falcon update"]);
    expect(await screen.findByText(/stored as placeholders/)).toBeInTheDocument();
  });

  it("asks to learn first when nothing is learned", async () => {
    const api = new Api("", async () => "t");
    vi.spyOn(api, "persona").mockResolvedValue({ ...SNAP, overall: null, conversations: [] });
    vi.spyOn(api, "learning").mockResolvedValue(STATUS);
    wrap(api, <Persona />);
    expect(await screen.findByRole("button", { name: "Learn my style" })).toBeInTheDocument();
  });
});

describe("SampleWorkspace", () => {
  it("lists sent mail with what happened to each item and shows what was stored", async () => {
    const api = new Api("", async () => "t");
    const ws: Ws = {
      note: "Synthetic sample data.",
      emails: [
        { id: "m1", conversationId: "c1", subject: "Acme invoice", sentAt: "2026-10-01T10:00:00Z",
          sender: { name: "You", email: "me@kestrel.example" }, to: [{ name: "John Miller", email: "john@acme.example" }],
          cc: [], direction: "sent", body: "Dear John, our GSTIN is 27AAPFU0939F1ZV.", status: "learned", reasons: [], storedId: "i1" },
        { id: "m2", conversationId: "c2", subject: "Falcon timeline", sentAt: "2026-10-02T10:00:00Z",
          sender: { name: "You", email: "me@kestrel.example" }, to: [{ name: "Karan", email: "k@bluefin.example" }],
          cc: [], direction: "sent", body: "Hi", status: "excluded", reasons: ["client_account"], storedId: null },
      ],
      chats: [], meetings: [],
    }; // prettier-ignore
    vi.spyOn(api, "sampleWorkspace").mockResolvedValue(ws);
    vi.spyOn(api, "storedItems").mockResolvedValue({ items: [ITEM], total: 1 });
    wrap(api, <SampleWorkspace />);
    expect(await screen.findByText("Excluded")).toBeInTheDocument();
    await userEvent.click(screen.getByText("Acme invoice"));
    // The body opens in the reading pane (the list also shows its first line as a preview).
    expect(within(screen.getByLabelText("Reading pane")).getByText(/27AAPFU0939F1ZV/)).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "See what Vanimo stored" }));
    expect(await screen.findAllByText(/Our GSTIN is \[GSTIN\]/, { selector: "pre" })).toHaveLength(2);
    expect(screen.getByText(/⟦ME.full⟧/)).toBeInTheDocument();
  });
});
