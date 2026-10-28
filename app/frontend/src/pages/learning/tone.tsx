/** Tone groups (F15), said the same way on every page: formal, friendly or casual, where a conversation
 * happens (email, a Teams 1:1 chat or a Teams group), and why Vanimo put someone in a group. */
import {
  Briefcase16Regular,
  Chat16Regular,
  Emoji16Regular,
  HandWave16Regular,
  Mail16Regular,
  People16Regular,
} from "@fluentui/react-icons";
import type { ReactElement } from "react";
import type { Bucket, ToneConversation, ToneGroup } from "../../api/client";
import type { Tone } from "../../ui";

export const TONE_ORDER: ToneGroup[] = ["formal", "friendly", "casual"];

export const TONE_INFO: Record<ToneGroup, { label: string; description: string; icon: ReactElement; example: string }> = {
  formal: {
    label: "Formal",
    description: "Respectful and professional",
    icon: <Briefcase16Regular />,
    example: "Dear Karan, … Kindly confirm. Best regards",
  },
  friendly: {
    label: "Friendly",
    description: "Professional, warm and relaxed",
    icon: <HandWave16Regular />,
    example: "Hi Meera, … Thanks!",
  },
  casual: {
    label: "Casual",
    description: "Like with friends",
    icon: <Emoji16Regular />,
    example: "Bhai, kal tak bhej dena pls",
  },
};

export const BUCKET_INFO: Record<Bucket, { label: string; short: string; icon: ReactElement; tone: Tone }> = {
  email: { label: "Email", short: "Email", icon: <Mail16Regular />, tone: "blue" },
  dm: { label: "Teams 1:1 chat", short: "Teams 1:1", icon: <Chat16Regular />, tone: "purple" },
  group: { label: "Teams group chat", short: "Teams group", icon: <People16Regular />, tone: "purple" },
};

/** Why someone is in a group, in plain words. */
export function toneReason(c: Pick<ToneConversation, "basis" | "override" | "mine" | "theirs" | "judgedBy">): string {
  if (c.override) return "You chose this.";
  const who = c.judgedBy === "ai" ? "Claude" : "Vanimo";
  switch (c.basis) {
    case "your_messages":
      return `${who} read ${c.mine} of your messages to them.`;
    case "their_messages":
      return `You've written little here yet, so ${who} read their ${c.theirs} message${c.theirs === 1 ? "" : "s"} to you.`;
    case "directory":
      return "Your messages here are short or neutral, so Vanimo went by your directory (manager, team, client).";
    default:
      return "Nothing to learn from yet, so Vanimo starts formal: too polite is safer than too casual.";
  }
}
