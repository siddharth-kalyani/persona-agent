/** Visual building blocks: tinted icon tiles, icon-only actions (always with a tooltip and a label),
 * colourful avatars for people, an info popover for explanations that don't belong in the page, and a
 * thin proportion bar. */
import {
  Avatar,
  Button,
  makeStyles,
  mergeClasses,
  Popover,
  PopoverSurface,
  PopoverTrigger,
  Tooltip,
  type ButtonProps,
} from "@fluentui/react-components";
import { Info16Regular } from "@fluentui/react-icons";
import type { MouseEvent, ReactElement, ReactNode } from "react";
import { vt } from "../theme/theme";
import { typo } from "../theme/typography";
import { TONES, type Tone } from "./tones";

const useStyles = makeStyles({
  tile: { display: "inline-grid", placeItems: "center", flexShrink: 0, lineHeight: 0 },
  s24: { width: "24px", height: "24px", borderRadius: "6px" },
  s28: { width: "28px", height: "28px", borderRadius: "7px" },
  s32: { width: "32px", height: "32px", borderRadius: "8px" },
  s36: { width: "36px", height: "36px", borderRadius: "9px" },
  s40: { width: "40px", height: "40px", borderRadius: "10px" },
  /** A raised tile (white card with a hairline) for page headers: the icon in the accent. */
  raised: {
    backgroundColor: vt.card,
    border: `1px solid ${vt.border}`,
    boxShadow: vt.shadowCard,
    color: vt.accent,
  },
  neutral: { backgroundColor: TONES.neutral.bg, color: TONES.neutral.fg },
  accent: { backgroundColor: TONES.accent.bg, color: TONES.accent.fg },
  blue: { backgroundColor: TONES.blue.bg, color: TONES.blue.fg },
  purple: { backgroundColor: TONES.purple.bg, color: TONES.purple.fg },
  success: { backgroundColor: TONES.success.bg, color: TONES.success.fg },
  warning: { backgroundColor: TONES.warning.bg, color: TONES.warning.fg },
  danger: { backgroundColor: TONES.danger.bg, color: TONES.danger.fg },
  avatar: { fontWeight: 600, letterSpacing: "0.01em" },
  action: { color: vt.text2, "@media (pointer: coarse)": { minWidth: "40px", minHeight: "40px" } },
  dangerHover: { ":hover": { color: vt.danger }, ":hover:active": { color: vt.danger } },
  infoButton: { color: vt.text3, minWidth: "auto", ":hover": { color: vt.text1 } },
  infoSurface: { maxWidth: "340px", padding: "12px 14px", ...typo.meta, color: vt.text2 },
  infoTitle: { ...typo.cardTitle, color: vt.text1, margin: "0 0 4px" },
  meter: { display: "block", height: "6px", borderRadius: "999px", backgroundColor: vt.neutralTint, overflow: "hidden", minWidth: "48px" },
  meterFill: { display: "block", height: "100%", borderRadius: "999px" },
});

export type TileSize = 24 | 28 | 32 | 36 | 40;

const SIZE = { 24: "s24", 28: "s28", 32: "s32", 36: "s36", 40: "s40" } as const;

/** A rounded tinted square holding an icon: leads stat cards, card headers, rows that represent an
 * object (an email, a chat, a meeting) and empty states. Decorative unless given a label. */
export function IconTile({
  icon,
  tone = "neutral",
  size = 32,
  raised,
  label,
  className,
}: {
  icon: ReactNode;
  tone?: Tone;
  size?: TileSize;
  /** The page-header style: a white tile with a hairline and the icon in the accent. */
  raised?: boolean;
  label?: string;
  className?: string;
}) {
  const s = useStyles();
  return (
    <span
      className={mergeClasses(s.tile, s[SIZE[size]], raised ? s.raised : s[tone], className)}
      aria-hidden={label ? undefined : true}
      role={label ? "img" : undefined}
      aria-label={label}
    >
      {icon}
    </span>
  );
}

/** An icon-only button. The tooltip doubles as its accessible name, so it always says what it does. */
export function IconAction({
  icon,
  label,
  danger,
  size = "small",
  appearance = "subtle",
  className,
  onClick,
  disabled,
  ...aria
}: {
  icon: ReactElement;
  label: string;
  /** Turns red on hover (delete, discard). */
  danger?: boolean;
  size?: ButtonProps["size"];
  appearance?: ButtonProps["appearance"];
  className?: string;
  onClick?: (e: MouseEvent<HTMLButtonElement>) => void;
  disabled?: boolean;
  "aria-pressed"?: boolean;
  "aria-expanded"?: boolean;
  "aria-describedby"?: string;
}) {
  const s = useStyles();
  return (
    <Tooltip content={label} relationship="label" withArrow>
      <Button
        {...aria}
        onClick={onClick}
        disabled={disabled}
        appearance={appearance}
        size={size}
        icon={icon}
        className={mergeClasses(s.action, danger && s.dangerHover, className)}
      />
    </Tooltip>
  );
}

/** Avatar tints: the same soft tints as icon tiles (never red, which would read as an error). */
const AVATAR_TONES: Tone[] = ["blue", "purple", "accent", "success", "warning", "neutral"];

function hash(text: string): number {
  let h = 0;
  for (let i = 0; i < text.length; i++) h = (Math.imul(h, 31) + text.charCodeAt(i)) >>> 0;
  return h;
}

/** "Meera Iyer" → "MI", "Nisha (home)" → "N", "Kestrel Colleague 01" → "KC": words that start with a
 * letter only, ignoring anything in brackets. */
export function initialsOf(name?: string | null): string {
  const words = (name ?? "")
    .replace(/\([^)]*\)/g, " ")
    .split(/[\s._-]+/)
    .filter((w) => /^\p{L}/u.test(w));
  if (words.length === 0) return "";
  const first = words[0]!.charAt(0);
  const last = words.length > 1 ? words[words.length - 1]!.charAt(0) : "";
  return (first + last).toUpperCase();
}

/** A person: initials on a soft tint, the tint fixed per address so the same person always matches. */
export function PersonAvatar({ name, id, size = 28 }: { name?: string | null; id?: string | null; size?: 20 | 24 | 28 | 32 | 36 | 40 }) {
  const s = useStyles();
  const tone = AVATAR_TONES[hash((id ?? name ?? "").toLowerCase()) % AVATAR_TONES.length]!;
  const initials = initialsOf(name);
  const tint = mergeClasses(s[tone], s.avatar);
  return (
    // Fluent paints an avatar's colour on its initials (or icon) slot, so the tint goes there.
    <Avatar
      name={name ?? undefined}
      initials={{ className: tint, ...(initials ? { children: initials } : {}) }}
      icon={{ className: tint }}
      color="neutral"
      size={size}
      aria-hidden
    />
  );
}

/** "More about this" behind an ⓘ: explanations that would otherwise be a paragraph under a title. */
export function InfoTip({ label, title, children }: { label: string; title?: ReactNode; children: ReactNode }) {
  const s = useStyles();
  return (
    <Popover withArrow positioning="below-start">
      <PopoverTrigger disableButtonEnhancement>
        <Button appearance="transparent" size="small" icon={<Info16Regular />} aria-label={label} className={s.infoButton} />
      </PopoverTrigger>
      <PopoverSurface className={s.infoSurface} tabIndex={-1} aria-label={label}>
        {title && <p className={s.infoTitle}>{title}</p>}
        {children}
      </PopoverSurface>
    </Popover>
  );
}

/** A thin proportion bar. Decorative: always show the number beside it. */
export function Meter({ value, tone = "accent", className }: { value: number; tone?: Tone; className?: string }) {
  const s = useStyles();
  const pct = Math.max(0, Math.min(1, value)) * 100;
  return (
    <span className={mergeClasses(s.meter, className)} aria-hidden>
      <span className={s.meterFill} style={{ width: `${pct}%`, backgroundColor: TONES[tone].fg }} />
    </span>
  );
}
