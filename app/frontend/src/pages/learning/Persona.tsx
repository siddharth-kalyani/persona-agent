/** Your persona: how you write, as Vanimo learned it from your own sent messages, per audience (a
 * segmented switch: everyone, your manager, your team, clients…), as label/value traits with
 * proportion meters; the studio that adjusts drafts relative to that; the rules learned from your
 * edits; and the offline style check as metric wells. Each block is one card. */
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
} from "@fluentui/react-components";
import {
  Briefcase16Regular,
  CheckmarkCircle16Filled,
  ClipboardCheckmark20Regular,
  Emoji16Regular,
  HandWave16Regular,
  Heart16Regular,
  Important16Regular,
  Options20Regular,
  PersonVoice16Regular,
  PersonVoice20Regular,
  Save16Regular,
  Signature16Regular,
  TextExpand16Regular,
  TextProofingToolsAbc16Regular,
  TextQuote16Regular,
} from "@fluentui/react-icons";
import { useEffect, useState, type ReactElement, type ReactNode } from "react";
import { useNavigate } from "react-router-dom";
import type { PersonaSettings, PersonaSnapshot, StyleCard } from "../../api/client";
import { useApi } from "../../api/context";
import {
  EmptyState,
  EngineBadge,
  KeyValueList,
  Meter,
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
import { EditsCard, Metric, MetricGrid } from "./EditsCard";

const PHONE = "@media (max-width: 639px)";

const useStyles = makeStyles({
  panel: { display: "grid", gap: "8px", minWidth: 0 },
  switcher: { paddingBottom: "8px" },
  panelHead: { display: "flex", alignItems: "center", gap: "8px", flexWrap: "wrap" },
  panelTitle: { ...typo.cardTitle, color: vt.text1 },
  term: { display: "inline-flex", alignItems: "center", gap: "8px", "& > svg": { color: vt.text3, flexShrink: 0 } },
  forms: { display: "grid", gap: "6px" },
  // A form and its share: the words, a meter, the percentage.
  share: {
    display: "grid",
    gridTemplateColumns: "minmax(0, 1fr) 120px 40px",
    alignItems: "center",
    gap: "12px",
    maxWidth: "520px",
    [PHONE]: { gridTemplateColumns: "minmax(0, 1fr) 56px 36px", gap: "8px" },
  },
  form: { ...typo.body, color: vt.text1, whiteSpace: "pre-line", overflowWrap: "anywhere" },
  formNone: { ...typo.body, color: vt.text2 },
  pct: { ...typo.meta, ...typo.tabular, color: vt.text2, textAlign: "right" },
  value: { ...typo.body, color: vt.text1 },
  valueMeta: { ...typo.meta, ...typo.tabular, color: vt.text3, marginLeft: "8px" },
  pills: { display: "flex", gap: "6px", flexWrap: "wrap" },
  slider: { width: "240px", maxWidth: "100%", [PHONE]: { width: "100%" } },
  radios: { flexWrap: "wrap" },
  phrases: {
    display: "grid",
    gridTemplateColumns: "repeat(2, minmax(0, 1fr))",
    gap: "16px",
    paddingTop: "16px",
    marginTop: "2px",
    borderTop: `1px solid ${vt.borderSubtle}`,
    "@media (max-width: 759px)": { gridTemplateColumns: "minmax(0, 1fr)" },
  },
  textarea: { minHeight: "96px" },
  saveRow: { display: "flex", alignItems: "center", gap: "12px", flexWrap: "wrap", marginTop: "16px" },
  saved: { display: "inline-flex", alignItems: "center", gap: "6px", ...typo.meta, color: vt.text2, margin: 0 },
  savedIcon: { color: vt.success, flexShrink: 0 },
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

/** The studio's settings and the traits they adjust share icons. */
const SETTING_ICON: Record<"formality" | "length" | "warmth", ReactElement> = {
  formality: <Briefcase16Regular />,
  length: <TextExpand16Regular />,
  warmth: <Heart16Regular />,
};

/** "Hi {first}," → "Hi <first name>," for display. */
export function formLabel(form: string): string {
  return form
    .replaceAll("{first}", "‹first name›")
    .replaceAll("{full}", "‹full name›")
    .replaceAll("{last}", "‹surname›")
    .replaceAll("{me_full}", "‹your full name›")
    .replaceAll("{me}", "‹your name›");
}

/** A share as a meter row: what, how often (bar), the percentage. */
function Share({ share, children }: { share: number; children: ReactNode }) {
  const styles = useStyles();
  return (
    <div className={styles.share}>
      {children}
      <Meter value={share} />
      <span className={styles.pct}>{Math.round(share * 100)}%</span>
    </div>
  );
}

function Forms({ dist, none }: { dist: [string, number][]; none: string }) {
  const styles = useStyles();
  if (dist.length === 0) return <span className={styles.formNone}>{none}</span>;
  return (
    <div className={styles.forms}>
      {dist.map(([form, share]) => (
        <Share key={form} share={share}>
          {form === "(none)" ? (
            <span className={styles.formNone}>{none}</span>
          ) : (
            <span className={styles.form}>{formLabel(form)}</span>
          )}
        </Share>
      ))}
    </div>
  );
}

function formality(f: number): string {
  return f >= 0.67 ? "Formal" : f <= 0.33 ? "Casual" : "Balanced";
}

/** A trait's label with its icon. */
function Term({ icon, children }: { icon: ReactElement; children: ReactNode }) {
  const styles = useStyles();
  return (
    <span className={styles.term}>
      {icon}
      {children}
    </span>
  );
}

/** One audience's style, as label/value traits. */
export function StyleCardView({ card, title }: { card: StyleCard; title: string }) {
  const styles = useStyles();
  const items: Array<[ReactNode, ReactNode]> = [
    [<Term icon={<HandWave16Regular />}>Greeting</Term>, <Forms dist={card.greetings} none="No greeting" />],
    [<Term icon={<Signature16Regular />}>Sign-off</Term>, <Forms dist={card.sign_offs} none="No sign-off" />],
    [
      <Term icon={SETTING_ICON.length}>Length</Term>,
      <span className={styles.value}>
        Usually {card.length.p25}–{card.length.p75} words
        <span className={styles.valueMeta}>median {card.length.median}</span>
      </span>,
    ],
    [
      <Term icon={SETTING_ICON.formality}>Formality</Term>,
      <Share share={card.formality}>
        <span className={styles.value}>{formality(card.formality)}</span>
      </Share>,
    ],
    [
      <Term icon={<Important16Regular />}>Exclamation marks</Term>,
      <span className={styles.value}>{card.exclamation_rate > 0.2 ? "Often" : "Rarely or never"}</span>,
    ],
    [<Term icon={<Emoji16Regular />}>Emoji</Term>, <span className={styles.value}>{card.emoji_rate > 0.1 ? "Often" : "Rarely or never"}</span>],
  ];
  if (card.phrases.length > 0)
    items.push([
      <Term icon={<TextQuote16Regular />}>Phrases you use often</Term>,
      <span className={styles.pills}>
        {card.phrases.map((p) => (
          <Pill key={p}>{p}</Pill>
        ))}
      </span>,
    ]);
  if (card.keep_list.length > 0)
    items.push([
      <Term icon={<PersonVoice16Regular />}>Kept as your voice</Term>,
      <span className={styles.pills}>
        {card.keep_list.map((w) => (
          <Pill key={w} tone="accent">
            {w}
          </Pill>
        ))}
      </span>,
    ]);
  return (
    <div className={styles.panel}>
      <div className={styles.panelHead}>
        <span className={styles.panelTitle}>{title}</span>
        <Pill>
          {card.n} message{card.n === 1 ? "" : "s"}
        </Pill>
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
  const num = (v: number | string | undefined) => (typeof v === "number" ? v : undefined);

  return (
    <Page
      title="Your persona"
      description={
        snap.overall
          ? `Learned from ${snap.learned_items} of your messages: ${snap.by.channel.email ?? 0} emails and ${
              snap.by.channel.chat ?? 0
            } chat messages${languages ? `, in ${languages}` : ""}.`
          : "How you write, as Vanimo learns it from your own sent messages."
      }
    >
      {!snap.overall ? (
        <Section variant="card" icon={<PersonVoice20Regular />} title="How you write">
          <EmptyState
            center
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
          variant="card"
          icon={<PersonVoice20Regular />}
          title="How you write"
          description="Read from your sent messages. Drafts follow the audience they're for."
        >
          {snap.audiences.length > 0 && (
            <div className={styles.switcher}>
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
            </div>
          )}
          {selected ? (
            <StyleCardView card={selected.card} title={AUDIENCE[selected.relationship] ?? selected.relationship} />
          ) : (
            <StyleCardView card={snap.overall} title="With everyone you write to" />
          )}
        </Section>
      )}

      <Section
        variant="card"
        icon={<Options20Regular />}
        title="Persona studio"
        description="Adjust how drafts sound, relative to what Vanimo learned."
      >
        <SettingList>
          {(["formality", "length", "warmth"] as const).map((k) => (
            <SettingRow
              key={k}
              icon={SETTING_ICON[k]}
              label={`${k.charAt(0).toUpperCase()}${k.slice(1)}`}
              description={SLIDER_LABELS[settings[k] + 2]}
            >
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
          <SettingRow icon={<Emoji16Regular />} label="Emoji" description="Let drafts use emoji.">
            <Switch checked={settings.emoji} onChange={(_, d) => set({ emoji: d.checked })} aria-label="Emoji allowed" />
          </SettingRow>
          <SettingRow
            icon={<TextProofingToolsAbc16Regular />}
            label="Corrections"
            description="Fix your typos while keeping your voice, or keep drafts exactly in your style."
          >
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
          <Button appearance="primary" icon={<Save16Regular />} onClick={() => void save()}>
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
          variant="card"
          icon={<ClipboardCheckmark20Regular />}
          title="Style check"
          description="Held-out replies re-drafted from your style cards and closest past reply. The Claude drafter must beat these numbers."
          actions={
            <EngineBadge
              offline
              detail="Offline stand-in, no AI model: this baseline re-drafts held-out replies from your style cards and closest past reply."
            />
          }
        >
          <MetricGrid label="Style check results">
            <Metric label="Replies checked" value={metrics.n_eval ?? "—"} />
            <Metric label="Greeting match" value={pct(metrics.greeting_match)} meter={num(metrics.greeting_match)} />
            <Metric label="Sign-off match" value={pct(metrics.sign_off_match)} meter={num(metrics.sign_off_match)} />
            <Metric label="Length match" value={pct(metrics.length_ratio)} meter={num(metrics.length_ratio)} />
            <Metric label="Wording overlap" value={pct(metrics.bigram_overlap)} meter={num(metrics.bigram_overlap)} />
          </MetricGrid>
        </Section>
      )}
    </Page>
  );
}

function pct(v: number | string | undefined): string {
  return typeof v === "number" ? `${Math.round(v * 100)}%` : "—";
}
