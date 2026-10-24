/** Page structure: a page header (icon tile, one h1, a one-sentence description, an optional ⓘ for
 * the longer story, at most one primary action), sections spaced apart, and cards for content. */
import { makeStyles, mergeClasses, shorthands, tokens } from "@fluentui/react-components";
import { createContext, useContext, useEffect, type ElementType, type ReactNode } from "react";
import { hoverTransition } from "../theme/motion";
import { vt } from "../theme/theme";
import { typo } from "../theme/typography";
import { Pill } from "./feedback";
import { IconTile, InfoTip } from "./visual";

const useStyles = makeStyles({
  // Grid children may shrink below their content's width: a single-line MessageBar (which switches to
  // multi-line only when it overflows) or a long row must never widen the page.
  page: {
    display: "grid",
    gap: "28px",
    width: "100%",
    minWidth: 0,
    alignContent: "start",
    "& > *": { minWidth: 0 },
  },
  reading: { maxWidth: "760px" },
  normal: { maxWidth: "1080px" },
  wide: { maxWidth: "1280px" },
  header: {
    display: "flex",
    alignItems: "flex-start",
    justifyContent: "space-between",
    gap: "16px",
    flexWrap: "wrap",
  },
  headerMain: { display: "flex", alignItems: "flex-start", gap: "14px", minWidth: 0, flex: "1 1 320px" },
  headerTop: { display: "grid", gap: "10px", minWidth: 0 },
  headerIcon: { marginTop: "2px", "@media (max-width: 639px)": { display: "none" } },
  headerText: { display: "grid", gap: "2px", minWidth: 0 },
  titleRow: { display: "flex", alignItems: "center", gap: "6px", minWidth: 0, "& > h1": { minWidth: 0 } },
  eyebrow: { ...typo.label, color: vt.text3, display: "flex", gap: "8px", alignItems: "center", flexWrap: "wrap" },
  title: { ...typo.pageTitle, color: vt.text1, margin: 0 },
  description: { ...typo.body, color: vt.text2, margin: 0, maxWidth: "72ch", textWrap: "pretty" },
  actions: { display: "flex", gap: "8px", alignItems: "center", flexWrap: "wrap", minWidth: 0, maxWidth: "100%" },
  headerActions: {
    paddingTop: "6px",
    // On phones the header buttons share the row evenly.
    "@media (max-width: 639px)": { width: "100%", paddingTop: 0, "& > button": { flexGrow: 1 } },
  },
  section: { display: "grid", gap: "12px", minWidth: 0, "& > *": { minWidth: 0 } },
  sectionHeader: {
    display: "flex",
    alignItems: "flex-end",
    justifyContent: "space-between",
    gap: "12px",
    flexWrap: "wrap",
    minWidth: 0,
  },
  sectionText: { display: "grid", gap: "2px", minWidth: 0 },
  sectionTitleRow: { display: "flex", alignItems: "center", gap: "8px", minWidth: 0, "& > h2, & > h3": { minWidth: 0 } },
  sectionIcon: { display: "inline-grid", color: vt.accent },
  sectionTitle: { ...typo.sectionTitle, color: vt.text1, margin: 0 },
  sectionDescription: { ...typo.meta, color: vt.text2, margin: 0, maxWidth: "72ch", textWrap: "pretty" },
  card: {
    backgroundColor: tokens.colorNeutralBackground1,
    border: `1px solid ${vt.border}`,
    borderRadius: tokens.borderRadiusXLarge,
    boxShadow: vt.shadowCard,
    minWidth: 0,
    overflow: "hidden",
  },
  cardSection: { gap: 0 },
  cardHeader: {
    display: "flex",
    alignItems: "center",
    justifyContent: "space-between",
    gap: "12px",
    flexWrap: "wrap",
    padding: "12px 16px",
    borderBottom: `1px solid ${vt.borderSubtle}`,
    minHeight: "52px",
  },
  cardHeaderMain: { display: "flex", alignItems: "center", gap: "10px", minWidth: 0 },
  cardTitle: { ...typo.cardTitle, color: vt.text1, margin: 0 },
  cardDescription: { ...typo.meta, color: vt.text3, margin: 0 },
  cardBody: { padding: "16px" },
  cardBodyFlush: { padding: 0 },
  surface: {
    backgroundColor: tokens.colorNeutralBackground1,
    border: `1px solid ${vt.border}`,
    borderRadius: tokens.borderRadiusXLarge,
    boxShadow: vt.shadowCard,
    minWidth: 0,
  },
  padNone: { padding: 0 },
  padS: { padding: "12px 16px" },
  padM: { padding: "16px 20px" },
  padL: { padding: "24px" },
  interactive: {
    ...hoverTransition,
    cursor: "pointer",
    "@media (hover: hover)": { ":hover": { ...shorthands.borderColor(vt.borderStrong), backgroundColor: tokens.colorNeutralBackground1Hover } },
  },
  rows: { display: "grid" },
  settingRow: {
    display: "grid",
    gridTemplateColumns: "minmax(0, 1fr) auto",
    alignItems: "center",
    gap: "16px",
    padding: "14px 0",
    borderTop: `1px solid ${vt.borderSubtle}`,
    ":first-child": { borderTop: "none" },
    "@media (max-width: 639px)": { gridTemplateColumns: "1fr" },
  },
  settingRowIcon: {
    gridTemplateColumns: "auto minmax(0, 1fr) auto",
    "@media (max-width: 639px)": { gridTemplateColumns: "auto minmax(0, 1fr)", alignItems: "start" },
  },
  settingControl: { "@media (max-width: 639px)": { gridColumn: "1 / -1" } },
  settingControlIcon: { "@media (max-width: 639px)": { gridColumn: "2" } },
  settingText: { display: "grid", gap: "2px", minWidth: 0 },
  settingLabel: { ...typo.itemTitle, color: vt.text1 },
  settingDescription: { ...typo.meta, color: vt.text2 },
  kv: {
    display: "grid",
    gridTemplateColumns: "minmax(120px, 200px) minmax(0, 1fr)",
    margin: 0,
    "@media (max-width: 479px)": { gridTemplateColumns: "minmax(0, 1fr)" },
  },
  kvTerm: {
    ...typo.meta,
    color: vt.text3,
    padding: "9px 16px 9px 0",
    borderTop: `1px solid ${vt.borderSubtle}`,
  },
  kvValue: {
    ...typo.meta,
    color: vt.text1,
    margin: 0,
    padding: "9px 0",
    borderTop: `1px solid ${vt.borderSubtle}`,
    overflowWrap: "anywhere",
    "@media (max-width: 479px)": { borderTop: "none", paddingTop: 0 },
  },
  kvFirst: { borderTop: "none" },
});

export type PageWidth = "reading" | "normal" | "wide";

/** The shell tells pages which icon their destination has, so every header carries it. */
export const PageIconContext = createContext<ReactNode>(null);

/** A page: header + content. Sets the document title. */
export function Page({
  title,
  description,
  info,
  eyebrow,
  actions,
  icon,
  documentTitle,
  width = "normal",
  className,
  children,
}: {
  title: ReactNode;
  /** One sentence. Longer explanations go in `info`. */
  description?: ReactNode;
  /** The longer story behind an ⓘ beside the title. */
  info?: ReactNode;
  /** A small line above the title (e.g. a date). */
  eyebrow?: ReactNode;
  actions?: ReactNode;
  /** Overrides the destination's icon (20px). */
  icon?: ReactNode;
  /** The browser tab's title when `title` isn't the page's name (e.g. a greeting). */
  documentTitle?: string;
  width?: PageWidth;
  className?: string;
  children?: ReactNode;
}) {
  const s = useStyles();
  const navIcon = useContext(PageIconContext);
  const tile = icon ?? navIcon;
  const tabTitle = documentTitle ?? (typeof title === "string" ? title : null);
  useEffect(() => {
    if (tabTitle) document.title = `${tabTitle} · Vanimo`;
  }, [tabTitle]);
  return (
    <div className={mergeClasses(s.page, s[width], className)}>
      <header className={s.headerTop}>
        {eyebrow && <div className={s.eyebrow}>{eyebrow}</div>}
        <div className={s.header}>
        <div className={s.headerMain}>
          {tile && <IconTile icon={tile} raised size={40} className={s.headerIcon} />}
          <div className={s.headerText}>
            <div className={s.titleRow}>
              <h1 className={s.title}>{title}</h1>
              {info && <InfoTip label={`About ${typeof title === "string" ? title : "this page"}`}>{info}</InfoTip>}
            </div>
            {description && <p className={s.description}>{description}</p>}
          </div>
        </div>
        {actions && <div className={mergeClasses(s.actions, s.headerActions)}>{actions}</div>}
        </div>
      </header>
      {children}
    </div>
  );
}

/** A titled group of content. `variant="card"` puts the header inside a card (dashboards); the plain
 * variant keeps the header above whatever cards the section holds. */
export function Section({
  title,
  description,
  actions,
  icon,
  count,
  info,
  variant = "plain",
  flush,
  headingLevel = 2,
  as = "section",
  className,
  children,
  "aria-label": ariaLabel,
}: {
  title?: ReactNode;
  description?: ReactNode;
  actions?: ReactNode;
  /** 16px in the plain header, 20px (in a tile) in the card header. */
  icon?: ReactNode;
  /** A neutral count beside the title. */
  count?: number;
  /** The longer story behind an ⓘ beside the title. */
  info?: ReactNode;
  variant?: "plain" | "card";
  /** Card variant: no padding around the content (lists and tables that run edge to edge). */
  flush?: boolean;
  /** 3 for a section nested under another h2. */
  headingLevel?: 2 | 3;
  as?: ElementType;
  className?: string;
  children?: ReactNode;
  "aria-label"?: string;
}) {
  const s = useStyles();
  const Tag = as;
  const H = headingLevel === 3 ? "h3" : "h2";
  const tip = info ? <InfoTip label={`About ${typeof title === "string" ? title : "this section"}`}>{info}</InfoTip> : null;
  const countPill = count !== undefined ? <Pill>{count}</Pill> : null;

  if (variant === "card") {
    return (
      <Tag className={mergeClasses(s.section, s.card, s.cardSection, className)} aria-label={ariaLabel}>
        {(title || actions) && (
          <div className={s.cardHeader}>
            <div className={s.cardHeaderMain}>
              {icon && <IconTile icon={icon} tone="accent" size={28} />}
              <div className={s.sectionText}>
                <div className={s.sectionTitleRow}>
                  {title && <H className={s.cardTitle}>{title}</H>}
                  {countPill}
                  {tip}
                </div>
                {description && <p className={s.cardDescription}>{description}</p>}
              </div>
            </div>
            {actions && <div className={s.actions}>{actions}</div>}
          </div>
        )}
        <div className={flush ? s.cardBodyFlush : s.cardBody}>{children}</div>
      </Tag>
    );
  }

  return (
    <Tag className={mergeClasses(s.section, className)} aria-label={ariaLabel}>
      {(title || actions) && (
        <div className={s.sectionHeader}>
          <div className={s.sectionText}>
            <div className={s.sectionTitleRow}>
              {icon && <span className={s.sectionIcon} aria-hidden>{icon}</span>}
              {title && <H className={s.sectionTitle}>{title}</H>}
              {countPill}
              {tip}
            </div>
            {description && <p className={s.sectionDescription}>{description}</p>}
          </div>
          {actions && <div className={s.actions}>{actions}</div>}
        </div>
      )}
      {children}
    </Tag>
  );
}

/** A card for a self-contained object (an email being answered, a meeting, a tile). Never nest them:
 * use a well (`vt.inset`) or a hairline inside. */
export function Surface({
  padding = "m",
  interactive,
  as = "div",
  className,
  children,
  ...rest
}: {
  padding?: "none" | "s" | "m" | "l";
  interactive?: boolean;
  as?: ElementType;
  className?: string;
  children?: ReactNode;
} & Record<string, unknown>) {
  const s = useStyles();
  const Tag = as;
  const pad = { none: s.padNone, s: s.padS, m: s.padM, l: s.padL }[padding];
  return (
    <Tag className={mergeClasses(s.surface, pad, interactive && s.interactive, className)} {...rest}>
      {children}
    </Tag>
  );
}

/** Settings list: an optional icon tile, label and description on the left, the control on the right. */
export function SettingRow({
  label,
  description,
  icon,
  children,
}: {
  label: ReactNode;
  description?: ReactNode;
  /** A 16px icon, shown in a neutral tile. */
  icon?: ReactNode;
  children?: ReactNode;
}) {
  const s = useStyles();
  return (
    <div className={mergeClasses(s.settingRow, Boolean(icon) && s.settingRowIcon)}>
      {icon && <IconTile icon={icon} size={32} />}
      <div className={s.settingText}>
        <span className={s.settingLabel}>{label}</span>
        {description && <span className={s.settingDescription}>{description}</span>}
      </div>
      {children && <div className={mergeClasses(s.settingControl, Boolean(icon) && s.settingControlIcon)}>{children}</div>}
    </div>
  );
}

export function SettingList({ children, className }: { children: ReactNode; className?: string }) {
  const s = useStyles();
  return <div className={mergeClasses(s.rows, className)}>{children}</div>;
}

/** Label/value pairs (details, diagnostics). */
export function KeyValueList({ items }: { items: Array<[ReactNode, ReactNode]> }) {
  const s = useStyles();
  return (
    <dl className={s.kv}>
      {items.map(([k, v], i) => (
        <div key={i} style={{ display: "contents" }}>
          <dt className={mergeClasses(s.kvTerm, i === 0 && s.kvFirst)}>{k}</dt>
          <dd className={mergeClasses(s.kvValue, i === 0 && s.kvFirst)}>{v}</dd>
        </div>
      ))}
    </dl>
  );
}
