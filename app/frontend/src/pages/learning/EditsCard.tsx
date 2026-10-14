/** Learned from your edits (M4): how often you send Vanimo's drafts unchanged, and the style rules
 * learned from the changes you make, for you to keep or reject. A rule is proposed only after it
 * was seen in at least 3 of your edits and your own sent mail agrees with it. */
import { Badge, Button, Caption1, Card, CardHeader, makeStyles, Text, tokens } from "@fluentui/react-components";
import { useCallback, useEffect, useState } from "react";
import type { EditSummary, LearnedRule } from "../../api/client";
import { useApi } from "../../api/context";
import { draftErrorText } from "../../drafting/DraftView";
import { formLabel } from "./Persona";

const useStyles = makeStyles({
  stack: { display: "grid", gap: tokens.spacingVerticalS },
  row: { display: "flex", gap: tokens.spacingHorizontalS, alignItems: "center", flexWrap: "wrap" },
  muted: { color: tokens.colorNeutralForeground3 },
});

const AUDIENCE: Record<string, string> = {
  manager: "your manager",
  report: "your direct reports",
  peer: "colleagues",
  external: "people outside your organisation",
  personal: "personal contacts",
  "*": "everyone",
};

/** The rule in plain words; greeting and sign-off forms shown with readable placeholders. */
export function ruleLabel(r: LearnedRule): string {
  return r.kind === "greeting" || r.kind === "sign_off" ? formLabel(r.text) : r.text;
}

function pct(v: number | undefined): string {
  return v === undefined ? "—" : `${Math.round(v * 100)}%`;
}

export function EditsCard() {
  const styles = useStyles();
  const api = useApi();
  const [rules, setRules] = useState<LearnedRule[]>([]);
  const [summary, setSummary] = useState<EditSummary | null>(null);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    try {
      const [r, s] = await Promise.all([api.learnedRules(), api.editSummary()]);
      setRules(r);
      setSummary(s);
    } catch (e) {
      setError(draftErrorText(e));
    }
  }, [api]);

  useEffect(() => {
    // Match drafts to sent mail first (skipped if it ran in the last minute, or before your review).
    void api.syncEdits().catch(() => undefined).finally(() => void refresh());
  }, [api, refresh]);

  async function decide(id: string, decision: "keep" | "reject") {
    try {
      await api.decideRule(id, decision);
      await refresh();
    } catch (e) {
      setError(draftErrorText(e));
    }
  }

  const toConfirm = rules.filter((r) => r.status === "active");
  const kept = rules.filter((r) => r.status === "confirmed");
  const learning = rules.filter((r) => r.status === "candidate");

  return (
    <Card>
      <CardHeader
        header={<Text weight="semibold">Learned from your edits</Text>}
        description={
          <Caption1>
            When you send a draft Vanimo wrote, it compares the draft with what you actually sent. Only the result and
            the kind of change are kept, never your sent text.
          </Caption1>
        }
      />
      <div className={styles.stack}>
        {error && <Caption1>{error}</Caption1>}
        {summary && summary.matched > 0 ? (
          <Caption1>
            {summary.matched} drafts sent · <b>{pct(summary.sendWithoutEditRate)} sent without edits</b> (5% or less
            changed) · {pct(summary.lightEditRate)} with at most light edits
          </Caption1>
        ) : (
          <Caption1 className={styles.muted}>No drafts sent yet.</Caption1>
        )}
        {toConfirm.length > 0 && <Text weight="semibold">To confirm ({toConfirm.length})</Text>}
        {toConfirm.map((r) => (
          <div key={r.id} className={styles.row}>
            <Text>
              {ruleLabel(r)} <span className={styles.muted}>· to {AUDIENCE[r.scope] ?? r.scope} · seen {r.evidence} times</span>
            </Text>
            <Button size="small" appearance="primary" onClick={() => void decide(r.id, "keep")}>
              Keep
            </Button>
            <Button size="small" onClick={() => void decide(r.id, "reject")}>
              Not me
            </Button>
          </div>
        ))}
        {kept.length > 0 && <Text weight="semibold">Kept</Text>}
        {kept.map((r) => (
          <div key={r.id} className={styles.row}>
            <Badge appearance="tint" color="success">Kept</Badge>
            <Text>
              {ruleLabel(r)} <span className={styles.muted}>· to {AUDIENCE[r.scope] ?? r.scope}</span>
            </Text>
            <Button size="small" appearance="subtle" onClick={() => void decide(r.id, "reject")}>
              Stop using
            </Button>
          </div>
        ))}
        {learning.length > 0 && (
          <Caption1 className={styles.muted}>
            Still learning: {learning.map((r) => `${ruleLabel(r)} (${r.evidence} of 3)`).join(" · ")}
          </Caption1>
        )}
      </div>
    </Card>
  );
}
