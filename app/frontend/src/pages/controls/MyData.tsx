import {
  Button,
  Caption1,
  Card,
  CardHeader,
  makeStyles,
  Spinner,
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
import type { ControlsStatus, Receipt } from "../../api/client";
import { useApi } from "../../api/context";
import { scanSummary } from "./Setup";
import { SourcesReview } from "./SourcesReview";

const useStyles = makeStyles({
  stack: { display: "grid", gap: tokens.spacingVerticalL },
  row: { display: "flex", gap: tokens.spacingHorizontalM, alignItems: "center", flexWrap: "wrap" },
  muted: { color: tokens.colorNeutralForeground3 },
});

const REASONS: Record<string, string> = {
  exclusion_added: "Exclusion added: derived data deleted",
  exclusion_removed: "Exclusion removed: source used again from now on",
  term_added: "Never-send word added: stored text re-masked",
  term_removed: "Never-send word removed",
  tenant_policy_changed: "Your organisation changed its rules",
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
  const [status, setStatus] = useState<ControlsStatus | null>(null);
  const [receipts, setReceipts] = useState<Receipt[]>([]);

  const refresh = useCallback(async () => {
    const [s, r] = await Promise.all([api.controlsStatus(), api.receipts()]);
    setStatus(s);
    setReceipts(r);
  }, [api]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  if (!status) return <Spinner label="Loading…" />;

  return (
    <div className={styles.stack}>
      <Title3 as="h2">My data controls</Title3>
      <div className={styles.row}>
        <Caption1 className={styles.muted}>
          {status.scan ? `Sources: ${scanSummary(status.scan)}.` : "No sources listed yet."}
        </Caption1>
        <Button size="small" onClick={() => void api.startScan().then(setStatus)}>
          Refresh sources
        </Button>
      </div>
      <SourcesReview onChange={() => setTimeout(() => void refresh(), 500)} />
      <Card>
        <CardHeader
          header={<Text weight="semibold">Receipts</Text>}
          description={<Caption1>Exclusions apply within a minute; deleting what was learned takes up to 24 hours.</Caption1>}
        />
        <Table size="small" aria-label="Receipts">
          <TableHeader>
            <TableRow>
              <TableHeaderCell>When</TableHeaderCell>
              <TableHeaderCell>What</TableHeaderCell>
              <TableHeaderCell>Status</TableHeaderCell>
            </TableRow>
          </TableHeader>
          <TableBody>
            {receipts.map((r) => (
              <TableRow key={r.id}>
                <TableCell>{new Date(r.requestedAt).toLocaleString()}</TableCell>
                <TableCell>
                  {REASONS[r.reason] ?? r.reason}
                  {receiptDetail(r) && <Caption1 className={styles.muted}> · {receiptDetail(r)}</Caption1>}
                </TableCell>
                <TableCell>{r.status}</TableCell>
              </TableRow>
            ))}
            {receipts.length === 0 && (
              <TableRow>
                <TableCell colSpan={3}>No changes yet.</TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
      </Card>
    </div>
  );
}
