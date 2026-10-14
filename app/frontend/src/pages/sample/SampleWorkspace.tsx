import {
  Badge,
  Body1,
  Button,
  Caption1,
  Card,
  makeStyles,
  MessageBar,
  MessageBarBody,
  Spinner,
  Tab,
  TabList,
  Text,
  Title3,
  tokens,
} from "@fluentui/react-components";
import { useEffect, useMemo, useState } from "react";
import { ApiError, type ItemStatus, type SamplePerson, type SampleWorkspace as Workspace, type StoredItem } from "../../api/client";
import { useApi } from "../../api/context";
import { errorText } from "../Home";

const useStyles = makeStyles({
  stack: { display: "grid", gap: tokens.spacingVerticalM },
  split: {
    display: "grid",
    gap: tokens.spacingHorizontalL,
    gridTemplateColumns: "minmax(240px, 340px) 1fr",
    "@media (max-width: 720px)": { gridTemplateColumns: "1fr" },
  },
  list: { display: "grid", gap: tokens.spacingVerticalXS, maxHeight: "70vh", overflowY: "auto", alignContent: "start" },
  item: {
    textAlign: "left",
    display: "grid",
    gap: "2px",
    padding: tokens.spacingVerticalS,
    borderRadius: tokens.borderRadiusMedium,
    border: `1px solid ${tokens.colorNeutralStroke2}`,
    backgroundColor: tokens.colorNeutralBackground1,
    cursor: "pointer",
  },
  selected: { border: `1px solid ${tokens.colorBrandStroke1}`, backgroundColor: tokens.colorBrandBackground2 },
  row: { display: "flex", gap: tokens.spacingHorizontalS, alignItems: "center", flexWrap: "wrap" },
  muted: { color: tokens.colorNeutralForeground3 },
  body: { whiteSpace: "pre-wrap", fontFamily: tokens.fontFamilyBase, margin: 0 },
  bubble: {
    padding: tokens.spacingVerticalS,
    borderRadius: tokens.borderRadiusLarge,
    backgroundColor: tokens.colorNeutralBackground3,
    maxWidth: "80%",
  },
  mine: { backgroundColor: tokens.colorBrandBackground2, justifySelf: "end" },
  compare: { display: "grid", gap: tokens.spacingHorizontalM, gridTemplateColumns: "1fr 1fr" },
  code: {
    whiteSpace: "pre-wrap",
    fontFamily: tokens.fontFamilyMonospace,
    fontSize: tokens.fontSizeBase200,
    backgroundColor: tokens.colorNeutralBackground3,
    padding: tokens.spacingVerticalS,
    borderRadius: tokens.borderRadiusMedium,
    margin: 0,
  },
});

const STATUS: Record<ItemStatus, { label: string; color: "success" | "danger" | "warning" | "informative" }> = {
  learned: { label: "Learned (redacted)", color: "success" },
  excluded: { label: "Excluded", color: "danger" },
  not_learned: { label: "Not learned yet", color: "warning" },
  received: { label: "Received", color: "informative" },
};

const REASON: Record<string, string> = {
  person: "a person you excluded",
  domain: "a domain you excluded",
  thread: "a thread you excluded",
  chat: "a chat you excluded",
  meeting: "a meeting you excluded",
  series: "a meeting series you excluded",
  client_account: "a client your organisation excluded",
  not_approved: "an external party your organisation hasn't approved",
};

export function StatusBadge({ status, reasons = [] }: { status: ItemStatus; reasons?: string[] }) {
  const s = STATUS[status];
  const why = reasons.map((r) => REASON[r] ?? r).join(", ");
  return (
    <Badge appearance="tint" color={s.color} title={why ? `Because of ${why}` : undefined}>
      {s.label}
    </Badge>
  );
}

function who(p: SamplePerson | null) {
  return p ? p.name || p.email : "—";
}

/** What Vanimo kept for one item: the stored L1 text next to your re-hydrated view of it. */
export function StoredView({ storedId }: { storedId: string }) {
  const styles = useStyles();
  const api = useApi();
  const [item, setItem] = useState<StoredItem | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    let live = true;
    api.storedItems({ ids: [storedId] }).then(
      (r) => live && setItem(r.items[0] ?? null),
      (e) => live && setError(errorText(e)),
    );
    return () => {
      live = false;
    };
  }, [api, storedId]);
  if (error) return <Caption1>{error}</Caption1>;
  if (!item) return <Spinner size="tiny" label="Loading what was stored…" />;
  return (
    <Card>
      <Text weight="semibold">What Vanimo stored</Text>
      <Caption1 className={styles.muted}>
        Labels: {item.relationship} · {item.intent} · {item.language} · {item.wordCount} words
        {item.heldOut ? " · held out for evaluation" : ""}
      </Caption1>
      <div className={styles.compare}>
        <div>
          <Caption1>Stored (encrypted at rest)</Caption1>
          <pre className={styles.code}>{item.stored}</pre>
        </div>
        <div>
          <Caption1>Shown to you</Caption1>
          <pre className={styles.code}>{item.display}</pre>
        </div>
      </div>
      {item.contextStored && (
        <>
          <Caption1>The message you replied to, as stored</Caption1>
          <pre className={styles.code}>{item.contextStored}</pre>
        </>
      )}
    </Card>
  );
}

type View = "inbox" | "sent" | "chats" | "meetings";

/** The sample workspace as Outlook and Teams would show it, with what Vanimo did with each item. */
export function SampleWorkspace() {
  const styles = useStyles();
  const api = useApi();
  const [ws, setWs] = useState<Workspace | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [view, setView] = useState<View>("sent");
  const [selected, setSelected] = useState<string | null>(null);
  const [showStored, setShowStored] = useState<string | null>(null);

  useEffect(() => {
    let live = true;
    api.sampleWorkspace().then(
      (w) => live && setWs(w),
      (e) =>
        live &&
        setError(
          e instanceof ApiError && e.code === "sample_workspace_only"
            ? "You're connected to Microsoft 365, so there's no sample workspace to show."
            : errorText(e),
        ),
    );
    return () => {
      live = false;
    };
  }, [api]);

  const emails = useMemo(
    () => (ws ? ws.emails.filter((e) => (view === "sent" ? e.direction === "sent" : e.direction === "received")) : []),
    [ws, view],
  );

  if (error)
    return (
      <MessageBar intent="info">
        <MessageBarBody>{error}</MessageBarBody>
      </MessageBar>
    );
  if (!ws) return <Spinner label="Opening the sample workspace…" />;

  const counts = {
    learned: ws.emails.filter((e) => e.status === "learned").length +
      ws.chats.flatMap((c) => c.messages).filter((m) => m.status === "learned").length,
  };
  const email = ws.emails.find((e) => e.id === selected);
  const chat = ws.chats.find((c) => c.id === selected);
  const meeting = ws.meetings.find((m) => m.id === selected);

  return (
    <div className={styles.stack}>
      <Title3 as="h2">Sample workspace</Title3>
      <MessageBar intent="info">
        <MessageBarBody>
          {ws.note} {counts.learned} of your messages are learned so far.
        </MessageBarBody>
      </MessageBar>
      <TabList
        selectedValue={view}
        onTabSelect={(_, d) => {
          setView(d.value as View);
          setSelected(null);
          setShowStored(null);
        }}
      >
        <Tab value="inbox">Inbox</Tab>
        <Tab value="sent">Sent</Tab>
        <Tab value="chats">Chats</Tab>
        <Tab value="meetings">Meetings</Tab>
      </TabList>
      <div className={styles.split}>
        <div className={styles.list} role="list" aria-label={view}>
          {(view === "inbox" || view === "sent") &&
            emails.map((e) => (
              <button
                key={e.id}
                role="listitem"
                className={`${styles.item} ${selected === e.id ? styles.selected : ""}`}
                onClick={() => {
                  setSelected(e.id);
                  setShowStored(null);
                }}
              >
                <div className={styles.row}>
                  <Text weight="semibold" truncate wrap={false}>
                    {view === "sent" ? `To: ${e.to.map(who).join(", ")}` : who(e.sender)}
                  </Text>
                </div>
                <Text truncate wrap={false}>{e.subject || "(no subject)"}</Text>
                <div className={styles.row}>
                  <Caption1 className={styles.muted}>{new Date(e.sentAt).toLocaleDateString()}</Caption1>
                  <StatusBadge status={e.status} reasons={e.reasons} />
                </div>
              </button>
            ))}
          {view === "chats" &&
            ws.chats.map((c) => (
              <button
                key={c.id}
                role="listitem"
                className={`${styles.item} ${selected === c.id ? styles.selected : ""}`}
                onClick={() => {
                  setSelected(c.id);
                  setShowStored(null);
                }}
              >
                <Text weight="semibold" truncate wrap={false}>{c.label}</Text>
                <div className={styles.row}>
                  <Caption1 className={styles.muted}>{c.members.length} people</Caption1>
                  {c.excluded && <StatusBadge status="excluded" reasons={c.reasons} />}
                </div>
              </button>
            ))}
          {view === "meetings" &&
            ws.meetings.map((m) => (
              <button
                key={m.id}
                role="listitem"
                className={`${styles.item} ${selected === m.id ? styles.selected : ""}`}
                onClick={() => setSelected(m.id)}
              >
                <Text weight="semibold" truncate wrap={false}>{m.subject || "(no subject)"}</Text>
                <div className={styles.row}>
                  <Caption1 className={styles.muted}>{new Date(m.start).toLocaleString()}</Caption1>
                  {m.excluded && <StatusBadge status="excluded" reasons={m.reasons} />}
                </div>
              </button>
            ))}
        </div>
        <div className={styles.stack}>
          {!selected && <Caption1 className={styles.muted}>Select an item to read it.</Caption1>}
          {email && (
            <Card>
              <Text weight="semibold" size={400}>{email.subject || "(no subject)"}</Text>
              <Caption1>
                From {who(email.sender)} · To {email.to.map(who).join(", ")}
                {email.cc.length > 0 && ` · Cc ${email.cc.map(who).join(", ")}`}
              </Caption1>
              <Caption1 className={styles.muted}>{new Date(email.sentAt).toLocaleString()}</Caption1>
              <pre className={styles.body}>{email.body}</pre>
              <div className={styles.row}>
                <StatusBadge status={email.status} reasons={email.reasons} />
                {email.storedId && (
                  <Button size="small" onClick={() => setShowStored(email.storedId)}>
                    See what Vanimo stored
                  </Button>
                )}
              </div>
            </Card>
          )}
          {chat && (
            <Card>
              <Text weight="semibold" size={400}>{chat.label}</Text>
              <Caption1 className={styles.muted}>{chat.members.map(who).join(", ")}</Caption1>
              <div className={styles.stack}>
                {chat.messages.map((m) => (
                  <div key={m.id} className={`${styles.bubble} ${m.fromMe ? styles.mine : ""}`}>
                    <Caption1>{m.fromMe ? "You" : who(m.sender)}</Caption1>
                    <Body1 block>{m.text}</Body1>
                    {m.fromMe && (
                      <div className={styles.row}>
                        <StatusBadge status={m.status} reasons={chat.reasons} />
                        {m.storedId && (
                          <Button size="small" appearance="subtle" onClick={() => setShowStored(m.storedId)}>
                            See what was stored
                          </Button>
                        )}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </Card>
          )}
          {meeting && (
            <Card>
              <Text weight="semibold" size={400}>{meeting.subject || "(no subject)"}</Text>
              <Caption1>
                {new Date(meeting.start).toLocaleString()} · organised by {who(meeting.organizer)}
              </Caption1>
              <Caption1 className={styles.muted}>{meeting.attendees.map(who).join(", ")}</Caption1>
              <pre className={styles.body}>{meeting.agenda || "No agenda."}</pre>
              <Caption1 className={styles.muted}>
                Meetings aren't learned from yet (meeting memory comes in a later milestone).
              </Caption1>
            </Card>
          )}
          {showStored && <StoredView storedId={showStored} />}
        </div>
      </div>
    </div>
  );
}
