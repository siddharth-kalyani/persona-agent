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
  Tooltip,
} from "@fluentui/react-components";
import { Delete16Regular, TextBulletListSquare20Regular } from "@fluentui/react-icons";
import { useCallback, useEffect, useState } from "react";
import type { NeverSendWord, TermKind, WordPreview } from "../../api/client";
import { useApi } from "../../api/context";
import { EmptyState, List, Pill, Rise, typo, vt } from "../../ui";
import { errorText } from "../Home";

const useStyles = makeStyles({
  stack: { display: "grid", gap: "28px", minWidth: 0 },
  intro: { ...typo.meta, color: vt.text2, margin: 0, maxWidth: "72ch" },
  block: { display: "grid", gap: "12px", minWidth: 0 },
  heading: { ...typo.itemTitle, color: vt.text1, margin: 0, display: "flex", alignItems: "baseline", gap: "8px" },
  headingCount: { ...typo.meta, ...typo.tabular, color: vt.text3, fontWeight: 400 },
  fields: {
    display: "grid",
    gridTemplateColumns: "minmax(0, 1fr) minmax(0, 1fr)",
    gap: "12px 16px",
    alignItems: "start",
    maxWidth: "720px",
    "@media (max-width: 639px)": { gridTemplateColumns: "minmax(0, 1fr)" },
  },
  kind: { display: "grid", gap: "2px" },
  kindHelp: { ...typo.meta, color: vt.text2, margin: 0, paddingLeft: "4px" },
  actions: { display: "flex", gap: "8px 12px", alignItems: "center", flexWrap: "wrap" },
  spacer: { flexGrow: 1, "@media (max-width: 479px)": { display: "none" } },
  preview: {
    display: "grid",
    gap: "10px",
    padding: "12px 16px",
    borderRadius: tokens.borderRadiusLarge,
    backgroundColor: vt.inset,
    border: `1px solid ${tokens.colorNeutralStroke3}`,
    maxWidth: "720px",
  },
  previewText: { ...typo.body, color: vt.text1, margin: 0 },
  variants: { display: "flex", gap: "4px", flexWrap: "wrap" },
  variant: { ...typo.address, fontWeight: 400, fontSize: "12.5px" },
  wordRow: {
    display: "grid",
    gridTemplateColumns: "minmax(0, 1fr) auto",
    alignItems: "center",
    gap: "8px 16px",
    padding: "10px 16px",
    borderTop: `1px solid ${tokens.colorNeutralStroke3}`,
    "@media (max-width: 479px)": { gridTemplateColumns: "minmax(0, 1fr)" },
  },
  wordFirst: { borderTopColor: "transparent" },
  wordText: { display: "grid", gap: "2px", minWidth: 0 },
  word: { ...typo.itemTitle, ...typo.address, color: vt.text1 },
  wordMeta: { ...typo.meta, color: vt.text2, overflowWrap: "anywhere" },
  wordActions: { display: "flex", alignItems: "center", gap: "8px", justifyContent: "flex-end" },
  switchLabel: { ...typo.meta, color: vt.text2 },
});

const KIND_HELP: Record<TermKind, string> = {
  word: "A word or phrase, matched as a whole word (plus plurals).",
  name: "A person's name, also with -ji, bhai, 's and similar endings.",
  codename: "A codename: matched inside other words and without spaces (project-falcon, projectfalcon).",
};

const KIND_LABEL: Record<TermKind, string> = { word: "Word", name: "Name", codename: "Codename" };

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
      <p className={styles.intro}>
        Codenames, client nicknames, family names, internal figures. They're replaced before any AI model sees your text,
        and drafts show [removed] where they would appear, unless you allow a word in your own drafts.
      </p>
      {error && (
        <MessageBar intent="error">
          <MessageBarBody>{error}</MessageBarBody>
        </MessageBar>
      )}

      <div className={styles.block}>
        <h3 className={styles.heading}>Add a word</h3>
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
        <div className={styles.actions}>
          <Switch checked={allow} onChange={(_, d) => setAllow(d.checked)} label="Allow in my own drafts" />
          <span className={styles.spacer} />
          <Button disabled={!text.trim()} onClick={() => void check()}>
            Preview
          </Button>
          <Button disabled={!preview || busy} onClick={() => void save()}>
            Add word
          </Button>
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
      </div>

      <div className={styles.block}>
        <h3 className={styles.heading}>
          Your never-send words
          {words.length > 0 && <span className={styles.headingCount}>{words.length}</span>}
        </h3>
        {words.length === 0 ? (
          <EmptyState icon={<TextBulletListSquare20Regular />} title="No never-send words yet">
            Add a codename or a name above. It's masked in everything Vanimo reads from then on, and in what it has
            already stored.
          </EmptyState>
        ) : (
          <List bordered label="Never-send words">
            {words.map((w, i) => (
              <li key={w.id} className={mergeClasses(styles.wordRow, i === 0 && styles.wordFirst)}>
                <span className={styles.wordText}>
                  <span className={styles.word}>{w.text}</span>
                  <span className={styles.wordMeta}>
                    {KIND_LABEL[w.kind] ?? w.kind}
                    {w.variants.length > 0 && ` · also ${w.variants.join(", ")}`}
                    {w.folds && " · Hinglish spellings"}
                  </span>
                </span>
                <span className={styles.wordActions}>
                  <Switch
                    checked={w.allowInDrafts}
                    label={<span className={styles.switchLabel}>In my drafts</span>}
                    aria-label={`Allow ${w.text} in my drafts`}
                    onChange={(_, d) => void api.updateWord(w.id, d.checked).then(load, (e) => setError(errorText(e)))}
                  />
                  <Tooltip content="Remove" relationship="description" withArrow>
                    <Button
                      size="small"
                      appearance="subtle"
                      icon={<Delete16Regular />}
                      aria-label={`Remove ${w.text}`}
                      onClick={() =>
                        void api
                          .deleteWord(w.id)
                          .then(load)
                          .then(() => onChange?.(), (e) => setError(errorText(e)))
                      }
                    />
                  </Tooltip>
                </span>
              </li>
            ))}
          </List>
        )}
      </div>
    </div>
  );
}
