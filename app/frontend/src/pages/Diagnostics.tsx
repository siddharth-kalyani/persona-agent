import { Button, Link, makeStyles, mergeClasses, MessageBar, MessageBarBody, Spinner } from "@fluentui/react-components";
import {
  Add16Regular,
  CheckmarkCircle16Filled,
  Circle16Filled,
  Delete16Regular,
  DismissCircle16Filled,
  Drafts20Regular,
  Open16Regular,
  Play16Regular,
  PlugConnected20Regular,
  Timer16Regular,
  Timer20Regular,
  Warning16Filled,
} from "@fluentui/react-icons";
import { useState, type ReactElement } from "react";
import type { CheckResult, HeaderPass, LatencyResult, Outcome } from "../api/client";
import { useApi } from "../api/context";
import { DataTable, EmptyState, KeyValueList, Page, Pill, Rise, Section, Td, type Tone, Tr, typo, vt } from "../ui";
import { errorText } from "./Home";

const useStyles = makeStyles({
  // Inside a flush card the table drops its own card edge (never a card in a card).
  results: { display: "grid", minWidth: 0 },
  well: { padding: "4px 16px 8px", borderBottom: `1px solid ${vt.borderSubtle}` },
  wellLast: { borderBottom: "none" },
  mono: { ...typo.mono, color: vt.text1 },
  details: { ...typo.mono, color: vt.text2, overflowWrap: "anywhere" },
  detail: { marginRight: "8px" },
  number: { ...typo.tabular, color: vt.text1, whiteSpace: "nowrap" },
  unit: { color: vt.text3 },
  outcome: { display: "inline-flex", alignItems: "center", gap: "6px", ...typo.meta, fontWeight: 500, whiteSpace: "nowrap" },
  probe: { display: "flex", gap: "8px 16px", alignItems: "center", flexWrap: "wrap", padding: "4px 16px 16px" },
  link: { display: "inline-flex", alignItems: "center", gap: "6px" },
  summary: { display: "flex", alignItems: "center", gap: "6px", flexWrap: "wrap", padding: "12px 16px" },
  summaryNote: { ...typo.meta, ...typo.tabular, color: vt.text3, marginLeft: "4px" },
});

const OUTCOME: Record<Outcome, [Tone, string]> = {
  ok: ["success", "OK"],
  warn: ["warning", "Warning"],
  fail: ["danger", "Failed"],
  skipped: ["neutral", "Skipped"],
};

/** Each outcome's glyph in its colour; the word beside it says the same. */
const OUTCOME_ICON: Record<Outcome, ReactElement> = {
  ok: <CheckmarkCircle16Filled style={{ color: vt.success }} aria-hidden />,
  warn: <Warning16Filled style={{ color: vt.warning }} aria-hidden />,
  fail: <DismissCircle16Filled style={{ color: vt.danger }} aria-hidden />,
  skipped: <Circle16Filled style={{ color: vt.dot }} aria-hidden />,
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

  const spin = (label: string, icon?: ReactElement) => (busy === label ? <Spinner size="extra-tiny" aria-hidden /> : icon);
  const ms = (v: number | null) =>
    v === null ? (
      <span className={styles.unit}>—</span>
    ) : (
      <>
        {v}
        <span className={styles.unit}> ms</span>
      </>
    );
  const summary = checks
    ? (["ok", "warn", "fail"] as const)
        .map((o) => [o, checks.filter((c) => c.outcome === o).length] as const)
        .filter(([, n]) => n > 0)
    : [];

  return (
    <Page
      title="Diagnostics"
      description="Check that Microsoft 365, Claude on Bedrock and the Outlook Drafts folder work for your organisation."
      info="Every result is counts and status codes, never content."
    >
      {error && (
        <MessageBar intent="error">
          <MessageBarBody>{error}</MessageBarBody>
        </MessageBar>
      )}

      <Section
        variant="card"
        flush
        icon={<PlugConnected20Regular />}
        title="Microsoft 365 checks"
        description="Headers and counts only: no message text is read."
        info="Profile, sent-mail headers and delta, chat roster, calendar, meeting transcripts. Message text waits for the review step in M1."
        actions={
          <>
            <Button disabled={!!busy} icon={spin("pass", <Timer16Regular />)} onClick={() => run("pass", () => api.headerPass(), setHeaderPass)}>
              {busy === "pass" ? "Timing (up to 45 s)…" : "Time the header pass"}
            </Button>
            <Button
              appearance="primary"
              disabled={!!busy}
              icon={spin("checks", <Play16Regular />)}
              onClick={() => run("checks", () => api.runDiagnostics(), (r) => setChecks(r.results))}
            >
              {busy === "checks" ? "Running…" : "Run checks"}
            </Button>
          </>
        }
      >
        {!checks && !headerPass && (
          <EmptyState icon={<PlugConnected20Regular />} title="Not run yet" center>
            Run the checks, or time how long listing your sent-mail and chat headers takes.
          </EmptyState>
        )}
        {(checks || headerPass) && (
          <Rise visible appear>
            <div className={styles.results}>
              {headerPass && (
                <div className={mergeClasses(styles.well, !checks && styles.wellLast)}>
                  <KeyValueList
                    items={[
                      [
                        "Sent headers",
                        <span key="s" className={styles.number}>
                          {headerPass.sentItems} in {headerPass.sentPages} pages ·{" "}
                          {headerPass.sentFinished ? "complete" : "not finished"}
                        </span>,
                      ],
                      [
                        "Chats",
                        <span key="c" className={styles.number}>
                          {headerPass.chats} · {headerPass.chatsFinished ? "complete" : "not finished"}
                        </span>,
                      ],
                      ["Elapsed", <span key="e" className={styles.number}>{Math.round(headerPass.elapsedMs / 1000)} s</span>],
                      [
                        "Rate",
                        <span key="r" className={styles.number}>
                          {headerPass.itemsPerSecond ?? "—"} headers/s
                        </span>,
                      ],
                    ]}
                  />
                </div>
              )}
              {checks && summary.length > 0 && (
                <div className={styles.summary} aria-label="Check results summary" role="group">
                  {summary.map(([o, n]) => (
                    <Pill key={o} tone={OUTCOME[o][0]} dot>
                      {n} {OUTCOME[o][1]}
                    </Pill>
                  ))}
                  <span className={styles.summaryNote}>of {checks.length} checks</span>
                </div>
              )}
              {checks && (
                <DataTable
                  label="Check results"
                  embedded
                  columns={[{ label: "Check" }, { label: "Result" }, { label: "Time", align: "end" }, { label: "Details" }]}
                >
                  {checks.map((c) => {
                    const [tone, word] = OUTCOME[c.outcome];
                    return (
                      <Tr key={c.check}>
                        <Td dense primary>
                          <span className={styles.mono}>{c.check}</span>
                        </Td>
                        <Td dense label="Result">
                          <span className={styles.outcome} style={{ color: TONE_TEXT[tone] }}>
                            {OUTCOME_ICON[c.outcome]}
                            {word}
                          </span>
                        </Td>
                        <Td dense label="Time" align="end" numeric>
                          {ms(Math.round(c.durationMs))}
                        </Td>
                        <Td dense label="Details">
                          <span className={styles.details}>
                            {Object.entries(c.details).map(([k, v]) => (
                              <span key={k} className={styles.detail}>
                                {k}={String(v)}{" "}
                              </span>
                            ))}
                          </span>
                        </Td>
                      </Tr>
                    );
                  })}
                </DataTable>
              )}
            </div>
          </Rise>
        )}
      </Section>

      <Section
        variant="card"
        flush
        icon={<Timer20Regular />}
        title="Claude on Bedrock latency"
        description="Time to first token (min / median / max) from this region."
        info="Five short synthetic prompts per model."
        actions={
          <Button disabled={!!busy} icon={spin("latency", <Timer16Regular />)} onClick={() => run("latency", () => api.bedrockLatency(5), setLatency)}>
            {busy === "latency" ? "Measuring…" : "Measure latency"}
          </Button>
        }
      >
        {!latency ? (
          <EmptyState icon={<Timer20Regular />} title="Not measured yet" center>
            Five short synthetic prompts per model; nothing of yours is sent.
          </EmptyState>
        ) : (
          <Rise visible appear>
            <div>
              <DataTable
                label="Latency results"
                embedded
                columns={[
                  { label: "Model" },
                  { label: "First token min / median / max", align: "end" },
                  { label: "Total median", align: "end" },
                  { label: "Errors", align: "end" },
                ]}
              >
                {latency.map((l) => (
                  <Tr key={l.modelId}>
                    <Td dense primary>
                      <span className={styles.mono}>{l.modelId}</span>
                    </Td>
                    <Td dense label="First token" align="end" numeric>
                      {l.ttftMinMs ?? "—"} / {l.ttftMedianMs ?? "—"} / {l.ttftMaxMs ?? "—"}
                      <span className={styles.unit}> ms</span>
                    </Td>
                    <Td dense label="Total median" align="end" numeric>
                      {ms(l.totalMedianMs)}
                    </Td>
                    <Td dense label="Errors" align="end" numeric>
                      {l.errors ? (
                        <Pill tone="danger" dot>
                          {`${l.errors} (${l.errorTypes.join(", ")})`}
                        </Pill>
                      ) : (
                        "0"
                      )}
                    </Td>
                  </Tr>
                ))}
              </DataTable>
            </div>
          </Rise>
        )}
      </Section>

      <Section
        variant="card"
        flush
        icon={<Drafts20Regular />}
        title="Drafts folder test"
        description='Creates a reply draft to your newest inbox email, marked "safe to delete".'
        actions={
          <Button disabled={!!busy || !!draft} icon={spin("draft", <Add16Regular />)} onClick={() => run("draft", () => api.createDraftProbe(), setDraft)}>
            Create test draft
          </Button>
        }
      >
        {!draft ? (
          <EmptyState icon={<Drafts20Regular />} title="No test draft" center>
            Check that it appears in Outlook on your phone, then delete it here.
          </EmptyState>
        ) : (
          <Rise visible appear>
            <div className={styles.results}>
              <div className={mergeClasses(styles.well, styles.wellLast)}>
                <KeyValueList items={[["Draft ID", <span key="id" className={styles.details}>{draft.draftId}</span>]]} />
              </div>
              <div className={styles.probe}>
                {draft.webLink && (
                  <Link className={styles.link} href={draft.webLink} target="_blank" rel="noreferrer">
                    Open in Outlook on the web <Open16Regular aria-hidden />
                  </Link>
                )}
                <Button
                  disabled={!!busy}
                  icon={spin("delete", <Delete16Regular />)}
                  onClick={() => run("delete", () => api.deleteDraftProbe(draft.draftId), () => setDraft(null))}
                >
                  Delete test draft
                </Button>
              </div>
            </div>
          </Rise>
        )}
      </Section>
    </Page>
  );
}
