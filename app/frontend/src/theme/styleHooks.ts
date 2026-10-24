/** App-wide restyling of Fluent's own components (FluentProvider `customStyleHooks_unstable`), so
 * buttons, fields, menus, tooltips and message bars match the rest of the system without per-page
 * overrides. Each hook runs after Fluent's own styles.
 *
 * Two techniques, chosen to never fight a page's own className:
 * - Fluent's colour variables are remapped on the component's root (inline custom properties), e.g.
 *   a field's "accessible" bottom border becomes the same hairline as its other sides. Fluent's
 *   selectors stay as they are; only the values they read change.
 * - Properties Fluent doesn't set (box-shadow, the focus halo) or that pages never override (font
 *   weight, radius) are merged as classes. */
import {
  makeStyles,
  mergeClasses,
  shorthands,
  type ButtonState,
  type DialogSurfaceState,
  type FluentProviderCustomStyleHooks,
  type ListboxState,
  type MenuItemState,
  type MenuPopoverState,
  type MessageBarState,
  type OptionState,
  type PopoverSurfaceState,
  type SelectState,
  type TooltipState,
} from "@fluentui/react-components";
import type { CSSProperties } from "react";
import { vt } from "./theme";

type Slot = { className?: string; style?: CSSProperties } | undefined | null;

/** Custom properties first, so a page's own inline style still wins. */
function withVars(slot: Slot, vars: Record<string, string>) {
  if (slot) slot.style = { ...(vars as CSSProperties), ...slot.style };
}

function withClass(slot: Slot, ...classes: Array<string | false | undefined>) {
  if (slot) slot.className = mergeClasses(slot.className, ...classes);
}

/** Text fields, selects and dropdowns: one even hairline, the field colour, an accent edge and a soft
 * halo on focus (instead of Fluent's darker bottom edge and animated underline). */
const FIELD_VARS = {
  "--colorNeutralBackground1": vt.field,
  "--colorNeutralStrokeAccessible": vt.borderStrong,
  "--colorNeutralStrokeAccessibleHover": "var(--colorNeutralStroke1Hover)",
  "--colorNeutralStrokeAccessiblePressed": vt.accent,
  "--colorNeutralStroke1Pressed": vt.accent,
  "--colorCompoundBrandStroke": vt.accent,
  "--colorCompoundBrandStrokePressed": vt.accent,
};

const useFieldStyles = makeStyles({
  root: {
    transitionProperty: "border-color, box-shadow",
    transitionDuration: "100ms",
    "::after": { display: "none" },
    ":focus-within": { boxShadow: `0 0 0 3px ${vt.accentRing}` },
  },
  select: { borderRadius: "8px" },
  selectFocus: { ":focus": { ...shorthands.borderColor(vt.accent) } },
});

const useButtonStyles = makeStyles({
  root: { fontWeight: 500 },
  auto: { minWidth: "auto" },
  medium: { paddingLeft: "14px", paddingRight: "14px" },
  primary: {
    boxShadow: "inset 0 1px 0 rgba(255,255,255,0.14), 0 1px 2px rgba(0,0,0,0.16)",
  },
  secondary: { boxShadow: vt.shadowButton },
});

const SECONDARY_VARS = {
  "--colorNeutralBackground1": vt.button,
  "--colorNeutralBackground1Hover": vt.buttonHover,
  "--colorNeutralBackground1Pressed": vt.buttonPressed,
};

function styleButton(state: ButtonState, s: ReturnType<typeof useButtonStyles>) {
  withClass(
    state.root,
    s.root,
    !state.iconOnly && s.auto,
    !state.iconOnly && state.size === "medium" && s.medium,
    state.appearance === "primary" && s.primary,
    state.appearance === "secondary" && s.secondary,
  );
  if (state.appearance === "secondary") withVars(state.root, SECONDARY_VARS);
}

const useLayerStyles = makeStyles({
  tooltip: {
    backgroundColor: vt.tooltip,
    color: vt.tooltipText,
    border: "none",
    borderRadius: "6px",
    padding: "5px 8px",
    fontSize: "12px",
    lineHeight: "16px",
    fontWeight: 500,
    boxShadow: vt.shadowRaised,
  },
  menu: { borderRadius: "10px", padding: "4px" },
  menuItem: { borderRadius: "6px" },
  popover: { borderRadius: "12px" },
  dialog: { borderRadius: "14px" },
  listbox: {
    borderRadius: "10px",
    padding: "4px",
    backgroundColor: vt.raised,
    border: `1px solid ${vt.border}`,
    boxShadow: vt.shadowRaised,
  },
  option: { borderRadius: "6px" },
});

const useMessageBarStyles = makeStyles({
  root: { borderRadius: "10px", minHeight: "40px" },
  info: { backgroundColor: vt.card, border: `1px solid ${vt.border}`, boxShadow: vt.shadowCard },
  infoIcon: { color: vt.info },
});

/** Every field component has a `root` that carries the border (Select's variables reach its inner
 * <select> by inheritance). */
const field = (extra?: (s: ReturnType<typeof useFieldStyles>) => string) => (state: unknown) => {
  const s = useFieldStyles();
  const root = (state as { root: Slot }).root;
  withVars(root, FIELD_VARS);
  withClass(root, s.root, extra?.(s));
};

export const styleHooks: FluentProviderCustomStyleHooks = {
  useButtonStyles_unstable: (state) => styleButton(state as ButtonState, useButtonStyles()),
  useMenuButtonStyles_unstable: (state) => styleButton(state as ButtonState, useButtonStyles()),
  useToggleButtonStyles_unstable: (state) => styleButton(state as ButtonState, useButtonStyles()),

  useInputStyles_unstable: field(),
  useTextareaStyles_unstable: field(),
  useSelectStyles_unstable: (state) => {
    field((s) => s.select)(state);
    const s = useFieldStyles();
    withClass((state as SelectState).select, s.selectFocus);
  },
  useDropdownStyles_unstable: field(),
  useComboboxStyles_unstable: field(),
  useSearchBoxStyles_unstable: field(),

  useTooltipStyles_unstable: (state) => {
    const s = useLayerStyles();
    const t = state as TooltipState;
    t.content.className = mergeClasses(t.content.className, s.tooltip);
  },
  useMenuPopoverStyles_unstable: (state) => {
    const s = useLayerStyles();
    withClass((state as MenuPopoverState).root, s.menu);
  },
  useMenuItemStyles_unstable: (state) => {
    const s = useLayerStyles();
    withClass((state as MenuItemState).root, s.menuItem);
  },
  useMenuItemRadioStyles_unstable: (state) => {
    const s = useLayerStyles();
    withClass((state as MenuItemState).root, s.menuItem);
  },
  usePopoverSurfaceStyles_unstable: (state) => {
    const s = useLayerStyles();
    withClass((state as PopoverSurfaceState).root, s.popover);
  },
  useDialogSurfaceStyles_unstable: (state) => {
    const s = useLayerStyles();
    withClass((state as DialogSurfaceState).root, s.dialog);
  },
  useListboxStyles_unstable: (state) => {
    const s = useLayerStyles();
    withClass((state as ListboxState).root, s.listbox);
  },
  useOptionStyles_unstable: (state) => {
    const s = useLayerStyles();
    withClass((state as OptionState).root, s.option);
  },
  useMessageBarStyles_unstable: (state) => {
    const s = useMessageBarStyles();
    const m = state as MessageBarState;
    withClass(m.root, s.root, m.intent === "info" && s.info);
    if (m.intent === "info") withClass(m.icon, s.infoIcon);
  },
};
