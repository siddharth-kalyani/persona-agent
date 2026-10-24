import { AnnounceProvider, Button, FluentProvider, Input, Popover, PopoverSurface, PopoverTrigger, webLightTheme } from "@fluentui/react-components";
import { Delete16Regular } from "@fluentui/react-icons";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { CommandPalette, score, type Command } from "../shell/CommandPalette";
import { activePath, visibleDestinations } from "../shell/nav";
import { useThemePreference, VanimoThemeProvider } from "../theme/ThemeProvider";
import { vanimoDark, vanimoLight, vt } from "../theme/theme";
import { relativeTime } from "./data";
import { IconAction, initialsOf } from "./visual";
import { DraftView } from "../drafting/DraftView";
import type { Draft } from "../api/client";

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

describe("initialsOf", () => {
  it("uses words that start with a letter and ignores brackets", () => {
    expect(initialsOf("Meera Iyer")).toBe("MI");
    expect(initialsOf("Kestrel Colleague 01")).toBe("KC");
    expect(initialsOf("Nisha (home)")).toBe("N");
    expect(initialsOf("")).toBe("");
  });
});

describe("draft checks", () => {
  it("are announced when they appear: blocking ones at once", async () => {
    const announce = vi.fn();
    const draft = {
      id: "d1", text: "Hi", generator: "offline", label: "Offline stand-in", modelId: "m", tier: "default", routeReason: "default",
      audience: { relationship: "external", label: "someone outside your organisation", to: [], cc: [], internal: 0, external: 1 },
      styleSlice: "", learned: false, basedOn: 0, exemplars: 0, checks: [], insertAllowed: false, oneOff: false,
      timing: { totalMs: 1, modelMs: null },
    } as unknown as Draft; // prettier-ignore
    render(
      <AnnounceProvider value={{ announce }}>
        <DraftView
          draft={draft}
          text="Hi"
          onTextChange={() => undefined}
          checks={[
            { code: "fill_in", severity: "info", message: "Fill in [x]." },
            { code: "payment_change", severity: "block", message: "This email asks to change payment details." },
          ]}
          confirmed={false}
          onConfirm={() => undefined}
          actions={null}
        />
      </AnnounceProvider>,
    );
    expect(announce).toHaveBeenCalledWith("Check before sending: This email asks to change payment details.", { alert: true });
    expect(announce).toHaveBeenCalledWith("Note: Fill in [x].", { polite: true });
    expect(screen.getByRole("group", { name: "Check before sending" })).toHaveTextContent("change payment details");
  });
});

describe("app-wide Fluent styling", () => {
  it("gives fields one even hairline and secondary buttons the raised fill, without touching page styles", () => {
    render(
      <VanimoThemeProvider>
        <Input aria-label="Name" />
        <Button>Save</Button>
        <Button appearance="primary" style={{ color: "red" }}>
          Go
        </Button>
      </VanimoThemeProvider>,
    );
    const field = screen.getByRole("textbox", { name: "Name" }).parentElement!;
    expect(field.style.getPropertyValue("--colorNeutralStrokeAccessible")).toBe(vt.borderStrong);
    expect(field.style.getPropertyValue("--colorNeutralBackground1")).toBe(vt.field);
    expect(screen.getByRole("button", { name: "Save" }).style.getPropertyValue("--colorNeutralBackground1")).toBe(vt.button);
    // A page's own inline style still wins, and primary buttons keep the brand fill.
    const go = screen.getByRole("button", { name: "Go" });
    expect(go.style.color).toBe("red");
    expect(go.style.getPropertyValue("--colorNeutralBackground1")).toBe("");
  });

  it("names icon-only actions by their tooltip", async () => {
    const onClick = vi.fn();
    render(
      <VanimoThemeProvider>
        <IconAction icon={<Delete16Regular />} label="Discard" onClick={onClick} />
      </VanimoThemeProvider>,
    );
    await userEvent.click(screen.getByRole("button", { name: "Discard" }));
    expect(onClick).toHaveBeenCalledTimes(1);
  });
});

describe("portals", () => {
  it("never get page-layout styles from the theme provider (they would cover the app)", async () => {
    const { container } = render(
      <VanimoThemeProvider>
        <Popover open>
          <PopoverTrigger>
            <button type="button">Open</button>
          </PopoverTrigger>
          <PopoverSurface>Inside a portal</PopoverSurface>
        </Popover>
      </VanimoThemeProvider>,
    );
    const surface = await screen.findByText("Inside a portal");
    const mount = [...document.body.children].find((el) => el !== container && el.contains(surface)) as HTMLElement;
    expect(mount).toBeTruthy();
    // jsdom doesn't apply Griffel's rules to computed styles, so read the rules themselves: none of the
    // mount node's classes may give it a height or fix it in place (it would lay a sheet over the app;
    // Fluent's own background on the zero-height node is harmless).
    const rules = [...document.styleSheets].flatMap((sheet) => [...sheet.cssRules]) as CSSStyleRule[];
    const offending = rules.filter(
      (r) =>
        r.selectorText &&
        [...mount.classList].some((c) => r.selectorText.split(/[\s,>+~]+/).includes(`.${c}`)) &&
        /(^|[\s{;])(min-)?height:|position:\s*fixed|inset:/.test(r.cssText),
    );
    expect(offending.map((r) => r.cssText)).toEqual([]);
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
