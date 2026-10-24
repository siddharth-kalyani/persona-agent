/** A segmented control (Fluent TabList underneath, so arrow keys and roles come for free): an inset
 * track with the selected segment raised, counts inside the segments. It scrolls sideways inside
 * itself on narrow screens, so the page never does. */
import { makeStyles, Tab, TabList } from "@fluentui/react-components";
import { useEffect, useRef, useState, type ReactNode } from "react";
import { vt } from "../theme/theme";
import { typo } from "../theme/typography";

const useSegmentStyles = makeStyles({
  // The control scrolls sideways inside itself on narrow screens; the page never does.
  scroller: { overflowX: "auto", minWidth: 0, maxWidth: "100%", scrollbarWidth: "none", "::-webkit-scrollbar": { display: "none" } },
  list: {
    flexWrap: "nowrap",
    width: "max-content",
    gap: "2px",
    padding: "3px",
    borderRadius: "10px",
    backgroundColor: vt.neutralTint,
    border: `1px solid ${vt.borderSubtle}`,
  },
  tab: {
    minHeight: "28px",
    padding: "4px 10px",
    borderRadius: "7px",
    color: vt.text2,
    // Fluent's selection underline and hover bar: the raised segment says it instead.
    "::before": { display: "none" },
    "::after": { display: "none" },
    ":hover": { backgroundColor: vt.hover, color: vt.text1 },
    '&[aria-selected="true"]': {
      backgroundColor: vt.button,
      color: vt.text1,
      boxShadow: `${vt.shadowButton}, 0 0 0 1px ${vt.border}`,
    },
    '&[aria-selected="true"]:hover': { backgroundColor: vt.button },
  },
  label: { ...typo.meta, fontWeight: 500, display: "inline-flex", alignItems: "center", gap: "6px" },
  count: { ...typo.label, ...typo.tabular, fontWeight: 500, color: vt.text3 },
  divider: {
    width: "1px",
    alignSelf: "stretch",
    margin: "6px 4px",
    backgroundColor: vt.borderStrong,
  },
});

export interface Segment<V extends string> {
  value: V;
  label: ReactNode;
  count?: number;
  /** A 16px icon before the label. */
  icon?: ReactNode;
  /** Draws a thin divider before this segment (a different kind of thing follows). */
  dividerBefore?: boolean;
}

/** When the control is wider than its space (phones), fade the edge that hides more segments, so it
 * reads as scrollable rather than cut off. */
function useOverflowEdges(deps: unknown) {
  const ref = useRef<HTMLDivElement>(null);
  const [edge, setEdge] = useState({ start: false, end: false });
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const update = () =>
      setEdge((prev) => {
        const next = { start: el.scrollLeft > 2, end: el.scrollLeft + el.clientWidth < el.scrollWidth - 2 };
        return next.start === prev.start && next.end === prev.end ? prev : next;
      });
    update();
    el.addEventListener("scroll", update, { passive: true });
    const ro = typeof ResizeObserver === "undefined" ? null : new ResizeObserver(update);
    ro?.observe(el);
    return () => {
      el.removeEventListener("scroll", update);
      ro?.disconnect();
    };
  }, [deps]);
  const fade = (on: boolean) => (on ? "28px" : "0px");
  const mask =
    edge.start || edge.end
      ? `linear-gradient(to right, transparent 0, #000 ${fade(edge.start)}, #000 calc(100% - ${fade(edge.end)}), transparent 100%)`
      : undefined;
  return { ref, style: mask ? { maskImage: mask, WebkitMaskImage: mask } : undefined };
}

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
  const edges = useOverflowEdges(segments.length);
  return (
    <div className={s.scroller} ref={edges.ref} style={edges.style}>
      <TabList
        className={s.list}
        appearance="subtle"
        size="small"
        selectedValue={value}
        onTabSelect={(_, d) => onChange(d.value as V)}
        aria-label={label}
      >
        {segments.flatMap((seg) => {
          const tab = (
            <Tab key={seg.value} value={seg.value} className={s.tab} icon={seg.icon ? <>{seg.icon}</> : undefined}>
              <span className={s.label}>
                {seg.label}
                {seg.count !== undefined && (
                  <>
                    {" "}
                    <span className={s.count}>{seg.count}</span>
                  </>
                )}
              </span>
            </Tab>
          );
          return seg.dividerBefore ? [<span key={`${seg.value}-divider`} className={s.divider} aria-hidden />, tab] : [tab];
        })}
      </TabList>
    </div>
  );
}
