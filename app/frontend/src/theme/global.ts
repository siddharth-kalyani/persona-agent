/** Page-wide styles that Fluent's components don't set: the document background, font rendering,
 * selection, scrollbars and raised surfaces in dark mode. Rules inside media queries live in
 * global.css (makeStaticStyles can't nest selectors in @media). */
import { makeStaticStyles } from "@fluentui/react-components";

export const useGlobalStyles = makeStaticStyles({
  // The body sits outside the FluentProvider (which defines the variables), so its colours follow
  // the data-theme attribute the theme provider sets on <html>.
  "html, body": {
    margin: 0,
    backgroundColor: "#F9F9F8",
    color: "#21201C",
    fontFamily: "'Inter Variable', 'Segoe UI Variable Text', 'Segoe UI', system-ui, sans-serif",
    WebkitFontSmoothing: "antialiased",
    MozOsxFontSmoothing: "grayscale",
    textRendering: "optimizeLegibility",
    fontOpticalSizing: "auto",
  },
  "html[data-theme='dark'], html[data-theme='dark'] body": { backgroundColor: "#111110", color: "#EEEEEC" },
  "*, *::before, *::after": { boxSizing: "border-box" },
  "::selection": { backgroundColor: "var(--vAccentTint, #C0ECE7)", color: "var(--vText1, #21201C)" },
  // Quiet scrollbars that follow the theme.
  "*": { scrollbarColor: "var(--colorNeutralStroke1Hover, #BCBBB5) transparent", scrollbarWidth: "thin" },
  // Floating layers sit one step above the surface (most visible in dark mode, where shadows vanish).
  // Element + class beats Fluent's single atomic class without !important.
  "body .fui-PopoverSurface, body .fui-MenuPopover, body .fui-DialogSurface, body .fui-Toast, body .fui-Tooltip": {
    backgroundColor: "var(--vRaised)",
  },
  "body .fui-DialogSurface": { border: "1px solid var(--vBorder)", boxShadow: "var(--vShadowOverlay)" },
  "body .fui-PopoverSurface, body .fui-MenuPopover": {
    border: "1px solid var(--vBorder)",
    boxShadow: "var(--vShadowRaised)",
  },
  "body .fui-DialogSurface__backdrop": { backgroundColor: "var(--vScrim)" },
});
