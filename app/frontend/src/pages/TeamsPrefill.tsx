import { Button, Field, Input, Link, makeStyles, Textarea, tokens } from "@fluentui/react-components";
import { Checkmark16Regular, Copy16Regular, Open16Regular } from "@fluentui/react-icons";
import { useState } from "react";
import { Page, Section, typo, vt } from "../ui";

const useStyles = makeStyles({
  test: { display: "grid", gap: "12px", maxWidth: "640px" },
  open: { display: "inline-flex", alignItems: "center", gap: "6px", ...typo.body },
  url: {
    ...typo.mono,
    color: vt.text2,
    margin: 0,
    padding: "8px 10px",
    borderRadius: tokens.borderRadiusLarge,
    backgroundColor: vt.inset,
    border: `1px solid ${vt.borderSubtle}`,
    overflowWrap: "anywhere",
  },
  urlLabel: { ...typo.label, color: vt.text3 },
  note: { ...typo.meta, color: vt.text2, margin: 0 },
  row: { display: "flex", gap: "8px 16px", alignItems: "center", flexWrap: "wrap" },
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

/** The link a test opens, shown so a tester can see exactly what Teams receives. */
function LinkPreview({ href }: { href: string }) {
  const styles = useStyles();
  return (
    <div>
      <span className={styles.urlLabel}>Link</span>
      <p className={styles.url}>{href}</p>
    </div>
  );
}

export function TeamsPrefill() {
  const styles = useStyles();
  const [emails, setEmails] = useState("");
  const [chatId, setChatId] = useState("");
  const [message, setMessage] = useState("Test from Vanimo: this text should appear in the compose box, unsent.");
  const [copied, setCopied] = useState(false);

  return (
    <Page
      title="Teams prefill test"
      width="reading"
      description="Week-1 spike: can Vanimo open a Teams chat with a draft already typed in (never sent)? If prefill doesn't work, the fallback is Copy."
    >
      <Section title="Message">
        <div className={styles.test}>
          <Field label="Message to prefill">
            <Textarea value={message} onChange={(_, d) => setMessage(d.value)} resize="vertical" />
          </Field>
          <div className={styles.row}>
            <Button
              icon={copied ? <Checkmark16Regular /> : <Copy16Regular />}
              onClick={() => {
                void navigator.clipboard.writeText(message).then(() => setCopied(true));
              }}
            >
              {copied ? "Copied" : "Copy text (fallback)"}
            </Button>
          </div>
        </div>
      </Section>

      <Section title="Test A: new or 1:1 chat" description="Microsoft documents prefill for new chats.">
        <div className={styles.test}>
          <Field label="Colleague email(s), comma-separated">
            <Input value={emails} onChange={(_, d) => setEmails(d.value)} placeholder="colleague@yourcompany.com" />
          </Field>
          {emails && <LinkPreview href={newChatLink(emails, message)} />}
          <div className={styles.row}>
            <Link
              className={styles.open}
              href={emails ? newChatLink(emails, message) : undefined}
              target="_blank"
              rel="noreferrer"
              disabled={!emails}
            >
              Open chat with text prefilled
              <Open16Regular aria-hidden />
            </Link>
          </div>
        </div>
      </Section>

      <Section title="Test B: existing group chat" description="The open question: does the same parameter prefill a chat that already exists?">
        <div className={styles.test}>
          <Field
            label="Chat ID"
            hint='In Teams: chat "…" menu → Copy link; the ID is the part starting 19: and ending @thread.v2'
          >
            <Input value={chatId} onChange={(_, d) => setChatId(d.value)} placeholder="19:…@thread.v2" />
          </Field>
          {chatId && <LinkPreview href={existingChatLink(chatId, message)} />}
          <div className={styles.row}>
            <Link
              className={styles.open}
              href={chatId ? existingChatLink(chatId, message) : undefined}
              target="_blank"
              rel="noreferrer"
              disabled={!chatId}
            >
              Open existing chat with text prefilled
              <Open16Regular aria-hidden />
            </Link>
          </div>
        </div>
      </Section>

      <p className={styles.note}>Record what happens on Teams desktop, web and mobile — the M5 Teams design depends on it.</p>
    </Page>
  );
}
