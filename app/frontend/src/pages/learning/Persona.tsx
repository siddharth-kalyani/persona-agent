/** Your persona: how you write, as Vanimo learned it from your own sent messages, per audience (a
 * segmented switch: everyone, your manager, your team, clients…), as plain label/value traits; the
 * studio that adjusts drafts relative to that; the rules learned from your edits; and the offline
 * style check. */
import {
  Button,
  Field,
  makeStyles,
  MessageBar,
  MessageBarBody,
  Radio,
  RadioGroup,
  Slider,
  Switch,
  Textarea,
  tokens,
} from "@fluentui/react-components";
import { CheckmarkCircle16Filled, PersonVoice20Regular } from "@fluentui/react-icons";
import { useEffect, useState, type ReactNode } from "react";
import { useNavigate } from "react-router-dom";
import type { PersonaSettings, PersonaSnapshot, StyleCard } from "../../api/client";
import { useApi } from "../../api/context";
import {
  EmptyState,
  KeyValueList,
  Page,
  PageSkeleton,
  Pill,
  Rise,
  Section,
  Segmented,
  SettingList,
  SettingRow,
  typo,
  vt,
} from "../../ui";
import { errorText } from "../Home";
import { EditsCard } from "./EditsCard";

const useStyles = makeStyles({
  panel: { display: "grid", gap: "4px", minWidth: 0 },
  panelHead: { display: "flex", alignItems: "baseline", gap: "8px", flexWrap: "wrap", paddingBottom: "4px" },
  panelTitle: { ...typo.itemTitle, color: vt.text1 },
  panelMeta: { ...typo.meta, ...typo.tabular, color: vt.text3 },
  forms: { display: "grid", gap: "4px" },
  formRow: { display: "flex", alignItems: "baseline", gap: "8px", flexWrap: "wrap" },
  form: { ...typo.body, color: vt.text1, whiteSpace: "pre-line" },
  formNone: { ...typo.body, color: vt.text2 },
  share: { ...typo.meta, ...typo.tabular, color: vt.text3 },
  value: { ...typo.body, color: vt.text1 },
  valueMeta: { ...typo.meta, ...typo.tabular, color: vt.text3, marginLeft: "6px" },
  pills: { display: "flex", gap: "6px", flexWrap: "wrap" },
  slider: { width: "240px", maxWidth: "100%", "@media (max-width: 639px)": { width: "100%" } },
  radios: { flexWrap: "wrap" },
  phrases: {
    display: "grid",
    gridTemplateColumns: "repeat(2, minmax(0, 1fr))",
    gap: "16px",
    paddingTop: "14px",
    borderTop: `1px solid ${tokens.colorNeutralStroke3}`,
    "@media (max-width: 759px)": { gridTemplateColumns: "minmax(0, 1fr)" },
  },
  textarea: { minHeight: "96px" },
  saveRow: { display: "flex", alignItems: "center", gap: "12px", flexWrap: "wrap" },
  saved: { display: "inline-flex", alignItems: "center", gap: "6px", ...typo.meta, color: vt.text2, margin: 0 },
  savedIcon: { color: vt.success, flexShrink: 0 },
  check: { ...typo.meta, ...typo.tabular, color: vt.text2, margin: 0 },
});

const AUDIENCE: Record<string, string> = {
  manager: "With your manager",
  report: "With your team",
  peer: "With colleagues",
  external: "With clients and partners",
  personal: "Personal",
};

/** Segment labels: short enough for a switch. */
const SHORT: Record<string, string> = {
  manager: "Manager",
  report: "Your team",
  peer: "Colleagues",
  external: "Clients and partners",
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

function Forms({ dist, none }: { dist: [string, number][]; none: string }) {
  const styles = useStyles();
  if (dist.length === 0) return <span className={styles.formNone}>{none}</span>;
  return (
    <div className={styles.forms}>
      {dist.map(([form, share]) => (
        <div key={form} className={styles.formRow}>
          {form === "(none)" ? (
            <span className={styles.formNone}>{none}</span>
          ) : (
            <span className={styles.form}>{formLabel(form)}</span>
          )}
          <span className={styles.share}>{Math.round(share * 100)}%</span>
        </div>
      ))}
    </div>
  );
}

function formality(f: number): string {
  return f >= 0.67 ? "Formal" : f <= 0.33 ? "Casual" : "Balanced";
}

/** One audience's style, as label/value traits. */
export function StyleCardView({ card, title }: { card: StyleCard; title: string }) {
  const styles = useStyles();
  const items: Array<[string, ReactNode]> = [
    ["Greeting", <Forms dist={card.greetings} none="No greeting" />],
    ["Sign-off", <Forms dist={card.sign_offs} none="No sign-off" />],
    [
      "Length",
      <span className={styles.value}>
        Usually {card.length.p25}–{card.length.p75} words
        <span className={styles.valueMeta}>median {card.length.median}</span>
      </span>,
    ],
    [
      "Formality",
      <span className={styles.value}>
        {formality(card.formality)}
        <span className={styles.valueMeta}>{Math.round(card.formality * 100)}%</span>
      </span>,
    ],
    ["Exclamation marks", <span className={styles.value}>{card.exclamation_rate > 0.2 ? "Often" : "Rarely or never"}</span>],
    ["Emoji", <span className={styles.value}>{card.emoji_rate > 0.1 ? "Often" : "Rarely or never"}</span>],
  ];
  if (card.phrases.length > 0)
    items.push([
      "Phrases you use often",
      <span className={styles.pills}>
        {card.phrases.map((p) => (
          <Pill key={p}>{p}</Pill>
        ))}
      </span>,
    ]);
  if (card.keep_list.length > 0)
    items.push(["Kept as your voice", <span className={styles.value}>{card.keep_list.join(", ")}</span>]);
  return (
    <div className={styles.panel}>
      <div className={styles.panelHead}>
        <span className={styles.panelTitle}>{title}</span>
        <span className={styles.panelMeta}>
          {card.n} message{card.n === 1 ? "" : "s"}
        </span>
      </div>
      <KeyValueList items={items} />
    </div>
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
  const navigate = useNavigate();
  const [snap, setSnap] = useState<PersonaSnapshot | null>(null);
  const [settings, setSettings] = useState<PersonaSettings | null>(null);
  const [doText, setDoText] = useState("");
  const [dontText, setDontText] = useState("");
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [audience, setAudience] = useState("overall");

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
      <Page title="Your persona">
        <MessageBar intent="error">
          <MessageBarBody>{error}</MessageBarBody>
        </MessageBar>
      </Page>
    );
  if (!snap || !settings) return <PageSkeleton label="Loading your persona…" />;

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
  const selected = snap.audiences.find((a) => a.relationship === audience);
  const languages = Object.entries(snap.by.language)
    .map(([k, v]) => `${k.charAt(0).toUpperCase()}${k.slice(1)} (${v})`)
    .join(", ");

  return (
    <Page
      title="Your persona"
      eyebrow={<Pill>{snap.source === "sample" ? "Sample workspace" : "Microsoft 365"}</Pill>}
      description={
        snap.overall
          ? `Learned from ${snap.learned_items} of your messages: ${snap.by.channel.email ?? 0} emails and ${
              snap.by.channel.chat ?? 0
            } chat messages${languages ? `, in ${languages}` : ""}.`
          : "How you write, as Vanimo learns it from your own sent messages."
      }
    >
      {!snap.overall ? (
        <Section title="How you write">
          <EmptyState
            icon={<PersonVoice20Regular />}
            title="Nothing learned yet"
            action={<Button onClick={() => navigate("/learning")}>Go to Learning</Button>}
          >
            Start learning on the Learning page. Your greetings, sign-offs, length and tone appear here, for everyone you
            write to and for each audience.
          </EmptyState>
        </Section>
      ) : (
        <Section
          title="How you write"
          description="Read from your sent messages. Drafts follow the audience they're for."
          actions={
            snap.audiences.length > 0 ? (
              <Segmented
                label="Audience"
                value={selected ? audience : "overall"}
                onChange={setAudience}
                segments={[
                  { value: "overall", label: "Everyone", count: snap.overall.n },
                  ...snap.audiences.map((a) => ({
                    value: a.relationship,
                    label: SHORT[a.relationship] ?? a.relationship,
                    count: a.card.n,
                  })),
                ]}
              />
            ) : undefined
          }
        >
          {selected ? (
            <StyleCardView card={selected.card} title={AUDIENCE[selected.relationship] ?? selected.relationship} />
          ) : (
            <StyleCardView card={snap.overall} title="With everyone you write to" />
          )}
        </Section>
      )}

      <Section title="Persona studio" description="Adjust how drafts sound, relative to what Vanimo learned.">
        <SettingList>
          {(["formality", "length", "warmth"] as const).map((k) => (
            <SettingRow key={k} label={`${k.charAt(0).toUpperCase()}${k.slice(1)}`} description={SLIDER_LABELS[settings[k] + 2]}>
              <Slider
                className={styles.slider}
                aria-label={`${k.charAt(0).toUpperCase()}${k.slice(1)}`}
                aria-valuetext={SLIDER_LABELS[settings[k] + 2]}
                min={-2}
                max={2}
                step={1}
                value={settings[k]}
                onChange={(_, d) => set({ [k]: d.value })}
              />
            </SettingRow>
          ))}
          <SettingRow label="Emoji" description="Let drafts use emoji.">
            <Switch checked={settings.emoji} onChange={(_, d) => set({ emoji: d.checked })} aria-label="Emoji allowed" />
          </SettingRow>
          <SettingRow label="Corrections" description="Fix your typos while keeping your voice, or keep drafts exactly in your style.">
            <RadioGroup
              layout="horizontal"
              aria-label="Corrections"
              className={styles.radios}
              value={settings.polish}
              onChange={(_, d) => set({ polish: d.value as PersonaSettings["polish"] })}
            >
              <Radio value="light" label="Fix typos, keep my voice" />
              <Radio value="none" label="Exactly my style" />
            </RadioGroup>
          </SettingRow>
        </SettingList>
        <div className={styles.phrases}>
          <Field label="Phrases to use (one per line)">
            <Textarea
              className={styles.textarea}
              value={doText}
              onChange={(_, d) => { setDoText(d.value); setSaved(false); }}
              resize="vertical"
            />
          </Field>
          <Field label="Phrases never to use (one per line)">
            <Textarea
              className={styles.textarea}
              value={dontText}
              onChange={(_, d) => { setDontText(d.value); setSaved(false); }}
              resize="vertical"
            />
          </Field>
        </div>
        <div className={styles.saveRow}>
          <Button appearance="primary" onClick={() => void save()}>
            Save
          </Button>
          {saved && (
            <Rise visible appear>
              <p className={styles.saved} role="status">
                <CheckmarkCircle16Filled className={styles.savedIcon} aria-hidden />
                Saved. Never-send words in phrases are stored as placeholders.
              </p>
            </Rise>
          )}
        </div>
      </Section>

      <EditsCard />

      {metrics && (
        <Section
          title="Style check (offline baseline)"
          description="Offline stand-in, no AI model: held-out replies re-drafted from your style cards and closest past reply. The Claude drafter must beat these numbers."
        >
          <p className={styles.check}>
            {metrics.n_eval} replies checked · greeting match {pct(metrics.greeting_match)} · sign-off match{" "}
            {pct(metrics.sign_off_match)} · length match {pct(metrics.length_ratio)} · wording overlap{" "}
            {pct(metrics.bigram_overlap)}
          </p>
        </Section>
      )}
    </Page>
  );
}

function pct(v: number | string | undefined): string {
  return typeof v === "number" ? `${Math.round(v * 100)}%` : "—";
}
