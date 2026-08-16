import { useEffect, useRef } from "react";
import { Check, CircleAlert, Info, TriangleAlert } from "lucide-react";
import type { AgentStep } from "../types";

function fmt(ts: number) {
  const d = new Date(ts * 1000);
  return d.toLocaleTimeString("en-GB", { hour12: false });
}

export default function ActivityLog({ steps, live }: { steps: AgentStep[]; live: boolean }) {
  const endRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (live) endRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [steps.length, live]);

  return (
    <div className="font-mono text-[11.5px] max-h-[420px] overflow-y-auto">
      {steps.length === 0 && <p className="text-faint">Waiting for agent…</p>}
      {steps.map((s, i) => {
        const Icon =
          s.kind === "success" ? Check : s.kind === "error" ? CircleAlert : s.kind === "warn" ? TriangleAlert : Info;
        const color =
          s.kind === "success"
            ? "text-good"
            : s.kind === "error"
            ? "text-bad"
            : s.kind === "warn"
            ? "text-warn"
            : "text-muted";
        return (
          <div key={i} className="flex gap-2 py-0.5 items-start">
            <span className="text-faint shrink-0 w-16">{fmt(s.ts)}</span>
            <Icon size={12} className={`${color} shrink-0 mt-0.5`} />
            <span className={color + (s.kind === "progress" ? " pulse-dot" : "")}>{s.message}</span>
          </div>
        );
      })}
      <div ref={endRef} />
    </div>
  );
}
