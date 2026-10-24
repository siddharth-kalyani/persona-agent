import { FluentProvider, webLightTheme } from "@fluentui/react-components";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ReactElement } from "react";
import { describe, expect, it, vi } from "vitest";
import { Api, type MeetingAnswer, type MeetingDetail, type MeetingList, type MeetingScan } from "../../api/client";
import { ApiTestProvider } from "../../api/context";
import { healthText } from "../admin/ClientScoping";
import { Meetings, noteSummary, scanText } from "./Meetings";

function wrap(api: Api, ui: ReactElement) {
  return render(
    <FluentProvider theme={webLightTheme}>
      <ApiTestProvider api={api}>{ui}</ApiTestProvider>
    </FluentProvider>,
  );
}

const LIST: MeetingList = {
  items: [
    {
      id: "m1", title: "Acme weekly sync", startsAt: "2026-10-13T04:30:00Z", endsAt: "2026-10-13T05:30:00Z",
      external: true, organizedByMe: true, attribution: "named", notes: { decision: 2, requirement: 1 },
      transcriptUntil: "2026-11-12T00:00:00Z", extractor: "offline",
    },
    {
      id: "m2", title: "Kestrel all hands", startsAt: "2026-10-09T08:30:00Z", endsAt: "2026-10-09T09:30:00Z",
      external: false, organizedByMe: false, attribution: "unattributed", notes: {}, transcriptUntil: null, extractor: "offline",
    },
  ],
  on: true, label: "Offline stand-in, no AI model: rule-based meeting notes", hidden: 0,
}; // prettier-ignore

const SCAN: MeetingScan = {
  stored: 2, atoms: 9, promises: 1, excluded: 0, waiting: 1, pending: false, skipped: false, off: false,
  unavailable: null, leftOut: 1,
}; // prettier-ignore

const ANSWER: MeetingAnswer = {
  answer: "In Acme weekly sync (Tue 13 Oct, 10:00):\n• Requirement — Lisa Chen: The go-live has to be on a weekend. [1]",
  citations: [
    {
      n: 1, meetingId: "m1", title: "Acme weekly sync", meetingStart: "2026-10-13T04:30:00Z", kind: "requirement",
      noteId: "a1", at: "2026-10-13T04:31:30Z", endAt: "2026-10-13T04:31:51Z", speaker: "Lisa Chen",
      quote: "The go-live has to be on a weekend.", turn: 1,
    },
  ],
  abstained: false, clarify: false, candidates: [], when: "", label: "Offline stand-in, no AI model: answers quote your meeting notes",
}; // prettier-ignore

const DETAIL: MeetingDetail = {
  ...LIST.items[0]!,
  notesList: [
    {
      id: "a1", kind: "requirement", text: "The go-live has to be on a weekend.", quote: "The go-live has to be on a weekend.",
      speaker: "Lisa Chen", speakerId: "⟦PERSON_aaaaaaaa.full⟧", speakerSide: "external", owner: null,
      saidAt: "2026-10-13T04:31:30Z", dueAt: null, duePhrase: null, trust: "high", status: "active", turn: 1,
    },
  ],
  transcript: [
    { turn: 0, at: "2026-10-13T04:31:00Z", speaker: "You", speakerId: "⟦ME.full⟧", speakerSide: "me", text: "Quick agenda today." },
    { turn: 1, at: "2026-10-13T04:31:30Z", speaker: "Lisa Chen", speakerId: "⟦PERSON_aaaaaaaa.full⟧", speakerSide: "external", text: "The go-live has to be on a weekend." },
  ],
  people: [
    { id: "⟦ME.full⟧", name: "You", side: "me" },
    { id: "⟦PERSON_aaaaaaaa.full⟧", name: "Lisa Chen", side: "external" },
    { id: "⟦PERSON_bbbbbbbb.full⟧", name: "John Miller", side: "external" },
  ],
}; // prettier-ignore

function api() {
  const a = new Api("", async () => "t");
  vi.spyOn(a, "meetings").mockResolvedValue(LIST);
  vi.spyOn(a, "scanMeetings").mockResolvedValue(SCAN);
  vi.spyOn(a, "meeting").mockResolvedValue(DETAIL);
  return a;
}

describe("Meetings", () => {
  it("lists remembered meetings and what the last look found", async () => {
    wrap(api(), <Meetings />);
    expect(await screen.findByText("Acme weekly sync")).toBeInTheDocument();
    // People from outside the organisation were invited: a Globe pill (was: "With people outside").
    expect(screen.getByText("External")).toBeInTheDocument();
    expect(screen.getByText("No speaker names")).toBeInTheDocument();
    expect(await screen.findByText(/2 new meetings remembered/)).toBeInTheDocument();
    // The engine badge; its tooltip (the list's label) also says "Offline stand-in", so match the badge exactly.
    expect(screen.getByText("Offline stand-in")).toBeInTheDocument();
  });

  it("answers with sources that open the meeting at the cited turn", async () => {
    const a = api();
    const ask = vi.spyOn(a, "askMeetings").mockResolvedValue(ANSWER);
    wrap(a, <Meetings />);
    await userEvent.type(await screen.findByLabelText("Ask about your meetings"), "What did the client ask for?");
    await userEvent.click(screen.getByRole("button", { name: "Ask" }));
    expect(ask).toHaveBeenCalledWith("What did the client ask for?", null);
    const sources = await screen.findByRole("list", { name: "Sources" });
    expect(within(sources).getByText(/Lisa Chen: “The go-live has to be on a weekend.”/)).toBeInTheDocument();
    await userEvent.click(within(sources).getByRole("button", { name: "Show in meeting" }));
    const meeting = await screen.findByLabelText("Meeting");
    expect(within(meeting).getByText("Requirements")).toBeInTheDocument();
    expect(within(meeting).getByText(/Quick agenda today/)).toBeInTheDocument();
  });

  it("asks which meeting when two match", async () => {
    const a = api();
    const ask = vi.spyOn(a, "askMeetings").mockResolvedValueOnce({
      ...ANSWER, answer: "More than one meeting matches. Which one did you mean?", citations: [], abstained: true,
      clarify: true, candidates: [{ id: "m1", title: "Acme weekly sync", startsAt: LIST.items[0]!.startsAt }],
    }).mockResolvedValueOnce(ANSWER); // prettier-ignore
    wrap(a, <Meetings />);
    await userEvent.type(await screen.findByLabelText("Ask about your meetings"), "the 10 am meeting");
    await userEvent.click(screen.getByRole("button", { name: "Ask" }));
    expect(await screen.findByText("Which meeting?")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: /Acme weekly sync \(/ }));
    expect(ask).toHaveBeenLastCalledWith("the 10 am meeting", "m1");
  });

  it("fixes a speaker, hides a note and forgets a meeting", async () => {
    const a = api();
    const fix = vi.spyOn(a, "correctSpeaker").mockResolvedValue(undefined);
    const note = vi.spyOn(a, "decideNote").mockResolvedValue(undefined);
    const forget = vi.spyOn(a, "forgetMeeting").mockResolvedValue(undefined);
    wrap(a, <Meetings />);
    // Each meeting row is itself the button that opens it (was: a separate "Open" button per meeting).
    await userEvent.click(await screen.findByRole("button", { name: /Acme weekly sync/ }));
    const meeting = await screen.findByLabelText("Meeting");
    await userEvent.click(within(meeting).getByRole("button", { name: "Not right" }));
    expect(note).toHaveBeenCalledWith("a1", "dismiss");
    await userEvent.selectOptions(within(meeting).getByLabelText("Wrong speaker?"), "⟦PERSON_aaaaaaaa.full⟧");
    await userEvent.selectOptions(within(meeting).getByLabelText("Was really"), "⟦PERSON_bbbbbbbb.full⟧");
    await userEvent.click(within(meeting).getByRole("button", { name: "Fix speaker" }));
    expect(fix).toHaveBeenCalledWith("m1", "⟦PERSON_aaaaaaaa.full⟧", "⟦PERSON_bbbbbbbb.full⟧");
    await userEvent.click(within(meeting).getByRole("button", { name: "Forget this meeting" }));
    await userEvent.click(within(meeting).getByRole("button", { name: "Yes, forget it" }));
    await waitFor(() => expect(forget).toHaveBeenCalledWith("m1"));
  });

  it("explains why nothing can be read", () => {
    expect(scanText({ ...SCAN, unavailable: "disabled" })).toMatch(/hasn't allowed apps to read Teams transcripts/);
    expect(scanText({ ...SCAN, off: true })).toMatch(/off for your organisation/);
    expect(scanText({ ...SCAN, stored: 0, promises: 0, waiting: 0, leftOut: 0 })).toBeNull();
    expect(noteSummary({ decision: 1, requirement: 2 })).toBe("1 decision · 2 requirements");
    expect(healthText({ key: "transcript_access", state: "fail", code: "disabled", counts: {} })).toMatch(/Transcript API access/);
  });
});
