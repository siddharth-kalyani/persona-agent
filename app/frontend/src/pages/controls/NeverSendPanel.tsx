import {
  Badge,
  Button,
  Caption1,
  Field,
  Input,
  makeStyles,
  MessageBar,
  MessageBarBody,
  Radio,
  RadioGroup,
  Switch,
  Table,
  TableBody,
  TableCell,
  TableHeader,
  TableHeaderCell,
  TableRow,
  Text,
  tokens,
} from "@fluentui/react-components";
import { useCallback, useEffect, useState } from "react";
import type { NeverSendWord, TermKind, WordPreview } from "../../api/client";
import { useApi } from "../../api/context";
import { errorText } from "../Home";

const useStyles = makeStyles({
  stack: { display: "grid", gap: tokens.spacingVerticalM },
  row: { display: "flex", gap: tokens.spacingHorizontalS, alignItems: "end", flexWrap: "wrap" },
  chips: { display: "flex", gap: tokens.spacingHorizontalXS, flexWrap: "wrap" },
  muted: { color: tokens.colorNeutralForeground3 },
});

const KIND_HELP: Record<TermKind, string> = {
  word: "A word or phrase, matched as a whole word (plus plurals).",
  name: "A person's name, also with -ji, bhai, 's and similar endings.",
  codename: "A codename: matched inside other words and without spaces (project-falcon, projectfalcon).",
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

  useEffect(() => setPreview(null), [text, kind]);

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
      await api.addWord(text, kind, spellings, allow);
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
      <Caption1 className={styles.muted}>
        Codenames, client nicknames, family names, internal figures. They're replaced before any AI model sees your text,
        and drafts show [removed] where they would appear, unless you allow a word in your own drafts.
      </Caption1>
      {error && (
        <MessageBar intent="error">
          <MessageBarBody>{error}</MessageBarBody>
        </MessageBar>
      )}
      <div className={styles.row}>
        <Field label="Word or phrase">
          <Input value={text} onChange={(_, d) => setText(d.value)} maxLength={100} />
        </Field>
        <Field label="Other spellings (optional, comma-separated)" hint="For example the Devanagari spelling">
          <Input value={extra} onChange={(_, d) => setExtra(d.value)} />
        </Field>
      </div>
      <RadioGroup layout="horizontal" value={kind} onChange={(_, d) => setKind(d.value as TermKind)}>
        <Radio value="word" label="Word" />
        <Radio value="name" label="Name" />
        <Radio value="codename" label="Codename" />
      </RadioGroup>
      <Caption1 className={styles.muted}>{KIND_HELP[kind]}</Caption1>
      <div className={styles.row}>
        <Button disabled={!text.trim()} onClick={() => void check()}>
          Preview
        </Button>
        <Switch checked={allow} onChange={(_, d) => setAllow(d.checked)} label="Allow in my own drafts" />
        <Button appearance="primary" disabled={!preview || busy} onClick={() => void save()}>
          Add word
        </Button>
      </div>
      {preview && (
        <div className={styles.stack}>
          <Text>
            Appears in {preview.appearsIn} of your stored sources. Also matched as:
          </Text>
          <div className={styles.chips}>
            {preview.variants.map((v) => (
              <Badge key={v} appearance="outline">
                {v}
              </Badge>
            ))}
          </div>
          {preview.commonWord && (
            <MessageBar intent="warning">
              <MessageBarBody>
                This is a common word. Removing it everywhere can make drafts sound less like you.
              </MessageBarBody>
            </MessageBar>
          )}
        </div>
      )}
      <Table size="small" aria-label="Never-send words">
        <TableHeader>
          <TableRow>
            <TableHeaderCell>Word</TableHeaderCell>
            <TableHeaderCell>Type</TableHeaderCell>
            <TableHeaderCell>In my drafts</TableHeaderCell>
            <TableHeaderCell />
          </TableRow>
        </TableHeader>
        <TableBody>
          {words.map((w) => (
            <TableRow key={w.id}>
              <TableCell>
                {w.text}
                {w.variants.length > 0 && <Caption1 className={styles.muted}> · also {w.variants.join(", ")}</Caption1>}
              </TableCell>
              <TableCell>{w.kind}</TableCell>
              <TableCell>
                <Switch
                  checked={w.allowInDrafts}
                  aria-label={`Allow ${w.text} in my drafts`}
                  onChange={(_, d) => void api.updateWord(w.id, d.checked).then(load)}
                />
              </TableCell>
              <TableCell>
                <Button size="small" onClick={() => void api.deleteWord(w.id).then(load).then(() => onChange?.())}>
                  Remove
                </Button>
              </TableCell>
            </TableRow>
          ))}
          {words.length === 0 && (
            <TableRow>
              <TableCell colSpan={4}>No never-send words yet.</TableCell>
            </TableRow>
          )}
        </TableBody>
      </Table>
    </div>
  );
}
