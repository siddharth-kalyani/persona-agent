import { createContext, useContext, useMemo, type ReactNode } from "react";
import { useAuth } from "../auth/session";
import type { AppConfig } from "../config";
import { Api } from "./client";

const ApiContext = createContext<Api | null>(null);

export function ApiProvider({ config, children }: { config: AppConfig; children: ReactNode }) {
  const auth = useAuth();
  const api = useMemo(
    () =>
      new Api(config.apiBase, auth.token, (code) => {
        if (auth.method !== "password") return;
        if (code === "password_change_required") auth.requirePasswordChange();
        else if (["session_expired", "password_signin_disabled"].includes(code)) auth.expire();
      }),
    [auth, config.apiBase],
  );
  return <ApiContext.Provider value={api}>{children}</ApiContext.Provider>;
}

export function ApiTestProvider({ api, children }: { api: Api; children: ReactNode }) {
  return <ApiContext.Provider value={api}>{children}</ApiContext.Provider>;
}

export function useApi(): Api {
  const api = useContext(ApiContext);
  if (!api) throw new Error("useApi outside ApiProvider");
  return api;
}
