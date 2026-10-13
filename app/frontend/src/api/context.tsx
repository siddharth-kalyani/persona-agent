import type { IPublicClientApplication } from "@azure/msal-browser";
import { createContext, useContext, useMemo, type ReactNode } from "react";
import { getApiToken } from "../auth/msal";
import type { AppConfig } from "../config";
import { Api } from "./client";

const ApiContext = createContext<Api | null>(null);
const ConfigContext = createContext<AppConfig | null>(null);

export function ApiProvider({
  msal,
  config,
  children,
}: {
  msal: IPublicClientApplication;
  config: AppConfig;
  children: ReactNode;
}) {
  const api = useMemo(() => new Api(config.apiBase, () => getApiToken(msal, config)), [msal, config]);
  return (
    <ConfigContext.Provider value={config}>
      <ApiContext.Provider value={api}>{children}</ApiContext.Provider>
    </ConfigContext.Provider>
  );
}

export function useConfig(): AppConfig {
  const config = useContext(ConfigContext);
  if (!config) throw new Error("useConfig outside ApiProvider");
  return config;
}

export function ApiTestProvider({ api, children }: { api: Api; children: ReactNode }) {
  return <ApiContext.Provider value={api}>{children}</ApiContext.Provider>;
}

export function useApi(): Api {
  const api = useContext(ApiContext);
  if (!api) throw new Error("useApi outside ApiProvider");
  return api;
}
