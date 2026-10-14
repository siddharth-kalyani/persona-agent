/** Typed client for the Vanimo API. Errors carry the API's error code, never message content. */

export type TokenProvider = () => Promise<string>;

export class ApiError extends Error {
  constructor(
    public readonly status: number,
    public readonly code: string,
    public readonly body: Record<string, unknown> = {},
  ) {
    super(`${status} ${code}`);
  }
}

export interface Person {
  displayName: string | null;
  jobTitle: string | null;
  department?: string | null;
}

export interface SentHeader {
  subject: string | null;
  sentDateTime: string | null;
  recipientCount: number;
}

export interface Me {
  user: Person;
  manager: Person | null;
  recentSent: SentHeader[];
  roles: string[];
  onboardingState: string;
  signInMethod: "entra" | "password";
  email?: string | null;
  dataSource: "graph" | "sample";
  microsoft365Connected: boolean;
}

// --- Data controls (M1) -----------------------------------------------------------------------
export type SourceKind = "people" | "domains" | "threads" | "chats" | "meetings";
export type RuleKind = "person" | "domain" | "chat" | "thread" | "meeting" | "series";
export type TermKind = "word" | "name" | "codename";

export interface ControlsStatus {
  onboardingState: "review_pending" | "review_done";
  reviewOutcome: "finished" | "skipped" | null;
  scan: {
    status: "running" | "done" | "failed";
    sourceKind: "graph" | "sample";
    startedAt: string;
    finishedAt: string | null;
    counts: Record<string, number>;
  } | null;
  rules: number;
  neverSendWords: number;
}

export interface SourceItem {
  id: string;
  kind: RuleKind;
  label: string;
  detail: string | null;
  counts: Record<string, number>;
  lastActivity: string | null;
  flags: string[];
  excluded: boolean;
  ruleId: string | null;
  via: string[];
  locked: boolean;
}

export interface Impact {
  emails: number;
  threads: number;
  chats: number;
  meetings: number;
  chatList: { id: string; label: string; members: number; large: boolean }[];
}

export interface Rule {
  id: string;
  kind: RuleKind;
  label: string;
  createdAt: string;
  exceptions: number;
}

export interface WordPreview {
  variants: string[];
  /** What optional Hinglish folding reduces the word to; null when it doesn't apply. */
  foldedForm: string | null;
  appearsIn: number;
  appearsInWithFolds: number;
  commonWord: boolean;
}

export interface NeverSendWord {
  id: string;
  text: string;
  kind: TermKind;
  variants: string[];
  allowInDrafts: boolean;
  folds: boolean;
  createdAt: string;
}

export interface Receipt {
  id: string;
  reason: string;
  status: string;
  requestedAt: string;
  completedAt: string | null;
  counts: Record<string, unknown>;
  /** Failed after every automatic retry: shown to the user with a Retry button. */
  needsAttention?: boolean;
}

export interface ClientAccount {
  id: string;
  name: string;
  mode: "excluded" | "approved";
  domains: string[];
  sensitiveWords: number;
  createdAt: string;
}

export interface Scoping {
  externalMode: "allow_all" | "approved_only";
  accounts: ClientAccount[];
}

export type Outcome = "ok" | "warn" | "fail" | "skipped";

export interface CheckResult {
  check: string;
  outcome: Outcome;
  durationMs: number;
  details: Record<string, string | number | boolean | null>;
}

export interface LatencyResult {
  modelId: string;
  runs: number;
  errors: number;
  ttftMinMs: number | null;
  ttftMedianMs: number | null;
  ttftMaxMs: number | null;
  totalMedianMs: number | null;
  errorTypes: string[];
}

export interface HeaderPass {
  sentItems: number;
  sentPages: number;
  sentFinished: boolean;
  chats: number;
  chatPages: number;
  chatsFinished: boolean;
  elapsedMs: number;
  itemsPerSecond: number | null;
}

// --- Learning, persona, sample workspace (M2) ----------------------------------------------------
export interface LearningRun {
  id: string;
  status: "running" | "done" | "failed";
  sourceKind: "graph" | "sample";
  startedAt: string;
  finishedAt: string | null;
  counts: Record<string, number>;
  errorCode: string | null;
}

export interface LearningStatus {
  onboardingState: "review_pending" | "review_done";
  sourceKind: "graph" | "sample";
  run: LearningRun | null;
  stored: { email: number; chat: number; total: number };
  styleCards: number;
}

export interface StoredItem {
  id: string;
  channel: "email" | "chat";
  sentAt: string;
  relationship: string;
  intent: string;
  language: string;
  wordCount: number;
  heldOut: boolean;
  suspicious: boolean;
  subject: string | null;
  /** Exactly what is stored: tokens, [slots] and never-send placeholders. */
  stored: string;
  /** The stored text re-hydrated for you: names back, never-send words as [removed]. */
  display: string;
  contextStored: string | null;
  contextDisplay: string | null;
}

export type Distribution = [string, number][];

export interface StyleCard {
  n: number;
  greetings: Distribution;
  sign_offs: Distribution;
  length: { median: number; p25: number; p75: number };
  formality: number;
  exclamation_rate: number;
  question_rate: number;
  emoji_rate: number;
  phrases: string[];
  keep_list: string[];
  languages: Record<string, number>;
  intents: Record<string, number>;
}

export interface PersonaSettings {
  formality: number;
  length: number;
  warmth: number;
  emoji: boolean;
  polish: "none" | "light";
  phrases_do: string[];
  phrases_dont: string[];
}

export interface PersonaSnapshot {
  source: "graph" | "sample";
  learned_items: number;
  by: { channel: Record<string, number>; relationship: Record<string, number>; language: Record<string, number> };
  overall: StyleCard | null;
  audiences: { relationship: string; card: StyleCard }[];
  cards: number;
  settings: PersonaSettings;
  evaluation: { metrics: Record<string, number | string>; at: string } | null;
}

export interface SamplePerson {
  name: string | null;
  email: string;
}

export type ItemStatus = "learned" | "excluded" | "not_learned" | "received";

export interface SampleEmail {
  id: string;
  conversationId: string;
  subject: string | null;
  sentAt: string;
  sender: SamplePerson;
  to: SamplePerson[];
  cc: SamplePerson[];
  direction: "sent" | "received";
  body: string;
  status: ItemStatus;
  reasons: string[];
  storedId: string | null;
}

export interface SampleChat {
  id: string;
  chatType: string;
  label: string;
  members: SamplePerson[];
  excluded: boolean;
  reasons: string[];
  messages: {
    id: string;
    sender: SamplePerson;
    createdAt: string;
    text: string;
    fromMe: boolean;
    status: ItemStatus;
    storedId: string | null;
  }[];
}

export interface SampleMeeting {
  id: string;
  subject: string | null;
  start: string;
  end: string;
  organizer: SamplePerson | null;
  attendees: SamplePerson[];
  agenda: string | null;
  excluded: boolean;
  reasons: string[];
}

export interface SampleWorkspace {
  note: string;
  emails: SampleEmail[];
  chats: SampleChat[];
  meetings: SampleMeeting[];
}

export class Api {
  constructor(
    private readonly base: string,
    private readonly token: TokenProvider,
    /** Called when the API rejects the credentials (expired/revoked session). */
    private readonly onUnauthorized?: (code: string) => void,
  ) {}

  private async request<T>(method: string, path: string, body?: unknown): Promise<T> {
    const headers: Record<string, string> = { Authorization: `Bearer ${await this.token()}` };
    if (body !== undefined) headers["Content-Type"] = "application/json";
    const res = await fetch(`${this.base}${path}`, {
      method,
      headers,
      body: body === undefined ? undefined : JSON.stringify(body),
    });
    if (res.status === 204) return undefined as T;
    let json: Record<string, unknown> = {};
    try {
      json = await res.json();
    } catch {
      // Non-JSON error page (e.g. a proxy); fall through with an empty body.
    }
    if (!res.ok) {
      const code = String(json.error ?? "error");
      if (res.status === 401 || code === "password_change_required") this.onUnauthorized?.(code);
      throw new ApiError(res.status, code, json);
    }
    return json as T;
  }

  me = () => this.request<Me>("GET", "/api/me");

  controlsStatus = () => this.request<ControlsStatus>("GET", "/api/controls/status");
  startScan = () => this.request<ControlsStatus>("POST", "/api/controls/scan");
  sources = (kind: SourceKind) => this.request<SourceItem[]>("GET", `/api/controls/sources?kind=${kind}`);
  impact = (kind: RuleKind, id: string) => this.request<Impact>("POST", "/api/controls/impact", { kind, id });
  addRule = (kind: RuleKind, id: string, exceptChatIds: string[] = []) =>
    this.request<Rule>("POST", "/api/controls/rules", { kind, id, exceptChatIds });
  rules = () => this.request<Rule[]>("GET", "/api/controls/rules");
  removeRule = (ruleId: string) => this.request<void>("DELETE", `/api/controls/rules/${encodeURIComponent(ruleId)}`);
  previewWord = (text: string, kind: TermKind) =>
    this.request<WordPreview>("POST", "/api/controls/never-send/preview", { text, kind });
  words = () => this.request<NeverSendWord[]>("GET", "/api/controls/never-send");
  addWord = (text: string, kind: TermKind, variants: string[], allowInDrafts: boolean, folds = false) =>
    this.request<NeverSendWord>("POST", "/api/controls/never-send", { text, kind, variants, allowInDrafts, folds });
  updateWord = (id: string, allowInDrafts: boolean) =>
    this.request<void>("PATCH", `/api/controls/never-send/${encodeURIComponent(id)}`, { allowInDrafts });
  deleteWord = (id: string) => this.request<void>("DELETE", `/api/controls/never-send/${encodeURIComponent(id)}`);
  completeReview = (outcome: "finished" | "skipped") =>
    this.request<ControlsStatus>("POST", "/api/controls/review", { outcome });
  receipts = () => this.request<Receipt[]>("GET", "/api/controls/receipts");
  retryReceipt = (id: string) => this.request<Receipt>("POST", `/api/controls/receipts/${encodeURIComponent(id)}/retry`);

  learning = () => this.request<LearningStatus>("GET", "/api/learning");
  startLearning = () => this.request<LearningStatus>("POST", "/api/learning/run");
  deleteLearning = () =>
    this.request<{ jobId: string; status: string; counts: Record<string, unknown> }>("DELETE", "/api/learning");
  storedItems = (params: { ids?: string[]; channel?: "email" | "chat"; limit?: number; offset?: number } = {}) => {
    const q = new URLSearchParams();
    for (const id of params.ids ?? []) q.append("ids", id);
    if (params.channel) q.set("channel", params.channel);
    if (params.limit) q.set("limit", String(params.limit));
    if (params.offset) q.set("offset", String(params.offset));
    return this.request<{ items: StoredItem[]; total: number }>("GET", `/api/learning/items?${q.toString()}`);
  };
  persona = () => this.request<PersonaSnapshot>("GET", "/api/persona");
  savePersonaSettings = (settings: PersonaSettings) =>
    this.request<PersonaSettings>("PUT", "/api/persona/settings", settings);
  sampleWorkspace = () => this.request<SampleWorkspace>("GET", "/api/sample/workspace");

  scoping = () => this.request<Scoping>("GET", "/api/admin/scoping");
  setExternalMode = (externalMode: Scoping["externalMode"]) =>
    this.request<Scoping>("PUT", "/api/admin/scoping/policy", { externalMode });
  addAccount = (account: { name: string; mode: ClientAccount["mode"]; domains: string[]; sensitiveWords: string[] }) =>
    this.request<Scoping>("POST", "/api/admin/scoping/accounts", account);
  removeAccount = (id: string) => this.request<Scoping>("DELETE", `/api/admin/scoping/accounts/${encodeURIComponent(id)}`);
  runDiagnostics = () => this.request<{ results: CheckResult[] }>("POST", "/api/admin/diagnostics/run");
  headerPass = () => this.request<HeaderPass>("POST", "/api/admin/diagnostics/header-pass");
  bedrockLatency = (runs = 5) =>
    this.request<LatencyResult[]>("POST", "/api/admin/diagnostics/bedrock-latency", { runs });
  createDraftProbe = () =>
    this.request<{ draftId: string; webLink: string | null }>("POST", "/api/admin/diagnostics/draft-probe");
  deleteDraftProbe = (draftId: string) =>
    this.request<void>("DELETE", `/api/admin/diagnostics/draft-probe/${encodeURIComponent(draftId)}`);
}
