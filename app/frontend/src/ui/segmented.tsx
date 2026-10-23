/** A segmented control (Fluent TabList, subtle-circular) with counts inside the segments. It scrolls
 * sideways inside itself on narrow screens, so the page never does. */
import { makeStyles, Tab, TabList, tokens } from "@fluentui/react-components";
import type { ReactNode } from "react";
import { vt } from "../theme/theme";
import { typo } from "../theme/typography";

const useSegmentStyles = makeStyles({
  // The control scrolls sideways inside itself on narrow screens; the page never does.
  scroller: { overflowX: "auto", minWidth: 0, marginInline: "-2px", padding: "2px" },
  list: { flexWrap: "nowrap", width: "max-content" },
  count: { ...typo.label, ...typo.tabular, fontWeight: 400, color: vt.text3, marginLeft: "2px" },
  divider: {
    width: "1px",
    alignSelf: "stretch",
    margin: "6px 6px",
    backgroundColor: tokens.colorNeutralStroke2,
  },
});

export interface Segment<V extends string> {
  value: V;
  label: ReactNode;
  count?: number;
  /** Draws a thin divider before this segment (a different kind of thing follows). */
  dividerBefore?: boolean;
}

/** A segmented control (Fluent TabList, subtle-circular). Counts sit inside the segments. */
export function Segmented<V extends string>({
  value,
  onChange,
  segments,
  label,
}: {
  value: V;
  onChange: (v: V) => void;
  segments: Segment<V>[];
  label: string;
}) {
  const s = useSegmentStyles();
  return (
    <div className={s.scroller}>
      <TabList
        className={s.list}
        appearance="subtle-circular"
        size="small"
        selectedValue={value}
        onTabSelect={(_, d) => onChange(d.value as V)}
        aria-label={label}
      >
        {segments.flatMap((seg) => {
          const tab = (
            <Tab key={seg.value} value={seg.value}>
              {seg.label}
              {seg.count !== undefined && (
                <>
                  {" "}
                  <span className={s.count}>{seg.count}</span>
                </>
              )}
            </Tab>
          );
          return seg.dividerBefore ? [<span key={`${seg.value}-divider`} className={s.divider} aria-hidden />, tab] : [tab];
        })}
      </TabList>
    </div>
  );
}
