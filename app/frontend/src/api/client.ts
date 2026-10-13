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
  appearsIn: number;
  commonWord: boolean;
}

export interface NeverSendWord {
  id: string;
  text: string;
  kind: TermKind;
  variants: string[];
  allowInDrafts: boolean;
  createdAt: string;
}

export interface Receipt {
  id: string;
  reason: string;
  status: string;
  requestedAt: string;
  completedAt: string | null;
  counts: Record<string, unknown>;
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
  addWord = (text: string, kind: TermKind, variants: string[], allowInDrafts: boolean) =>
    this.request<NeverSendWord>("POST", "/api/controls/never-send", { text, kind, variants, allowInDrafts });
  updateWord = (id: string, allowInDrafts: boolean) =>
    this.request<void>("PATCH", `/api/controls/never-send/${encodeURIComponent(id)}`, { allowInDrafts });
  deleteWord = (id: string) => this.request<void>("DELETE", `/api/controls/never-send/${encodeURIComponent(id)}`);
  completeReview = (outcome: "finished" | "skipped") =>
    this.request<ControlsStatus>("POST", "/api/controls/review", { outcome });
  receipts = () => this.request<Receipt[]>("GET", "/api/controls/receipts");

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
