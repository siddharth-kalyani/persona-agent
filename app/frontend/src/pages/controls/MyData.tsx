import { Button, makeStyles, MessageBar, MessageBarBody, Spinner } from "@fluentui/react-components";
import { ArrowClockwise16Regular, ArrowRight16Regular, Receipt20Regular } from "@fluentui/react-icons";
import { useCallback, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import type { ControlsStatus, Receipt } from "../../api/client";
import { useApi } from "../../api/context";
import {
  EmptyState,
  List,
  ListRow,
  Page,
  PageSkeleton,
  Pill,
  Section,
  SettingList,
  SettingRow,
  StatusDot,
  Time,
  typo,
  vt,
  type Tone,
} from "../../ui";
import { errorText } from "../Home";
import { scanSummary } from "./Setup";
import { SourcesReview } from "./SourcesReview";

const useStyles = makeStyles({
  status: { display: "flex", alignItems: "center", gap: "6px 12px", flexWrap: "wrap", ...typo.meta, color: vt.text2 },
  running: { display: "inline-flex", alignItems: "center", gap: "8px" },
  statusTime: { color: vt.text3 },
  receiptMeta: { display: "inline-flex", gap: "6px", alignItems: "baseline", flexWrap: "wrap" },
  receiptTrailing: { display: "flex", alignItems: "center", gap: "8px", flexWrap: "wrap", justifyContent: "flex-end" },
});

const REASONS: Record<string, string> = {
  exclusion_added: "Exclusion added: derived data deleted",
  exclusion_removed: "Exclusion removed: source used again from now on",
  term_added: "Never-send word added: stored text re-masked",
  term_removed: "Never-send word removed",
  tenant_policy_changed: "Your organisation changed its rules",
  learning_deleted: "You deleted what Vanimo learned",
};

/** A receipt's job state in words, with a dot that is never the only signal. */
const RECEIPT_STATE: Record<string, [Tone, string]> = {
  done: ["success", "Done"],
  running: ["accent", "In progress"],
  pending: ["neutral", "Waiting"],
  queued: ["neutral", "Waiting"],
  failed: ["danger", "Failed"],
};

export function receiptDetail(r: Receipt): string {
  const parts = Object.entries(r.counts)
    .filter(([, v]) => typeof v === "number")
    .map(([k, v]) => `${v} ${k.replaceAll("_", " ")}`);
  return parts.join(", ");
}

/** My data controls: change exclusions and never-send words any time; see receipts. */
export function MyData() {
  const styles = useStyles();
  const api = useApi();
  const navigate = useNavigate();
  const [status, setStatus] = useState<ControlsStatus | null>(null);
  const [receipts, setReceipts] = useState<Receipt[]>([]);

  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    try {
      const [s, r] = await Promise.all([api.controlsStatus(), api.receipts()]);
      setStatus(s);
      setReceipts(r);
    } catch (e) {
      setError(errorText(e));
    }
  }, [api]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  // Follow a running rescan until it finishes.
  useEffect(() => {
    if (status?.scan?.status !== "running") return;
    const timer = setInterval(() => void refresh(), 2000);
    return () => clearInterval(timer);
  }, [status?.scan?.status, refresh]);

  if (!status)
    return error ? (
      <Page title="My data">
        <MessageBar intent="error">
          <MessageBarBody>{error}</MessageBarBody>
        </MessageBar>
      </Page>
    ) : (
      <PageSkeleton label="Loading…" />
    );

  const scan = status.scan;
  const scanning = scan?.status === "running";

  return (
    <Page
      title="My data"
      eyebrow={scan ? <Pill>{scan.sourceKind === "sample" ? "Sample workspace" : "Microsoft 365"}</Pill> : undefined}
      description="What Vanimo may learn from, the words it must never send to an AI model, and a receipt for every change. Change any of it at any time."
      actions={
        <Button
          icon={scanning ? <Spinner size="extra-tiny" aria-hidden /> : <ArrowClockwise16Regular />}
          disabled={scanning}
          onClick={() => void api.startScan().then(setStatus, (e) => setError(errorText(e)))}
        >
          {scanning ? "Refreshing…" : "Refresh sources"}
        </Button>
      }
    >
      {error && (
        <MessageBar intent="error">
          <MessageBarBody>{error}</MessageBarBody>
        </MessageBar>
      )}

      <Section title="Sources and never-send words">
        <div className={styles.status} role="status">
          {!scan ? (
            <StatusDot>No sources listed yet.</StatusDot>
          ) : scanning ? (
            <span className={styles.running}>
              <Spinner size="extra-tiny" aria-hidden />
              Listing your sources again (headers only)…
            </span>
          ) : scan.status === "failed" ? (
            <StatusDot tone="danger">The last refresh didn't finish. Refresh sources to try again.</StatusDot>
          ) : (
            <>
              <StatusDot tone="success">Sources: {scanSummary(scan)}.</StatusDot>
              {scan.finishedAt && (
                <span className={styles.statusTime}>
                  Headers listed <Time iso={scan.finishedAt} />
                </span>
              )}
            </>
          )}
        </div>
        <SourcesReview onChange={() => setTimeout(() => void refresh(), 500)} counts={scan?.counts} />
      </Section>

      <Section
        title="Receipts"
        description="Exclusions apply within a minute; deleting what was learned takes up to 24 hours."
      >
        {receipts.length === 0 ? (
          <EmptyState icon={<Receipt20Regular />} title="No changes yet">
            When you exclude a source or add a never-send word, a receipt appears here with what was deleted or re-masked.
          </EmptyState>
        ) : (
          <List bordered label="Receipts">
            {receipts.map((r) => {
              const [tone, word] = RECEIPT_STATE[r.status] ?? (["neutral", r.status] as [Tone, string]);
              const detail = receiptDetail(r);
              return (
                <ListRow
                  key={r.id}
                  wrap
                  title={REASONS[r.reason] ?? r.reason}
                  meta={
                    <span className={styles.receiptMeta}>
                      <Time iso={r.requestedAt} />
                      {detail && <span>· {detail}</span>}
                    </span>
                  }
                  trailing={
                    r.needsAttention ? (
                      <span className={styles.receiptTrailing}>
                        <Pill tone="warning">Needs attention</Pill>
                        <Button
                          size="small"
                          onClick={() => void api.retryReceipt(r.id).then(refresh, (e) => setError(errorText(e)))}
                        >
                          Retry
                        </Button>
                      </span>
                    ) : (
                      <StatusDot tone={tone}>{word}</StatusDot>
                    )
                  }
                />
              );
            })}
          </List>
        )}
      </Section>

      <Section title="Delete what Vanimo learned">
        <SettingList>
          <SettingRow
            label="Delete everything learned from your messages"
            description="Every stored message, name token, style card and evaluation is deleted, and you get a receipt here. Your persona settings and these controls stay. You confirm on the Learning page."
          >
            <Button appearance="subtle" icon={<ArrowRight16Regular />} iconPosition="after" onClick={() => navigate("/learning")}>
              Go to Learning
            </Button>
          </SettingRow>
        </SettingList>
      </Section>
    </Page>
  );
}
