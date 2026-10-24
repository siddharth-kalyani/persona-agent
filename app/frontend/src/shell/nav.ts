/** Where you can go: the sidebar groups and the command palette read the same list. */
import {
  Beaker20Filled,
  Beaker20Regular,
  BuildingMultiple20Filled,
  BuildingMultiple20Regular,
  bundleIcon,
  CalendarLtr20Filled,
  CalendarLtr20Regular,
  ChatMultiple20Filled,
  ChatMultiple20Regular,
  Compose20Filled,
  Compose20Regular,
  DataUsage20Filled,
  DataUsage20Regular,
  DocumentSearch20Filled,
  DocumentSearch20Regular,
  HatGraduation20Filled,
  HatGraduation20Regular,
  Home20Filled,
  Home20Regular,
  MailInbox20Filled,
  MailInbox20Regular,
  PersonVoice20Filled,
  PersonVoice20Regular,
  ShieldCheckmark20Filled,
  ShieldCheckmark20Regular,
  ShieldLock20Filled,
  ShieldLock20Regular,
  TaskListSquareLtr20Filled,
  TaskListSquareLtr20Regular,
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
  { path: "/", label: "Home", icon: bundleIcon(Home20Filled, Home20Regular), group: "main", aliases: ["dashboard", "start"] },
  { path: "/draft", label: "Draft", icon: bundleIcon(Compose20Filled, Compose20Regular), group: "main", aliases: ["reply", "write", "compose", "email"] },
  { path: "/queue", label: "Queue", icon: bundleIcon(MailInbox20Filled, MailInbox20Regular), group: "main", aliases: ["drafts", "waiting", "inbox"] },
  { path: "/commitments", label: "Commitments", icon: bundleIcon(TaskListSquareLtr20Filled, TaskListSquareLtr20Regular), group: "main", aliases: ["promises", "follow up", "tasks", "due"] },
  { path: "/meetings", label: "Meetings", icon: bundleIcon(CalendarLtr20Filled, CalendarLtr20Regular), group: "main", aliases: ["transcripts", "notes", "ask"] },
  { path: "/learning", label: "Learning", icon: bundleIcon(HatGraduation20Filled, HatGraduation20Regular), group: "voice", aliases: ["learn", "style", "training"] },
  { path: "/persona", label: "Persona", icon: bundleIcon(PersonVoice20Filled, PersonVoice20Regular), group: "voice", aliases: ["voice", "tone", "rules", "audience"] },
  { path: "/setup", label: "Sources", icon: bundleIcon(DocumentSearch20Filled, DocumentSearch20Regular), group: "data", aliases: ["setup", "review", "exclude", "choose what vanimo learns from"] },
  { path: "/controls", label: "My data", icon: bundleIcon(ShieldLock20Filled, ShieldLock20Regular), group: "data", aliases: ["privacy", "never-send", "delete", "purge", "rules"] },
  { path: "/sample", label: "Sample workspace", icon: bundleIcon(Beaker20Filled, Beaker20Regular), group: "data", aliases: ["synthetic", "kestrel", "demo"], sampleOnly: true },
  { path: "/admin/scoping", label: "Client scoping", icon: bundleIcon(BuildingMultiple20Filled, BuildingMultiple20Regular), group: "admin", aliases: ["clients", "domains", "organisation"], adminOnly: true },
  { path: "/admin/backstops", label: "Redaction checks", icon: bundleIcon(ShieldCheckmark20Filled, ShieldCheckmark20Regular), group: "admin", aliases: ["pii", "comprehend", "guardrails", "macie", "redact"], adminOnly: true },
  { path: "/admin/diagnostics", label: "Diagnostics", icon: bundleIcon(DataUsage20Filled, DataUsage20Regular), group: "admin", aliases: ["health", "latency", "spikes"], adminOnly: true },
  { path: "/spikes/teams", label: "Teams prefill test", icon: bundleIcon(ChatMultiple20Filled, ChatMultiple20Regular), group: "admin", aliases: ["teams", "deep link"], adminOnly: true },
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
