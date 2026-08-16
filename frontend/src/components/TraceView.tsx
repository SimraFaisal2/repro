import { useState } from "react";
import { ChevronDown, ChevronRight } from "lucide-react";
import type { TraceFrame } from "../types";
import CodeView from "./CodeView";

function frameLabel(f: TraceFrame) {
  const file = f.file.split("/").pop()?.split("\\").pop() || f.file;
  return `${f.func}() — ${file}:${f.line}`;
}

export default function TraceView({ trace }: { trace: TraceFrame[] }) {
  const [open, setOpen] = useState<number | null>(null);
  if (!trace.length) {
    return <p className="text-xs text-faint">No runtime trace captured.</p>;
  }
  return (
    <div className="space-y-1">
      {trace.map((f, i) => {
        const isOpen = open === i;
        const isLast = i === trace.length - 1;
        return (
          <div key={i}>
            <button
              onClick={() => setOpen(isOpen ? null : i)}
              className={`w-full text-left flex items-center gap-2 px-2.5 py-1.5 rounded text-[12.5px] font-mono border ${
                isOpen
                  ? "bg-accent/10 border-accent/30"
                  : "bg-panel2/60 border-border hover:border-faint"
              } ${isLast ? "text-bad" : "text-ink"}`}
            >
              {isOpen ? <ChevronDown size={13} /> : <ChevronRight size={13} />}
              <span className="text-faint">#{i + 1}</span>
              <span className="flex-1 truncate">{frameLabel(f)}</span>
              {f.exec_time != null && (
                <span className="text-[10px] text-faint">{f.exec_time.toFixed(4)}s</span>
              )}
              {isLast && <span className="text-[10px] text-bad">❌</span>}
            </button>
            {isOpen && (
              <div className="mt-1 ml-4 border-l border-border pl-3 space-y-2 pb-1">
                <div className="grid grid-cols-2 gap-x-4 gap-y-0.5 text-[11.5px]">
                  <KV k="function" v={f.func} />
                  <KV k="file" v={f.file} />
                  <KV k="line" v={String(f.line)} />
                  <KV k="exec time" v={f.exec_time != null ? `${f.exec_time.toFixed(4)}s` : "—"} />
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
