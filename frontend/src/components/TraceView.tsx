import { useState } from "react";
import {
  ChevronDown,
  ChevronRight,
  GitBranch,
  Scissors,
  Activity,
  AlertOctagon,
} from "lucide-react";
import type { TraceData, TraceFrame } from "../types";
import CodeView from "./CodeView";

function frameLabel(f: TraceFrame) {
  const file = f.file.split("/").pop()?.split("\\").pop() || f.file;
  return `${f.func}() — ${file}:${f.line}`;
}

function toFrames(trace: TraceData | TraceFrame[] | null | undefined): {
  frames: TraceFrame[];
  data?: TraceData;
} {
  if (!trace) return { frames: [] };
  if (Array.isArray(trace)) return { frames: trace }; // legacy shape
  return { frames: trace.frames || [], data: trace };
}

export default function TraceView({ trace }: { trace: TraceData | TraceFrame[] | null | undefined }) {
  const [open, setOpen] = useState<number | null>(null);
  const { frames, data } = toFrames(trace);
  const slice = data?.slice;
  const summary = data?.summary;

  if (!frames.length) {
    return <p className="text-xs text-faint">No runtime trace captured.</p>;
  }

  return (
    <div className="space-y-2.5">
      {/* failure-slice banner */}
      {slice && slice.path.length > 0 && (
        <div className="rounded-md border border-accent/30 bg-accent/5 px-3 py-2">
          <div className="flex items-center gap-1.5 text-[10.5px] uppercase tracking-wide text-accent mb-1.5">
            <Scissors size={11} /> failure slice
          </div>
          <div className="flex flex-wrap items-center gap-1 text-[11px] mono">
            {slice.path.map((p, i) => (
              <span key={i} className="flex items-center gap-1">
                {i > 0 && <span className="text-faint/50">→</span>}
                <span className={`rounded border px-1.5 py-0.5 ${i === slice.path.length - 1 ? "border-bad/40 bg-bad/10 text-bad" : "border-border bg-panel2/60 text-ink/80"}`}>
                  {p}
                </span>
              </span>
            ))}
          </div>
          <div className="mt-1.5 flex flex-wrap gap-x-3 gap-y-0.5 text-[10.5px] text-faint mono">
            <span>{slice.frames} frame(s) · {slice.events} event(s)</span>
            <span>max depth {slice.max_depth}</span>
            {summary?.branches != null && <span>{summary.branches} branch(es)</span>}
            {summary?.calls != null && <span>{summary.calls} call(s)</span>}
            {summary?.truncated && (
              <span className="text-warn flex items-center gap-1">
                <AlertOctagon size={10} /> trace capped
              </span>
            )}
          </div>
        </div>
      )}

      <div className="space-y-1">
        {frames.map((f, i) => {
          const isOpen = open === i;
          const isLast = i === frames.length - 1;
          const pad = Math.min((f.depth || 0) * 14, 56);
          return (
            <div key={i}>
              <button
                onClick={() => setOpen(isOpen ? null : i)}
                style={{ paddingLeft: 10 + pad }}
                className={`w-full text-left flex items-center gap-2 px-2.5 py-1.5 rounded text-[12.5px] font-mono border ${
                  isOpen
                    ? "bg-accent/10 border-accent/30"
                    : f.in_slice
                    ? "bg-accent/5 border-accent/20 hover:border-accent/50"
                    : "bg-panel2/60 border-border hover:border-faint"
                } ${isLast ? "text-bad" : "text-ink"}`}
              >
                {isOpen ? <ChevronDown size={13} /> : <ChevronRight size={13} />}
                <span className="text-faint shrink-0">#{i + 1}</span>
                {f.in_slice && (
                  <span className="shrink-0 rounded border border-accent/40 bg-accent/10 px-1 text-[9px] text-accent">
                    SLICE
                  </span>
                )}
                <span className="flex-1 truncate">{frameLabel(f)}</span>
                {f.duration_ms != null && (
                  <span className="text-[10px] text-faint shrink-0">{(f.duration_ms / 1000).toFixed(4)}s</span>
                )}
                {isLast && <span className="text-[10px] text-bad shrink-0">❌</span>}
              </button>
              {isOpen && (
                <div className="mt-1 ml-4 border-l border-border pl-3 space-y-2 pb-1">
                  <div className="grid grid-cols-2 gap-x-4 gap-y-0.5 text-[11.5px]">
                    <KV k="function" v={f.func} />
                    <KV k="module" v={f.module || "—"} />
                    <KV k="file" v={f.file} />
                    <KV k="line" v={String(f.line)} />
                    <KV k="depth" v={f.depth != null ? String(f.depth) : "—"} />
                    <KV k="duration" v={f.duration_ms != null ? `${(f.duration_ms / 1000).toFixed(4)}s` : "—"} />
                  </div>
                  {f.args && Object.keys(f.args).length > 0 && (
                    <div className="text-[11.5px]">
                      <div className="text-faint mb-0.5">arguments</div>
                      {Object.entries(f.args).map(([k, v]) => (
                        <div key={k} className="mono flex gap-2">
                          <span className="text-vio shrink-0">{k} =</span>
                          <span className="text-ink/80 break-all">{v}</span>
                        </div>
                      ))}
                    </div>
                  )}
                  {f.return_value != null && (
                    <KV k="returned" v={String(f.return_value)} />
                  )}
                  {f.state_changes && Object.keys(f.state_changes).length > 0 && (
                    <div className="text-[11.5px]">
                      <div className="text-warn mb-0.5 flex items-center gap-1">
                        <Activity size={10} /> state changes (call → failure)
                      </div>
                      {Object.entries(f.state_changes).map(([k, v]) => (
                        <div key={k} className="mono flex gap-2">
                          <span className="text-warn shrink-0">{k} ⇒</span>
                          <span className="text-ink/80 break-all">{v}</span>
                        </div>
                      ))}
                    </div>
                  )}
                  {f.branches && f.branches.length > 0 && (
                    <div className="text-[11.5px]">
                      <div className="text-faint mb-0.5 flex items-center gap-1">
                        <GitBranch size={10} /> branch decisions
                      </div>
                      <div className="flex flex-wrap gap-1">
                        {f.branches.map((b, bi) => (
                          <span key={bi} className="mono rounded border border-border bg-panel2/60 px-1.5 py-0.5 text-faint">
                            {b.from} → {b.to}
                          </span>
                        ))}
                      </div>
                    </div>
                  )}
                  {f.locals && Object.keys(f.locals).length > 0 && (
                    <div className="text-[11.5px]">
                      <div className="text-bad mb-0.5 flex items-center gap-1">
                        <AlertOctagon size={10} /> values at failure
                      </div>
                      {Object.entries(f.locals).map(([k, v]) => (
                        <div key={k} className="mono flex gap-2">
                          <span className="text-bad/80 shrink-0">{k} =</span>
                          <span className="text-ink/80 break-all">{v}</span>
                        </div>
                      ))}
                    </div>
                  )}
                  {f.exception && (
                    <div className="text-[11.5px] text-bad mono">raised: {f.exception}</div>
                  )}
                  {f.source && f.source.length > 0 && (
                    <div className="rounded-md border border-border overflow-hidden">
                      <CodeView
                        source={f.source.map((s) => s.text).join("\n")}
                        startLine={f.source[0].line}
                        failingLine={f.line}
                      />
                    </div>
                  )}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

function KV({ k, v }: { k: string; v: string }) {
  return (
    <div className="flex gap-1.5 min-w-0">
      <span className="text-faint shrink-0">{k}:</span>
      <span className="text-ink/85 truncate">{v}</span>
    </div>
  );
}
