/** Light, dark or the system's choice. The preference is a per-browser convenience (localStorage);
 * the page renders correctly without it. */
import { AriaLiveAnnouncer, FluentProvider } from "@fluentui/react-components";
import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { useGlobalStyles } from "./global";
import { vanimoDark, vanimoLight } from "./theme";

export type ThemePreference = "system" | "light" | "dark";

const KEY = "vanimo.theme";

interface ThemeState {
  preference: ThemePreference;
  mode: "light" | "dark";
  setPreference: (p: ThemePreference) => void;
}

const ThemeContext = createContext<ThemeState>({ preference: "system", mode: "light", setPreference: () => undefined });

function stored(): ThemePreference {
  try {
    const v = localStorage.getItem(KEY);
    return v === "light" || v === "dark" ? v : "system";
  } catch {
    return "system";
  }
}

function systemDark(): boolean {
  return typeof window !== "undefined" && window.matchMedia?.("(prefers-color-scheme: dark)").matches === true;
}

export function VanimoThemeProvider({ children }: { children: ReactNode }) {
  useGlobalStyles();
  const [preference, setPreferenceState] = useState<ThemePreference>(stored);
  const [dark, setDark] = useState(systemDark);

  useEffect(() => {
    const mq = window.matchMedia?.("(prefers-color-scheme: dark)");
    if (!mq) return;
    const onChange = () => setDark(mq.matches);
    mq.addEventListener("change", onChange);
    return () => mq.removeEventListener("change", onChange);
  }, []);

  const mode = preference === "system" ? (dark ? "dark" : "light") : preference;

  useEffect(() => {
    // Native form controls and scrollbars follow too; no transition on theme change.
    document.documentElement.style.colorScheme = mode;
    document.documentElement.dataset.theme = mode;
  }, [mode]);

  const value = useMemo<ThemeState>(
    () => ({
      preference,
      mode,
      setPreference: (p) => {
        setPreferenceState(p);
        try {
          if (p === "system") localStorage.removeItem(KEY);
          else localStorage.setItem(KEY, p);
        } catch {
          // Private window or blocked storage: the choice lasts for this visit only.
        }
      },
    }),
    [preference, mode],
  );

  return (
    <ThemeContext.Provider value={value}>
      {/* No className here: Fluent copies the provider's classes onto every portal mount node (menus,
          tooltips, the live announcer), so a layout style on it would cover the page. The shell and
          the signed-out screens paint the frame themselves. */}
      <FluentProvider theme={mode === "dark" ? vanimoDark : vanimoLight}>
        <AriaLiveAnnouncer>{children}</AriaLiveAnnouncer>
      </FluentProvider>
    </ThemeContext.Provider>
  );
}

export function useThemePreference(): ThemeState {
  return useContext(ThemeContext);
}
