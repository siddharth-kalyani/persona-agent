/** A hairline data table with quiet headers that becomes labelled, stacked rows below 640px (each
 * cell names itself, since the header row is hidden there). For dense admin and settings data;
 * use List/ListRow for things people scan and open. */
import { makeStyles, mergeClasses, tokens } from "@fluentui/react-components";
import type { ReactNode } from "react";
import { vt } from "../theme/theme";
import { typo } from "../theme/typography";

const PHONE = "@media (max-width: 639px)";

const srOnly = {
  position: "absolute",
  width: "1px",
  height: "1px",
  padding: 0,
  margin: "-1px",
  overflow: "hidden",
  clip: "rect(0 0 0 0)",
  whiteSpace: "nowrap",
  border: 0,
} as const;

const useTableStyles = makeStyles({
  wrap: {
    border: `1px solid ${vt.border}`,
    borderRadius: tokens.borderRadiusXLarge,
    backgroundColor: tokens.colorNeutralBackground1,
    boxShadow: vt.shadowCard,
    // Clips to the radius; a table that still can't fit scrolls inside itself, never the page.
    overflowX: "auto",
    minWidth: 0,
  },
  embedded: { border: "none", borderRadius: 0, boxShadow: "none" },
  table: {
    width: "100%",
    borderCollapse: "collapse",
    tableLayout: "auto",
    [PHONE]: { display: "block" },
  },
  head: { [PHONE]: srOnly },
  th: {
    ...typo.label,
    color: vt.text3,
    textAlign: "left",
    whiteSpace: "nowrap",
    padding: "10px 16px",
    backgroundColor: vt.inset,
    borderBottom: `1px solid ${vt.borderSubtle}`,
  },
  thEnd: { textAlign: "right" },
  body: { [PHONE]: { display: "block" } },
  tr: {
    borderTop: `1px solid ${vt.borderSubtle}`,
    [PHONE]: {
      display: "grid",
      gap: "6px",
      padding: "12px 16px",
      ":first-child": { borderTopColor: "transparent" },
    },
  },
  td: {
    ...typo.meta,
    color: vt.text2,
    padding: "12px 16px",
    verticalAlign: "middle",
    overflowWrap: "anywhere",
    [PHONE]: { display: "block", padding: 0 },
  },
  dense: { padding: "8px 16px", [PHONE]: { padding: 0 } },
  primary: { ...typo.body, color: vt.text1, minWidth: "140px", [PHONE]: { minWidth: 0 } },
  end: { textAlign: "right", [PHONE]: { textAlign: "left" } },
  numeric: { ...typo.tabular, whiteSpace: "nowrap" },
  mono: { ...typo.mono, color: vt.text2 },
  actions: {
    textAlign: "right",
    whiteSpace: "nowrap",
    width: "1%",
    [PHONE]: { textAlign: "left", width: "auto", paddingTop: "4px" },
  },
  // On phones each labelled cell says what it is ("Activity 6 emails"), since the header is hidden.
  labelled: {
    [PHONE]: {
      "::before": {
        content: "attr(data-label)",
        ...typo.label,
        color: vt.text3,
        marginRight: "8px",
      },
    },
  },
  empty: { ...typo.meta, color: vt.text2, padding: "16px", [PHONE]: { padding: 0 } },
});

export interface Column {
  label?: ReactNode;
  /** Visually hidden header text (for action columns). */
  hiddenLabel?: string;
  align?: "start" | "end";
}

/** A data table with hairline rows and quiet headers; below 640px each row stacks into a block. */
export function DataTable({
  label,
  columns,
  children,
  embedded,
  className,
}: {
  label: string;
  columns: Column[];
  children: ReactNode;
  /** Inside a card (`Section variant="card" flush`): no frame of its own. */
  embedded?: boolean;
  className?: string;
}) {
  const s = useTableStyles();
  return (
    <div className={mergeClasses(s.wrap, embedded && s.embedded, className)}>
      <table className={s.table} aria-label={label}>
        <thead className={s.head}>
          <tr>
            {columns.map((c, i) => (
              <th key={i} scope="col" className={mergeClasses(s.th, c.align === "end" && s.thEnd)}>
                {c.label ?? (c.hiddenLabel ? <span style={srOnly}>{c.hiddenLabel}</span> : null)}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className={s.body}>{children}</tbody>
      </table>
    </div>
  );
}

export function Tr({ children, className }: { children: ReactNode; className?: string }) {
  const s = useTableStyles();
  return <tr className={mergeClasses(s.tr, className)}>{children}</tr>;
}

/** A cell. `label` names the value on phones, where the header row is hidden. */
export function Td({
  children,
  label,
  primary,
  align,
  numeric,
  mono,
  actions,
  dense,
  colSpan,
  className,
}: {
  children?: ReactNode;
  label?: string;
  primary?: boolean;
  align?: "start" | "end";
  numeric?: boolean;
  mono?: boolean;
  actions?: boolean;
  dense?: boolean;
  colSpan?: number;
  className?: string;
}) {
  const s = useTableStyles();
  return (
    <td
      colSpan={colSpan}
      data-label={label}
      className={mergeClasses(
        s.td,
        dense && s.dense,
        primary && s.primary,
        align === "end" && s.end,
        numeric && s.numeric,
        mono && s.mono,
        actions && s.actions,
        label && s.labelled,
        className,
      )}
    >
      {children}
    </td>
  );
}

export function EmptyRow({ colSpan, children }: { colSpan: number; children: ReactNode }) {
  const s = useTableStyles();
  return (
    <tr className={s.tr}>
      <td colSpan={colSpan} className={s.empty}>
        {children}
      </td>
    </tr>
  );
}

