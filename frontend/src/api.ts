// Typed API client for Precedent — mirrors docs/API.md

let redactMode = false;

export function setRedactMode(enabled: boolean) {
  redactMode = enabled;
}

function qs(params?: Record<string, string | boolean | undefined>): string {
  const p = new URLSearchParams();
  if (redactMode) p.set('redact', '1');
  if (params) {
    for (const [k, v] of Object.entries(params)) {
      if (v !== undefined && v !== false) p.set(k, String(v));
    }
  }
  const s = p.toString();
  return s ? `?${s}` : '';
}

async function get<T>(path: string, params?: Record<string, string | boolean | undefined>): Promise<T> {
  const res = await fetch(`/api${path}${qs(params)}`);
  if (!res.ok) throw new ApiError(res.status, await res.text());
  return res.json();
}

async function post<T>(path: string, body?: unknown): Promise<T> {
  const res = await fetch(`/api${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });
  if (!res.ok) throw new ApiError(res.status, await res.text());
  return res.json();
}

export class ApiError extends Error {
  status: number;
  body: string;
  constructor(status: number, body: string) {
    super(`API ${status}: ${body}`);
    this.status = status;
    this.body = body;
  }
}

// ─── Types ───

export interface Health {
  ok: boolean;
  demo_mode: boolean;
  provider: string;
  models: Record<string, string>;
}

export interface Stats {
  emails: number;
  threads: number;
  people: number;
  candidate_threads: number;
  filtered_pct: number;
  records: number;
  decisions: number;
  decisions_by_status: Record<string, number>;
  conflicts: number;
  authority_flags: number;
  implicit: number;
  quotes_total: number;
  quotes_snapped: number;
  quotes_dropped: number;
  evidence_verified_ratio: number;
  stage_seconds: Record<string, number>;
  usage_by_stage: UsageByStage[];
  demo_mode: boolean;
}

export interface UsageByStage {
  stage: string;
  calls: number;
  tokens_in: number;
  tokens_out: number;
  cost_usd: number;
}

export interface DecisionSummary {
  decision_id: string;
  cluster_id: string;
  text: string;
  decided_by: string[];
  decided_at: string;
  status: DecisionStatus;
  decision_type: 'explicit' | 'implicit';
  authority_flag: boolean;
  cross_thread: boolean;
  confidence: number;
}

export type DecisionStatus = 'active' | 'superseded' | 'amended' | 'contested';

export interface Evidence {
  message_id: string;
  thread_id: string;
  subject: string;
  sender: string;
  sender_addr: string;
  sender_role: string;
  date: string;
  sent_at: string;
  to: string[];
  cc: string[];
  quote: string;
  role: string;
  forwarded: boolean;
  original_author?: string;
  original_date?: string;
}

export interface HistoryItem {
  decision_id: string;
  text: string;
  decided_at: string;
  status: DecisionStatus;
}

export interface Edge {
  src: string;
  dst: string;
  kind: 'supersedes' | 'amends' | 'refines';
  scope: 'full' | 'partial';
  aspect: string | null;
  rationale: string;
}

export interface DecisionDetail extends DecisionSummary {
  rationale: string | null;
  alternatives: string[];
  authority_note: string | null;
  evidence: Evidence[];
  history: HistoryItem[];
  edges: Edge[];
  topic: string;
  current_state: string;
  conflict_ids: string[];
  confidence_label: { label: string; why: string };
}

export interface ClusterSummary {
  cluster_id: string;
  topic: string;
  current_state: string;
  n_decisions: number;
  first_at: string;
  last_at: string;
  statuses: string[];
}

export interface ClusterDetail {
  cluster_id: string;
  topic: string;
  current_state: string;
  decisions: DecisionSummary[];
  edges: Edge[];
}

export interface GraphNode extends DecisionSummary {
  lane: string;
}

export interface Graph {
  nodes: GraphNode[];
  edges: Edge[];
  lanes: { cluster_id: string; topic: string }[];
}

export interface ConflictSide {
  side: string;
  claimant: string;
  claim: string;
  evidence: Evidence[];
}

export interface Conflict {
  conflict_id: string;
  cluster_id: string;
  topic: string;
  summary: string;
  decision_id: string;
  sides: ConflictSide[];
  note: string;
}

export interface Citation {
  n: number;
  message_id: string;
  quote: string;
  sender: string;
  date: string;
  subject: string;
}

export interface AskDecision {
  decision_id: string;
  canonical_text: string;
  status: DecisionStatus;
  decided_at: string;
  decision_type: string;
  authority_flag: boolean | number;
}

export interface ClosestDiscussion {
  message_id: string;
  why: string;
  sender: string;
  date: string;
  subject: string;
}

export interface AskResponse {
  question: string;
  status: 'found' | 'contested' | 'no_decision' | 'partial';
  answer_md: string;
  citations: Citation[];
  decision_ids: string[];
  decisions: AskDecision[];
  confidence: string;
  model_confidence: string;
  caveats: string[];
  closest: ClosestDiscussion[];
  question_type: string;
  verification_errors: string[];
  latency_ms: number;
}

export interface EmailDetail {
  message_id: string;
  thread_id: string;
  subject: string;
  sender: string;
  sender_addr: string;
  sender_role: string;
  date: string;
  sent_at: string;
  to: string[];
  cc: string[];
  new_text: string;
  quoted_text: string;
  fwd_text: string;
  fwd_meta: unknown;
  attachments: string[];
  thread: EmailThreadItem[];
}

export interface EmailThreadItem {
  message_id: string;
  thread_id: string;
  subject: string;
  sender: string;
  sender_addr: string;
  sender_role: string;
  date: string;
  sent_at: string;
  to: string[];
  cc: string[];
}

export interface EvalResult {
  generated_at: string;
  git_commit: string;
  banner: string;
  targets: Record<string, number>;
  global: Record<string, unknown>;
  models: Record<string, string>;
  splits: Record<string, EvalSplit>;
}

export interface EvalSplit {
  recall: number;
  precision: number;
  near_fp: number;
  near_fp_total: number;
  supersession_accuracy: number;
  conflict_detection: string;
  evidence_support: number;
  qa_accuracy: number;
  no_decision_correct: string | number;
  latency_p50_ms: number;
  quote_validity: number;
  pipeline_minutes: number;
  decisions_table: EvalDecisionRow[];
  qa: EvalQARow[];
  decision_recall?: number;
  decision_precision?: number;
  near_decision_fp?: number;
  near_decision_n?: number;
  conflicts_detected?: number;
  evidence_support_strict?: number;
  qa_n?: number;
  no_decision_n?: number;
  latency_p90_ms?: number;
  triage_recall?: number;
  status_accuracy?: number;
  [key: string]: unknown;
}

export interface EvalDecisionRow {
  gt_id: string;
  gt_text: string;
  gt_date?: string;
  gt_status?: string;
  result: string;
  pred_id?: string;
  pred_text?: string;
  pred_date?: string;
  pred_status?: string;
}

export interface EvalQARow {
  id?: string;
  question: string;
  score: number;
  status: string;
  expected_status: string;
  confidence?: string;
  latency_ms?: number;
}

export interface IngestResponse {
  run_id: string;
  files?: number;
}

export interface SSEEvent {
  event: string;
  run_id: string;
  ts: string;
  stage?: string;
  done?: number;
  total?: number;
  decision_id?: string;
  record_id?: string;
  text?: string;
  date?: string;
  status?: string;
  message?: string;
  summary?: Record<string, unknown>;
  [key: string]: unknown;
}

// ─── API functions ───

export const api = {
  health: () => get<Health>('/health'),
  stats: () => get<Stats>('/stats'),

  decisions: (params?: { status?: string; q?: string; from?: string; to?: string; cluster?: string; type?: string }) =>
    get<DecisionSummary[]>('/decisions', params),
  decision: (id: string) => get<DecisionDetail>(`/decisions/${encodeURIComponent(id)}`),
  dispute: (id: string, note: string) => post<{ ok: boolean }>(`/decisions/${encodeURIComponent(id)}/dispute`, { note }),

  clusters: () => get<ClusterSummary[]>('/clusters'),
  cluster: (id: string) => get<ClusterDetail>(`/clusters/${encodeURIComponent(id)}`),

  graph: () => get<Graph>('/graph'),

  conflicts: () => get<Conflict[]>('/conflicts'),

  email: (messageId: string) => get<EmailDetail>(`/emails/${encodeURIComponent(messageId)}`),

  ask: (question: string) => post<AskResponse>('/ask', { question }),

  evalLatest: () => get<EvalResult>('/eval/latest'),

  demoLoad: (enabled: boolean) => post<{ demo_mode: boolean }>('/demo/load', { enabled }),

  ingest: async (files: File[]) => {
    const form = new FormData();
    for (const f of files) form.append('files', f);
    const res = await fetch('/api/ingest', { method: 'POST', body: form });
    if (!res.ok) throw new ApiError(res.status, await res.text());
    return res.json() as Promise<IngestResponse>;
  },

  ingestCorpus: () => post<IngestResponse>('/ingest/corpus'),

  subscribeRun: (runId: string, onEvent: (e: SSEEvent) => void, onError?: (e: Event) => void) => {
    const es = new EventSource(`/api/runs/${encodeURIComponent(runId)}/events`);
    es.onmessage = (msg) => {
      try {
        onEvent(JSON.parse(msg.data));
      } catch { /* skip bad JSON */ }
    };
    if (onError) es.onerror = onError;
    return es;
  },
};
