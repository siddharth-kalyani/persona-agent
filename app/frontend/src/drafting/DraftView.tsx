/** A draft as every surface shows it (web, Outlook add-in, Teams): who it's for, what wrote it and
 * from how much of your writing, the text (editable, in reading type), the pre-send checks (blocking
 * first, shown at once, never animated) and, for a blocking check, the confirmation that unlocks
 * insert. Uses Fluent tokens and fallback-safe Vanimo tokens, so it also looks right under
 * Microsoft's own themes in Outlook and Teams. */
import {
  Button,
  Checkbox,
  makeStyles,
  MessageBar,
  MessageBarBody,
  MessageBarTitle,
  Textarea,
  tokens,
} from "@fluentui/react-components";
import type { ReactNode } from "react";
import { ApiError, type Draft, type DraftCheck } from "../api/client";
import { Pill } from "../ui/feedback";
import { vt } from "../theme/theme";
import { typo } from "../theme/typography";

const useStyles = makeStyles({
  card: {
    position: "relative",
    display: "grid",
    gap: "12px",
    padding: "16px",
    backgroundColor: tokens.colorNeutralBackground1,
    border: `1px solid ${tokens.colorNeutralStroke2}`,
    borderRadius: tokens.borderRadiusXLarge,
    minWidth: 0,
    // A thin accent rule marks text Vanimo wrote (no glow, no sparkle).
    "::before": {
      content: '""',
      position: "absolute",
      left: "-1px",
      top: "16px",
      bottom: "16px",
      width: "2px",
      borderRadius: "2px",
      backgroundColor: vt.accent,
    },
  },
  head: { display: "grid", gap: "6px" },
  row: { display: "flex", gap: "6px", alignItems: "center", flexWrap: "wrap" },
  kicker: { ...typo.label, color: vt.text3, marginRight: "2px" },
  provenance: { ...typo.meta, color: vt.text2, margin: 0 },
  textarea: { width: "100%" },
  text: { ...typo.reading, minHeight: "220px", padding: "10px 12px" },
  checks: { display: "grid", gap: "8px" },
  confirm: { marginTop: "-2px" },
  actions: {
    display: "flex",
    gap: "8px",
    alignItems: "center",
    flexWrap: "wrap",
    paddingTop: "12px",
    borderTop: `1px solid ${tokens.colorNeutralStroke3}`,
  },
  rate: { display: "inline-flex", gap: "2px", marginLeft: "auto" },
});

const SEVERITY_INTENT = { block: "error", warn: "warning", info: "info" } as const;
const SEVERITY_TITLE = { block: "Check before sending", warn: "Have a look", info: "Note" } as const;

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
}: {
  draft: Draft;
  text: string;
  onTextChange: (text: string) => void;
  checks: DraftCheck[];
  confirmed: boolean;
  onConfirm: (value: boolean) => void;
  actions: ReactNode;
}) {
  const styles = useStyles();
  const offline = draft.generator === "offline";
  return (
    <section className={styles.card} aria-label="Vanimo draft">
      <div className={styles.head}>
        <div className={styles.row}>
          <span className={styles.kicker}>Vanimo draft</span>
          <Pill tone="accent" wrap>
            Writing to: {draft.audience.label}
          </Pill>
          {offline ? (
            <Pill tone="warning">Offline stand-in, no AI model</Pill>
          ) : (
            <Pill>{draft.tier === "premium" ? "Higher quality" : "Standard"}</Pill>
          )}
          {draft.oneOff && <Pill>One-off, not saved</Pill>}
        </div>
        <p className={styles.provenance}>
          {offline ? draft.label : `Written by ${draft.modelId}`}
          {draft.learned ? ` · in your style from ${draft.basedOn} of your messages` : " · your style isn't learned yet"}
        </p>
      </div>
      <Textarea
        aria-label="Draft"
        className={styles.textarea}
        textarea={{ className: styles.text }}
        resize="vertical"
        value={text}
        onChange={(_, d) => onTextChange(d.value)}
      />
      {checks.length > 0 && (
        <div className={styles.checks}>
          {sortChecks(checks).map((c) => (
            <MessageBar key={c.code} intent={SEVERITY_INTENT[c.severity]} layout="multiline">
              <MessageBarBody>
                <MessageBarTitle>{SEVERITY_TITLE[c.severity]}</MessageBarTitle>
                {c.message}
              </MessageBarBody>
            </MessageBar>
          ))}
          {hasBlock(checks) && (
            <Checkbox
              className={styles.confirm}
              checked={confirmed}
              onChange={(_, d) => onConfirm(Boolean(d.checked))}
              label="I've checked this another way (for example, by phone on a number I already had)"
            />
          )}
        </div>
      )}
      <div className={styles.actions}>{actions}</div>
    </section>
  );
}

export function RateButtons({ onRate, rated }: { onRate: (rating: "good" | "bad") => void; rated: string | null }) {
  const styles = useStyles();
  return (
    <span className={styles.rate} role="group" aria-label="Does this sound like you?">
      <Button size="small" appearance={rated === "good" ? "secondary" : "subtle"} aria-pressed={rated === "good"} onClick={() => onRate("good")}>
        Sounds like me
      </Button>
      <Button size="small" appearance={rated === "bad" ? "secondary" : "subtle"} aria-pressed={rated === "bad"} onClick={() => onRate("bad")}>
        Doesn't sound like me
      </Button>
    </span>
  );
}
