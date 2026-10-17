/** Commitments (M5): the promises you made in your sent email and Teams chats (and, M6, in Teams
 * meetings), with follow-ups drafted in your voice. Shown in the web app and as the Vanimo tab in Teams.
 * Vanimo never sends: you copy or open the follow-up and send it yourself. A promise made in a meeting
 * has no conversation to follow up in. */
import {
  Badge,
  Button,
  Caption1,
  Card,
  Field,
  Input,
  makeStyles,
  Menu,
  MenuItem,
  MenuList,
  MenuPopover,
  MenuTrigger,
  MessageBar,
  MessageBarBody,
  Spinner,
  Tab,
  TabList,
  Text,
  Title3,
  tokens,
} from "@fluentui/react-components";
import { useCallback, useEffect, useState } from "react";
import type { Commitment, Draft, DraftCheck, FollowUpKind, Ledger } from "../../api/client";
import { useApi } from "../../api/context";
import { DraftView, draftErrorText, hasBlock, recheck } from "../../drafting/DraftView";
import { newChatLink } from "../TeamsPrefill";

const useStyles = makeStyles({
  stack: { display: "grid", gap: tokens.spacingVerticalL },
  row: { display: "flex", gap: tokens.spacingHorizontalM, alignItems: "center", flexWrap: "wrap" },
  item: { display: "grid", gap: tokens.spacingVerticalXS },
  muted: { color: tokens.colorNeutralForeground3 },
  quote: { margin: 0, fontStyle: "italic", color: tokens.colorNeutralForeground2 },
});

const AUDIENCE: Record<string, string> = {
  manager: "your manager",
  report: "your team",
  peer: "colleagues",
  external: "a client or partner",
  personal: "a personal contact",
};

const CHANNEL: Record<Commitment["channel"], string> = { email: "Email", chat: "Teams", meeting: "Meeting" };

const FOLLOW_UP: Record<FollowUpKind, string> = {
  done: "It's done: send it",
  late: "Running late: ask for more time",
  update: "Still on it: send an update",
};

function day(iso: string): string {
  return new Date(iso).toLocaleString(undefined, { weekday: "short", day: "numeric", month: "short", hour: "numeric", minute: "2-digit" });
}

/** Which group a promise is in now. */
export function bucket(c: Commitment, now = new Date()): "overdue" | "soon" | "later" | "undated" {
  if (!c.dueAt) return "undated";
  const due = new Date(c.dueAt).getTime();
  if (due < now.getTime()) return "overdue";
  return due < now.getTime() + 86_400_000 ? "soon" : "later";
}

const GROUPS = [
  ["overdue", "Overdue"],
  ["soon", "Due in the next day"],
  ["later", "Later"],
  ["undated", "No date given"],
] as const;

export function Commitments({ embedded = false, prefill = false }: { embedded?: boolean; prefill?: boolean }) {
  const styles = useStyles();
  const api = useApi();
  const [status, setStatus] = useState<"open" | "done" | "dismissed">("open");
  const [ledger, setLedger] = useState<Ledger | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [scanNote, setScanNote] = useState<string | null>(null);
  const [active, setActive] = useState<{ id: string; kind: FollowUpKind } | null>(null);
  const [newDate, setNewDate] = useState("");
  const [busy, setBusy] = useState(false);
  const [draft, setDraft] = useState<{ id: string; draft: Draft } | null>(null);
  const [text, setText] = useState("");
  const [checks, setChecks] = useState<DraftCheck[]>([]);
  const [confirmed, setConfirmed] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    try {
      setLedger(await api.commitments(status));
    } catch (e) {
      setError(draftErrorText(e));
    }
  }, [api, status]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  useEffect(() => {
    // Look for new promises in what you sent since the last look (at most once a minute).
    api.scanCommitments().then(
      (r) => {
        if (r.found || r.hints) {
          setScanNote(
            [r.found ? `${r.found} new promise${r.found > 1 ? "s" : ""} found` : "", r.hints ? `${r.hints} look done` : ""]
              .filter(Boolean)
              .join(" · "),
          );
          void refresh();
        }
      },
      () => undefined, // e.g. the review isn't done yet: the list explains itself
    );
  }, [api, refresh]);

  async function decide(c: Commitment, action: "done" | "dismiss" | "reopen" | "snooze") {
    try {
      await api.decideCommitment(c.id, action);
      await refresh();
    } catch (e) {
      setError(draftErrorText(e));
    }
  }

  async function followUp(c: Commitment, kind: FollowUpKind) {
    setBusy(true);
    setNotice(null);
    try {
      const d = await api.followUp(c.id, kind, newDate.trim() || null);
      setDraft({ id: c.id, draft: d });
      setText(d.text);
      setChecks(d.checks);
      setConfirmed(false);
      setActive(null);
    } catch (e) {
      setNotice(draftErrorText(e));
    } finally {
      setBusy(false);
    }
  }

  async function copy(d: Draft) {
    try {
      await navigator.clipboard.writeText(text);
      setNotice(d.channel === "chat" ? "Copied. Paste it into the Teams chat." : "Copied. Paste it into your reply.");
      if (d.id) await api.draftFeedback(d.id, { outcome: "copied" });
    } catch {
      setNotice("Couldn't copy automatically: select the text and copy it.");
    }
  }

  async function checkAgain(d: Draft) {
    try {
      // The follow-up's conversation is the promise's: the API knows it, the page doesn't (no ID here).
      const res = await api.checkText(text, d.audience.to, d.audience.cc, null, d.channel === "chat" ? "chat" : "email");
      const merged = recheck(d.checks, res.checks);
      setChecks(merged);
      setNotice(merged.length ? null : "No problems found in your text.");
    } catch (e) {
      setNotice(draftErrorText(e));
    }
  }

  async function place(d: Draft) {
    if (!d.id) return;
    try {
      const res = await api.placeDraft(d.id, text, confirmed);
      setNotice(res.webLink ? "In your Outlook Drafts folder." : "In your Drafts folder (simulated in the sample workspace).");
    } catch (e) {
      setNotice(draftErrorText(e));
    }
  }

  if (error) return <MessageBar intent="error"><MessageBarBody>{error}</MessageBarBody></MessageBar>; // prettier-ignore
  if (!ledger) return <Spinner label="Loading your promises…" />;

  const card = (c: Commitment) => (
    <Card key={c.id}>
      <div className={styles.item}>
        <div className={styles.row}>
          <Text weight="semibold">{c.what}</Text>
          <Badge appearance="tint" color="informative">{CHANNEL[c.channel]}</Badge>
          {c.looksDoneAt && c.status === "open" && (
            <Badge appearance="tint" color="success">Looks done</Badge>
          )}
        </div>
        <p className={styles.quote}>“{c.sentence}”</p>
        <Caption1 className={styles.muted}>
          {c.channel === "meeting" ? "In a meeting with " : "To "}
          {AUDIENCE[c.relationship] ?? c.relationship} · {day(c.madeAt)}
          {c.dueAt ? ` · due ${day(c.dueAt)}` : ""}
          {c.duePhrase ? ` (“${c.duePhrase}”)` : ""}
          {c.snoozedUntil && new Date(c.snoozedUntil) > new Date() ? ` · snoozed until ${day(c.snoozedUntil)}` : ""}
          {c.looksDoneAt && c.status === "open" ? ` · you wrote in the same thread on ${day(c.looksDoneAt)}` : ""}
        </Caption1>
        {c.status === "open" ? (
          <div className={styles.row}>
            <Button size="small" onClick={() => void decide(c, "done")}>Done</Button>
            {c.channel !== "meeting" && (
            <Menu>
              <MenuTrigger disableButtonEnhancement>
                <Button size="small" appearance="primary" disabled={busy}>Draft a follow-up</Button>
              </MenuTrigger>
              <MenuPopover>
                <MenuList>
                  {(Object.keys(FOLLOW_UP) as FollowUpKind[]).map((k) => (
                    <MenuItem key={k} onClick={() => (k === "done" ? void followUp(c, k) : setActive({ id: c.id, kind: k }))}>
                      {FOLLOW_UP[k]}
                    </MenuItem>
                  ))}
                </MenuList>
              </MenuPopover>
            </Menu>
            )}
            <Button size="small" appearance="subtle" onClick={() => void decide(c, "snooze")}>Remind me tomorrow</Button>
            <Button size="small" appearance="subtle" onClick={() => void decide(c, "dismiss")}>Not a promise</Button>
          </div>
        ) : (
          <div className={styles.row}>
            <Button size="small" appearance="subtle" onClick={() => void decide(c, "reopen")}>Reopen</Button>
          </div>
        )}
        {active?.id === c.id && (
          <div className={styles.row}>
            <Field label={active.kind === "late" ? "New date (optional)" : "Next update by (optional)"}>
              <Input value={newDate} maxLength={40} placeholder="Monday, 21 Oct…" onChange={(_, d) => setNewDate(d.value)} />
            </Field>
            <Button appearance="primary" disabled={busy} onClick={() => void followUp(c, active.kind)}>
              {busy ? "Drafting…" : "Draft it"}
            </Button>
            <Button appearance="subtle" onClick={() => setActive(null)}>Cancel</Button>
          </div>
        )}
        {draft?.id === c.id && (
          <DraftView
            draft={draft.draft}
            text={text}
            onTextChange={setText}
            checks={checks}
            confirmed={confirmed}
            onConfirm={setConfirmed}
            actions={
              <>
                <Button appearance="primary" disabled={hasBlock(checks) && !confirmed} onClick={() => void copy(draft.draft)}>
                  Copy
                </Button>
                {draft.draft.channel === "chat" && prefill && (draft.draft.chatUsers?.length ?? 0) > 0 && (
                  <Button
                    disabled={hasBlock(checks) && !confirmed}
                    onClick={() => window.open(newChatLink((draft.draft.chatUsers ?? []).join(","), text), "_blank", "noreferrer")}
                  >
                    Open in Teams with this text
                  </Button>
                )}
                <Button onClick={() => void checkAgain(draft.draft)}>Check my edits</Button>
                {draft.draft.channel !== "chat" && draft.draft.id && (
                  <Button disabled={hasBlock(checks) && !confirmed} onClick={() => void place(draft.draft)}>
                    Put in my Drafts folder
                  </Button>
                )}
                <Button appearance="subtle" onClick={() => setDraft(null)}>Close</Button>
              </>
            }
          />
        )}
      </div>
    </Card>
  );

  return (
    <div className={styles.stack}>
      {!embedded && (
        <div>
          <Title3 as="h2">Commitments</Title3>
          <Text as="p">
            What you promised people in your emails, Teams chats and meetings, found in what Vanimo is allowed to learn
            from. Mark them done, or let Vanimo draft the follow-up in your voice. Vanimo never sends.
          </Text>
        </div>
      )}
      <div className={styles.row}>
        <Badge appearance="tint" color={ledger.label.startsWith("Offline") ? "warning" : "brand"}>{ledger.label}</Badge>
        <Caption1 className={styles.muted}>
          {ledger.open} open · {ledger.overdue} overdue · {ledger.dueSoon} due in the next day · {ledger.capturedThisWeek} found this week
          {ledger.precision !== null
            ? ` · ${Math.round(ledger.precision * 100)}% of the ${ledger.decided} you decided on were real promises`
            : ""}
        </Caption1>
      </div>
      {scanNote && (
        <MessageBar intent="success">
          <MessageBarBody>{scanNote}</MessageBarBody>
        </MessageBar>
      )}
      {notice && (
        <MessageBar intent="info">
          <MessageBarBody>{notice}</MessageBarBody>
        </MessageBar>
      )}
      <TabList selectedValue={status} onTabSelect={(_, d) => setStatus(d.value as typeof status)}>
        <Tab value="open">Open</Tab>
        <Tab value="done">Done</Tab>
        <Tab value="dismissed">Not promises</Tab>
      </TabList>
      {ledger.items.length === 0 && (
        <Caption1>
          {status === "open"
            ? "No open promises. Vanimo looks in what you sent: run Learning first, then new mail and chats are checked each time you open this page."
            : "Nothing here yet."}
        </Caption1>
      )}
      {status === "open"
        ? GROUPS.map(([key, title]) => {
            const items = ledger.items.filter((c) => bucket(c) === key);
            return items.length ? (
              <div key={key} className={styles.stack}>
                <Text weight="semibold">{title}</Text>
                {items.map(card)}
              </div>
            ) : null;
          })
        : ledger.items.map(card)}
      {ledger.hidden > 0 && (
        <Caption1 className={styles.muted}>
          {ledger.hidden} hidden because of a rule you added; they're being deleted.
        </Caption1>
      )}
    </div>
  );
}
