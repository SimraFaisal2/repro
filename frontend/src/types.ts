export interface Project {
  id: string;
  name: string;
  source_type: string;
  source_url?: string;
  local_path: string;
  overview?: Overview | null;
  created_at: number;
}

export interface Overview {
  language: string;
  python_version: string;
  framework: string;
  package_manager: string;
  test_framework: string;
  files: number;
  python_files: number;
  tests_files: number;
  dependencies: string[];
  dependencies_count: number;
  has_requirements: boolean;
  tree: string[];
  graph: { modules: string[]; edges: [string, string][] };
  root: string;
}

export interface TestRun {
  stage: string;
  total: number;
  passed: number;
  failed: number;
  skipped: number;
  duration: number;
  output?: string;
}

export interface Failure {
  test_id: string;
  error_type: string;
  error_msg: string;
  file: string;
  line: number | null;
  severity: string;
  stack_trace: string;
  reproducible: boolean;
}

export interface AgentStep {
  ts: number;
  message: string;
  kind: string;
}

export interface PatchCheck {
  id: string;
  name: string;
  status: "pass" | "fail" | "skip";
  detail: string;
}

export interface PatchReport {
  root_cause: string;
  explanation: string;
  files: string[];
  files_changed: number;
  lines_added: number;
  lines_removed: number;
  tests_affected: string[];
  tests_before: { passed: number; failed: number; total: number; failed_ids?: string[] };
  tests_after: { passed: number; failed: number; total: number; failed_ids?: string[] };
  regression_status: string;
  regression_new: string[];
  patch_confidence: number | null;
  risk: string;
  checks: PatchCheck[];
}

export interface Patch {
  id?: string;
  diff: string;
  files_changed: number;
  lines_added: number;
  lines_removed: number;
  risk: string;
  confidence: number | null;
  reason: string;
  status: string;
  applied: boolean;
  branch?: string;
  checks?: PatchCheck[];
  report?: PatchReport | null;
}

export interface Verification {
  before?: any;
  after?: any;
  full?: any;
  passed: boolean;
}

export interface TraceBranch {
  from: number;
  to: number;
}

export interface TraceFrame {
  func: string;
  module?: string;
  file: string;
  line: number;
  depth?: number | null;
  call_id?: number | null;
  parent_id?: number | null;
  args?: Record<string, string>;
  return_value?: string | null;
  duration_ms?: number | null;
  exec_time?: number | null;
  exception?: string | null;
  exc_type?: string;
  exc_msg?: string;
  locals?: Record<string, string>;
  state_changes?: Record<string, string>;
  branches?: TraceBranch[];
  in_slice?: boolean;
  traced?: boolean;
  source?: { line: number; text: string; failing?: boolean }[];
}

export interface TraceSlice {
  path: string[];
  events: number;
  frames: number;
  max_depth: number;
}

export interface TraceSummary {
  calls: number;
  branches: number;
  max_depth: number;
  truncated: boolean;
}

export interface TraceData {
  schema?: number;
  frames: TraceFrame[];
  slice?: TraceSlice;
  summary?: TraceSummary;
}

export interface Hypothesis {
  root_cause: string;
  explanation: string;
  confidence: number;
  risk: string;
  rule: string;
  evidence: { kind: string; source: string; text: string }[];
  related_tests?: string[];
  severity?: string;
}

export interface DebugHypothesis {
  rule: string;
  root_cause: string;
  confidence: number | null;
  result: string;
}

export interface DebugPatch {
  rule: string;
  risk: string;
  status: string;
  result: string;
  lines_added: number;
  lines_removed: number;
}

export interface DebugLoop {
  type: string;
  detail: string;
  iteration: number;
}

export interface DebugStateMachine {
  state: string;
  iteration: number;
  budget: number;
  strategy: string;
  termination: string;
  loops: DebugLoop[];
  hypotheses: DebugHypothesis[];
  patches: DebugPatch[];
  failures: { test_id: string; error_type: string; error_msg: string }[];
  evidence_sets: number;
}

export interface Investigation {
  id: string;
  project_id: string;
  status: string;
  branch?: string | null;
  attempts: number;
  confidence?: number | null;
  summary?: any;
  test_runs: TestRun[];
  failures: Failure[];
  steps: AgentStep[];
  patches: Patch[];
  verifications: Verification[];
  created_at: number;
  updated_at: number;
}

export interface EventPayload {
  type: string;
  message?: string;
  kind?: string;
  status?: string;
  failure?: Failure;
  trace?: TraceData | TraceFrame[];
  hypothesis?: Hypothesis;
  patch?: Patch;
  verification?: Verification;
}

export const STATUS_LABEL: Record<string, string> = {
  created: "Queued",
  running: "Running",
  investigating: "Investigating",
  fixed: "✓ Verified",
  failed: "✗ Not fixed",
  "no-failure": "No failure",
  "needs-approval": "⚠ Needs approval",
};

export const STATUS_COLOR: Record<string, string> = {
  created: "text-muted border-border",
  running: "text-accent border-accent/40",
  investigating: "text-warn border-warn/40",
  fixed: "text-good border-good/40",
  failed: "text-bad border-bad/40",
  "no-failure": "text-muted border-border",
  "needs-approval": "text-warn border-warn/40",
};
