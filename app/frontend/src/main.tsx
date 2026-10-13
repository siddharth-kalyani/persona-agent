import { MsalProvider } from "@azure/msal-react";
import { FluentProvider, webLightTheme } from "@fluentui/react-components";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import { App } from "./App";
import { ApiProvider } from "./api/context";
import { createMsal } from "./auth/msal";
import { loadConfig } from "./config";

async function start() {
  const root = createRoot(document.getElementById("root")!);
  try {
    const config = await loadConfig();
    const msal = await createMsal(config);
    root.render(
      <StrictMode>
        <FluentProvider theme={webLightTheme}>
          <MsalProvider instance={msal}>
            <ApiProvider msal={msal} config={config}>
              <BrowserRouter>
                <App />
              </BrowserRouter>
            </ApiProvider>
          </MsalProvider>
        </FluentProvider>
      </StrictMode>,
    );
  } catch (err) {
    root.render(<p style={{ padding: 24, fontFamily: "Segoe UI, sans-serif" }}>{(err as Error).message}</p>);
  }
}

void start();
