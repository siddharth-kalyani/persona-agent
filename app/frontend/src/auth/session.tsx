/** One auth context for both sign-in methods: Microsoft (MSAL) and local email + password. */
import type { IPublicClientApplication } from "@azure/msal-browser";
import { createContext, useCallback, useContext, useMemo, useState, type ReactNode } from "react";
import type { AppConfig, SignInOptions } from "../config";
import { apiScope } from "../config";
import { getApiToken } from "./msal";

const STORAGE_KEY = "vanimo.session";

export interface PasswordSession {
  token: string;
  expiresAt: string;
  mustChangePassword: boolean;
  roles: string[];
  email: string;
}

export interface AuthState {
  options: SignInOptions;
  signedIn: boolean;
  method: "microsoft" | "password" | null;
  email: string | null;
  roles: string[];
  isAdmin: boolean;
  mustChangePassword: boolean;
  token: () => Promise<string>;
  signInWithPassword: (email: string, password: string) => Promise<void>;
  changePassword: (current: string, next: string) => Promise<void>;
  signInWithMicrosoft: () => Promise<void>;
  signOut: () => Promise<void>;
  /** Drop a local session the API no longer accepts (expired, revoked). */
  expire: () => void;
}

export class AuthFailure extends Error {
  constructor(public readonly code: string) {
    super(code);
  }
}

function readStored(): PasswordSession | null {
  try {
    const raw = sessionStorage.getItem(STORAGE_KEY);
    if (!raw) return null;
    const session = JSON.parse(raw) as PasswordSession;
    return new Date(session.expiresAt) > new Date() ? session : null;
  } catch {
    return null;
  }
}

function store(session: PasswordSession | null) {
  try {
    if (session) sessionStorage.setItem(STORAGE_KEY, JSON.stringify(session));
    else sessionStorage.removeItem(STORAGE_KEY);
  } catch {
    // Storage unavailable (private mode): the session lives in memory for this tab only.
  }
}

async function postJson(url: string, body: unknown, token?: string): Promise<Record<string, unknown>> {
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  if (token) headers.Authorization = `Bearer ${token}`;
  const res = await fetch(url, { method: "POST", headers, body: JSON.stringify(body) });
  const json = res.status === 204 ? {} : await res.json().catch(() => ({}));
  if (!res.ok) throw new AuthFailure(String((json as { error?: string }).error ?? `http_${res.status}`));
  return json as Record<string, unknown>;
}

const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({
  config,
  options,
  msal,
  children,
}: {
  config: AppConfig;
  options: SignInOptions;
  msal: IPublicClientApplication | null;
  children: ReactNode;
}) {
  const [session, setSession] = useState<PasswordSession | null>(() => readStored());
  const msalAccount = msal?.getActiveAccount() ?? null;

  const save = useCallback((s: PasswordSession | null) => {
    store(s);
    setSession(s);
  }, []);

  const signInWithPassword = useCallback(
    async (email: string, password: string) => {
      const body = await postJson(`${config.apiBase}/api/auth/login`, { email, password });
      save({ ...(body as unknown as Omit<PasswordSession, "email">), email: email.trim().toLowerCase() });
    },
    [config.apiBase, save],
  );

  const changePassword = useCallback(
    async (current: string, next: string) => {
      if (!session) throw new AuthFailure("session_expired");
      const body = await postJson(
        `${config.apiBase}/api/auth/change-password`,
        { currentPassword: current, newPassword: next },
        session.token,
      );
      save({ ...(body as unknown as Omit<PasswordSession, "email">), email: session.email });
    },
    [config.apiBase, save, session],
  );

  const signOut = useCallback(async () => {
    if (session) {
      await postJson(`${config.apiBase}/api/auth/logout`, {}, session.token).catch(() => undefined);
      save(null);
      return;
    }
    if (msal) await msal.logoutRedirect();
  }, [config.apiBase, msal, save, session]);

  const value = useMemo<AuthState>(() => {
    const roles = session?.roles ?? ((msalAccount?.idTokenClaims?.roles as string[] | undefined) ?? []);
    const method = session ? "password" : msalAccount ? "microsoft" : null;
    return {
      options,
      signedIn: method !== null,
      method,
      email: session?.email ?? msalAccount?.username ?? null,
      roles,
      isAdmin: roles.includes("Vanimo.Admin") || roles.includes("Vanimo.SuperAdmin"),
      mustChangePassword: session?.mustChangePassword ?? false,
      token: async () => {
        if (session) return session.token;
        if (msal) return getApiToken(msal, config);
        throw new AuthFailure("not_signed_in");
      },
      signInWithPassword,
      changePassword,
      signInWithMicrosoft: async () => {
        if (!msal) throw new AuthFailure("microsoft_signin_not_configured");
        await msal.loginRedirect({ scopes: [apiScope(config)] });
      },
      signOut,
      expire: () => save(null),
    };
  }, [changePassword, config, msal, msalAccount, options, save, session, signInWithPassword, signOut]);

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function AuthTestProvider({ value, children }: { value: AuthState; children: ReactNode }) {
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthState {
  const auth = useContext(AuthContext);
  if (!auth) throw new Error("useAuth outside AuthProvider");
  return auth;
}
