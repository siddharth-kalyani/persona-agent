/** Learned from your edits (M4): how often you send Vanimo's drafts unchanged, and the style rules
 * learned from the changes you make, for you to keep or reject. A rule is proposed only after it
 * was seen in at least 3 of your edits and your own sent mail agrees with it. A phrase you keep
 * cutting is shown struck through, a phrase you keep adding is highlighted, like a word diff.
 * Layout: one card; the send rates as metric wells with meters, then the rules in banded groups
 * (to confirm · kept · still learning), each rule a row with thumbs up/down. */
import { makeStyles, MessageBar, MessageBarBody } from "@fluentui/react-components";
import {
  DismissCircle16Regular,
  Edit16Regular,
  Eye16Regular,
  HandWave16Regular,
  Important16Regular,
  People16Regular,
  Signature16Regular,
  TextEditStyle20Regular,
  TextExpand16Regular,
  TextQuote16Regular,
  TextStrikethrough16Regular,
  ThumbDislike16Regular,
  ThumbLike16Regular,
} from "@fluentui/react-icons";
import { useCallback, useEffect, useState, type ReactElement, type ReactNode } from "react";
import type { EditSummary, LearnedRule } from "../../api/client";
import { useApi } from "../../api/context";
import { draftErrorText } from "../../drafting/DraftView";
import { EmptyState, IconAction, IconTile, List, ListRow, Meter, Pill, Section, typo, vt, type Tone } from "../../ui";
import { formLabel } from "./Persona";

const useStyles = makeStyles({
  metrics: { padding: "16px" },
  grid: { display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(150px, 1fr))", gap: "10px" },
  // One number in a well inside the card: label, value, an optional meter and hint.
  metric: {
    display: "grid",
    gap: "4px",
    alignContent: "start",
    padding: "12px 14px",
    borderRadius: "8px",
    backgroundColor: vt.inset,
    border: `1px solid ${vt.borderSubtle}`,
    minWidth: 0,
  },
  metricLabel: { ...typo.meta, fontWeight: 500, color: vt.text2 },
  metricValue: { ...typo.tabular, fontSize: "22px", lineHeight: "28px", fontWeight: 600, letterSpacing: "-0.02em", color: vt.text1 },
  metricMeter: { marginTop: "4px" },
  metricHint: { ...typo.meta, color: vt.text3 },
  muted: { ...typo.meta, color: vt.text2, margin: 0, padding: "14px 16px" },
  // A group of rules: a quiet band, then edge-to-edge rows.
  band: {
    display: "flex",
    alignItems: "center",
    gap: "8px",
    flexWrap: "wrap",
    margin: 0,
    padding: "8px 16px",
    backgroundColor: vt.inset,
    borderTop: `1px solid ${vt.borderSubtle}`,
    borderBottom: `1px solid ${vt.borderSubtle}`,
  },
  bandTitle: { ...typo.label, color: vt.text1, margin: 0 },
  bandNote: { ...typo.meta, color: vt.text3, margin: 0 },
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
  progress: { display: "inline-flex", alignItems: "center", gap: "8px", ...typo.tabular, whiteSpace: "nowrap", color: vt.text2 },
  progressMeter: { width: "56px" },
  actions: { display: "flex", gap: "2px", alignItems: "center" },
  meta: { display: "inline-flex", alignItems: "center", gap: "4px 14px", flexWrap: "wrap" },
  metaItem: { display: "inline-flex", alignItems: "center", gap: "5px" },
});

/** One number in a well: a label, the value, an optional proportion meter and a hint. A group named
 * by its label, so the number can be found by what it measures. */
export function Metric({ label, value, meter, hint }: { label: string; value: ReactNode; meter?: number; hint?: ReactNode }) {
  const s = useStyles();
  return (
    <div className={s.metric} role="group" aria-label={label}>
      <span className={s.metricLabel}>{label}</span>
      <span className={s.metricValue}>{value}</span>
      {meter !== undefined && <Meter value={meter} className={s.metricMeter} />}
      {hint && <span className={s.metricHint}>{hint}</span>}
    </div>
  );
}

export function MetricGrid({ children, label }: { children: ReactNode; label?: string }) {
  const s = useStyles();
  return (
    <div className={s.grid} role="group" aria-label={label}>
      {children}
    </div>
  );
}

const AUDIENCE: Record<string, string> = {
  manager: "your manager",
  report: "your direct reports",
  peer: "colleagues",
  external: "people outside your organisation",
  personal: "personal contacts",
  "*": "everyone",
};

/** What kind of rule it is, at a glance. */
const RULE_ICON: Record<LearnedRule["kind"], ReactElement> = {
  greeting: <HandWave16Regular />,
  sign_off: <Signature16Regular />,
  length: <TextExpand16Regular />,
  avoid: <TextStrikethrough16Regular />,
  prefer: <TextQuote16Regular />,
  exclamations: <Important16Regular />,
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
  const sent = Boolean(summary && summary.matched > 0);

  const tile = (r: LearnedRule, tone: Tone = "neutral") => <IconTile icon={RULE_ICON[r.kind] ?? <Edit16Regular />} tone={tone} size={32} />;
  const scope = (r: LearnedRule) => (
    <span className={styles.metaItem}>
      <People16Regular aria-hidden />
      To {AUDIENCE[r.scope] ?? r.scope}
    </span>
  );
  const band = (title: string, count: number, note?: string) => (
    <div className={styles.band}>
      <h3 className={styles.bandTitle}>{title}</h3>
      <Pill>{count}</Pill>
      {note && <p className={styles.bandNote}>{note}</p>}
    </div>
  );

  return (
    <Section
      variant="card"
      flush
      icon={<TextEditStyle20Regular />}
      title="Learned from your edits"
      description="Only the result and the kind of change are kept, never your sent text."
      info="When you send a draft Vanimo wrote, it compares the draft with what you actually sent. A rule is proposed only after it was seen in at least 3 of your edits and your own sent mail agrees with it."
    >
      {error && (
        <div className={styles.metrics}>
          <MessageBar intent="error">
            <MessageBarBody>{error}</MessageBarBody>
          </MessageBar>
        </div>
      )}
      {sent && summary ? (
        <div className={styles.metrics}>
          <MetricGrid label="How your drafts were sent">
            <Metric label="Drafts sent" value={summary.matched} hint="Matched to what you sent" />
            <Metric
              label="Sent without edits"
              value={pct(summary.sendWithoutEditRate)}
              meter={summary.sendWithoutEditRate}
              hint="5% or less changed"
            />
            <Metric label="At most light edits" value={pct(summary.lightEditRate)} meter={summary.lightEditRate} />
          </MetricGrid>
        </div>
      ) : rules.length === 0 ? (
        <EmptyState center icon={<TextEditStyle20Regular />} title="No drafts sent yet">
          Send a draft Vanimo wrote, with or without changes, and what you changed shows up here.
        </EmptyState>
      ) : (
        <p className={styles.muted}>No drafts sent yet.</p>
      )}

      {toConfirm.length > 0 && (
        <>
          {band("To confirm", toConfirm.length)}
          <List label="Rules to confirm">
            {toConfirm.map((r) => (
              <ListRow
                key={r.id}
                wrap
                leading={tile(r, "accent")}
                title={<RuleText rule={r} />}
                meta={
                  <span className={styles.meta}>
                    {scope(r)}
                    <span className={styles.metaItem}>
                      <Eye16Regular aria-hidden />
                      Seen {r.evidence} times
                    </span>
                  </span>
                }
                trailing={
                  <span className={styles.actions}>
                    <IconAction icon={<ThumbLike16Regular />} label="Keep" onClick={() => void decide(r.id, "keep")} />
                    <IconAction icon={<ThumbDislike16Regular />} label="Not me" onClick={() => void decide(r.id, "reject")} />
                  </span>
                }
              />
            ))}
          </List>
        </>
      )}

      {kept.length > 0 && (
        <>
          {band("Kept", kept.length)}
          <List label="Rules you kept">
            {kept.map((r) => (
              <ListRow
                key={r.id}
                wrap
                leading={tile(r, "success")}
                title={<RuleText rule={r} />}
                meta={<span className={styles.meta}>{scope(r)}</span>}
                trailing={
                  <span className={styles.actions}>
                    <Pill tone="success" dot>
                      Kept
                    </Pill>
                    <IconAction icon={<DismissCircle16Regular />} label="Stop using" danger onClick={() => void decide(r.id, "reject")} />
                  </span>
                }
              />
            ))}
          </List>
        </>
      )}

      {learning.length > 0 && (
        <>
          {band("Still learning", learning.length, "Proposed once seen in 3 of your edits.")}
          <List label="Rules still being learned">
            {learning.map((r) => (
              <ListRow
                key={r.id}
                wrap
                leading={tile(r)}
                title={<RuleText rule={r} />}
                meta={<span className={styles.meta}>{scope(r)}</span>}
                trailing={
                  <span className={styles.progress}>
                    <Meter value={r.evidence / 3} className={styles.progressMeter} />
                    {r.evidence} of 3
                  </span>
                }
              />
            ))}
          </List>
        </>
      )}
    </Section>
  );
}
