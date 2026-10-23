/** Vanimo's visual system on Fluent UI v9: warm neutrals, one deep-teal accent, Inter, hairlines
 * before shadows. Light and dark are tuned separately (surfaces get lighter as they rise in dark).
 * Contrast ratios were checked for every text token (WCAG 2.2 AA); tertiary text is never used on
 * the "selected" background. */
import { createDarkTheme, createLightTheme, type BrandVariants, type Theme } from "@fluentui/react-components";

/** Deep teal, OKLCH hue 188: not the indigo of AI products, not Outlook blue. */
export const brand: BrandVariants = {
  10: "#001C1A", 20: "#002926", 30: "#003632", 40: "#00433E", 50: "#00504B", 60: "#005E58", 70: "#006C65",
  80: "#007972", 90: "#008881", 100: "#259790", 110: "#40A69E", 120: "#5AB5AD", 130: "#79C6BF", 140: "#9BD8D2",
  150: "#C0ECE7", 160: "#E5F8F6",
}; // prettier-ignore

/** Tokens Fluent doesn't have. The FluentProvider writes every theme key as a CSS variable, so these
 * swap with light/dark like Fluent's own. Use them through `vt`. */
export interface VanimoTokens {
  vFrame: string; // app background and sidebar
  vSurface: string; // content panel, cards, inputs
  vRaised: string; // menus, popovers, dialogs
  vInset: string; // quoted text, code, kbd, excerpts
  vHover: string;
  vSelected: string;
  vBorderSubtle: string;
  vBorder: string;
  vText1: string;
  vText2: string;
  vText3: string;
  vAccent: string; // accent as text/icon on surfaces
  vAccentTint: string; // selected chips, highlights
  vAccentTintText: string;
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
  vShadowRaised: string;
  vShadowOverlay: string;
  vScrim: string;
}



const FONT_BASE = "'Inter Variable', 'Segoe UI Variable Text', 'Segoe UI', system-ui, -apple-system, sans-serif";
const FONT_MONO = "'JetBrains Mono Variable', Consolas, ui-monospace, 'SF Mono', monospace";

const SHARED: Partial<Theme> = {
  fontFamilyBase: FONT_BASE,
  fontFamilyNumeric: FONT_BASE, // Fluent's default (Bahnschrift) would clash
  fontFamilyMonospace: FONT_MONO,
  borderRadiusSmall: "4px",
  borderRadiusMedium: "6px",
  borderRadiusLarge: "8px",
  borderRadiusXLarge: "12px",
  // Fluent's decelerate curve and durations stay; motion is used sparingly (see theme/motion.ts).
};

function lightTheme(): Theme & VanimoTokens {
  const v: VanimoTokens = {
    vFrame: "#F9F9F8",
    vSurface: "#FDFDFC",
    vRaised: "#FFFFFF",
    vInset: "#F1F0EF",
    vHover: "#F1F0EF",
    vSelected: "#E9E8E6",
    vBorderSubtle: "#E9E8E6",
    vBorder: "#DAD9D6",
    vText1: "#21201C",
    vText2: "#63635E",
    vText3: "#6C6B66",
    vAccent: "#007972",
    vAccentTint: "#E5F8F6",
    vAccentTintText: "#006C65",
    vSuccess: "#257235",
    vSuccessTint: "#E9F6E9",
    vWarning: "#8C5A00",
    vWarningTint: "#FFF7C2",
    vDanger: "#C4262B",
    vDangerTint: "#FEEBEC",
    vDiffAddLine: "#E9F6E9",
    vDiffAddWord: "#C9E8CA",
    vDiffDelLine: "#FEEBEC",
    vDiffDelWord: "#FFCDCE",
    vDot: "#8D8D86",
    vShadowRaised: "0 1px 2px rgba(0,0,0,.06), 0 4px 16px rgba(0,0,0,.08)",
    vShadowOverlay: "0 1px 3px rgba(0,0,0,.08), 0 24px 48px rgba(0,0,0,.16)",
    vScrim: "rgba(17,17,16,.24)",
  };
  return {
    ...createLightTheme(brand),
    ...SHARED,
    ...v,
    colorNeutralBackground1: v.vSurface,
    colorNeutralBackground1Hover: v.vHover,
    colorNeutralBackground1Pressed: v.vSelected,
    colorNeutralBackground1Selected: v.vSelected,
    colorNeutralBackground2: v.vFrame,
    colorNeutralBackground2Hover: v.vHover,
    colorNeutralBackground2Pressed: v.vSelected,
    colorNeutralBackground2Selected: v.vSelected,
    colorNeutralBackground3: v.vInset,
    colorNeutralBackground4: "#EEEDEB",
    colorNeutralBackground5: "#E9E8E6",
    colorSubtleBackgroundHover: v.vHover,
    colorSubtleBackgroundPressed: v.vSelected,
    colorSubtleBackgroundSelected: v.vSelected,
    colorTransparentBackgroundHover: v.vHover,
    colorTransparentBackgroundPressed: v.vSelected,
    colorNeutralForeground1: v.vText1,
    colorNeutralForeground1Hover: v.vText1,
    colorNeutralForeground1Pressed: v.vText1,
    colorNeutralForeground1Selected: v.vText1,
    colorNeutralForeground2: "#44433E",
    colorNeutralForeground2Hover: v.vText1,
    colorNeutralForeground2Pressed: v.vText1,
    colorNeutralForeground2Selected: v.vText1,
    colorNeutralForeground3: v.vText2,
    colorNeutralForeground3Hover: "#44433E",
    colorNeutralForeground3Pressed: "#44433E",
    colorNeutralForeground3Selected: "#44433E",
    colorNeutralForeground4: v.vText3,
    colorNeutralForegroundDisabled: "#BCBBB5",
    colorNeutralStroke1: "#CFCECA",
    colorNeutralStroke1Hover: "#BCBBB5",
    colorNeutralStroke1Pressed: "#A9A8A2",
    colorNeutralStroke1Selected: "#BCBBB5",
    colorNeutralStroke2: v.vBorder,
    colorNeutralStroke3: v.vBorderSubtle,
    colorNeutralStrokeSubtle: v.vBorderSubtle,
    colorNeutralStrokeAccessible: "#8D8D86",
    colorNeutralStrokeAccessibleHover: "#6C6B66",
    colorNeutralStrokeAccessiblePressed: "#63635E",
    colorStrokeFocus2: v.vAccent,
    colorNeutralShadowAmbient: "rgba(0,0,0,0.06)",
    colorNeutralShadowKey: "rgba(0,0,0,0.08)",
    shadow2: "0 0 1px rgba(0,0,0,.08), 0 1px 2px rgba(0,0,0,.06)",
    shadow4: "0 0 1px rgba(0,0,0,.08), 0 2px 4px rgba(0,0,0,.06)",
    shadow8: "0 1px 2px rgba(0,0,0,.06), 0 4px 12px rgba(0,0,0,.08)",
    shadow16: v.vShadowRaised,
    shadow28: "0 1px 3px rgba(0,0,0,.08), 0 14px 32px rgba(0,0,0,.12)",
    shadow64: v.vShadowOverlay,
    colorStatusSuccessBackground1: v.vSuccessTint,
    colorStatusSuccessBorder1: "#B2DDB5",
    colorStatusSuccessForeground1: v.vSuccess,
    colorStatusSuccessForeground3: v.vSuccess,
    colorStatusWarningBackground1: v.vWarningTint,
    colorStatusWarningBorder1: "#F3D673",
    colorStatusWarningForeground1: v.vWarning,
    colorStatusWarningForeground3: v.vWarning,
    colorStatusDangerBackground1: v.vDangerTint,
    colorStatusDangerBorder1: "#FDBDBE",
    colorStatusDangerForeground1: v.vDanger,
    colorStatusDangerForeground3: v.vDanger,
    colorStatusDangerBackground3: "#CE2C31",
    colorStatusDangerBackground3Hover: "#B8252A",
    colorStatusDangerBackground3Pressed: "#A11F24",
  };
}

function darkTheme(): Theme & VanimoTokens {
  const v: VanimoTokens = {
    vFrame: "#111110",
    vSurface: "#191918",
    vRaised: "#222221",
    vInset: "#111110",
    vHover: "#222221",
    vSelected: "#2A2A28",
    vBorderSubtle: "#2A2A28",
    vBorder: "#3B3A37",
    vText1: "#EEEEEC",
    vText2: "#B5B3AD",
    vText3: "#8F8D86",
    vAccent: "#40A69E",
    vAccentTint: "#0D2D2A",
    vAccentTintText: "#40A69E",
    vSuccess: "#71D083",
    vSuccessTint: "#1B2A1E",
    vWarning: "#FFCA16",
    vWarningTint: "#302008",
    vDanger: "#FF9592",
    vDangerTint: "#3B1219",
    vDiffAddLine: "#1B2A1E",
    vDiffAddWord: "#2D5736",
    vDiffDelLine: "#3B1219",
    vDiffDelWord: "#611623",
    vDot: "#6F6D66",
    vShadowRaised: "0 8px 24px rgba(0,0,0,.5)",
    vShadowOverlay: "0 24px 48px rgba(0,0,0,.6)",
    vScrim: "rgba(0,0,0,.56)",
  };
  return {
    ...createDarkTheme(brand),
    ...SHARED,
    ...v,
    colorBrandForeground1: brand[110],
    colorBrandForeground2: brand[120],
    colorBrandForegroundLink: brand[110],
    colorBrandForegroundLinkHover: brand[120],
    colorBrandForegroundLinkPressed: brand[100],
    colorNeutralBackground1: v.vSurface,
    colorNeutralBackground1Hover: v.vHover,
    colorNeutralBackground1Pressed: v.vSelected,
    colorNeutralBackground1Selected: v.vSelected,
    colorNeutralBackground2: v.vFrame,
    colorNeutralBackground2Hover: v.vHover,
    colorNeutralBackground2Pressed: v.vSelected,
    colorNeutralBackground2Selected: v.vSelected,
    colorNeutralBackground3: v.vInset,
    colorNeutralBackground4: "#0D0D0C",
    colorNeutralBackground5: "#0A0A09",
    colorSubtleBackgroundHover: v.vHover,
    colorSubtleBackgroundPressed: v.vSelected,
    colorSubtleBackgroundSelected: v.vSelected,
    colorTransparentBackgroundHover: v.vHover,
    colorTransparentBackgroundPressed: v.vSelected,
    colorNeutralForeground1: v.vText1,
    colorNeutralForeground1Hover: v.vText1,
    colorNeutralForeground1Pressed: v.vText1,
    colorNeutralForeground1Selected: v.vText1,
    colorNeutralForeground2: "#D0CEC8",
    colorNeutralForeground2Hover: v.vText1,
    colorNeutralForeground2Pressed: v.vText1,
    colorNeutralForeground2Selected: v.vText1,
    colorNeutralForeground3: v.vText2,
    colorNeutralForeground3Hover: "#D0CEC8",
    colorNeutralForeground3Pressed: "#D0CEC8",
    colorNeutralForeground3Selected: "#D0CEC8",
    colorNeutralForeground4: v.vText3,
    colorNeutralForegroundDisabled: "#62605B",
    colorNeutralStroke1: "#494844",
    colorNeutralStroke1Hover: "#5A5853",
    colorNeutralStroke1Pressed: "#62605B",
    colorNeutralStroke1Selected: "#5A5853",
    colorNeutralStroke2: v.vBorder,
    colorNeutralStroke3: v.vBorderSubtle,
    colorNeutralStrokeSubtle: v.vBorderSubtle,
    colorNeutralStrokeAccessible: "#6F6D66",
    colorNeutralStrokeAccessibleHover: "#8F8D86",
    colorNeutralStrokeAccessiblePressed: "#B5B3AD",
    colorStrokeFocus2: brand[120],
    shadow16: v.vShadowRaised,
    shadow64: v.vShadowOverlay,
    colorStatusSuccessBackground1: v.vSuccessTint,
    colorStatusSuccessBorder1: "#2D5736",
    colorStatusSuccessForeground1: v.vSuccess,
    colorStatusSuccessForeground3: v.vSuccess,
    colorStatusWarningBackground1: v.vWarningTint,
    colorStatusWarningBorder1: "#5C3D05",
    colorStatusWarningForeground1: v.vWarning,
    colorStatusWarningForeground3: v.vWarning,
    colorStatusDangerBackground1: v.vDangerTint,
    colorStatusDangerBorder1: "#72232D",
    colorStatusDangerForeground1: v.vDanger,
    colorStatusDangerForeground3: v.vDanger,
    colorStatusDangerBackground3: "#CE2C31",
    colorStatusDangerBackground3Hover: "#B8252A",
    colorStatusDangerBackground3Pressed: "#A11F24",
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
  raised: v("vRaised"),
  inset: v("vInset"),
  hover: v("vHover"),
  selected: v("vSelected"),
  borderSubtle: v("vBorderSubtle"),
  border: v("vBorder"),
  text1: v("vText1"),
  text2: v("vText2"),
  text3: v("vText3"),
  accent: v("vAccent"),
  accentTint: v("vAccentTint"),
  accentTintText: v("vAccentTintText"),
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
  shadowRaised: v("vShadowRaised"),
  shadowOverlay: v("vShadowOverlay"),
  scrim: v("vScrim"),
} as const;
