/** Meetings (M6): what your Teams meetings decided, asked for and promised, read from Microsoft's own
 * transcripts, and questions about them answered with citations. Shown in the web app and as a tab in
 * Teams. Only internal Teams meetings with transcription on; your exclusions apply before anything is
 * read. Answers quote your notes and say where they come from, or say they found nothing.
 * Layout: the ask bar first; the answer in reading type with numbered citation chips and a sources
 * list; then the meetings (grouped by day) beside the open meeting's notes and transcript.
 * No router hooks: the Teams tab renders this without a router. */
import {
  Button,
  Field,
  Input,
  makeStyles,
  mergeClasses,
  shorthands,
  MessageBar,
  MessageBarBody,
  Select,
  Spinner,
  tokens,
  Tooltip,
} from "@fluentui/react-components";
import { CalendarLtr20Regular, Delete16Regular, Dismiss20Regular, Search16Regular } from "@fluentui/react-icons";
import { useCallback, useEffect, useRef, useState, type ReactNode } from "react";
import type {
  MeetingAnswer,
  MeetingCitation,
  MeetingDetail,
  MeetingList,
  MeetingNote,
  MeetingScan,
  NoteKind,
} from "../../api/client";
import { useApi } from "../../api/context";
import { draftErrorText } from "../../drafting/DraftView";
import { EmptyState, hoverTransition, List, ListRow, Page, PageSkeleton, Pill, Rise, StatusDot, Surface, typo, vt } from "../../ui";

const useStyles = makeStyles({
  embedded: { display: "grid", gap: "24px", minWidth: 0 },
  context: { display: "flex", alignItems: "center", gap: "8px 12px", flexWrap: "wrap" },
  // Ask
  ask: { display: "grid", gap: "12px", minWidth: 0 },
  askForm: { display: "flex", alignItems: "flex-end", gap: "8px", flexWrap: "wrap" },
  askField: { flex: "1 1 320px", minWidth: 0 },
  examples: { display: "flex", alignItems: "center", gap: "6px", flexWrap: "wrap" },
  examplesLabel: { ...typo.meta, color: vt.text3, marginRight: "2px" },
  answer: {
    display: "grid",
    gap: "16px",
    minWidth: 0,
    padding: "20px 24px",
    border: `1px solid ${tokens.colorNeutralStroke2}`,
    borderRadius: tokens.borderRadiusXLarge,
    backgroundColor: tokens.colorNeutralBackground1,
    "@media (max-width: 639px)": { padding: "16px" },
  },
  answerWhen: { ...typo.meta, color: vt.text3, margin: 0 },
  answerText: { ...typo.reading, color: vt.text1, margin: 0, whiteSpace: "pre-wrap", overflowWrap: "anywhere", maxWidth: "72ch" },
  cite: {
    display: "inline-grid",
    placeItems: "center",
    minWidth: "18px",
    height: "18px",
    padding: "0 4px",
    margin: "0 1px",
    verticalAlign: "1px",
    borderRadius: tokens.borderRadiusSmall,
    border: `1px solid ${tokens.colorNeutralStroke2}`,
    backgroundColor: vt.inset,
    color: vt.text2,
    fontFamily: tokens.fontFamilyBase,
    fontSize: "12px",
    lineHeight: "16px",
    fontWeight: 500,
    ...typo.tabular,
    cursor: "pointer",
    ...hoverTransition,
    "@media (hover: hover)": {
      ":hover": { backgroundColor: vt.accentTint, color: vt.accentTintText, ...shorthands.borderColor(vt.accent) },
    },
    ":focus-visible": { outline: `2px solid ${tokens.colorStrokeFocus2}`, outlineOffset: "1px" },
  },
  sources: { display: "grid", gap: "8px", minWidth: 0 },
  sourcesTitle: { ...typo.label, color: vt.text2, margin: 0 },
  sourceList: { display: "grid", margin: 0, padding: 0, listStyle: "none" },
  source: {
    display: "grid",
    gridTemplateColumns: "auto minmax(0, 1fr) auto",
    gap: "4px 12px",
    alignItems: "start",
    padding: "10px 0",
    borderTop: `1px solid ${tokens.colorNeutralStroke3}`,
    "@media (max-width: 639px)": { gridTemplateColumns: "auto minmax(0, 1fr)" },
  },
  sourceChip: {
    display: "inline-grid",
    placeItems: "center",
    minWidth: "18px",
    height: "18px",
    padding: "0 4px",
    marginTop: "1px",
    borderRadius: tokens.borderRadiusSmall,
    border: `1px solid ${tokens.colorNeutralStroke2}`,
    backgroundColor: vt.inset,
    color: vt.text2,
    fontSize: "12px",
    lineHeight: "16px",
    fontWeight: 500,
    ...typo.tabular,
  },
  sourceBody: { display: "grid", gap: "2px", minWidth: 0 },
  sourceTitle: { ...typo.itemTitle, color: vt.text1 },
  sourceMeta: { ...typo.meta, ...typo.tabular, color: vt.text3 },
  sourceQuote: { ...typo.meta, color: vt.text2, overflowWrap: "anywhere" },
  sourceAction: { "@media (max-width: 639px)": { gridColumn: "2 / -1", justifySelf: "start" } },
  candidates: { display: "flex", alignItems: "center", gap: "8px", flexWrap: "wrap" },
  candidatesLabel: { ...typo.itemTitle, color: vt.text1 },
  answerLabel: {
    ...typo.meta,
    color: vt.text3,
    margin: 0,
    paddingTop: "12px",
    borderTop: `1px solid ${tokens.colorNeutralStroke3}`,
  },
  // Meetings and the open meeting
  split: {
    display: "grid",
    gridTemplateColumns: "minmax(0, 1fr)",
    gap: "24px",
    alignItems: "start",
    "@media (min-width: 1200px)": {
      gridTemplateColumns: "340px minmax(0, 1fr)",
      gridTemplateAreas: '"list detail"',
    },
  },
  listPane: { display: "grid", gap: "12px", minWidth: 0, "@media (min-width: 1200px)": { gridArea: "list" } },
  detailPane: { minWidth: 0, "@media (min-width: 1200px)": { gridArea: "detail" } },
  placeholder: {
    display: "none",
    ...typo.meta,
    color: vt.text2,
    margin: 0,
    "@media (min-width: 1200px)": {
      display: "flex",
      alignItems: "center",
      gap: "10px",
      gridArea: "detail",
      padding: "20px 24px",
      border: `1px solid ${tokens.colorNeutralStroke3}`,
      borderRadius: tokens.borderRadiusXLarge,
    },
  },
  placeholderIcon: { color: vt.text3, flexShrink: 0 },
  h2: { ...typo.sectionTitle, color: vt.text1, margin: 0, display: "flex", alignItems: "baseline", gap: "8px" },
  count: { ...typo.meta, ...typo.tabular, color: vt.text3, fontWeight: 400 },
  dayHead: {
    ...typo.label,
    color: vt.text2,
    margin: 0,
    padding: "6px 16px",
    backgroundColor: tokens.colorNeutralBackground2,
    borderTop: `1px solid ${tokens.colorNeutralStroke3}`,
  },
  rowMeta: { display: "inline-flex", alignItems: "center", gap: "6px", flexWrap: "wrap", ...typo.tabular },
  hidden: { ...typo.meta, color: vt.text2, margin: 0 },
  // Meeting detail
  detail: { display: "grid", gap: "24px", minWidth: 0 },
  detailHead: { display: "grid", gridTemplateColumns: "minmax(0, 1fr) auto", gap: "12px", alignItems: "start" },
  detailTitle: { ...typo.sectionTitle, color: vt.text1, margin: 0, overflowWrap: "anywhere" },
  detailMeta: { display: "flex", alignItems: "center", gap: "6px 8px", flexWrap: "wrap", ...typo.meta, ...typo.tabular, color: vt.text2, margin: "4px 0 0" },
  detailNote: { ...typo.meta, color: vt.text2, margin: 0 },
  block: { display: "grid", gap: "8px", minWidth: 0 },
  h3: { ...typo.itemTitle, color: vt.text1, margin: 0, display: "flex", alignItems: "baseline", gap: "8px" },
  notes: { display: "grid", margin: 0, padding: 0, listStyle: "none" },
  note: {
    display: "grid",
    gridTemplateColumns: "minmax(0, 1fr) auto",
    gap: "4px 12px",
    alignItems: "start",
    padding: "8px 0",
    borderTop: `1px solid ${tokens.colorNeutralStroke3}`,
    ":first-child": { borderTop: "none", paddingTop: 0 },
  },
  noteBody: { display: "grid", gap: "2px", minWidth: 0 },
  noteText: { ...typo.body, color: vt.text1, overflowWrap: "anywhere" },
  noteDismissed: { color: vt.text3, textDecorationLine: "line-through" },
  noteMeta: { ...typo.meta, ...typo.tabular, color: vt.text3 },
  transcript: {
    position: "relative",
    display: "grid",
    gap: "2px",
    margin: 0,
    padding: "4px",
    listStyle: "none",
    maxHeight: "440px",
    overflowY: "auto",
    backgroundColor: vt.inset,
    borderRadius: tokens.borderRadiusLarge,
  },
  turn: {
    display: "grid",
    gridTemplateColumns: "72px minmax(0, 1fr)",
    gap: "12px",
    padding: "6px 8px",
    borderRadius: tokens.borderRadiusMedium,
    "@media (max-width: 639px)": { gridTemplateColumns: "minmax(0, 1fr)", gap: "2px" },
  },
  turnFocus: { backgroundColor: vt.accentTint },
  turnTime: { ...typo.meta, ...typo.tabular, color: vt.text2, paddingTop: "3px" },
  turnBody: { display: "grid", gap: "2px", minWidth: 0 },
  turnSpeaker: { ...typo.label, color: vt.text2 },
  turnText: { ...typo.reading, color: vt.text1, overflowWrap: "anywhere" },
  footer: {
    display: "grid",
    gap: "16px",
    paddingTop: "16px",
    borderTop: `1px solid ${tokens.colorNeutralStroke3}`,
  },
  fixRow: { display: "flex", alignItems: "flex-end", gap: "8px 12px", flexWrap: "wrap" },
  fixField: { flex: "1 1 180px", maxWidth: "260px" },
  forget: { display: "flex", alignItems: "center", gap: "8px 12px", flexWrap: "wrap" },
  forgetText: { ...typo.meta, color: vt.text1, margin: 0, flex: "1 1 260px" },
  dangerText: {
    ":enabled": { color: vt.danger },
    ":enabled:hover": { color: vt.danger },
    ":enabled:hover:active": { color: vt.danger },
  },
  dangerPrimary: {
    backgroundColor: tokens.colorStatusDangerBackground3,
    color: tokens.colorNeutralForegroundOnBrand,
    ":hover": { backgroundColor: tokens.colorStatusDangerBackground3Hover, color: tokens.colorNeutralForegroundOnBrand },
    ":hover:active": { backgroundColor: tokens.colorStatusDangerBackground3Pressed, color: tokens.colorNeutralForegroundOnBrand },
  },
});

export const NOTE_LABEL: Record<NoteKind, [string, string]> = {
  decision: ["Decision", "Decisions"],
  requirement: ["Requirement", "Requirements"],
  action_item: ["Action item", "Action items"],
  commitment: ["Promise", "Promises"],
  open_question: ["Open question", "Open questions"],
  risk: ["Risk", "Risks"],
  idea: ["Idea", "Ideas"],
};
const ORDER: NoteKind[] = ["decision", "requirement", "action_item", "commitment", "open_question", "risk", "idea"];
const EXAMPLES = [
  "What did the client ask for last week?",
  "What did we decide yesterday?",
  "What did I promise in meetings?",
];

function when(iso: string): string {
  return new Date(iso).toLocaleString(undefined, { weekday: "short", day: "numeric", month: "short", hour: "numeric", minute: "2-digit" });
}

function clock(iso: string): string {
  return new Date(iso).toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit", second: "2-digit" });
}

function hm(iso: string): string {
  return new Date(iso).toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit" });
}

/** "Today", "Yesterday", "Tuesday", "13 Oct", "13 Oct 2025": the heading of a day's meetings. */
function dayLabel(iso: string, now = new Date()): string {
  const d = new Date(iso);
  const start = (x: Date) => new Date(x.getFullYear(), x.getMonth(), x.getDate()).getTime();
  const diff = Math.round((start(now) - start(d)) / 86_400_000);
  if (diff === 0) return "Today";
  if (diff === 1) return "Yesterday";
  if (diff > 1 && diff < 7) return d.toLocaleDateString(undefined, { weekday: "long" });
  return d.toLocaleDateString(undefined, {
    day: "numeric",
    month: "short",
    ...(d.getFullYear() === now.getFullYear() ? {} : { year: "numeric" }),
  });
}

/** The notes summary of a meeting: "2 decisions · 1 requirement". */
export function noteSummary(notes: MeetingList["items"][number]["notes"]): string {
  const parts = ORDER.filter((k) => notes[k]).map((k) => `${notes[k]} ${NOTE_LABEL[k][notes[k] === 1 ? 0 : 1].toLowerCase()}`);
  return parts.join(" · ") || "No notes";
}

/** What the last look for new transcripts found, in plain words (null: nothing worth saying). */
export function scanText(r: MeetingScan): string | null {
  if (r.off) return "Meeting memory is off for your organisation.";
  if (r.unavailable === "disabled")
    return "Your organisation hasn't allowed apps to read Teams transcripts yet, so Vanimo can't remember meetings. Ask your Teams admin.";
  if (r.unavailable === "permission") return "Vanimo doesn't have permission to read meeting transcripts yet. Ask your admin.";
  const parts: string[] = [];
  if (r.stored) parts.push(`${r.stored} new meeting${r.stored > 1 ? "s" : ""} remembered`);
  if (r.promises) parts.push(`${r.promises} of your promises added to Commitments`);
  if (r.waiting) parts.push(`${r.waiting} waiting for a transcript`);
  if (r.leftOut) parts.push(`${r.leftOut} part${r.leftOut > 1 ? "s" : ""} left out (people not on the invite, or text that couldn't be made safe)`);
  return parts.length ? parts.join(" · ") : null;
}

/** The answer's text with each "[n]" turned into a citation chip that opens the cited moment. */
function AnswerText({ text, citations, onCite }: { text: string; citations: MeetingCitation[]; onCite: (c: MeetingCitation) => void }) {
  const s = useStyles();
  const byN = new Map(citations.map((c) => [c.n, c]));
  return (
    <>
      {text.split(/(\[\d+\])/).map((part, i) => {
        const m = /^\[(\d+)\]$/.exec(part);
        const c = m ? byN.get(Number(m[1])) : undefined;
        if (!c) return part;
        return (
          <Tooltip key={i} content={`${c.speaker}, ${clock(c.at)}: “${c.quote}”`} relationship="description" withArrow>
            <button type="button" className={s.cite} aria-label={`Source ${c.n}: ${c.title}`} onClick={() => onCite(c)}>
              {c.n}
            </button>
          </Tooltip>
        );
      })}
    </>
  );
}

export function Meetings({ embedded = false }: { embedded?: boolean }) {
  const styles = useStyles();
  const api = useApi();
  const [list, setList] = useState<MeetingList | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [scanNote, setScanNote] = useState<string | null>(null);
  const [question, setQuestion] = useState("");
  const [asking, setAsking] = useState(false);
  const [answer, setAnswer] = useState<MeetingAnswer | null>(null);
  const [detail, setDetail] = useState<MeetingDetail | null>(null);
  const detailRef = useRef<HTMLDivElement>(null);
  const opened = useRef<string | null>(null);
  const moveFocus = useRef(false);
  const [focusTurn, setFocusTurn] = useState<number | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    try {
      setList(await api.meetings());
    } catch (e) {
      setError(draftErrorText(e));
    }
  }, [api]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  useEffect(() => {
    // Read the transcripts of meetings that ended since the last look (at most once a minute).
    api.scanMeetings().then(
      (r) => {
        setScanNote(scanText(r));
        if (r.stored) void refresh();
      },
      () => undefined, // e.g. the review isn't done yet: the list explains itself
    );
  }, [api, refresh]);

  async function ask(q: string, meetingId: string | null = null) {
    if (!q.trim()) return;
    setAsking(true);
    setNotice(null);
    try {
      setAnswer(await api.askMeetings(q.trim(), meetingId));
    } catch (e) {
      setNotice(draftErrorText(e));
    } finally {
      setAsking(false);
    }
  }

  async function open(id: string, turn: number | null = null) {
    try {
      setDetail(await api.meeting(id));
      setFocusTurn(turn);
      if (opened.current !== id) {
        opened.current = id;
        moveFocus.current = true;
      }
    } catch (e) {
      setNotice(draftErrorText(e));
    }
  }

  async function decide(note: MeetingNote) {
    if (!detail) return;
    try {
      await api.decideNote(note.id, note.status === "active" ? "dismiss" : "restore");
      await open(detail.id, focusTurn);
      await refresh();
    } catch (e) {
      setNotice(draftErrorText(e));
    }
  }

  // A newly opened meeting takes focus (its title) and scrolls into view; refreshes of the same one don't.
  useEffect(() => {
    if (!detail) {
      opened.current = null;
      return;
    }
    if (!moveFocus.current) return;
    moveFocus.current = false;
    const title = detailRef.current?.querySelector<HTMLElement>("h2");
    if (title) {
      title.tabIndex = -1;
      title.focus({ preventScroll: true });
      title.scrollIntoView?.({ block: "start", behavior: "auto" });
    }
  }, [detail]);

  const frame = (children: ReactNode) =>
    embedded ? (
      <div className={styles.embedded}>{children}</div>
    ) : (
      <Page
        title="Meetings"
        width="wide"
        description="What your Teams meetings decided, asked for and promised, read from Microsoft's own transcripts of internal meetings you were invited to. Ask a question and every answer says which meeting and when it was said."
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
  if (!list) return <PageSkeleton label="Loading your meetings…" />;

  // Meetings by day, in the order the API gives them (newest first).
  const days: Array<{ label: string; items: MeetingList["items"] }> = [];
  for (const m of list.items) {
    const label = dayLabel(m.startsAt);
    const last = days[days.length - 1];
    if (last && last.label === label) last.items.push(m);
    else days.push({ label, items: [m] });
  }

  return frame(
    <>
      <div className={styles.context}>
        <StatusDot tone={list.label.startsWith("Offline") ? "warning" : "neutral"}>{list.label}</StatusDot>
        {!list.on && <Pill tone="danger">Off for your organisation</Pill>}
      </div>
      {scanNote && (
        <MessageBar intent="info">
          <MessageBarBody>{scanNote}</MessageBarBody>
        </MessageBar>
      )}
      {notice && (
        <MessageBar intent="warning">
          <MessageBarBody>{notice}</MessageBarBody>
        </MessageBar>
      )}

      <div className={styles.ask}>
        <form
          className={styles.askForm}
          onSubmit={(e) => {
            e.preventDefault();
            void ask(question);
          }}
        >
          <Field label="Ask about your meetings" className={styles.askField}>
            <Input
              value={question}
              maxLength={300}
              contentBefore={<Search16Regular aria-hidden />}
              placeholder="What did the client ask for in Tuesday's meeting?"
              onChange={(_, d) => setQuestion(d.value)}
            />
          </Field>
          <Button
            type="submit"
            appearance="primary"
            icon={asking ? <Spinner size="extra-tiny" /> : undefined}
            disabled={asking || !list.on || question.trim().length < 3}
          >
            {asking ? "Looking…" : "Ask"}
          </Button>
        </form>
        <div className={styles.examples}>
          <span className={styles.examplesLabel}>Try</span>
          {EXAMPLES.map((q) => (
            <Button key={q} size="small" shape="circular" disabled={!list.on} onClick={() => { setQuestion(q); void ask(q); }}>
              {q}
            </Button>
          ))}
        </div>

        {answer && (
          <Rise visible appear>
            <div className={styles.answer} role="region" aria-label="Answer">
              {answer.when && <p className={styles.answerWhen}>Looked at: {answer.when}</p>}
              <p className={styles.answerText}>
                <AnswerText text={answer.answer} citations={answer.citations} onCite={(c) => void open(c.meetingId, c.turn)} />
              </p>
              {answer.citations.length > 0 && (
                <div className={styles.sources}>
                  <h2 className={styles.sourcesTitle}>Sources</h2>
                  <ol className={styles.sourceList} aria-label="Sources">
                    {answer.citations.map((c) => (
                      <li key={c.n} value={c.n} className={styles.source}>
                        <span className={styles.sourceChip} aria-hidden>
                          {c.n}
                        </span>
                        <span className={styles.sourceBody}>
                          <span className={styles.sourceTitle}>{c.title}</span>
                          <span className={styles.sourceMeta}>
                            {when(c.meetingStart)} · {clock(c.at)}–{clock(c.endAt)}
                          </span>
                          <span className={styles.sourceQuote}>
                            {c.speaker}: “{c.quote}”
                          </span>
                        </span>
                        <Button
                          size="small"
                          appearance="subtle"
                          className={styles.sourceAction}
                          onClick={() => void open(c.meetingId, c.turn)}
                        >
                          Show in meeting
                        </Button>
                      </li>
                    ))}
                  </ol>
                </div>
              )}
              {answer.candidates.length > 0 && (
                <div className={styles.candidates}>
                  <span className={styles.candidatesLabel}>{answer.clarify ? "Which meeting?" : "Close matches:"}</span>
                  {answer.candidates.map((m) => (
                    <Button key={m.id} size="small" onClick={() => void ask(question, m.id)}>
                      {m.title} ({when(m.startsAt)})
                    </Button>
                  ))}
                </div>
              )}
              <p className={styles.answerLabel}>{answer.label}. Check anything important against the meeting.</p>
            </div>
          </Rise>
        )}
      </div>

      <div className={styles.split}>
        <section className={styles.listPane} aria-labelledby="meetings-list-title">
          <h2 id="meetings-list-title" className={styles.h2}>
            Remembered meetings
            <span className={styles.count}>{list.items.length}</span>
          </h2>
          {list.items.length === 0 ? (
            <EmptyState icon={<CalendarLtr20Regular />} title={list.on ? "No meetings yet" : "Meeting memory is off"}>
              {list.on
                ? "No meetings yet. Vanimo reads the transcripts of internal Teams meetings that had transcription on, after they end, each time you open this page."
                : "Your organisation turned meeting memory off."}
            </EmptyState>
          ) : (
            <List bordered label="Remembered meetings">
              {days.map((d, i) => (
                <MeetingDay key={`${i}-${d.label}`} label={d.label}>
                  {d.items.map((m) => (
                    <ListRow
                      key={m.id}
                      wrap
                      selected={detail?.id === m.id}
                      onClick={() => void open(m.id)}
                      title={m.title}
                      meta={
                        <span className={styles.rowMeta}>
                          <span>
                            {hm(m.startsAt)}–{hm(m.endsAt)} · {noteSummary(m.notes)}
                          </span>
                          {m.external && <Pill>With people outside</Pill>}
                          {m.attribution === "unattributed" && <Pill tone="warning">No speaker names</Pill>}
                        </span>
                      }
                    />
                  ))}
                </MeetingDay>
              ))}
            </List>
          )}
          {list.hidden > 0 && (
            <p className={styles.hidden}>{list.hidden} hidden because of a rule you added; they're being deleted.</p>
          )}
        </section>

        {detail ? (
          <div className={styles.detailPane} ref={detailRef}>
            <MeetingView
              key={`${detail.id}:${detail.transcript.map((t) => t.speakerId).join(",")}`}
              detail={detail}
              focusTurn={focusTurn}
              onDecide={(n) => void decide(n)}
              onClose={() => setDetail(null)}
              onChanged={async (forgotten) => {
                if (forgotten) setDetail(null);
                else await open(detail.id, focusTurn);
                await refresh();
              }}
              onError={setNotice}
            />
          </div>
        ) : (
          list.items.length > 0 && (
            <p className={styles.placeholder}>
              <CalendarLtr20Regular className={styles.placeholderIcon} aria-hidden />
              Pick a meeting to read its notes and transcript, or ask a question above.
            </p>
          )
        )}
      </div>
    </>,
  );
}

/** A day's heading inside the meetings list, followed by that day's rows. */
function MeetingDay({ label, children }: { label: string; children: ReactNode }) {
  const styles = useStyles();
  return (
    <>
      <li>
        <h3 className={styles.dayHead}>{label}</h3>
      </li>
      {children}
    </>
  );
}

function MeetingView({
  detail,
  focusTurn,
  onDecide,
  onClose,
  onChanged,
  onError,
}: {
  detail: MeetingDetail;
  focusTurn: number | null;
  onDecide: (n: MeetingNote) => void;
  onClose: () => void;
  onChanged: (forgotten: boolean) => Promise<void>;
  onError: (text: string) => void;
}) {
  const styles = useStyles();
  const api = useApi();
  const speakers = detail.people.filter((p) => detail.transcript.some((t) => t.speakerId === p.id) || detail.notesList.some((n) => n.speakerId === p.id));
  const [from, setFrom] = useState(speakers[0]?.id ?? "");
  const [to, setTo] = useState("");
  const [confirmForget, setConfirmForget] = useState(false);
  const transcriptRef = useRef<HTMLOListElement>(null);

  // Bring the cited moment into view inside the transcript (no page jump, no animation).
  useEffect(() => {
    const box = transcriptRef.current;
    if (!box || focusTurn === null) return;
    const turn = box.querySelector<HTMLElement>(`[data-turn="${focusTurn}"]`);
    if (turn) box.scrollTop = Math.max(0, turn.offsetTop - 8);
  }, [focusTurn, detail]);

  async function fixSpeaker() {
    try {
      await api.correctSpeaker(detail.id, from, to || null);
      await onChanged(false);
    } catch (e) {
      onError(draftErrorText(e));
    }
  }

  async function forget() {
    try {
      await api.forgetMeeting(detail.id);
      await onChanged(true);
    } catch (e) {
      onError(draftErrorText(e));
    }
  }

  return (
    <Surface as="section" padding="l" aria-label="Meeting" className={styles.detail}>
      <div className={styles.detailHead}>
        <div>
          <h2 className={styles.detailTitle}>{detail.title}</h2>
          <p className={styles.detailMeta}>
            <span>
              {when(detail.startsAt)}–{hm(detail.endsAt)}
            </span>
            {detail.external && <Pill>With people outside</Pill>}
          </p>
        </div>
        <Tooltip content="Close" relationship="label">
          <Button appearance="subtle" icon={<Dismiss20Regular />} onClick={onClose} />
        </Tooltip>
      </div>
      {detail.attribution === "unattributed" && (
        <p className={styles.detailNote}>Speaker names were off for this meeting, so notes don't say who said what.</p>
      )}
      {ORDER.map((kind) => {
        const notes = detail.notesList.filter((n) => n.kind === kind);
        return notes.length ? (
          <div key={kind} className={styles.block}>
            <h3 className={styles.h3}>
              {NOTE_LABEL[kind][1]}
              <span className={styles.count}>{notes.length}</span>
            </h3>
            <ul className={styles.notes}>
              {notes.map((n) => (
                <li key={n.id} className={styles.note}>
                  <span className={styles.noteBody}>
                    <span className={mergeClasses(styles.noteText, n.status === "dismissed" && styles.noteDismissed)}>
                      {n.text}
                      {n.owner ? ` — for ${n.owner}` : ""}
                      {n.dueAt ? ` (due ${when(n.dueAt)})` : ""}
                    </span>
                    <span className={styles.noteMeta}>
                      {n.speaker}, {clock(n.saidAt)}
                      {n.status === "dismissed" ? " · marked not right" : ""}
                    </span>
                  </span>
                  <Button size="small" appearance="subtle" onClick={() => onDecide(n)}>
                    {n.status === "active" ? "Not right" : "Restore"}
                  </Button>
                </li>
              ))}
            </ul>
          </div>
        ) : null;
      })}
      {detail.transcript.length > 0 ? (
        <div className={styles.block}>
          <h3 className={styles.h3}>Transcript</h3>
          <p className={styles.detailNote}>
            Kept until {detail.transcriptUntil ? new Date(detail.transcriptUntil).toLocaleDateString() : "—"}; then only the
            notes stay. Names you excluded and never-send words are never stored.
          </p>
          <ol className={styles.transcript} ref={transcriptRef} aria-label="Transcript">
            {detail.transcript.map((t, i) => (
              <li
                key={t.turn}
                data-turn={t.turn}
                className={mergeClasses(styles.turn, t.turn === focusTurn && styles.turnFocus)}
                aria-current={t.turn === focusTurn ? "true" : undefined}
              >
                <span className={styles.turnTime}>{clock(t.at)}</span>
                <span className={styles.turnBody}>
                  {(i === 0 || detail.transcript[i - 1]?.speaker !== t.speaker) && (
                    <span className={styles.turnSpeaker}>{t.speaker}</span>
                  )}
                  <span className={styles.turnText}>{t.text}</span>
                </span>
              </li>
            ))}
          </ol>
        </div>
      ) : (
        <p className={styles.detailNote}>The transcript is no longer kept; the notes stay.</p>
      )}
      <div className={styles.footer}>
        {speakers.length > 0 && (
          <div className={styles.fixRow}>
            <Field label="Wrong speaker?" className={styles.fixField}>
              <Select value={from} onChange={(_, d) => setFrom(d.value)}>
                {speakers.map((p) => (
                  <option key={p.id} value={p.id}>{p.name}</option>
                ))}
              </Select>
            </Field>
            <Field label="was really" className={styles.fixField}>
              <Select value={to} onChange={(_, d) => setTo(d.value)}>
                <option value="">I don't know who</option>
                {detail.people
                  .filter((p) => p.id !== from)
                  .map((p) => (
                    <option key={p.id} value={p.id}>{p.name}</option>
                  ))}
              </Select>
            </Field>
            <Button disabled={!from} onClick={() => void fixSpeaker()}>Fix speaker</Button>
          </div>
        )}
        <div className={styles.forget}>
          {confirmForget ? (
            <>
              <p className={styles.forgetText}>Forget this meeting? Its notes, transcript and promises go, and it's never read again.</p>
              <Button appearance="primary" className={styles.dangerPrimary} onClick={() => void forget()}>Yes, forget it</Button>
              <Button appearance="subtle" onClick={() => setConfirmForget(false)}>Cancel</Button>
            </>
          ) : (
            <Button appearance="subtle" icon={<Delete16Regular />} className={styles.dangerText} onClick={() => setConfirmForget(true)}>
              Forget this meeting
            </Button>
          )}
        </div>
      </div>
    </Surface>
  );
}
