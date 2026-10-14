/** A draft as both surfaces show it: who it's for, what wrote it, the text (editable), the
 * pre-send checks and, for a blocking check, the confirmation that unlocks insert. */
import {
  Badge,
  Button,
  Caption1,
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

const useStyles = makeStyles({
  stack: { display: "grid", gap: tokens.spacingVerticalS },
  row: { display: "flex", gap: tokens.spacingHorizontalS, alignItems: "center", flexWrap: "wrap" },
  muted: { color: tokens.colorNeutralForeground3 },
  text: { minHeight: "180px" },
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

/** Plain-language reasons a draft couldn't be made (codes from the API, never content). */
export function draftErrorText(err: unknown): string {
  if (!(err instanceof ApiError)) return "Something went wrong. Try again.";
  switch (err.code) {
    case "review_pending":
      return "Finish the “Choose what Vanimo learns from” review first (My data → Set up).";
    case "conversation_excluded":
      return err.body.by === "organisation"
        ? "Your organisation excludes this conversation, so Vanimo can't draft in it."
        : "You excluded this conversation, so Vanimo doesn't use it.";
    case "instruction_required":
      return "Say what the email should say: a new email needs an instruction.";
    case "recipients_required":
      return "Add at least one recipient.";
    case "thread_not_found":
    case "thread_empty":
      return "Vanimo couldn't find this conversation in your mailbox.";
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
    <div className={styles.stack}>
      <div className={styles.row}>
        <Badge appearance="tint" color="brand">
          Writing to: {draft.audience.label}
        </Badge>
        {offline ? (
          <Badge appearance="tint" color="warning">
            Offline stand-in, no AI model
          </Badge>
        ) : (
          <Badge appearance="tint">{draft.tier === "premium" ? "Higher quality" : "Standard"}</Badge>
        )}
        {draft.oneOff && <Badge appearance="tint" color="informative">One-off, not saved</Badge>}
      </div>
      <Caption1 className={styles.muted}>
        {offline ? draft.label : `Written by ${draft.modelId}`}
        {draft.learned ? ` · in your style from ${draft.basedOn} of your messages` : " · your style isn't learned yet"}
      </Caption1>
      <Textarea
        aria-label="Draft"
        className={styles.text}
        resize="vertical"
        value={text}
        onChange={(_, d) => onTextChange(d.value)}
      />
      {sortChecks(checks).map((c) => (
        <MessageBar key={c.code} intent={SEVERITY_INTENT[c.severity]}>
          <MessageBarBody>
            <MessageBarTitle>{SEVERITY_TITLE[c.severity]}</MessageBarTitle>
            {c.message}
          </MessageBarBody>
        </MessageBar>
      ))}
      {hasBlock(checks) && (
        <Checkbox
          checked={confirmed}
          onChange={(_, d) => onConfirm(Boolean(d.checked))}
          label="I've checked this another way (for example, by phone on a number I already had)"
        />
      )}
      <div className={styles.row}>{actions}</div>
    </div>
  );
}

export function RateButtons({ onRate, rated }: { onRate: (rating: "good" | "bad") => void; rated: string | null }) {
  return (
    <>
      <Button size="small" appearance={rated === "good" ? "primary" : "subtle"} onClick={() => onRate("good")}>
        Sounds like me
      </Button>
      <Button size="small" appearance={rated === "bad" ? "primary" : "subtle"} onClick={() => onRate("bad")}>
        Doesn't sound like me
      </Button>
    </>
  );
}
