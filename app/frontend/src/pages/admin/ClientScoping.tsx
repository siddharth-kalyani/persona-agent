import {
  Button,
  Field,
  Input,
  makeStyles,
  MessageBar,
  MessageBarBody,
  Radio,
  RadioGroup,
  Spinner,
  Switch,
  Textarea,
  Tooltip,
} from "@fluentui/react-components";
import { BuildingMultiple20Regular, Delete16Regular } from "@fluentui/react-icons";
import { useEffect, useState } from "react";
import type { ClientAccount, MeetingHealth, Scoping } from "../../api/client";
import { ApiError } from "../../api/client";
import { useApi } from "../../api/context";
import {
  DataTable,
  EmptyState,
  Page,
  PageSkeleton,
  Pill,
  Rise,
  Section,
  SettingList,
  SettingRow,
  StatusDot,
  Td,
  Time,
  type Tone,
  Tr,
  typo,
  vt,
} from "../../ui";
import { errorText } from "../Home";

const useStyles = makeStyles({
  form: {
    display: "grid",
    gridTemplateColumns: "minmax(0, 1fr) minmax(0, 1fr)",
    gap: "16px",
    maxWidth: "720px",
    "@media (max-width: 639px)": { gridTemplateColumns: "minmax(0, 1fr)" },
  },
  full: { gridColumn: "1 / -1" },
  formActions: { gridColumn: "1 / -1", display: "flex", gap: "8px" },
  clientName: { ...typo.itemTitle, color: vt.text1, display: "block" },
  clientMeta: { ...typo.meta, ...typo.tabular, color: vt.text2, display: "block" },
  domains: { display: "flex", gap: "4px", flexWrap: "wrap" },
  domain: { ...typo.address, fontWeight: 400, height: "auto", minHeight: "20px", whiteSpace: "normal" },
  check: { display: "grid", gap: "12px" },
  checkedAt: { ...typo.meta, color: vt.text3, display: "inline-flex", gap: "4px" },
  health: { listStyle: "none", margin: 0, padding: 0, display: "grid", maxWidth: "820px" },
  healthRow: {
    display: "grid",
    gridTemplateColumns: "110px minmax(0, 1fr)",
    gap: "4px 16px",
    padding: "10px 0",
    borderTop: `1px solid ${vt.borderSubtle}`,
    ":first-child": { borderTopColor: "transparent" },
    "@media (max-width: 479px)": { gridTemplateColumns: "minmax(0, 1fr)" },
  },
  healthText: { ...typo.meta, color: vt.text1 },
});

export function splitList(value: string): string[] {
  return value
    .split(/[,;\n]/)
    .map((v) => v.trim())
    .filter(Boolean);
}

function scopingError(e: unknown): string {
  if (e instanceof ApiError && e.code === "domain_already_assigned") return "One of those domains already belongs to a client.";
  if (e instanceof ApiError && e.code === "invalid_request") return "Check the domains: use names like client.com.";
  return errorText(e);
}

const HEALTH: Record<MeetingHealth["checks"][number]["state"], [Tone, string]> = {
  ok: ["success", "OK"],
  warn: ["warning", "Warning"],
  fail: ["danger", "Problem"],
  info: ["neutral", "Info"],
};

/** One transcript health check, in plain words with what to do about it. */
export function healthText(c: MeetingHealth["checks"][number]): string {
  const n = (k: string) => c.counts[k] ?? 0;
  switch (`${c.key}:${c.code}`) {
    case "switch:on":
      return "Meeting memory is on.";
    case "switch:off":
      return "Meeting memory is off: no meetings are read.";
    case "transcript_access:listed":
      return `Transcripts can be read (${n("transcripts")} found in your recent meetings).`;
    case "transcript_access:none_found":
      return "Your recent meetings have no transcripts: is transcription allowed in the Teams meeting policy?";
    case "transcript_access:disabled":
      return "Graph access to transcripts is off. Teams admin center → Meetings → Meeting settings → Transcript API access (or Set-CsTeamsMeetingConfiguration).";
    case "transcript_access:permission":
      return "Vanimo can't read transcripts: grant admin consent for OnlineMeetings.Read and OnlineMeetingTranscript.Read.All.";
    case "transcript_access:sample_workspace":
      return "Sample workspace: transcripts are simulated, so there's nothing to check in Teams.";
    case "transcript_access:no_recent_meetings":
      return "You had no internal Teams meetings in the last 14 days to check with.";
    case "speaker_attribution:on":
      return `Speaker names are on (${n("named")} meetings read with names).`;
    case "speaker_attribution:off":
      return "Speaker attribution is off: notes have no names and your promises in meetings can't be found. Turn it on next to Transcript API access.";
    case "speaker_attribution:no_data":
      return "No meetings read yet in the last 14 days.";
    case "access_policy:not_needed_delegated":
      return "No Teams application access policy needed: Vanimo reads transcripts as each signed-in person.";
    default:
      return `Last 14 days: ${Object.entries(c.counts)
        .map(([k, v]) => `${k.replaceAll("_", " ")} ${v}`)
        .join(", ")}.`;
  }
}

/** Admin: client/account scoping for the whole organisation (D9). Never shows anyone's content. */
export function ClientScoping() {
  const styles = useStyles();
  const api = useApi();
  const [scoping, setScoping] = useState<Scoping | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [name, setName] = useState("");
  const [mode, setMode] = useState<ClientAccount["mode"]>("excluded");
  const [domains, setDomains] = useState("");
  const [words, setWords] = useState("");
  const [busy, setBusy] = useState(false);
  const [health, setHealth] = useState<MeetingHealth | null>(null);
  const [checking, setChecking] = useState(false);

  useEffect(() => {
    api.scoping().then(setScoping, (e) => setError(errorText(e)));
  }, [api]);

  async function run(fn: () => Promise<Scoping>) {
    setBusy(true);
    setError(null);
    try {
      setScoping(await fn());
      return true;
    } catch (e) {
      setError(scopingError(e));
      return false;
    } finally {
      setBusy(false);
    }
  }

  async function add() {
    const ok = await run(() => api.addAccount({ name, mode, domains: splitList(domains), sensitiveWords: splitList(words) }));
    if (ok) {
      setName("");
      setDomains("");
      setWords("");
    }
  }

  if (!scoping)
    return error ? (
      <Page title="Client scoping">
        <MessageBar intent="error">
          <MessageBarBody>{error}</MessageBarBody>
        </MessageBar>
      </Page>
    ) : (
      <PageSkeleton label="Loading…" />
    );

  const approvedCount = scoping.accounts.filter((a) => a.mode === "approved").length;

  return (
    <Page
      title="Client scoping"
      description="Rules here apply to everyone in your organisation. Users see them as locked and can't undo them. You never see anyone's emails, chats or personal exclusions here."
    >
      {error && (
        <MessageBar intent="error">
          <MessageBarBody>{error}</MessageBarBody>
        </MessageBar>
      )}

      <Section title="External people" description="Which conversations with people outside your organisation Vanimo may use.">
        <RadioGroup
          aria-label="External people"
          value={scoping.externalMode}
          onChange={(_, d) => void run(() => api.setExternalMode(d.value as Scoping["externalMode"]))}
        >
          <Radio value="allow_all" label="Use conversations with any external people, except excluded clients" />
          <Radio value="approved_only" label="Only use conversations with approved clients (everything else external is excluded)" />
        </RadioGroup>
        {scoping.externalMode === "approved_only" && approvedCount === 0 && (
          <MessageBar intent="warning">
            <MessageBarBody>
              No client is approved yet, so every conversation with external people is excluded. Add approved clients
              below.
            </MessageBarBody>
          </MessageBar>
        )}
      </Section>

      <Section
        title="Client accounts"
        description={
          scoping.accounts.length > 0
            ? `${scoping.accounts.length} ${scoping.accounts.length === 1 ? "client" : "clients"}, ${approvedCount} approved. Domains include their subdomains.`
            : undefined
        }
      >
        {scoping.accounts.length === 0 ? (
          <EmptyState icon={<BuildingMultiple20Regular />} title="No client accounts yet">
            Add a client below to exclude it for everyone, or to approve it when only approved clients are used.
          </EmptyState>
        ) : (
          <DataTable
            label="Client accounts"
            columns={[{ label: "Client" }, { label: "Domains" }, { label: "Rule" }, { hiddenLabel: "Actions" }]}
          >
            {scoping.accounts.map((a) => (
              <Tr key={a.id}>
                <Td primary>
                  <span className={styles.clientName}>{a.name}</span>
                  {a.sensitiveWords > 0 && (
                    <span className={styles.clientMeta}>
                      {a.sensitiveWords} sensitive {a.sensitiveWords === 1 ? "word" : "words"}
                    </span>
                  )}
                </Td>
                <Td label="Domains">
                  <span className={styles.domains}>
                    {a.domains.map((d) => (
                      <Pill key={d} className={styles.domain}>
                        {d}
                      </Pill>
                    ))}
                  </span>
                </Td>
                <Td label="Rule">
                  <Pill tone={a.mode === "excluded" ? "neutral" : "success"}>
                    {a.mode === "excluded" ? "Excluded" : "Approved"}
                  </Pill>
                </Td>
                <Td actions>
                  <Tooltip content="Remove" relationship="description" withArrow>
                    <Button
                      size="small"
                      appearance="subtle"
                      icon={<Delete16Regular />}
                      aria-label={`Remove ${a.name}`}
                      disabled={busy}
                      onClick={() => void run(() => api.removeAccount(a.id))}
                    />
                  </Tooltip>
                </Td>
              </Tr>
            ))}
          </DataTable>
        )}
      </Section>

      <Section title="Add a client">
        <div className={styles.form}>
          <Field label="Client name" required>
            <Input value={name} onChange={(_, d) => setName(d.value)} maxLength={120} />
          </Field>
          <Field label="Email domains" required hint="Comma-separated. Subdomains are included.">
            <Input value={domains} onChange={(_, d) => setDomains(d.value)} placeholder="client.com, client.co.in" />
          </Field>
          <RadioGroup
            className={styles.full}
            aria-label="Rule"
            layout="horizontal"
            value={mode}
            onChange={(_, d) => setMode(d.value as ClientAccount["mode"])}
          >
            <Radio value="excluded" label="Exclude (never learn from or draft with this client)" />
            <Radio value="approved" label="Approve" />
          </RadioGroup>
          <Field
            className={styles.full}
            label="Company-sensitive words for this client (optional)"
            hint="Codenames, pricing terms. Masked before any AI model sees them."
          >
            <Textarea value={words} onChange={(_, d) => setWords(d.value)} resize="vertical" />
          </Field>
          <div className={styles.formActions}>
            <Button appearance="primary" disabled={busy || !name.trim() || !domains.trim()} onClick={() => void add()}>
              Add client
            </Button>
          </div>
        </div>
      </Section>

      <Section title="Organisation settings" description="Each applies to everyone in your organisation.">
        <SettingList>
          <SettingRow
            label="Allow drafts in people's Outlook Drafts folder"
            description="Lets people choose to have reply drafts put in their Outlook Drafts folder (each person opts in; Vanimo never sends). Turning it off stops new ones; drafts already there stay until people delete them."
          >
            <Switch
              checked={scoping.serverDrafts}
              aria-label="Allow drafts in people's Outlook Drafts folder"
              onChange={(_, d) => void run(() => api.setServerDrafts(d.checked))}
            />
          </SettingRow>
          <SettingRow
            label="Open Teams chats with the draft typed in"
            description="Teams has no way for an app to type into the message box. Vanimo can open a chat with the draft already typed in (never sent), which Microsoft documents for new chats only: turn it on once the Teams prefill test (week-1 spike 1) shows it works in existing chats on your Teams clients. Until then people copy the draft."
          >
            <Switch
              checked={scoping.teamsPrefill}
              aria-label="Open Teams chats with the draft typed in"
              onChange={(_, d) => void run(() => api.setTeamsPolicy(d.checked, scoping.teamsNotifications))}
            />
          </SettingRow>
          <SettingRow
            label="Send reminders to people's Teams activity feed"
            description="Notifications carry counts only, never content."
          >
            <Switch
              checked={scoping.teamsNotifications}
              aria-label="Send reminders to people's Teams activity feed"
              onChange={(_, d) => void run(() => api.setTeamsPolicy(scoping.teamsPrefill, d.checked))}
            />
          </SettingRow>
          <SettingRow
            label="Remember Teams meetings"
            description="Vanimo reads the Teams transcripts of internal meetings people were invited to (as them, with their own permission) and keeps their decisions, requirements and promises so they can ask about them. Each person's exclusions still apply. Nothing is read until a Teams admin allows Microsoft Graph access to transcripts; with speaker attribution off, notes have no names."
          >
            <Switch
              checked={scoping.meetingMemory}
              aria-label="Remember Teams meetings"
              onChange={(_, d) => void run(() => api.setMeetingsPolicy(d.checked))}
            />
          </SettingRow>
          <SettingRow
            label="Transcript access"
            description={
              health ? (
                <span className={styles.checkedAt}>
                  Checked <Time iso={health.checkedAt} />
                </span>
              ) : (
                "Checks that Teams lets Vanimo read meeting transcripts, using your own recent meetings."
              )
            }
          >
            <Button
              disabled={busy || checking}
              icon={checking ? <Spinner size="extra-tiny" aria-hidden /> : undefined}
              onClick={() => {
                setChecking(true);
                api
                  .meetingHealth()
                  .then(setHealth, (e) => setError(errorText(e)))
                  .finally(() => setChecking(false));
              }}
            >
              Check transcript access
            </Button>
          </SettingRow>
        </SettingList>
        {health && (
          <Rise visible appear>
            <ul className={styles.health} aria-label="Transcript health">
              {health.checks.map((c) => {
                const [tone, word] = HEALTH[c.state];
                return (
                  <li key={c.key} className={styles.healthRow}>
                    <StatusDot tone={tone}>{word}</StatusDot>
                    <span className={styles.healthText}>{healthText(c)}</span>
                  </li>
                );
              })}
            </ul>
          </Rise>
        )}
      </Section>
    </Page>
  );
}
