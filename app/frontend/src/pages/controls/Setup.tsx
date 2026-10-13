import {
  Button,
  Caption1,
  Card,
  CardHeader,
  makeStyles,
  MessageBar,
  MessageBarBody,
  Spinner,
  Text,
  Title3,
  tokens,
} from "@fluentui/react-components";
import { useCallback, useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import type { ControlsStatus } from "../../api/client";
import { useApi } from "../../api/context";
import { errorText } from "../Home";
import { SourcesReview } from "./SourcesReview";

const useStyles = makeStyles({
  stack: { display: "grid", gap: tokens.spacingVerticalL },
  row: { display: "flex", gap: tokens.spacingHorizontalM, alignItems: "center", flexWrap: "wrap" },
  muted: { color: tokens.colorNeutralForeground3 },
});

export function scanSummary(s: ControlsStatus["scan"]): string {
  if (!s) return "";
  const c = s.counts;
  return `${c.people ?? 0} people, ${c.threads ?? 0} email threads (${c.messages ?? 0} emails), ${c.chats ?? 0} chats, ${c.meetings ?? 0} meetings`;
}

/** Onboarding: scan headers → review → Finish or Skip. Nothing beyond headers is read before Finish/Skip. */
export function Setup() {
  const styles = useStyles();
  const api = useApi();
  const navigate = useNavigate();
  const [status, setStatus] = useState<ControlsStatus | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const started = useRef(false);

  const refresh = useCallback(async () => {
    try {
      const s = await api.controlsStatus();
      setStatus(s);
      return s;
    } catch (e) {
      setError(errorText(e));
      return null;
    }
  }, [api]);

  useEffect(() => {
    void (async () => {
      const s = await refresh();
      // Start the header pass automatically the first time.
      if (s && !s.scan && !started.current) {
        started.current = true;
        try {
          setStatus(await api.startScan());
        } catch (e) {
          setError(errorText(e));
        }
      }
    })();
  }, [api, refresh]);

  useEffect(() => {
    if (status?.scan?.status !== "running") return;
    const timer = setInterval(() => void refresh(), 2000);
    return () => clearInterval(timer);
  }, [status?.scan?.status, refresh]);

  async function complete(outcome: "finished" | "skipped") {
    setBusy(true);
    try {
      await api.completeReview(outcome);
      navigate("/");
    } catch (e) {
      setError(errorText(e));
      setBusy(false);
    }
  }

  if (!status) return <Spinner label="Loading…" />;
  const scan = status.scan;

  return (
    <div className={styles.stack}>
      <Title3 as="h2">Choose what Vanimo learns from</Title3>
      <Text>
        Vanimo has only read headers so far: who you write to, chat names and meeting titles. Exclude anything it
        shouldn't learn from, then finish. Nothing else is read until you do. You can change this any time later.
      </Text>
      {error && (
        <MessageBar intent="error">
          <MessageBarBody>{error}</MessageBarBody>
        </MessageBar>
      )}
      {!scan || scan.status === "running" ? (
        <Spinner label="Listing your sources (headers only)…" />
      ) : scan.status === "failed" ? (
        <MessageBar intent="error">
          <MessageBarBody>
            The scan didn't finish.{" "}
            <Button size="small" onClick={() => void api.startScan().then(setStatus, (e) => setError(errorText(e)))}>
              Try again
            </Button>{" "}
            <Button size="small" disabled={busy} onClick={() => void complete("skipped")}>
              Skip for now
            </Button>
          </MessageBarBody>
        </MessageBar>
      ) : (
        <>
          <Caption1 className={styles.muted}>
            Found {scanSummary(scan)}
            {scan.sourceKind === "sample" ? " in the sample workspace." : "."}
          </Caption1>
          <SourcesReview onChange={() => void refresh()} />
          <Card>
            <CardHeader
              header={<Text weight="semibold">Done reviewing?</Text>}
              description={
                <Caption1>
                  {status.rules} exclusions and {status.neverSendWords} never-send words so far. Vanimo starts
                  learning only from what's left.
                </Caption1>
              }
            />
            <div className={styles.row}>
              <Button appearance="primary" disabled={busy} onClick={() => void complete("finished")}>
                Finish
              </Button>
              <Button disabled={busy} onClick={() => void complete("skipped")}>
                Skip for now
              </Button>
            </div>
          </Card>
        </>
      )}
    </div>
  );
}
