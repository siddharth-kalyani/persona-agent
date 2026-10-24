/** Meetings (M6): what your Teams meetings decided, asked for and promised, read from Microsoft's own
 * transcripts, and questions about them answered with citations. Shown in the web app and as a tab in
 * Teams. Only internal Teams meetings with transcription on; your exclusions apply before anything is
 * read. Answers quote your notes and say where they come from, or say they found nothing.
 * Layout: the ask card first (a large field, suggestions, and the answer in reading type with
 * numbered citation chips and its sources in a well); then the meetings (grouped by day, each row
 * with its notes as icon counts) beside the open meeting: notes by kind, the transcript in a well,
 * and the corrections at the foot.
 * No router hooks: the Teams tab renders this without a router. Only `vt`/`tokens` colours (with light
 * fallbacks), so it also renders under Microsoft's Teams theme. */
import {
  Button,
  Field,
  Input,
  makeStyles,
  mergeClasses,
  MessageBar,
  MessageBarBody,
  Select,
  Spinner,
  tokens,
  Tooltip,
  useId,
} from "@fluentui/react-components";
import {
  ArrowUndo16Regular,
  CalendarClock16Regular,
  CalendarLtr16Regular,
  CalendarLtr20Regular,
  CheckmarkCircle16Regular,
  ClipboardTask16Regular,
  Clock16Regular,
  Delete16Regular,
  Dismiss16Regular,
  DocumentText16Regular,
  EyeOff16Regular,
  Globe16Regular,
  Handshake16Regular,
  Info16Regular,
  Lightbulb16Regular,
  Open16Regular,
  PersonEdit16Regular,
  PersonQuestionMark16Regular,
  QuestionCircle16Regular,
  Search20Regular,
  Send16Regular,
  ShieldCheckmark16Regular,
  TaskListSquareLtr16Regular,
  ThumbDislike16Regular,
  Warning16Regular,
} from "@fluentui/react-icons";
import { useCallback, useEffect, useRef, useState, type ReactElement, type ReactNode } from "react";
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
import {
  CHANNELS,
  EmptyState,
  EngineBadge,
  hoverTransition,
  IconAction,
  IconTile,
  List,
  ListRow,
  Page,
  PageSkeleton,
  PersonAvatar,
  Pill,
  Rise,
  Section,
  Surface,
  typo,
  vt,
  type Tone,
} from "../../ui";

const PHONE = "@media (max-width: 639px)";
const WIDE = "@media (min-width: 1200px)";

const srOnly = {
  position: "absolute",
  width: "1px",
  height: "1px",
  padding: 0,
  margin: "-1px",
  overflow: "hidden",
  clip: "rect(0 0 0 0)",
  whiteSpace: "nowrap",
  border: 0,
} as const;

/** A numbered citation chip, in the text and in the sources list. */
const chip = {
  display: "inline-grid",
  placeItems: "center",
  minWidth: "20px",
  height: "20px",
  padding: "0 5px",
  borderRadius: "6px",
  backgroundColor: vt.accentTint,
  color: vt.accentTintText,
  fontFamily: tokens.fontFamilyBase,
  fontSize: "12px",
  lineHeight: "16px",
  fontWeight: 600,
  ...typo.tabular,
} as const;

const useStyles = makeStyles({
  embedded: { display: "grid", gap: "24px", minWidth: 0 },
  // Ask
  askCard: { display: "grid", gap: "14px", minWidth: 0, padding: "20px", [PHONE]: { padding: "16px" } },
  askHead: { display: "flex", alignItems: "center", justifyContent: "space-between", gap: "8px 12px", flexWrap: "wrap" },
  askLabel: { ...typo.cardTitle, color: vt.text1, display: "inline-flex", alignItems: "center", gap: "10px" },
  askForm: { display: "flex", alignItems: "stretch", gap: "8px", flexWrap: "wrap" },
  askInput: { flex: "1 1 200px", minWidth: 0 },
  askIcon: { color: vt.text3 },
  examples: { display: "flex", alignItems: "center", gap: "6px", flexWrap: "wrap" },
  examplesLabel: { ...typo.meta, color: vt.text3, marginRight: "4px" },
  // Answer (inside the ask card, under a hairline)
  answer: {
    display: "grid",
    gap: "16px",
    minWidth: 0,
    paddingTop: "18px",
    marginTop: "4px",
    borderTop: `1px solid ${vt.borderSubtle}`,
  },
  answerWhen: { ...typo.meta, color: vt.text2, margin: 0, display: "inline-flex", alignItems: "center", gap: "6px", "& > svg": { color: vt.text3 } },
  answerText: { ...typo.reading, color: vt.text1, margin: 0, whiteSpace: "pre-wrap", overflowWrap: "anywhere", maxWidth: "76ch" },
  cite: {
    ...chip,
    margin: "0 2px",
    verticalAlign: "1px",
    border: "none",
    cursor: "pointer",
    ...hoverTransition,
    "@media (hover: hover)": { ":hover": { backgroundColor: tokens.colorBrandBackground, color: tokens.colorNeutralForegroundOnBrand } },
    ":focus-visible": { outline: `2px solid ${tokens.colorStrokeFocus2}`, outlineOffset: "1px" },
  },
  sources: { display: "grid", gap: "8px", minWidth: 0 },
  sourcesTitle: { ...typo.label, color: vt.text2, margin: 0 },
  // The sources sit in a well (never a card in a card).
  sourceList: {
    display: "grid",
    margin: 0,
    padding: "0 14px",
    listStyle: "none",
    borderRadius: "8px",
    backgroundColor: vt.inset,
    border: `1px solid ${vt.borderSubtle}`,
  },
  source: {
    display: "grid",
    gridTemplateColumns: "auto minmax(0, 1fr) auto",
    gap: "4px 12px",
    alignItems: "start",
    padding: "12px 0",
    borderTop: `1px solid ${vt.borderSubtle}`,
    ":first-child": { borderTopColor: "transparent" },
  },
  sourceChip: { ...chip, marginTop: "1px" },
  sourceBody: { display: "grid", gap: "4px", minWidth: 0 },
  sourceTitle: { ...typo.itemTitle, color: vt.text1, overflowWrap: "anywhere" },
  sourceMeta: {
    ...typo.meta,
    ...typo.tabular,
    color: vt.text2,
    display: "flex",
    alignItems: "flex-start",
    gap: "5px",
    "& > svg": { color: vt.text3, flexShrink: 0, marginTop: "1px" },
  },
  sourceQuote: { ...typo.meta, color: vt.text2, overflowWrap: "anywhere", display: "flex", alignItems: "flex-start", gap: "8px" },
  candidates: { display: "flex", alignItems: "center", gap: "8px", flexWrap: "wrap" },
  candidatesLabel: { ...typo.itemTitle, color: vt.text1 },
  answerFoot: { display: "flex", alignItems: "center", gap: "8px 12px", flexWrap: "wrap", ...typo.meta, color: vt.text2 },
  footNote: { display: "inline-flex", alignItems: "center", gap: "6px", "& > svg": { color: vt.text3, flexShrink: 0 } },
  // Meetings and the open meeting
  split: {
    display: "grid",
    gridTemplateColumns: "minmax(0, 1fr)",
    gap: "24px",
    alignItems: "start",
    [WIDE]: { gridTemplateColumns: "360px minmax(0, 1fr)", gridTemplateAreas: '"list detail"' },
  },
  listPane: { minWidth: 0, [WIDE]: { gridArea: "list" } },
  detailPane: { minWidth: 0, [WIDE]: { gridArea: "detail" } },
  // Beside the list, the empty pane runs as tall as the list (no dead space under a short card).
  placeholder: { display: "none", [WIDE]: { display: "grid", gridArea: "detail", minHeight: "320px", alignContent: "center", alignSelf: "stretch" } },
  dayHead: {
    ...typo.label,
    color: vt.text2,
    margin: 0,
    padding: "7px 16px",
    backgroundColor: vt.inset,
    borderTop: `1px solid ${vt.borderSubtle}`,
  },
  rowMeta: { display: "grid", gap: "6px", whiteSpace: "normal" },
  rowTime: { display: "inline-flex", alignItems: "center", gap: "5px", ...typo.tabular },
  // Pills keep their own icon colour (the row's meta greys plain icons).
  pills: { display: "flex", alignItems: "center", gap: "4px", flexWrap: "wrap", "& span > svg": { color: "currentColor", verticalAlign: "0" } },
  countWrap: { display: "inline-flex" },
  hidden: { ...typo.meta, color: vt.text2, margin: "12px 0 0", display: "flex", alignItems: "center", gap: "6px", "& > svg": { color: vt.text3, flexShrink: 0 } },
  // Meeting detail
  detail: { display: "grid", minWidth: 0, overflow: "hidden" },
  detailHead: {
    display: "grid",
    gridTemplateColumns: "auto minmax(0, 1fr) auto",
    gap: "14px",
    alignItems: "start",
    padding: "18px 20px",
    borderBottom: `1px solid ${vt.borderSubtle}`,
    [PHONE]: { gridTemplateColumns: "minmax(0, 1fr) auto", padding: "16px" },
  },
  detailTile: { [PHONE]: { display: "none" } },
  // Focus lands here when a meeting opens: an accent ring, not the browser's default.
  detailTitle: {
    ...typo.sectionTitle,
    color: vt.text1,
    margin: 0,
    overflowWrap: "anywhere",
    borderRadius: "4px",
    ":focus-visible": { outline: `2px solid ${vt.accent}`, outlineOffset: "2px" },
  },
  detailMeta: { display: "flex", alignItems: "center", gap: "6px 10px", flexWrap: "wrap", ...typo.meta, ...typo.tabular, color: vt.text2, margin: "4px 0 0" },
  detailTime: { display: "inline-flex", alignItems: "center", gap: "5px", "& > svg": { color: vt.text3 } },
  detailBody: { display: "grid", gap: "24px", padding: "20px", minWidth: 0, [PHONE]: { padding: "16px" } },
  warnNote: {
    ...typo.meta,
    color: vt.text1,
    margin: 0,
    display: "flex",
    alignItems: "flex-start",
    gap: "8px",
    padding: "10px 12px",
    borderRadius: "8px",
    backgroundColor: vt.warningTint,
    "& > svg": { color: vt.warning, flexShrink: 0, marginTop: "1px" },
  },
  block: { display: "grid", gap: "10px", minWidth: 0 },
  blockHead: { display: "flex", alignItems: "center", gap: "10px", minWidth: 0 },
  h3: { ...typo.cardTitle, color: vt.text1, margin: 0 },
  notes: { display: "grid", margin: 0, padding: 0, listStyle: "none" },
  note: {
    display: "grid",
    gridTemplateColumns: "minmax(0, 1fr) auto",
    gap: "4px 12px",
    alignItems: "start",
    padding: "10px 0",
    borderTop: `1px solid ${vt.borderSubtle}`,
    ":first-child": { borderTopColor: "transparent", paddingTop: "2px" },
  },
  noteBody: { display: "grid", gap: "4px", minWidth: 0 },
  noteText: { ...typo.body, color: vt.text1, overflowWrap: "anywhere" },
  noteDismissed: { color: vt.text3, textDecorationLine: "line-through" },
  noteMeta: { ...typo.meta, ...typo.tabular, color: vt.text2, display: "flex", alignItems: "center", gap: "4px 12px", flexWrap: "wrap" },
  noteMetaItem: { display: "inline-flex", alignItems: "center", gap: "6px", "& > svg": { color: vt.text3 } },
  retention: { ...typo.meta, color: vt.text2, margin: 0, display: "flex", alignItems: "flex-start", gap: "6px", "& > svg": { color: vt.success, flexShrink: 0, marginTop: "1px" } },
  transcript: {
    position: "relative",
    display: "grid",
    gap: "2px",
    margin: 0,
    padding: "6px",
    listStyle: "none",
    maxHeight: "440px",
    overflowY: "auto",
    backgroundColor: vt.inset,
    border: `1px solid ${vt.borderSubtle}`,
    borderRadius: "8px",
  },
  turn: {
    display: "grid",
    gridTemplateColumns: "96px minmax(0, 1fr)",
    gap: "12px",
    padding: "8px 10px",
    borderRadius: "6px",
    [PHONE]: { gridTemplateColumns: "minmax(0, 1fr)", gap: "2px" },
  },
  turnFocus: { backgroundColor: vt.accentTint, boxShadow: `inset 3px 0 0 ${vt.accent}` },
  turnTime: { ...typo.meta, ...typo.tabular, color: vt.text3, paddingTop: "1px", whiteSpace: "nowrap" },
  turnBody: { display: "grid", gap: "4px", minWidth: 0 },
  turnSpeaker: { ...typo.label, color: vt.text1, display: "inline-flex", alignItems: "center", gap: "6px" },
  turnText: { ...typo.reading, color: vt.text1, overflowWrap: "anywhere" },
  footer: {
    display: "grid",
    gap: "14px",
    padding: "16px 20px",
    borderTop: `1px solid ${vt.borderSubtle}`,
    backgroundColor: vt.inset,
    [PHONE]: { padding: "16px" },
  },
  fixRow: {
    display: "grid",
    gridTemplateColumns: "minmax(0, 1fr) minmax(0, 1fr) auto",
    alignItems: "end",
    gap: "8px 12px",
    minWidth: 0,
    [PHONE]: { gridTemplateColumns: "minmax(0, 1fr)", justifyItems: "start" },
  },
  fixField: { minWidth: 0, [PHONE]: { width: "100%" } },
  forget: {
    display: "flex",
    alignItems: "center",
    gap: "8px 12px",
    flexWrap: "wrap",
    paddingTop: "12px",
    borderTop: `1px solid ${vt.borderSubtle}`,
  },
  forgetText: { ...typo.meta, color: vt.text1, margin: 0, flex: "1 1 240px" },
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

/** Each kind of note has one icon everywhere (the counts in the list, the groups in a meeting). */
const NOTE_ICON: Record<NoteKind, { icon: ReactElement; tone: Tone }> = {
  decision: { icon: <CheckmarkCircle16Regular />, tone: "neutral" },
  requirement: { icon: <ClipboardTask16Regular />, tone: "neutral" },
  action_item: { icon: <TaskListSquareLtr16Regular />, tone: "neutral" },
  commitment: { icon: <Handshake16Regular />, tone: "neutral" },
  open_question: { icon: <QuestionCircle16Regular />, tone: "neutral" },
  risk: { icon: <Warning16Regular />, tone: "warning" },
  idea: { icon: <Lightbulb16Regular />, tone: "neutral" },
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
  return new Date(iso).toLocaleTimeString(undefined, { hour: "numeric", minute: "2-digit" });
}

function hm(iso: string): string {
  return new Date(iso).toLocaleTimeString(undefined, { hour: "numeric", minute: "2-digit" });
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

/** One kind's count in words: "2 decisions". */
function noteCount(kind: NoteKind, n: number): string {
  return `${n} ${NOTE_LABEL[kind][n === 1 ? 0 : 1].toLowerCase()}`;
}

/** The notes summary of a meeting: "2 decisions · 1 requirement". */
export function noteSummary(notes: MeetingList["items"][number]["notes"]): string {
  const parts = ORDER.filter((k) => notes[k]).map((k) => noteCount(k, notes[k]!));
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

/** A meeting's notes as icon counts ("✓ 2", "⚠ 1"), each named for screen readers and on hover. */
function NoteCounts({ notes }: { notes: MeetingList["items"][number]["notes"] }) {
  const s = useStyles();
  return (
    <>
      {ORDER.filter((k) => notes[k]).map((k) => (
        <Tooltip key={k} content={noteCount(k, notes[k]!)} relationship="description" withArrow>
          <span className={s.countWrap}>
            <Pill tone={NOTE_ICON[k].tone} icon={NOTE_ICON[k].icon}>
              {notes[k]}
              <span style={srOnly}> {NOTE_LABEL[k][notes[k] === 1 ? 0 : 1].toLowerCase()}</span>
            </Pill>
          </span>
        </Tooltip>
      ))}
    </>
  );
}

export function Meetings({ embedded = false }: { embedded?: boolean }) {
  const styles = useStyles();
  const api = useApi();
  const askId = useId("ask");
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
        description="What your Teams meetings decided, asked for and promised, with answers that say where they come from."
        info="Read from Microsoft's own transcripts of internal Teams meetings you were invited to, after they end. Ask a question and every answer says which meeting and when it was said."
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

      <Surface padding="none" className={styles.askCard}>
        <div className={styles.askHead}>
          <label htmlFor={askId} className={styles.askLabel}>
            <IconTile icon={<Search20Regular />} tone="accent" size={28} />
            Ask about your meetings
          </label>
          {!list.on && (
            <Pill tone="danger" dot>
              Off for your organisation
            </Pill>
          )}
        </div>
        <form
          className={styles.askForm}
          onSubmit={(e) => {
            e.preventDefault();
            void ask(question);
          }}
        >
          <Input
            id={askId}
            size="large"
            className={styles.askInput}
            value={question}
            maxLength={300}
            contentBefore={<Search20Regular className={styles.askIcon} aria-hidden />}
            placeholder="What did the client ask for in Tuesday's meeting?"
            onChange={(_, d) => setQuestion(d.value)}
          />
          <Button
            type="submit"
            size="large"
            appearance="primary"
            icon={asking ? <Spinner size="extra-tiny" /> : <Send16Regular />}
            disabled={asking || !list.on || question.trim().length < 3}
          >
            {asking ? "Looking…" : "Ask"}
          </Button>
        </form>
        <div className={styles.examples}>
          <span className={styles.examplesLabel}>Try</span>
          {EXAMPLES.map((q) => (
            <Button
              key={q}
              size="small"
              shape="circular"
              appearance="outline"
              disabled={!list.on}
              onClick={() => {
                setQuestion(q);
                void ask(q);
              }}
            >
              {q}
            </Button>
          ))}
        </div>

        {answer && (
          <Rise visible appear>
            <div className={styles.answer} role="region" aria-label="Answer">
              {answer.when && (
                <p className={styles.answerWhen}>
                  <CalendarClock16Regular aria-hidden />
                  Looked at: {answer.when}
                </p>
              )}
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
                            <Clock16Regular aria-hidden />
                            {when(c.meetingStart)} · {clock(c.at)}–{clock(c.endAt)}
                          </span>
                          <span className={styles.sourceQuote}>
                            <PersonAvatar name={c.speaker} size={20} />
                            <span>
                              {c.speaker}: “{c.quote}”
                            </span>
                          </span>
                        </span>
                        <IconAction icon={<Open16Regular />} label="Show in meeting" onClick={() => void open(c.meetingId, c.turn)} />
                      </li>
                    ))}
                  </ol>
                </div>
              )}
              {answer.candidates.length > 0 && (
                <div className={styles.candidates}>
                  <span className={styles.candidatesLabel}>{answer.clarify ? "Which meeting?" : "Close matches:"}</span>
                  {answer.candidates.map((m) => (
                    <Button key={m.id} size="small" icon={<CalendarLtr16Regular />} onClick={() => void ask(question, m.id)}>
                      {m.title} ({when(m.startsAt)})
                    </Button>
                  ))}
                </div>
              )}
              <div className={styles.answerFoot}>
                <EngineBadge offline={answer.label.startsWith("Offline")} detail={answer.label} />
                <span className={styles.footNote}>
                  <Info16Regular aria-hidden />
                  Check anything important against the meeting.
                </span>
              </div>
            </div>
          </Rise>
        )}
      </Surface>

      <div className={styles.split}>
        <Section
          className={styles.listPane}
          title="Remembered meetings"
          count={list.items.length}
          aria-label="Remembered meetings"
          actions={<EngineBadge offline={list.label.startsWith("Offline")} detail={list.label} />}
        >
          {list.items.length === 0 ? (
            <Surface>
              <EmptyState center icon={<CalendarLtr20Regular />} title={list.on ? "No meetings yet" : "Meeting memory is off"}>
                {list.on
                  ? "No meetings yet. Vanimo reads the transcripts of internal Teams meetings that had transcription on, after they end, each time you open this page."
                  : "Your organisation turned meeting memory off."}
              </EmptyState>
            </Surface>
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
                      leading={<IconTile icon={CHANNELS.meeting.icon} tone={CHANNELS.meeting.tone} size={32} />}
                      title={m.title}
                      meta={
                        <span className={styles.rowMeta}>
                          <span className={styles.rowTime}>
                            <Clock16Regular aria-hidden />
                            {hm(m.startsAt)}–{hm(m.endsAt)}
                          </span>
                          {(Object.keys(m.notes).length > 0 || m.external || m.attribution === "unattributed") && (
                            <span className={styles.pills}>
                              <NoteCounts notes={m.notes} />
                              {m.external && <Pill icon={<Globe16Regular />}>External</Pill>}
                              {m.attribution === "unattributed" && (
                                <Pill tone="warning" icon={<PersonQuestionMark16Regular />}>
                                  No speaker names
                                </Pill>
                              )}
                            </span>
                          )}
                        </span>
                      }
                    />
                  ))}
                </MeetingDay>
              ))}
            </List>
          )}
          {list.hidden > 0 && (
            <p className={styles.hidden}>
              <EyeOff16Regular aria-hidden />
              {list.hidden} hidden because of a rule you added; they're being deleted.
            </p>
          )}
        </Section>

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
            <Surface className={styles.placeholder}>
              <EmptyState center icon={<CalendarLtr20Regular />} title="Pick a meeting">
                Its notes and transcript open here. Or ask a question above.
              </EmptyState>
            </Surface>
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
    <Surface as="section" padding="none" aria-label="Meeting" className={styles.detail}>
      <div className={styles.detailHead}>
        <IconTile icon={CHANNELS.meeting.icon20} tone={CHANNELS.meeting.tone} size={40} className={styles.detailTile} />
        <div>
          <h2 className={styles.detailTitle}>{detail.title}</h2>
          <p className={styles.detailMeta}>
            <span className={styles.detailTime}>
              <Clock16Regular aria-hidden />
              {when(detail.startsAt)}–{hm(detail.endsAt)}
            </span>
            {detail.external && <Pill icon={<Globe16Regular />}>External</Pill>}
          </p>
        </div>
        <IconAction icon={<Dismiss16Regular />} label="Close" onClick={onClose} />
      </div>
      <div className={styles.detailBody}>
        {detail.attribution === "unattributed" && (
          <p className={styles.warnNote}>
            <PersonQuestionMark16Regular aria-hidden />
            Speaker names were off for this meeting, so notes don't say who said what.
          </p>
        )}
        {ORDER.map((kind) => {
          const notes = detail.notesList.filter((n) => n.kind === kind);
          return notes.length ? (
            <div key={kind} className={styles.block}>
              <div className={styles.blockHead}>
                <IconTile icon={NOTE_ICON[kind].icon} tone={NOTE_ICON[kind].tone === "neutral" ? "accent" : NOTE_ICON[kind].tone} size={24} />
                <h3 className={styles.h3}>{NOTE_LABEL[kind][1]}</h3>
                <Pill>{notes.length}</Pill>
              </div>
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
                        <span className={styles.noteMetaItem}>
                          <PersonAvatar name={n.speaker} size={20} />
                          {n.speaker}
                        </span>
                        <span className={styles.noteMetaItem}>
                          <Clock16Regular aria-hidden />
                          {clock(n.saidAt)}
                        </span>
                        {n.status === "dismissed" && (
                          <span className={styles.noteMetaItem}>
                            <ThumbDislike16Regular aria-hidden />
                            Marked not right
                          </span>
                        )}
                      </span>
                    </span>
                    {n.status === "active" ? (
                      <IconAction icon={<ThumbDislike16Regular />} label="Not right" onClick={() => onDecide(n)} />
                    ) : (
                      <IconAction icon={<ArrowUndo16Regular />} label="Restore" onClick={() => onDecide(n)} />
                    )}
                  </li>
                ))}
              </ul>
            </div>
          ) : null;
        })}
        {detail.transcript.length > 0 ? (
          <div className={styles.block}>
            <div className={styles.blockHead}>
              <IconTile icon={<DocumentText16Regular />} tone="accent" size={24} />
              <h3 className={styles.h3}>Transcript</h3>
            </div>
            <p className={styles.retention}>
              <ShieldCheckmark16Regular aria-hidden />
              <span>
                Kept until {detail.transcriptUntil ? new Date(detail.transcriptUntil).toLocaleDateString() : "—"}; then only the
                notes stay. Names you excluded and never-send words are never stored.
              </span>
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
                      <span className={styles.turnSpeaker}>
                        <PersonAvatar name={t.speaker} id={t.speakerId} size={20} />
                        {t.speaker}
                      </span>
                    )}
                    <span className={styles.turnText}>{t.text}</span>
                  </span>
                </li>
              ))}
            </ol>
          </div>
        ) : (
          <p className={styles.retention}>
            <ShieldCheckmark16Regular aria-hidden />
            The transcript is no longer kept; the notes stay.
          </p>
        )}
      </div>
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
            <Field label="Was really" className={styles.fixField}>
              <Select value={to} onChange={(_, d) => setTo(d.value)}>
                <option value="">I don't know who</option>
                {detail.people
                  .filter((p) => p.id !== from)
                  .map((p) => (
                    <option key={p.id} value={p.id}>{p.name}</option>
                  ))}
              </Select>
            </Field>
            <Button icon={<PersonEdit16Regular />} disabled={!from} onClick={() => void fixSpeaker()}>
              Fix speaker
            </Button>
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
