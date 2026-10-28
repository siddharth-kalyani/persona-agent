/** Status and progress: dots and pills (never colour alone: always with a word), empty states that
 * name the next step, skeletons that mirror the layout (shown only after 300 ms, so fast answers
 * never flash), honest step lists for long AI work, and the drafting-engine badge. */
import { makeStyles, mergeClasses, Skeleton, SkeletonItem, Spinner, tokens, Tooltip } from "@fluentui/react-components";
import {
  CheckmarkCircle16Filled,
  DismissCircle16Filled,
  PlugDisconnected16Regular,
  ShieldCheckmark16Regular,
} from "@fluentui/react-icons";
import { useEffect, useState, type HTMLAttributes, type ReactNode, type Ref } from "react";
import { vt } from "../theme/theme";
import { typo } from "../theme/typography";
import { TONES, type Tone } from "./tones";
import { IconTile } from "./visual";

export type { Tone };

const useStyles = makeStyles({
  // A status is one or two words: it never breaks inside a word in a narrow table column.
  dotWrap: { display: "inline-flex", alignItems: "center", gap: "6px", ...typo.meta, color: vt.text2, whiteSpace: "nowrap" },
  dot: { width: "8px", height: "8px", borderRadius: "50%", flexShrink: 0 },
  neutral: { backgroundColor: vt.dot },
  accent: { backgroundColor: vt.accent },
  blue: { backgroundColor: vt.info },
  purple: { backgroundColor: vt.purple },
  success: { backgroundColor: vt.success },
  warning: { backgroundColor: vt.warning },
  danger: { backgroundColor: vt.danger },
  pill: {
    display: "inline-flex",
    alignItems: "center",
    gap: "5px",
    minHeight: "22px",
    maxWidth: "100%",
    padding: "2px 8px",
    borderRadius: "6px",
    ...typo.label,
    whiteSpace: "nowrap",
    overflow: "hidden",
    textOverflow: "ellipsis",
    "& > svg": { flexShrink: 0 },
  },
  pillWithIcon: { paddingLeft: "6px" },
  pillWrap: { whiteSpace: "normal", overflowWrap: "anywhere" },
  pillDot: { width: "6px", height: "6px", borderRadius: "50%", flexShrink: 0, backgroundColor: "currentColor" },
  pillNeutral: { backgroundColor: TONES.neutral.bg, color: TONES.neutral.fg },
  pillAccent: { backgroundColor: TONES.accent.bg, color: TONES.accent.fg },
  pillBlue: { backgroundColor: TONES.blue.bg, color: TONES.blue.fg },
  pillPurple: { backgroundColor: TONES.purple.bg, color: TONES.purple.fg },
  pillSuccess: { backgroundColor: TONES.success.bg, color: TONES.success.fg },
  pillWarning: { backgroundColor: TONES.warning.bg, color: TONES.warning.fg },
  pillDanger: { backgroundColor: TONES.danger.bg, color: TONES.danger.fg },
  empty: { display: "grid", gap: "6px", justifyItems: "start", maxWidth: "460px", padding: "28px 0" },
  emptyCenter: { justifyItems: "center", textAlign: "center", marginInline: "auto", paddingInline: "16px" },
  emptyIcon: { marginBottom: "8px" },
  emptyTitle: { ...typo.sectionTitle, color: vt.text1, margin: 0 },
  emptyBody: { ...typo.body, color: vt.text2, margin: 0 },
  emptyAction: { marginTop: "8px", display: "flex", gap: "8px", flexWrap: "wrap" },
  skeleton: { display: "grid", gap: "12px" },
  skelTitle: { width: "220px", height: "24px" },
  skelLine: { height: "14px" },
  skelRow: { height: "52px", borderRadius: tokens.borderRadiusLarge },
  steps: { listStyle: "none", margin: 0, padding: 0, display: "grid", gap: "6px" },
  step: { display: "grid", gridTemplateColumns: "16px minmax(0, 1fr)", gap: "10px", alignItems: "start", ...typo.meta },
  stepIcon: { height: "18px", display: "grid", placeItems: "center" },
  stepDone: { color: vt.success },
  stepError: { color: vt.danger },
  stepPending: { width: "6px", height: "6px", borderRadius: "50%", backgroundColor: vt.dot },
  stepLabelDone: { color: vt.text2 },
  stepLabelActive: { color: vt.text1, fontWeight: 500 },
  stepLabelPending: { color: vt.text3 },
  stepDetail: { color: vt.text3, ...typo.tabular },
});

export function StatusDot({ tone = "neutral", children }: { tone?: Tone; children: ReactNode }) {
  const s = useStyles();
  return (
    <span className={s.dotWrap}>
      <span className={mergeClasses(s.dot, s[tone])} aria-hidden />
      {children}
    </span>
  );
}

/** A small label for a state. Neutral unless the state needs attention. */
export function Pill({
  tone = "neutral",
  icon,
  wrap,
  dot,
  children,
  className,
  ...rest
}: {
  tone?: Tone;
  icon?: ReactNode;
  /** Let long text wrap (e.g. "Writing to: someone outside your organisation") instead of truncating. */
  wrap?: boolean;
  /** A small dot in the tone's colour before the text (status: "Live", "Paused"). */
  dot?: boolean;
  children: ReactNode;
  className?: string;
} & Omit<HTMLAttributes<HTMLSpanElement>, "children" | "className"> & { ref?: Ref<HTMLSpanElement> }) {
  const s = useStyles();
  const t = {
    neutral: s.pillNeutral,
    accent: s.pillAccent,
    blue: s.pillBlue,
    purple: s.pillPurple,
    success: s.pillSuccess,
    warning: s.pillWarning,
    danger: s.pillDanger,
  }[tone];
  return (
    <span {...rest} className={mergeClasses(s.pill, t, Boolean(icon || dot) && s.pillWithIcon, wrap && s.pillWrap, className)}>
      {dot && <span className={s.pillDot} aria-hidden />}
      {icon}
      {children}
    </span>
  );
}

/** What drafts and extraction run on: the labelled offline stand-in, or Claude on Amazon Bedrock. The
 * explanation sits in a tooltip (and is the badge's description for screen readers). */
export function EngineBadge({ offline, detail }: { offline: boolean; detail?: string }) {
  const text =
    detail ?? (offline ? "No AI model is connected yet: this runs on rules, clearly labelled." : "Runs on Claude in Amazon Bedrock.");
  return (
    <Tooltip content={text} relationship="description" withArrow>
      {offline ? (
        <Pill tabIndex={0} icon={<PlugDisconnected16Regular />}>
          Offline stand-in
        </Pill>
      ) : (
        <Pill tabIndex={0} tone="accent" icon={<ShieldCheckmark16Regular />}>
          Claude on Bedrock
        </Pill>
      )}
    </Tooltip>
  );
}

export function EmptyState({
  icon,
  tone = "accent",
  title,
  children,
  action,
  headingLevel = 3,
  center,
}: {
  /** A 20px icon: it sits in a tinted tile. */
  icon?: ReactNode;
  tone?: Tone;
  title: ReactNode;
  children?: ReactNode;
  action?: ReactNode;
  /** 2 directly under the page title, 3 inside a section, 4 inside a sub-section. */
  headingLevel?: 2 | 3 | 4;
  /** Centred, for an empty card or pane. */
  center?: boolean;
}) {
  const s = useStyles();
  const Heading = (`h${headingLevel}` as "h2" | "h3" | "h4");
  return (
    <div className={mergeClasses(s.empty, center && s.emptyCenter)}>
      {icon && <IconTile icon={icon} tone={tone} size={40} className={s.emptyIcon} />}
      <Heading className={s.emptyTitle}>{title}</Heading>
      {children && <p className={s.emptyBody}>{children}</p>}
      {action && <div className={s.emptyAction}>{action}</div>}
    </div>
  );
}

/** True after `ms`: lets fast loads finish without a skeleton flashing. */
export function useDelayed(ms = 300): boolean {
  const [show, setShow] = useState(false);
  useEffect(() => {
    const t = setTimeout(() => setShow(true), ms);
    return () => clearTimeout(t);
  }, [ms]);
  return show;
}

/** First-load placeholder for a page: a title bar and rows, shown after 300 ms. */
export function PageSkeleton({ label = "Loading…", rows = 5 }: { label?: string; rows?: number }) {
  const s = useStyles();
  const show = useDelayed();
  return (
    <div role="status" aria-label={label} aria-busy="true">
      {show && (
        <Skeleton animation="pulse" className={s.skeleton} aria-hidden>
          <SkeletonItem className={s.skelTitle} />
          <SkeletonItem className={s.skelLine} style={{ width: "min(420px, 80%)" }} />
          <div style={{ height: 16 }} />
          {Array.from({ length: rows }, (_, i) => (
            <SkeletonItem key={i} className={s.skelRow} />
          ))}
        </Skeleton>
      )}
    </div>
  );
}

/** Placeholder rows inside a section (lists that load after the page). */
export function RowsSkeleton({ rows = 3, label = "Loading…" }: { rows?: number; label?: string }) {
  const s = useStyles();
  const show = useDelayed();
  return (
    <div role="status" aria-label={label} aria-busy="true">
      {show && (
        <Skeleton animation="pulse" className={s.skeleton} aria-hidden>
          {Array.from({ length: rows }, (_, i) => (
            <SkeletonItem key={i} className={s.skelRow} />
          ))}
        </Skeleton>
      )}
    </div>
  );
}

export type StepState = "done" | "active" | "pending" | "error";

/** What a long operation is doing, step by step, in plain words. */
export function StepList({ steps, label }: { steps: Array<{ label: ReactNode; state: StepState; detail?: ReactNode }>; label?: string }) {
  const s = useStyles();
  return (
    <ol className={s.steps} aria-label={label}>
      {steps.map((step, i) => (
        <li key={i} className={s.step}>
          <span className={s.stepIcon}>
            {step.state === "done" && <CheckmarkCircle16Filled className={s.stepDone} aria-label="Done" />}
            {step.state === "error" && <DismissCircle16Filled className={s.stepError} aria-label="Failed" />}
            {step.state === "active" && <Spinner size="extra-tiny" aria-label="In progress" />}
            {step.state === "pending" && <span className={s.stepPending} aria-hidden />}
          </span>
          <span>
            <span
              className={
                step.state === "active" ? s.stepLabelActive : step.state === "pending" ? s.stepLabelPending : s.stepLabelDone
              }
            >
              {step.label}
            </span>
            {step.detail && <span className={s.stepDetail}> · {step.detail}</span>}
          </span>
        </li>
      ))}
    </ol>
  );
}
