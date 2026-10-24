import type { IPublicClientApplication } from "@azure/msal-browser";
import { MsalProvider } from "@azure/msal-react";
import "@fontsource-variable/inter/opsz.css";
import "@fontsource-variable/jetbrains-mono";
import "./theme/global.css";
import { StrictMode, type ReactNode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import { App } from "./App";
import { ApiProvider } from "./api/context";
import { createMsal } from "./auth/msal";
import { AuthProvider } from "./auth/session";
import { loadConfig, loadSignInOptions } from "./config";
import { VanimoThemeProvider } from "./theme/ThemeProvider";

async function start() {
  const root = createRoot(document.getElementById("root")!);
  try {
    const config = await loadConfig();
    const options = await loadSignInOptions(config);
    const msal: IPublicClientApplication | null = options.microsoft ? await createMsal(config) : null;
    const withMsal = (children: ReactNode) => (msal ? <MsalProvider instance={msal}>{children}</MsalProvider> : children);
    root.render(
      <StrictMode>
        <VanimoThemeProvider>
          {withMsal(
            <AuthProvider config={config} options={options} msal={msal}>
              <ApiProvider config={config}>
                <BrowserRouter>
                  <App />
                </BrowserRouter>
              </ApiProvider>
            </AuthProvider>,
          )}
        </VanimoThemeProvider>
      </StrictMode>,
    );
  } catch (err) {
    root.render(
      <p style={{ padding: 24, fontFamily: "'Inter Variable', 'Segoe UI', sans-serif", color: "#111318" }}>
        {(err as Error).message}
      </p>,
    );
  }
}

void start();
