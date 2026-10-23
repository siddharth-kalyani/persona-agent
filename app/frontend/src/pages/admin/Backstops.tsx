import {
  Button,
  makeStyles,
  MessageBar,
  MessageBarActions,
  MessageBarBody,
  MessageBarTitle,
  Spinner,
} from "@fluentui/react-components";
import { ShieldCheckmark20Regular } from "@fluentui/react-icons";
import { useCallback, useEffect, useState } from "react";
import type { BackstopEvent, BackstopKey, BackstopProbe, BackstopStatus } from "../../api/client";
import { useApi } from "../../api/context";
import {
  absoluteTime,
  DataTable,
  EmptyState,
  KeyValueList,
  Page,
  PageSkeleton,
  Pill,
  Rise,
  Section,
  StatusDot,
  Td,
  Time,
  type Tone,
  Tr,
  typo,
  vt,
} from "../../ui";
import { errorText } from "../Home";

const useStyles = makeStyles({
  name: { ...typo.itemTitle, color: vt.text1, display: "block" },
  role: { ...typo.meta, color: vt.text2, display: "block", maxWidth: "48ch" },
  modeLabel: { ...typo.meta, color: vt.text3, display: "block", marginTop: "4px" },
  probes: { display: "grid", gap: "8px", minWidth: "220px", "@media (max-width: 639px)": { minWidth: 0 } },
  probe: { display: "grid", gap: "2px" },
  probeHead: { display: "flex", gap: "8px", alignItems: "center", flexWrap: "wrap" },
  ms: { ...typo.label, ...typo.tabular, fontWeight: 400, color: vt.text3 },
  probeText: { ...typo.meta, color: vt.text1 },
  quiet: { ...typo.meta, color: vt.text3 },
  ref: { ...typo.mono, color: vt.text3, display: "block" },
  code: { ...typo.mono },
  checkCell: { display: "flex", gap: "6px", alignItems: "center", flexWrap: "wrap" },
  stage: { display: "block", color: vt.text1 },
  outcome: { display: "block", color: vt.text2 },
  found: { ...typo.tabular, color: vt.text1 },
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

const OUTCOME: Record<BackstopEvent["outcome"], string> = {
  blocked: "Blocked",
  finding: "Finding",
  unavailable: "Check unavailable",
};

const SEVERITY: Record<NonNullable<BackstopEvent["severity"]>, string> = { low: "Low", medium: "Medium", high: "High" };

const PROBE: Record<BackstopProbe["state"], [Tone, string]> = {
  ok: ["success", "Passed"],
  warn: ["warning", "Warning"],
  fail: ["danger", "Failed"],
};

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

type Work = "probe" | "export" | "resume" | `purge-${number}`;

/** Admin: the AWS redaction backstops (F11), the organisation's pause, and what they caught. */
export function Backstops() {
  const styles = useStyles();
  const api = useApi();
  const [status, setStatus] = useState<BackstopStatus | null>(null);
  const [probes, setProbes] = useState<BackstopProbe[] | null>(null);
  const [note, setNote] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [working, setWorking] = useState<Work | null>(null);

  const load = useCallback(() => api.backstops().then(setStatus, (e) => setError(errorText(e))), [api]);
  useEffect(() => {
    void load();
  }, [load]);

  async function act(fn: () => Promise<string>, what: Work) {
    setBusy(true);
    setWorking(what);
    setError(null);
    setNote(null);
    try {
      setNote(await fn());
      await load();
    } catch (e) {
      setError(errorText(e));
    } finally {
      setBusy(false);
      setWorking(null);
    }
  }

  if (!status)
    return error ? (
      <Page title="Redaction checks">
        <MessageBar intent="error">
          <MessageBarBody>{error}</MessageBarBody>
        </MessageBar>
      </Page>
    ) : (
      <PageSkeleton label="Loading…" />
    );

  const spin = (what: Work) => (working === what ? <Spinner size="extra-tiny" aria-hidden /> : undefined);
  const probesFor = (key: BackstopKey) =>
    (probes ?? []).filter((p) => p.key === key || (key === "guardrail" && p.key === "guardrail_india"));

  return (
    <Page
      title="Redaction checks"
      eyebrow={
        status.paused ? (
          <StatusDot tone="warning">Paused</StatusDot>
        ) : (
          <StatusDot tone="success">Running: no open findings.</StatusDot>
        )
      }
      description="Extra AWS checks on top of Vanimo's own redaction. Each one fails closed: if it can't run, nothing goes through unchecked."
      actions={
        <>
          <Button
            disabled={busy}
            icon={spin("export")}
            onClick={() =>
              void act(async () => {
                const r = await api.exportSnapshots();
                return `Exported ${r.exported} snapshots${r.failed ? `, ${r.failed} failed` : ""}; ${
                  r.findings + r.newFindings
                } findings.`;
              }, "export")
            }
          >
            Export snapshots now
          </Button>
          <Button
            disabled={busy}
            icon={spin("probe")}
            onClick={() =>
              void act(async () => {
                setProbes(await api.probeBackstops());
                return "Checked with made-up test text (no one's data).";
              }, "probe")
            }
          >
            Check the services
          </Button>
        </>
      }
    >
      {status.paused && (
        <MessageBar intent="warning" layout="multiline">
          <MessageBarBody>
            <MessageBarTitle>Review the finding, then resume</MessageBarTitle>
            Paused since {absoluteTime(status.paused.since)}: a sensitive-data finding in the daily snapshot
            {status.paused.ref ? (
              <>
                {" "}
                (finding <span className={styles.code}>{status.paused.ref}</span>)
              </>
            ) : null}
            . Nothing new is read, learned or drafted for anyone in your organisation. Remove the flagged items below (you
            never see them), then resume.
          </MessageBarBody>
          <MessageBarActions>
            <Button
              appearance="primary"
              disabled={busy}
              icon={spin("resume")}
              onClick={() =>
                void act(
                  async () => ((await api.resumePipeline()).resumed ? "Vanimo is running again." : "It wasn't paused."),
                  "resume",
                )
              }
            >
              Resume after review
            </Button>
          </MessageBarActions>
        </MessageBar>
      )}
      {error && (
        <MessageBar intent="error">
          <MessageBarBody>{error}</MessageBarBody>
        </MessageBar>
      )}
      {note && (
        <Rise visible appear>
          <div role="status">
            <StatusDot tone="success">{note}</StatusDot>
          </div>
        </Rise>
      )}

      <Section title="Checks" description="Each check, how it runs here, and the result of the last service check on this page.">
        <DataTable label="Redaction checks" columns={[{ label: "Check" }, { label: "Runs as" }, { label: "Last service check" }]}>
          {status.backstops.map((b) => {
            const results = probesFor(b.key);
            return (
              <Tr key={b.key}>
                <Td primary>
                  <span className={styles.name}>{NAMES[b.key]}</span>
                  <span className={styles.role}>{ROLE[b.key]}</span>
                </Td>
                <Td label="Runs as">
                  <Pill tone={b.mode === "aws" ? "neutral" : "warning"}>{b.mode === "aws" ? "AWS" : "Offline stand-in"}</Pill>
                  <span className={styles.modeLabel}>{b.label}</span>
                </Td>
                <Td label="Last service check">
                  {results.length === 0 ? (
                    <span className={styles.quiet}>Not checked yet</span>
                  ) : (
                    <div className={styles.probes}>
                      {results.map((p) => {
                        const [tone, word] = PROBE[p.state];
                        return (
                          <div key={p.key} className={styles.probe}>
                            <span className={styles.probeHead}>
                              <StatusDot tone={tone}>{p.key === "guardrail_india" ? `${word} · Indian IDs` : word}</StatusDot>
                              <span className={styles.ms}>{p.ms} ms</span>
                            </span>
                            <span className={styles.probeText}>{probeText(p)}</span>
                          </div>
                        );
                      })}
                    </div>
                  )}
                </Td>
              </Tr>
            );
          })}
        </DataTable>
        <KeyValueList
          items={[
            ["Comprehend checks", status.comprehendScope === "all" ? "Every item" : "Only items with identifiers"],
            ["Snapshots", `Rewritten every ${status.snapshotEveryHours} hours`],
            [
              "Your snapshot",
              status.mySnapshot ? (
                <>
                  {status.mySnapshot.items} items · exported <Time iso={status.mySnapshot.exportedAt} />
                </>
              ) : (
                "Not exported yet"
              ),
            ],
          ]}
        />
      </Section>

      <Section title="What the checks caught" description="Types and counts only: never the values themselves.">
        {status.events.length === 0 ? (
          <EmptyState icon={<ShieldCheckmark20Regular />} title="Nothing caught yet">
            When a check blocks something or finds personal details, the type and count appear here.
          </EmptyState>
        ) : (
          <DataTable
            label="Caught"
            columns={[
              { label: "When" },
              { label: "Check" },
              { label: "Found" },
              { label: "User" },
              { hiddenLabel: "Actions" },
            ]}
          >
            {status.events.map((e, i) => (
              <Tr key={`${e.at}-${i}`}>
                <Td label="When" numeric>
                  <Time iso={e.at} />
                </Td>
                <Td label="Check">
                  <span className={styles.checkCell}>
                    <span className={styles.stage}>{NAMES[e.source]}</span>
                    {e.severity && (
                      <Pill tone={e.severity === "high" ? "danger" : "warning"}>{SEVERITY[e.severity]} severity</Pill>
                    )}
                  </span>
                  <span className={styles.outcome}>
                    {STAGE[e.stage]} · {OUTCOME[e.outcome] ?? e.outcome}
                  </span>
                  <span className={styles.ref}>{e.ref}</span>
                </Td>
                <Td label="Found">
                  <span className={styles.found}>{kindsText(e.kinds)}</span>
                </Td>
                <Td label="User" mono>
                  {e.user ?? "—"}
                </Td>
                <Td actions>
                  {e.purgedAt ? (
                    <StatusDot>Removed</StatusDot>
                  ) : (
                    e.flaggedItems > 0 && (
                      <Button
                        size="small"
                        disabled={busy}
                        icon={spin(`purge-${e.id}`)}
                        onClick={() =>
                          void act(async () => {
                            const r = await api.purgeFlagged(e.id);
                            return `Removed ${r.removed} flagged item${r.removed === 1 ? "" : "s"}. The snapshot is rewritten without them.`;
                          }, `purge-${e.id}`)
                        }
                      >
                        Remove {e.flaggedItems} flagged item{e.flaggedItems === 1 ? "" : "s"}
                      </Button>
                    )
                  )}
                </Td>
              </Tr>
            ))}
          </DataTable>
        )}
      </Section>
    </Page>
  );
}
