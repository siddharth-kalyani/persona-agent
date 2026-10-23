import { FluentProvider, webLightTheme } from "@fluentui/react-components";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";
import { App } from "../App";
import { Api, type Me } from "../api/client";
import { ApiTestProvider } from "../api/context";
import { AuthFailure, AuthTestProvider, type AuthState } from "../auth/session";

function authState(overrides: Partial<AuthState> = {}): AuthState {
  return {
    options: { microsoft: false, password: true },
    signedIn: false,
    method: null,
    email: null,
    roles: [],
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

function renderApp(auth: AuthState, api = new Api("", async () => "t")) {
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

describe("sign-in", () => {
  it("shows email + password only when Microsoft isn't configured", () => {
    renderApp(authState());
    expect(screen.getByLabelText(/Email/)).toBeInTheDocument();
    expect(screen.queryByText("Sign in with Microsoft")).not.toBeInTheDocument();
  });

  it("submits credentials and shows a friendly error", async () => {
    const signIn = vi.fn(async () => {
      throw new AuthFailure("invalid_credentials");
    });
    renderApp(authState({ signInWithPassword: signIn }));
    await userEvent.type(screen.getByLabelText(/Email/), "me@example.com");
    await userEvent.type(screen.getByLabelText(/Password/), "wrong");
    await userEvent.click(screen.getByRole("button", { name: "Sign in" }));
    expect(signIn).toHaveBeenCalledWith("me@example.com", "wrong");
    expect(await screen.findByText(/That email and password don't match/)).toBeInTheDocument();
  });

  it("forces a password change before anything else", async () => {
    const change = vi.fn(async () => undefined);
    renderApp(authState({ signedIn: true, method: "password", email: "me@example.com", mustChangePassword: true, changePassword: change }));
    expect(screen.getByText("Set your password")).toBeInTheDocument();
    expect(screen.queryByRole("navigation", { name: "Main" })).not.toBeInTheDocument();
    const button = screen.getByRole("button", { name: "Set password" });
    await userEvent.type(screen.getByLabelText(/One-time password/), "ABCD-efgh-2345-jkmn");
    await userEvent.type(screen.getByLabelText(/^New password/), "a long enough phrase");
    await userEvent.type(screen.getByLabelText(/Confirm new password/), "a long enough phrase!");
    expect(button).toBeDisabled();
    expect(screen.getByText("The passwords don't match.")).toBeInTheDocument();
    await userEvent.type(screen.getByLabelText(/Confirm new password/), "{backspace}");
    await userEvent.click(button);
    expect(change).toHaveBeenCalledWith("ABCD-efgh-2345-jkmn", "a long enough phrase");
  });

  it("super-admins see the admin pages in the sidebar and a Microsoft 365 notice", async () => {
    const api = new Api("", async () => "t");
    const me: Me = {
      user: { displayName: "Me Example", jobTitle: "Engagement Manager" },
      manager: { displayName: "Meera Iyer", jobTitle: "Director, Delivery" },
      recentSent: [{ subject: "Weekly status: Acme replatforming", sentDateTime: "2026-10-12T10:00:00Z", recipientCount: 2 }],
      roles: ["Vanimo.Admin", "Vanimo.SuperAdmin", "Vanimo.User"],
      onboardingState: "review_pending",
      signInMethod: "password",
      email: "me@example.com",
      dataSource: "sample",
      microsoft365Connected: false,
    };
    vi.spyOn(api, "me").mockResolvedValue(me);
    renderApp(
      authState({ signedIn: true, method: "password", email: "me@example.com", roles: me.roles, isAdmin: true }),
      api,
    );
    const nav = screen.getAllByRole("navigation", { name: "Main" })[0]!;
    expect(within(nav).getByRole("link", { name: "Diagnostics" })).toBeInTheDocument();
    expect(within(nav).getByRole("link", { name: "Home" })).toHaveAttribute("aria-current", "page");
    expect(screen.getByText("Super-admin")).toBeInTheDocument();
    expect(await screen.findByText(/You're seeing the sample workspace/)).toBeInTheDocument();
    expect(screen.getByText("Meera Iyer")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Choose what Vanimo learns from/ })).toBeInTheDocument();
  });
});
