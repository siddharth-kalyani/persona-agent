import {
  Badge,
  Button,
  Caption1,
  Card,
  CardHeader,
  Field,
  makeStyles,
  MessageBar,
  MessageBarBody,
  ProgressBar,
  Radio,
  RadioGroup,
  Slider,
  Spinner,
  Switch,
  Text,
  Textarea,
  Title3,
  tokens,
} from "@fluentui/react-components";
import { useEffect, useState } from "react";
import type { PersonaSettings, PersonaSnapshot, StyleCard } from "../../api/client";
import { useApi } from "../../api/context";
import { errorText } from "../Home";

const useStyles = makeStyles({
  stack: { display: "grid", gap: tokens.spacingVerticalL },
  grid: { display: "grid", gap: tokens.spacingVerticalL, gridTemplateColumns: "repeat(auto-fit, minmax(300px, 1fr))" },
  row: { display: "flex", gap: tokens.spacingHorizontalS, alignItems: "center", flexWrap: "wrap" },
  muted: { color: tokens.colorNeutralForeground3 },
  form: { whiteSpace: "pre-line" },
});

const AUDIENCE: Record<string, string> = {
  manager: "With your manager",
  report: "With your team",
  peer: "With colleagues",
  external: "With clients and partners",
  personal: "Personal",
};

const SLIDER_LABELS = ["Much less", "Less", "As learned", "More", "Much more"];

/** "Hi {first}," → "Hi <first name>," for display. */
export function formLabel(form: string): string {
  return form
    .replaceAll("{first}", "‹first name›")
    .replaceAll("{full}", "‹full name›")
    .replaceAll("{last}", "‹surname›")
    .replaceAll("{me_full}", "‹your full name›")
    .replaceAll("{me}", "‹your name›");
}

function Habit({ title, dist }: { title: string; dist: [string, number][] }) {
  const styles = useStyles();
  return (
    <div>
      <Caption1 className={styles.muted}>{title}</Caption1>
      {dist.map(([form, share]) => (
        <div key={form} className={styles.row}>
          <Text className={styles.form}>{form === "(none)" ? "(none)" : formLabel(form)}</Text>
          <Caption1 className={styles.muted}>{Math.round(share * 100)}%</Caption1>
        </div>
      ))}
    </div>
  );
}

export function StyleCardView({ card, title }: { card: StyleCard; title: string }) {
  const styles = useStyles();
  return (
    <Card>
      <CardHeader header={<Text weight="semibold">{title}</Text>} description={<Caption1>{card.n} messages</Caption1>} />
      <Field label={`Formality ${Math.round(card.formality * 100)}%`}>
        <ProgressBar value={card.formality} thickness="large" />
      </Field>
      <Caption1>
        Usually {card.length.p25}–{card.length.p75} words (median {card.length.median})
        {card.exclamation_rate > 0.2 ? " · uses exclamation marks" : ""}
        {card.emoji_rate > 0.1 ? " · uses emoji" : ""}
      </Caption1>
      <Habit title="Greetings" dist={card.greetings} />
      <Habit title="Sign-offs" dist={card.sign_offs} />
      {card.phrases.length > 0 && (
        <div>
          <Caption1 className={styles.muted}>Phrases you use often</Caption1>
          <div className={styles.row}>
            {card.phrases.map((p) => (
              <Badge key={p} appearance="outline">
                {p}
              </Badge>
            ))}
          </div>
        </div>
      )}
      {card.keep_list.length > 0 && (
        <Caption1>Kept as your voice: {card.keep_list.join(", ")}</Caption1>
      )}
    </Card>
  );
}

function lines(v: string): string[] {
  return v
    .split("\n")
    .map((s) => s.trim())
    .filter(Boolean);
}

export function Persona() {
  const styles = useStyles();
  const api = useApi();
  const [snap, setSnap] = useState<PersonaSnapshot | null>(null);
  const [settings, setSettings] = useState<PersonaSettings | null>(null);
  const [doText, setDoText] = useState("");
  const [dontText, setDontText] = useState("");
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let live = true;
    api.persona().then(
      (s) => {
        if (!live) return;
        setSnap(s);
        setSettings(s.settings);
        setDoText(s.settings.phrases_do.join("\n"));
        setDontText(s.settings.phrases_dont.join("\n"));
      },
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
  if (!snap || !settings) return <Spinner label="Loading your persona…" />;

  const set = (patch: Partial<PersonaSettings>) => {
    setSettings({ ...settings, ...patch });
    setSaved(false);
  };
  const save = async () => {
    try {
      const out = await api.savePersonaSettings({ ...settings, phrases_do: lines(doText), phrases_dont: lines(dontText) });
      setSettings(out);
      setDoText(out.phrases_do.join("\n"));
      setDontText(out.phrases_dont.join("\n"));
      setSaved(true);
    } catch (e) {
      setError(errorText(e));
    }
  };
  const metrics = snap.evaluation?.metrics;

  return (
    <div className={styles.stack}>
      <Title3 as="h2">Your persona</Title3>
      {!snap.overall ? (
        <MessageBar intent="info">
          <MessageBarBody>Nothing learned yet. Start learning on the Learning page.</MessageBarBody>
        </MessageBar>
      ) : (
        <>
          <Caption1 className={styles.muted}>
            Learned from {snap.learned_items} of your messages ({snap.by.channel.email ?? 0} emails,{" "}
            {snap.by.channel.chat ?? 0} chat messages) · languages:{" "}
            {Object.entries(snap.by.language)
              .map(([k, v]) => `${k} ${v}`)
              .join(", ")}
          </Caption1>
          <div className={styles.grid}>
            <StyleCardView card={snap.overall} title="Overall" />
            {snap.audiences.map((a) => (
              <StyleCardView key={a.relationship} card={a.card} title={AUDIENCE[a.relationship] ?? a.relationship} />
            ))}
          </div>
        </>
      )}
      <Card>
        <CardHeader
          header={<Text weight="semibold">Persona studio</Text>}
          description={<Caption1>Adjust how drafts sound, relative to what Vanimo learned.</Caption1>}
        />
        <div className={styles.grid}>
          {(["formality", "length", "warmth"] as const).map((k) => (
            <Field key={k} label={`${k.charAt(0).toUpperCase()}${k.slice(1)}: ${SLIDER_LABELS[settings[k] + 2]}`}>
              <Slider min={-2} max={2} step={1} value={settings[k]} onChange={(_, d) => set({ [k]: d.value })} />
            </Field>
          ))}
        </div>
        <div className={styles.row}>
          <Switch checked={settings.emoji} onChange={(_, d) => set({ emoji: d.checked })} label="Emoji allowed" />
          <RadioGroup
            layout="horizontal"
            value={settings.polish}
            onChange={(_, d) => set({ polish: d.value as PersonaSettings["polish"] })}
          >
            <Radio value="light" label="Fix typos, keep my voice" />
            <Radio value="none" label="Exactly my style" />
          </RadioGroup>
        </div>
        <div className={styles.grid}>
          <Field label="Phrases to use (one per line)">
            <Textarea value={doText} onChange={(_, d) => { setDoText(d.value); setSaved(false); }} resize="vertical" />
          </Field>
          <Field label="Phrases never to use (one per line)">
            <Textarea value={dontText} onChange={(_, d) => { setDontText(d.value); setSaved(false); }} resize="vertical" />
          </Field>
        </div>
        <div className={styles.row}>
          <Button appearance="primary" onClick={() => void save()}>
            Save
          </Button>
          {saved && <Caption1>Saved. Never-send words in phrases are stored as placeholders.</Caption1>}
        </div>
      </Card>
      {metrics && (
        <Card>
          <CardHeader
            header={<Text weight="semibold">Style check (offline baseline)</Text>}
            description={
              <Caption1>
                Offline stand-in, no AI model: held-out replies re-drafted from your style cards and closest past reply.
                The Claude drafter must beat these numbers.
              </Caption1>
            }
          />
          <Caption1>
            {metrics.n_eval} replies checked · greeting match {pct(metrics.greeting_match)} · sign-off match{" "}
            {pct(metrics.sign_off_match)} · length match {pct(metrics.length_ratio)} · wording overlap{" "}
            {pct(metrics.bigram_overlap)}
          </Caption1>
        </Card>
      )}
    </div>
  );
}

function pct(v: number | string | undefined): string {
  return typeof v === "number" ? `${Math.round(v * 100)}%` : "—";
}
