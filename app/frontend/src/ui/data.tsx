/** Lists, metrics, time and keyboard hints. Rows are hairline-separated (no zebra, no cards per
 * row); numbers are tabular; dates are relative with the exact time on hover. */
import { makeStyles, mergeClasses, shorthands, tokens, Tooltip } from "@fluentui/react-components";
import type { ElementType, KeyboardEvent, MouseEvent, ReactNode } from "react";
import { hoverTransition } from "../theme/motion";
import { vt } from "../theme/theme";
import { typo } from "../theme/typography";

const useStyles = makeStyles({
  list: {
    display: "grid",
    margin: 0,
    padding: 0,
    listStyle: "none",
    "& > li:first-child > *": { borderTopColor: "transparent" },
  },
  bordered: {
    border: `1px solid ${tokens.colorNeutralStroke2}`,
    borderRadius: tokens.borderRadiusXLarge,
    backgroundColor: tokens.colorNeutralBackground1,
    overflow: "hidden",
  },
  row: {
    ...hoverTransition,
    display: "grid",
    gridTemplateColumns: "auto minmax(0, 1fr) auto",
    alignItems: "center",
    gap: "12px",
    minHeight: "40px",
    padding: "10px 16px",
    ...shorthands.borderStyle("solid", "none", "none", "none"),
    ...shorthands.borderWidth("1px", "0", "0", "0"),
    borderTopColor: tokens.colorNeutralStroke3,
    textAlign: "left",
    width: "100%",
    backgroundColor: "transparent",
    color: "inherit",
    font: "inherit",
    textDecoration: "none",
    position: "relative",
  },
  first: { borderTopColor: "transparent" },
  clickable: {
    cursor: "pointer",
    "@media (hover: hover)": { ":hover": { backgroundColor: tokens.colorNeutralBackground1Hover } },
    ":focus-visible": { outline: `2px solid ${tokens.colorStrokeFocus2}`, outlineOffset: "-2px", borderRadius: "6px" },
  },
  selected: {
    backgroundColor: tokens.colorNeutralBackground1Selected,
    "::before": {
      content: '""',
      position: "absolute",
      left: 0,
      top: "8px",
      bottom: "8px",
      width: "2px",
      borderRadius: "2px",
      backgroundColor: vt.accent,
    },
    "@media (hover: hover)": { ":hover": { backgroundColor: tokens.colorNeutralBackground1Selected } },
  },
  selectedTrailing: { color: vt.text2 },
  noLeading: { gridTemplateColumns: "minmax(0, 1fr) auto" },
  leading: { display: "grid", placeItems: "center", color: vt.text2 },
  body: { display: "grid", gap: "2px", minWidth: 0 },
  title: { ...typo.itemTitle, color: vt.text1, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" },
  titleWrap: { whiteSpace: "normal" },
  meta: { ...typo.meta, color: vt.text2, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" },
  metaWrap: { whiteSpace: "normal" },
  trailing: { display: "flex", alignItems: "center", gap: "8px", ...typo.meta, color: vt.text3, ...typo.tabular },
  strip: {
    display: "grid",
    gridTemplateColumns: "repeat(auto-fit, minmax(160px, 1fr))",
    border: `1px solid ${tokens.colorNeutralStroke2}`,
    borderRadius: tokens.borderRadiusXLarge,
    backgroundColor: tokens.colorNeutralBackground1,
    overflow: "hidden", // clips the first row's and column's outer hairlines
  },
  stat: {
    ...hoverTransition,
    display: "grid",
    gap: "4px",
    padding: "16px 20px",
    textAlign: "left",
    border: "none",
    backgroundColor: tokens.colorNeutralBackground1,
    // Hairlines on each cell's left and top: whatever the wrap, rows and columns stay ruled.
    boxShadow: `-1px 0 0 0 ${tokens.colorNeutralStroke3}, 0 -1px 0 0 ${tokens.colorNeutralStroke3}`,
    color: "inherit",
    font: "inherit",
    minWidth: 0,
  },
  statClickable: {
    cursor: "pointer",
    "@media (hover: hover)": { ":hover": { backgroundColor: tokens.colorNeutralBackground1Hover } },
    ":focus-visible": { outline: `2px solid ${tokens.colorStrokeFocus2}`, outlineOffset: "-2px" },
  },
  statValue: { ...typo.metric, color: vt.text1 },
  statLabel: { ...typo.meta, color: vt.text2 },
  statHint: { ...typo.label, fontWeight: 400, color: vt.text3 },
  kbd: {
    display: "inline-grid",
    placeItems: "center",
    minWidth: "20px",
    height: "20px",
    padding: "0 5px",
    borderRadius: tokens.borderRadiusSmall,
    backgroundColor: vt.inset,
    border: `1px solid ${tokens.colorNeutralStroke2}`,
    color: vt.text2,
    fontFamily: tokens.fontFamilyBase,
    fontSize: "11px",
    fontWeight: 500,
    lineHeight: 1,
  },
  time: { ...typo.tabular, whiteSpace: "nowrap" },
});

export function List({ children, bordered, className, label }: { children: ReactNode; bordered?: boolean; className?: string; label?: string }) {
  const s = useStyles();
  return (
    <ul className={mergeClasses(s.list, bordered && s.bordered, className)} aria-label={label}>
      {children}
    </ul>
  );
}

/** One row: optional leading icon, a title and a meta line, and trailing meta or actions. Clickable
 * rows are buttons (or links with `href`). */
export function ListRow({
  title,
  meta,
  leading,
  trailing,
  selected,
  onClick,
  href,
  first,
  wrap,
  className,
  "aria-label": ariaLabel,
  "aria-current": ariaCurrent,
}: {
  title: ReactNode;
  meta?: ReactNode;
  leading?: ReactNode;
  trailing?: ReactNode;
  selected?: boolean;
  onClick?: (e: MouseEvent) => void;
  href?: string;
  first?: boolean;
  /** Let title and meta wrap instead of truncating. */
  wrap?: boolean;
  className?: string;
  "aria-label"?: string;
  "aria-current"?: boolean | "page" | "true";
}) {
  const s = useStyles();
  const clickable = Boolean(onClick || href);
  const Tag: ElementType = href ? "a" : onClick ? "button" : "div";
  return (
    <li>
      <Tag
        className={mergeClasses(
          s.row,
          !leading && s.noLeading,
          first && s.first,
          clickable && s.clickable,
          selected && s.selected,
          className,
        )}
        onClick={onClick}
        href={href}
        type={Tag === "button" ? "button" : undefined}
        aria-label={ariaLabel}
        aria-current={ariaCurrent ?? (selected && clickable ? "true" : undefined)}
      >
        {leading && <span className={s.leading}>{leading}</span>}
        <span className={s.body}>
          <span className={mergeClasses(s.title, wrap && s.titleWrap)}>{title}</span>
          {meta && <span className={mergeClasses(s.meta, wrap && s.metaWrap)}>{meta}</span>}
        </span>
        {trailing && <span className={mergeClasses(s.trailing, selected && s.selectedTrailing)}>{trailing}</span>}
      </Tag>
    </li>
  );
}

/** A thin strip of 2–4 key numbers, each optionally a link to its page. */
export function StatStrip({ children, label }: { children: ReactNode; label?: string }) {
  const s = useStyles();
  return (
    <div className={s.strip} role="group" aria-label={label}>
      {children}
    </div>
  );
}

export function Stat({ value, label, hint, onClick }: { value: ReactNode; label: ReactNode; hint?: ReactNode; onClick?: () => void }) {
  const s = useStyles();
  const Tag: ElementType = onClick ? "button" : "div";
  return (
    <Tag className={mergeClasses(s.stat, onClick && s.statClickable)} onClick={onClick} type={onClick ? "button" : undefined}>
      <span className={s.statValue}>{value}</span>
      <span className={s.statLabel}>{label}</span>
      {hint && <span className={s.statHint}>{hint}</span>}
    </Tag>
  );
}

export const isMac = typeof navigator !== "undefined" && /Mac|iPhone|iPad/.test(navigator.platform || navigator.userAgent);

/** "Ctrl" on Windows/Linux, "⌘" on macOS. */
export const modKey = isMac ? "⌘" : "Ctrl";

export function Kbd({ children }: { children: ReactNode }) {
  const s = useStyles();
  return <kbd className={s.kbd}>{children}</kbd>;
}

/** Was this keyboard event the app-wide modifier (Ctrl, or ⌘ on macOS) plus `key`? */
export function isMod(e: KeyboardEvent | globalThis.KeyboardEvent, key: string): boolean {
  return (isMac ? e.metaKey : e.ctrlKey) && !e.altKey && e.key.toLowerCase() === key.toLowerCase();
}

const DAY = 86_400_000;

/** "just now", "5 min ago", "3 h ago", "Yesterday", "Tue", "12 Oct", "12 Oct 2025"; future dates
 * read "in 3 h", "Tomorrow", "Fri", "14 Nov". */
export function relativeTime(iso: string, now: Date = new Date()): string {
  const d = new Date(iso);
  const ms = d.getTime() - now.getTime();
  const abs = Math.abs(ms);
  const future = ms > 0;
  if (Number.isNaN(ms)) return "";
  if (abs < 60_000) return future ? "in a moment" : "just now";
  if (abs < 3_600_000) {
    const m = Math.round(abs / 60_000);
    return future ? `in ${m} min` : `${m} min ago`;
  }
  const startOf = (x: Date) => new Date(x.getFullYear(), x.getMonth(), x.getDate()).getTime();
  const dayDiff = Math.round((startOf(d) - startOf(now)) / DAY);
  if (dayDiff === 0) {
    const h = Math.round(abs / 3_600_000);
    return future ? `in ${h} h` : `${h} h ago`;
  }
  if (dayDiff === -1) return "Yesterday";
  if (dayDiff === 1) return "Tomorrow";
  if (Math.abs(dayDiff) < 7) return d.toLocaleDateString(undefined, { weekday: "short" });
  const sameYear = d.getFullYear() === now.getFullYear();
  return d.toLocaleDateString(undefined, { day: "numeric", month: "short", ...(sameYear ? {} : { year: "numeric" }) });
}

export function absoluteTime(iso: string): string {
  return new Date(iso).toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" });
}

/** A relative date with the exact date and time in a tooltip. */
export function Time({ iso, className }: { iso: string; className?: string }) {
  const s = useStyles();
  return (
    <Tooltip content={absoluteTime(iso)} relationship="description" withArrow>
      <time dateTime={iso} className={mergeClasses(s.time, className)}>
        {relativeTime(iso)}
      </time>
    </Tooltip>
  );
}
