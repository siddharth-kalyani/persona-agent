/** The type scale (Inter Variable with optical sizes). Hierarchy comes from weight, colour and space
 * more than size: three weights (400/500/600), sentence case, tabular numbers wherever numbers are
 * compared. Tracking follows Inter's dynamic-metrics formula. Spread into makeStyles rules. */
import { tokens, type GriffelStyle } from "@fluentui/react-components";

const tabular: GriffelStyle = { fontVariantNumeric: "tabular-nums" };

export const typo = {
  pageTitle: { fontSize: "24px", lineHeight: "32px", fontWeight: 600, letterSpacing: "-0.022em" },
  sectionTitle: { fontSize: "15px", lineHeight: "22px", fontWeight: 600, letterSpacing: "-0.012em" },
  /** Card and panel headers. */
  cardTitle: { fontSize: "14px", lineHeight: "20px", fontWeight: 600, letterSpacing: "-0.008em" },
  itemTitle: { fontSize: "14px", lineHeight: "20px", fontWeight: 500, letterSpacing: "-0.006em" },
  body: { fontSize: "14px", lineHeight: "20px", fontWeight: 400, letterSpacing: "-0.006em" },
  /** Drafts, emails, transcripts, answers: text people read rather than scan. */
  reading: { fontSize: "15px", lineHeight: "24px", fontWeight: 400, letterSpacing: "-0.009em" },
  meta: { fontSize: "13px", lineHeight: "18px", fontWeight: 400, letterSpacing: "-0.003em" },
  label: { fontSize: "12px", lineHeight: "16px", fontWeight: 500, letterSpacing: "0" },
  metric: { fontSize: "28px", lineHeight: "34px", fontWeight: 600, letterSpacing: "-0.025em", ...tabular },
  /** Literal machine data only: tokens such as ⟦PERSON_…⟧, IDs, versions, hashes. */
  mono: { fontFamily: tokens.fontFamilyMonospace, fontSize: "12.5px", lineHeight: "18px", fontWeight: 400 },
  tabular,
  /** Email addresses and domains: Inter's disambiguation set makes l/I/1 and 0/O distinct. */
  address: { fontFeatureSettings: "'ss02'", overflowWrap: "anywhere" },
} satisfies Record<string, GriffelStyle>;
