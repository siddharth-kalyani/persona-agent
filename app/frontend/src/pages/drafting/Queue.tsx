/** Drafts queue (M4): conversations waiting for your reply, with a draft ready for each — and,
 * if you opt in, waiting in your Outlook Drafts folder (every Outlook, including mobile).
 * Vanimo never sends: you open the draft in Outlook, edit it and send it yourself. */
import {
  Badge,
  Button,
  Caption1,
  Card,
  CardHeader,
  Link,
  makeStyles,
  MessageBar,
  MessageBarBody,
  Select,
  Spinner,
  Switch,
  Text,
  Title3,
  tokens,
} from "@fluentui/react-components";
import { useCallback, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import type { Prepared, QueueItem, QueueView } from "../../api/client";
import { useApi } from "../../api/context";
import { draftErrorText } from "../../drafting/DraftView";

const useStyles = makeStyles({
  stack: { display: "grid", gap: tokens.spacingVerticalL },
  row: { display: "flex", gap: tokens.spacingHorizontalM, alignItems: "center", flexWrap: "wrap" },
  item: { display: "grid", gap: tokens.spacingVerticalXS },
  muted: { color: tokens.colorNeutralForeground3 },
});

const NOT_PLACED: Record<NonNullable<Prepared["notPlacedReason"]>, string> = {
  off: "Draft ready. Turn on “Put drafts in my Outlook Drafts folder” to find it in Outlook too.",
  organisation_off: "Draft ready. Your organisation doesn't allow drafts in mailboxes.",
  blocked: "Draft ready, but not put in Outlook: it has a warning you need to check first (open it on the Draft page).",
  not_saved: "Draft made once and not saved (excluded conversation), so it can't go to Outlook.",
};

const PLACED_STATE: Record<string, string> = {
  placed: "In your Drafts folder",
  sent: "You sent it",
  removed_stale: "Removed from Drafts (unused)",
  replaced: "Removed from Drafts (you replied yourself)",
  kept_edited: "In your Drafts folder (you edited it)",
  gone: "No longer in your Drafts folder",
};

function when(iso: string): string {
  return new Date(iso).toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" });
}

export function Queue() {
  const styles = useStyles();
  const api = useApi();
  const navigate = useNavigate();
  const [view, setView] = useState<QueueView | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [notice, setNotice] = useState<Record<string, string>>({});
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    try {
      setView(await api.queue());
    } catch (e) {
      setError(draftErrorText(e));
    }
  }, [api]);

  useEffect(() => {
    // Housekeeping first (both are quick and safe to skip): unused drafts leave Outlook, and drafts
    // are matched to what you sent so Vanimo learns from your edits.
    void Promise.allSettled([api.tidy(), api.syncEdits()]).then(() => refresh());
  }, [api, refresh]);

  async function prepare(item: QueueItem) {
    setBusy(item.conversationId);
    try {
      const p = await api.prepare(item.conversationId);
      setNotice((n) => ({
        ...n,
        [item.conversationId]: p.placed
          ? "Draft ready in your Outlook Drafts folder. Read it before you send."
          : NOT_PLACED[p.notPlacedReason ?? "off"],
      }));
      await refresh();
    } catch (e) {
      setNotice((n) => ({ ...n, [item.conversationId]: draftErrorText(e) }));
    } finally {
      setBusy(null);
    }
  }

  async function prepareAll() {
    if (!view) return;
    const todo = view.items.filter((i) => i.needsReply && !i.excluded && !i.draft).slice(0, 5);
    for (const item of todo) await prepare(item);
  }

  async function saveSettings(outlookDrafts: boolean, staleDays: number) {
    try {
      const s = await api.saveDraftingSettings(outlookDrafts, staleDays);
      setView((v) => (v ? { ...v, settings: s } : v));
    } catch (e) {
      setError(draftErrorText(e));
    }
  }

  async function dismiss(item: QueueItem) {
    await api.dismiss(item.conversationId).catch(() => undefined);
    await refresh();
  }

  if (error) return <MessageBar intent="error"><MessageBarBody>{error}</MessageBarBody></MessageBar>; // prettier-ignore
  if (!view) return <Spinner label="Checking what's waiting for your reply…" />;
  const s = view.settings;
  const waiting = view.items.filter((i) => i.needsReply && !i.excluded);

  return (
    <div className={styles.stack}>
      <div>
        <Title3 as="h2">Drafts queue</Title3>
        <Text as="p">
          Emails waiting for your reply, with a draft in your voice. Vanimo never sends: you read, edit and send.
        </Text>
      </div>
      <Card>
        <CardHeader header={<Text weight="semibold">Drafts in Outlook</Text>} />
        <div className={styles.row}>
          <Switch
            checked={s.outlookDrafts}
            disabled={!s.allowedByOrganisation}
            onChange={(_, d) => void saveSettings(d.checked, s.staleDays)}
            label="Put drafts in my Outlook Drafts folder (works on Outlook mobile too)"
          />
          <Select
            aria-label="Remove unused drafts after"
            value={String(s.staleDays)}
            onChange={(_, d) => void saveSettings(s.outlookDrafts, Number(d.value))}
          >
            {[1, 2, 3, 5, 7, 14].map((n) => (
              <option key={n} value={n}>
                Remove unused drafts after {n} day{n > 1 ? "s" : ""}
              </option>
            ))}
          </Select>
        </div>
        <Caption1 className={styles.muted}>
          {s.allowedByOrganisation
            ? "Only drafts without warnings go to Outlook. Drafts you edited or sent are never removed."
            : "Your organisation has turned drafts in mailboxes off."}
          {view.sourceKind === "sample" && " Sample workspace: the Drafts folder is simulated."}
        </Caption1>
      </Card>
      <div className={styles.row}>
        <Text weight="semibold">{waiting.length} waiting for your reply</Text>
        <Button
          appearance="primary"
          disabled={busy !== null || !waiting.some((i) => !i.draft)}
          onClick={() => void prepareAll()}
        >
          Prepare drafts for all
        </Button>
      </div>
      {view.items.length === 0 && <Caption1>Nothing waiting for a reply.</Caption1>}
      {view.items.map((i) => (
        <Card key={i.conversationId}>
          <div className={styles.item}>
            <div className={styles.row}>
              <Text weight="semibold">{i.subject ?? "(no subject)"}</Text>
              {i.excluded ? (
                <Badge appearance="tint" color="subtle">Excluded</Badge>
              ) : i.needsReply ? (
                <Badge appearance="tint" color="brand">Needs a reply</Badge>
              ) : (
                <Badge appearance="tint" color="informative">For your information</Badge>
              )}
            </div>
            <Caption1 className={styles.muted}>
              {i.sender.name ?? i.sender.email} · {when(i.receivedAt)}
              {i.reason ? ` · ${i.reason}` : ""}
            </Caption1>
            {i.draft && (
              <Caption1>
                Draft {when(i.draft.createdAt)}
                {i.draft.placedState ? ` · ${PLACED_STATE[i.draft.placedState] ?? i.draft.placedState}` : ""}
                {i.draft.blocked ? " · has a warning to check" : ""}
                {i.draft.webLink && i.draft.placed && (
                  <>
                    {" · "}
                    <Link href={i.draft.webLink} target="_blank" rel="noreferrer">
                      Open in Outlook
                    </Link>
                  </>
                )}
              </Caption1>
            )}
            {notice[i.conversationId] && <Caption1>{notice[i.conversationId]}</Caption1>}
            {!i.excluded && (
              <div className={styles.row}>
                <Button size="small" disabled={busy !== null} onClick={() => void prepare(i)}>
                  {busy === i.conversationId ? "Drafting…" : i.draft ? "Draft again" : "Prepare draft"}
                </Button>
                <Button size="small" appearance="subtle" onClick={() => navigate("/draft")}>
                  Open the Draft page
                </Button>
                <Button size="small" appearance="subtle" onClick={() => void dismiss(i)}>
                  No reply needed
                </Button>
              </div>
            )}
          </div>
        </Card>
      ))}
    </div>
  );
}
