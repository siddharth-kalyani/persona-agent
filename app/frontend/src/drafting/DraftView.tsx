/** A draft as every surface shows it (web, Outlook add-in, Teams): who it's for, what wrote it and
 * from how much of your writing, the text (editable, in reading type), the pre-send checks (blocking
 * first, shown at once, never animated) and, for a blocking check, the confirmation that unlocks
 * insert. Uses Fluent tokens and fallback-safe Vanimo tokens, so it also looks right under
 * Microsoft's own themes in Outlook and Teams. */
import { Checkbox, makeStyles, mergeClasses, shorthands, Textarea, tokens, useAnnounce } from "@fluentui/react-components";
import {
  Compose16Regular,
  Info16Regular,
  People16Regular,
  ShieldError16Filled,
  ThumbDislike16Filled,
  ThumbDislike16Regular,
  ThumbLike16Filled,
  ThumbLike16Regular,
  Warning16Filled,
} from "@fluentui/react-icons";
import { useEffect, useId, type ReactNode } from "react";
import { ApiError, type Draft, type DraftCheck } from "../api/client";
import { Pill } from "../ui/feedback";
import { IconAction, IconTile } from "../ui/visual";
import { vt } from "../theme/theme";
import { typo } from "../theme/typography";

const useStyles = makeStyles({
  card: {
    display: "grid",
    backgroundColor: tokens.colorNeutralBackground1,
    border: `1px solid ${vt.border}`,
    borderRadius: tokens.borderRadiusXLarge,
    boxShadow: vt.shadowCard,
    minWidth: 0,
  },
  /** Inside another card (a commitment row): no frame of its own, just the parts. */
  flat: { backgroundColor: "transparent", border: "none", boxShadow: "none", borderRadius: 0 },
  flatHead: { padding: "0 0 12px" },
  flatBody: { padding: "12px 0" },
  flatActions: { padding: "12px 0 0", backgroundColor: "transparent" },
  head: {
    display: "grid",
    gridTemplateColumns: "auto minmax(0, 1fr)",
    gap: "4px 12px",
    alignItems: "center",
    padding: "14px 16px 12px",
    borderBottom: `1px solid ${vt.borderSubtle}`,
  },
  row: { display: "flex", gap: "6px", alignItems: "center", flexWrap: "wrap", minWidth: 0 },
  kicker: { ...typo.cardTitle, color: vt.text1, marginRight: "4px" },
  provenance: { ...typo.meta, color: vt.text2, margin: 0, gridColumn: "2" },
  body: { display: "grid", gap: "12px", padding: "16px", minWidth: 0 },
  textarea: { width: "100%" },
  text: { ...typo.reading, minHeight: "220px", maxHeight: "60vh", padding: "12px 14px", fieldSizing: "content" },
  checks: { display: "grid", gap: "10px" },
  // Pre-send checks, grouped by severity: one tinted panel per kind, never animated.
  group: {
    display: "grid",
    gap: "8px",
    padding: "12px 14px",
    borderRadius: tokens.borderRadiusLarge,
    ...shorthands.border("1px", "solid", "transparent"),
  },
  block: {
    backgroundColor: vt.inset,
    ...shorthands.borderColor(tokens.colorStatusDangerBorder1),
    boxShadow: `inset 3px 0 0 ${vt.danger}`,
  },
  warn: {
    backgroundColor: vt.inset,
    ...shorthands.borderColor(tokens.colorStatusWarningBorder1),
    boxShadow: `inset 3px 0 0 ${vt.warning}`,
  },
  groupHead: { display: "flex", alignItems: "center", gap: "8px" },
  blockIcon: { color: vt.danger, flexShrink: 0 },
  warnIcon: { color: vt.warning, flexShrink: 0 },
  groupTitle: { ...typo.cardTitle, color: vt.text1 },
  items: {
    margin: 0,
    paddingLeft: "42px",
    display: "grid",
    gap: "6px",
    ...typo.body,
    color: vt.text1,
    "& li::marker": { color: vt.text3 },
  },
  confirm: {
    marginTop: "2px",
    paddingTop: "6px",
    marginLeft: "-6px",
    borderTop: `1px solid ${vt.borderSubtle}`,
  },
  confirmLabel: { ...typo.body, fontWeight: 500, color: vt.text1 },
  note: { display: "flex", gap: "8px", alignItems: "flex-start", margin: 0, padding: "0 2px", ...typo.meta, color: vt.text2 },
  noteIcon: { color: vt.info, flexShrink: 0, marginTop: "1px" },
  noteTitle: { fontWeight: 600, color: vt.text1 },
  actions: {
    display: "flex",
    gap: "8px",
    alignItems: "center",
    flexWrap: "wrap",
    padding: "12px 16px",
    borderTop: `1px solid ${vt.borderSubtle}`,
    backgroundColor: vt.inset,
    borderBottomLeftRadius: tokens.borderRadiusXLarge,
    borderBottomRightRadius: tokens.borderRadiusXLarge,
  },
  rate: { display: "inline-flex", gap: "2px", marginLeft: "auto", alignItems: "center" },
  rateLabel: { ...typo.meta, color: vt.text3, marginRight: "4px", "@media (max-width: 479px)": { display: "none" } },
  rated: { color: vt.accent },
});

const SEVERITY_TITLE = { block: "Check before sending", warn: "Have a look", info: "Note" } as const;

/** Text areas that grow with their content where the browser supports it; elsewhere they keep a
 * resize grip (Firefox, older Safari: OWA and Outlook for Mac). */
export const AUTOSIZE = typeof CSS !== "undefined" && typeof CSS.supports === "function" && CSS.supports("field-sizing", "content");

/** Says the checks out loud when they appear or change: blocking checks and warnings at once, notes
 * politely. */
function useAnnounceChecks(checks: DraftCheck[]) {
  const { announce } = useAnnounce();
  const key = checks.map((c) => c.code).join(",");
  useEffect(() => {
    const urgent = sortChecks(checks).filter((c) => c.severity !== "info");
    const notes = checks.filter((c) => c.severity === "info");
    if (urgent.length) announce(`${SEVERITY_TITLE[urgent[0]!.severity]}: ${urgent.map((c) => c.message).join(" ")}`, { alert: true });
    if (notes.length) announce(`Note: ${notes.map((c) => c.message).join(" ")}`, { polite: true });
    // Only when the set of checks changes, not on every keystroke in the draft.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key]);
}

/** Blocking checks first, then warnings, then notes. */
export function sortChecks(checks: DraftCheck[]): DraftCheck[] {
  const rank = { block: 0, warn: 1, info: 2 } as const;
  return [...checks].sort((a, b) => rank[a.severity] - rank[b.severity]);
}

export function hasBlock(checks: DraftCheck[]): boolean {
  return checks.some((c) => c.severity === "block");
}

/** Checks after "Check my edits": a block found when drafting (a payment-change request in the
 * thread) still stands, since re-checking your edits may not see the thread. */
export function recheck(drafted: DraftCheck[], found: DraftCheck[]): DraftCheck[] {
  const blocks = drafted.filter((c) => c.severity === "block" && !found.some((r) => r.code === c.code));
  return [...blocks, ...found];
}

/** Plain-language reasons a draft couldn't be made (codes from the API, never content). */
export function draftErrorText(err: unknown): string {
  if (!(err instanceof ApiError)) return "Something went wrong. Try again.";
  switch (err.code) {
    case "review_pending":
      return "Finish the “Choose what Vanimo learns from” review first (My data → Set up).";
    case "conversation_excluded":
      if (err.body.by === "organisation") return "Your organisation excludes this conversation, so Vanimo can't draft in it.";
      if (err.body.by === "unverifiable" && Array.isArray(err.body.reasons) && err.body.reasons.includes("meeting_unknown"))
        return "Vanimo can't tie this meeting chat to its meeting, so it can't check it against your meeting rules. Run a new scan on My data first.";
      if (err.body.by === "unverifiable")
        return "Someone in this conversation has no email address Vanimo can check against your rules, so it isn't used.";
      return "You excluded this conversation, so Vanimo doesn't use it.";
    case "instruction_required":
      return "Say what the email should say: a new email needs an instruction.";
    case "recipients_required":
      return "Add at least one recipient.";
    case "thread_not_found":
      return "Vanimo couldn't find this conversation in your mailbox.";
    case "thread_empty":
      return "There's nothing to reply to here yet. For a chat, turn on “New message” and say what it should say.";
    case "chat_not_found":
    case "message_not_found":
      return "Vanimo couldn't find this chat or message in Teams.";
    case "chat_required":
      return "Pick a Teams chat first.";
    case "no_conversation":
      return "Vanimo doesn't know where this promise was made, so it can't draft the follow-up there.";
    case "handle_expired":
    case "handle_not_yours":
    case "invalid_handle":
      return "This Teams dialog has expired. Close it and choose “Draft reply” again.";
    case "too_many_drafts":
      return "That's a lot of drafts in a short time. Wait a minute and try again.";
    case "draft_blocked":
      return "The draft contained a regulated identifier, so it was not shown. Try again or write this one yourself.";
    case "thread_blocked":
    case "instruction_blocked":
    case "subject_blocked":
      return "The privacy check couldn't safely prepare this text for the model, so nothing was drafted.";
    case "model_unavailable":
      return "The drafting model didn't answer. Try again in a moment.";
    case "server_drafts_off":
      return "Your organisation doesn't allow drafts in mailboxes.";
    case "already_placed":
      return "This draft is already in your Drafts folder.";
    case "confirmation_required":
      return "Tick the confirmation under the warning first.";
    case "reply_drafts_only":
      return "Only replies can go to your Drafts folder; copy a new email instead.";
    case "outlook_drafts_off":
      return "Turn on “Put drafts in my Outlook Drafts folder” on the Queue tab first.";
    case "controls_changed":
      return "Your data controls changed meanwhile. Try again.";
    case "already_matched":
      return "This draft was already marked as sent.";
    case "db_unavailable":
      return "Vanimo is waking up. Try again in a few seconds.";
    default:
      return `Something went wrong (${err.code}).`;
  }
}

export function DraftView({
  draft,
  text,
  onTextChange,
  checks,
  confirmed,
  onConfirm,
  actions,
  flat,
}: {
  draft: Draft;
  text: string;
  onTextChange: (text: string) => void;
  checks: DraftCheck[];
  confirmed: boolean;
  onConfirm: (value: boolean) => void;
  actions: ReactNode;
  /** No card frame: for a draft shown inside another card. */
  flat?: boolean;
}) {
  const styles = useStyles();
  const titleId = useId();
  useAnnounceChecks(checks);
  const offline = draft.generator === "offline";
  return (
    <section className={mergeClasses(styles.card, flat && styles.flat)} aria-label="Vanimo draft">
      <div className={mergeClasses(styles.head, flat && styles.flatHead)}>
        <IconTile icon={<Compose16Regular />} tone="accent" size={32} />
        <div className={styles.row}>
          <span className={styles.kicker}>Vanimo draft</span>
          <Pill tone="accent" icon={<People16Regular />} wrap>
            Writing to: {draft.audience.label}
          </Pill>
          {!offline && <Pill>{draft.tier === "premium" ? "Higher quality" : "Standard"}</Pill>}
          {draft.oneOff && <Pill tone="warning">One-off, not saved</Pill>}
        </div>
        <p className={styles.provenance}>
          {offline ? draft.label : `Written by ${draft.modelId}`}
          {draft.learned ? ` · in your style from ${draft.basedOn} of your messages` : " · your style isn't learned yet"}
        </p>
      </div>
      <div className={mergeClasses(styles.body, flat && styles.flatBody)}>
        <Textarea
          aria-label="Draft"
          className={styles.textarea}
          textarea={{ className: styles.text }}
          resize={AUTOSIZE ? "none" : "vertical"}
          value={text}
          onChange={(_, d) => onTextChange(d.value)}
        />
        {checks.length > 0 && (
          <div className={styles.checks}>
            {(["block", "warn"] as const).map((severity) => {
              const items = checks.filter((c) => c.severity === severity);
              if (!items.length) return null;
              const id = `${titleId}-${severity}`;
              return (
                <div key={severity} className={mergeClasses(styles.group, styles[severity])} role="group" aria-labelledby={id}>
                  <div className={styles.groupHead}>
                    {severity === "block" ? (
                      <ShieldError16Filled className={styles.blockIcon} aria-hidden />
                    ) : (
                      <Warning16Filled className={styles.warnIcon} aria-hidden />
                    )}
                    <span id={id} className={styles.groupTitle}>
                      {SEVERITY_TITLE[severity]}
                    </span>
                  </div>
                  <ul className={styles.items}>
                    {items.map((c) => (
                      <li key={c.code}>{c.message}</li>
                    ))}
                  </ul>
                  {severity === "block" && (
                    <Checkbox
                      className={styles.confirm}
                      checked={confirmed}
                      onChange={(_, d) => onConfirm(Boolean(d.checked))}
                      label={{
                        className: styles.confirmLabel,
                        children: "I've checked this another way (for example, by phone on a number I already had)",
                      }}
                    />
                  )}
                </div>
              );
            })}
            {checks
              .filter((c) => c.severity === "info")
              .map((c) => (
                <p key={c.code} className={styles.note}>
                  <Info16Regular className={styles.noteIcon} aria-hidden />
                  <span>
                    <strong className={styles.noteTitle}>{SEVERITY_TITLE.info}</strong> {c.message}
                  </span>
                </p>
              ))}
          </div>
        )}
      </div>
      <div className={mergeClasses(styles.actions, flat && styles.flatActions)}>{actions}</div>
    </section>
  );
}

/** "Does this sound like you?": thumbs up or down, remembered per draft. */
export function RateButtons({ onRate, rated }: { onRate: (rating: "good" | "bad") => void; rated: string | null }) {
  const styles = useStyles();
  return (
    <span className={styles.rate} role="group" aria-label="Does this sound like you?">
      <span className={styles.rateLabel} aria-hidden>
        Sounds like you?
      </span>
      <IconAction
        icon={rated === "good" ? <ThumbLike16Filled /> : <ThumbLike16Regular />}
        label="Sounds like me"
        aria-pressed={rated === "good"}
        className={rated === "good" ? styles.rated : undefined}
        onClick={() => onRate("good")}
      />
      <IconAction
        icon={rated === "bad" ? <ThumbDislike16Filled /> : <ThumbDislike16Regular />}
        label="Doesn't sound like me"
        aria-pressed={rated === "bad"}
        className={rated === "bad" ? styles.rated : undefined}
        onClick={() => onRate("bad")}
      />
    </span>
  );
}
