/** Where something happened, drawn the same way everywhere: email is blue (Mail), a Teams chat is
 * purple (Chat), a meeting is the accent (CalendarLtr). Use with `IconTile` (rows) or `Pill`
 * (inline meta). */
import { CalendarLtr16Regular, CalendarLtr20Regular, Chat16Regular, Chat20Regular, Mail16Regular, Mail20Regular } from "@fluentui/react-icons";
import type { ReactElement } from "react";
import type { Tone } from "./tones";

export type Channel = "email" | "chat" | "meeting";

export const CHANNELS: Record<Channel, { icon: ReactElement; icon20: ReactElement; tone: Tone; label: string }> = {
  email: { icon: <Mail16Regular />, icon20: <Mail20Regular />, tone: "blue", label: "Email" },
  chat: { icon: <Chat16Regular />, icon20: <Chat20Regular />, tone: "purple", label: "Teams chat" },
  meeting: { icon: <CalendarLtr16Regular />, icon20: <CalendarLtr20Regular />, tone: "accent", label: "Meeting" },
};
