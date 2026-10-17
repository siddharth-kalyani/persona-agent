import { FluentProvider, webLightTheme } from "@fluentui/react-components";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";
import { Api, type ControlsStatus, type SourceItem } from "../../api/client";
import { ApiTestProvider } from "../../api/context";
import { ClientScoping, splitList } from "../admin/ClientScoping";
import { Setup } from "./Setup";
import { impactSentence, SourcesReview } from "./SourcesReview";

function wrap(api: Api, ui: React.ReactElement) {
  return render(
    <FluentProvider theme={webLightTheme}>
      <ApiTestProvider api={api}>
        <MemoryRouter>{ui}</MemoryRouter>
      </ApiTestProvider>
    </FluentProvider>,
  );
}

const PEOPLE: SourceItem[] = [
  {
    id: "p1", kind: "person", label: "Rahul Verma", detail: "rahul.verma@kestrel.example",
    counts: { emails: 6, chats: 4, meetings: 0 }, lastActivity: null, flags: [], excluded: false, ruleId: null, via: [], locked: false,
  },
  {
    id: "p2", kind: "person", label: "Karan Malhotra", detail: "karan@bluefinbank.example",
    counts: { emails: 7 }, lastActivity: null, flags: ["external"], excluded: true, ruleId: null,
    via: ["Your organisation: Bluefin Bank"], locked: true,
  },
  {
    id: "p3", kind: "person", label: "Nisha (home)", detail: "nisha@gmail.com",
    counts: { emails: 2 }, lastActivity: null, flags: ["personal email", "external"], excluded: true, ruleId: "r9", via: [], locked: false,
  },
]; // prettier-ignore

describe("impact sentence", () => {
  it("reads like the spec", () => {
    expect(impactSentence({ emails: 214, threads: 37, chats: 1, meetings: 3, chatList: [] })).toBe(
      "214 emails in 37 threads, 1 chat, 3 meetings",
    );
    expect(impactSentence({ emails: 0, threads: 0, chats: 0, meetings: 0, chatList: [] })).toBe("Nothing stored yet");
  });
});

describe("SourcesReview", () => {
  it("shows status, flags and organisation locks; excluding asks with an impact preview", async () => {
    const api = new Api("", async () => "t");
    vi.spyOn(api, "sources").mockResolvedValue(PEOPLE);
    vi.spyOn(api, "impact").mockResolvedValue({
      emails: 6, threads: 4, chats: 2, meetings: 0,
      chatList: [
        { id: "c-big", label: "All Kestrel India", members: 62, large: true },
        { id: "c-1", label: "Rahul Verma", members: 1, large: false },
      ],
    }); // prettier-ignore
    const addRule = vi.spyOn(api, "addRule").mockResolvedValue({ id: "r1", kind: "person", label: "Rahul Verma", createdAt: "", exceptions: 1 });
    const removeRule = vi.spyOn(api, "removeRule").mockResolvedValue(undefined);
    wrap(api, <SourcesReview />);

    expect(await screen.findByText("Rahul Verma")).toBeInTheDocument();
    expect(screen.getByText("Your organisation: Bluefin Bank")).toBeInTheDocument();
    expect(screen.getByText("personal email")).toBeInTheDocument();
    // Locked rows can't be changed; the user's own exclusion can be undone.
    const karanRow = screen.getByText("Karan Malhotra").closest("tr")!;
    expect(within(karanRow).queryByRole("button")).not.toBeInTheDocument();
    await userEvent.click(within(screen.getByText("Nisha (home)").closest("tr")!).getByRole("button", { name: "Use again" }));
    expect(removeRule).toHaveBeenCalledWith("r9");

    await userEvent.click(within(screen.getByText("Rahul Verma").closest("tr")!).getByRole("button", { name: "Exclude" }));
    expect(await screen.findByText(/6 emails in 4 threads, 2 chats/)).toBeInTheDocument();
    const dialog = screen.getByRole("dialog");
    await userEvent.click(within(dialog).getByLabelText(/All Kestrel India/)); // untick: keep using the big chat
    await userEvent.click(within(dialog).getByRole("button", { name: "Exclude" }));
    await waitFor(() => expect(addRule).toHaveBeenCalledWith("person", "p1", ["c-big"]));
  });

  it("offers 'also add to never-send words' only for real names", async () => {
    const api = new Api("", async () => "t");
    vi.spyOn(api, "sources").mockResolvedValue([{ ...PEOPLE[0]!, label: "ann@fabrikam.example" }]);
    vi.spyOn(api, "impact").mockResolvedValue({ emails: 1, threads: 1, chats: 0, meetings: 0, chatList: [] });
    wrap(api, <SourcesReview />);
    await userEvent.click(await screen.findByRole("button", { name: "Exclude" }));
    await screen.findByText(/1 email in 1 thread/);
    expect(screen.queryByLabelText(/never-send words/)).not.toBeInTheDocument();
  });

  it("filters by search", async () => {
    const api = new Api("", async () => "t");
    vi.spyOn(api, "sources").mockResolvedValue(PEOPLE);
    wrap(api, <SourcesReview />);
    await screen.findByText("Rahul Verma");
    await userEvent.type(screen.getByLabelText("Search sources"), "bluefin");
    expect(screen.queryByText("Rahul Verma")).not.toBeInTheDocument();
    expect(screen.getByText("Karan Malhotra")).toBeInTheDocument();
  });

  it("previews and adds a never-send word", async () => {
    const api = new Api("", async () => "t");
    vi.spyOn(api, "sources").mockResolvedValue([]);
    vi.spyOn(api, "words").mockResolvedValue([]);
    vi.spyOn(api, "previewWord").mockResolvedValue({
      variants: ["falcon", "falcons"], foldedForm: "falcon", appearsIn: 5, appearsInWithFolds: 6, commonWord: false,
    }); // prettier-ignore
    const addWord = vi.spyOn(api, "addWord").mockResolvedValue({
      id: "w1", text: "Falcon", kind: "codename", variants: ["फाल्कन"], allowInDrafts: false, folds: false, createdAt: "",
    }); // prettier-ignore
    wrap(api, <SourcesReview />);
    await userEvent.click(await screen.findByRole("tab", { name: "Never-send words" }));
    await userEvent.type(screen.getByLabelText("Word or phrase"), "Falcon");
    await userEvent.type(screen.getByLabelText(/Other spellings/), "फाल्कन");
    await userEvent.click(screen.getByLabelText("Codename"));
    expect(screen.getByRole("button", { name: "Add word" })).toBeDisabled(); // preview first
    await userEvent.click(screen.getByRole("button", { name: "Preview" }));
    expect(await screen.findByText(/Appears in 5 of your stored sources/)).toBeInTheDocument();
    // Hinglish folding is opt-in and shows its effect first.
    await userEvent.click(screen.getByLabelText(/Also catch Hinglish spellings .*6 sources instead of 5/));
    await userEvent.click(screen.getByRole("button", { name: "Add word" }));
    expect(addWord).toHaveBeenCalledWith("Falcon", "codename", ["फाल्कन"], false, true);
  });
});

describe("Setup", () => {
  const done: ControlsStatus = {
    onboardingState: "review_pending", reviewOutcome: null, rules: 0, neverSendWords: 0,
    scan: { status: "done", sourceKind: "sample", startedAt: "", finishedAt: "", counts: { people: 70, threads: 24, messages: 44, chats: 13, meetings: 20 } },
  }; // prettier-ignore

  it("starts the header scan on first visit, then finishes the review", async () => {
    const api = new Api("", async () => "t");
    vi.spyOn(api, "controlsStatus").mockResolvedValue({ ...done, scan: null });
    const startScan = vi.spyOn(api, "startScan").mockResolvedValue(done);
    vi.spyOn(api, "sources").mockResolvedValue([]);
    const complete = vi.spyOn(api, "completeReview").mockResolvedValue({ ...done, onboardingState: "review_done" });
    wrap(api, <Setup />);
    expect(await screen.findByText(/70 people, 24 email threads \(44 emails\), 13 chats, 20 meetings/)).toBeInTheDocument();
    expect(startScan).toHaveBeenCalledOnce();
    await userEvent.click(screen.getByRole("button", { name: "Finish" }));
    expect(complete).toHaveBeenCalledWith("finished");
  });
});

describe("ClientScoping", () => {
  it("adds a client account with domains and sensitive words", async () => {
    const api = new Api("", async () => "t");
    vi.spyOn(api, "scoping").mockResolvedValue({ externalMode: "allow_all", accounts: [], serverDrafts: true, teamsPrefill: false, teamsNotifications: true, meetingMemory: true });
    const add = vi.spyOn(api, "addAccount").mockResolvedValue({
      externalMode: "allow_all",
      serverDrafts: true,
      teamsPrefill: false,
      teamsNotifications: true,
      meetingMemory: true,
      accounts: [{ id: "a1", name: "Bluefin Bank", mode: "excluded", domains: ["bluefinbank.example"], sensitiveWords: 1, createdAt: "" }],
    });
    wrap(api, <ClientScoping />);
    await userEvent.type(await screen.findByLabelText(/Client name/), "Bluefin Bank");
    await userEvent.type(screen.getByLabelText(/Email domains/), "bluefinbank.example, bluefin.example");
    await userEvent.type(screen.getByLabelText(/Company-sensitive words/), "Falcon");
    await userEvent.click(screen.getByRole("button", { name: "Add client" }));
    expect(add).toHaveBeenCalledWith({
      name: "Bluefin Bank", mode: "excluded", domains: ["bluefinbank.example", "bluefin.example"], sensitiveWords: ["Falcon"],
    }); // prettier-ignore
    expect(await screen.findByText("Excluded")).toBeInTheDocument();
  });

  it("splits lists on commas, semicolons and new lines", () => {
    expect(splitList("a.com; b.com,\n c.com ,")).toEqual(["a.com", "b.com", "c.com"]);
  });
});
