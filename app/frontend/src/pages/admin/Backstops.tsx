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
  CheckmarkCircle16Filled,
  CheckmarkCircle16Regular,
  Circle16Regular,
  Clock16Regular,
  Cloud16Regular,
  Cloud20Regular,
  CloudArrowUp16Regular,
  Database20Regular,
  Delete16Regular,
  DismissCircle16Filled,
  DocumentSearch16Regular,
  DocumentSearch20Regular,
  Filter16Regular,
  History16Regular,
  PlugDisconnected16Regular,
  ScanText16Regular,
  ScanText20Regular,
  Shield16Regular,
  Shield20Regular,
  ShieldCheckmark16Regular,
  ShieldCheckmark20Regular,
  ShieldError20Regular,
  Warning16Filled,
} from "@fluentui/react-icons";
import { useCallback, useEffect, useState, type ReactElement } from "react";
import type { BackstopEvent, BackstopKey, BackstopProbe, BackstopStatus } from "../../api/client";
import { useApi } from "../../api/context";
import { announceMeChanged } from "../../shell/events";
import {
  absoluteTime,
  DataTable,
  EmptyState,
  IconTile,
  Page,
  PageSkeleton,
  Pill,
  Rise,
  Section,
  Stat,
  StatStrip,
  Td,
  Time,
  type Tone,
  Tr,
  typo,
  vt,
} from "../../ui";
import { errorText } from "../Home";

const useStyles = makeStyles({
  // Inside a flush card the table drops its own card edge (never a card in a card).
  checks: { listStyle: "none", margin: 0, padding: 0, display: "grid" },
  check: {
    display: "grid",
    gridTemplateColumns: "auto minmax(0, 1fr) auto",
    alignItems: "start",
    columnGap: "14px",
    rowGap: "12px",
    padding: "16px",
    borderTop: `1px solid ${vt.borderSubtle}`,
    ":first-child": { borderTopColor: "transparent" },
    "@media (max-width: 639px)": { gridTemplateColumns: "auto minmax(0, 1fr)" },
  },
  checkText: { display: "grid", gap: "2px", minWidth: 0 },
  name: { ...typo.itemTitle, color: vt.text1 },
  role: { ...typo.meta, color: vt.text2, maxWidth: "68ch" },
  facts: { display: "flex", gap: "4px 16px", flexWrap: "wrap", ...typo.meta, color: vt.text3, marginTop: "6px" },
  fact: { display: "inline-flex", alignItems: "flex-start", gap: "5px", minWidth: 0, "& > svg": { flexShrink: 0, marginTop: "1px" } },
  mode: { "@media (max-width: 639px)": { gridColumn: "2", gridRow: "2", justifySelf: "start" } },
  // The last service check: a well under the check's description.
  probes: {
    gridColumn: "2 / -1",
    display: "grid",
    gap: "10px",
    padding: "10px 12px",
    borderRadius: tokens.borderRadiusLarge,
    backgroundColor: vt.inset,
    border: `1px solid ${vt.borderSubtle}`,
    minWidth: 0,
  },
  probe: { display: "grid", gridTemplateColumns: "16px minmax(0, 1fr)", gap: "8px", alignItems: "start" },
  probeIcon: { marginTop: "1px", display: "inline-flex" },
  probeBody: { display: "grid", gap: "2px", minWidth: 0 },
  probeHead: { display: "flex", gap: "8px", alignItems: "baseline", flexWrap: "wrap", ...typo.meta, fontWeight: 500 },
  ms: { ...typo.label, ...typo.tabular, fontWeight: 400, color: vt.text3 },
  probeText: { ...typo.meta, color: vt.text1 },
  notChecked: { gridColumn: "2 / -1", display: "inline-flex", alignItems: "center", gap: "6px", ...typo.meta, color: vt.text3 },
  ref: { ...typo.mono, color: vt.text3, display: "block" },
  code: { ...typo.mono },
  eventCheck: { display: "grid", gridTemplateColumns: "auto minmax(0, 1fr)", gap: "10px", alignItems: "center", minWidth: 0 },
  eventText: { display: "grid", minWidth: 0 },
  stage: { ...typo.itemTitle, color: vt.text1, display: "flex", gap: "6px", alignItems: "center", flexWrap: "wrap" },
  outcome: { display: "block", color: vt.text2 },
  found: { ...typo.tabular, color: vt.text1 },
  when: { display: "inline-flex", alignItems: "center", gap: "5px", whiteSpace: "nowrap", "& > svg": { color: vt.text3 } },
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

/** Each check's own icon, so the three read apart at a glance (20px in the checks card, 16px in rows). */
const ICON: Record<BackstopKey, { icon20: ReactElement; icon16: ReactElement }> = {
  comprehend: { icon20: <ScanText20Regular />, icon16: <ScanText16Regular /> },
  guardrail: { icon20: <Shield20Regular />, icon16: <Shield16Regular /> },
  macie: { icon20: <DocumentSearch20Regular />, icon16: <DocumentSearch16Regular /> },
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

/** A caught event's tile tone: a finding needs attention, a block did its job, unavailable is neutral. */
const OUTCOME_TONE: Record<BackstopEvent["outcome"], Tone> = { finding: "danger", blocked: "warning", unavailable: "neutral" };

const SEVERITY: Record<NonNullable<BackstopEvent["severity"]>, string> = { low: "Low", medium: "Medium", high: "High" };

const PROBE: Record<BackstopProbe["state"], [Tone, string]> = {
  ok: ["success", "Passed"],
  warn: ["warning", "Warning"],
  fail: ["danger", "Failed"],
};

const PROBE_ICON: Record<BackstopProbe["state"], ReactElement> = {
  ok: <CheckmarkCircle16Filled style={{ color: vt.success }} aria-hidden />,
  warn: <Warning16Filled style={{ color: vt.warning }} aria-hidden />,
  fail: <DismissCircle16Filled style={{ color: vt.danger }} aria-hidden />,
};

const TONE_TEXT: Record<Tone, string> = {
  neutral: vt.text2,
  accent: vt.accent,
  blue: vt.info,
  purple: vt.purple,
  success: vt.success,
  warning: vt.warning,
  danger: vt.danger,
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
      announceMeChanged(); // the shell's paused banner follows a resume at once
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

  const spin = (what: Work, icon?: ReactElement) => (working === what ? <Spinner size="extra-tiny" aria-hidden /> : icon);
  const probesFor = (key: BackstopKey) =>
    (probes ?? []).filter((p) => p.key === key || (key === "guardrail" && p.key === "guardrail_india"));
  const onAws = status.backstops.filter((b) => b.mode === "aws").length;
  const offline = status.backstops.length - onAws;
  const toRemove = status.events.filter((e) => !e.purgedAt).reduce((n, e) => n + e.flaggedItems, 0);

  return (
    <Page
      title="Redaction checks"
      eyebrow={
        status.paused ? (
          <Pill tone="warning" dot>
            Paused
          </Pill>
        ) : (
          <Pill tone="success" dot>
            Running: no open findings
          </Pill>
        )
      }
      description="Extra AWS checks on top of Vanimo's own redaction: if one can't run, nothing goes through unchecked."
      info="Each check fails closed. Check the services sends made-up test text (no one's data) to each one; exporting writes today's snapshot for Macie to scan."
      actions={
        <>
          <Button
            disabled={busy}
            icon={spin("export", <CloudArrowUp16Regular />)}
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
            icon={spin("probe", <ShieldCheckmark16Regular />)}
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
            <MessageBar intent="success">
              <MessageBarBody>{note}</MessageBarBody>
            </MessageBar>
          </div>
        </Rise>
      )}

      <StatStrip label="At a glance">
        <Stat
          icon={<Cloud20Regular />}
          value={`${onAws} of ${status.backstops.length}`}
          label="Checks running on AWS"
          hint={offline ? `${offline} on the offline stand-in` : "None on the offline stand-in"}
          hintTone={offline ? "warning" : undefined}
        />
        <Stat
          icon={<ShieldError20Regular />}
          tone={status.events.length ? "warning" : "success"}
          value={status.events.length}
          label="Caught"
          hint={
            toRemove
              ? `${toRemove} flagged ${toRemove === 1 ? "item" : "items"} to remove`
              : "Types and counts only, never values"
          }
          hintTone={toRemove ? "danger" : undefined}
        />
        <Stat
          icon={<Database20Regular />}
          tone="blue"
          value={status.mySnapshot ? status.mySnapshot.items : "–"}
          label="Items in your snapshot"
          hint={
            status.mySnapshot ? (
              <>
                Exported <Time iso={status.mySnapshot.exportedAt} />
              </>
            ) : (
              "Not exported yet"
            )
          }
        />
      </StatStrip>

      <Section
        variant="card"
        flush
        icon={<ShieldCheckmark20Regular />}
        title="Checks"
        description="Each check, how it runs here, and the result of the last service check on this page."
      >
        <ul className={styles.checks} aria-label="Redaction checks">
          {status.backstops.map((b) => {
            const results = probesFor(b.key);
            return (
              <li key={b.key} className={styles.check}>
                <IconTile icon={ICON[b.key].icon20} tone="accent" size={36} />
                <div className={styles.checkText}>
                  <span className={styles.name}>{NAMES[b.key]}</span>
                  <span className={styles.role}>{ROLE[b.key]}</span>
                  <span className={styles.facts}>
                    <span className={styles.fact}>
                      {b.mode === "aws" ? <Cloud16Regular aria-hidden /> : <PlugDisconnected16Regular aria-hidden />}
                      {b.label}
                    </span>
                    {b.key === "comprehend" && (
                      <span className={styles.fact}>
                        <Filter16Regular aria-hidden />
                        {status.comprehendScope === "all" ? "Checks every item" : "Checks only items with identifiers"}
                      </span>
                    )}
                    {b.key === "macie" && (
                      <span className={styles.fact}>
                        <History16Regular aria-hidden />
                        Snapshots rewritten every {status.snapshotEveryHours} hours
                      </span>
                    )}
                  </span>
                </div>
                <span className={styles.mode}>
                  {b.mode === "aws" ? (
                    <Pill icon={<Cloud16Regular />}>AWS</Pill>
                  ) : (
                    <Pill icon={<PlugDisconnected16Regular />}>Offline stand-in</Pill>
                  )}
                </span>
                {results.length === 0 ? (
                  <span className={styles.notChecked}>
                    <Circle16Regular aria-hidden />
                    Not checked yet
                  </span>
                ) : (
                  <div className={styles.probes} aria-label={`Last service check: ${NAMES[b.key]}`} role="group">
                    {results.map((p) => {
                      const [tone, word] = PROBE[p.state];
                      return (
                        <div key={p.key} className={styles.probe}>
                          <span className={styles.probeIcon}>{PROBE_ICON[p.state]}</span>
                          <span className={styles.probeBody}>
                            <span className={styles.probeHead}>
                              <span style={{ color: TONE_TEXT[tone] }}>
                                {p.key === "guardrail_india" ? `${word} · Indian IDs` : word}
                              </span>
                              <span className={styles.ms}>{p.ms} ms</span>
                            </span>
                            <span className={styles.probeText}>{probeText(p)}</span>
                          </span>
                        </div>
                      );
                    })}
                  </div>
                )}
              </li>
            );
          })}
        </ul>
      </Section>

      <Section
        variant="card"
        flush
        icon={<ShieldError20Regular />}
        title="What the checks caught"
        count={status.events.length > 0 ? status.events.length : undefined}
        description="Types and counts only: never the values themselves."
      >
        {status.events.length === 0 ? (
          <EmptyState icon={<ShieldCheckmark20Regular />} tone="success" title="Nothing caught yet" center>
            When a check blocks something or finds personal details, the type and count appear here.
          </EmptyState>
        ) : (
          <DataTable
            label="Caught"
            embedded
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
                  <span className={styles.when}>
                    <Clock16Regular aria-hidden />
                    <Time iso={e.at} />
                  </span>
                </Td>
                <Td label="Check">
                  <span className={styles.eventCheck}>
                    <IconTile icon={ICON[e.source].icon16} tone={OUTCOME_TONE[e.outcome]} size={28} />
                    <span className={styles.eventText}>
                      <span className={styles.stage}>
                        {NAMES[e.source]}
                        {e.severity && (
                          <Pill tone={e.severity === "high" ? "danger" : "warning"}>{SEVERITY[e.severity]} severity</Pill>
                        )}
                      </span>
                      <span className={styles.outcome}>
                        {STAGE[e.stage]} · {OUTCOME[e.outcome] ?? e.outcome}
                      </span>
                      <span className={styles.ref}>{e.ref}</span>
                    </span>
                  </span>
                </Td>
                <Td label="Found">
                  <span className={styles.found}>{kindsText(e.kinds)}</span>
                </Td>
                <Td label="User" mono>
                  {e.user ?? "—"}
                </Td>
                <Td actions>
                  {e.purgedAt ? (
                    <Pill tone="success" icon={<CheckmarkCircle16Regular />}>
                      Removed
                    </Pill>
                  ) : (
                    e.flaggedItems > 0 && (
                      <Button
                        size="small"
                        disabled={busy}
                        icon={spin(`purge-${e.id}`, <Delete16Regular />)}
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
