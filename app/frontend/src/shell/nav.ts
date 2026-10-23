/** Where you can go: the sidebar groups and the command palette read the same list. */
import {
  Beaker16Filled,
  Beaker16Regular,
  BookOpen16Filled,
  BookOpen16Regular,
  BuildingMultiple16Filled,
  BuildingMultiple16Regular,
  bundleIcon,
  CalendarLtr16Filled,
  CalendarLtr16Regular,
  ChatMultiple16Filled,
  ChatMultiple16Regular,
  Compose16Filled,
  Compose16Regular,
  DataUsage16Filled,
  DataUsage16Regular,
  DocumentSearch16Filled,
  DocumentSearch16Regular,
  Home16Filled,
  Home16Regular,
  MailInbox16Filled,
  MailInbox16Regular,
  PersonVoice16Filled,
  PersonVoice16Regular,
  ShieldCheckmark16Filled,
  ShieldCheckmark16Regular,
  ShieldLock16Filled,
  ShieldLock16Regular,
  TaskListSquareLtr16Filled,
  TaskListSquareLtr16Regular,
  type FluentIcon,
} from "@fluentui/react-icons";

export interface Destination {
  path: string;
  label: string;
  icon: FluentIcon;
  group: "main" | "voice" | "data" | "admin";
  /** Extra words the command palette matches ("promise" finds Commitments). */
  aliases?: string[];
  adminOnly?: boolean;
  sampleOnly?: boolean;
}

export const GROUP_LABELS: Record<Destination["group"], string | null> = {
  main: null,
  voice: "Your voice",
  data: "Data & privacy",
  admin: "Admin",
};

export const DESTINATIONS: Destination[] = [
  { path: "/", label: "Home", icon: bundleIcon(Home16Filled, Home16Regular), group: "main", aliases: ["dashboard", "start"] },
  { path: "/draft", label: "Draft", icon: bundleIcon(Compose16Filled, Compose16Regular), group: "main", aliases: ["reply", "write", "compose", "email"] },
  { path: "/queue", label: "Queue", icon: bundleIcon(MailInbox16Filled, MailInbox16Regular), group: "main", aliases: ["drafts", "waiting", "inbox"] },
  { path: "/commitments", label: "Commitments", icon: bundleIcon(TaskListSquareLtr16Filled, TaskListSquareLtr16Regular), group: "main", aliases: ["promises", "follow up", "tasks", "due"] },
  { path: "/meetings", label: "Meetings", icon: bundleIcon(CalendarLtr16Filled, CalendarLtr16Regular), group: "main", aliases: ["transcripts", "notes", "ask"] },
  { path: "/learning", label: "Learning", icon: bundleIcon(BookOpen16Filled, BookOpen16Regular), group: "voice", aliases: ["learn", "style", "training"] },
  { path: "/persona", label: "Persona", icon: bundleIcon(PersonVoice16Filled, PersonVoice16Regular), group: "voice", aliases: ["voice", "tone", "rules", "audience"] },
  { path: "/setup", label: "Sources", icon: bundleIcon(DocumentSearch16Filled, DocumentSearch16Regular), group: "data", aliases: ["setup", "review", "exclude", "choose what vanimo learns from"] },
  { path: "/controls", label: "My data", icon: bundleIcon(ShieldLock16Filled, ShieldLock16Regular), group: "data", aliases: ["privacy", "never-send", "delete", "purge", "rules"] },
  { path: "/sample", label: "Sample workspace", icon: bundleIcon(Beaker16Filled, Beaker16Regular), group: "data", aliases: ["synthetic", "kestrel", "demo"], sampleOnly: true },
  { path: "/admin/scoping", label: "Client scoping", icon: bundleIcon(BuildingMultiple16Filled, BuildingMultiple16Regular), group: "admin", aliases: ["clients", "domains", "organisation"], adminOnly: true },
  { path: "/admin/backstops", label: "Redaction checks", icon: bundleIcon(ShieldCheckmark16Filled, ShieldCheckmark16Regular), group: "admin", aliases: ["pii", "comprehend", "guardrails", "macie", "redact"], adminOnly: true },
  { path: "/admin/diagnostics", label: "Diagnostics", icon: bundleIcon(DataUsage16Filled, DataUsage16Regular), group: "admin", aliases: ["health", "latency", "spikes"], adminOnly: true },
  { path: "/spikes/teams", label: "Teams prefill test", icon: bundleIcon(ChatMultiple16Filled, ChatMultiple16Regular), group: "admin", aliases: ["teams", "deep link"], adminOnly: true },
]; // prettier-ignore

export function visibleDestinations(opts: { isAdmin: boolean; sample: boolean }): Destination[] {
  return DESTINATIONS.filter((d) => (!d.adminOnly || opts.isAdmin) && (!d.sampleOnly || opts.sample));
}

/** The destination a pathname belongs to ("/" only matches exactly). */
export function activePath(pathname: string): string {
  const match = DESTINATIONS.filter((d) => d.path !== "/" && pathname.startsWith(d.path)).sort(
    (a, b) => b.path.length - a.path.length,
  )[0];
  return match?.path ?? "/";
}
