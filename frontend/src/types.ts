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
}

export interface Verification {
  before?: any;
  after?: any;
  full?: any;
  passed: boolean;
}

export interface TraceFrame {
  func: string;
  file: string;
  line: number;
  args?: Record<string, string>;
  return_value?: string | null;
  exec_time?: number | null;
  exception?: string | null;
  source?: { line: number; text: string; failing?: boolean }[];
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
  trace?: TraceFrame[];
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
};

export const STATUS_COLOR: Record<string, string> = {
  created: "text-muted border-border",
  running: "text-accent border-accent/40",
  investigating: "text-warn border-warn/40",
  fixed: "text-good border-good/40",
  failed: "text-bad border-bad/40",
  "no-failure": "text-muted border-border",
};
