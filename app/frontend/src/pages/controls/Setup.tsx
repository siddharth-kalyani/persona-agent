import {
  Button,
  makeStyles,
  MessageBar,
  MessageBarActions,
  MessageBarBody,
  MessageBarTitle,
  Spinner,
  tokens,
} from "@fluentui/react-components";
import {
  ArrowClockwise16Regular,
  ArrowForward16Regular,
  Checkmark16Regular,
  CheckmarkCircle16Regular,
  CheckmarkCircle20Regular,
  Clock16Regular,
  DocumentSearch16Regular,
} from "@fluentui/react-icons";
import { useCallback, useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import type { ControlsStatus } from "../../api/client";
import { useApi } from "../../api/context";
import { IconTile, Page, PageSkeleton, Pill, RowsSkeleton, Section, Time, typo, vt } from "../../ui";
import { errorText } from "../Home";
import { SourcesReview } from "./SourcesReview";

const useStyles = makeStyles({
  running: { display: "inline-flex", alignItems: "center", gap: "8px", ...typo.meta, color: vt.text2 },
  listed: {
    display: "inline-flex",
    alignItems: "center",
    gap: "6px",
    ...typo.meta,
    color: vt.text3,
    whiteSpace: "nowrap",
    "& > svg": { flexShrink: 0 },
  },
  // The decision stays in reach while the list scrolls: a floating bar, not a popup.
  decision: {
    position: "sticky",
    bottom: "16px",
    zIndex: 2,
    display: "flex",
    alignItems: "center",
    justifyContent: "space-between",
    gap: "12px 24px",
    flexWrap: "wrap",
    padding: "12px 12px 12px 16px",
    backgroundColor: tokens.colorNeutralBackground1,
    border: `1px solid ${vt.border}`,
    borderRadius: tokens.borderRadiusXLarge,
    boxShadow: vt.shadowRaised,
    "@media (max-width: 639px)": { bottom: "8px", padding: "12px" },
  },
  decisionMain: { display: "flex", alignItems: "center", gap: "12px", minWidth: 0, flex: "1 1 320px" },
  decisionText: { display: "grid", gap: "2px", minWidth: 0 },
  decisionTitle: { ...typo.itemTitle, color: vt.text1 },
  decisionMeta: { ...typo.meta, ...typo.tabular, color: vt.text2 },
  decisionActions: { display: "flex", gap: "8px", flexWrap: "wrap", marginLeft: "auto" },
});

export function scanSummary(s: ControlsStatus["scan"]): string {
  if (!s) return "";
  const c = s.counts;
  return `${c.people ?? 0} people, ${c.threads ?? 0} email threads (${c.messages ?? 0} emails), ${c.chats ?? 0} chats, ${c.meetings ?? 0} meetings`;
}

const plural = (n: number, one: string, many: string) => `${n} ${n === 1 ? one : many}`;

const TITLE = "Choose what Vanimo learns from";

/** Onboarding: scan headers → review → Finish or Skip. Nothing beyond headers is read before Finish/Skip. */
export function Setup() {
  const styles = useStyles();
  const api = useApi();
  const navigate = useNavigate();
  const [status, setStatus] = useState<ControlsStatus | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [doing, setDoing] = useState<"finished" | "skipped" | null>(null);
  const started = useRef(false);

  const refresh = useCallback(async () => {
    try {
      const s = await api.controlsStatus();
      setStatus(s);
      return s;
    } catch (e) {
      setError(errorText(e));
      return null;
    }
  }, [api]);

  useEffect(() => {
    void (async () => {
      const s = await refresh();
      // Start the header pass automatically the first time.
      if (s && !s.scan && !started.current) {
        started.current = true;
        try {
          setStatus(await api.startScan());
        } catch (e) {
          setError(errorText(e));
        }
      }
    })();
  }, [api, refresh]);

  useEffect(() => {
    if (status?.scan?.status !== "running") return;
    const timer = setInterval(() => void refresh(), 2000);
    return () => clearInterval(timer);
  }, [status?.scan?.status, refresh]);

  async function complete(outcome: "finished" | "skipped") {
    setBusy(true);
    setDoing(outcome);
    try {
      await api.completeReview(outcome);
      navigate("/");
    } catch (e) {
      setError(errorText(e));
      setBusy(false);
      setDoing(null);
    }
  }

  if (!status)
    return error ? (
      <Page title={TITLE}>
        <MessageBar intent="error">
          <MessageBarBody>{error}</MessageBarBody>
        </MessageBar>
      </Page>
    ) : (
      <PageSkeleton label="Loading…" />
    );
  const scan = status.scan;
  const reviewed = status.onboardingState === "review_done";
  const working = <Spinner size="extra-tiny" aria-hidden />;

  return (
    <Page
      title={TITLE}
      eyebrow={
        reviewed ? (
          status.reviewOutcome === "skipped" ? (
            <Pill icon={<ArrowForward16Regular />}>Review skipped</Pill>
          ) : (
            <Pill tone="success" icon={<CheckmarkCircle16Regular />}>
              Review finished
            </Pill>
          )
        ) : undefined
      }
      description={
        reviewed
          ? "You can still exclude anything here: exclusions apply within a minute."
          : "Vanimo has only read headers so far. Nothing else is read until you finish."
      }
      info={
        reviewed
          ? "You've already been through this review. Excluded sources are never used: no style learning, no memory, never as context for a draft."
          : "Headers are who you write to, chat names and meeting titles. Exclude anything Vanimo shouldn't learn from, then finish. You can change this any time later."
      }
    >
      {error && (
        <MessageBar intent="error">
          <MessageBarBody>{error}</MessageBarBody>
        </MessageBar>
      )}
      {!scan || scan.status === "running" ? (
        <Section title="Your sources" icon={<DocumentSearch16Regular />}>
          <div role="status">
            <span className={styles.running}>
              <Spinner size="extra-tiny" aria-hidden />
              Listing your sources (headers only)…
            </span>
          </div>
          <RowsSkeleton rows={6} label="Listing your sources…" />
        </Section>
      ) : scan.status === "failed" ? (
        <MessageBar intent="error" layout="multiline">
          <MessageBarBody>
            <MessageBarTitle>The scan didn't finish.</MessageBarTitle>
            Nothing beyond headers was read. Try again, or skip and review your sources later from My data.
          </MessageBarBody>
          <MessageBarActions>
            <Button
              size="small"
              icon={<ArrowClockwise16Regular />}
              onClick={() => void api.startScan().then(setStatus, (e) => setError(errorText(e)))}
            >
              Try again
            </Button>
            <Button size="small" disabled={busy} onClick={() => void complete("skipped")}>
              Skip for now
            </Button>
          </MessageBarActions>
        </MessageBar>
      ) : (
        <>
          <Section
            title="Your sources"
            icon={<DocumentSearch16Regular />}
            description={`Found ${scanSummary(scan)}${scan.sourceKind === "sample" ? " in the sample workspace." : "."}`}
            actions={
              scan.finishedAt && (
                <span className={styles.listed}>
                  <Clock16Regular aria-hidden />
                  <span>
                    Headers listed <Time iso={scan.finishedAt} inSentence />
                  </span>
                </span>
              )
            }
          >
            <SourcesReview onChange={() => void refresh()} counts={scan.counts} />
          </Section>
          <div className={styles.decision} role="region" aria-label="Finish the review">
            <div className={styles.decisionMain}>
              <IconTile icon={<CheckmarkCircle20Regular />} tone="accent" size={36} />
              <div className={styles.decisionText}>
                <span className={styles.decisionTitle}>Done reviewing?</span>
                <span className={styles.decisionMeta}>
                  {plural(status.rules, "exclusion", "exclusions")} and{" "}
                  {plural(status.neverSendWords, "never-send word", "never-send words")} so far. Vanimo starts learning
                  only from what's left.
                </span>
              </div>
            </div>
            <div className={styles.decisionActions}>
              <Button disabled={busy} icon={doing === "skipped" ? working : undefined} onClick={() => void complete("skipped")}>
                Skip for now
              </Button>
              <Button
                appearance="primary"
                disabled={busy}
                icon={doing === "finished" ? working : <Checkmark16Regular />}
                onClick={() => void complete("finished")}
              >
                Finish
              </Button>
            </div>
          </div>
        </>
      )}
    </Page>
  );
}
