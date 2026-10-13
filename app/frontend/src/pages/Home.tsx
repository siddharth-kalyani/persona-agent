import {
  Body1,
  Caption1,
  Card,
  CardHeader,
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
    return `Something went wrong (${err.code}).`;
  }
  return "Something went wrong. Try again.";
}

export function Home() {
  const styles = useStyles();
  const api = useApi();
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

  return (
    <div className={styles.grid}>
      <Card>
        <CardHeader header={<Text weight="semibold">You</Text>} description={<Caption1>From Microsoft 365</Caption1>} />
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
          description={<Caption1>Subjects only, read live from Microsoft 365. Vanimo stores none of this.</Caption1>}
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
      <Caption1 className={styles.wide}>
        Roles: {me.roles.join(", ")} · Setup: {me.onboardingState === "review_pending" ? "choose what Vanimo learns from (coming in M1)" : "done"}
      </Caption1>
    </div>
  );
}
