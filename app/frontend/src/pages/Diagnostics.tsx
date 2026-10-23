import { Button, Link, makeStyles, MessageBar, MessageBarBody, Spinner } from "@fluentui/react-components";
import { Open16Regular } from "@fluentui/react-icons";
import { useState } from "react";
import type { CheckResult, HeaderPass, LatencyResult, Outcome } from "../api/client";
import { useApi } from "../api/context";
import { DataTable, KeyValueList, Page, Rise, Section, StatusDot, Td, type Tone, Tr, typo, vt } from "../ui";
import { errorText } from "./Home";

const useStyles = makeStyles({
  quiet: { ...typo.meta, color: vt.text3, margin: 0 },
  results: { display: "grid", gap: "16px", minWidth: 0 },
  mono: { ...typo.mono, color: vt.text1 },
  details: { ...typo.mono, color: vt.text2, overflowWrap: "anywhere" },
  detail: { marginRight: "8px" },
  number: { ...typo.tabular, color: vt.text1, whiteSpace: "nowrap" },
  unit: { color: vt.text3 },
  probe: { display: "flex", gap: "8px 16px", alignItems: "center", flexWrap: "wrap" },
});

const OUTCOME: Record<Outcome, [Tone, string]> = {
  ok: ["success", "OK"],
  warn: ["warning", "Warning"],
  fail: ["danger", "Failed"],
  skipped: ["neutral", "Skipped"],
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

  const spin = (label: string) => (busy === label ? <Spinner size="extra-tiny" aria-hidden /> : undefined);
  const ms = (v: number | null) =>
    v === null ? (
      <span className={styles.unit}>—</span>
    ) : (
      <>
        {v}
        <span className={styles.unit}> ms</span>
      </>
    );

  return (
    <Page
      title="Diagnostics"
      description="Week-1 spike checks for Microsoft 365, Claude on Bedrock and the Outlook Drafts folder. Every result is counts and status codes, never content."
    >
      {error && (
        <MessageBar intent="error">
          <MessageBarBody>{error}</MessageBarBody>
        </MessageBar>
      )}

      <Section
        title="Microsoft 365 checks"
        description="Profile, sent-mail headers and delta, chat roster, calendar, meeting transcripts. Headers and counts only — no message text is read (that waits for the review step in M1)."
        actions={
          <>
            <Button disabled={!!busy} icon={spin("pass")} onClick={() => run("pass", () => api.headerPass(), setHeaderPass)}>
              {busy === "pass" ? "Timing (up to 45 s)…" : "Time the header pass"}
            </Button>
            <Button
              appearance="primary"
              disabled={!!busy}
              icon={spin("checks")}
              onClick={() => run("checks", () => api.runDiagnostics(), (r) => setChecks(r.results))}
            >
              {busy === "checks" ? "Running…" : "Run checks"}
            </Button>
          </>
        }
      >
        {!checks && !headerPass && <p className={styles.quiet}>Not run yet.</p>}
        {(checks || headerPass) && (
          <Rise visible appear>
            <div className={styles.results}>
              {headerPass && (
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
              )}
              {checks && (
                <DataTable
                  label="Check results"
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
                          <StatusDot tone={tone}>{word}</StatusDot>
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
        title="Claude on Bedrock latency"
        description="Five short synthetic prompts per model from this region; time to first token (min / median / max)."
        actions={
          <Button disabled={!!busy} icon={spin("latency")} onClick={() => run("latency", () => api.bedrockLatency(5), setLatency)}>
            {busy === "latency" ? "Measuring…" : "Measure latency"}
          </Button>
        }
      >
        {!latency ? (
          <p className={styles.quiet}>Not measured yet.</p>
        ) : (
          <Rise visible appear>
            <div>
              <DataTable
                label="Latency results"
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
                      {l.errors ? `${l.errors} (${l.errorTypes.join(", ")})` : "0"}
                    </Td>
                  </Tr>
                ))}
              </DataTable>
            </div>
          </Rise>
        )}
      </Section>

      <Section
        title="Drafts folder test"
        description='Creates a reply draft to your newest inbox email, marked "safe to delete". Check that it appears in Outlook on your phone, then delete it here.'
        actions={
          <Button disabled={!!busy || !!draft} icon={spin("draft")} onClick={() => run("draft", () => api.createDraftProbe(), setDraft)}>
            Create test draft
          </Button>
        }
      >
        {!draft ? (
          <p className={styles.quiet}>No test draft.</p>
        ) : (
          <Rise visible appear>
            <div className={styles.results}>
              <KeyValueList items={[["Draft ID", <span key="id" className={styles.details}>{draft.draftId}</span>]]} />
              <div className={styles.probe}>
                {draft.webLink && (
                  <Link href={draft.webLink} target="_blank" rel="noreferrer">
                    Open in Outlook on the web <Open16Regular aria-hidden style={{ verticalAlign: "-3px" }} />
                  </Link>
                )}
                <Button
                  disabled={!!busy}
                  icon={spin("delete")}
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
