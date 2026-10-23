/** Learned from your edits (M4): how often you send Vanimo's drafts unchanged, and the style rules
 * learned from the changes you make, for you to keep or reject. A rule is proposed only after it
 * was seen in at least 3 of your edits and your own sent mail agrees with it. A phrase you keep
 * cutting is shown struck through, a phrase you keep adding is highlighted, like a word diff. */
import { Button, makeStyles, MessageBar, MessageBarBody } from "@fluentui/react-components";
import { useCallback, useEffect, useState } from "react";
import type { EditSummary, LearnedRule } from "../../api/client";
import { useApi } from "../../api/context";
import { draftErrorText } from "../../drafting/DraftView";
import { List, ListRow, Pill, Section, typo, vt } from "../../ui";
import { formLabel } from "./Persona";

const useStyles = makeStyles({
  summary: { ...typo.body, ...typo.tabular, color: vt.text2, margin: 0 },
  strong: { fontWeight: 600, color: vt.text1 },
  muted: { ...typo.meta, color: vt.text2, margin: 0 },
  group: { display: "grid", gap: "8px", minWidth: 0 },
  groupTitle: { ...typo.itemTitle, color: vt.text1, margin: 0, display: "flex", alignItems: "baseline", gap: "8px" },
  count: { ...typo.meta, ...typo.tabular, color: vt.text3, fontWeight: 400 },
  groupNote: { ...typo.meta, color: vt.text2, margin: 0 },
  // Word-diff colours, plus strikethrough or the rule's own words, so meaning never rests on colour.
  del: {
    backgroundColor: vt.diffDelWord,
    color: vt.text1,
    textDecorationLine: "line-through",
    textDecorationColor: vt.danger,
    borderRadius: "3px",
    padding: "0 2px",
  },
  ins: {
    backgroundColor: vt.diffAddWord,
    color: vt.text1,
    textDecorationLine: "none",
    borderRadius: "3px",
    padding: "0 2px",
  },
  progress: { ...typo.tabular, whiteSpace: "nowrap" },
  actions: { display: "flex", gap: "4px", alignItems: "center" },
  row: { minHeight: "52px" },
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

/** The rule's words, with the phrase it removes or adds marked like a word diff. */
function RuleText({ rule }: { rule: LearnedRule }) {
  const s = useStyles();
  const label = ruleLabel(rule);
  const at = rule.value && (rule.kind === "avoid" || rule.kind === "prefer") ? label.indexOf(rule.value) : -1;
  if (at < 0) return <>{label}</>;
  const Mark = rule.kind === "avoid" ? "del" : "ins";
  return (
    <>
      {label.slice(0, at)}
      <Mark className={rule.kind === "avoid" ? s.del : s.ins}>{rule.value}</Mark>
      {label.slice(at + rule.value.length)}
    </>
  );
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
    <Section
      title="Learned from your edits"
      description="When you send a draft Vanimo wrote, it compares the draft with what you actually sent. Only the result and the kind of change are kept, never your sent text."
    >
      {error && (
        <MessageBar intent="error">
          <MessageBarBody>{error}</MessageBarBody>
        </MessageBar>
      )}
      {summary && summary.matched > 0 ? (
        <p className={styles.summary}>
          {summary.matched} draft{summary.matched === 1 ? "" : "s"} sent ·{" "}
          <b className={styles.strong}>{pct(summary.sendWithoutEditRate)} sent without edits</b> (5% or less changed) ·{" "}
          {pct(summary.lightEditRate)} with at most light edits
        </p>
      ) : (
        <p className={styles.muted}>No drafts sent yet.</p>
      )}

      {toConfirm.length > 0 && (
        <div className={styles.group}>
          <h3 className={styles.groupTitle}>
            To confirm <span className={styles.count}>{toConfirm.length}</span>
          </h3>
          <List bordered label="Rules to confirm">
            {toConfirm.map((r) => (
              <ListRow
                key={r.id}
                className={styles.row}
                wrap
                title={<RuleText rule={r} />}
                meta={`to ${AUDIENCE[r.scope] ?? r.scope} · seen ${r.evidence} times`}
                trailing={
                  <span className={styles.actions}>
                    <Button size="small" onClick={() => void decide(r.id, "keep")}>
                      Keep
                    </Button>
                    <Button size="small" appearance="subtle" onClick={() => void decide(r.id, "reject")}>
                      Not me
                    </Button>
                  </span>
                }
              />
            ))}
          </List>
        </div>
      )}

      {kept.length > 0 && (
        <div className={styles.group}>
          <h3 className={styles.groupTitle}>
            Kept <span className={styles.count}>{kept.length}</span>
          </h3>
          <List bordered label="Rules you kept">
            {kept.map((r) => (
              <ListRow
                key={r.id}
                wrap
                title={<RuleText rule={r} />}
                meta={`to ${AUDIENCE[r.scope] ?? r.scope}`}
                trailing={
                  <span className={styles.actions}>
                    <Pill tone="success">Kept</Pill>
                    <Button size="small" appearance="subtle" onClick={() => void decide(r.id, "reject")}>
                      Stop using
                    </Button>
                  </span>
                }
              />
            ))}
          </List>
        </div>
      )}

      {learning.length > 0 && (
        <div className={styles.group}>
          <h3 className={styles.groupTitle}>
            Still learning <span className={styles.count}>{learning.length}</span>
          </h3>
          <p className={styles.groupNote}>Proposed once seen in 3 of your edits.</p>
          <List bordered label="Rules still being learned">
            {learning.map((r) => (
              <ListRow
                key={r.id}
                wrap
                title={<RuleText rule={r} />}
                meta={`to ${AUDIENCE[r.scope] ?? r.scope}`}
                trailing={<span className={styles.progress}>{r.evidence} of 3</span>}
              />
            ))}
          </List>
        </div>
      )}
    </Section>
  );
}
