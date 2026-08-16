import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { ArrowRight, Bug, FlaskConical, FolderGit2, ScanSearch } from "lucide-react";
import { api } from "../api";

const LIFECYCLE = ["REPRODUCE", "INVESTIGATE", "DIAGNOSE", "PATCH", "VERIFY"];

const DEMOS = [
  { key: "auth", label: "Null / None handling" },
  { key: "offbyone", label: "Off-by-one error" },
  { key: "api", label: "API response handling" },
  { key: "sql", label: "Incorrect SQL column" },
  { key: "auth2", label: "Authentication logic" },
];

export default function Landing() {
  const nav = useNavigate();
  const [busy, setBusy] = useState(false);

  async function tryDemo(bug: string) {
    setBusy(true);
    try {
      const res = await api.runDemo(bug);
      await api.runInvestigation(res.investigation.id);
      nav(`/investigation/${res.investigation.id}`);
    } finally {
      setBusy(false);
    }
  }

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
          <button className="btn-primary" disabled={busy} onClick={() => tryDemo("auth")}>
            <FlaskConical size={15} /> Try Demo
          </button>
          <button className="btn-ghost" onClick={() => nav("/dashboard")}>
            <FolderGit2 size={15} /> Analyze Repository
          </button>
        </div>
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


