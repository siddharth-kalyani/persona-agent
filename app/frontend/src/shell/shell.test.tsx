import { FluentProvider, webLightTheme } from "@fluentui/react-components";
import { act, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";
import { App } from "../App";
import { Api, type Me } from "../api/client";
import { ApiTestProvider } from "../api/context";
import { AuthTestProvider, type AuthState } from "../auth/session";
import { announceMeChanged } from "./events";

function authState(overrides: Partial<AuthState> = {}): AuthState {
  return {
    options: { microsoft: false, password: true },
    signedIn: true,
    method: "password",
    email: "asha@example.com",
    roles: ["Vanimo.User"],
    isAdmin: false,
    mustChangePassword: false,
    token: async () => "t",
    signInWithPassword: vi.fn(async () => undefined),
    changePassword: vi.fn(async () => undefined),
    signInWithMicrosoft: vi.fn(async () => undefined),
    signOut: vi.fn(async () => undefined),
    expire: vi.fn(),
    requirePasswordChange: vi.fn(),
    ...overrides,
  };
}

const ME: Me = {
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

function renderApp(auth: AuthState, api: Api) {
  return render(
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
}

describe("shell", () => {
  it("lets you sign out of a forced password change", async () => {
    const auth = authState({ method: "password", mustChangePassword: true });
    renderApp(auth, new Api("", async () => "t"));
    await userEvent.click(screen.getByRole("button", { name: "Sign out" }));
    expect(auth.signOut).toHaveBeenCalled();
  });

  it("drops the paused banner as soon as the organisation is resumed", async () => {
    const api = new Api("", async () => "t");
    const me = vi.spyOn(api, "me").mockResolvedValue(ME);
    renderApp(authState(), api);
    expect(await screen.findByText("Paused for your organisation")).toBeInTheDocument();
    me.mockResolvedValue({ ...ME, pipelinePaused: false });
    act(() => announceMeChanged());
    await waitFor(() => expect(screen.queryByText("Paused for your organisation")).toBeNull());
  });
});
