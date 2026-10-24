/** Commitments (M5): the promises you made in your sent email and Teams chats (and, M6, in Teams
 * meetings), with follow-ups drafted in your voice. Shown in the web app and as the Vanimo tab in Teams.
 * Vanimo never sends: you copy or open the follow-up and send it yourself. A promise made in a meeting
 * has no conversation to follow up in.
 * Layout: a segmented filter (Open · Done · Not promises), the ledger grouped by when things are due
 * (a section header per group above a card of rows), each row led by its channel tile with the due
 * pill and icon actions on the right, and the follow-up drafted in place. A quiet footer says what the
 * promise finder runs on and how it's doing.
 * No router hooks: the Teams tab renders this without a router. Only `vt`/`tokens` colours (with light
 * fallbacks), so it also renders under Microsoft's Teams theme. */
import {
  Button,
  Field,
  Input,
  makeStyles,
  Menu,
  MenuButton,
  MenuItem,
  MenuList,
  MenuPopover,
  MenuTrigger,
  MessageBar,
  MessageBarBody,
  Tooltip,
} from "@fluentui/react-components";
import {
  ArrowUndo16Regular,
  CalendarClock16Regular,
  CalendarLtr16Regular,
  Checkmark16Regular,
  CheckmarkCircle16Regular,
  Clock16Regular,
  CalendarArrowRight16Regular,
  ClockAlarm16Regular,
  Compose16Regular,
  Dismiss16Regular,
  EyeOff16Regular,
  History16Regular,
  MailCheckmark16Regular,
  People16Regular,
  Search16Regular,
  Snooze16Regular,
  TaskListSquareLtr20Regular,
  Target16Regular,
} from "@fluentui/react-icons";
import { useCallback, useEffect, useState, type ReactNode } from "react";
import type { Commitment, Draft, DraftCheck, FollowUpKind, Ledger } from "../../api/client";
import { useApi } from "../../api/context";
import { DraftView, draftErrorText, hasBlock, recheck } from "../../drafting/DraftView";
import {
  absoluteTime,
  CHANNELS,
  EmptyState,
  EngineBadge,
  IconAction,
  IconTile,
  List,
  Page,
  PageSkeleton,
  Pill,
  relativeTime,
  Rise,
  Section,
  Segmented,
  StatusDot,
  Surface,
  typo,
  vt,
} from "../../ui";
import { newChatLink } from "../TeamsPrefill";

const PHONE = "@media (max-width: 639px)";

const useStyles = makeStyles({
  embedded: { display: "grid", gap: "24px", minWidth: 0 },
  toolbar: { display: "flex", alignItems: "center", justifyContent: "space-between", gap: "8px 16px", flexWrap: "wrap", minWidth: 0 },
  groups: { display: "grid", gap: "28px", minWidth: 0 },
  overdueIcon: { color: vt.danger },
  // One promise: channel tile · what, the sentence and its facts · due pill over the actions.
  row: {
    display: "grid",
    gridTemplateColumns: "auto minmax(0, 1fr) auto",
    columnGap: "14px",
    rowGap: "12px",
    padding: "14px 16px",
    borderTop: `1px solid ${vt.borderSubtle}`,
    ":first-child": { borderTopColor: "transparent" },
    [PHONE]: { gridTemplateColumns: "auto minmax(0, 1fr)", columnGap: "12px" },
  },
  tile: { alignSelf: "start" },
  main: { display: "grid", gap: "6px", minWidth: 0 },
  titleLine: { display: "flex", alignItems: "center", gap: "8px", flexWrap: "wrap", minWidth: 0, minHeight: "22px" },
  what: { ...typo.itemTitle, color: vt.text1, overflowWrap: "anywhere" },
  // What you actually wrote: set off by a hairline rule, like a quotation.
  quote: {
    ...typo.meta,
    color: vt.text2,
    margin: 0,
    paddingLeft: "10px",
    borderLeft: `2px solid ${vt.border}`,
    overflowWrap: "anywhere",
  },
  meta: {
    display: "flex",
    flexWrap: "wrap",
    alignItems: "center",
    gap: "4px 14px",
    ...typo.meta,
    color: vt.text2,
    minWidth: 0,
  },
  metaItem: {
    display: "inline-flex",
    alignItems: "center",
    gap: "5px",
    minWidth: 0,
    overflowWrap: "anywhere",
    "& > svg": { color: vt.text3, flexShrink: 0 },
  },
  side: {
    display: "flex",
    flexDirection: "column",
    alignItems: "flex-end",
    justifyContent: "space-between",
    gap: "12px",
    [PHONE]: {
      gridColumn: "2 / -1",
      flexDirection: "row",
      alignItems: "center",
      justifyContent: "space-between",
      flexWrap: "wrap",
      gap: "8px",
    },
  },
  actions: { display: "flex", alignItems: "center", gap: "2px", flexWrap: "wrap", justifyContent: "flex-end", [PHONE]: { marginLeft: "auto" } },
  followUp: { marginRight: "6px" },
  // The follow-up form sits in a well inside the card (never a card in a card).
  extra: {
    gridColumn: "2 / -1",
    display: "grid",
    gap: "12px",
    minWidth: 0,
    padding: "14px 16px",
    borderRadius: "8px",
    backgroundColor: vt.inset,
    border: `1px solid ${vt.borderSubtle}`,
    [PHONE]: { gridColumn: "1 / -1" },
  },
  // The drafted follow-up: a well inside the row, the draft's own parts without a second card frame.
  extraWell: {
    gridColumn: "2 / -1",
    minWidth: 0,
    padding: "14px 16px",
    borderRadius: "10px",
    backgroundColor: vt.inset,
    border: `1px solid ${vt.borderSubtle}`,
    [PHONE]: { gridColumn: "1 / -1", padding: "12px" },
  },
  extraTitle: { ...typo.cardTitle, color: vt.text1, margin: 0, display: "flex", alignItems: "center", gap: "8px", "& > svg": { color: vt.accent } },
  form: { display: "flex", alignItems: "flex-end", gap: "8px", flexWrap: "wrap" },
  field: { flex: "1 1 220px", maxWidth: "320px" },
  overdueText: {
    display: "inline-flex",
    alignItems: "center",
    gap: "4px",
    ...typo.label,
    color: vt.danger,
    whiteSpace: "nowrap",
    paddingTop: "2px",
  },
  footer: {
    display: "flex",
    alignItems: "center",
    flexWrap: "wrap",
    gap: "8px 18px",
    ...typo.meta,
    color: vt.text2,
    margin: 0,
    paddingTop: "16px",
    borderTop: `1px solid ${vt.borderSubtle}`,
  },
});

export const AUDIENCE: Record<string, string> = {
  manager: "your manager",
  report: "your team",
  peer: "colleagues",
  external: "a client or partner",
  personal: "a personal contact",
};

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

/** relativeTime, readable mid-sentence ("due tomorrow", not "due Tomorrow"). */
function rel(iso: string): string {
  const r = relativeTime(iso);
  return r === "Tomorrow" || r === "Yesterday" ? r.toLowerCase() : r;
}

/** Who the promise was made to, and where: "Email to your team", "In a meeting with your manager". */
function where(c: Commitment): string {
  const who = AUDIENCE[c.relationship] ?? c.relationship;
  if (c.channel === "meeting") return `In a meeting with ${who}`;
  return c.channel === "chat" ? `Teams chat with ${who}` : `Email to ${who}`;
}

/** A relative date in a phrase, with the exact date and time on hover. */
function When({ iso, children, className }: { iso: string; children: ReactNode; className?: string }) {
  return (
    <Tooltip content={absoluteTime(iso)} relationship="description" withArrow>
      <time dateTime={iso} className={className}>
        {children}
      </time>
    </Tooltip>
  );
}

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
  // Which commitment the notice is about (null: the page as a whole).
  const [noticeFor, setNoticeFor] = useState<string | null>(null);

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
      setNoticeFor(c.id);
      setNotice(draftErrorText(e));
    } finally {
      setBusy(false);
    }
  }

  async function copy(d: Draft) {
    setNoticeFor(draft?.id ?? null);
    try {
      await navigator.clipboard.writeText(text);
      setNotice(d.channel === "chat" ? "Copied. Paste it into the Teams chat." : "Copied. Paste it into your reply.");
      if (d.id) await api.draftFeedback(d.id, { outcome: "copied" });
    } catch {
      setNotice("Couldn't copy automatically: select the text and copy it.");
    }
  }

  async function checkAgain(d: Draft) {
    setNoticeFor(draft?.id ?? null);
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
    setNoticeFor(draft?.id ?? null);
    try {
      const res = await api.placeDraft(d.id, text, confirmed);
      setNotice(res.webLink ? "In your Outlook Drafts folder." : "In your Drafts folder (simulated in the sample workspace).");
    } catch (e) {
      setNotice(draftErrorText(e));
    }
  }

  const frame = (children: ReactNode) =>
    embedded ? (
      <div className={styles.embedded}>{children}</div>
    ) : (
      <Page
        title="Commitments"
        description="What you promised people in your emails, Teams chats and meetings, with follow-ups drafted in your voice. Vanimo never sends."
        info="Found in what Vanimo is allowed to learn from. Mark a promise done, snooze it, or let Vanimo draft the follow-up in your voice: you copy it or put it in your Drafts folder and send it yourself. Promises made in meetings have no conversation to follow up in."
      >
        {children}
      </Page>
    );

  if (error)
    return frame(
      <MessageBar intent="error">
        <MessageBarBody>{error}</MessageBarBody>
      </MessageBar>,
    );
  if (!ledger) return <PageSkeleton label="Loading your promises…" />;

  // A notice about the follow-up being edited sits with it; anything else goes above the list.
  const noticeInDraft = Boolean(draft && noticeFor === draft.id && ledger.items.some((c) => c.id === draft.id));
  const noticeBar = notice && (
    <MessageBar intent="info">
      <MessageBarBody>{notice}</MessageBarBody>
    </MessageBar>
  );

  const row = (c: Commitment) => {
    const open = c.status === "open";
    const channel = CHANNELS[c.channel];
    const snoozed = Boolean(c.snoozedUntil && new Date(c.snoozedUntil) > new Date());
    const when = bucket(c);
    return (
      <li key={c.id} className={styles.row}>
        <IconTile icon={channel.icon} tone={channel.tone} size={32} className={styles.tile} />
        <div className={styles.main}>
          <div className={styles.titleLine}>
            <span className={styles.what}>{c.what}</span>
            {c.looksDoneAt && open && (
              <Pill tone="success" icon={<CheckmarkCircle16Regular />}>
                Looks done
              </Pill>
            )}
            {snoozed && open && <Pill icon={<Snooze16Regular />}>Snoozed</Pill>}
          </div>
          <p className={styles.quote}>“{c.sentence}”</p>
          <div className={styles.meta}>
            <span className={styles.metaItem}>
              <People16Regular aria-hidden />
              {where(c)}
            </span>
            <span className={styles.metaItem}>
              <History16Regular aria-hidden />
              <span>
                Made <When iso={c.madeAt}>{rel(c.madeAt)}</When>
              </span>
            </span>
            {snoozed && c.snoozedUntil && (
              <span className={styles.metaItem}>
                <Snooze16Regular aria-hidden />
                Snoozed until {day(c.snoozedUntil)}
              </span>
            )}
            {c.looksDoneAt && open && (
              <span className={styles.metaItem}>
                <MailCheckmark16Regular aria-hidden />
                You wrote in the same thread on {day(c.looksDoneAt)}
              </span>
            )}
            {!open && c.statusAt && (
              <span className={styles.metaItem}>
                {c.status === "done" ? <Checkmark16Regular aria-hidden /> : <Dismiss16Regular aria-hidden />}
                <span>
                  {c.status === "done" ? "Marked done" : "Marked not a promise"} <When iso={c.statusAt}>{rel(c.statusAt)}</When>
                </span>
              </span>
            )}
          </div>
        </div>
        <div className={styles.side}>
          {open && c.dueAt ? (
            <When iso={c.dueAt}>
              {when === "overdue" ? (
                <span className={styles.overdueText}>
                  <ClockAlarm16Regular aria-hidden />
                  Was due {rel(c.dueAt)}
                </span>
              ) : (
                <Pill tone={when === "soon" ? "warning" : "neutral"} icon={<Clock16Regular />}>
                  Due {rel(c.dueAt)}
                </Pill>
              )}
            </When>
          ) : (
            <span aria-hidden />
          )}
          {open ? (
            <div className={styles.actions}>
              {c.channel !== "meeting" && (
                <Menu>
                  <MenuTrigger disableButtonEnhancement>
                    <MenuButton size="small" icon={<Compose16Regular />} disabled={busy} className={styles.followUp}>
                      Draft a follow-up
                    </MenuButton>
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
              <IconAction icon={<Checkmark16Regular />} label="Mark done" onClick={() => void decide(c, "done")} />
              <IconAction icon={<CalendarArrowRight16Regular />} label="Remind me tomorrow" onClick={() => void decide(c, "snooze")} />
              <IconAction icon={<Dismiss16Regular />} label="Not a promise" onClick={() => void decide(c, "dismiss")} />
            </div>
          ) : (
            <div className={styles.actions}>
              <IconAction icon={<ArrowUndo16Regular />} label="Reopen" onClick={() => void decide(c, "reopen")} />
            </div>
          )}
        </div>
        {active?.id === c.id && (
          <Rise visible appear>
            <div className={styles.extra}>
              <p className={styles.extraTitle}>
                <Compose16Regular aria-hidden />
                {FOLLOW_UP[active.kind]}
              </p>
              <div className={styles.form}>
                <Field label={active.kind === "late" ? "New date (optional)" : "Next update by (optional)"} className={styles.field}>
                  <Input
                    value={newDate}
                    maxLength={40}
                    placeholder="Monday, 21 Oct…"
                    contentBefore={<CalendarLtr16Regular aria-hidden />}
                    onChange={(_, d) => setNewDate(d.value)}
                  />
                </Field>
                <Button
                  appearance={draft?.id === c.id ? "secondary" : "primary"}
                  disabled={busy}
                  onClick={() => void followUp(c, active.kind)}
                >
                  {busy ? "Drafting…" : "Draft it"}
                </Button>
                <Button appearance="subtle" onClick={() => setActive(null)}>Cancel</Button>
              </div>
            </div>
          </Rise>
        )}
        {draft?.id === c.id && (
          <Rise visible appear>
            <div className={styles.extraWell} role="group" aria-label="Follow-up draft">
              <DraftView
                flat
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
              {noticeInDraft && noticeBar}
            </div>
          </Rise>
        )}
      </li>
    );
  };

  const offline = ledger.label.startsWith("Offline");
  let body: ReactNode;
  if (ledger.items.length === 0) {
    body = (
      <Surface padding="l">
        <EmptyState
          center
          headingLevel={2}
          icon={<TaskListSquareLtr20Regular />}
          title={status === "open" ? "No open promises" : status === "done" ? "Nothing marked done yet" : "Nothing marked as not a promise"}
        >
          {status === "open"
            ? "Vanimo looks in what you sent: run Learning first, then new mail and chats are checked each time you open this page."
            : "Nothing here yet."}
        </EmptyState>
      </Surface>
    );
  } else if (status === "open") {
    body = (
      <div className={styles.groups}>
        {GROUPS.map(([key, title]) => {
          const items = ledger.items.filter((c) => bucket(c) === key);
          if (!items.length) return null;
          const icon =
            key === "overdue" ? (
              <ClockAlarm16Regular className={styles.overdueIcon} />
            ) : key === "undated" ? (
              <CalendarLtr16Regular />
            ) : (
              <CalendarClock16Regular />
            );
          return (
            <Section key={key} title={title} count={items.length} icon={icon} aria-label={title}>
              <List bordered label={title}>
                {items.map(row)}
              </List>
            </Section>
          );
        })}
      </div>
    );
  } else {
    body = (
      <List bordered label={status === "done" ? "Done" : "Not promises"}>
        {ledger.items.map(row)}
      </List>
    );
  }

  return frame(
    <>
      <div className={styles.toolbar}>
        <Segmented
          label="Show"
          value={status}
          onChange={setStatus}
          segments={[
            { value: "open", label: "Open", count: ledger.open },
            { value: "done", label: "Done" },
            { value: "dismissed", label: "Not promises" },
          ]}
        />
        {scanNote && <StatusDot tone="success">{scanNote}</StatusDot>}
      </div>
      {!noticeInDraft && noticeBar}
      {body}
      <div className={styles.footer}>
        <EngineBadge offline={offline} detail={ledger.label} />
        <span className={styles.metaItem}>
          <ClockAlarm16Regular aria-hidden />
          {`${ledger.overdue} overdue`}
        </span>
        <span className={styles.metaItem}>
          <Clock16Regular aria-hidden />
          {`${ledger.dueSoon} due in the next day`}
        </span>
        <span className={styles.metaItem}>
          <Search16Regular aria-hidden />
          {`${ledger.capturedThisWeek} found this week`}
        </span>
        {ledger.precision !== null && (
          <span className={styles.metaItem}>
            <Target16Regular aria-hidden />
            {`${Math.round(ledger.precision * 100)}% of the ${ledger.decided} you decided on were real promises`}
          </span>
        )}
        {ledger.hidden > 0 && (
          <span className={styles.metaItem}>
            <EyeOff16Regular aria-hidden />
            {`${ledger.hidden} hidden because of a rule you added; they're being deleted.`}
          </span>
        )}
      </div>
    </>,
  );
}
