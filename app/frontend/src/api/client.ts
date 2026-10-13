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
  microsoft365Connected: boolean;
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
  runDiagnostics = () => this.request<{ results: CheckResult[] }>("POST", "/api/admin/diagnostics/run");
  headerPass = () => this.request<HeaderPass>("POST", "/api/admin/diagnostics/header-pass");
  bedrockLatency = (runs = 5) =>
    this.request<LatencyResult[]>("POST", "/api/admin/diagnostics/bedrock-latency", { runs });
  createDraftProbe = () =>
    this.request<{ draftId: string; webLink: string | null }>("POST", "/api/admin/diagnostics/draft-probe");
  deleteDraftProbe = (draftId: string) =>
    this.request<void>("DELETE", `/api/admin/diagnostics/draft-probe/${encodeURIComponent(draftId)}`);
}
