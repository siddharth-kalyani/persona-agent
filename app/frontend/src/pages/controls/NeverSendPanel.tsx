import {
  Button,
  Checkbox,
  Field,
  Input,
  makeStyles,
  mergeClasses,
  MessageBar,
  MessageBarBody,
  Radio,
  RadioGroup,
  Switch,
  tokens,
} from "@fluentui/react-components";
import {
  Add16Regular,
  Dismiss16Regular,
  Eye16Regular,
  Person16Regular,
  Prohibited20Regular,
  Tag16Regular,
  TextBulletListSquare20Regular,
  TextT16Regular,
  Translate16Regular,
} from "@fluentui/react-icons";
import { useCallback, useEffect, useState, type ReactElement, type ReactNode } from "react";
import type { NeverSendWord, TermKind, WordPreview } from "../../api/client";
import { useApi } from "../../api/context";
import { EmptyState, IconAction, Pill, Rise, Section, typo, vt } from "../../ui";
import { errorText } from "../Home";

const useStyles = makeStyles({
  stack: { display: "grid", gap: "20px", minWidth: 0 },
  form: { display: "grid", gap: "16px", minWidth: 0 },
  fields: {
    display: "grid",
    gridTemplateColumns: "minmax(0, 1fr) minmax(0, 1fr)",
    gap: "12px 16px",
    alignItems: "start",
    "@media (max-width: 639px)": { gridTemplateColumns: "minmax(0, 1fr)" },
  },
  kind: { display: "grid", gap: "2px" },
  kindHelp: { ...typo.meta, color: vt.text2, margin: 0, paddingLeft: "4px" },
  actions: {
    display: "flex",
    gap: "8px 12px",
    alignItems: "center",
    flexWrap: "wrap",
    paddingTop: "16px",
    borderTop: `1px solid ${vt.borderSubtle}`,
  },
  spacer: { flexGrow: 1, "@media (max-width: 479px)": { display: "none" } },
  preview: {
    display: "grid",
    gap: "10px",
    padding: "12px 14px",
    borderRadius: tokens.borderRadiusLarge,
    backgroundColor: vt.inset,
    border: `1px solid ${vt.borderSubtle}`,
  },
  previewText: { ...typo.body, color: vt.text1, margin: 0 },
  variants: { display: "flex", gap: "4px", flexWrap: "wrap" },
  variant: { ...typo.address, fontWeight: 400, fontSize: "12.5px" },
  list: { listStyle: "none", margin: 0, padding: 0, display: "grid" },
  wordRow: {
    display: "grid",
    gridTemplateColumns: "minmax(0, 1fr) auto",
    alignItems: "center",
    gap: "8px 16px",
    padding: "10px 12px 10px 16px",
    borderTop: `1px solid ${vt.borderSubtle}`,
    "@media (max-width: 479px)": { gridTemplateColumns: "minmax(0, 1fr)" },
  },
  wordFirst: { borderTopColor: "transparent" },
  wordMain: { display: "flex", alignItems: "center", gap: "6px 12px", flexWrap: "wrap", minWidth: 0 },
  // The word itself as a token: the thing that is masked.
  chip: {
    display: "inline-flex",
    alignItems: "center",
    gap: "6px",
    minHeight: "26px",
    padding: "2px 10px 2px 8px",
    borderRadius: "7px",
    backgroundColor: vt.inset,
    border: `1px solid ${vt.border}`,
    ...typo.itemTitle,
    ...typo.address,
    color: vt.text1,
    maxWidth: "100%",
    "& > svg": { flexShrink: 0, color: vt.text3 },
  },
  wordMeta: {
    display: "inline-flex",
    alignItems: "center",
    gap: "4px 10px",
    flexWrap: "wrap",
    ...typo.meta,
    color: vt.text2,
    minWidth: 0,
    overflowWrap: "anywhere",
  },
  metaItem: { display: "inline-flex", alignItems: "center", gap: "4px", "& > svg": { color: vt.text3, flexShrink: 0 } },
  wordActions: { display: "flex", alignItems: "center", gap: "4px", justifyContent: "flex-end" },
  switchLabel: { ...typo.meta, color: vt.text2 },
});

/** A card section one heading level down (h3): it sits inside the Sources section of Setup and My data. */
function Card({ title, ...rest }: { icon: ReactElement; title: string; description?: string; info?: string; count?: number; flush?: boolean; children: ReactNode }) {
  return <Section variant="card" headingLevel={3} title={title} aria-label={title} {...rest} />;
}

const KIND_HELP: Record<TermKind, string> = {
  word: "A word or phrase, matched as a whole word (plus plurals).",
  name: "A person's name, also with -ji, bhai, 's and similar endings.",
  codename: "A codename: matched inside other words and without spaces (project-falcon, projectfalcon).",
};

const KIND_LABEL: Record<TermKind, string> = { word: "Word", name: "Name", codename: "Codename" };

const KIND_ICON: Record<TermKind, ReactElement> = {
  word: <TextT16Regular aria-hidden />,
  name: <Person16Regular aria-hidden />,
  codename: <Tag16Regular aria-hidden />,
};

/** Never-send words: never stored by Vanimo in readable form and never sent to any AI model. */
export function NeverSendPanel({ onChange }: { onChange?: () => void }) {
  const styles = useStyles();
  const api = useApi();
  const [words, setWords] = useState<NeverSendWord[]>([]);
  const [text, setText] = useState("");
  const [kind, setKind] = useState<TermKind>("word");
  const [extra, setExtra] = useState("");
  const [allow, setAllow] = useState(false);
  const [folds, setFolds] = useState(false);
  const [preview, setPreview] = useState<WordPreview | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    try {
      setWords(await api.words());
    } catch (e) {
      setError(errorText(e));
    }
  }, [api]);

  useEffect(() => {
    void load();
  }, [load]);

  useEffect(() => {
    setPreview(null);
    setFolds(false);
  }, [text, kind]);

  async function check() {
    setError(null);
    try {
      setPreview(await api.previewWord(text, kind));
    } catch (e) {
      setError(errorText(e));
    }
  }

  async function save() {
    setBusy(true);
    setError(null);
    try {
      const spellings = extra.split(",").map((s) => s.trim()).filter(Boolean);
      await api.addWord(text, kind, spellings, allow, folds);
      setText("");
      setExtra("");
      setAllow(false);
      setPreview(null);
      await load();
      onChange?.();
    } catch (e) {
      setError(errorText(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className={styles.stack}>
      {error && (
        <MessageBar intent="error">
          <MessageBarBody>{error}</MessageBarBody>
        </MessageBar>
      )}

      <Card
        icon={<Prohibited20Regular />}
        title="Add a never-send word"
        description="Replaced before any AI model sees your text."
        info="Codenames, client nicknames, family names, internal figures. Drafts show [removed] where they would appear, unless you allow a word in your own drafts."
      >
        <div className={styles.form}>
          <div className={styles.fields}>
            <Field label="Word or phrase">
              <Input value={text} onChange={(_, d) => setText(d.value)} maxLength={100} />
            </Field>
            <Field label="Other spellings (optional, comma-separated)" hint="For example the Devanagari spelling">
              <Input value={extra} onChange={(_, d) => setExtra(d.value)} />
            </Field>
          </div>
          <div className={styles.kind}>
            <RadioGroup layout="horizontal" value={kind} onChange={(_, d) => setKind(d.value as TermKind)} aria-label="Type">
              <Radio value="word" label="Word" />
              <Radio value="name" label="Name" />
              <Radio value="codename" label="Codename" />
            </RadioGroup>
            <p className={styles.kindHelp}>{KIND_HELP[kind]}</p>
          </div>
          {preview && (
            <Rise visible appear>
              <div className={styles.preview} role="status">
                <p className={styles.previewText}>Appears in {preview.appearsIn} of your stored sources. Also matched as:</p>
                <div className={styles.variants}>
                  {preview.variants.map((v) => (
                    <Pill key={v} className={styles.variant}>
                      {v}
                    </Pill>
                  ))}
                </div>
                {preview.foldedForm && (
                  <Checkbox
                    checked={folds}
                    onChange={(_, d) => setFolds(!!d.checked)}
                    label={`Also catch Hinglish spellings (anything that simplifies to "${preview.foldedForm}"): ${preview.appearsInWithFolds} sources instead of ${preview.appearsIn}`}
                  />
                )}
              </div>
            </Rise>
          )}
          {preview?.commonWord && (
            <MessageBar intent="warning">
              <MessageBarBody>This is a common word. Removing it everywhere can make drafts sound less like you.</MessageBarBody>
            </MessageBar>
          )}
          <div className={styles.actions}>
            <Switch checked={allow} onChange={(_, d) => setAllow(d.checked)} label="Allow in my own drafts" />
            <span className={styles.spacer} />
            <Button icon={<Eye16Regular />} disabled={!text.trim()} onClick={() => void check()}>
              Preview
            </Button>
            <Button icon={<Add16Regular />} disabled={!preview || busy} onClick={() => void save()}>
              Add word
            </Button>
          </div>
        </div>
      </Card>

      <Card
        flush
        icon={<TextBulletListSquare20Regular />}
        title="Your never-send words"
        count={words.length > 0 ? words.length : undefined}
      >
        {words.length === 0 ? (
          <EmptyState headingLevel={4} icon={<Prohibited20Regular />} title="No never-send words yet" center>
            Add a codename or a name above. It's masked in everything Vanimo reads from then on, and in what it has
            already stored.
          </EmptyState>
        ) : (
          <ul className={styles.list} aria-label="Never-send words">
            {words.map((w, i) => (
              <li key={w.id} className={mergeClasses(styles.wordRow, i === 0 && styles.wordFirst)}>
                <span className={styles.wordMain}>
                  <span className={styles.chip}>
                    {KIND_ICON[w.kind]}
                    {w.text}
                  </span>
                  <span className={styles.wordMeta}>
                    <span>{KIND_LABEL[w.kind] ?? w.kind}</span>
                    {w.variants.length > 0 && <span>also {w.variants.join(", ")}</span>}
                    {w.folds && (
                      <span className={styles.metaItem}>
                        <Translate16Regular aria-hidden />
                        Hinglish spellings
                      </span>
                    )}
                  </span>
                </span>
                <span className={styles.wordActions}>
                  <Switch
                    checked={w.allowInDrafts}
                    label={<span className={styles.switchLabel}>In my drafts</span>}
                    aria-label={`Allow ${w.text} in my drafts`}
                    onChange={(_, d) => void api.updateWord(w.id, d.checked).then(load, (e) => setError(errorText(e)))}
                  />
                  <IconAction
                    icon={<Dismiss16Regular />}
                    label={`Remove ${w.text}`}
                    danger
                    onClick={() =>
                      void api
                        .deleteWord(w.id)
                        .then(load)
                        .then(() => onChange?.(), (e) => setError(errorText(e)))
                    }
                  />
                </span>
              </li>
            ))}
          </ul>
        )}
      </Card>
    </div>
  );
}
