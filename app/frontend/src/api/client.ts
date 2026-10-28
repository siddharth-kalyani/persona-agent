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
  /** F11: a Macie finding paused the organisation's pipeline until an admin resumes it. */
  pipelinePaused?: boolean;
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
  /** The organisation allows drafts in people's Outlook Drafts folder (each person still opts in). */
  serverDrafts: boolean;
  /** Teams (M5): open a chat with the draft typed in (after the prefill spike); else Copy only. */
  teamsPrefill: boolean;
  teamsNotifications: boolean;
  /** Meeting memory (M6): read Teams transcripts of internal meetings (each still goes through people's exclusions). */
  meetingMemory: boolean;
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
  /** Drafting may start: a finished run whose result is still stored (F15). */
  learned: boolean;
  /** The last finished run predates tone groups: learn again before drafting. */
  outdated: boolean;
}

/** Tone groups (F15): how you write to someone, learned from your own messages. */
export type ToneGroup = "formal" | "friendly" | "casual";
/** Where a conversation happens: email, a Teams 1:1 chat or a Teams group chat. */
export type Bucket = "email" | "dm" | "group";

export interface StoredItem {
  id: string;
  channel: "email" | "chat";
  sentAt: string;
  relationship: string;
  intent: string;
  language: string;
  wordCount: number;
  bucket: Bucket;
  tone: ToneGroup;
  situations: string[];
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

/** One conversation partner and its tone: a person (email or a Teams 1:1 chat) or a group chat. */
export interface ToneConversation {
  /** Opaque: what PUT /api/persona/tones names it by. */
  key: string;
  bucket: Bucket;
  /** Your choice if you made one, else what Vanimo judged. */
  tone: ToneGroup;
  judged: ToneGroup;
  override: ToneGroup | null;
  basis: "your_messages" | "their_messages" | "directory" | "default";
  judgedBy: "ai" | "rules";
  mine: number;
  theirs: number;
  label: string | null;
  email: string | null;
  members: number | null;
  learned: number;
  updatedAt: string;
}

export interface VocabularyPhrase {
  phrase: string;
  uses: number;
  conversations: number;
  channels: Bucket[];
}

export interface PersonaSnapshot {
  source: "graph" | "sample";
  learned_items: number;
  by: {
    channel: Record<string, number>;
    bucket: Record<string, number>;
    tone: Record<string, number>;
    language: Record<string, number>;
  };
  overall: StyleCard | null;
  tone_cards: Partial<Record<ToneGroup, StyleCard>>;
  bucket_cards: Partial<Record<Bucket, StyleCard>>;
  /** Keyed "tone|bucket". */
  tone_bucket_cards: Record<string, StyleCard>;
  conversations: ToneConversation[];
  vocabulary: {
    tones: Partial<Record<ToneGroup, Record<string, VocabularyPhrase[]>>>;
    spellings: { use: string; instead_of: string; share: number; uses: number }[];
    labels: Record<string, string>;
  };
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

// --- Drafting (M3) ------------------------------------------------------------------------------
export type Severity = "block" | "warn" | "info";

export interface DraftCheck {
  code: string;
  /** block = insert stays off until you confirm; warn = read before sending; info = for your information. */
  severity: Severity;
  message: string;
}

export interface PersonRef {
  email: string;
  name?: string | null;
}

export interface DraftingStatus {
  generator: "offline" | "bedrock";
  label: string;
  defaultModel: string;
  premiumModel: string;
  premiumLeftToday: number;
  reviewDone: boolean;
  learnedItems: number;
  sourceKind: "graph" | "sample";
  /** Drafting waits for this (F15). */
  learned: boolean;
  learningRunning: boolean;
  learningOutdated: boolean;
}

export interface DraftThread {
  conversationId: string;
  subject: string | null;
  sender: PersonRef;
  receivedAt: string;
  excluded: boolean;
  excludedBy: "you" | "organisation" | "unverifiable" | null;
  reasons: string[];
}

export interface ThreadView {
  conversationId: string;
  subject: string | null;
  messages: { sender: PersonRef; sentAt: string; fromMe: boolean; text: string }[];
  participants: PersonRef[];
}

export interface DraftRequest {
  mode: "reply" | "new";
  surface?: "outlook" | "web" | "teams";
  /** "chat": a Teams chat; conversationId is then the chat ID. */
  channel?: "email" | "chat";
  conversationId?: string | null;
  /** Teams: the chat message being answered. */
  messageId?: string | null;
  to?: PersonRef[];
  cc?: PersonRef[];
  subject?: string | null;
  instruction?: string | null;
  quality?: "auto" | "standard" | "premium";
  replyAll?: boolean;
  /** Draft once, in memory, in a conversation you excluded. */
  oneOff?: boolean;
}

export interface Draft {
  id: string | null;
  text: string;
  generator: "offline" | "bedrock";
  label: string;
  modelId: string;
  tier: "default" | "premium";
  routeReason: string;
  audience: {
    relationship: string;
    label: string;
    to: PersonRef[];
    cc: PersonRef[];
    internal: number;
    external: number;
    bucket?: Bucket;
    tone?: ToneGroup;
    /** learned, or how a new conversation's tone was judged just now. */
    toneBasis?: string | null;
  };
  styleSlice: string | null;
  learned: boolean;
  basedOn: number;
  exemplars: number;
  checks: DraftCheck[];
  insertAllowed: boolean;
  oneOff: boolean;
  timing: { totalMs: number; modelMs: number | null };
  channel?: "email" | "chat";
  /** Teams: who "Open chat" opens the chat with. */
  chatUsers?: string[];
}

export interface DraftSummary {
  id: string;
  createdAt: string;
  surface: string;
  mode: string;
  generator: string;
  tier: string;
  modelId: string | null;
  relationship: string;
  wordCount: number;
  latencyMs: number | null;
  checks: string[];
  outcome: string | null;
  rating: string | null;
  channel?: "email" | "chat";
  tone?: ToneGroup | null;
}

export type DraftOutcome = "inserted" | "copied" | "opened_reply" | "opened_chat" | "discarded";

// --- Teams chats, commitments, notifications (M5) -------------------------------------------------
export interface DraftChat {
  chatId: string;
  chatType: "oneOnOne" | "group" | "meeting";
  label: string;
  members: number;
  lastActivityAt: string | null;
  excluded: boolean;
  excludedBy: "you" | "organisation" | "unverifiable" | null;
  reasons: string[];
}

export interface ChatView {
  chatId: string;
  label: string;
  messages: { sender: PersonRef; sentAt: string; fromMe: boolean; text: string }[];
}

export interface Commitment {
  id: string;
  /** "meeting": said in a Teams meeting (M6); there's no conversation to follow up in. */
  channel: "email" | "chat" | "meeting";
  what: string;
  sentence: string;
  duePhrase: string | null;
  dueAt: string | null;
  madeAt: string;
  relationship: string;
  status: "open" | "done" | "dismissed";
  statusAt: string | null;
  snoozedUntil: string | null;
  /** A later message of yours in the same thread seems to deliver it. */
  looksDoneAt: string | null;
  extractor: "offline" | "bedrock";
}

export interface Ledger {
  items: Commitment[];
  open: number;
  overdue: number;
  dueSoon: number;
  capturedThisWeek: number;
  precision: number | null;
  decided: number;
  label: string;
  hidden: number;
}

export interface CommitmentScan {
  found: number;
  hints: number;
  read: number;
  excluded: number;
  pending: boolean;
  skipped: boolean;
}

export type FollowUpKind = "done" | "late" | "update";

export interface AppNotification {
  id: string;
  kind: "commitments_due" | "rules_to_confirm" | "review_reminder";
  count: number;
  text: string;
  createdAt: string;
  read: boolean;
  teams: "pending" | "sent" | "failed" | "off";
}

export interface TeamsConfig {
  prefill: boolean;
  appId: string | null;
}

export interface TeamsDialogTarget {
  mode: "reply" | "new" | "channel";
  chatId: string | null;
  messageId: string | null;
}

// --- Drafts queue, Outlook Drafts folder, edit loop (M4) ----------------------------------------
// --- Meeting memory (M6) ----------------------------------------------------------------------------
export type NoteKind = "decision" | "action_item" | "commitment" | "requirement" | "open_question" | "risk" | "idea";
export type SpeakerSide = "me" | "internal" | "external" | "unknown";

export interface MeetingSummary {
  id: string;
  title: string;
  startsAt: string;
  endsAt: string;
  /** People from outside the organisation were invited. */
  external: boolean;
  organizedByMe: boolean;
  /** "unattributed": the organisation turned Teams speaker attribution off (no names). */
  attribution: "named" | "unattributed";
  notes: Partial<Record<NoteKind, number>>;
  /** The transcript is kept until then (30 days), for citations. */
  transcriptUntil: string | null;
  extractor: "offline" | "bedrock";
}

export interface MeetingList {
  items: MeetingSummary[];
  on: boolean;
  label: string;
  hidden: number;
}

export interface MeetingNote {
  id: string;
  kind: NoteKind;
  text: string;
  quote: string;
  speaker: string;
  speakerId: string | null;
  speakerSide: SpeakerSide;
  owner: string | null;
  saidAt: string;
  dueAt: string | null;
  duePhrase: string | null;
  trust: "high" | "medium" | "low";
  status: "active" | "dismissed";
  turn: number;
}

export interface MeetingTurn {
  turn: number;
  at: string;
  speaker: string;
  speakerId: string | null;
  speakerSide: SpeakerSide;
  text: string;
}

export interface MeetingDetail extends MeetingSummary {
  notesList: MeetingNote[];
  transcript: MeetingTurn[];
  people: { id: string; name: string; side: SpeakerSide }[];
}

export interface MeetingScan {
  stored: number;
  atoms: number;
  promises: number;
  excluded: number;
  waiting: number;
  pending: boolean;
  skipped: boolean;
  off: boolean;
  /** Why transcripts can't be read: "disabled" (Teams admin), "permission" (consent). */
  unavailable: string | null;
  leftOut: number;
}

export interface MeetingCitation {
  n: number;
  meetingId: string;
  title: string;
  meetingStart: string;
  kind: NoteKind | "said";
  noteId: string | null;
  at: string;
  endAt: string;
  speaker: string;
  quote: string;
  turn: number;
}

export interface MeetingAnswer {
  answer: string;
  citations: MeetingCitation[];
  abstained: boolean;
  /** Two meetings match: pick one of `candidates` and ask again. */
  clarify: boolean;
  candidates: { id: string; title: string; startsAt: string }[];
  when: string;
  label: string;
}

export interface MeetingHealth {
  on: boolean;
  checks: { key: string; state: "ok" | "warn" | "fail" | "info"; code: string; counts: Record<string, number> }[];
  checkedAt: string;
}

// --- Redaction backstops (F11) ------------------------------------------------------------------
export type BackstopKey = "comprehend" | "guardrail" | "macie";

export interface BackstopEvent {
  id: number;
  at: string;
  source: BackstopKey;
  stage: "redaction" | "model_input" | "model_output" | "snapshot";
  outcome: "blocked" | "finding" | "unavailable";
  /** Entity types and counts: never the values. */
  kinds: Record<string, number>;
  severity: "low" | "medium" | "high" | null;
  /** Internal user ID (no name or address). */
  user: string | null;
  ref: string;
  /** Rows a snapshot finding names: removable by an admin without seeing them. */
  flaggedItems: number;
  purgedAt: string | null;
}

export interface BackstopStatus {
  backstops: { key: BackstopKey; mode: "aws" | "offline"; label: string }[];
  comprehendScope: "all" | "flagged";
  snapshotEveryHours: number;
  paused: { since: string; reason: string; ref: string | null } | null;
  mySnapshot: { exportedAt: string; items: number; stored: boolean; offlineFindings: number | null } | null;
  events: BackstopEvent[];
}

export interface BackstopProbe {
  key: BackstopKey | "guardrail_india";
  state: "ok" | "warn" | "fail";
  code: string;
  ms: number;
}

export interface SnapshotExport {
  exported: number;
  failed: number;
  findings: number;
  newFindings: number;
}

export interface DraftingSettings {
  outlookDrafts: boolean;
  staleDays: number;
  allowedByOrganisation: boolean;
}

export interface QueueItem {
  conversationId: string;
  subject: string | null;
  sender: PersonRef;
  receivedAt: string;
  needsReply: boolean;
  reason: string;
  excluded: boolean;
  excludedBy: string | null;
  ccOnly: boolean;
  draft: {
    id: string;
    createdAt: string;
    placed: boolean;
    placedState: string | null;
    webLink: string | null;
    outcome: string | null;
    matchState: string;
    blocked: boolean;
  } | null;
}

export interface QueueView {
  items: QueueItem[];
  settings: DraftingSettings;
  sourceKind: "graph" | "sample";
}

export interface Prepared {
  draft: Draft;
  placed: boolean;
  webLink: string | null;
  notPlacedReason: "off" | "organisation_off" | "blocked" | "not_saved" | null;
}

export type RuleStatus = "candidate" | "active" | "confirmed" | "rejected";

export interface LearnedRule {
  id: string;
  scope: string;
  kind: "greeting" | "sign_off" | "length" | "avoid" | "prefer" | "exclamations";
  value: string;
  text: string;
  status: RuleStatus;
  evidence: number;
  contradictions: number;
  support: number | null;
  lastSeen: string;
}

export interface EditSummary {
  matched: number;
  sent_as_is?: number;
  light_edit?: number;
  heavy_edit?: number;
  rewritten?: number;
  sendWithoutEditRate?: number;
  lightEditRate?: number;
  medianEditShare?: number;
  byRelationship?: Record<string, { matched: number; sendWithoutEditRate: number }>;
  drafts: Record<string, number>;
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
  setTone = (bucket: Bucket, key: string, tone: ToneGroup | null) =>
    this.request<void>("PUT", "/api/persona/tones", { bucket, key, tone });
  savePersonaSettings = (settings: PersonaSettings) =>
    this.request<PersonaSettings>("PUT", "/api/persona/settings", settings);
  sampleWorkspace = () => this.request<SampleWorkspace>("GET", "/api/sample/workspace");

  draftingStatus = () => this.request<DraftingStatus>("GET", "/api/drafting/status");
  draftingThreads = () => this.request<DraftThread[]>("GET", "/api/drafting/threads");
  draftingThread = (conversationId: string) =>
    this.request<ThreadView>("GET", `/api/drafting/thread?conversationId=${encodeURIComponent(conversationId)}`);
  draftingChats = () => this.request<DraftChat[]>("GET", "/api/drafting/chats");
  draftingChat = (chatId: string) =>
    this.request<ChatView>("GET", `/api/drafting/chat?chatId=${encodeURIComponent(chatId)}`);
  createDraft = (req: DraftRequest) => this.request<Draft>("POST", "/api/drafts", req);
  checkText = (
    body: string,
    to: PersonRef[],
    cc: PersonRef[] = [],
    conversationId: string | null = null,
    channel: "email" | "chat" = "email",
  ) =>
    this.request<{ checks: DraftCheck[]; insertAllowed: boolean }>("POST", "/api/drafts/check", {
      body,
      to,
      cc,
      conversationId,
      channel,
    });
  drafts = () => this.request<DraftSummary[]>("GET", "/api/drafts");
  draftFeedback = (id: string, feedback: { outcome?: DraftOutcome; rating?: "good" | "bad" }) =>
    this.request<void>("POST", `/api/drafts/${encodeURIComponent(id)}/feedback`, feedback);

  queue = () => this.request<QueueView>("GET", "/api/queue");
  prepare = (conversationId: string, instruction: string | null = null) =>
    this.request<Prepared>("POST", "/api/queue/prepare", { conversationId, instruction });
  dismiss = (conversationId: string) => this.request<void>("POST", "/api/queue/dismiss", { conversationId });
  tidy = () => this.request<Record<string, number>>("POST", "/api/queue/tidy");
  draftingSettings = () => this.request<DraftingSettings>("GET", "/api/drafting/settings");
  saveDraftingSettings = (outlookDrafts: boolean, staleDays: number) =>
    this.request<DraftingSettings>("PUT", "/api/drafting/settings", { outlookDrafts, staleDays });
  placeDraft = (id: string, text: string, confirmed = false) =>
    this.request<{ placed: boolean; webLink: string | null }>("POST", `/api/drafts/${encodeURIComponent(id)}/place`, {
      text,
      confirmed,
    });
  markSent = (id: string, text: string) =>
    this.request<{ outcome: string; editShare: number; edits: string[] }>(
      "POST",
      `/api/drafts/${encodeURIComponent(id)}/sent`,
      { text },
    );
  syncEdits = () =>
    this.request<{ matched: number; unmatched: number; excluded: number; superseded: number; pending: number; skipped: boolean }>(
      "POST",
      "/api/edits/sync",
    );
  editSummary = () => this.request<EditSummary>("GET", "/api/edits/summary");
  learnedRules = () => this.request<LearnedRule[]>("GET", "/api/rules");
  decideRule = (id: string, decision: "keep" | "reject") =>
    this.request<LearnedRule>("PUT", `/api/rules/${encodeURIComponent(id)}`, { decision });

  commitments = (status: "open" | "done" | "dismissed" | "all" = "open") =>
    this.request<Ledger>("GET", `/api/commitments?status=${status}`);
  scanCommitments = () => this.request<CommitmentScan>("POST", "/api/commitments/scan");
  decideCommitment = (id: string, action: "done" | "dismiss" | "reopen" | "snooze", days = 1) =>
    this.request<void>("PUT", `/api/commitments/${encodeURIComponent(id)}`, { action, days });
  followUp = (id: string, kind: FollowUpKind, newDate: string | null = null, note: string | null = null) =>
    this.request<Draft>("POST", `/api/commitments/${encodeURIComponent(id)}/follow-up`, { kind, newDate, note });

  meetings = () => this.request<MeetingList>("GET", "/api/meetings");
  scanMeetings = () => this.request<MeetingScan>("POST", "/api/meetings/scan");
  meeting = (id: string) => this.request<MeetingDetail>("GET", `/api/meetings/${encodeURIComponent(id)}`);
  askMeetings = (question: string, meetingId: string | null = null) =>
    this.request<MeetingAnswer>("POST", "/api/meetings/ask", { question, meetingId });
  decideNote = (id: string, action: "dismiss" | "restore") =>
    this.request<void>("PUT", `/api/meetings/notes/${encodeURIComponent(id)}`, { action });
  correctSpeaker = (meetingId: string, fromId: string, toId: string | null) =>
    this.request<void>("PUT", `/api/meetings/${encodeURIComponent(meetingId)}/speakers`, { fromId, toId });
  forgetMeeting = (id: string) => this.request<void>("DELETE", `/api/meetings/${encodeURIComponent(id)}`);
  meetingHealth = () => this.request<MeetingHealth>("GET", "/api/admin/meetings/health");

  backstops = () => this.request<BackstopStatus>("GET", "/api/admin/backstops");
  probeBackstops = () => this.request<BackstopProbe[]>("POST", "/api/admin/backstops/probe");
  exportSnapshots = () => this.request<SnapshotExport>("POST", "/api/admin/backstops/snapshots");
  resumePipeline = () => this.request<{ resumed: boolean }>("POST", "/api/admin/backstops/resume");
  purgeFlagged = (eventId: number) =>
    this.request<{ removed: number }>("POST", `/api/admin/backstops/events/${eventId}/purge`);
  setMeetingsPolicy = (meetingMemory: boolean) =>
    this.request<Scoping>("PUT", "/api/admin/scoping/meetings", { meetingMemory });

  notifications = () => this.request<{ items: AppNotification[]; unread: number }>("GET", "/api/notifications");
  markNotificationsRead = (id: string | null = null) => this.request<void>("POST", "/api/notifications/read", { id });

  teamsConfig = () => this.request<TeamsConfig>("GET", "/api/teams/config");
  teamsDialog = (handle: string) => this.request<TeamsDialogTarget>("POST", "/api/teams/dialog", { handle });

  scoping = () => this.request<Scoping>("GET", "/api/admin/scoping");
  setTeamsPolicy = (teamsPrefill: boolean, teamsNotifications: boolean) =>
    this.request<Scoping>("PUT", "/api/admin/scoping/teams", { teamsPrefill, teamsNotifications });
  setExternalMode = (externalMode: Scoping["externalMode"]) =>
    this.request<Scoping>("PUT", "/api/admin/scoping/policy", { externalMode });
  addAccount = (account: { name: string; mode: ClientAccount["mode"]; domains: string[]; sensitiveWords: string[] }) =>
    this.request<Scoping>("POST", "/api/admin/scoping/accounts", account);
  setServerDrafts = (serverDrafts: boolean) => this.request<Scoping>("PUT", "/api/admin/scoping/drafts", { serverDrafts });
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
