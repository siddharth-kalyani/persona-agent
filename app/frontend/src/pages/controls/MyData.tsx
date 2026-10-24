import { Button, makeStyles, MessageBar, MessageBarBody, Spinner, tokens } from "@fluentui/react-components";
import {
  ArrowClockwise16Regular,
  ArrowRight16Regular,
  ArrowUndo16Regular,
  Building16Regular,
  Clock16Regular,
  Delete16Regular,
  DocumentSearch16Regular,
  EyeOff16Regular,
  Prohibited16Regular,
  Receipt16Regular,
  Receipt20Regular,
  Warning16Regular,
} from "@fluentui/react-icons";
import { useCallback, useEffect, useState, type ReactElement } from "react";
import { useNavigate } from "react-router-dom";
import type { ControlsStatus, Receipt } from "../../api/client";
import { useApi } from "../../api/context";
import {
  EmptyState,
  IconTile,
  List,
  ListRow,
  Page,
  PageSkeleton,
  Pill,
  Section,
  SettingList,
  SettingRow,
  Time,
  typo,
  vt,
  type Tone,
} from "../../ui";
import { errorText } from "../Home";
import { scanSummary } from "./Setup";
import { SourcesReview } from "./SourcesReview";

const useStyles = makeStyles({
  failed: { color: vt.danger },
  deleteCard: {
    padding: "4px 16px",
    backgroundColor: tokens.colorNeutralBackground1,
    border: `1px solid ${vt.border}`,
    borderRadius: tokens.borderRadiusXLarge,
    boxShadow: vt.shadowCard,
  },
  listed: {
    display: "inline-flex",
    alignItems: "center",
    gap: "6px",
    ...typo.meta,
    color: vt.text3,
    whiteSpace: "nowrap",
    "& > svg": { flexShrink: 0 },
  },
  receiptMeta: { display: "inline-flex", gap: "4px 12px", alignItems: "center", flexWrap: "wrap" },
  metaItem: { display: "inline-flex", alignItems: "center", gap: "4px", whiteSpace: "nowrap", "& > svg": { flexShrink: 0 } },
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

/** What kind of change a receipt is for, as the row's icon. */
const REASON_ICON: Record<string, ReactElement> = {
  exclusion_added: <EyeOff16Regular />,
  exclusion_removed: <ArrowUndo16Regular />,
  term_added: <Prohibited16Regular />,
  term_removed: <Prohibited16Regular />,
  tenant_policy_changed: <Building16Regular />,
  learning_deleted: <Delete16Regular />,
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
      description="What Vanimo may learn from and the words it must never send to an AI model."
      info="Change any of it at any time. Every change gets a receipt below, with what was deleted or re-masked."
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

      <Section
        title="Sources and never-send words"
        icon={<DocumentSearch16Regular />}
        description={
          // Text only (it sits in a paragraph); the Refresh button in the header shows the spinner.
          <span role="status" className={scan?.status === "failed" ? styles.failed : undefined}>
            {!scan
              ? "No sources listed yet."
              : scanning
                ? "Listing your sources again (headers only)…"
                : scan.status === "failed"
                  ? "The last refresh didn't finish. Refresh sources to try again."
                  : `Sources: ${scanSummary(scan)}.`}
          </span>
        }
        actions={
          scan?.status === "done" &&
          scan.finishedAt && (
            <span className={styles.listed}>
              <Clock16Regular aria-hidden />
              <span>
                Headers listed <Time iso={scan.finishedAt} inSentence />
              </span>
            </span>
          )
        }
      >
        <SourcesReview onChange={() => setTimeout(() => void refresh(), 500)} counts={scan?.counts} />
      </Section>

      <Section
        variant="card"
        flush
        icon={<Receipt20Regular />}
        title="Receipts"
        count={receipts.length > 0 ? receipts.length : undefined}
        description="Exclusions apply within a minute; deleting what was learned takes up to 24 hours."
      >
        {receipts.length === 0 ? (
          <EmptyState icon={<Receipt20Regular />} title="No changes yet" center>
            When you exclude a source or add a never-send word, a receipt appears here with what was deleted or re-masked.
          </EmptyState>
        ) : (
          <List label="Receipts">
            {receipts.map((r) => {
              const [tone, word] = RECEIPT_STATE[r.status] ?? (["neutral", r.status] as [Tone, string]);
              const detail = receiptDetail(r);
              return (
                <ListRow
                  key={r.id}
                  wrap
                  leading={<IconTile icon={REASON_ICON[r.reason] ?? <Receipt16Regular />} size={32} />}
                  title={REASONS[r.reason] ?? r.reason}
                  meta={
                    <span className={styles.receiptMeta}>
                      <span className={styles.metaItem}>
                        <Clock16Regular aria-hidden />
                        <Time iso={r.requestedAt} />
                      </span>
                      {detail && <span>{detail}</span>}
                    </span>
                  }
                  trailing={
                    r.needsAttention ? (
                      <span className={styles.receiptTrailing}>
                        <Pill tone="warning" icon={<Warning16Regular />}>
                          Needs attention
                        </Pill>
                        <Button
                          size="small"
                          icon={<ArrowClockwise16Regular />}
                          onClick={() => void api.retryReceipt(r.id).then(refresh, (e) => setError(errorText(e)))}
                        >
                          Retry
                        </Button>
                      </span>
                    ) : (
                      <Pill tone={tone} dot>
                        {word}
                      </Pill>
                    )
                  }
                />
              );
            })}
          </List>
        )}
      </Section>

      <Section icon={<Delete16Regular />} title="Delete what Vanimo learned">
        <SettingList className={styles.deleteCard}>
          <SettingRow
            icon={<Delete16Regular />}
            label="Delete everything learned from your messages"
            description="Every stored message, name token, style card and evaluation is deleted, and you get a receipt here. Your persona settings and these controls stay. You confirm on the Learning page."
          >
            <Button icon={<ArrowRight16Regular />} iconPosition="after" onClick={() => navigate("/learning")}>
              Go to Learning
            </Button>
          </SettingRow>
        </SettingList>
      </Section>
    </Page>
  );
}
