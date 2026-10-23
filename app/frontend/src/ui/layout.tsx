/** Page structure: a page header (one h1, an optional line of description, at most one primary
 * action), sections separated by space rather than boxes, and bordered surfaces only where a block
 * is a self-contained object. */
import { makeStyles, mergeClasses, shorthands, tokens } from "@fluentui/react-components";
import { useEffect, type ElementType, type ReactNode } from "react";
import { hoverTransition } from "../theme/motion";
import { vt } from "../theme/theme";
import { typo } from "../theme/typography";

const useStyles = makeStyles({
  page: { display: "grid", gap: "32px", marginInline: "auto", width: "100%", minWidth: 0, alignContent: "start" },
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
  headerText: { display: "grid", gap: "4px", minWidth: 0, flex: "1 1 320px" },
  eyebrow: { ...typo.label, color: vt.text3, display: "flex", gap: "8px", alignItems: "center" },
  title: { ...typo.pageTitle, color: vt.text1, margin: 0 },
  description: { ...typo.body, color: vt.text2, margin: 0, maxWidth: "68ch" },
  actions: { display: "flex", gap: "8px", alignItems: "center", flexWrap: "wrap" },
  section: { display: "grid", gap: "12px", minWidth: 0 },
  sectionHeader: { display: "flex", alignItems: "flex-end", justifyContent: "space-between", gap: "12px", flexWrap: "wrap" },
  sectionText: { display: "grid", gap: "2px", minWidth: 0 },
  sectionTitle: { ...typo.sectionTitle, color: vt.text1, margin: 0 },
  sectionDescription: { ...typo.meta, color: vt.text2, margin: 0, maxWidth: "72ch" },
  surface: {
    backgroundColor: tokens.colorNeutralBackground1,
    border: `1px solid ${tokens.colorNeutralStroke2}`,
    borderRadius: tokens.borderRadiusXLarge,
    minWidth: 0,
  },
  padNone: { padding: 0 },
  padS: { padding: "12px 16px" },
  padM: { padding: "16px 20px" },
  padL: { padding: "24px" },
  interactive: {
    ...hoverTransition,
    cursor: "pointer",
    "@media (hover: hover)": {
      ":hover": { backgroundColor: tokens.colorNeutralBackground1Hover, ...shorthands.borderColor(tokens.colorNeutralStroke1) },
    },
  },
  rows: { display: "grid" },
  settingRow: {
    display: "grid",
    gridTemplateColumns: "minmax(0, 1fr) auto",
    alignItems: "center",
    gap: "16px",
    padding: "14px 0",
    borderTop: `1px solid ${tokens.colorNeutralStroke3}`,
    ":first-child": { borderTop: "none" },
    "@media (max-width: 639px)": { gridTemplateColumns: "1fr" },
  },
  settingText: { display: "grid", gap: "2px", minWidth: 0 },
  settingLabel: { ...typo.itemTitle, color: vt.text1 },
  settingDescription: { ...typo.meta, color: vt.text2 },
  kv: { display: "grid", gridTemplateColumns: "minmax(120px, 200px) minmax(0, 1fr)", margin: 0 },
  kvTerm: {
    ...typo.meta,
    color: vt.text3,
    padding: "8px 16px 8px 0",
    borderTop: `1px solid ${tokens.colorNeutralStroke3}`,
  },
  kvValue: {
    ...typo.meta,
    color: vt.text1,
    margin: 0,
    padding: "8px 0",
    borderTop: `1px solid ${tokens.colorNeutralStroke3}`,
    overflowWrap: "anywhere",
  },
  kvFirst: { borderTop: "none" },
});

export type PageWidth = "reading" | "normal" | "wide";

/** A page: header + content. Sets the document title. */
export function Page({
  title,
  description,
  eyebrow,
  actions,
  width = "normal",
  className,
  children,
}: {
  title: ReactNode;
  description?: ReactNode;
  /** A small line above the title (e.g. a data-source badge or breadcrumb). */
  eyebrow?: ReactNode;
  actions?: ReactNode;
  width?: PageWidth;
  className?: string;
  children?: ReactNode;
}) {
  const s = useStyles();
  useEffect(() => {
    if (typeof title === "string") document.title = `${title} · Vanimo`;
  }, [title]);
  return (
    <div className={mergeClasses(s.page, s[width], className)}>
      <header className={s.header}>
        <div className={s.headerText}>
          {eyebrow && <div className={s.eyebrow}>{eyebrow}</div>}
          <h1 className={s.title}>{title}</h1>
          {description && <p className={s.description}>{description}</p>}
        </div>
        {actions && <div className={s.actions}>{actions}</div>}
      </header>
      {children}
    </div>
  );
}

/** A titled group of content. No box: sections are separated by the page's spacing. */
export function Section({
  title,
  description,
  actions,
  as = "section",
  className,
  children,
  "aria-label": ariaLabel,
}: {
  title?: ReactNode;
  description?: ReactNode;
  actions?: ReactNode;
  as?: ElementType;
  className?: string;
  children?: ReactNode;
  "aria-label"?: string;
}) {
  const s = useStyles();
  const Tag = as;
  return (
    <Tag className={mergeClasses(s.section, className)} aria-label={ariaLabel}>
      {(title || actions) && (
        <div className={s.sectionHeader}>
          <div className={s.sectionText}>
            {title && <h2 className={s.sectionTitle}>{title}</h2>}
            {description && <p className={s.sectionDescription}>{description}</p>}
          </div>
          {actions && <div className={s.actions}>{actions}</div>}
        </div>
      )}
      {children}
    </Tag>
  );
}

/** A bordered surface for a self-contained object (an email being answered, a meeting, a tile).
 * Never nest surfaces. */
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

/** Settings list: label and description on the left, the control on the right. */
export function SettingRow({ label, description, children }: { label: ReactNode; description?: ReactNode; children?: ReactNode }) {
  const s = useStyles();
  return (
    <div className={s.settingRow}>
      <div className={s.settingText}>
        <span className={s.settingLabel}>{label}</span>
        {description && <span className={s.settingDescription}>{description}</span>}
      </div>
      {children && <div>{children}</div>}
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
