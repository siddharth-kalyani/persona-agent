/** Vanimo's visual system on Fluent UI v9: cool neutrals, one teal accent, tints for meaning, Inter.
 * Light and dark are tuned separately. Dark is layered, not inverted: surfaces get lighter as they
 * rise, borders are low-alpha white, cards carry a faint top highlight. Contrast ratios were checked
 * for every text token (WCAG 2.2 AA, scratch script); tertiary text is never used on a selected row. */
import { createDarkTheme, createLightTheme, type BrandVariants, type Theme } from "@fluentui/react-components";

/** Deep teal, OKLCH hue 188: not the indigo of AI products, not Outlook blue. */
export const brand: BrandVariants = {
  10: "#001C1A", 20: "#002926", 30: "#003632", 40: "#00433E", 50: "#00504B", 60: "#005E58", 70: "#006A63",
  80: "#00756E", 90: "#008881", 100: "#259790", 110: "#40A69E", 120: "#5AB5AD", 130: "#79C6BF", 140: "#9BD8D2",
  150: "#C0ECE7", 160: "#E5F8F6",
}; // prettier-ignore

/** Tokens Fluent doesn't have. The FluentProvider writes every theme key as a CSS variable, so these
 * swap with light/dark like Fluent's own. Use them through `vt`. */
export interface VanimoTokens {
  vFrame: string; // app background and sidebar
  vSurface: string; // the content panel
  vCard: string; // cards, lists, tables, inputs (= colorNeutralBackground1)
  vRaised: string; // menus, popovers, dialogs
  vInset: string; // wells: quoted text, transcripts, code, kbd
  vField: string; // text fields and selects (recessed in dark)
  vButton: string; // secondary buttons (raised in dark)
  vButtonHover: string;
  vButtonPressed: string;
  vHover: string; // alpha: works on any surface
  vSelected: string;
  vBorderSubtle: string; // hairlines inside cards
  vBorder: string; // card edges
  vBorderStrong: string; // control edges (inputs, secondary buttons)
  vText1: string;
  vText2: string;
  vText3: string;
  vAccent: string; // accent as text/icon on surfaces
  vAccentTint: string; // selected chips, accent icon tiles
  vAccentTintText: string;
  vAccentRing: string; // focus halo around inputs
  vNeutralTint: string;
  vNeutralTintText: string;
  vInfo: string; // blue: email
  vInfoTint: string;
  vPurple: string; // purple: Teams chat
  vPurpleTint: string;
  vSuccess: string;
  vSuccessTint: string;
  vWarning: string;
  vWarningTint: string;
  vDanger: string;
  vDangerTint: string;
  vDiffAddLine: string;
  vDiffAddWord: string;
  vDiffDelLine: string;
  vDiffDelWord: string;
  vDot: string; // idle status dot
  vShadowCard: string;
  vShadowButton: string;
  vShadowRaised: string;
  vShadowOverlay: string;
  vTooltip: string;
  vTooltipText: string;
  vScrim: string;
}

const FONT_BASE = "'Inter Variable', 'Segoe UI Variable Text', 'Segoe UI', system-ui, -apple-system, sans-serif";
const FONT_MONO = "'JetBrains Mono Variable', Consolas, ui-monospace, 'SF Mono', monospace";

const SHARED: Partial<Theme> = {
  fontFamilyBase: FONT_BASE,
  fontFamilyNumeric: FONT_BASE, // Fluent's default (Bahnschrift) would clash
  fontFamilyMonospace: FONT_MONO,
  borderRadiusSmall: "4px",
  borderRadiusMedium: "8px", // buttons, inputs, nav items
  borderRadiusLarge: "10px",
  borderRadiusXLarge: "12px", // cards and the content panel
  // Fluent's decelerate curve and durations stay; motion is used sparingly (see theme/motion.ts).
};

const LIGHT: VanimoTokens = {
  vFrame: "#EEF0F2",
  vSurface: "#F7F8FA",
  vCard: "#FFFFFF",
  vRaised: "#FFFFFF",
  vInset: "#F5F6F8",
  vField: "#FFFFFF",
  vButton: "#FFFFFF",
  vButtonHover: "#F6F7F9",
  vButtonPressed: "#EEF0F2",
  vHover: "rgba(16,18,24,0.04)",
  vSelected: "rgba(16,18,24,0.06)",
  vBorderSubtle: "#EEEFF2",
  vBorder: "#E3E5E9",
  vBorderStrong: "#CDD1D7",
  vText1: "#111318",
  vText2: "#4D525C",
  vText3: "#62686F",
  vAccent: "#00756E",
  vAccentTint: "#E3F5F3",
  vAccentTintText: "#00685F",
  vAccentRing: "rgba(0,117,110,0.20)",
  vNeutralTint: "#F0F1F3",
  vNeutralTintText: "#4D525C",
  vInfo: "#1F5FBF",
  vInfoTint: "#E8F1FD",
  vPurple: "#5B4FC7",
  vPurpleTint: "#EFEDFC",
  vSuccess: "#1E7B44",
  vSuccessTint: "#E7F5EC",
  vWarning: "#9A5B00",
  vWarningTint: "#FDF3DC",
  vDanger: "#C42B2B",
  vDangerTint: "#FDECEC",
  vDiffAddLine: "#E7F5EC",
  vDiffAddWord: "#C6EBD3",
  vDiffDelLine: "#FDECEC",
  vDiffDelWord: "#FBCFCF",
  vDot: "#9CA1A9",
  vShadowCard: "0 1px 2px rgba(16,24,40,0.04), 0 1px 3px rgba(16,24,40,0.03)",
  vShadowButton: "0 1px 2px rgba(16,24,40,0.06)",
  vShadowRaised: "0 1px 3px rgba(16,24,40,0.06), 0 8px 24px rgba(16,24,40,0.10)",
  vShadowOverlay: "0 4px 12px rgba(16,24,40,0.08), 0 24px 56px rgba(16,24,40,0.18)",
  vTooltip: "#1B1D22",
  vTooltipText: "#FFFFFF",
  vScrim: "rgba(10,12,16,0.42)",
};

const DARK: VanimoTokens = {
  vFrame: "#0A0B0D",
  vSurface: "#0F1012",
  vCard: "#151619",
  vRaised: "#1C1D21",
  vInset: "#0C0D0F",
  vField: "#101114",
  vButton: "#1D1E22",
  vButtonHover: "#24262B",
  vButtonPressed: "#2A2C31",
  vHover: "rgba(255,255,255,0.045)",
  vSelected: "rgba(255,255,255,0.07)",
  vBorderSubtle: "rgba(255,255,255,0.055)",
  vBorder: "rgba(255,255,255,0.085)",
  vBorderStrong: "rgba(255,255,255,0.13)",
  vText1: "#EDEEF0",
  vText2: "#A3A8B0",
  vText3: "#878C94",
  vAccent: "#4CC2B6",
  vAccentTint: "rgba(56,189,176,0.13)",
  vAccentTintText: "#5ECFC3",
  vAccentRing: "rgba(76,194,182,0.28)",
  vNeutralTint: "rgba(255,255,255,0.06)",
  vNeutralTintText: "#B4B8BF",
  vInfo: "#7EB0FF",
  vInfoTint: "rgba(77,141,255,0.14)",
  vPurple: "#A99FFF",
  vPurpleTint: "rgba(139,124,246,0.15)",
  vSuccess: "#5DD48A",
  vSuccessTint: "rgba(52,199,107,0.13)",
  vWarning: "#F5B544",
  vWarningTint: "rgba(245,166,35,0.13)",
  vDanger: "#FF8A85",
  vDangerTint: "rgba(240,80,80,0.14)",
  vDiffAddLine: "rgba(52,199,107,0.10)",
  vDiffAddWord: "rgba(52,199,107,0.28)",
  vDiffDelLine: "rgba(240,80,80,0.10)",
  vDiffDelWord: "rgba(240,80,80,0.30)",
  vDot: "#5E636B",
  vShadowCard: "inset 0 1px 0 rgba(255,255,255,0.035), 0 1px 2px rgba(0,0,0,0.4)",
  vShadowButton: "inset 0 1px 0 rgba(255,255,255,0.04), 0 1px 2px rgba(0,0,0,0.4)",
  vShadowRaised: "0 8px 28px rgba(0,0,0,0.55), 0 1px 3px rgba(0,0,0,0.4)",
  vShadowOverlay: "0 24px 64px rgba(0,0,0,0.65), 0 2px 8px rgba(0,0,0,0.4)",
  vTooltip: "#2A2B30",
  vTooltipText: "#EDEEF0",
  vScrim: "rgba(0,0,0,0.6)",
};

/** Fluent's tokens, mapped onto ours, so Fluent's own components sit in the same palette. */
interface Extras {
  hover: string; // opaque hovers for opaque components (menu items, options, card buttons)
  pressed: string;
  fg2: string;
  disabledFg: string;
  disabledBg: string;
  strokeHover: string;
  strokePressed: string;
  accessible: string; // checkbox, radio and switch outlines (3:1)
  accessibleHover: string;
  stencil1: string; // skeletons
  stencil2: string;
}

function fluent(v: VanimoTokens, x: Extras): Partial<Theme> {
  return {
    colorNeutralBackground1: v.vCard,
    colorNeutralBackground1Hover: x.hover,
    colorNeutralBackground1Pressed: x.pressed,
    colorNeutralBackground1Selected: x.pressed,
    colorNeutralBackground2: v.vFrame,
    colorNeutralBackground2Hover: x.hover,
    colorNeutralBackground2Pressed: x.pressed,
    colorNeutralBackground2Selected: x.pressed,
    colorNeutralBackground3: v.vInset,
    colorNeutralBackground3Hover: x.hover,
    colorNeutralBackground3Pressed: x.pressed,
    colorNeutralBackground3Selected: x.pressed,
    colorNeutralBackgroundDisabled: x.disabledBg,
    colorSubtleBackgroundHover: v.vHover,
    colorSubtleBackgroundPressed: v.vSelected,
    colorSubtleBackgroundSelected: v.vSelected,
    colorTransparentBackgroundHover: v.vHover,
    colorTransparentBackgroundPressed: v.vSelected,
    colorTransparentBackgroundSelected: v.vSelected,
    colorNeutralForeground1: v.vText1,
    colorNeutralForeground1Hover: v.vText1,
    colorNeutralForeground1Pressed: v.vText1,
    colorNeutralForeground1Selected: v.vText1,
    colorNeutralForeground2: x.fg2,
    colorNeutralForeground2Hover: v.vText1,
    colorNeutralForeground2Pressed: v.vText1,
    colorNeutralForeground2Selected: v.vText1,
    colorNeutralForeground3: v.vText2,
    colorNeutralForeground3Hover: x.fg2,
    colorNeutralForeground3Pressed: x.fg2,
    colorNeutralForeground3Selected: x.fg2,
    colorNeutralForeground4: v.vText3,
    colorNeutralForegroundDisabled: x.disabledFg,
    colorNeutralStroke1: v.vBorderStrong,
    colorNeutralStroke1Hover: x.strokeHover,
    colorNeutralStroke1Pressed: x.strokePressed,
    colorNeutralStroke1Selected: x.strokeHover,
    colorNeutralStroke2: v.vBorder,
    colorNeutralStroke3: v.vBorderSubtle,
    colorNeutralStrokeSubtle: v.vBorderSubtle,
    colorNeutralStrokeAccessible: x.accessible,
    colorNeutralStrokeAccessibleHover: x.accessibleHover,
    colorNeutralStrokeAccessiblePressed: x.accessibleHover,
    colorNeutralStrokeDisabled: v.vBorder,
    colorNeutralStencil1: x.stencil1,
    colorNeutralStencil2: x.stencil2,
    colorStrokeFocus2: v.vAccent,
    shadow2: v.vShadowButton,
    shadow4: v.vShadowCard,
    shadow8: v.vShadowRaised,
    shadow16: v.vShadowRaised,
    shadow28: v.vShadowOverlay,
    shadow64: v.vShadowOverlay,
    colorStatusSuccessBackground1: v.vSuccessTint,
    colorStatusSuccessForeground1: v.vSuccess,
    colorStatusSuccessForeground3: v.vSuccess,
    colorStatusWarningBackground1: v.vWarningTint,
    colorStatusWarningForeground1: v.vWarning,
    colorStatusWarningForeground3: v.vWarning,
    colorStatusDangerBackground1: v.vDangerTint,
    colorStatusDangerForeground1: v.vDanger,
    colorStatusDangerForeground3: v.vDanger,
  };
}

function lightTheme(): Theme & VanimoTokens {
  const v = LIGHT;
  return {
    ...createLightTheme(brand),
    ...SHARED,
    ...v,
    ...fluent(v, {
      hover: "#F6F7F9",
      pressed: "#EEF0F2",
      fg2: "#2F333A",
      disabledFg: "#959AA2",
      disabledBg: "#F0F1F3",
      strokeHover: "#B9BEC6",
      strokePressed: "#A9AEB6",
      accessible: "#8A9099",
      accessibleHover: "#6F757E",
      stencil1: "#ECEEF1",
      stencil2: "#F6F7F9",
    }),
    colorBrandBackground: brand[80],
    colorBrandBackgroundHover: brand[70],
    colorBrandBackgroundPressed: brand[60],
    colorBrandBackgroundSelected: brand[70],
    colorBrandForeground1: v.vAccent,
    colorBrandForegroundLink: v.vAccent,
    colorBrandForegroundLinkHover: brand[60],
    colorBrandForegroundLinkPressed: brand[50],
    colorBrandBackground2: v.vAccentTint,
    colorStatusSuccessBorder1: "#BFE3CC",
    colorStatusWarningBorder1: "#F3DDA8",
    colorStatusDangerBorder1: "#F6C6C6",
    colorStatusDangerBackground3: "#C42B2B",
    colorStatusDangerBackground3Hover: "#AE2424",
    colorStatusDangerBackground3Pressed: "#971F1F",
  };
}

function darkTheme(): Theme & VanimoTokens {
  const v = DARK;
  return {
    ...createDarkTheme(brand),
    ...SHARED,
    ...v,
    ...fluent(v, {
      hover: "#202227",
      pressed: "#26282D",
      fg2: "#D4D6DA",
      disabledFg: "#6B7078",
      disabledBg: "#1A1B1F",
      strokeHover: "rgba(255,255,255,0.2)",
      strokePressed: "rgba(255,255,255,0.26)",
      accessible: "#6E737B",
      accessibleHover: "#8A8F97",
      stencil1: "#1C1D21",
      stencil2: "#16171A",
    }),
    colorBrandBackground: "#0F7F76",
    colorBrandBackgroundHover: "#0C746C",
    colorBrandBackgroundPressed: "#0A6862",
    colorBrandBackgroundSelected: "#0C746C",
    colorBrandForeground1: v.vAccent,
    colorBrandForeground2: v.vAccentTintText,
    colorBrandForegroundLink: v.vAccent,
    colorBrandForegroundLinkHover: "#79D3CA",
    colorBrandForegroundLinkPressed: "#3AA79C",
    colorBrandBackground2: v.vAccentTint,
    colorCompoundBrandBackground: "#2A9E94",
    colorCompoundBrandBackgroundHover: "#33AAA0",
    colorCompoundBrandBackgroundPressed: "#24877F",
    colorCompoundBrandStroke: "#2A9E94",
    colorCompoundBrandForeground1: v.vAccent,
    colorStatusSuccessBorder1: "rgba(52,199,107,0.3)",
    colorStatusWarningBorder1: "rgba(245,166,35,0.3)",
    colorStatusDangerBorder1: "rgba(240,80,80,0.32)",
    colorStatusDangerBackground3: "#C93B3B",
    colorStatusDangerBackground3Hover: "#B53333",
    colorStatusDangerBackground3Pressed: "#9F2C2C",
  };
}

export const vanimoLight = lightTheme();
export const vanimoDark = darkTheme();

// With the light value as fallback: shared components (DraftView) also render inside the Outlook
// add-in and Teams, which keep Microsoft's own themes and so don't define these variables.
const v = (name: keyof VanimoTokens) => `var(--${name}, ${vanimoLight[name]})`;

/** Vanimo tokens for makeStyles, e.g. `backgroundColor: vt.frame`. */
export const vt = {
  frame: v("vFrame"),
  surface: v("vSurface"),
  card: v("vCard"),
  raised: v("vRaised"),
  inset: v("vInset"),
  field: v("vField"),
  button: v("vButton"),
  buttonHover: v("vButtonHover"),
  buttonPressed: v("vButtonPressed"),
  hover: v("vHover"),
  selected: v("vSelected"),
  borderSubtle: v("vBorderSubtle"),
  border: v("vBorder"),
  borderStrong: v("vBorderStrong"),
  text1: v("vText1"),
  text2: v("vText2"),
  text3: v("vText3"),
  accent: v("vAccent"),
  accentTint: v("vAccentTint"),
  accentTintText: v("vAccentTintText"),
  accentRing: v("vAccentRing"),
  neutralTint: v("vNeutralTint"),
  neutralTintText: v("vNeutralTintText"),
  info: v("vInfo"),
  infoTint: v("vInfoTint"),
  purple: v("vPurple"),
  purpleTint: v("vPurpleTint"),
  success: v("vSuccess"),
  successTint: v("vSuccessTint"),
  warning: v("vWarning"),
  warningTint: v("vWarningTint"),
  danger: v("vDanger"),
  dangerTint: v("vDangerTint"),
  diffAddLine: v("vDiffAddLine"),
  diffAddWord: v("vDiffAddWord"),
  diffDelLine: v("vDiffDelLine"),
  diffDelWord: v("vDiffDelWord"),
  dot: v("vDot"),
  shadowCard: v("vShadowCard"),
  shadowButton: v("vShadowButton"),
  shadowRaised: v("vShadowRaised"),
  shadowOverlay: v("vShadowOverlay"),
  tooltip: v("vTooltip"),
  tooltipText: v("vTooltipText"),
  scrim: v("vScrim"),
} as const;
