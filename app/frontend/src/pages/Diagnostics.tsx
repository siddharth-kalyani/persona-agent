import {
  Badge,
  Button,
  Caption1,
  Card,
  CardHeader,
  Link,
  makeStyles,
  MessageBar,
  MessageBarBody,
  Table,
  TableBody,
  TableCell,
  TableHeader,
  TableHeaderCell,
  TableRow,
  Text,
  tokens,
} from "@fluentui/react-components";
import { useState } from "react";
import type { CheckResult, HeaderPass, LatencyResult, Outcome } from "../api/client";
import { useApi } from "../api/context";
import { errorText } from "./Home";

const useStyles = makeStyles({
  stack: { display: "grid", gap: tokens.spacingVerticalL },
  row: { display: "flex", gap: tokens.spacingHorizontalM, alignItems: "center", flexWrap: "wrap" },
  details: { fontFamily: tokens.fontFamilyMonospace, fontSize: tokens.fontSizeBase200, wordBreak: "break-word" },
});

const OUTCOME_COLOR: Record<Outcome, "success" | "warning" | "danger" | "informative"> = {
  ok: "success",
  warn: "warning",
  fail: "danger",
  skipped: "informative",
};

/** Admin page for the M0 week-1 spikes. Every result is counts and status codes — no content. */
export function Diagnostics() {
  const styles = useStyles();
  const api = useApi();
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [headerPass, setHeaderPass] = useState<HeaderPass | null>(null);
  const [checks, setChecks] = useState<CheckResult[] | null>(null);
  const [latency, setLatency] = useState<LatencyResult[] | null>(null);
  const [draft, setDraft] = useState<{ draftId: string; webLink: string | null } | null>(null);

  async function run<T>(label: string, fn: () => Promise<T>, done: (v: T) => void) {
    setBusy(label);
    setError(null);
    try {
      done(await fn());
    } catch (e) {
      setError(errorText(e));
    } finally {
      setBusy(null);
    }
  }

  return (
    <div className={styles.stack}>
      {error && (
        <MessageBar intent="error">
          <MessageBarBody>{error}</MessageBarBody>
        </MessageBar>
      )}

      <Card>
        <CardHeader
          header={<Text weight="semibold">Microsoft 365 checks</Text>}
          description={<Caption1>Profile, sent-mail headers and delta, chat roster, calendar, meeting transcripts.</Caption1>}
        />
        <div className={styles.row}>
          <Button appearance="primary" disabled={!!busy} onClick={() => run("checks", () => api.runDiagnostics(), (r) => setChecks(r.results))}>
            {busy === "checks" ? "Running…" : "Run checks"}
          </Button>
          <Button disabled={!!busy} onClick={() => run("pass", () => api.headerPass(), setHeaderPass)}>
            {busy === "pass" ? "Timing (up to 45 s)…" : "Time the header pass"}
          </Button>
        </div>
        <Caption1>Headers and counts only — no message text is read (that waits for the review step in M1).</Caption1>
        {headerPass && (
          <Caption1 className={styles.details}>
            sent headers: {headerPass.sentItems} in {headerPass.sentPages} pages ({headerPass.sentFinished ? "complete" : "not finished"}) ·
            chats: {headerPass.chats} ({headerPass.chatsFinished ? "complete" : "not finished"}) · {Math.round(headerPass.elapsedMs / 1000)} s ·{" "}
            {headerPass.itemsPerSecond ?? "—"} headers/s
          </Caption1>
        )}
        {checks && (
          <Table size="small" aria-label="Check results">
            <TableHeader>
              <TableRow>
                <TableHeaderCell>Check</TableHeaderCell>
                <TableHeaderCell>Result</TableHeaderCell>
                <TableHeaderCell>Time</TableHeaderCell>
                <TableHeaderCell>Details</TableHeaderCell>
              </TableRow>
            </TableHeader>
            <TableBody>
              {checks.map((c) => (
                <TableRow key={c.check}>
                  <TableCell>{c.check}</TableCell>
                  <TableCell>
                    <Badge color={OUTCOME_COLOR[c.outcome]}>{c.outcome}</Badge>
                  </TableCell>
                  <TableCell>{Math.round(c.durationMs)} ms</TableCell>
                  <TableCell className={styles.details}>
                    {Object.entries(c.details)
                      .map(([k, v]) => `${k}=${String(v)}`)
                      .join("  ")}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </Card>

      <Card>
        <CardHeader
          header={<Text weight="semibold">Claude on Bedrock latency</Text>}
          description={<Caption1>Five short synthetic prompts per model from this region; time to first token (min / median / max).</Caption1>}
        />
        <div className={styles.row}>
          <Button disabled={!!busy} onClick={() => run("latency", () => api.bedrockLatency(5), setLatency)}>
            {busy === "latency" ? "Measuring…" : "Measure latency"}
          </Button>
        </div>
        {latency && (
          <Table size="small" aria-label="Latency results">
            <TableHeader>
              <TableRow>
                <TableHeaderCell>Model</TableHeaderCell>
                <TableHeaderCell>First token min / median / max</TableHeaderCell>
                <TableHeaderCell>Total median</TableHeaderCell>
                <TableHeaderCell>Errors</TableHeaderCell>
              </TableRow>
            </TableHeader>
            <TableBody>
              {latency.map((l) => (
                <TableRow key={l.modelId}>
                  <TableCell>{l.modelId}</TableCell>
                  <TableCell>
                    {l.ttftMinMs ?? "—"} / {l.ttftMedianMs ?? "—"} / {l.ttftMaxMs ?? "—"} ms
                  </TableCell>
                  <TableCell>{l.totalMedianMs ?? "—"} ms</TableCell>
                  <TableCell>{l.errors ? `${l.errors} (${l.errorTypes.join(", ")})` : "0"}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </Card>

      <Card>
        <CardHeader
          header={<Text weight="semibold">Drafts folder test</Text>}
          description={
            <Caption1>
              Creates a reply draft to your newest inbox email, marked "safe to delete". Check that it appears in Outlook on
              your phone, then delete it here.
            </Caption1>
          }
        />
        <div className={styles.row}>
          <Button disabled={!!busy || !!draft} onClick={() => run("draft", () => api.createDraftProbe(), setDraft)}>
            Create test draft
          </Button>
          {draft && (
            <>
              {draft.webLink && (
                <Link href={draft.webLink} target="_blank" rel="noreferrer">
                  Open in Outlook on the web
                </Link>
              )}
              <Button disabled={!!busy} onClick={() => run("delete", () => api.deleteDraftProbe(draft.draftId), () => setDraft(null))}>
                Delete test draft
              </Button>
            </>
          )}
        </div>
      </Card>
    </div>
  );
}
