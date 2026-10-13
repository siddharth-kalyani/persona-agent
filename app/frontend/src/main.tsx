import type { IPublicClientApplication } from "@azure/msal-browser";
import { MsalProvider } from "@azure/msal-react";
import { FluentProvider, webLightTheme } from "@fluentui/react-components";
import { StrictMode, type ReactNode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import { App } from "./App";
import { ApiProvider } from "./api/context";
import { createMsal } from "./auth/msal";
import { AuthProvider } from "./auth/session";
import { loadConfig, loadSignInOptions } from "./config";

async function start() {
  const root = createRoot(document.getElementById("root")!);
  try {
    const config = await loadConfig();
    const options = await loadSignInOptions(config);
    const msal: IPublicClientApplication | null = options.microsoft ? await createMsal(config) : null;
    const withMsal = (children: ReactNode) => (msal ? <MsalProvider instance={msal}>{children}</MsalProvider> : children);
    root.render(
      <StrictMode>
        <FluentProvider theme={webLightTheme}>
          {withMsal(
            <AuthProvider config={config} options={options} msal={msal}>
              <ApiProvider config={config}>
                <BrowserRouter>
                  <App />
                </BrowserRouter>
              </ApiProvider>
            </AuthProvider>,
          )}
        </FluentProvider>
      </StrictMode>,
    );
  } catch (err) {
    root.render(<p style={{ padding: 24, fontFamily: "Segoe UI, sans-serif" }}>{(err as Error).message}</p>);
  }
}

void start();
