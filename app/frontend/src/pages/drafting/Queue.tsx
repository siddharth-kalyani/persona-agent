/** Drafts queue (M4): conversations waiting for your reply, with a draft ready for each — and,
 * if you opt in, waiting in your Outlook Drafts folder (every Outlook, including mobile).
 * Vanimo never sends: you open the draft in Outlook, edit it and send it yourself.
 * Layout: a count header with the one primary action, hairline rows (subject and status, sender and
 * why, the draft's state, row actions on the right), and the Outlook settings as a settings list. */
import {
  Button,
  Link,
  makeStyles,
  mergeClasses,
  MessageBar,
  MessageBarBody,
  Select,
  Spinner,
  Switch,
  tokens,
  Tooltip,
} from "@fluentui/react-components";
import { Compose16Regular, MailInbox20Regular, Open16Regular } from "@fluentui/react-icons";
import { useCallback, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import type { Prepared, QueueItem, QueueView } from "../../api/client";
import { useApi } from "../../api/context";
import { draftErrorText } from "../../drafting/DraftView";
import {
  EmptyState,
  Page,
  PageSkeleton,
  Pill,
  Rise,
  Section,
  SettingList,
  SettingRow,
  StatusDot,
  Time,
  typo,
  vt,
  type Tone,
} from "../../ui";

const useStyles = makeStyles({
  list: {
    display: "grid",
    margin: 0,
    padding: 0,
    listStyle: "none",
    border: `1px solid ${tokens.colorNeutralStroke2}`,
    borderRadius: tokens.borderRadiusXLarge,
    backgroundColor: tokens.colorNeutralBackground1,
    overflow: "hidden",
  },
  row: {
    display: "grid",
    gridTemplateColumns: "minmax(0, 1fr) auto",
    gap: "8px 24px",
    padding: "14px 16px",
    borderTop: `1px solid ${tokens.colorNeutralStroke3}`,
    ":first-child": { borderTop: "none" },
    "@media (max-width: 639px)": { gridTemplateColumns: "minmax(0, 1fr)" },
  },
  main: { display: "grid", gap: "4px", minWidth: 0 },
  titleLine: { display: "flex", alignItems: "center", gap: "8px", minWidth: 0, flexWrap: "wrap" },
  subject: { ...typo.itemTitle, color: vt.text1, overflowWrap: "anywhere" },
  subjectMuted: { color: vt.text2 },
  meta: { ...typo.meta, color: vt.text2, overflowWrap: "anywhere" },
  sender: { ...typo.address, color: vt.text1 },
  draftLine: {
    display: "flex",
    alignItems: "center",
    flexWrap: "wrap",
    gap: "4px 10px",
    ...typo.meta,
    ...typo.tabular,
    color: vt.text2,
    marginTop: "2px",
  },
  link: { display: "inline-flex", alignItems: "center", gap: "4px" },
  notice: { ...typo.meta, color: vt.text1, margin: "4px 0 0", maxWidth: "72ch" },
  side: {
    display: "flex",
    flexDirection: "column",
    alignItems: "flex-end",
    justifyContent: "space-between",
    gap: "10px",
    "@media (max-width: 639px)": { flexDirection: "row", alignItems: "center", flexWrap: "wrap" },
  },
  time: { ...typo.meta, color: vt.text3 },
  actions: { display: "flex", alignItems: "center", gap: "4px", flexWrap: "wrap" },
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

const GOOD_STATES = new Set(["placed", "kept_edited", "sent"]);

function DraftState({ draft }: { draft: NonNullable<QueueItem["draft"]> }) {
  const s = useStyles();
  const tone: Tone = draft.blocked ? "warning" : draft.placedState && GOOD_STATES.has(draft.placedState) ? "success" : "neutral";
  return (
    <div className={s.draftLine}>
      <StatusDot tone={tone}>
        {draft.placedState ? (PLACED_STATE[draft.placedState] ?? draft.placedState) : "Draft ready"}
      </StatusDot>
      <span>
        Drafted <Time iso={draft.createdAt} />
      </span>
      {draft.blocked && <Pill tone="warning">Has a warning to check</Pill>}
      {draft.webLink && draft.placed && (
        <Link href={draft.webLink} target="_blank" rel="noreferrer" className={s.link}>
          Open in Outlook
          <Open16Regular aria-hidden />
        </Link>
      )}
    </div>
  );
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

  if (error)
    return (
      <Page title="Queue">
        <MessageBar intent="error">
          <MessageBarBody>{error}</MessageBarBody>
        </MessageBar>
      </Page>
    );
  if (!view) return <PageSkeleton label="Checking what's waiting for your reply…" />;
  const s = view.settings;
  const waiting = view.items.filter((i) => i.needsReply && !i.excluded);

  return (
    <Page
      title="Queue"
      eyebrow={<Pill>{view.sourceKind === "sample" ? "Sample workspace" : "Microsoft 365"}</Pill>}
      description="Emails waiting for your reply, with a draft in your voice. Vanimo never sends: you read, edit and send."
    >
      <Section
        title={`${waiting.length} waiting for your reply`}
        description={waiting.length > 0 ? "Prepare drafts for up to 5 at a time, then read and send them yourself." : undefined}
        actions={
          <Button
            appearance="primary"
            disabled={busy !== null || !waiting.some((i) => !i.draft)}
            onClick={() => void prepareAll()}
          >
            Prepare drafts for all
          </Button>
        }
      >
        {view.items.length === 0 ? (
          <EmptyState icon={<MailInbox20Regular />} title="Nothing waiting for a reply">
            Emails that need an answer from you appear here, ready for Vanimo to draft a reply in your voice.
          </EmptyState>
        ) : (
          <ul className={styles.list} aria-label="Conversations">
            {view.items.map((i) => {
              const drafting = busy === i.conversationId;
              return (
                <li key={i.conversationId} className={styles.row}>
                  <div className={styles.main}>
                    <div className={styles.titleLine}>
                      <span className={mergeClasses(styles.subject, i.excluded && styles.subjectMuted)}>
                        {i.subject ?? "(no subject)"}
                      </span>
                      {i.excluded ? (
                        <Pill>Excluded</Pill>
                      ) : i.needsReply ? (
                        <Pill tone="accent">Needs a reply</Pill>
                      ) : (
                        <Pill>For your information</Pill>
                      )}
                    </div>
                    <div className={styles.meta}>
                      <span className={styles.sender}>{i.sender.name ?? i.sender.email}</span>
                      {i.reason ? ` · ${i.reason}` : ""}
                    </div>
                    {i.draft && <DraftState draft={i.draft} />}
                    {notice[i.conversationId] && (
                      <Rise visible appear>
                        <p className={styles.notice} role="status">
                          {notice[i.conversationId]}
                        </p>
                      </Rise>
                    )}
                  </div>
                  <div className={styles.side}>
                    <Time iso={i.receivedAt} className={styles.time} />
                    {!i.excluded && (
                      <div className={styles.actions}>
                        <Button
                          size="small"
                          disabled={busy !== null}
                          icon={drafting ? <Spinner size="extra-tiny" /> : undefined}
                          onClick={() => void prepare(i)}
                        >
                          {drafting ? "Drafting…" : i.draft ? "Draft again" : "Prepare draft"}
                        </Button>
                        <Button size="small" appearance="subtle" onClick={() => void dismiss(i)}>
                          No reply needed
                        </Button>
                        <Tooltip content="Open the Draft page" relationship="label">
                          <Button size="small" appearance="subtle" icon={<Compose16Regular />} onClick={() => navigate("/draft")} />
                        </Tooltip>
                      </div>
                    )}
                  </div>
                </li>
              );
            })}
          </ul>
        )}
      </Section>

      <Section
        title="Drafts in Outlook"
        description={view.sourceKind === "sample" ? "Sample workspace: the Drafts folder is simulated." : undefined}
      >
        <SettingList>
          <SettingRow
            label="Put drafts in my Outlook Drafts folder"
            description={
              s.allowedByOrganisation
                ? "Works in every Outlook, including mobile. Only drafts without warnings go to Outlook."
                : "Your organisation has turned drafts in mailboxes off."
            }
          >
            <Switch
              checked={s.outlookDrafts}
              disabled={!s.allowedByOrganisation}
              onChange={(_, d) => void saveSettings(d.checked, s.staleDays)}
              aria-label="Put drafts in my Outlook Drafts folder (works on Outlook mobile too)"
            />
          </SettingRow>
          <SettingRow label="Remove unused drafts after" description="Drafts you edited or sent are never removed.">
            <Select
              aria-label="Remove unused drafts after"
              value={String(s.staleDays)}
              onChange={(_, d) => void saveSettings(s.outlookDrafts, Number(d.value))}
            >
              {[1, 2, 3, 5, 7, 14].map((n) => (
                <option key={n} value={n}>
                  {n} day{n > 1 ? "s" : ""}
                </option>
              ))}
            </Select>
          </SettingRow>
        </SettingList>
      </Section>
    </Page>
  );
}
