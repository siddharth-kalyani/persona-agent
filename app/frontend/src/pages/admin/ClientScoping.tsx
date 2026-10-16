import {
  Badge,
  Button,
  Caption1,
  Card,
  CardHeader,
  Field,
  Input,
  makeStyles,
  MessageBar,
  MessageBarBody,
  Radio,
  RadioGroup,
  Spinner,
  Table,
  TableBody,
  TableCell,
  TableHeader,
  TableHeaderCell,
  TableRow,
  Text,
  Textarea,
  Title3,
  tokens,
  Switch,
} from "@fluentui/react-components";
import { useEffect, useState } from "react";
import type { ClientAccount, Scoping } from "../../api/client";
import { ApiError } from "../../api/client";
import { useApi } from "../../api/context";
import { errorText } from "../Home";

const useStyles = makeStyles({
  stack: { display: "grid", gap: tokens.spacingVerticalL },
  form: { display: "grid", gap: tokens.spacingVerticalM, maxWidth: "640px" },
  row: { display: "flex", gap: tokens.spacingHorizontalM, alignItems: "center", flexWrap: "wrap" },
  muted: { color: tokens.colorNeutralForeground3 },
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

  if (!scoping) return error ? <MessageBar intent="error"><MessageBarBody>{error}</MessageBarBody></MessageBar> : <Spinner label="Loading…" />;

  return (
    <div className={styles.stack}>
      <Title3 as="h2">Client scoping</Title3>
      <Text>
        Rules here apply to everyone in your organisation. Users see them as locked and can't undo them. You never see
        anyone's emails, chats or personal exclusions here.
      </Text>
      {error && (
        <MessageBar intent="error">
          <MessageBarBody>{error}</MessageBarBody>
        </MessageBar>
      )}
      <Card>
        <CardHeader
          header={<Text weight="semibold">Drafts in mailboxes</Text>}
          description={
            <Caption1>
              Lets people choose to have reply drafts put in their Outlook Drafts folder (each person opts in; Vanimo
              never sends). Turning it off stops new ones; drafts already there stay until people delete them.
            </Caption1>
          }
        />
        <Switch
          checked={scoping.serverDrafts}
          onChange={(_, d) => void run(() => api.setServerDrafts(d.checked))}
          label="Allow drafts in people's Outlook Drafts folder"
        />
      </Card>
      <Card>
        <CardHeader
          header={<Text weight="semibold">Teams</Text>}
          description={
            <Caption1>
              Teams has no way for an app to type into the message box. Vanimo can open a chat with the draft already
              typed in (never sent), which Microsoft documents for new chats only: turn it on once the Teams prefill
              test (week-1 spike 1) shows it works in existing chats on your Teams clients. Until then people copy the
              draft. Notifications carry counts only, never content.
            </Caption1>
          }
        />
        <Switch
          checked={scoping.teamsPrefill}
          onChange={(_, d) => void run(() => api.setTeamsPolicy(d.checked, scoping.teamsNotifications))}
          label="Open Teams chats with the draft typed in"
        />
        <Switch
          checked={scoping.teamsNotifications}
          onChange={(_, d) => void run(() => api.setTeamsPolicy(scoping.teamsPrefill, d.checked))}
          label="Send reminders to people's Teams activity feed"
        />
      </Card>
      <Card>
        <CardHeader header={<Text weight="semibold">External people</Text>} />
        <RadioGroup
          value={scoping.externalMode}
          onChange={(_, d) => void run(() => api.setExternalMode(d.value as Scoping["externalMode"]))}
        >
          <Radio value="allow_all" label="Use conversations with any external people, except excluded clients" />
          <Radio value="approved_only" label="Only use conversations with approved clients (everything else external is excluded)" />
        </RadioGroup>
        {scoping.externalMode === "approved_only" && !scoping.accounts.some((a) => a.mode === "approved") && (
          <MessageBar intent="warning">
            <MessageBarBody>
              No client is approved yet, so every conversation with external people is excluded. Add approved clients
              below.
            </MessageBarBody>
          </MessageBar>
        )}
      </Card>
      <Card>
        <CardHeader header={<Text weight="semibold">Client accounts</Text>} />
        <Table size="small" aria-label="Client accounts">
          <TableHeader>
            <TableRow>
              <TableHeaderCell>Client</TableHeaderCell>
              <TableHeaderCell>Domains</TableHeaderCell>
              <TableHeaderCell>Rule</TableHeaderCell>
              <TableHeaderCell />
            </TableRow>
          </TableHeader>
          <TableBody>
            {scoping.accounts.map((a) => (
              <TableRow key={a.id}>
                <TableCell>
                  {a.name}
                  {a.sensitiveWords > 0 && <Caption1 className={styles.muted}> · {a.sensitiveWords} sensitive words</Caption1>}
                </TableCell>
                <TableCell>{a.domains.join(", ")}</TableCell>
                <TableCell>
                  <Badge color={a.mode === "excluded" ? "danger" : "success"} appearance="tint">
                    {a.mode === "excluded" ? "Excluded" : "Approved"}
                  </Badge>
                </TableCell>
                <TableCell>
                  <Button size="small" disabled={busy} onClick={() => void run(() => api.removeAccount(a.id))}>
                    Remove
                  </Button>
                </TableCell>
              </TableRow>
            ))}
            {scoping.accounts.length === 0 && (
              <TableRow>
                <TableCell colSpan={4}>No client accounts yet.</TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
      </Card>
      <Card>
        <CardHeader header={<Text weight="semibold">Add a client</Text>} />
        <div className={styles.form}>
          <Field label="Client name" required>
            <Input value={name} onChange={(_, d) => setName(d.value)} maxLength={120} />
          </Field>
          <Field label="Email domains" required hint="Comma-separated. Subdomains are included.">
            <Input value={domains} onChange={(_, d) => setDomains(d.value)} placeholder="client.com, client.co.in" />
          </Field>
          <RadioGroup layout="horizontal" value={mode} onChange={(_, d) => setMode(d.value as ClientAccount["mode"])}>
            <Radio value="excluded" label="Exclude (never learn from or draft with this client)" />
            <Radio value="approved" label="Approve" />
          </RadioGroup>
          <Field label="Company-sensitive words for this client (optional)" hint="Codenames, pricing terms. Masked before any AI model sees them.">
            <Textarea value={words} onChange={(_, d) => setWords(d.value)} />
          </Field>
          <div className={styles.row}>
            <Button appearance="primary" disabled={busy || !name.trim() || !domains.trim()} onClick={() => void add()}>
              Add client
            </Button>
          </div>
        </div>
      </Card>
    </div>
  );
}
