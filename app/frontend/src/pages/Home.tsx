import {
  Body1,
  Caption1,
  Card,
  CardHeader,
  Link,
  makeStyles,
  MessageBar,
  MessageBarBody,
  Spinner,
  Table,
  TableBody,
  TableCell,
  TableHeader,
  TableHeaderCell,
  TableRow,
  Text,
  tokens,
} from "@fluentui/react-components";
import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { ApiError, type Me } from "../api/client";
import { useApi } from "../api/context";

const useStyles = makeStyles({
  grid: { display: "grid", gap: tokens.spacingVerticalL, gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))" },
  wide: { gridColumn: "1 / -1" },
});

export function errorText(err: unknown): string {
  if (err instanceof ApiError) {
    if (err.code === "consent_required") return "Vanimo needs admin consent for its Microsoft 365 permissions.";
    if (err.code === "not_assigned") return "Your account hasn't been given access to Vanimo yet. Ask your IT admin.";
    if (err.code === "db_unavailable") return "Vanimo is waking up. Try again in a few seconds.";
    if (err.code === "unauthorized_client") return "This app isn't allowed to call Vanimo.";
    if (err.code === "graph_error") return `Microsoft 365 returned an error (${String(err.body.graphCode ?? err.status)}).`;
    if (err.code === "pipeline_paused")
      return "Vanimo is paused for your organisation while an admin checks a sensitive-data finding. Nothing new is read or drafted until then.";
    if (err.code === "redaction_unavailable")
      return "Vanimo's sensitive-data check is unreachable right now, so nothing was read. Try again in a minute.";
    if (err.code === "model_check_unavailable")
      return "Vanimo's AI safety check is unreachable right now, so no AI was used. Try again in a minute.";
    if (err.code === "model_check_blocked")
      return "Vanimo's safety check found personal details that should have been hidden, so it stopped. Your admin has been told.";
    return `Something went wrong (${err.code}).`;
  }
  return "Something went wrong. Try again.";
}

export function Home() {
  const styles = useStyles();
  const api = useApi();
  const navigate = useNavigate();
  const [me, setMe] = useState<Me | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let live = true;
    api.me().then(
      (m) => live && setMe(m),
      (e) => live && setError(errorText(e)),
    );
    return () => {
      live = false;
    };
  }, [api]);

  if (error)
    return (
      <MessageBar intent="error">
        <MessageBarBody>{error}</MessageBarBody>
      </MessageBar>
    );
  if (!me) return <Spinner label="Loading your profile…" />;

  const sourceLabel = me.dataSource === "sample" ? "From the sample workspace" : "From Microsoft 365";
  return (
    <div className={styles.grid}>
      {me.dataSource === "sample" && (
        <MessageBar intent="info" className={styles.wide}>
          <MessageBarBody>
            You're seeing the sample workspace — a fictional company, Kestrel Analytics. Your own Microsoft 365 data
            appears when you sign in with Microsoft.
          </MessageBarBody>
        </MessageBar>
      )}
      {me.pipelinePaused && (
        <MessageBar intent="warning" className={styles.wide}>
          <MessageBarBody>
            Vanimo is paused for your organisation: a sensitive-data check found something to review. Nothing new is
            read, learned or drafted until an admin resumes it. Your settings and data controls still work.
          </MessageBarBody>
        </MessageBar>
      )}
      {me.onboardingState === "review_pending" && (
        <Card className={styles.wide}>
          <CardHeader
            header={<Text weight="semibold">Before Vanimo learns anything</Text>}
            description={<Caption1>Nothing is read beyond headers until you finish or skip this step.</Caption1>}
          />
          <Link as="a" href="/setup" onClick={(e) => { e.preventDefault(); navigate("/setup"); }}>
            Choose what Vanimo learns from
          </Link>
        </Card>
      )}
      <Card>
        <CardHeader header={<Text weight="semibold">You</Text>} description={<Caption1>{sourceLabel}</Caption1>} />
        <Body1>{me.user.displayName ?? "—"}</Body1>
        <Caption1>{[me.user.jobTitle, me.user.department].filter(Boolean).join(" · ") || "No job title"}</Caption1>
      </Card>
      <Card>
        <CardHeader header={<Text weight="semibold">Your manager</Text>} />
        {me.manager ? (
          <>
            <Body1>{me.manager.displayName ?? "—"}</Body1>
            <Caption1>{me.manager.jobTitle ?? ""}</Caption1>
          </>
        ) : (
          <Caption1>No manager listed in your directory.</Caption1>
        )}
      </Card>
      <Card className={styles.wide}>
        <CardHeader
          header={<Text weight="semibold">Your last 5 sent emails</Text>}
          description={<Caption1>Subjects only, read live. Vanimo doesn't store them.</Caption1>}
        />
        <Table size="small" aria-label="Last sent emails">
          <TableHeader>
            <TableRow>
              <TableHeaderCell>Subject</TableHeaderCell>
              <TableHeaderCell>Sent</TableHeaderCell>
              <TableHeaderCell>Recipients</TableHeaderCell>
            </TableRow>
          </TableHeader>
          <TableBody>
            {me.recentSent.map((m, i) => (
              <TableRow key={i}>
                <TableCell>{m.subject || "(no subject)"}</TableCell>
                <TableCell>{m.sentDateTime ? new Date(m.sentDateTime).toLocaleString() : "—"}</TableCell>
                <TableCell>{m.recipientCount}</TableCell>
              </TableRow>
            ))}
            {me.recentSent.length === 0 && (
              <TableRow>
                <TableCell colSpan={3}>No sent emails found.</TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
      </Card>
      <Caption1 className={styles.wide}>Roles: {me.roles.join(", ")}</Caption1>
    </div>
  );
}
