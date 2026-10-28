/** Drafting starts only once Vanimo knows how you write (F15). Wherever a draft would start too early,
 * this one card says what's missing and does it: choose your sources, or learn your style (with live
 * progress), then hands back to the page. One step, one button, no dead ends. */
import { Button, makeStyles, MessageBar, MessageBarBody } from "@fluentui/react-components";
import {
  ArrowSync16Regular,
  DocumentSearch20Regular,
  HatGraduation20Regular,
  Play16Regular,
} from "@fluentui/react-icons";
import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { ApiError } from "../../api/client";
import { useApi } from "../../api/context";
import { IconTile, StepList, Surface, typo, vt, type StepState } from "../../ui";
import { errorText } from "../Home";

const useStyles = makeStyles({
  card: { display: "grid", justifyItems: "center", textAlign: "center", gap: "12px", padding: "40px 24px" },
  title: { ...typo.sectionTitle, fontSize: "18px", lineHeight: "26px", color: vt.text1, margin: 0 },
  body: { ...typo.body, color: vt.text2, margin: 0, maxWidth: "56ch" },
  steps: { justifySelf: "stretch", maxWidth: "420px", width: "100%", marginInline: "auto", textAlign: "start" },
  action: { marginTop: "8px" },
});

export interface LearnFirstState {
  reviewDone: boolean;
  learningRunning: boolean;
  learningOutdated: boolean;
}

const STEPS = [
  "Read your own sent emails and chats, from the sources you allowed",
  "Remove names, ID numbers and never-send words before anything is kept",
  "Work out who you're formal, friendly or casual with",
  "Learn the words you use for each",
];

export function LearnFirst({ state, onLearned }: { state: LearnFirstState; onLearned: () => void }) {
  const styles = useStyles();
  const api = useApi();
  const navigate = useNavigate();
  const [running, setRunning] = useState(state.learningRunning);
  const [error, setError] = useState<string | null>(null);
  const live = useRef(true);
  useEffect(() => {
    live.current = true;
    return () => {
      live.current = false;
    };
  }, []);

  // While a run is going (started here or elsewhere), check every 2 seconds and hand back when it's done.
  useEffect(() => {
    if (!running) return;
    const timer = setInterval(async () => {
      try {
        const s = await api.learning();
        if (!live.current || s.run?.status === "running") return;
        setRunning(false);
        if (s.learned) onLearned();
        else setError("Learning stopped before it finished. Try again.");
      } catch (e) {
        if (live.current) setError(errorText(e));
      }
    }, 2000);
    return () => clearInterval(timer);
  }, [running, api, onLearned]);

  async function learn() {
    setError(null);
    try {
      const s = await api.startLearning();
      if (s.run?.status === "running") setRunning(true);
      else if (s.learned) onLearned();
      else setError("Learning stopped before it finished. Try again.");
    } catch (e) {
      if (e instanceof ApiError && e.code === "learning_running") setRunning(true);
      else setError(errorText(e));
    }
  }

  if (!state.reviewDone) {
    return (
      <Surface padding="none" className={styles.card}>
        <IconTile icon={<DocumentSearch20Regular />} tone="accent" size={40} />
        <h2 className={styles.title}>First, choose what Vanimo may learn from</h2>
        <p className={styles.body}>
          Leave out any people, chats or clients you want kept private. Until you finish, Vanimo reads nothing but
          subject lines and names.
        </p>
        <Button appearance="primary" className={styles.action} onClick={() => navigate("/setup")}>
          Choose sources
        </Button>
      </Surface>
    );
  }

  // While running, the spinner sits on the first step: the server reports counts only when a run ends.
  const stepState = (i: number): StepState => (running && i === 0 ? "active" : "pending");
  return (
    <Surface padding="none" className={styles.card} aria-live="polite">
      <IconTile icon={<HatGraduation20Regular />} tone="accent" size={40} />
      <h2 className={styles.title}>
        {running
          ? "Learning your style…"
          : state.learningOutdated
            ? "Learn again to write in each person's tone"
            : "Vanimo needs to learn your style first"}
      </h2>
      <p className={styles.body}>
        {running
          ? "This page carries on by itself when it's done. You can leave it open or come back later."
          : state.learningOutdated
            ? "Vanimo now learns who you're formal, friendly or casual with, and the words you use for each. It takes about a minute."
            : "So every draft sounds like you, Vanimo first learns how you write to each person. It takes about a minute, and you can see everything it learned."}
      </p>
      <div className={styles.steps}>
        <StepList label="What learning does" steps={STEPS.map((label, i) => ({ label, state: stepState(i) }))} />
      </div>
      {error && (
        <MessageBar intent="error">
          <MessageBarBody>{error}</MessageBarBody>
        </MessageBar>
      )}
      {!running && (
        <Button
          appearance="primary"
          className={styles.action}
          icon={state.learningOutdated ? <ArrowSync16Regular /> : <Play16Regular />}
          onClick={() => void learn()}
        >
          {state.learningOutdated ? "Learn again" : "Learn my style"}
        </Button>
      )}
    </Surface>
  );
}
