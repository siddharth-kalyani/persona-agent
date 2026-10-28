/** Your style (F15): how you write, as Vanimo learned it from your own sent messages.
 *
 * In order of what matters to you:
 *  1. Tone groups: who you're formal, friendly or casual with (people and group chats), why, and a one-click
 *     "move to" when Vanimo got someone wrong (your choice always wins and survives learning again);
 *  2. Your words: the phrases you use for each kind of thing, per tone, and your own spellings;
 *  3. How you write in each channel (email, Teams 1:1, Teams groups), per tone: greetings, sign-offs, length;
 *  4. Adjust drafts (the studio), rules learned from your edits, and the style check. */
import {
  Button,
  Field,
  makeStyles,
  Menu,
  MenuDivider,
  MenuItem,
  MenuList,
  MenuPopover,
  MenuTrigger,
  MessageBar,
  MessageBarBody,
  Radio,
  RadioGroup,
  Slider,
  Switch,
  Textarea,
  Tooltip,
} from "@fluentui/react-components";
import {
  ArrowSync16Regular,
  Briefcase16Regular,
  Checkmark16Regular,
  CheckmarkCircle16Filled,
  ChevronDown16Regular,
  ClipboardCheckmark20Regular,
  Emoji16Regular,
  HandWave16Regular,
  Heart16Regular,
  Important16Regular,
  MoreHorizontal16Regular,
  Options20Regular,
  People16Regular,
  PeopleTeam20Regular,
  PersonVoice16Regular,
  Save16Regular,
  Signature16Regular,
  TextExpand16Regular,
  TextProofingToolsAbc16Regular,
  TextQuote16Regular,
  TextQuote20Regular,
  Translate16Regular,
} from "@fluentui/react-icons";
import { useCallback, useEffect, useState, type ReactElement, type ReactNode } from "react";
import { useNavigate } from "react-router-dom";
import type {
  Bucket,
  LearningStatus,
  PersonaSettings,
  PersonaSnapshot,
  StyleCard,
  ToneConversation,
  ToneGroup,
} from "../../api/client";
import { useApi } from "../../api/context";
import {
  EmptyState,
  EngineBadge,
  IconTile,
  KeyValueList,
  List,
  ListRow,
  Meter,
  Page,
  PageSkeleton,
  PersonAvatar,
  Pill,
  Rise,
  Section,
  Segmented,
  SettingList,
  SettingRow,
  Surface,
  typo,
  vt,
} from "../../ui";
import { errorText } from "../Home";
import { EditsCard, Metric, MetricGrid } from "./EditsCard";
import { LearnFirst } from "./LearnFirst";
import { BUCKET_INFO, TONE_INFO, TONE_ORDER, toneReason } from "./tone";

const PHONE = "@media (max-width: 639px)";
const SHOWN_PER_GROUP = 6;

const useStyles = makeStyles({
  groups: {
    display: "grid",
    gridTemplateColumns: "repeat(3, minmax(0, 1fr))",
    gap: "16px",
    alignItems: "start",
    "@media (max-width: 1099px)": { gridTemplateColumns: "minmax(0, 1fr)" },
  },
  group: { display: "grid", minWidth: 0 },
  groupHead: {
    display: "grid",
    gridTemplateColumns: "auto minmax(0, 1fr) auto",
    gap: "12px",
    alignItems: "center",
    padding: "14px 16px",
    borderBottom: `1px solid ${vt.borderSubtle}`,
  },
  groupText: { display: "grid", minWidth: 0 },
  groupTitle: { ...typo.cardTitle, color: vt.text1, margin: 0 },
  groupMeta: { ...typo.meta, color: vt.text2 },
  groupExample: { ...typo.meta, color: vt.text3, padding: "10px 16px 0", margin: 0, fontStyle: "italic" },
  groupEmpty: { ...typo.meta, color: vt.text3, padding: "16px", margin: 0 },
  rowMeta: { display: "inline-flex", alignItems: "center", gap: "6px", "& > svg": { color: vt.text3, flexShrink: 0 } },
  more: { display: "flex", justifyContent: "center", padding: "6px", borderTop: `1px solid ${vt.borderSubtle}` },
  words: { display: "grid", gap: "12px" },
  switcher: { paddingBottom: "4px" },
  phrases: { display: "flex", gap: "6px", flexWrap: "wrap" },
  wordsNote: { ...typo.meta, color: vt.text2, margin: 0, maxWidth: "72ch" },
  panel: { display: "grid", gap: "8px", minWidth: 0 },
  switches: { display: "flex", gap: "12px", flexWrap: "wrap", paddingBottom: "8px" },
  panelHead: { display: "flex", alignItems: "center", gap: "8px", flexWrap: "wrap" },
  panelTitle: { ...typo.cardTitle, color: vt.text1 },
  term: { display: "inline-flex", alignItems: "center", gap: "8px", "& > svg": { color: vt.text3, flexShrink: 0 } },
  forms: { display: "grid", gap: "6px" },
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
  slider: { width: "240px", maxWidth: "100%", [PHONE]: { width: "100%" } },
  radios: { flexWrap: "wrap" },
  studioPhrases: {
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
  details: { display: "flex", justifyContent: "center" },
});

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
    .replaceAll("{name}", "‹name›")
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

/** One style card as label/value traits. */
export function StyleCardView({ card, title }: { card: StyleCard; title: string }) {
  const styles = useStyles();
  const hinglish = (card.languages.hinglish ?? 0) + (card.languages.hindi ?? 0);
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
  if (hinglish > 0)
    items.push([
      <Term icon={<Translate16Regular />}>Hinglish</Term>,
      <Share share={hinglish}>
        <span className={styles.value}>Hindi mixed in</span>
      </Share>,
    ]);
  if (card.phrases.length > 0)
    items.push([
      <Term icon={<TextQuote16Regular />}>Phrases you use often</Term>,
      <span className={styles.phrases}>
        {card.phrases.map((p) => (
          <Pill key={p}>{p}</Pill>
        ))}
      </span>,
    ]);
  if (card.keep_list.length > 0)
    items.push([
      <Term icon={<PersonVoice16Regular />}>Kept as your voice</Term>,
      <span className={styles.phrases}>
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

/** "Move to…": the three tones, and back to what Vanimo judged once you've chosen. */
function ToneMenu({ c, onChoose }: { c: ToneConversation; onChoose: (tone: ToneGroup | null) => void }) {
  return (
    <Menu positioning="below-end">
      <MenuTrigger disableButtonEnhancement>
        <Tooltip content={`Change the tone for ${c.label ?? "this conversation"}`} relationship="label" withArrow>
          <Button appearance="subtle" size="small" icon={<MoreHorizontal16Regular />} />
        </Tooltip>
      </MenuTrigger>
      <MenuPopover>
        <MenuList>
          {TONE_ORDER.map((t) => (
            <MenuItem
              key={t}
              icon={c.tone === t ? <Checkmark16Regular /> : TONE_INFO[t].icon}
              disabled={c.tone === t}
              onClick={() => onChoose(t)}
            >
              {c.tone === t ? `${TONE_INFO[t].label} (now)` : `Move to ${TONE_INFO[t].label.toLowerCase()}`}
            </MenuItem>
          ))}
          {c.override && (
            <>
              <MenuDivider />
              <MenuItem icon={<ArrowSync16Regular />} onClick={() => onChoose(null)}>
                Let Vanimo decide ({TONE_INFO[c.judged].label.toLowerCase()})
              </MenuItem>
            </>
          )}
        </MenuList>
      </MenuPopover>
    </Menu>
  );
}

/** One tone group: who's in it (people and group chats), why, and "move to". */
function ToneGroupCard({
  tone,
  members,
  onChoose,
}: {
  tone: ToneGroup;
  members: ToneConversation[];
  onChoose: (c: ToneConversation, tone: ToneGroup | null) => void;
}) {
  const styles = useStyles();
  const [all, setAll] = useState(false);
  const info = TONE_INFO[tone];
  const shown = all ? members : members.slice(0, SHOWN_PER_GROUP);
  return (
    <Surface padding="none" className={styles.group} as="section" aria-label={`${info.label} tone`}>
      <div className={styles.groupHead}>
        <IconTile icon={info.icon} tone="accent" size={32} />
        <div className={styles.groupText}>
          <h3 className={styles.groupTitle}>{info.label}</h3>
          <span className={styles.groupMeta}>{info.description}</span>
        </div>
        <Pill>{members.length}</Pill>
      </div>
      <p className={styles.groupExample}>“{info.example}”</p>
      {members.length === 0 ? (
        <p className={styles.groupEmpty}>Nobody yet.</p>
      ) : (
        <List label={`${info.label} tone`}>
          {shown.map((c) => {
            const bucket = BUCKET_INFO[c.bucket];
            const name = c.label ?? (c.bucket === "group" ? "A group chat" : "Someone you write to");
            return (
              <ListRow
                key={`${c.bucket}:${c.key}`}
                leading={
                  c.bucket === "group" ? (
                    <IconTile icon={<People16Regular />} tone="purple" size={32} />
                  ) : (
                    <PersonAvatar name={name} id={c.email} size={32} />
                  )
                }
                title={name}
                meta={
                  <Tooltip content={toneReason(c)} relationship="description" withArrow>
                    <span className={styles.rowMeta} tabIndex={0}>
                      {bucket.icon}
                      {bucket.short}
                      {c.override ? " · your choice" : ""}
                    </span>
                  </Tooltip>
                }
                trailing={<ToneMenu c={c} onChoose={(t) => onChoose(c, t)} />}
              />
            );
          })}
        </List>
      )}
      {members.length > SHOWN_PER_GROUP && (
        <div className={styles.more}>
          <Button appearance="subtle" size="small" icon={<ChevronDown16Regular />} onClick={() => setAll((v) => !v)}>
            {all ? "Show fewer" : `Show all ${members.length}`}
          </Button>
        </div>
      )}
    </Surface>
  );
}

export function Persona() {
  const styles = useStyles();
  const api = useApi();
  const navigate = useNavigate();
  const [snap, setSnap] = useState<PersonaSnapshot | null>(null);
  const [learning, setLearning] = useState<LearningStatus | null>(null);
  const [settings, setSettings] = useState<PersonaSettings | null>(null);
  const [doText, setDoText] = useState("");
  const [dontText, setDontText] = useState("");
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [wordsTone, setWordsTone] = useState<ToneGroup>("formal");
  const [channel, setChannel] = useState<Bucket>("email");
  const [cardTone, setCardTone] = useState<ToneGroup | "all">("all");
  const [details, setDetails] = useState(false);

  const load = useCallback(async () => {
    try {
      const [s, l] = await Promise.all([api.persona(), api.learning()]);
      setSnap(s);
      setLearning(l);
      setSettings(s.settings);
      setDoText(s.settings.phrases_do.join("\n"));
      setDontText(s.settings.phrases_dont.join("\n"));
    } catch (e) {
      setError(errorText(e));
    }
  }, [api]);

  useEffect(() => {
    void load();
  }, [load]);

  if (error && !snap)
    return (
      <Page title="Your style">
        <MessageBar intent="error">
          <MessageBarBody>{error}</MessageBarBody>
        </MessageBar>
      </Page>
    );
  if (!snap || !settings || !learning) return <PageSkeleton label="Loading your style…" />;

  if (!learning.learned)
    return (
      <Page title="Your style" description="How you write to the people you work with, learned from your own messages.">
        <LearnFirst
          state={{
            reviewDone: learning.onboardingState === "review_done",
            learningRunning: learning.run?.status === "running",
            learningOutdated: learning.outdated,
          }}
          onLearned={() => void load()}
        />
      </Page>
    );

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
  const choose = async (c: ToneConversation, tone: ToneGroup | null) => {
    try {
      await api.setTone(c.bucket, c.key, tone);
      await load();
    } catch (e) {
      setError(errorText(e));
    }
  };

  const byTone = (t: ToneGroup) => snap.conversations.filter((c) => c.tone === t);
  const words = snap.vocabulary.tones[wordsTone] ?? {};
  const situations = Object.entries(words).filter(([, ps]) => ps.length > 0);
  const card =
    cardTone === "all" ? snap.bucket_cards[channel] : snap.tone_bucket_cards[`${cardTone}|${channel}`];
  const metrics = snap.evaluation?.metrics;
  const num = (v: number | string | undefined) => (typeof v === "number" ? v : undefined);
  const email = snap.by.bucket.email ?? 0;
  const dms = snap.by.bucket.dm ?? 0;
  const groups = snap.by.bucket.group ?? 0;

  return (
    <Page
      title="Your style"
      description={`Learned from ${snap.learned_items} of your messages: ${email} emails, ${dms} Teams 1:1 and ${groups} group chat messages.`}
      info="Vanimo reads how you write to each person, never job titles alone: a senior who is a close friend can be casual. Names, ID numbers and never-send words are removed before anything is stored, and only you can see this page."
      actions={
        <Button icon={<ArrowSync16Regular />} onClick={() => navigate("/learning")}>
          Learn again
        </Button>
      }
    >
      {error && (
        <MessageBar intent="error">
          <MessageBarBody>{error}</MessageBarBody>
        </MessageBar>
      )}

      <Section
        icon={<PeopleTeam20Regular />}
        title="Who you're formal, friendly or casual with"
        description="Each draft is written in the tone you use with that person or group. Got someone wrong? Move them: your choice always wins."
      >
        <div className={styles.groups}>
          {TONE_ORDER.map((t) => (
            <ToneGroupCard key={t} tone={t} members={byTone(t)} onChoose={(c, tone) => void choose(c, tone)} />
          ))}
        </div>
      </Section>

      <Section
        icon={<TextQuote20Regular />}
        title="Your words"
        description="What you say for each kind of message, per tone, used across email and Teams."
        info="A phrase is shared only after you've used it in 3 different conversations, so nothing you said to one person (a nickname, a project name) reaches anyone else. Names and numbers are never kept."
      >
        <div className={styles.words}>
          <div className={styles.switcher}>
            <Segmented
              label="Tone"
              value={wordsTone}
              onChange={setWordsTone}
              segments={TONE_ORDER.map((t) => ({
                value: t,
                label: TONE_INFO[t].label,
                icon: TONE_INFO[t].icon,
                count: Object.values(snap.vocabulary.tones[t] ?? {}).reduce((n, ps) => n + ps.length, 0),
              }))}
            />
          </div>
          <Surface>
            {situations.length > 0 ? (
              <KeyValueList
                items={situations.map(([situation, phrases]) => [
                  <span>{snap.vocabulary.labels[situation] ?? situation}</span>,
                  <span className={styles.phrases}>
                    {phrases.map((p) => (
                      <Tooltip
                        key={p.phrase}
                        relationship="description"
                        withArrow
                        content={`Used ${p.uses} times in ${p.conversations} conversations · ${p.channels
                          .map((b) => BUCKET_INFO[b].short)
                          .join(", ")}`}
                      >
                        <Pill tabIndex={0}>{p.phrase}</Pill>
                      </Tooltip>
                    ))}
                  </span>,
                ])}
              />
            ) : (
              <EmptyState icon={<TextQuote20Regular />} title={`No ${TONE_INFO[wordsTone].label.toLowerCase()} phrases yet`} center>
                They appear once you've used the same words in 3 different conversations.
              </EmptyState>
            )}
          </Surface>
          {(snap.vocabulary.spellings.length > 0 || settings.phrases_dont.length > 0) && (
            <KeyValueList
              items={[
                ...(snap.vocabulary.spellings.length > 0
                  ? ([
                      [
                        <Term icon={<TextProofingToolsAbc16Regular />}>Your spellings</Term>,
                        <span className={styles.phrases}>
                          {snap.vocabulary.spellings.map((s) => (
                            <Pill key={s.use}>
                              {s.use} (not {s.instead_of})
                            </Pill>
                          ))}
                        </span>,
                      ],
                    ] as Array<[ReactNode, ReactNode]>)
                  : []),
                ...(settings.phrases_dont.length > 0
                  ? ([
                      [
                        <Term icon={<Important16Regular />}>Never use</Term>,
                        <span className={styles.phrases}>
                          {settings.phrases_dont.map((p) => (
                            <Pill key={p} tone="danger">
                              {p}
                            </Pill>
                          ))}
                        </span>,
                      ],
                    ] as Array<[ReactNode, ReactNode]>)
                  : []),
              ]}
            />
          )}
        </div>
      </Section>

      {!details ? (
        <div className={styles.details}>
          <Button appearance="subtle" icon={<ChevronDown16Regular />} onClick={() => setDetails(true)}>
            Show greetings, sign-offs and length per channel
          </Button>
        </div>
      ) : (
        <Rise visible appear>
          <Section
            variant="card"
            title="How you write in each channel"
            description="Greetings, sign-offs and length stay with their channel: a chat never gets “Best regards”."
          >
            <div className={styles.switches}>
              <Segmented
                label="Channel"
                value={channel}
                onChange={setChannel}
                segments={(["email", "dm", "group"] as Bucket[]).map((b) => ({
                  value: b,
                  label: BUCKET_INFO[b].short,
                  icon: BUCKET_INFO[b].icon,
                  count: snap.by.bucket[b] ?? 0,
                }))}
              />
              <Segmented
                label="Tone"
                value={cardTone}
                onChange={setCardTone}
                segments={[
                  { value: "all" as const, label: "All" },
                  ...TONE_ORDER.map((t) => ({ value: t, label: TONE_INFO[t].label })),
                ]}
              />
            </div>
            {card ? (
              <StyleCardView
                card={card}
                title={`${cardTone === "all" ? "All tones" : TONE_INFO[cardTone].label} · ${BUCKET_INFO[channel].label}`}
              />
            ) : (
              <EmptyState icon={<TextQuote20Regular />} title="Not enough messages here yet" center>
                Vanimo needs at least 3 of your messages of this kind. Until then, drafts use your general style.
              </EmptyState>
            )}
          </Section>
        </Rise>
      )}

      <Section
        variant="card"
        icon={<Options20Regular />}
        title="Adjust drafts"
        description="Nudge every draft, relative to what Vanimo learned."
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
          <SettingRow icon={<Emoji16Regular />} label="Emoji" description="Let drafts use emoji where you do.">
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
        <div className={styles.studioPhrases}>
          <Field label="Phrases to use (one per line)">
            <Textarea
              className={styles.textarea}
              value={doText}
              onChange={(_, d) => {
                setDoText(d.value);
                setSaved(false);
              }}
              resize="vertical"
            />
          </Field>
          <Field label="Phrases never to use (one per line)">
            <Textarea
              className={styles.textarea}
              value={dontText}
              onChange={(_, d) => {
                setDontText(d.value);
                setSaved(false);
              }}
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
          description="Some of your real replies were set aside, re-drafted, and compared with what you actually wrote."
          actions={
            <EngineBadge
              offline
              detail="Offline stand-in, no AI model: this baseline re-drafts the set-aside replies from your style and closest past reply."
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
