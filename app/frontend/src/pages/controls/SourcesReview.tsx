import {
  Button,
  Checkbox,
  Dialog,
  DialogActions,
  DialogBody,
  DialogContent,
  DialogSurface,
  DialogTitle,
  Input,
  makeStyles,
  mergeClasses,
  MessageBar,
  MessageBarBody,
  Spinner,
  tokens,
} from "@fluentui/react-components";
import {
  ArrowForward16Regular,
  ArrowRepeatAll16Regular,
  ArrowUndo16Regular,
  ChevronDown16Regular,
  ChevronUp16Regular,
  Building16Regular,
  CalendarArrowRepeatAll16Regular,
  CalendarLtr16Regular,
  Chat16Regular,
  ChatMultiple16Regular,
  Clock16Regular,
  EyeOff16Regular,
  Globe16Regular,
  Info16Regular,
  LockClosed16Regular,
  Mail16Regular,
  People16Regular,
  PeopleTeam16Regular,
  Prohibited16Regular,
  Search16Regular,
  Warning16Regular,
} from "@fluentui/react-icons";
import { useCallback, useEffect, useMemo, useState, type ReactElement, type ReactNode } from "react";
import type { Impact, SourceItem, SourceKind } from "../../api/client";
import { useApi } from "../../api/context";
import {
  CHANNELS,
  DataTable,
  EmptyRow,
  IconTile,
  PersonAvatar,
  Pill,
  RowsSkeleton,
  type Segment,
  Segmented,
  StatusDot,
  Td,
  Time,
  type Tone,
  Tr,
  typo,
  vt,
} from "../../ui";
import { errorText } from "../Home";
import { NeverSendPanel } from "./NeverSendPanel";

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

const PHONE = "@media (max-width: 639px)";

const useStyles = makeStyles({
  stack: { display: "grid", gap: "16px", minWidth: 0 },
  toolbar: {
    display: "flex",
    gap: "8px 16px",
    alignItems: "center",
    flexWrap: "wrap",
  },
  search: { flex: "0 1 320px", minWidth: "200px", "@media (max-width: 479px)": { flex: "1 1 100%" } },
  hint: {
    ...typo.meta,
    color: vt.text3,
    margin: 0,
    flex: "1 1 280px",
    display: "flex",
    alignItems: "flex-start",
    gap: "6px",
    "& > svg": { flexShrink: 0, marginTop: "1px" },
  },
  matches: { ...typo.meta, ...typo.tabular, color: vt.text3 },
  source: { display: "grid", gridTemplateColumns: "auto minmax(0, 1fr)", alignItems: "center", gap: "12px", minWidth: 0 },
  sourceText: { display: "grid", minWidth: 0 },
  titleLine: { display: "flex", alignItems: "center", gap: "4px 8px", flexWrap: "wrap", minWidth: 0 },
  label: { ...typo.itemTitle, color: vt.text1, overflowWrap: "anywhere" },
  labelExcluded: { color: vt.text2 },
  detail: { ...typo.meta, ...typo.address, color: vt.text2 },
  dimmed: { opacity: 0.55 },
  // Phones: the source on top, then activity and status, then last active and the action, so a row
  // takes three short lines instead of a labelled line per cell (the header stays for screen readers).
  row: { [PHONE]: { gridTemplateColumns: "minmax(0, 1fr) auto", alignItems: "center", columnGap: "12px" } },
  cellSource: { [PHONE]: { gridColumn: "1 / -1", marginBottom: "4px" } },
  cellActivity: { [PHONE]: { gridColumn: "1", gridRow: "2" } },
  cellStatus: { [PHONE]: { gridColumn: "2", gridRow: "2", justifySelf: "end" } },
  cellLast: { [PHONE]: { gridColumn: "1", gridRow: "3" } },
  cellAction: { [PHONE]: { gridColumn: "2", gridRow: "3", justifySelf: "end", paddingTop: 0 } },
  more: { textAlign: "center", padding: "8px", [PHONE]: { display: "flex", justifyContent: "center" } },
  counts: { display: "inline-flex", alignItems: "center", gap: "4px 14px", flexWrap: "wrap", ...typo.tabular, color: vt.text1 },
  count: { display: "inline-flex", alignItems: "center", gap: "5px", whiteSpace: "nowrap", "& > svg": { color: vt.text3 } },
  when: { display: "inline-flex", alignItems: "center", gap: "5px", whiteSpace: "nowrap", color: vt.text2, "& > svg": { color: vt.text3 } },
  quiet: { color: vt.text3 },
  sr: srOnly,
  dialogBody: { display: "grid", gap: "12px" },
  impact: { ...typo.body, color: vt.text1, margin: 0 },
  chatsLabel: { ...typo.meta, color: vt.text2, margin: 0 },
  chatList: {
    display: "grid",
    gap: "2px",
    maxHeight: "240px",
    overflowY: "auto",
    padding: "4px",
    border: `1px solid ${vt.borderSubtle}`,
    borderRadius: tokens.borderRadiusLarge,
    backgroundColor: vt.inset,
  },
});

const TABS: { value: SourceKind | "words"; label: string; icon: ReactElement }[] = [
  { value: "people", label: "People", icon: <People16Regular /> },
  { value: "domains", label: "Domains", icon: <Globe16Regular /> },
  { value: "chats", label: "Chats", icon: <Chat16Regular /> },
  { value: "threads", label: "Email threads", icon: <Mail16Regular /> },
  { value: "meetings", label: "Meetings", icon: <CalendarLtr16Regular /> },
  { value: "words", label: "Never-send words", icon: <Prohibited16Regular /> },
];

/** Each activity count as icon + number; the noun is there for screen readers and on hover. */
const COUNT: Record<string, { icon: ReactElement; one: string; many: string }> = {
  emails: { icon: <Mail16Regular aria-hidden />, one: "email", many: "emails" },
  chats: { icon: <Chat16Regular aria-hidden />, one: "chat", many: "chats" },
  meetings: { icon: <CalendarLtr16Regular aria-hidden />, one: "meeting", many: "meetings" },
  people: { icon: <People16Regular aria-hidden />, one: "person", many: "people" },
  members: { icon: <People16Regular aria-hidden />, one: "member", many: "members" },
  attendees: { icon: <People16Regular aria-hidden />, one: "attendee", many: "attendees" },
  occurrences: { icon: <ArrowRepeatAll16Regular aria-hidden />, one: "occurrence", many: "occurrences" },
};

/** The scan's flags as pills: what they are in words, with an icon. */
const FLAG: Record<string, { label: string; tone: Tone; icon: ReactElement }> = {
  external: { label: "External", tone: "neutral", icon: <Globe16Regular /> },
  "personal email": { label: "Personal email", tone: "warning", icon: <Warning16Regular /> },
  "your organisation": { label: "Your organisation", tone: "accent", icon: <Building16Regular /> },
  "hidden in Teams": { label: "Hidden in Teams", tone: "neutral", icon: <EyeOff16Regular /> },
  "large group": { label: "Large group", tone: "neutral", icon: <PeopleTeam16Regular /> },
  forward: { label: "Forwarded", tone: "neutral", icon: <ArrowForward16Regular /> },
  private: { label: "Private", tone: "neutral", icon: <LockClosed16Regular /> },
};

/** What a row is, drawn the way the rest of Vanimo draws it: people as avatars, chats purple, email
 * blue, meetings in the accent. */
function Leading({ item }: { item: SourceItem }) {
  switch (item.kind) {
    case "person":
      return <PersonAvatar name={item.label} id={item.detail ?? item.label} size={28} />;
    case "domain":
      return <IconTile icon={item.flags.includes("your organisation") ? <Building16Regular /> : <Globe16Regular />} size={28} />;
    case "chat":
      return <IconTile icon={item.detail === "1:1 chat" ? <Chat16Regular /> : <ChatMultiple16Regular />} tone={CHANNELS.chat.tone} size={28} />;
    case "thread":
      return <IconTile icon={CHANNELS.email.icon} tone={CHANNELS.email.tone} size={28} />;
    case "series":
      return <IconTile icon={<CalendarArrowRepeatAll16Regular />} tone={CHANNELS.meeting.tone} size={28} />;
    default:
      return <IconTile icon={CHANNELS.meeting.icon} tone={CHANNELS.meeting.tone} size={28} />;
  }
}

function Counts({ item }: { item: SourceItem }) {
  const styles = useStyles();
  const parts = Object.entries(item.counts).filter(([, v]) => v > 0);
  if (parts.length === 0) return <span className={styles.quiet}>—</span>;
  return (
    <span className={styles.counts}>
      {parts.map(([k, v]) => {
        const c = COUNT[k];
        const noun = c ? (v === 1 ? c.one : c.many) : k.replaceAll("_", " ");
        return (
          <span key={k} className={styles.count} title={`${v} ${noun}`}>
            {c?.icon}
            {v}
            <span className={styles.sr}> {noun}</span>
          </span>
        );
      })}
    </span>
  );
}

function StatusPill({ item }: { item: SourceItem }): ReactNode {
  if (!item.excluded) return <StatusDot tone="success">{statusText(item)}</StatusDot>;
  if (item.locked)
    return (
      <Pill icon={<LockClosed16Regular aria-label="Locked" />} wrap>
        {statusText(item)}
      </Pill>
    );
  return (
    <Pill dot wrap>
      {statusText(item)}
    </Pill>
  );
}

/** Rows shown before "Show all": the busiest sources come first, and search covers everything. */
const FIRST = 25;

const NOUN: Record<SourceKind, string> = {
  people: "people",
  domains: "domains",
  chats: "chats",
  threads: "email threads",
  meetings: "meetings",
};

export function impactSentence(i: Impact): string {
  const parts: string[] = [];
  const n = (count: number, one: string, many: string) => `${count} ${count === 1 ? one : many}`;
  if (i.emails) parts.push(`${n(i.emails, "email", "emails")} in ${n(i.threads, "thread", "threads")}`);
  else if (i.threads) parts.push(n(i.threads, "thread", "threads"));
  if (i.chats) parts.push(n(i.chats, "chat", "chats"));
  if (i.meetings) parts.push(n(i.meetings, "meeting", "meetings"));
  return parts.length ? parts.join(", ") : "Nothing stored yet";
}

function statusText(item: SourceItem): string {
  if (!item.excluded) return "Used";
  if (item.locked) return item.via.find((v) => v.startsWith("Your organisation")) ?? "Blocked by your organisation";
  if (item.ruleId) return "Excluded by you";
  return `Excluded via ${item.via.join(", ")}`;
}

/** "Choose what Vanimo learns from": the Sources index with search, flags and exclusions.
 * `counts` (the header scan's totals) appear inside the kind switcher when given. */
export function SourcesReview({ onChange, counts }: { onChange?: () => void; counts?: Record<string, unknown> }) {
  const styles = useStyles();
  const api = useApi();
  const [tab, setTab] = useState<SourceKind | "words">("people");
  const [items, setItems] = useState<SourceItem[] | null>(null);
  const [query, setQuery] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState<SourceItem | null>(null);
  const [showAll, setShowAll] = useState(false);

  useEffect(() => setShowAll(false), [tab]);

  const load = useCallback(async () => {
    if (tab === "words") return;
    setItems(null);
    try {
      setItems(await api.sources(tab));
    } catch (e) {
      setError(errorText(e));
    }
  }, [api, tab]);

  useEffect(() => {
    void load();
  }, [load]);

  const shown = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!items) return [];
    return q ? items.filter((i) => `${i.label} ${i.detail ?? ""}`.toLowerCase().includes(q)) : items;
  }, [items, query]);
  const visible = showAll || query.trim() ? shown : shown.slice(0, FIRST);

  async function include(item: SourceItem) {
    if (!item.ruleId) return;
    try {
      await api.removeRule(item.ruleId);
      await load();
      onChange?.();
    } catch (e) {
      setError(errorText(e));
    }
  }

  const segments: Segment<SourceKind | "words">[] = TABS.map((t) => {
    const n = t.value === "words" ? undefined : counts?.[t.value];
    return { ...t, count: typeof n === "number" ? n : undefined, dividerBefore: t.value === "words" };
  });

  return (
    <div className={styles.stack}>
      <Segmented value={tab} onChange={setTab} segments={segments} label="What to review" />
      {error && (
        <MessageBar intent="error">
          <MessageBarBody>{error}</MessageBarBody>
        </MessageBar>
      )}
      {tab === "words" ? (
        <NeverSendPanel onChange={onChange} />
      ) : (
        <>
          <div className={styles.toolbar}>
            <Input
              className={styles.search}
              contentBefore={<Search16Regular aria-hidden />}
              placeholder="Search names, addresses, subjects…"
              value={query}
              onChange={(_, d) => setQuery(d.value)}
              aria-label="Search sources"
            />
            {items && query.trim() && (
              <span className={styles.matches} aria-live="polite">
                {shown.length} of {items.length}
              </span>
            )}
            <p className={styles.hint}>
              <Info16Regular aria-hidden />
              Excluded means not used at all: no style learning, no memory, never as context for a draft.
            </p>
          </div>
          {!items ? (
            <RowsSkeleton rows={5} label="Loading sources…" />
          ) : (
            <DataTable
              label="Sources"
              columns={[
                { label: "Source" },
                { label: "Activity" },
                { label: "Last active" },
                { label: "Status" },
                { hiddenLabel: "Actions" },
              ]}
            >
              {visible.map((item) => (
                <Tr key={item.id} className={styles.row}>
                  <Td primary dense className={styles.cellSource}>
                    <span className={styles.source}>
                      <span className={mergeClasses(item.excluded && styles.dimmed)}>
                        <Leading item={item} />
                      </span>
                      <span className={styles.sourceText}>
                        <span className={styles.titleLine}>
                          <span className={mergeClasses(styles.label, item.excluded && styles.labelExcluded)}>
                            {item.label}
                          </span>
                          {item.flags.map((f) => {
                            const flag = FLAG[f];
                            return (
                              <Pill key={f} tone={flag?.tone ?? "neutral"} icon={flag?.icon}>
                                {flag?.label ?? f}
                              </Pill>
                            );
                          })}
                        </span>
                        {item.detail && <span className={styles.detail}>{item.detail}</span>}
                      </span>
                    </span>
                  </Td>
                  <Td dense className={styles.cellActivity}>
                    <Counts item={item} />
                  </Td>
                  <Td dense className={styles.cellLast}>
                    {item.lastActivity ? (
                      <span className={styles.when}>
                        <Clock16Regular aria-hidden />
                        <Time iso={item.lastActivity} />
                      </span>
                    ) : (
                      <span className={styles.quiet}>—</span>
                    )}
                  </Td>
                  <Td dense className={styles.cellStatus}>
                    <StatusPill item={item} />
                  </Td>
                  <Td dense actions className={styles.cellAction}>
                    {item.ruleId ? (
                      <Button size="small" icon={<ArrowUndo16Regular />} onClick={() => void include(item)}>
                        Use again
                      </Button>
                    ) : !item.excluded ? (
                      <Button size="small" icon={<EyeOff16Regular />} onClick={() => setPending(item)}>
                        Exclude
                      </Button>
                    ) : null}
                  </Td>
                </Tr>
              ))}
              {!query.trim() && shown.length > FIRST && (
                <Tr>
                  <Td colSpan={5} className={styles.more}>
                    <Button
                      appearance="subtle"
                      size="small"
                      icon={showAll ? <ChevronUp16Regular /> : <ChevronDown16Regular />}
                      aria-expanded={showAll}
                      onClick={() => setShowAll((v) => !v)}
                    >
                      {showAll ? "Show fewer" : `Show all ${shown.length}`}
                    </Button>
                  </Td>
                </Tr>
              )}
              {shown.length === 0 && (
                <EmptyRow colSpan={5}>
                  {items.length === 0
                    ? `No ${NOUN[tab]} were found in the header scan.`
                    : `Nothing matches “${query.trim()}”.`}
                </EmptyRow>
              )}
            </DataTable>
          )}
        </>
      )}
      {pending && (
        <ExcludeDialog
          item={pending}
          onClose={() => setPending(null)}
          onDone={async (warning) => {
            setPending(null);
            await load();
            if (warning) setError(warning);
            onChange?.();
          }}
        />
      )}
    </div>
  );
}

function ExcludeDialog({
  item,
  onClose,
  onDone,
}: {
  item: SourceItem;
  onClose: () => void;
  onDone: (warning?: string) => Promise<void>;
}) {
  const styles = useStyles();
  const api = useApi();
  const [impact, setImpact] = useState<Impact | null>(null);
  const [keep, setKeep] = useState<Set<string>>(new Set());
  const [alsoWord, setAlsoWord] = useState(false);
  // Only a real name can become a never-send word (not an address, not text already masked).
  const canAddName = item.kind === "person" && !item.label.includes("@") && !item.label.includes("[removed]");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.impact(item.kind, item.id).then(setImpact, (e) => setError(errorText(e)));
  }, [api, item]);

  async function confirm() {
    setBusy(true);
    try {
      await api.addRule(item.kind, item.id, [...keep]);
    } catch (e) {
      setError(errorText(e));
      setBusy(false);
      return;
    }
    if (alsoWord && canAddName) {
      try {
        await api.addWord(item.label, "name", [], false);
      } catch {
        // The exclusion is saved: close the dialog and say what's left to do.
        await onDone(`Excluded. Adding "${item.label}" to never-send words didn't work; add it on the Never-send words tab.`);
        return;
      }
    }
    await onDone();
  }

  return (
    <Dialog open onOpenChange={(_, d) => !d.open && onClose()}>
      <DialogSurface>
        <DialogBody>
          <DialogTitle>Exclude {item.label}?</DialogTitle>
          <DialogContent className={styles.dialogBody}>
            {error && (
              <MessageBar intent="error">
                <MessageBarBody>{error}</MessageBarBody>
              </MessageBar>
            )}
            {!impact ? (
              <Spinner size="tiny" labelPosition="after" label="Working out what this removes…" />
            ) : (
              <>
                <p className={styles.impact}>Vanimo will stop using: {impactSentence(impact)}.</p>
                {impact.chatList.length > 0 && (
                  <>
                    <p className={styles.chatsLabel}>
                      Chats {item.kind === "person" ? "they're" : "people from this domain are"} in. Untick a chat to keep using it:
                    </p>
                    <div className={styles.chatList}>
                      {impact.chatList.map((c) => (
                        <Checkbox
                          key={c.id}
                          checked={!keep.has(c.id)}
                          label={`${c.label} (${c.members} members${c.large ? ", large group" : ""})`}
                          onChange={(_, d) => {
                            const next = new Set(keep);
                            if (d.checked) next.delete(c.id);
                            else next.add(c.id);
                            setKeep(next);
                          }}
                        />
                      ))}
                    </div>
                  </>
                )}
                {canAddName && (
                  <Checkbox
                    checked={alsoWord}
                    onChange={(_, d) => setAlsoWord(!!d.checked)}
                    label={`Also add "${item.label}" to never-send words (removes mentions everywhere else)`}
                  />
                )}
              </>
            )}
          </DialogContent>
          <DialogActions>
            <Button onClick={onClose}>Cancel</Button>
            <Button appearance="primary" icon={<EyeOff16Regular />} disabled={!impact || busy} onClick={() => void confirm()}>
              {busy ? "Excluding…" : "Exclude"}
            </Button>
          </DialogActions>
        </DialogBody>
      </DialogSurface>
    </Dialog>
  );
}
