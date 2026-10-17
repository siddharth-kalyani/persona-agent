/** Meetings (M6): what your Teams meetings decided, asked for and promised, read from Microsoft's own
 * transcripts, and questions about them answered with citations. Shown in the web app and as a tab in
 * Teams. Only internal Teams meetings with transcription on; your exclusions apply before anything is
 * read. Answers quote your notes and say where they come from, or say they found nothing. */
import {
  Badge,
  Button,
  Caption1,
  Card,
  Field,
  Input,
  makeStyles,
  MessageBar,
  MessageBarBody,
  Select,
  Spinner,
  Text,
  Title3,
  tokens,
} from "@fluentui/react-components";
import { useCallback, useEffect, useState } from "react";
import type { MeetingAnswer, MeetingDetail, MeetingList, MeetingNote, MeetingScan, NoteKind } from "../../api/client";
import { useApi } from "../../api/context";
import { draftErrorText } from "../../drafting/DraftView";

const useStyles = makeStyles({
  stack: { display: "grid", gap: tokens.spacingVerticalL },
  tight: { display: "grid", gap: tokens.spacingVerticalXS },
  row: { display: "flex", gap: tokens.spacingHorizontalM, alignItems: "center", flexWrap: "wrap" },
  muted: { color: tokens.colorNeutralForeground3 },
  answer: { whiteSpace: "pre-wrap", margin: 0 },
  quote: { margin: 0, fontStyle: "italic", color: tokens.colorNeutralForeground2 },
  turn: { margin: 0 },
  highlight: { margin: 0, backgroundColor: tokens.colorPaletteYellowBackground2 },
  list: { margin: 0, paddingLeft: tokens.spacingHorizontalL },
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

  if (error) return <MessageBar intent="error"><MessageBarBody>{error}</MessageBarBody></MessageBar>; // prettier-ignore
  if (!list) return <Spinner label="Loading your meetings…" />;

  return (
    <div className={styles.stack}>
      {!embedded && (
        <div>
          <Title3 as="h2">Meetings</Title3>
          <Text as="p">
            What your Teams meetings decided, asked for and promised, read from Microsoft's own transcripts of internal
            meetings you were invited to. Ask a question and every answer says which meeting and when it was said.
          </Text>
        </div>
      )}
      <div className={styles.row}>
        <Badge appearance="tint" color={list.label.startsWith("Offline") ? "warning" : "brand"}>{list.label}</Badge>
        {!list.on && <Badge appearance="tint" color="danger">Off for your organisation</Badge>}
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

      <Card>
        <form
          className={styles.tight}
          onSubmit={(e) => {
            e.preventDefault();
            void ask(question);
          }}
        >
          <Field label="Ask about your meetings">
            <Input
              value={question}
              maxLength={300}
              placeholder="What did the client ask for in Tuesday's meeting?"
              onChange={(_, d) => setQuestion(d.value)}
            />
          </Field>
          <div className={styles.row}>
            <Button type="submit" appearance="primary" disabled={asking || !list.on || question.trim().length < 3}>
              {asking ? "Looking…" : "Ask"}
            </Button>
            {EXAMPLES.map((q) => (
              <Button key={q} size="small" appearance="subtle" disabled={!list.on} onClick={() => { setQuestion(q); void ask(q); }}>
                {q}
              </Button>
            ))}
          </div>
        </form>
        {answer && (
          <div className={styles.tight} aria-label="Answer">
            {answer.when && <Caption1 className={styles.muted}>Looked at: {answer.when}</Caption1>}
            <p className={styles.answer}>{answer.answer}</p>
            {answer.citations.length > 0 && (
              <ol className={styles.list} aria-label="Sources">
                {answer.citations.map((c) => (
                  <li key={c.n} value={c.n}>
                    <Caption1>
                      {c.title}, {when(c.meetingStart)} · {clock(c.at)}–{clock(c.endAt)} · {c.speaker}: “{c.quote}”{" "}
                    </Caption1>
                    <Button size="small" appearance="transparent" onClick={() => void open(c.meetingId, c.turn)}>
                      Show in meeting
                    </Button>
                  </li>
                ))}
              </ol>
            )}
            {answer.candidates.length > 0 && (
              <div className={styles.row}>
                <Caption1>{answer.clarify ? "Which meeting?" : "Close matches:"}</Caption1>
                {answer.candidates.map((m) => (
                  <Button key={m.id} size="small" onClick={() => void ask(question, m.id)}>
                    {m.title} ({when(m.startsAt)})
                  </Button>
                ))}
              </div>
            )}
            <Caption1 className={styles.muted}>{answer.label}. Check anything important against the meeting.</Caption1>
          </div>
        )}
      </Card>

      {detail && (
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
      )}

      {list.items.length === 0 ? (
        <Caption1>
          {list.on
            ? "No meetings yet. Vanimo reads the transcripts of internal Teams meetings that had transcription on, after they end, each time you open this page."
            : "Your organisation turned meeting memory off."}
        </Caption1>
      ) : (
        <div className={styles.stack}>
          {list.items.map((m) => (
            <Card key={m.id}>
              <div className={styles.row}>
                <Text weight="semibold">{m.title}</Text>
                {m.external && <Badge appearance="tint" color="informative">With people outside</Badge>}
                {m.attribution === "unattributed" && <Badge appearance="tint" color="warning">No speaker names</Badge>}
              </div>
              <Caption1 className={styles.muted}>
                {when(m.startsAt)} · {noteSummary(m.notes)}
                {m.transcriptUntil ? ` · transcript kept until ${new Date(m.transcriptUntil).toLocaleDateString()}` : ""}
              </Caption1>
              <div className={styles.row}>
                <Button size="small" onClick={() => void open(m.id)}>Open</Button>
              </div>
            </Card>
          ))}
        </div>
      )}
      {list.hidden > 0 && (
        <Caption1 className={styles.muted}>{list.hidden} hidden because of a rule you added; they're being deleted.</Caption1>
      )}
    </div>
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
    <Card aria-label="Meeting">
      <div className={styles.row}>
        <Title3 as="h3">{detail.title}</Title3>
        <Caption1 className={styles.muted}>{when(detail.startsAt)}</Caption1>
        <Button size="small" appearance="subtle" onClick={onClose}>Close</Button>
      </div>
      {detail.attribution === "unattributed" && (
        <Caption1>Speaker names were off for this meeting, so notes don't say who said what.</Caption1>
      )}
      {ORDER.map((kind) => {
        const notes = detail.notesList.filter((n) => n.kind === kind);
        return notes.length ? (
          <div key={kind} className={styles.tight}>
            <Text weight="semibold">{NOTE_LABEL[kind][1]}</Text>
            {notes.map((n) => (
              <div key={n.id} className={styles.row}>
                <Text strikethrough={n.status === "dismissed"}>
                  {n.text}
                  {n.owner ? ` — for ${n.owner}` : ""}
                  {n.dueAt ? ` (due ${when(n.dueAt)})` : ""}
                </Text>
                <Caption1 className={styles.muted}>
                  {n.speaker}, {clock(n.saidAt)}
                </Caption1>
                <Button size="small" appearance="subtle" onClick={() => onDecide(n)}>
                  {n.status === "active" ? "Not right" : "Restore"}
                </Button>
              </div>
            ))}
          </div>
        ) : null;
      })}
      {detail.transcript.length > 0 ? (
        <div className={styles.tight}>
          <Text weight="semibold">Transcript</Text>
          <Caption1 className={styles.muted}>
            Kept until {detail.transcriptUntil ? new Date(detail.transcriptUntil).toLocaleDateString() : "—"}; then only the
            notes stay. Names you excluded and never-send words are never stored.
          </Caption1>
          {detail.transcript.map((t) => (
            <p key={t.turn} className={t.turn === focusTurn ? styles.highlight : styles.turn}>
              <Caption1 className={styles.muted}>{clock(t.at)}</Caption1> <b>{t.speaker}:</b> {t.text}
            </p>
          ))}
        </div>
      ) : (
        <Caption1 className={styles.muted}>The transcript is no longer kept; the notes stay.</Caption1>
      )}
      {speakers.length > 0 && (
        <div className={styles.row}>
          <Field label="Wrong speaker?">
            <Select value={from} onChange={(_, d) => setFrom(d.value)}>
              {speakers.map((p) => (
                <option key={p.id} value={p.id}>{p.name}</option>
              ))}
            </Select>
          </Field>
          <Field label="was really">
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
      <div className={styles.row}>
        {confirmForget ? (
          <>
            <Caption1>Forget this meeting? Its notes, transcript and promises go, and it's never read again.</Caption1>
            <Button appearance="primary" onClick={() => void forget()}>Yes, forget it</Button>
            <Button appearance="subtle" onClick={() => setConfirmForget(false)}>Cancel</Button>
          </>
        ) : (
          <Button appearance="subtle" onClick={() => setConfirmForget(true)}>Forget this meeting</Button>
        )}
      </div>
    </Card>
  );
}
