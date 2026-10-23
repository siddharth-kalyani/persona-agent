/** Status and progress: dots and pills (never colour alone: always with a word), empty states that
 * name the next step, skeletons that mirror the layout (shown only after 300 ms, so fast answers
 * never flash), and honest step lists for long AI work. */
import { makeStyles, mergeClasses, Skeleton, SkeletonItem, Spinner, tokens } from "@fluentui/react-components";
import { CheckmarkCircle16Filled, DismissCircle16Filled } from "@fluentui/react-icons";
import { useEffect, useState, type ReactNode } from "react";
import { vt } from "../theme/theme";
import { typo } from "../theme/typography";

export type Tone = "neutral" | "accent" | "success" | "warning" | "danger";

const useStyles = makeStyles({
  dotWrap: { display: "inline-flex", alignItems: "center", gap: "6px", ...typo.meta, color: vt.text2 },
  dot: { width: "8px", height: "8px", borderRadius: "50%", flexShrink: 0 },
  neutral: { backgroundColor: vt.dot },
  accent: { backgroundColor: vt.accent },
  success: { backgroundColor: vt.success },
  warning: { backgroundColor: vt.warning },
  danger: { backgroundColor: vt.danger },
  pill: {
    display: "inline-flex",
    alignItems: "center",
    gap: "4px",
    minHeight: "20px",
    maxWidth: "100%",
    padding: "1px 6px",
    borderRadius: tokens.borderRadiusSmall,
    ...typo.label,
    whiteSpace: "nowrap",
    overflow: "hidden",
    textOverflow: "ellipsis",
    border: "1px solid transparent",
  },
  pillWrap: { whiteSpace: "normal", overflowWrap: "anywhere" },
  pillNeutral: { backgroundColor: vt.inset, color: vt.text2, border: `1px solid ${tokens.colorNeutralStroke2}` },
  pillAccent: { backgroundColor: vt.accentTint, color: vt.accentTintText },
  pillSuccess: { backgroundColor: vt.successTint, color: vt.success },
  pillWarning: { backgroundColor: vt.warningTint, color: vt.warning },
  pillDanger: { backgroundColor: vt.dangerTint, color: vt.danger },
  empty: { display: "grid", gap: "8px", justifyItems: "start", maxWidth: "460px", padding: "24px 0" },
  emptyIcon: {
    width: "40px",
    height: "40px",
    borderRadius: tokens.borderRadiusLarge,
    backgroundColor: vt.inset,
    border: `1px solid ${tokens.colorNeutralStroke3}`,
    display: "grid",
    placeItems: "center",
    color: vt.text2,
    fontSize: "20px",
    marginBottom: "4px",
  },
  emptyTitle: { ...typo.sectionTitle, color: vt.text1, margin: 0 },
  emptyBody: { ...typo.body, color: vt.text2, margin: 0 },
  emptyAction: { marginTop: "8px", display: "flex", gap: "8px", flexWrap: "wrap" },
  skeleton: { display: "grid", gap: "12px" },
  skelTitle: { width: "220px", height: "24px" },
  skelLine: { height: "14px" },
  skelRow: { height: "48px", borderRadius: tokens.borderRadiusMedium },
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
  children,
  className,
}: {
  tone?: Tone;
  icon?: ReactNode;
  /** Let long text wrap (e.g. "Writing to: someone outside your organisation") instead of truncating. */
  wrap?: boolean;
  children: ReactNode;
  className?: string;
}) {
  const s = useStyles();
  const t = { neutral: s.pillNeutral, accent: s.pillAccent, success: s.pillSuccess, warning: s.pillWarning, danger: s.pillDanger }[tone];
  return (
    <span className={mergeClasses(s.pill, t, wrap && s.pillWrap, className)}>
      {icon}
      {children}
    </span>
  );
}

export function EmptyState({
  icon,
  title,
  children,
  action,
  headingLevel = 3,
}: {
  icon?: ReactNode;
  title: ReactNode;
  children?: ReactNode;
  action?: ReactNode;
  /** 2 directly under the page title, 3 inside a section, 4 inside a sub-section. */
  headingLevel?: 2 | 3 | 4;
}) {
  const s = useStyles();
  const Heading = (`h${headingLevel}` as "h2" | "h3" | "h4");
  return (
    <div className={s.empty}>
      {icon && <div className={s.emptyIcon} aria-hidden>{icon}</div>}
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
