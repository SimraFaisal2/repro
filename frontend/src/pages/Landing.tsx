import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  ArrowRight,
  Bug,
  Check,
  FlaskConical,
  FolderGit2,
  Microscope,
  Play,
  ScanSearch,
  ShieldCheck,
  Wand2,
  X,
} from "lucide-react";
import { api } from "../api";
import type { AgentStep, EventPayload, Failure, Hypothesis, Patch, Project, Verification } from "../types";
import { STATUS_COLOR, STATUS_LABEL } from "../types";
import { Panel, Spinner } from "../components/Panel";
import ActivityLog from "../components/ActivityLog";
import DiffView from "../components/DiffView";

const LIFECYCLE = ["REPRODUCE", "INVESTIGATE", "DIAGNOSE", "PATCH", "VERIFY"];

// Agent phases, ordered. The first not-yet-reached phase is the active one.
const PHASES = [
  { key: "analyze", label: "Analyze", icon: ScanSearch },
  { key: "reproduce", label: "Reproduce", icon: FlaskConical },
  { key: "investigate", label: "Investigate", icon: Microscope },
  { key: "diagnose", label: "Diagnose", icon: Bug },
  { key: "patch", label: "Patch", icon: Wand2 },
  { key: "verify", label: "Verify", icon: ShieldCheck },
];

const PHASE_KEYWORDS: Record<string, string[]> = {
  analyze: ["Analyzing repository", "Project:"],
  reproduce: ["Running test suite (baseline)", "Baseline:", "Failure reproduced", "tests discovered"],
  investigate: ["Runtime trace captured"],
  diagnose: ["Root cause hypothesis"],
  patch: ["Patch generated", "LLM patch verified"],
  verify: ["fix verified in sandbox", "Full suite green", "Reached 3 autonomous"],
};

function phaseOf(msg: string): string | null {
  for (const [phase, kws] of Object.entries(PHASE_KEYWORDS)) {
    for (const kw of kws) if (msg.includes(kw)) return phase;
  }
  return null;
}

const TERMINAL = new Set(["fixed", "failed", "no-failure"]);

const DEMOS = [
  { key: "auth", label: "Null / None handling" },
  { key: "offbyone", label: "Off-by-one error" },
  { key: "api", label: "API response handling" },
  { key: "sql", label: "Incorrect SQL column" },
  { key: "auth2", label: "Authentication logic" },
];

interface DemoState {
  id: string;
  project: Project;
  status: string;
  steps: AgentStep[];
  failures: Failure[];
  hypothesis: Hypothesis | null;
  patch: Patch | null;
  verification: Verification | null;
}

export default function Landing() {
  const nav = useNavigate();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [demo, setDemo] = useState<DemoState | null>(null);
  const panelRef = useRef<HTMLDivElement>(null);

  async function tryDemo(bug: string) {
    setBusy(true);
    setError("");
    try {
      const res = await api.runDemo(bug);
      await api.runInvestigation(res.investigation.id);
      setDemo({
        id: res.investigation.id,
        project: res.project,
        status: "running",
        steps: [],
        failures: [],
        hypothesis: null,
        patch: null,
        verification: null,
      });
      setTimeout(() => panelRef.current?.scrollIntoView({ behavior: "smooth", block: "start" }), 60);
    } catch (e: any) {
      setError(e?.message || "demo failed to start");
    } finally {
      setBusy(false);
    }
  }

  // Stream the running investigation live into the page. On stream close,
  // re-fetch the authoritative state from the DB so a dropped SSE event can
  // never leave the demo stuck at "running" without a verdict.
  useEffect(() => {
    if (!demo) return;
    const id = demo.id;
    const sync = async () => {
      try {
        const inv = await api.getInvestigation(id);
        setDemo((prev) =>
          prev && prev.id === id
            ? {
                ...prev,
                status: inv.status,
                steps: inv.steps.length ? inv.steps : prev.steps,
                failures: inv.failures.length ? inv.failures : prev.failures,
                hypothesis: inv.summary?._hypothesis ?? prev.hypothesis,
                patch: inv.patches?.[inv.patches.length - 1] ?? prev.patch,
                verification: inv.verifications?.[inv.verifications.length - 1] ?? prev.verification,
              }
            : prev
        );
      } catch {
        /* keep streamed state */
      }
    };
    const es = new EventSource(api.eventsUrl(id));
    es.onmessage = (e) => {
      let p: EventPayload;
      try {
        p = JSON.parse(e.data);
      } catch {
        return;
      }
      if (p.type === "__close__") {
        es.close();
        sync();
        return;
      }
      if (p.type === "step") {
        setDemo((prev) =>
          prev
            ? { ...prev, steps: [...prev.steps, { ts: Date.now() / 1000, message: p.message!, kind: p.kind! }] }
            : prev
        );
      }
      if (p.type === "status") setDemo((prev) => (prev ? { ...prev, status: p.status! } : prev));
      if (p.type === "failure")
        setDemo((prev) =>
          prev && p.failure
            ? { ...prev, failures: [...prev.failures.filter((f) => f.test_id !== p.failure!.test_id), p.failure] }
            : prev
        );
      if (p.type === "hypothesis") setDemo((prev) => (prev ? { ...prev, hypothesis: p.hypothesis || null } : prev));
      if (p.type === "patch") setDemo((prev) => (prev ? { ...prev, patch: p.patch || null } : prev));
      if (p.type === "verification")
        setDemo((prev) => (prev ? { ...prev, verification: p.verification || null } : prev));
      if (p.type === "done") {
        es.close();
        sync();
      }
    };
    es.onerror = () => {
      /* transient — EventSource reconnects */
    };
    return () => es.close();
  }, [demo?.id]);

  const steps = demo?.steps || [];
  const donePhases = new Set<string>();
  for (const s of steps) {
    const ph = phaseOf(s.message);
    if (ph) donePhases.add(ph);
  }
  const activePhaseIdx = PHASES.findIndex((p) => !donePhases.has(p.key));
  const running = demo !== null && !TERMINAL.has(demo.status);
  const done = demo !== null && TERMINAL.has(demo.status);
  const fixed = demo?.status === "fixed";
  const failed = demo?.status === "failed";

  return (
    <div className="max-w-3xl mx-auto pt-16 pb-24">
      <div className="text-center space-y-6">
        <div className="inline-flex items-center gap-2 rounded-full border border-accent/30 bg-accent/10 px-3 py-1 text-[11px] text-accent font-mono">
          <Bug size={12} /> AI software investigator
        </div>
        <h1 className="text-5xl sm:text-6xl font-bold tracking-tight">
          REPRO
          <span className="block text-lg sm:text-xl font-normal text-muted mt-4 max-w-xl mx-auto leading-relaxed">
            It doesn't just tell you what's broken. It{" "}
            <span className="text-ink">reproduces</span> the failure,{" "}
            <span className="text-ink">finds</span> the cause,{" "}
            <span className="text-ink">fixes</span> it, and{" "}
            <span className="text-ink">proves the fix works</span>.
          </span>
        </h1>
        <div className="flex items-center justify-center gap-3 pt-2">
          <button className="btn-primary !px-6 !py-2.5 text-base" disabled={busy} onClick={() => tryDemo("auth")}>
            <Play size={16} /> Try REPRO
          </button>
          <button className="btn-ghost" onClick={() => nav("/dashboard")}>
            <FolderGit2 size={15} /> Analyze Repository
          </button>
        </div>
        <p className="text-[11px] text-faint mono">
          no setup · no API keys · runs a real investigation on a bundled broken repo
        </p>
      </div>

      <div className="mt-16">
        <div className="flex items-center justify-center gap-2 sm:gap-3 flex-wrap">
          {LIFECYCLE.map((step, i) => (
            <div key={step} className="flex items-center gap-2 sm:gap-3">
              <span className="px-3 py-1.5 rounded-md border border-border bg-panel text-[11px] font-mono tracking-wider text-muted">
                {step}
              </span>
              {i < LIFECYCLE.length - 1 && <ArrowRight size={13} className="text-faint" />}
            </div>
          ))}
        </div>
      </div>

      {error && (
        <div className="mt-8 flex items-center justify-center gap-2 rounded-md border border-bad/40 bg-bad/10 px-4 py-2.5 text-sm text-bad">
          <X size={14} /> {error}
          <button onClick={() => setError("")} className="ml-2 text-faint hover:text-ink">
            <X size={13} />
          </button>
        </div>
      )}

      {/* ---------- live demo panel ---------- */}
      {demo && (
        <div ref={panelRef} className="mt-10 space-y-5">
          {/* verdict banner (when finished) */}
          {done && (
            <div
              className={`rounded-md border px-4 py-3 text-sm ${
                fixed
                  ? "border-good/40 bg-good/10 text-good"
                  : failed
                  ? "border-bad/40 bg-bad/10 text-bad"
                  : "border-border bg-panel text-muted"
              }`}
            >
              <div className="flex flex-wrap items-center gap-3">
                <span className="font-semibold">
                  {fixed ? "✓ Fixed — verified in the sandbox" : failed ? "✗ Not fixed — the agent stopped and explained why" : "No failure detected"}
                </span>
                <span className={`ml-auto inline-flex items-center gap-1.5 text-[11px] rounded-full border px-2 py-0.5 ${STATUS_COLOR[demo.status] || STATUS_COLOR.created}`}>
                  {STATUS_LABEL[demo.status] || demo.status}
                </span>
              </div>
              <div className="mt-2 flex flex-wrap items-center gap-4 text-xs text-ink/70">
                {demo.verification && (
                  <span>
                    tests: <span className="text-good">{demo.verification.after?.passed ?? 0} passed</span>
                    {" / "}
                    <span className="text-bad">{demo.verification.after?.failed ?? 0} failed</span>
                  </span>
                )}
                {demo.hypothesis && demo.hypothesis.confidence != null && (
                  <span>
                    confidence <span className="text-accent">{(demo.hypothesis.confidence * 100).toFixed(0)}%</span>
                  </span>
                )}
                {demo.patch && (
                  <span>
                    patch <span className="text-good">+{demo.patch.lines_added}</span>
                    <span className="text-bad">-{demo.patch.lines_removed}</span> · {demo.patch.files_changed} file(s)
                  </span>
                )}
              </div>
              <button className="btn-primary mt-3" onClick={() => nav(`/investigation/${demo.id}`)}>
                <FlaskConical size={14} /> Open full investigation
              </button>
            </div>
          )}

          {/* phase stepper */}
          <div className="panel px-4 py-3">
            <div className="flex items-center gap-1 overflow-x-auto">
              {PHASES.map((ph, i) => {
                const Icon = ph.icon;
                const isDone = donePhases.has(ph.key);
                const isActive = i === activePhaseIdx && running;
                const color = isDone
                  ? "text-good border-good/40 bg-good/10"
                  : isActive
                  ? "text-accent border-accent/40 bg-accent/10 pulse-dot"
                  : "text-faint border-border bg-panel2/40";
                return (
                  <div key={ph.key} className="flex items-center gap-1 shrink-0">
                    <span className={`flex items-center gap-1.5 px-2.5 py-1 rounded-md border text-[11px] font-mono ${color}`}>
                      <Icon size={12} /> {ph.label}
                      {isDone && <Check size={11} />}
                    </span>
                    {i < PHASES.length - 1 && <span className="text-faint/50">→</span>}
                  </div>
                );
              })}
              {running && (
                <span className="ml-2">
                  <Spinner label="agent working" />
                </span>
              )}
            </div>
          </div>

          {/* live failure → root cause → patch → verify */}
          <div className="grid grid-cols-1 xl:grid-cols-2 gap-5">
            <div className="space-y-5 min-w-0">
              <Panel title="Failure detected">
                {demo.failures[0] ? (
                  <div className="space-y-2">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="mono text-[12px] text-bad bg-bad/10 border border-bad/30 rounded px-2 py-0.5">
                        {demo.failures[0].test_id}
                      </span>
                      <span className="text-[11px] mono text-bad">{demo.failures[0].error_type}</span>
                      <span className="text-[11px] mono text-faint">
                        {demo.failures[0].file}:{demo.failures[0].line}
                      </span>
                    </div>
                    <p className="text-sm text-ink/90 font-mono">{demo.failures[0].error_msg}</p>
                  </div>
                ) : running ? (
                  <Spinner label="running tests…" />
                ) : (
                  <p className="text-xs text-faint">No failure.</p>
                )}
              </Panel>

              <Panel title="Root cause">
                {demo.hypothesis ? (
                  <div className="space-y-2">
                    <div className="text-sm text-ink">{demo.hypothesis.root_cause}</div>
                    <p className="text-[12.5px] text-ink/70 leading-relaxed">{demo.hypothesis.explanation}</p>
                  </div>
                ) : running ? (
                  <Spinner label="analyzing evidence…" />
                ) : (
                  <p className="text-xs text-faint">No hypothesis.</p>
                )}
              </Panel>
            </div>

            <div className="space-y-5 min-w-0">
              <Panel
                title="Proposed fix"
                right={demo.patch ? <span className="mono text-[11px] text-faint">+{demo.patch.lines_added}/-{demo.patch.lines_removed}</span> : undefined}
              >
                {demo.patch ? (
                  <div className="space-y-2">
                    {demo.patch.reason && <p className="text-[12.5px] text-ink/75">{demo.patch.reason}</p>}
                    <DiffView diff={demo.patch.diff} />
                  </div>
                ) : running ? (
                  <Spinner label="generating patch…" />
                ) : (
                  <p className="text-xs text-faint">No patch.</p>
                )}
              </Panel>

              <Panel title="Verification">
                {demo.verification ? (
                  <div className="grid grid-cols-2 gap-3">
                    <div className="rounded-md border border-border p-3">
                      <div className="text-[11px] uppercase text-faint mb-1">before fix</div>
                      <div className="mono text-lg">{demo.verification.before?.passed ?? 0} <span className="text-good">passed</span></div>
                      <div className="mono text-sm">{demo.verification.before?.failed ?? 0} <span className="text-bad">failed</span></div>
                    </div>
                    <div className="rounded-md border border-border p-3">
                      <div className="text-[11px] uppercase text-faint mb-1">after fix</div>
                      <div className="mono text-lg">{demo.verification.after?.passed ?? 0} <span className="text-good">passed</span></div>
                      <div className="mono text-sm">{demo.verification.after?.failed ?? 0} <span className="text-bad">failed</span></div>
                    </div>
                  </div>
                ) : running ? (
                  <Spinner label="verifying fix…" />
                ) : (
                  <p className="text-xs text-faint">No verification yet.</p>
                )}
              </Panel>
            </div>
          </div>

          {/* agent activity */}
          <Panel title="Agent activity" right={running ? <Spinner /> : <span className="mono text-[11px] text-faint">{steps.length} steps</span>}>
            <ActivityLog steps={steps} live={running} />
          </Panel>
        </div>
      )}

      <div className="mt-16 panel">
        <header className="panel-head">
          <span>Bundled demo repositories</span>
          <ScanSearch size={13} className="text-faint" />
        </header>
        <div className="divide-y divide-border">
          {DEMOS.map((d) => (
            <button
              key={d.key}
              disabled={busy}
              onClick={() => tryDemo(d.key)}
              className="w-full text-left px-4 py-3 flex items-center justify-between hover:bg-panel2/60 disabled:opacity-50 transition-colors"
            >
              <span className="text-sm text-ink/85">{d.label}</span>
              <span className="text-[11px] mono text-faint">{d.key}</span>
            </button>
          ))}
        </div>
      </div>

      <p className="mt-12 text-center text-xs text-faint leading-relaxed max-w-lg mx-auto">
        REPRO reasons over real evidence — test output, stack traces, runtime
        arguments and return values, schema, source. Every metric you see comes
        from actual execution, and fixes are only ever applied inside an
        isolated sandbox unless you explicitly approve them.
      </p>
    </div>
  );
}
