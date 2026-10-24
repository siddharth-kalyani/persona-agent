/** Page-wide styles that Fluent's components don't set: the document background, font rendering,
 * selection, scrollbars and raised layers. Rules inside media queries live in global.css
 * (makeStaticStyles can't nest selectors in @media). */
import { makeStaticStyles } from "@fluentui/react-components";

export const useGlobalStyles = makeStaticStyles({
  // The body sits outside the FluentProvider (which defines the variables), so its colours follow
  // the data-theme attribute the theme provider sets on <html>.
  "html, body": {
    margin: 0,
    backgroundColor: "#EEF0F2",
    color: "#111318",
    fontFamily: "'Inter Variable', 'Segoe UI Variable Text', 'Segoe UI', system-ui, sans-serif",
    WebkitFontSmoothing: "antialiased",
    MozOsxFontSmoothing: "grayscale",
    textRendering: "optimizeLegibility",
    fontOpticalSizing: "auto",
  },
  "html[data-theme='dark'], html[data-theme='dark'] body": { backgroundColor: "#0A0B0D", color: "#EDEEF0" },
  "*, *::before, *::after": { boxSizing: "border-box" },
  "::selection": { backgroundColor: "var(--vAccentRing, rgba(0,117,110,0.2))", color: "inherit" },
  // Quiet scrollbars that follow the theme.
  "*": { scrollbarColor: "var(--vBorderStrong, #CDD1D7) transparent", scrollbarWidth: "thin" },
  // Floating layers sit one step above the surface (in dark mode, where shadows barely show, the
  // lighter fill and the hairline do the work). Element + class beats Fluent's single atomic class
  // without !important.
  "body .fui-PopoverSurface, body .fui-MenuPopover, body .fui-DialogSurface, body .fui-Toast": {
    backgroundColor: "var(--vRaised)",
  },
  "body .fui-DialogSurface": { border: "1px solid var(--vBorder)", boxShadow: "var(--vShadowOverlay)" },
  "body .fui-PopoverSurface, body .fui-MenuPopover": {
    border: "1px solid var(--vBorder)",
    boxShadow: "var(--vShadowRaised)",
  },
  "body .fui-DialogSurface__backdrop": { backgroundColor: "var(--vScrim)" },
});
