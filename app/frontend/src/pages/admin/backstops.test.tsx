import { FluentProvider, webLightTheme } from "@fluentui/react-components";
import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";
import { App } from "../../App";
import { Api, ApiError, type BackstopStatus, type Me } from "../../api/client";
import { ApiTestProvider } from "../../api/context";
import { AuthTestProvider, type AuthState } from "../../auth/session";
import { errorText } from "../Home";
import { Backstops, kindsText, probeText } from "./Backstops";

const PAUSED: BackstopStatus = {
  backstops: [
    { key: "comprehend", mode: "offline", label: "Offline stand-in for Amazon Comprehend" },
    { key: "guardrail", mode: "aws", label: "Amazon Bedrock Guardrails (ApplyGuardrail)" },
    { key: "macie", mode: "aws", label: "Amazon Macie" },
  ],
  comprehendScope: "all",
  snapshotEveryHours: 24,
  paused: { since: "2026-10-19T08:00:00Z", reason: "macie_finding", ref: "f-123" },
  mySnapshot: null,
  events: [
    {
      id: 7,
      at: "2026-10-19T08:00:00Z",
      source: "macie",
      stage: "snapshot",
      outcome: "finding",
      kinds: { PAN: 1, NAME: 2 },
      severity: "high",
      user: "5f0c-user",
      ref: "f-123",
      flaggedItems: 1,
      purgedAt: null,
    },
  ],
};

function renderWith(api: Api, ui: React.ReactElement) {
  return render(
    <FluentProvider theme={webLightTheme}>
      <ApiTestProvider api={api}>
        <MemoryRouter>{ui}</MemoryRouter>
      </ApiTestProvider>
    </FluentProvider>,
  );
}

describe("Redaction checks (admin)", () => {
  it("shows the pause, each service's mode and what was caught (types only)", async () => {
    const api = new Api("", async () => "t");
    vi.spyOn(api, "backstops").mockResolvedValue(PAUSED);
    renderWith(api, <Backstops />);
    expect(await screen.findByText(/Paused since/)).toBeInTheDocument();
    expect(screen.getByText("Offline stand-in")).toBeInTheDocument();
    expect(screen.getAllByText("AWS")).toHaveLength(2);
    expect(screen.getByText("PAN 1, NAME 2")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Resume after review" })).toBeInTheDocument();
  });

  it("resumes and reloads", async () => {
    const api = new Api("", async () => "t");
    const load = vi
      .spyOn(api, "backstops")
      .mockResolvedValueOnce(PAUSED)
      .mockResolvedValueOnce({ ...PAUSED, paused: null });
    const resume = vi.spyOn(api, "resumePipeline").mockResolvedValue({ resumed: true });
    renderWith(api, <Backstops />);
    fireEvent.click(await screen.findByRole("button", { name: "Resume after review" }));
    expect(await screen.findByText("Vanimo is running again.")).toBeInTheDocument();
    expect(resume).toHaveBeenCalledOnce();
    expect(load).toHaveBeenCalledTimes(2);
    expect(screen.getByText(/no open findings/)).toBeInTheDocument();
  });

  it("removes the flagged items of a finding", async () => {
    const api = new Api("", async () => "t");
    vi.spyOn(api, "backstops").mockResolvedValue(PAUSED);
    const purge = vi.spyOn(api, "purgeFlagged").mockResolvedValue({ removed: 1 });
    renderWith(api, <Backstops />);
    fireEvent.click(await screen.findByRole("button", { name: "Remove 1 flagged item" }));
    expect(await screen.findByText(/Removed 1 flagged item\./)).toBeInTheDocument();
    expect(purge).toHaveBeenCalledWith(7);
  });

  it("explains probe results in plain words", () => {
    expect(probeText({ key: "guardrail_india", state: "warn", code: "missed_pan_upi", ms: 1 })).toBe(
      "Let through: pan, upi. Check the guardrail's regexes.",
    );
    expect(probeText({ key: "guardrail", state: "warn", code: "not_blocked", ms: 1 })).toMatch(/Let test text/);
    expect(probeText({ key: "comprehend", state: "fail", code: "AccessDeniedException", ms: 1 })).toContain(
      "AccessDeniedException",
    );
    expect(kindsText({})).toBe("");
  });
});

describe("paused organisation", () => {
  // The notice moved from Home into the app shell (it now shows above every page, Home included).
  it("tells users above every page and in errors", async () => {
    const api = new Api("", async () => "t");
    const me: Me = {
      user: { displayName: "Asha Rao", jobTitle: null },
      manager: null,
      recentSent: [],
      roles: ["Vanimo.User"],
      onboardingState: "review_done",
      signInMethod: "password",
      dataSource: "sample",
      microsoft365Connected: false,
      pipelinePaused: true,
    };
    vi.spyOn(api, "me").mockResolvedValue(me);
    const auth: AuthState = {
      options: { microsoft: false, password: true },
      signedIn: true,
      method: "password",
      email: "asha@example.com",
      roles: me.roles,
      isAdmin: false,
      mustChangePassword: false,
      token: async () => "t",
      signInWithPassword: vi.fn(async () => undefined),
      changePassword: vi.fn(async () => undefined),
      signInWithMicrosoft: vi.fn(async () => undefined),
      signOut: vi.fn(async () => undefined),
      expire: vi.fn(),
      requirePasswordChange: vi.fn(),
    };
    render(
      <FluentProvider theme={webLightTheme}>
        <AuthTestProvider value={auth}>
          <ApiTestProvider api={api}>
            <MemoryRouter>
              <App />
            </MemoryRouter>
          </ApiTestProvider>
        </AuthTestProvider>
      </FluentProvider>,
    );
    expect(await screen.findByText("Paused for your organisation")).toBeInTheDocument();
    expect(screen.getByText(/Nothing new is read, learned or drafted\s+until it's resumed/)).toBeInTheDocument();
    expect(errorText(new ApiError(423, "pipeline_paused"))).toMatch(/paused/);
    expect(errorText(new ApiError(503, "redaction_unavailable"))).toMatch(/unreachable/);
    expect(errorText(new ApiError(422, "model_check_blocked", { stage: "output" }))).toMatch(/stopped/);
  });
});
