/** Learning: Vanimo learns how you write from your own sent emails and chat messages (only from the
 * sources you allowed), redacting each one before it is stored. The header starts or repeats a run,
 * stat cards say what's stored, the last run is a card with its status and per-source counts,
 * "What's stored" shows every kept item exactly as stored (tokens as mono chips) or as shown to you,
 * and deleting sits at the end in a danger-zone card. */
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
  mergeClasses,
  MessageBar,
  MessageBarBody,
  Spinner,
  tokens,
  Tooltip,
} from "@fluentui/react-components";
import {
  ArrowSync16Regular,
  BookOpen20Regular,
  CalendarCancel16Regular,
  Chat16Regular,
  Chat20Regular,
  CheckmarkCircle16Filled,
  ChevronDown16Regular,
  Clock16Regular,
  Code16Regular,
  Delete16Regular,
  Delete20Regular,
  DocumentDismiss16Regular,
  Eye16Regular,
  EyeOff16Regular,
  History20Regular,
  Mail16Regular,
  Mail20Regular,
  MailDismiss16Regular,
  People16Regular,
  Play16Regular,
  ShieldError16Regular,
  Tag16Regular,
  TextAlignLeft16Regular,
  TextQuote20Regular,
  Timer16Regular,
  Translate16Regular,
} from "@fluentui/react-icons";
import { useCallback, useEffect, useState, type ReactElement, type ReactNode } from "react";
import { useNavigate } from "react-router-dom";
import { ApiError, type LearningRun, type LearningStatus, type StoredItem } from "../../api/client";
import { useApi } from "../../api/context";
import {
  absoluteTime,
  CHANNELS,
  EmptyState,
  IconTile,
  List,
  Page,
  PageSkeleton,
  Pill,
  relativeTime,
  Rise,
  Section,
  Segmented,
  Stat,
  StatStrip,
  Surface,
  Time,
  typo,
  vt,
  type Tone,
} from "../../ui";
import { errorText } from "../Home";

/** Stored items shown before "Show all". */
const SHOWN = 12;

const PHONE = "@media (max-width: 639px)";

const useStyles = makeStyles({
  // Last run
  runMeta: { display: "flex", alignItems: "center", flexWrap: "wrap", gap: "6px 18px", ...typo.meta, ...typo.tabular, color: vt.text2 },
  runMetaItem: { display: "inline-flex", alignItems: "center", gap: "6px", "& > svg": { color: vt.text3 } },
  runNote: { ...typo.meta, color: vt.text2, margin: "12px 0 0", maxWidth: "72ch" },
  code: {
    ...typo.mono,
    padding: "0 4px",
    borderRadius: "4px",
    backgroundColor: vt.neutralTint,
    color: vt.text1,
  },
  receipt: {
    display: "grid",
    gridTemplateColumns: "repeat(auto-fill, minmax(220px, 1fr))",
    gap: "8px",
    margin: "14px 0 0",
    padding: 0,
    listStyle: "none",
  },
  // Each count in a well inside the card.
  receiptItem: {
    display: "grid",
    gridTemplateColumns: "auto minmax(0, 1fr)",
    alignItems: "center",
    gap: "12px",
    padding: "10px 12px",
    borderRadius: "8px",
    backgroundColor: vt.inset,
    border: `1px solid ${vt.borderSubtle}`,
  },
  receiptText: { display: "grid", minWidth: 0 },
  receiptNumber: { ...typo.cardTitle, ...typo.tabular, color: vt.text1, fontSize: "16px", lineHeight: "22px" },
  receiptLabel: { ...typo.meta, color: vt.text2 },
  // Stored items
  item: {
    display: "grid",
    gridTemplateColumns: "auto minmax(0, 1fr)",
    columnGap: "14px",
    padding: "14px 16px",
    borderTop: `1px solid ${vt.borderSubtle}`,
    ":first-child": { borderTopColor: "transparent" },
    [PHONE]: { columnGap: "12px" },
  },
  itemBody: { display: "grid", gap: "8px", minWidth: 0 },
  itemText: {
    ...typo.body,
    color: vt.text1,
    margin: 0,
    whiteSpace: "pre-wrap",
    overflowWrap: "anywhere",
    paddingTop: "6px",
  },
  itemMeta: {
    display: "flex",
    flexWrap: "wrap",
    alignItems: "center",
    gap: "4px 14px",
    ...typo.meta,
    ...typo.tabular,
    color: vt.text2,
  },
  metaItem: { display: "inline-flex", alignItems: "center", gap: "5px", "& > svg": { color: vt.text3, flexShrink: 0 } },
  token: {
    ...typo.mono,
    padding: "0 4px",
    borderRadius: "4px",
    backgroundColor: vt.neutralTint,
    color: vt.text2,
  },
  more: { listStyle: "none", padding: "8px 12px", display: "flex", justifyContent: "center", borderTop: `1px solid ${vt.borderSubtle}` },
  // Start over
  zone: {
    display: "grid",
    gridTemplateColumns: "auto minmax(0, 1fr) auto",
    alignItems: "center",
    gap: "14px 16px",
    [PHONE]: { gridTemplateColumns: "auto minmax(0, 1fr)" },
  },
  zoneText: { display: "grid", gap: "2px", minWidth: 0 },
  zoneTitle: { ...typo.itemTitle, color: vt.text1 },
  zoneBody: { ...typo.meta, color: vt.text2, maxWidth: "64ch" },
  zoneAction: { [PHONE]: { gridColumn: "2 / -1", justifySelf: "start" } },
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
  done: {
    display: "flex",
    alignItems: "center",
    gap: "6px",
    ...typo.meta,
    color: vt.text2,
    margin: "14px 0 0",
    paddingTop: "12px",
    borderTop: `1px solid ${vt.borderSubtle}`,
  },
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

/** A run's content-free counts as { key, n, label } lines, in the order the run reported them. */
function runLines(counts: Record<string, number>): Array<{ key: string; n: number; label: string }> {
  const out: Array<{ key: string; n: number; label: string }> = [];
  for (const [k, v] of Object.entries(counts)) {
    if (!v || k === "stored" || k.startsWith("eval_") || k === "style_cards") continue;
    if (k.startsWith("blocked_")) out.push({ key: k, n: v, label: `blocked by the privacy check (${k.slice(8).replaceAll("_", " ")})` });
    else if (k.startsWith("context_blocked_")) out.push({ key: k, n: v, label: "replied-to messages left out by the privacy check" });
    else if (COUNT_LABELS[k]) out.push({ key: k, n: v, label: COUNT_LABELS[k] });
  }
  return out;
}

/** Plain-language summary of a run's content-free counts. */
export function runSummary(counts: Record<string, number>): string[] {
  return runLines(counts).map((l) => `${l.n} ${l.label}`);
}

/** The icon for one count: learned in the channel's colour, skipped in grey, blocked in amber. */
function countIcon(key: string): { icon: ReactElement; tone: Tone } {
  if (key === "email_learned") return { icon: <Mail16Regular />, tone: "blue" };
  if (key === "chat_learned") return { icon: <Chat16Regular />, tone: "purple" };
  if (key.includes("blocked")) return { icon: <ShieldError16Regular />, tone: "warning" };
  if (key.endsWith("_excluded")) return { icon: <EyeOff16Regular />, tone: "neutral" };
  if (key === "chat_meeting_unknown") return { icon: <CalendarCancel16Regular />, tone: "neutral" };
  if (key === "email_missing") return { icon: <MailDismiss16Regular />, tone: "neutral" };
  return { icon: <DocumentDismiss16Regular />, tone: "neutral" };
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

/** Stored text with the name tokens (⟦…⟧) set as mono chips, so they read as placeholders, not words. */
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
  const lines = runLines(run.counts);
  return (
    <>
      <div className={s.runMeta}>
        <span className={s.runMetaItem}>
          <Clock16Regular aria-hidden />
          <span>
            Started <When iso={run.startedAt} />
          </span>
        </span>
        {run.finishedAt && (
          <span className={s.runMetaItem}>
            <Timer16Regular aria-hidden />
            Took {took(run.startedAt, run.finishedAt)}
          </span>
        )}
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
      {!running && lines.length > 0 && (
        <ul className={s.receipt} aria-label="What the last run did">
          {lines.map((line) => {
            const { icon, tone } = countIcon(line.key);
            return (
              <li key={line.key} className={s.receiptItem}>
                <IconTile icon={icon} tone={tone} size={32} />
                <span className={s.receiptText}>
                  <span className={s.receiptNumber}>{line.n}</span>
                  <span className={s.receiptLabel}>{cap(line.label)}</span>
                </span>
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
  const [showAll, setShowAll] = useState(false);
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
      <List bordered label="Stored items">
        {(showAll ? items : items.slice(0, SHOWN)).map((i) => {
          const channel = CHANNELS[i.channel];
          return (
            <li key={i.id} className={styles.item}>
              <IconTile icon={channel.icon} tone={channel.tone} size={32} label={i.channel === "email" ? "Email" : "Chat"} />
              <div className={styles.itemBody}>
                <p className={styles.itemText}>
                  {asStored ? <Redacted text={i.stored} tokenClass={styles.token} /> : i.display}
                </p>
                <div className={styles.itemMeta}>
                  <span className={styles.metaItem}>
                    <People16Regular aria-hidden />
                    {cap(AUDIENCE[i.relationship] ?? i.relationship)}
                  </span>
                  <span className={styles.metaItem}>
                    <Tag16Regular aria-hidden />
                    {cap(i.intent)}
                  </span>
                  <span className={styles.metaItem}>
                    <Translate16Regular aria-hidden />
                    {cap(i.language)}
                  </span>
                  <span className={styles.metaItem}>
                    <TextAlignLeft16Regular aria-hidden />
                    {i.wordCount} words
                  </span>
                  <span className={styles.metaItem}>
                    <Clock16Regular aria-hidden />
                    <Time iso={i.sentAt} />
                  </span>
                </div>
              </div>
            </li>
          );
        })}
        {!showAll && items.length > SHOWN && (
          <li className={styles.more}>
            <Button appearance="subtle" size="small" icon={<ChevronDown16Regular />} onClick={() => setShowAll(true)}>
              Show all {items.length}
            </Button>
          </li>
        )}
      </List>
    );
  } else {
    storedBody = (
      <Surface padding="l">
        <EmptyState center icon={<BookOpen20Regular />} title="Nothing stored yet">
          {gated
            ? "Once you've reviewed your sources, start learning: each message Vanimo keeps appears here exactly as stored."
            : "Start learning and each message Vanimo keeps appears here exactly as stored, so you can check what it holds."}
        </EmptyState>
      </Surface>
    );
  }

  return (
    <Page
      title="Learning"
      description="Vanimo learns how you write from your own sent emails and chat messages, only from the sources you allowed."
      actions={
        <Button
          appearance="primary"
          icon={running ? <Spinner size="extra-tiny" /> : run ? <ArrowSync16Regular /> : <Play16Regular />}
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
        <Stat icon={<Mail20Regular />} tone="blue" value={status.stored.email} label="Emails stored" hint="From your sent mail" />
        <Stat icon={<Chat20Regular />} tone="purple" value={status.stored.chat} label="Chat messages stored" hint="From your Teams chats" />
        <Stat
          icon={<TextQuote20Regular />}
          value={status.styleCards}
          label="Style cards"
          hint="See your persona"
          onClick={() => navigate("/persona")}
        />
      </StatStrip>

      {run && (
        <Section
          variant="card"
          icon={<History20Regular />}
          title={running ? "Learning now" : "Last run"}
          actions={
            running ? (
              <Pill tone="accent" dot>
                Running
              </Pill>
            ) : run.status === "done" ? (
              <Pill tone="success" dot>
                Finished
              </Pill>
            ) : (
              <Pill tone="danger" dot>
                Didn't finish
              </Pill>
            )
          }
        >
          <RunStatus run={run} />
        </Section>
      )}

      <Section
        title="What's stored"
        count={total || undefined}
        description={
          <>
            {items.length > 0 && items.length < total && `The ${items.length} most recent of ${total} items. `}
            {items.length > 0 && "Only you can read these. "}
            Each message is redacted before it's stored.
          </>
        }
        info="ID numbers, card and bank details and secrets are removed for good, names become tokens, and your never-send words become placeholders. “Exactly as stored” shows the tokens; “As shown to you” puts the names back for you."
        actions={
          items.length > 0 ? (
            <Segmented
              label="How to show stored items"
              value={asStored ? "stored" : "shown"}
              onChange={(v) => setAsStored(v === "stored")}
              segments={[
                { value: "stored", label: "Exactly as stored", icon: <Code16Regular /> },
                { value: "shown", label: "As shown to you", icon: <Eye16Regular /> },
              ]}
            />
          ) : undefined
        }
      >
        {storedBody}
      </Section>

      <Section title="Start over">
        <Surface>
          <div className={styles.zone}>
            <IconTile icon={<Delete20Regular />} tone="danger" size={36} />
            <div className={styles.zoneText}>
              <span className={styles.zoneTitle}>Delete what's stored</span>
              <span className={styles.zoneBody}>
                Every stored message, name token, style card and evaluation goes now, and you get a receipt. Your persona
                settings and data controls stay.
              </span>
            </div>
            <Button
              icon={<Delete16Regular />}
              className={mergeClasses(styles.dangerButton, styles.zoneAction)}
              disabled={busy || total === 0}
              onClick={() => setConfirm(true)}
            >
              Delete what Vanimo learned
            </Button>
          </div>
          {notice && (
            <Rise visible appear>
              <p className={styles.done} role="status">
                <CheckmarkCircle16Filled className={styles.doneIcon} aria-hidden />
                {notice}
              </p>
            </Rise>
          )}
        </Surface>
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
