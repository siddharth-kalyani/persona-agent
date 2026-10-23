import { FluentProvider, webLightTheme } from "@fluentui/react-components";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { CommandPalette, score, type Command } from "../shell/CommandPalette";
import { activePath, visibleDestinations } from "../shell/nav";
import { useThemePreference, VanimoThemeProvider } from "../theme/ThemeProvider";
import { vanimoDark, vanimoLight, vt } from "../theme/theme";
import { relativeTime } from "./data";

describe("relativeTime", () => {
  const now = new Date("2026-10-23T12:00:00");
  it("reads naturally in both directions", () => {
    expect(relativeTime("2026-10-23T11:59:40", now)).toBe("just now");
    expect(relativeTime("2026-10-23T11:15:00", now)).toBe("45 min ago");
    expect(relativeTime("2026-10-23T09:00:00", now)).toBe("3 h ago");
    expect(relativeTime("2026-10-22T09:00:00", now)).toBe("Yesterday");
    expect(relativeTime("2026-10-24T09:00:00", now)).toBe("Tomorrow");
    expect(relativeTime("2026-10-23T15:00:00", now)).toBe("in 3 h");
    expect(relativeTime("not a date", now)).toBe("");
  });
});

describe("theme", () => {
  it("defines every Vanimo token in both themes, with a light fallback for other surfaces", () => {
    for (const ref of Object.values(vt)) {
      const name = ref.match(/var\(--(\w+),/)![1]! as keyof typeof vanimoLight;
      expect(vanimoLight[name]).toBeTruthy();
      expect(vanimoDark[name]).toBeTruthy();
      expect(ref).toContain(String(vanimoLight[name]));
    }
    expect(vanimoLight.fontFamilyBase).toMatch(/^'Inter Variable'/);
    expect(vanimoDark.colorNeutralBackground1).not.toBe(vanimoLight.colorNeutralBackground1);
  });

  it("remembers an explicit choice and follows the system otherwise", async () => {
    function Probe() {
      const t = useThemePreference();
      return (
        <button type="button" onClick={() => t.setPreference(t.mode === "dark" ? "light" : "dark")}>
          {t.preference}:{t.mode}
        </button>
      );
    }
    localStorage.removeItem("vanimo.theme");
    render(
      <VanimoThemeProvider>
        <Probe />
      </VanimoThemeProvider>,
    );
    const button = screen.getByRole("button");
    expect(button).toHaveTextContent("system:light");
    await userEvent.click(button);
    expect(button).toHaveTextContent("dark:dark");
    expect(localStorage.getItem("vanimo.theme")).toBe("dark");
    expect(document.documentElement.dataset.theme).toBe("dark");
    localStorage.removeItem("vanimo.theme");
  });
});

describe("navigation", () => {
  it("shows admin pages to admins and the sample workspace only with sample data", () => {
    const user = visibleDestinations({ isAdmin: false, sample: false }).map((d) => d.label);
    expect(user).not.toContain("Diagnostics");
    expect(user).not.toContain("Sample workspace");
    expect(visibleDestinations({ isAdmin: true, sample: true }).map((d) => d.label)).toEqual(
      expect.arrayContaining(["Diagnostics", "Sample workspace", "Redaction checks"]),
    );
  });

  it("marks the section a path belongs to", () => {
    expect(activePath("/")).toBe("/");
    expect(activePath("/draft")).toBe("/draft");
    expect(activePath("/admin/backstops")).toBe("/admin/backstops");
    expect(activePath("/nowhere")).toBe("/");
  });
});

describe("command palette", () => {
  const commands = (run = vi.fn()): Command[] => [
    { id: "home", label: "Home", group: "Go to", run },
    { id: "commitments", label: "Commitments", group: "Go to", aliases: ["promises"], run },
    { id: "redaction", label: "Redaction checks", group: "Go to", aliases: ["pii", "macie"], run },
  ];

  it("ranks prefix over substring over alias over loose letters", () => {
    const [home, commitments, redaction] = commands();
    expect(score(commitments!, "comm")).toBeGreaterThan(score(redaction!, "checks"));
    expect(score(redaction!, "pii")).toBe(2);
    expect(score(commitments!, "cmmt")).toBe(1);
    expect(score(home!, "zzz")).toBe(0);
  });

  it("filters as you type and runs the highlighted command with Enter", async () => {
    const run = vi.fn();
    const onOpenChange = vi.fn();
    render(
      <FluentProvider theme={webLightTheme}>
        <CommandPalette open onOpenChange={onOpenChange} commands={commands(run)} />
      </FluentProvider>,
    );
    const input = screen.getByRole("combobox", { name: "Search pages and actions" });
    await userEvent.type(input, "promises");
    expect(screen.getAllByRole("option")).toHaveLength(1);
    expect(screen.getByRole("option")).toHaveTextContent("Commitments");
    await userEvent.keyboard("{Enter}");
    expect(run).toHaveBeenCalledTimes(1);
    expect(onOpenChange).toHaveBeenCalledWith(false);
  });

  it("says so when nothing matches", async () => {
    render(
      <FluentProvider theme={webLightTheme}>
        <CommandPalette open onOpenChange={() => undefined} commands={commands()} />
      </FluentProvider>,
    );
    await userEvent.type(screen.getByRole("combobox"), "qqq");
    expect(screen.getByText(/Nothing matches/)).toBeInTheDocument();
  });
});
