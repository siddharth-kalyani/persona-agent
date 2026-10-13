import { FluentProvider, webLightTheme } from "@fluentui/react-components";
import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { Api, ApiError, type Me } from "../api/client";
import { ApiTestProvider } from "../api/context";
import { errorText, Home } from "./Home";
import { existingChatLink, newChatLink } from "./TeamsPrefill";

const ME: Me = {
  user: { displayName: "Asha Rao", jobTitle: "Consultant", department: "Delivery" },
  manager: null,
  recentSent: [{ subject: "Re: SOW", sentDateTime: "2026-10-12T10:00:00Z", recipientCount: 2 }],
  roles: ["Vanimo.User"],
  onboardingState: "review_pending",
};

function renderWith(api: Api, ui: React.ReactElement) {
  return render(
    <FluentProvider theme={webLightTheme}>
      <ApiTestProvider api={api}>{ui}</ApiTestProvider>
    </FluentProvider>,
  );
}

describe("Home", () => {
  it("shows profile, missing manager and sent subjects", async () => {
    const api = new Api("", async () => "t");
    vi.spyOn(api, "me").mockResolvedValue(ME);
    renderWith(api, <Home />);
    expect(await screen.findByText("Asha Rao")).toBeInTheDocument();
    expect(screen.getByText("No manager listed in your directory.")).toBeInTheDocument();
    expect(screen.getByText("Re: SOW")).toBeInTheDocument();
    expect(screen.getByText(/Vanimo stores none of this/)).toBeInTheDocument();
  });

  it("explains a missing assignment", async () => {
    const api = new Api("", async () => "t");
    vi.spyOn(api, "me").mockRejectedValue(new ApiError(403, "not_assigned"));
    renderWith(api, <Home />);
    expect(await screen.findByText(/hasn't been given access/)).toBeInTheDocument();
  });
});

describe("errorText", () => {
  it("never echoes raw error messages", () => {
    expect(errorText(new Error("secret client name"))).not.toContain("secret");
    expect(errorText(new ApiError(502, "graph_error", { graphCode: "ErrorAccessDenied" }))).toContain("ErrorAccessDenied");
  });
});

describe("Teams deep links", () => {
  it("encodes recipients and message", () => {
    const url = newChatLink("a@x.com, b@x.com", "hi & bye");
    expect(url).toBe("https://teams.microsoft.com/l/chat/0/0?users=a%40x.com%2Cb%40x.com&message=hi%20%26%20bye");
  });
  it("targets an existing chat by id", () => {
    expect(existingChatLink(" 19:abc@thread.v2 ", "x")).toBe(
      "https://teams.microsoft.com/l/chat/19%3Aabc%40thread.v2/conversations?message=x",
    );
  });
});

describe("Api client", () => {
  it("sends the bearer token and maps errors to codes", async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify({ error: "admin_role_required" }), { status: 403 }));
    vi.stubGlobal("fetch", fetchMock);
    const api = new Api("https://api.test", async () => "tok");
    await expect(api.runDiagnostics()).rejects.toMatchObject({ status: 403, code: "admin_role_required" });
    const [url, init] = fetchMock.mock.calls[0]!;
    expect(url).toBe("https://api.test/api/admin/diagnostics/run");
    expect(init.headers.Authorization).toBe("Bearer tok");
    vi.unstubAllGlobals();
  });
});
