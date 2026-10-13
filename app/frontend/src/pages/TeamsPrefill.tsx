import { Button, Caption1, Card, CardHeader, Field, Input, Link, makeStyles, Text, Textarea, tokens } from "@fluentui/react-components";
import { useState } from "react";

const useStyles = makeStyles({
  stack: { display: "grid", gap: tokens.spacingVerticalL },
  row: { display: "flex", gap: tokens.spacingHorizontalM, alignItems: "center", flexWrap: "wrap" },
});

/** Deep link that opens a new or 1:1/group chat with the text prefilled (documented Teams deep link). */
export function newChatLink(emails: string, message: string): string {
  const users = emails
    .split(/[,;\s]+/)
    .map((e) => e.trim())
    .filter(Boolean)
    .join(",");
  return `https://teams.microsoft.com/l/chat/0/0?users=${encodeURIComponent(users)}&message=${encodeURIComponent(message)}`;
}

/** Spike: does `message=` also prefill an EXISTING chat opened by its ID? (docs/05 §5, spike 1) */
export function existingChatLink(chatId: string, message: string): string {
  return `https://teams.microsoft.com/l/chat/${encodeURIComponent(chatId.trim())}/conversations?message=${encodeURIComponent(message)}`;
}

export function TeamsPrefill() {
  const styles = useStyles();
  const [emails, setEmails] = useState("");
  const [chatId, setChatId] = useState("");
  const [message, setMessage] = useState("Test from Vanimo: this text should appear in the compose box, unsent.");
  const [copied, setCopied] = useState(false);

  return (
    <div className={styles.stack}>
      <Card>
        <CardHeader
          header={<Text weight="semibold">Teams prefill test</Text>}
          description={
            <Caption1>
              Week-1 spike: can Vanimo open a Teams chat with a draft already typed in (never sent)? If prefill doesn't work, the
              fallback is Copy.
            </Caption1>
          }
        />
        <Field label="Message to prefill">
          <Textarea value={message} onChange={(_, d) => setMessage(d.value)} resize="vertical" />
        </Field>
        <Field label="Test A: new or 1:1 chat — colleague email(s), comma-separated">
          <Input value={emails} onChange={(_, d) => setEmails(d.value)} placeholder="colleague@yourcompany.com" />
        </Field>
        <div className={styles.row}>
          <Link href={emails ? newChatLink(emails, message) : undefined} target="_blank" rel="noreferrer" disabled={!emails}>
            Open chat with text prefilled
          </Link>
        </div>
        <Field
          label="Test B: existing group chat — chat ID"
          hint='In Teams: chat "…" menu → Copy link; the ID is the part starting 19: and ending @thread.v2'
        >
          <Input value={chatId} onChange={(_, d) => setChatId(d.value)} placeholder="19:…@thread.v2" />
        </Field>
        <div className={styles.row}>
          <Link href={chatId ? existingChatLink(chatId, message) : undefined} target="_blank" rel="noreferrer" disabled={!chatId}>
            Open existing chat with text prefilled
          </Link>
          <Button
            onClick={() => {
              void navigator.clipboard.writeText(message).then(() => setCopied(true));
            }}
          >
            {copied ? "Copied" : "Copy text (fallback)"}
          </Button>
        </div>
        <Caption1>Record what happens on Teams desktop, web and mobile — the M5 Teams design depends on it.</Caption1>
      </Card>
    </div>
  );
}
