/** Tones for pills, icon tiles and meters: neutral; the accent; categories (blue = email, purple =
 * Teams chat; meetings use the accent); states (success, warning, danger). A soft tint with a strong
 * foreground, AA in both themes. */
import { vt } from "../theme/theme";

export type Tone = "neutral" | "accent" | "blue" | "purple" | "success" | "warning" | "danger";

export const TONES: Record<Tone, { bg: string; fg: string }> = {
  neutral: { bg: vt.neutralTint, fg: vt.neutralTintText },
  accent: { bg: vt.accentTint, fg: vt.accentTintText },
  blue: { bg: vt.infoTint, fg: vt.info },
  purple: { bg: vt.purpleTint, fg: vt.purple },
  success: { bg: vt.successTint, fg: vt.success },
  warning: { bg: vt.warningTint, fg: vt.warning },
  danger: { bg: vt.dangerTint, fg: vt.danger },
};
