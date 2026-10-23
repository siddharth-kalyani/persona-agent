/** Learning: Vanimo learns how you write from your own sent emails and chat messages (only from the
 * sources you allowed), redacting each one before it is stored. The header starts or repeats a run,
 * a strip says what's stored, the last run reads as a receipt, "What's stored" shows every kept item
 * exactly as stored (tokens in mono) or as shown to you, and deleting sits at the end. */
import {
  Button,
  Dialog,
  DialogActions,
  DialogBody,
  DialogContent,
  DialogSurface,
  DialogTitle,
  Link,
  makeStyles,
  MessageBar,
  MessageBarBody,
  Spinner,
  Tab,
  TabList,
  tokens,
  Tooltip,
} from "@fluentui/react-components";
import { BookOpen20Regular, CheckmarkCircle16Filled, Delete16Regular } from "@fluentui/react-icons";
import { useCallback, useEffect, useState, type ReactNode } from "react";
import { useNavigate } from "react-router-dom";
import { ApiError, type LearningRun, type LearningStatus, type StoredItem } from "../../api/client";
import { useApi } from "../../api/context";
import {
  absoluteTime,
  EmptyState,
  Page,
  PageSkeleton,
  Pill,
  relativeTime,
  Rise,
  Section,
  SettingList,
  SettingRow,
  Stat,
  StatStrip,
  StatusDot,
  Time,
  typo,
  vt,
} from "../../ui";
import { errorText } from "../Home";

const useStyles = makeStyles({
  runHead: { display: "flex", alignItems: "center", flexWrap: "wrap", gap: "6px 16px", ...typo.meta, color: vt.text2 },
  runHeadItem: { ...typo.tabular },
  runNote: { ...typo.meta, color: vt.text2, margin: 0, maxWidth: "72ch" },
  receipt: {
    display: "grid",
    gridTemplateColumns: "repeat(auto-fill, minmax(260px, 1fr))",
    columnGap: "32px",
    margin: 0,
    padding: 0,
    listStyle: "none",
  },
  receiptRow: {
    display: "grid",
    gridTemplateColumns: "48px minmax(0, 1fr)",
    gap: "12px",
    alignItems: "baseline",
    padding: "6px 0",
    borderTop: `1px solid ${tokens.colorNeutralStroke3}`,
  },
  receiptNumber: { ...typo.itemTitle, ...typo.tabular, color: vt.text1, textAlign: "right" },
  receiptLabel: { ...typo.meta, color: vt.text2 },
  code: {
    ...typo.mono,
    padding: "0 4px",
    borderRadius: tokens.borderRadiusSmall,
    backgroundColor: vt.inset,
    border: `1px solid ${tokens.colorNeutralStroke3}`,
  },
  items: {
    display: "grid",
    margin: 0,
    padding: 0,
    listStyle: "none",
    border: `1px solid ${tokens.colorNeutralStroke2}`,
    borderRadius: tokens.borderRadiusXLarge,
    backgroundColor: tokens.colorNeutralBackground1,
    overflow: "hidden",
  },
  item: {
    display: "grid",
    gap: "6px",
    padding: "14px 16px",
    borderTop: `1px solid ${tokens.colorNeutralStroke3}`,
    ":first-child": { borderTop: "none" },
  },
  itemMeta: {
    display: "flex",
    flexWrap: "wrap",
    alignItems: "center",
    columnGap: "6px",
    rowGap: "2px",
    ...typo.meta,
    ...typo.tabular,
    color: vt.text2,
  },
  sep: { color: vt.text3 },
  itemText: {
    ...typo.body,
    color: vt.text1,
    margin: 0,
    whiteSpace: "pre-wrap",
    overflowWrap: "anywhere",
  },
  token: {
    ...typo.mono,
    padding: "0 3px",
    borderRadius: tokens.borderRadiusSmall,
    backgroundColor: vt.inset,
    border: `1px solid ${tokens.colorNeutralStroke3}`,
    color: vt.text2,
  },
  segmented: { flexWrap: "wrap" },
  zone: { borderTop: `1px solid ${tokens.colorNeutralStroke3}`, paddingTop: "24px" },
  // Only while enabled: a disabled delete keeps Fluent's disabled grey.
  dangerButton: {
    ":enabled": { color: vt.danger },
    ":enabled:hover": { color: vt.danger },
    ":enabled:hover:active": { color: vt.danger },
  },
  dangerPrimary: {
    backgroundColor: tokens.colorStatusDangerBackground3,
    color: tokens.colorNeutralForegroundOnBrand,
    ":hover": { backgroundColor: tokens.colorStatusDangerBackground3Hover, color: tokens.colorNeutralForegroundOnBrand },
    ":hover:active": { backgroundColor: tokens.colorStatusDangerBackground3Pressed, color: tokens.colorNeutralForegroundOnBrand },
  },
  done: { display: "inline-flex", alignItems: "center", gap: "6px", ...typo.meta, color: vt.text2, margin: 0 },
  doneIcon: { color: vt.success, flexShrink: 0 },
});

const COUNT_LABELS: Record<string, string> = {
  email_learned: "emails learned",
  chat_learned: "chat messages learned",
  email_excluded: "emails skipped (excluded)",
  chat_excluded: "chats skipped (excluded)",
  context_excluded: "replied-to messages left out (excluded participant)",
  chat_meeting_unknown: "meeting chats skipped (meeting not found)",
  email_missing: "emails no longer in the mailbox",
  subject_blocked: "subjects left out by the privacy check",
  empty: "empty messages",
};

/** Plain-language summary of a run's content-free counts. */
export function runSummary(counts: Record<string, number>): string[] {
  const out: string[] = [];
  for (const [k, v] of Object.entries(counts)) {
    if (!v || k === "stored" || k.startsWith("eval_") || k === "style_cards") continue;
    if (k.startsWith("blocked_")) out.push(`${v} blocked by the privacy check (${k.slice(8).replaceAll("_", " ")})`);
    else if (k.startsWith("context_blocked_")) out.push(`${v} replied-to messages left out by the privacy check`);
    else if (COUNT_LABELS[k]) out.push(`${v} ${COUNT_LABELS[k]}`);
  }
  return out;
}

const AUDIENCE: Record<string, string> = {
  manager: "to your manager",
  report: "to your team",
  peer: "to colleagues",
  external: "to clients and partners",
  personal: "personal",
};

/** "1 min 20 s", "12 min", "1 h 5 min". */
function took(fromIso: string, toIso: string): string {
  const s = Math.max(0, Math.round((new Date(toIso).getTime() - new Date(fromIso).getTime()) / 1000));
  if (s < 60) return `${s} s`;
  const m = Math.floor(s / 60);
  if (m < 10) return s % 60 ? `${m} min ${s % 60} s` : `${m} min`;
  if (m < 60) return `${m} min`;
  return m % 60 ? `${Math.floor(m / 60)} h ${m % 60} min` : `${Math.floor(m / 60)} h`;
}

const cap = (s: string) => (s ? s.charAt(0).toUpperCase() + s.slice(1) : s);

/** A relative time inside a phrase ("started yesterday"), exact time on hover. */
function When({ iso }: { iso: string }) {
  const r = relativeTime(iso);
  return (
    <Tooltip content={absoluteTime(iso)} relationship="description" withArrow>
      <time dateTime={iso}>{r === "Yesterday" || r === "Tomorrow" ? r.toLowerCase() : r}</time>
    </Tooltip>
  );
}

/** Stored text with the name tokens (⟦…⟧) set in mono, so they read as placeholders, not words. */
function Redacted({ text, tokenClass }: { text: string; tokenClass: string }) {
  const parts = text.split(/(⟦[^⟧]*⟧)/);
  return (
    <>
      {parts.map((p, i) =>
        i % 2 === 1 ? (
          <span key={i} className={tokenClass}>
            {p}
          </span>
        ) : (
          p
        ),
      )}
    </>
  );
}

function RunStatus({ run }: { run: LearningRun }) {
  const s = useStyles();
  const running = run.status === "running";
  const summary = runSummary(run.counts);
  return (
    <>
      <div className={s.runHead}>
        {running ? (
          <StatusDot tone="accent">Running</StatusDot>
        ) : run.status === "done" ? (
          <StatusDot tone="success">Finished</StatusDot>
        ) : (
          <StatusDot tone="danger">Didn't finish</StatusDot>
        )}
        <span className={s.runHeadItem}>
          Started <When iso={run.startedAt} />
        </span>
        {run.finishedAt && <span className={s.runHeadItem}>Took {took(run.startedAt, run.finishedAt)}</span>}
      </div>
      {running && (
        <p className={s.runNote}>
          Reading your sent emails and chats from the sources you allowed and redacting each one before it's stored,
          then rebuilding your style cards. This page updates by itself.
        </p>
      )}
      {run.status === "failed" && (
        <p className={s.runNote}>
          This run stopped before it finished
          {run.errorCode ? (
            <>
              {" "}
              (<code className={s.code}>{run.errorCode}</code>)
            </>
          ) : null}
          . Try learning again.
        </p>
      )}
      {!running && summary.length > 0 && (
        <ul className={s.receipt} aria-label="What the last run did">
          {summary.map((line, i) => {
            const m = /^(\d+) (.+)$/.exec(line);
            return (
              <li key={i} className={s.receiptRow}>
                <span className={s.receiptNumber}>{m ? m[1] : ""}</span>
                <span className={s.receiptLabel}>{m ? m[2] : line}</span>
              </li>
            );
          })}
        </ul>
      )}
    </>
  );
}

export function Learning() {
  const styles = useStyles();
  const api = useApi();
  const navigate = useNavigate();
  const [status, setStatus] = useState<LearningStatus | null>(null);
  const [items, setItems] = useState<StoredItem[]>([]);
  const [asStored, setAsStored] = useState(true);
  const [busy, setBusy] = useState(false);
  const [confirm, setConfirm] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    try {
      const s = await api.learning();
      setStatus(s);
      setItems(s.stored.total ? (await api.storedItems({ limit: 50 })).items : []);
    } catch (e) {
      setError(errorText(e));
    }
  }, [api]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  useEffect(() => {
    if (status?.run?.status !== "running") return;
    const timer = setInterval(() => void refresh(), 2000);
    return () => clearInterval(timer);
  }, [status?.run?.status, refresh]);

  const start = async () => {
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      await api.startLearning();
      await refresh();
    } catch (e) {
      setError(
        e instanceof ApiError && e.code === "learning_running"
          ? "Learning is already running."
          : e instanceof ApiError && e.code === "review_pending"
            ? "Finish or skip the review first."
            : errorText(e),
      );
    } finally {
      setBusy(false);
    }
  };

  const remove = async () => {
    setConfirm(false);
    setBusy(true);
    try {
      const receipt = await api.deleteLearning();
      if (receipt.status === "done") setNotice(`Deleted. Receipt ${receipt.jobId.slice(0, 8)}.`);
      else setError(`Deleting didn't finish (receipt ${receipt.jobId.slice(0, 8)}). Retry it from My data.`);
      await refresh();
    } catch (e) {
      setError(errorText(e));
    } finally {
      setBusy(false);
    }
  };

  if (!status)
    return error ? (
      <Page title="Learning">
        <MessageBar intent="error">
          <MessageBarBody>{error}</MessageBarBody>
        </MessageBar>
      </Page>
    ) : (
      <PageSkeleton label="Loading what Vanimo has learned…" />
    );

  const run = status.run;
  const running = run?.status === "running";
  const gated = status.onboardingState !== "review_done";
  const total = status.stored.total;

  let storedBody: ReactNode;
  if (items.length > 0) {
    storedBody = (
      <ul className={styles.items} aria-label="Stored items">
        {items.map((i) => (
          <li key={i.id} className={styles.item}>
            <div className={styles.itemMeta}>
              <span>{i.channel === "email" ? "Email" : "Chat"}</span>
              <span className={styles.sep} aria-hidden>·</span>
              <span>{AUDIENCE[i.relationship] ?? i.relationship}</span>
              <span className={styles.sep} aria-hidden>·</span>
              <span>{cap(i.intent)}</span>
              <span className={styles.sep} aria-hidden>·</span>
              <span>{cap(i.language)}</span>
              <span className={styles.sep} aria-hidden>·</span>
              <span>{i.wordCount} words</span>
              <span className={styles.sep} aria-hidden>·</span>
              <Time iso={i.sentAt} />
            </div>
            <p className={styles.itemText}>
              {asStored ? <Redacted text={i.stored} tokenClass={styles.token} /> : i.display}
            </p>
          </li>
        ))}
      </ul>
    );
  } else {
    storedBody = (
      <EmptyState icon={<BookOpen20Regular />} title="Nothing stored yet">
        {gated
          ? "Once you've reviewed your sources, start learning: each message Vanimo keeps appears here exactly as stored."
          : "Start learning and each message Vanimo keeps appears here exactly as stored, so you can check what it holds."}
      </EmptyState>
    );
  }

  return (
    <Page
      title="Learning"
      eyebrow={<Pill>{status.sourceKind === "sample" ? "Sample workspace" : "Microsoft 365"}</Pill>}
      description="Vanimo learns how you write from your own sent emails and chat messages, only from the sources you allowed."
      actions={
        <Button
          appearance="primary"
          icon={running ? <Spinner size="extra-tiny" /> : undefined}
          disabled={gated || busy || running}
          onClick={() => void start()}
        >
          {running ? "Learning…" : run ? "Learn again" : "Start learning"}
        </Button>
      }
    >
      {gated && (
        <MessageBar intent="warning">
          <MessageBarBody>
            Vanimo reads no message text until you review your sources.{" "}
            <Link as="a" href="/setup" onClick={(e) => { e.preventDefault(); navigate("/setup"); }}>
              Review sources
            </Link>
          </MessageBarBody>
        </MessageBar>
      )}
      {error && (
        <MessageBar intent="error">
          <MessageBarBody>{error}</MessageBarBody>
        </MessageBar>
      )}

      <StatStrip label="Totals">
        <Stat value={status.stored.email} label="Emails stored" />
        <Stat value={status.stored.chat} label="Chat messages stored" />
        <Stat value={status.styleCards} label="Style cards" hint="See your persona" onClick={() => navigate("/persona")} />
      </StatStrip>

      {run && (
        <Section title={running ? "Learning now" : "Last run"}>
          <RunStatus run={run} />
        </Section>
      )}

      <Section
        title="What's stored"
        description={
          <>
            {items.length > 0 && items.length < total && `The ${items.length} most recent of ${total} items. `}
            {items.length > 0 && "Only you can read these. "}
            Each message is redacted before it's stored: ID numbers, card and bank details and secrets are removed for
            good, names become tokens, and your never-send words become placeholders.
          </>
        }
        actions={
          items.length > 0 ? (
            <TabList
              size="small"
              appearance="subtle-circular"
              className={styles.segmented}
              aria-label="How to show stored items"
              selectedValue={asStored ? "stored" : "shown"}
              onTabSelect={(_, d) => setAsStored(d.value === "stored")}
            >
              <Tab value="stored">Exactly as stored</Tab>
              <Tab value="shown">As shown to you</Tab>
            </TabList>
          ) : undefined
        }
      >
        {storedBody}
      </Section>

      <Section title="Start over" className={styles.zone}>
        <SettingList>
          <SettingRow
            label="Delete what's stored"
            description="Every stored message, name token, style card and evaluation goes now, and you get a receipt. Your persona settings and data controls stay."
          >
            <Button
              icon={<Delete16Regular />}
              className={styles.dangerButton}
              disabled={busy || total === 0}
              onClick={() => setConfirm(true)}
            >
              Delete what Vanimo learned
            </Button>
          </SettingRow>
        </SettingList>
        {notice && (
          <Rise visible appear>
            <p className={styles.done} role="status">
              <CheckmarkCircle16Filled className={styles.doneIcon} aria-hidden />
              {notice}
            </p>
          </Rise>
        )}
      </Section>

      <Dialog open={confirm} onOpenChange={(_, d) => setConfirm(d.open)}>
        <DialogSurface>
          <DialogBody>
            <DialogTitle>Delete what Vanimo learned?</DialogTitle>
            <DialogContent>
              Every stored message, name token, style card and evaluation is deleted now, and you get a receipt. Your
              persona settings and data controls stay. You can learn again any time.
            </DialogContent>
            <DialogActions>
              <Button onClick={() => setConfirm(false)}>Cancel</Button>
              <Button appearance="primary" className={styles.dangerPrimary} onClick={() => void remove()}>
                Delete
              </Button>
            </DialogActions>
          </DialogBody>
        </DialogSurface>
      </Dialog>
    </Page>
  );
}
