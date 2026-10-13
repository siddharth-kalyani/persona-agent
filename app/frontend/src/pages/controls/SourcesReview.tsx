import {
  Badge,
  Button,
  Caption1,
  Checkbox,
  Dialog,
  DialogActions,
  DialogBody,
  DialogContent,
  DialogSurface,
  DialogTitle,
  Input,
  makeStyles,
  MessageBar,
  MessageBarBody,
  Spinner,
  Tab,
  Table,
  TableBody,
  TableCell,
  TableHeader,
  TableHeaderCell,
  TableRow,
  TabList,
  Text,
  tokens,
} from "@fluentui/react-components";
import { useCallback, useEffect, useMemo, useState } from "react";
import type { Impact, SourceItem, SourceKind } from "../../api/client";
import { useApi } from "../../api/context";
import { errorText } from "../Home";
import { NeverSendPanel } from "./NeverSendPanel";

const useStyles = makeStyles({
  stack: { display: "grid", gap: tokens.spacingVerticalM },
  toolbar: { display: "flex", gap: tokens.spacingHorizontalM, alignItems: "center", flexWrap: "wrap" },
  flags: { display: "flex", gap: tokens.spacingHorizontalXS, flexWrap: "wrap" },
  muted: { color: tokens.colorNeutralForeground3 },
  excludedRow: { backgroundColor: tokens.colorNeutralBackground3 },
  chatList: { display: "grid", gap: tokens.spacingVerticalXS, maxHeight: "240px", overflowY: "auto" },
});

const TABS: { value: SourceKind | "words"; label: string }[] = [
  { value: "people", label: "People" },
  { value: "domains", label: "Domains" },
  { value: "chats", label: "Chats" },
  { value: "threads", label: "Email threads" },
  { value: "meetings", label: "Meetings" },
  { value: "words", label: "Never-send words" },
];

export function impactSentence(i: Impact): string {
  const parts: string[] = [];
  const n = (count: number, one: string, many: string) => `${count} ${count === 1 ? one : many}`;
  if (i.emails) parts.push(`${n(i.emails, "email", "emails")} in ${n(i.threads, "thread", "threads")}`);
  else if (i.threads) parts.push(n(i.threads, "thread", "threads"));
  if (i.chats) parts.push(n(i.chats, "chat", "chats"));
  if (i.meetings) parts.push(n(i.meetings, "meeting", "meetings"));
  return parts.length ? parts.join(", ") : "Nothing stored yet";
}

function countsText(item: SourceItem): string {
  return Object.entries(item.counts)
    .filter(([, v]) => v > 0)
    .map(([k, v]) => `${v} ${k}`)
    .join(" · ");
}

function statusText(item: SourceItem): string {
  if (!item.excluded) return "Used";
  if (item.locked) return item.via.find((v) => v.startsWith("Your organisation")) ?? "Blocked by your organisation";
  if (item.ruleId) return "Excluded by you";
  return `Excluded via ${item.via.join(", ")}`;
}

/** "Choose what Vanimo learns from": the Sources index with search, flags and exclusions. */
export function SourcesReview({ onChange }: { onChange?: () => void }) {
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

  return (
    <div className={styles.stack}>
      <TabList selectedValue={tab} onTabSelect={(_, d) => setTab(d.value as SourceKind | "words")}>
        {TABS.map((t) => (
          <Tab key={t.value} value={t.value}>
            {t.label}
          </Tab>
        ))}
      </TabList>
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
              placeholder="Search names, addresses, subjects…"
              value={query}
              onChange={(_, d) => setQuery(d.value)}
              aria-label="Search sources"
            />
            <Caption1 className={styles.muted}>
              Excluded means not used at all: no style learning, no memory, never as context for a draft.
            </Caption1>
          </div>
          {!items ? (
            <Spinner label="Loading…" />
          ) : (
            <Table size="small" aria-label="Sources">
              <TableHeader>
                <TableRow>
                  <TableHeaderCell>Source</TableHeaderCell>
                  <TableHeaderCell>Activity</TableHeaderCell>
                  <TableHeaderCell>Status</TableHeaderCell>
                  <TableHeaderCell />
                </TableRow>
              </TableHeader>
              <TableBody>
                {shown.map((item) => (
                  <TableRow key={item.id} className={item.excluded ? styles.excludedRow : undefined}>
                    <TableCell>
                      <Text weight="semibold">{item.label}</Text>
                      {item.detail && <Caption1 className={styles.muted}> · {item.detail}</Caption1>}
                      {item.flags.length > 0 && (
                        <div className={styles.flags}>
                          {item.flags.map((f) => (
                            <Badge key={f} appearance="tint" color={f === "your organisation" ? "brand" : "warning"} size="small">
                              {f}
                            </Badge>
                          ))}
                        </div>
                      )}
                    </TableCell>
                    <TableCell>
                      <Caption1>{countsText(item)}</Caption1>
                    </TableCell>
                    <TableCell>
                      <Caption1>{statusText(item)}</Caption1>
                    </TableCell>
                    <TableCell>
                      {item.ruleId ? (
                        <Button size="small" onClick={() => void include(item)}>
                          Use again
                        </Button>
                      ) : !item.excluded ? (
                        <Button size="small" appearance="primary" onClick={() => setPending(item)}>
                          Exclude
                        </Button>
                      ) : null}
                    </TableCell>
                  </TableRow>
                ))}
                {shown.length === 0 && (
                  <TableRow>
                    <TableCell colSpan={4}>Nothing matches.</TableCell>
                  </TableRow>
                )}
              </TableBody>
            </Table>
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
          <DialogContent className={styles.stack}>
            {error && (
              <MessageBar intent="error">
                <MessageBarBody>{error}</MessageBarBody>
              </MessageBar>
            )}
            {!impact ? (
              <Spinner size="tiny" label="Working out what this removes…" />
            ) : (
              <>
                <Text>Vanimo will stop using: {impactSentence(impact)}.</Text>
                {impact.chatList.length > 0 && (
                  <>
                    <Caption1>Chats {item.kind === "person" ? "they're" : "people from this domain are"} in. Untick a chat to keep using it:</Caption1>
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
