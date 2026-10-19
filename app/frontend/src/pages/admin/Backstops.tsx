import {
  Badge,
  Button,
  Caption1,
  Card,
  CardHeader,
  makeStyles,
  MessageBar,
  MessageBarBody,
  Spinner,
  Table,
  TableBody,
  TableCell,
  TableHeader,
  TableHeaderCell,
  TableRow,
  Text,
  tokens,
} from "@fluentui/react-components";
import { useCallback, useEffect, useState } from "react";
import type { BackstopEvent, BackstopKey, BackstopProbe, BackstopStatus } from "../../api/client";
import { useApi } from "../../api/context";
import { errorText } from "../Home";

const useStyles = makeStyles({
  stack: { display: "grid", gap: tokens.spacingVerticalL },
  row: { display: "flex", gap: tokens.spacingHorizontalM, alignItems: "center", flexWrap: "wrap" },
  muted: { color: tokens.colorNeutralForeground3 },
});

const NAMES: Record<BackstopKey | "guardrail_india", string> = {
  comprehend: "Amazon Comprehend",
  guardrail: "Bedrock Guardrails",
  guardrail_india: "Bedrock Guardrails (Indian IDs)",
  macie: "Amazon Macie",
};

const ROLE: Record<BackstopKey, string> = {
  comprehend: "Second detector inside redaction: finds names, addresses and IDs our own rules missed.",
  guardrail: "Checks everything sent to the AI model and everything it returns; blocks on any personal detail.",
  macie: "Scans a daily copy of the redacted text; a finding pauses Vanimo for the organisation.",
};

const STAGE: Record<BackstopEvent["stage"], string> = {
  redaction: "Redaction",
  model_input: "Sent to the model",
  model_output: "Model's answer",
  snapshot: "Daily snapshot",
};

const PROBE_COLOR = { ok: "success", warn: "warning", fail: "danger" } as const;

/** One probe result in plain words. */
export function probeText(p: BackstopProbe): string {
  switch (`${p.key}:${p.code}`) {
    case "comprehend:found":
      return "Found the made-up personal details in the test text.";
    case "comprehend:nothing_found":
      return "Found nothing in test text full of made-up personal details: check the service and region.";
    case "guardrail:blocked":
      return "Blocked the test text, as it should.";
    case "guardrail:not_blocked":
      return "Let test text with personal details through: check the guardrail's sensitive-information policy.";
    case "guardrail_india:blocked":
      return "Blocked each made-up PAN, GSTIN, IFSC and UPI ID on its own.";
    case "macie:findings_readable":
      return "Findings can be read.";
    case "macie:offline":
      return "Offline stand-in: snapshots are scanned in Vanimo itself.";
    default:
      if (p.key === "guardrail_india" && p.code.startsWith("missed_"))
        return `Let through: ${p.code.slice(7).replaceAll("_", ", ")}. Check the guardrail's regexes.`;
      return `Couldn't check (${p.code}).`;
  }
}

/** Entity types and counts, e.g. "NAME 2, PAN 1". Never values. */
export function kindsText(kinds: Record<string, number>): string {
  return Object.entries(kinds)
    .map(([k, n]) => `${k} ${n}`)
    .join(", ");
}

/** Admin: the AWS redaction backstops (F11), the organisation's pause, and what they caught. */
export function Backstops() {
  const styles = useStyles();
  const api = useApi();
  const [status, setStatus] = useState<BackstopStatus | null>(null);
  const [probes, setProbes] = useState<BackstopProbe[] | null>(null);
  const [note, setNote] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const load = useCallback(() => api.backstops().then(setStatus, (e) => setError(errorText(e))), [api]);
  useEffect(() => {
    void load();
  }, [load]);

  async function act(fn: () => Promise<string>) {
    setBusy(true);
    setError(null);
    setNote(null);
    try {
      setNote(await fn());
      await load();
    } catch (e) {
      setError(errorText(e));
    } finally {
      setBusy(false);
    }
  }

  if (!status)
    return error ? (
      <MessageBar intent="error">
        <MessageBarBody>{error}</MessageBarBody>
      </MessageBar>
    ) : (
      <Spinner label="Loading…" />
    );

  return (
    <div className={styles.stack}>
      {error && (
        <MessageBar intent="error">
          <MessageBarBody>{error}</MessageBarBody>
        </MessageBar>
      )}
      {note && (
        <MessageBar intent="success">
          <MessageBarBody>{note}</MessageBarBody>
        </MessageBar>
      )}
      {status.paused ? (
        <MessageBar intent="error">
          <MessageBarBody>
            Paused since {new Date(status.paused.since).toLocaleString()}: a sensitive-data finding in the daily snapshot
            (finding {status.paused.ref}). Nothing new is read, learned or drafted for anyone in your organisation. Remove
            the flagged items below (you never see them), then resume.
          </MessageBarBody>
        </MessageBar>
      ) : (
        <MessageBar intent="success">
          <MessageBarBody>Running: no open findings.</MessageBarBody>
        </MessageBar>
      )}
      <Card>
        <CardHeader
          header={<Text weight="semibold">Redaction checks</Text>}
          description={
            <Caption1 className={styles.muted}>
              Extra AWS checks on top of Vanimo's own redaction. Each one fails closed: if it can't run, nothing goes
              through unchecked.
            </Caption1>
          }
        />
        <Table size="small" aria-label="Redaction checks">
          <TableHeader>
            <TableRow>
              <TableHeaderCell>Check</TableHeaderCell>
              <TableHeaderCell>Runs as</TableHeaderCell>
              <TableHeaderCell>What it does</TableHeaderCell>
            </TableRow>
          </TableHeader>
          <TableBody>
            {status.backstops.map((b) => (
              <TableRow key={b.key}>
                <TableCell>{NAMES[b.key]}</TableCell>
                <TableCell>
                  <Badge appearance="tint" color={b.mode === "aws" ? "success" : "warning"}>
                    {b.mode === "aws" ? "AWS" : "Offline stand-in"}
                  </Badge>{" "}
                  <Caption1 className={styles.muted}>{b.label}</Caption1>
                </TableCell>
                <TableCell>{ROLE[b.key]}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
        <Caption1 className={styles.muted}>
          Comprehend checks {status.comprehendScope === "all" ? "every item" : "only items with identifiers"}; snapshots
          are rewritten every {status.snapshotEveryHours} hours.
          {status.mySnapshot &&
            ` Your snapshot: ${status.mySnapshot.items} items, ${new Date(status.mySnapshot.exportedAt).toLocaleString()}.`}
        </Caption1>
        <div className={styles.row}>
          <Button
            disabled={busy}
            onClick={() =>
              void act(async () => {
                setProbes(await api.probeBackstops());
                return "Checked with made-up test text (no one's data).";
              })
            }
          >
            Check the services
          </Button>
          <Button
            disabled={busy}
            onClick={() =>
              void act(async () => {
                const r = await api.exportSnapshots();
                return `Exported ${r.exported} snapshots${r.failed ? `, ${r.failed} failed` : ""}; ${
                  r.findings + r.newFindings
                } findings.`;
              })
            }
          >
            Export snapshots now
          </Button>
          {status.paused && (
            <Button
              appearance="primary"
              disabled={busy}
              onClick={() =>
                void act(async () => ((await api.resumePipeline()).resumed ? "Vanimo is running again." : "It wasn't paused."))
              }
            >
              Resume after review
            </Button>
          )}
        </div>
        {probes && (
          <ul aria-label="Service checks">
            {probes.map((p) => (
              <li key={p.key}>
                <Badge appearance="tint" color={PROBE_COLOR[p.state]}>
                  {p.state}
                </Badge>{" "}
                {NAMES[p.key]}: {probeText(p)} <Caption1 className={styles.muted}>({p.ms} ms)</Caption1>
              </li>
            ))}
          </ul>
        )}
      </Card>
      <Card>
        <CardHeader
          header={<Text weight="semibold">What the checks caught</Text>}
          description={<Caption1 className={styles.muted}>Types and counts only: never the values themselves.</Caption1>}
        />
        {status.events.length === 0 ? (
          <Caption1>Nothing yet.</Caption1>
        ) : (
          <Table size="small" aria-label="Caught">
            <TableHeader>
              <TableRow>
                <TableHeaderCell>When</TableHeaderCell>
                <TableHeaderCell>Check</TableHeaderCell>
                <TableHeaderCell>Where</TableHeaderCell>
                <TableHeaderCell>Found</TableHeaderCell>
                <TableHeaderCell>User</TableHeaderCell>
                <TableHeaderCell />
              </TableRow>
            </TableHeader>
            <TableBody>
              {status.events.map((e, i) => (
                <TableRow key={`${e.at}-${i}`}>
                  <TableCell>{new Date(e.at).toLocaleString()}</TableCell>
                  <TableCell>
                    {NAMES[e.source]}
                    {e.severity && (
                      <Badge appearance="tint" color={e.severity === "high" ? "danger" : "warning"}>
                        {e.severity}
                      </Badge>
                    )}
                  </TableCell>
                  <TableCell>{STAGE[e.stage]}</TableCell>
                  <TableCell>{kindsText(e.kinds)}</TableCell>
                  <TableCell>
                    <Caption1 className={styles.muted}>{e.user ?? "—"}</Caption1>
                  </TableCell>
                  <TableCell>
                    {e.purgedAt ? (
                      <Caption1 className={styles.muted}>Removed</Caption1>
                    ) : (
                      e.flaggedItems > 0 && (
                        <Button
                          size="small"
                          disabled={busy}
                          onClick={() =>
                            void act(async () => {
                              const r = await api.purgeFlagged(e.id);
                              return `Removed ${r.removed} flagged item${r.removed === 1 ? "" : "s"}. The snapshot is rewritten without them.`;
                            })
                          }
                        >
                          Remove {e.flaggedItems} flagged item{e.flaggedItems === 1 ? "" : "s"}
                        </Button>
                      )
                    )}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </Card>
    </div>
  );
}
