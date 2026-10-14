import {
  Button,
  Caption1,
  Card,
  CardHeader,
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
  Switch,
  Table,
  TableBody,
  TableCell,
  TableHeader,
  TableHeaderCell,
  TableRow,
  Text,
  Title3,
  tokens,
} from "@fluentui/react-components";
import { useCallback, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { ApiError, type LearningStatus, type StoredItem } from "../../api/client";
import { useApi } from "../../api/context";
import { errorText } from "../Home";

const useStyles = makeStyles({
  stack: { display: "grid", gap: tokens.spacingVerticalL },
  row: { display: "flex", gap: tokens.spacingHorizontalM, alignItems: "center", flexWrap: "wrap" },
  stats: { display: "grid", gap: tokens.spacingHorizontalL, gridTemplateColumns: "repeat(auto-fit, minmax(140px, 1fr))" },
  stat: { display: "grid" },
  big: { fontSize: tokens.fontSizeHero700, fontWeight: tokens.fontWeightSemibold },
  muted: { color: tokens.colorNeutralForeground3 },
  text: { whiteSpace: "pre-wrap", fontFamily: tokens.fontFamilyMonospace, fontSize: tokens.fontSizeBase200, margin: 0 },
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
      <MessageBar intent="error">
        <MessageBarBody>{error}</MessageBarBody>
      </MessageBar>
    ) : (
      <Spinner label="Loading…" />
    );

  const run = status.run;
  const gated = status.onboardingState !== "review_done";
  return (
    <div className={styles.stack}>
      <Title3 as="h2">Learning</Title3>
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
      {notice && (
        <MessageBar intent="success">
          <MessageBarBody>{notice}</MessageBarBody>
        </MessageBar>
      )}
      <Card>
        <CardHeader
          header={<Text weight="semibold">Learn from your sent messages</Text>}
          description={
            <Caption1>
              Only your own sent emails and chat messages from sources you allowed. Each one is redacted before it is
              stored: ID numbers, card and bank details and secrets are removed for good, names become tokens, and your
              never-send words become placeholders.
            </Caption1>
          }
        />
        <div className={styles.row}>
          <Button appearance="primary" disabled={gated || busy || run?.status === "running"} onClick={() => void start()}>
            {run?.status === "running" ? "Learning…" : run ? "Learn again" : "Start learning"}
          </Button>
          <Button disabled={busy || status.stored.total === 0} onClick={() => setConfirm(true)}>
            Delete what Vanimo learned
          </Button>
          {run && (
            <Caption1 className={styles.muted}>
              Last run {run.status} · {new Date(run.startedAt).toLocaleString()}
              {run.errorCode ? ` · ${run.errorCode}` : ""}
            </Caption1>
          )}
        </div>
        <div className={styles.stats}>
          <div className={styles.stat}>
            <span className={styles.big}>{status.stored.email}</span>
            <Caption1>emails stored</Caption1>
          </div>
          <div className={styles.stat}>
            <span className={styles.big}>{status.stored.chat}</span>
            <Caption1>chat messages stored</Caption1>
          </div>
          <div className={styles.stat}>
            <span className={styles.big}>{status.styleCards}</span>
            <Caption1>style cards</Caption1>
          </div>
        </div>
        {run && runSummary(run.counts).length > 0 && (
          <Caption1 className={styles.muted}>{runSummary(run.counts).join(" · ")}</Caption1>
        )}
      </Card>
      {items.length > 0 && (
        <Card>
          <CardHeader
            header={<Text weight="semibold">What's stored</Text>}
            description={<Caption1>The 50 most recent items. Only you can read these.</Caption1>}
            action={
              <Switch
                checked={asStored}
                onChange={(_, d) => setAsStored(d.checked)}
                label={asStored ? "Exactly as stored" : "As shown to you"}
              />
            }
          />
          <Table size="small" aria-label="Stored items">
            <TableHeader>
              <TableRow>
                <TableHeaderCell>Text</TableHeaderCell>
                <TableHeaderCell>Audience</TableHeaderCell>
                <TableHeaderCell>Intent</TableHeaderCell>
                <TableHeaderCell>Language</TableHeaderCell>
              </TableRow>
            </TableHeader>
            <TableBody>
              {items.map((i) => (
                <TableRow key={i.id}>
                  <TableCell>
                    <pre className={styles.text}>{asStored ? i.stored : i.display}</pre>
                  </TableCell>
                  <TableCell>
                    {i.relationship} · {i.channel}
                  </TableCell>
                  <TableCell>{i.intent}</TableCell>
                  <TableCell>{i.language}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </Card>
      )}
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
              <Button appearance="primary" onClick={() => void remove()}>
                Delete
              </Button>
            </DialogActions>
          </DialogBody>
        </DialogSurface>
      </Dialog>
    </div>
  );
}
