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
import { LockClosed16Regular, Search16Regular } from "@fluentui/react-icons";
import { useCallback, useEffect, useMemo, useState } from "react";
import type { Impact, SourceItem, SourceKind } from "../../api/client";
import { useApi } from "../../api/context";
import {
  DataTable,
  EmptyRow,
  Pill,
  RowsSkeleton,
  type Segment,
  Segmented,
  StatusDot,
  Td,
  Time,
  Tr,
  typo,
  vt,
} from "../../ui";
import { errorText } from "../Home";
import { NeverSendPanel } from "./NeverSendPanel";

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
  hint: { ...typo.meta, color: vt.text2, margin: 0, flex: "1 1 280px" },
  matches: { ...typo.meta, ...typo.tabular, color: vt.text3 },
  label: { ...typo.itemTitle, color: vt.text1 },
  labelExcluded: { color: vt.text2 },
  detail: { ...typo.meta, ...typo.address, color: vt.text2, display: "block" },
  flags: { display: "flex", gap: "4px", flexWrap: "wrap", marginTop: "6px" },
  counts: { ...typo.tabular, color: vt.text2, display: "block", [PHONE]: { display: "inline" } },
  last: { ...typo.tabular, color: vt.text3, display: "block", [PHONE]: { display: "inline", marginLeft: "8px" } },
  quiet: { color: vt.text3 },
  locked: { display: "inline-flex", alignItems: "center", gap: "6px", ...typo.meta, color: vt.text2 },
  lockIcon: { color: vt.text3, flexShrink: 0 },
  dialogBody: { display: "grid", gap: "12px" },
  impact: { ...typo.body, color: vt.text1, margin: 0 },
  chatsLabel: { ...typo.meta, color: vt.text2, margin: 0 },
  chatList: {
    display: "grid",
    gap: "2px",
    maxHeight: "240px",
    overflowY: "auto",
    padding: "4px",
    border: `1px solid ${tokens.colorNeutralStroke2}`,
    borderRadius: tokens.borderRadiusLarge,
    backgroundColor: vt.inset,
  },
});

const TABS: { value: SourceKind | "words"; label: string }[] = [
  { value: "people", label: "People" },
  { value: "domains", label: "Domains" },
  { value: "chats", label: "Chats" },
  { value: "threads", label: "Email threads" },
  { value: "meetings", label: "Meetings" },
  { value: "words", label: "Never-send words" },
];

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

/** "6 emails · 1 chat": singular where the count is one. */
function countsText(item: SourceItem): string {
  return Object.entries(item.counts)
    .filter(([, v]) => v > 0)
    .map(([k, v]) => `${v} ${v === 1 ? (k === "people" ? "person" : k.replace(/s$/, "")) : k}`)
    .join(" · ");
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
                { label: "Status" },
                { hiddenLabel: "Actions" },
              ]}
            >
              {shown.map((item) => (
                <Tr key={item.id}>
                  <Td primary>
                    <span className={mergeClasses(styles.label, item.excluded && styles.labelExcluded)}>
                      {item.label}
                    </span>
                    {item.detail && <span className={styles.detail}>{item.detail}</span>}
                    {item.flags.length > 0 && (
                      <span className={styles.flags}>
                        {item.flags.map((f) => (
                          <Pill key={f} tone={f === "personal email" ? "warning" : "neutral"}>
                            {f}
                          </Pill>
                        ))}
                      </span>
                    )}
                  </Td>
                  <Td label="Activity">
                    <span className={styles.counts}>{countsText(item) || <span className={styles.quiet}>—</span>}</span>
                    {item.lastActivity && (
                      <span className={styles.last}>
                        Last <Time iso={item.lastActivity} />
                      </span>
                    )}
                  </Td>
                  <Td label="Status">
                    {item.locked ? (
                      <span className={styles.locked}>
                        <LockClosed16Regular className={styles.lockIcon} aria-label="Locked" />
                        <span>{statusText(item)}</span>
                      </span>
                    ) : (
                      <StatusDot tone={item.excluded ? "neutral" : "success"}>{statusText(item)}</StatusDot>
                    )}
                  </Td>
                  <Td actions>
                    {item.ruleId ? (
                      <Button size="small" onClick={() => void include(item)}>
                        Use again
                      </Button>
                    ) : !item.excluded ? (
                      <Button size="small" onClick={() => setPending(item)}>
                        Exclude
                      </Button>
                    ) : null}
                  </Td>
                </Tr>
              ))}
              {shown.length === 0 && (
                <EmptyRow colSpan={4}>
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
            <Button appearance="primary" disabled={!impact || busy} onClick={() => void confirm()}>
              {busy ? "Excluding…" : "Exclude"}
            </Button>
          </DialogActions>
        </DialogBody>
      </DialogSurface>
    </Dialog>
  );
}
