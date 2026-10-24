import { Button, Field, Input, makeStyles, Textarea, tokens } from "@fluentui/react-components";
import {
  Chat16Regular,
  ChatMultiple16Regular,
  ChatMultiple20Regular,
  Checkmark16Regular,
  Copy16Regular,
  Info16Regular,
  Open16Regular,
  TextQuote16Regular,
} from "@fluentui/react-icons";
import { useState, type ReactElement, type ReactNode } from "react";
import { CHANNELS, IconTile, Page, Section, type Tone, typo, vt } from "../ui";

const useStyles = makeStyles({
  form: { display: "grid", minWidth: 0 },
  block: {
    display: "grid",
    gap: "14px",
    padding: "20px",
    borderTop: `1px solid ${vt.borderSubtle}`,
    ":first-child": { borderTop: "none" },
    "@media (max-width: 479px)": { padding: "16px" },
  },
  blockHead: { display: "grid", gridTemplateColumns: "auto minmax(0, 1fr)", gap: "12px", alignItems: "center" },
  blockText: { display: "grid", gap: "2px", minWidth: 0 },
  blockTitle: { ...typo.cardTitle, color: vt.text1, margin: 0 },
  blockDescription: { ...typo.meta, color: vt.text2, margin: 0 },
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
  urlWrap: { display: "grid", gap: "4px" },
  urlLabel: { ...typo.label, color: vt.text3 },
  row: { display: "flex", gap: "8px 16px", alignItems: "center", flexWrap: "wrap" },
  note: {
    display: "flex",
    gap: "8px",
    alignItems: "flex-start",
    ...typo.meta,
    color: vt.text2,
    margin: 0,
    padding: "12px 20px",
    backgroundColor: vt.inset,
    borderTop: `1px solid ${vt.borderSubtle}`,
    "& > svg": { flexShrink: 0, marginTop: "1px", color: vt.text3 },
  },
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
    <div className={styles.urlWrap}>
      <span className={styles.urlLabel}>Link</span>
      <p className={styles.url}>{href}</p>
    </div>
  );
}

/** One part of the test: a tile, a heading (h3, under the card's h2) and its fields. */
function Block({ icon, tone, title, description, children }: { icon: ReactElement; tone?: Tone; title: string; description?: string; children: ReactNode }) {
  const styles = useStyles();
  return (
    <section className={styles.block} aria-label={title}>
      <div className={styles.blockHead}>
        <IconTile icon={icon} tone={tone} size={32} />
        <div className={styles.blockText}>
          <h3 className={styles.blockTitle}>{title}</h3>
          {description && <p className={styles.blockDescription}>{description}</p>}
        </div>
      </div>
      {children}
    </section>
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
      description="Can Vanimo open a Teams chat with a draft already typed in (never sent)?"
      info="If prefill doesn't work, the fallback is Copy."
    >
      <Section
        variant="card"
        flush
        icon={<ChatMultiple20Regular />}
        title="Prefill test"
        description="Write the message once, then open each test in Teams."
      >
        <div className={styles.form}>
          <Block icon={<TextQuote16Regular />} title="Message">
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
          </Block>

          <Block icon={<Chat16Regular />} tone={CHANNELS.chat.tone} title="Test A: new or 1:1 chat" description="Microsoft documents prefill for new chats.">
            <Field label="Colleague email(s), comma-separated">
              <Input value={emails} onChange={(_, d) => setEmails(d.value)} placeholder="colleague@yourcompany.com" />
            </Field>
            {emails && <LinkPreview href={newChatLink(emails, message)} />}
            <div className={styles.row}>
              <Button
                as="a"
                href={emails ? newChatLink(emails, message) : undefined}
                target="_blank"
                rel="noreferrer"
                disabled={!emails}
                icon={<Open16Regular />}
                iconPosition="after"
              >
                Open chat with text prefilled
              </Button>
            </div>
          </Block>

          <Block
            icon={<ChatMultiple16Regular />}
            tone={CHANNELS.chat.tone}
            title="Test B: existing group chat"
            description="The open question: does the same parameter prefill a chat that already exists?"
          >
            <Field
              label="Chat ID"
              hint='In Teams: chat "…" menu → Copy link; the ID is the part starting 19: and ending @thread.v2'
            >
              <Input value={chatId} onChange={(_, d) => setChatId(d.value)} placeholder="19:…@thread.v2" />
            </Field>
            {chatId && <LinkPreview href={existingChatLink(chatId, message)} />}
            <div className={styles.row}>
              <Button
                as="a"
                href={chatId ? existingChatLink(chatId, message) : undefined}
                target="_blank"
                rel="noreferrer"
                disabled={!chatId}
                icon={<Open16Regular />}
                iconPosition="after"
              >
                Open existing chat with text prefilled
              </Button>
            </div>
          </Block>
        </div>
        <p className={styles.note}>
          <Info16Regular aria-hidden />
          Record what happens on Teams desktop, web and mobile: Vanimo's Teams drafting depends on it.
        </p>
      </Section>
    </Page>
  );
}
