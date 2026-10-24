/** Lists, metrics, time and keyboard hints. Rows are hairline-separated inside a card (no zebra, no
 * card per row) and usually lead with an icon tile or an avatar; numbers are tabular; dates are
 * relative with the exact time on hover. */
import { makeStyles, mergeClasses, shorthands, tokens, Tooltip } from "@fluentui/react-components";
import { ChevronRight16Regular } from "@fluentui/react-icons";
import type { ElementType, KeyboardEvent, MouseEvent, ReactNode } from "react";
import { hoverTransition } from "../theme/motion";
import { vt } from "../theme/theme";
import { typo } from "../theme/typography";
import type { Tone } from "./tones";
import { TONES } from "./tones";
import { IconTile } from "./visual";

const PHONE = "@media (max-width: 639px)";

const useStyles = makeStyles({
  list: {
    display: "grid",
    margin: 0,
    padding: 0,
    listStyle: "none",
    "& > li:first-child > *": { borderTopColor: "transparent" },
  },
  bordered: {
    border: `1px solid ${vt.border}`,
    borderRadius: tokens.borderRadiusXLarge,
    backgroundColor: tokens.colorNeutralBackground1,
    boxShadow: vt.shadowCard,
    overflow: "hidden",
  },
  row: {
    ...hoverTransition,
    display: "grid",
    gridTemplateColumns: "auto minmax(0, 1fr) auto",
    alignItems: "center",
    gap: "12px",
    minHeight: "48px",
    padding: "11px 16px",
    ...shorthands.borderStyle("solid", "none", "none", "none"),
    ...shorthands.borderWidth("1px", "0", "0", "0"),
    borderTopColor: vt.borderSubtle,
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
    "@media (hover: hover)": { ":hover": { backgroundColor: vt.hover } },
    ":focus-visible": { outline: `2px solid ${tokens.colorStrokeFocus2}`, outlineOffset: "-2px", borderRadius: "8px" },
  },
  selected: {
    backgroundColor: vt.selected,
    "::before": {
      content: '""',
      position: "absolute",
      left: 0,
      top: "10px",
      bottom: "10px",
      width: "3px",
      borderRadius: "0 3px 3px 0",
      backgroundColor: vt.accent,
    },
    "@media (hover: hover)": { ":hover": { backgroundColor: vt.selected } },
  },
  selectedTrailing: { color: vt.text2 },
  noLeading: { gridTemplateColumns: "minmax(0, 1fr) auto" },
  leading: { display: "grid", placeItems: "center", color: vt.text2 },
  leadingTop: { alignSelf: "start", marginTop: "2px" },
  body: { display: "grid", gap: "2px", minWidth: 0 },
  title: { ...typo.itemTitle, color: vt.text1, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" },
  titleWrap: { whiteSpace: "normal" },
  meta: {
    ...typo.meta,
    color: vt.text2,
    overflow: "hidden",
    textOverflow: "ellipsis",
    whiteSpace: "nowrap",
    // Icons in the meta line sit on the text baseline and take its colour (a pill keeps its own).
    "& svg": { verticalAlign: "-3px" },
  },
  metaWrap: { whiteSpace: "normal" },
  trailing: { display: "flex", alignItems: "center", gap: "8px", ...typo.meta, color: vt.text3, ...typo.tabular },
  strip: {
    display: "grid",
    gridTemplateColumns: "repeat(auto-fit, minmax(160px, 1fr))",
    gap: "12px",
    [PHONE]: { gridTemplateColumns: "minmax(0, 1fr)", gap: "8px" },
  },
  stat: {
    ...hoverTransition,
    display: "grid",
    gridTemplateColumns: "minmax(0, 1fr) auto",
    gridTemplateRows: "auto auto auto",
    columnGap: "12px",
    rowGap: "2px",
    alignItems: "start",
    padding: "16px 18px",
    textAlign: "left",
    border: `1px solid ${vt.border}`,
    borderRadius: tokens.borderRadiusXLarge,
    backgroundColor: tokens.colorNeutralBackground1,
    boxShadow: vt.shadowCard,
    color: "inherit",
    font: "inherit",
    minWidth: 0,
    position: "relative",
    // Phones: one compact line per stat (tile, label and hint, value on the right), no orphans.
    [PHONE]: {
      gridTemplateColumns: "auto minmax(0, 1fr) auto",
      gridTemplateRows: "auto auto",
      alignItems: "center",
      padding: "12px 14px",
    },
  },
  statClickable: {
    cursor: "pointer",
    "@media (hover: hover)": {
      ":hover": { ...shorthands.borderColor(vt.borderStrong) },
      ":hover .vanimo-stat-go": { opacity: 1 },
    },
    ":focus-visible": { outline: `2px solid ${tokens.colorStrokeFocus2}`, outlineOffset: "2px" },
  },
  statLabel: {
    ...typo.meta,
    fontWeight: 500,
    color: vt.text2,
    gridColumn: "1",
    alignSelf: "center",
    [PHONE]: { gridColumn: "2", gridRow: "1", alignSelf: "end" },
  },
  statIcon: { gridColumn: "2", gridRow: "1 / span 2", [PHONE]: { gridColumn: "1", gridRow: "1 / span 2" } },
  statValue: {
    ...typo.metric,
    color: vt.text1,
    gridColumn: "1",
    marginTop: "6px",
    [PHONE]: { gridColumn: "3", gridRow: "1 / span 2", marginTop: 0, fontSize: "22px", lineHeight: "28px" },
  },
  statHint: {
    ...typo.meta,
    color: vt.text3,
    gridColumn: "1 / span 2",
    display: "inline-flex",
    alignItems: "center",
    gap: "6px",
    marginTop: "2px",
    minHeight: "18px", // kept even when empty, so cards in a row line up
    [PHONE]: { gridColumn: "2", gridRow: "2", marginTop: 0, minHeight: 0, alignSelf: "start" },
  },
  statHintDot: { width: "6px", height: "6px", borderRadius: "50%", flexShrink: 0 },
  statGo: {
    position: "absolute",
    right: "14px",
    bottom: "14px",
    color: vt.text3,
    opacity: 0,
    transitionProperty: "opacity",
    transitionDuration: "100ms",
    [PHONE]: { display: "none" },
  },
  kbd: {
    display: "inline-grid",
    placeItems: "center",
    minWidth: "20px",
    height: "20px",
    padding: "0 5px",
    borderRadius: "5px",
    backgroundColor: vt.card,
    border: `1px solid ${vt.border}`,
    boxShadow: `inset 0 -1px 0 ${vt.border}`,
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

/** One row: optional leading tile or avatar, a title and a meta line, and trailing meta or actions.
 * Clickable rows are buttons (or links with `href`). */
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
  alignLeading = "center",
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
  /** "start" pins the leading tile to the top of a tall row. */
  alignLeading?: "center" | "start";
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
        {leading && <span className={mergeClasses(s.leading, alignLeading === "start" && s.leadingTop)}>{leading}</span>}
        <span className={s.body}>
          <span className={mergeClasses(s.title, wrap && s.titleWrap)}>{title}</span>
          {meta && <span className={mergeClasses(s.meta, wrap && s.metaWrap)}>{meta}</span>}
        </span>
        {trailing && <span className={mergeClasses(s.trailing, selected && s.selectedTrailing)}>{trailing}</span>}
      </Tag>
    </li>
  );
}

/** A row of 2–4 stat cards, each optionally a link to its page. */
export function StatStrip({ children, label }: { children: ReactNode; label?: string }) {
  const s = useStyles();
  return (
    <div className={s.strip} role="group" aria-label={label}>
      {children}
    </div>
  );
}

/** One stat card: label and icon tile on top, the value, then a hint (e.g. "7 overdue", in the hint's
 * tone with a dot). */
export function Stat({
  value,
  label,
  hint,
  hintTone,
  icon,
  tone = "accent",
  onClick,
}: {
  value: ReactNode;
  label: ReactNode;
  hint?: ReactNode;
  /** Colours the hint and adds a dot: `danger` for overdue, `success` for done. */
  hintTone?: Tone;
  /** A 20px icon for the tile. */
  icon?: ReactNode;
  tone?: Tone;
  onClick?: () => void;
}) {
  const s = useStyles();
  const Tag: ElementType = onClick ? "button" : "div";
  return (
    <Tag className={mergeClasses(s.stat, onClick && s.statClickable)} onClick={onClick} type={onClick ? "button" : undefined}>
      <span className={s.statLabel}>{label}</span>
      {icon && <IconTile icon={icon} tone={tone} size={36} className={s.statIcon} />}
      <span className={s.statValue}>{value}</span>
      <span className={s.statHint} style={hint && hintTone ? { color: TONES[hintTone].fg } : undefined}>
        {hint && hintTone && <span className={s.statHintDot} style={{ backgroundColor: TONES[hintTone].fg }} aria-hidden />}
        {hint}
      </span>
      {onClick && <ChevronRight16Regular className={mergeClasses(s.statGo, "vanimo-stat-go")} aria-hidden />}
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

/** A relative date with the exact date and time in a tooltip. `inSentence` lower-cases "Yesterday" and
 * "Tomorrow" mid-sentence. */
export function Time({ iso, className, inSentence }: { iso: string; className?: string; inSentence?: boolean }) {
  const s = useStyles();
  const text = relativeTime(iso);
  return (
    <Tooltip content={absoluteTime(iso)} relationship="description" withArrow>
      <time dateTime={iso} className={mergeClasses(s.time, className)}>
        {inSentence && (text === "Yesterday" || text === "Tomorrow") ? text.toLowerCase() : text}
      </time>
    </Tooltip>
  );
}
