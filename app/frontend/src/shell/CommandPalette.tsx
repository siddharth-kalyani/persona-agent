/** Ctrl/⌘ K: jump anywhere or run an action by typing. Opens and closes instantly (keyboard actions
 * never animate); arrow keys move, Enter runs, Esc closes and gives focus back. */
import { Dialog, DialogSurface, makeStyles, mergeClasses, tokens } from "@fluentui/react-components";
import { Search20Regular } from "@fluentui/react-icons";
import { useEffect, useId, useMemo, useRef, useState, type ReactNode } from "react";
import { Kbd, typo, vt } from "../ui";

export interface Command {
  id: string;
  label: string;
  group: string;
  icon?: ReactNode;
  aliases?: string[];
  hint?: string;
  run: () => void;
}

const useStyles = makeStyles({
  surface: {
    width: "min(640px, calc(100vw - 32px))",
    maxWidth: "640px",
    padding: 0,
    alignSelf: "start",
    marginTop: "12vh",
    overflow: "hidden",
    "@media (max-width: 639px)": { marginTop: 0, width: "100vw", maxWidth: "100vw", height: "100dvh", borderRadius: 0 },
  },
  inputRow: {
    display: "flex",
    alignItems: "center",
    gap: "10px",
    padding: "0 16px",
    height: "52px",
    borderBottom: `1px solid ${tokens.colorNeutralStroke3}`,
    color: vt.text3,
  },
  input: {
    flexGrow: 1,
    border: "none",
    outline: "none",
    backgroundColor: "transparent",
    color: vt.text1,
    fontFamily: tokens.fontFamilyBase,
    fontSize: "15px",
    lineHeight: "24px",
    "::placeholder": { color: vt.text3 },
  },
  list: { maxHeight: "min(400px, 60vh)", overflowY: "auto", padding: "6px", margin: 0, listStyle: "none" },
  group: { ...typo.label, color: vt.text3, padding: "10px 10px 4px" },
  item: {
    display: "flex",
    alignItems: "center",
    gap: "10px",
    height: "36px",
    padding: "0 10px",
    borderRadius: tokens.borderRadiusMedium,
    color: vt.text1,
    cursor: "pointer",
    ...typo.body,
  },
  active: { backgroundColor: vt.selected },
  icon: { display: "grid", placeItems: "center", color: vt.text2, fontSize: "16px", width: "16px" },
  hint: { marginLeft: "auto", ...typo.meta, color: vt.text3 },
  empty: { padding: "24px 16px", ...typo.body, color: vt.text2 },
  footer: {
    display: "flex",
    gap: "16px",
    alignItems: "center",
    height: "36px",
    padding: "0 16px",
    borderTop: `1px solid ${tokens.colorNeutralStroke3}`,
    ...typo.label,
    fontWeight: 400,
    color: vt.text3,
    "@media (max-width: 639px)": { display: "none" },
  },
});

/** Score a command for a query: prefix > word prefix > substring > alias > in-order letters. */
export function score(c: Command, query: string): number {
  const q = query.trim().toLowerCase();
  if (!q) return 1;
  const label = c.label.toLowerCase();
  if (label.startsWith(q)) return 5;
  if (label.split(/\s+/).some((w) => w.startsWith(q))) return 4;
  if (label.includes(q)) return 3;
  if (c.aliases?.some((a) => a.toLowerCase().includes(q))) return 2;
  let i = 0;
  for (const ch of label) if (ch === q[i]) i++;
  return i === q.length ? 1 : 0;
}

export function CommandPalette({ open, onOpenChange, commands }: { open: boolean; onOpenChange: (open: boolean) => void; commands: Command[] }) {
  const s = useStyles();
  const [query, setQuery] = useState("");
  const [active, setActive] = useState(0);
  const listId = useId();
  const listRef = useRef<HTMLUListElement>(null);

  const results = useMemo(() => {
    const scored = commands.map((c, i) => ({ c, i, score: score(c, query) })).filter((x) => x.score > 0);
    if (query.trim()) scored.sort((a, b) => b.score - a.score || a.i - b.i);
    return scored.map((x) => x.c);
  }, [commands, query]);

  useEffect(() => {
    if (open) {
      setQuery("");
      setActive(0);
    }
  }, [open]);

  useEffect(() => setActive(0), [query]);

  useEffect(() => {
    listRef.current?.querySelector(`[data-index="${active}"]`)?.scrollIntoView({ block: "nearest" });
  }, [active]);

  function run(c: Command | undefined) {
    if (!c) return;
    onOpenChange(false);
    c.run();
  }

  function onKeyDown(e: React.KeyboardEvent) {
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setActive((a) => (results.length ? (a + 1) % results.length : 0));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setActive((a) => (results.length ? (a - 1 + results.length) % results.length : 0));
    } else if (e.key === "Enter") {
      e.preventDefault();
      run(results[active]);
    }
  }

  let lastGroup = "";
  return (
    <Dialog open={open} onOpenChange={(_, d) => onOpenChange(d.open)} surfaceMotion={null}>
      <DialogSurface className={s.surface} aria-label="Command palette" backdropMotion={null}>
        <div className={s.inputRow}>
          <Search20Regular aria-hidden />
          <input
            className={s.input}
            autoFocus
            placeholder="Search pages and actions…"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={onKeyDown}
            role="combobox"
            aria-expanded="true"
            aria-controls={listId}
            aria-activedescendant={results[active] ? `${listId}-${results[active].id}` : undefined}
            aria-label="Search pages and actions"
          />
        </div>
        {results.length === 0 ? (
          <div className={s.empty}>Nothing matches “{query}”.</div>
        ) : (
          <ul className={s.list} id={listId} role="listbox" ref={listRef} aria-label="Results">
            {results.map((c, i) => {
              const header = !query.trim() && c.group !== lastGroup ? c.group : null;
              lastGroup = c.group;
              return (
                <li key={c.id} role="presentation">
                  {header && <div className={s.group} role="presentation">{header}</div>}
                  <div
                    id={`${listId}-${c.id}`}
                    role="option"
                    aria-selected={i === active}
                    data-index={i}
                    className={mergeClasses(s.item, i === active && s.active)}
                    onMouseMove={() => i !== active && setActive(i)}
                    onClick={() => run(c)}
                  >
                    <span className={s.icon} aria-hidden>{c.icon}</span>
                    {c.label}
                    {c.hint && <span className={s.hint}>{c.hint}</span>}
                  </div>
                </li>
              );
            })}
          </ul>
        )}
        <div className={s.footer} aria-hidden>
          <span><Kbd>↑</Kbd> <Kbd>↓</Kbd> to move</span>
          <span><Kbd>↵</Kbd> to open</span>
          <span><Kbd>Esc</Kbd> to close</span>
        </div>
      </DialogSurface>
    </Dialog>
  );
}
