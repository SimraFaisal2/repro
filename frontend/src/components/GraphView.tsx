import { useMemo, useState } from "react";
import type { Overview } from "../types";

interface Node {
  id: string;
  label: string;
  x: number;
  y: number;
}

export default function GraphView({
  graph,
  failingModule,
  onSelect,
}: {
  graph: { modules: string[]; edges: [string, string][] };
  failingModule?: string | null;
  onSelect?: (mod: string) => void;
}) {
  const [selected, setSelected] = useState<string | null>(null);

  const { nodes, edges } = useMemo(() => {
    const mods = graph.modules.slice(0, 40);
    const imp: Record<string, Set<string>> = {};
    for (const m of mods) imp[m] = new Set();
    for (const [a, b] of graph.edges) {
      if (imp[b]) imp[b].add(a);
    }
    // level = longest path from entry modules (nothing imports them)
    const level: Record<string, number> = {};
    const compute = (m: string): number => {
      if (m in level) return level[m];
      const parents = imp[m] || new Set();
      if (parents.size === 0) {
        level[m] = 0;
      } else {
        level[m] = 1 + Math.max(0, ...Array.from(parents).map(compute));
      }
      return level[m];
    };
    for (const m of mods) compute(m);
    const byLevel: Record<number, string[]> = {};
    for (const m of mods) {
      const l = level[m];
      (byLevel[l] ||= []).push(m);
    }
    const levels = Object.keys(byLevel)
      .map(Number)
      .sort((a, b) => a - b);
    const W = 230,
      H = 44;
    const maxL = Math.max(...levels.map((l) => byLevel[l].length), 1);
    const nodes: Node[] = [];
    for (const l of levels) {
      const col = byLevel[l];
      col.forEach((m, i) => {
        nodes.push({
          id: m,
          label: m.split(".").slice(-2).join("."),
          x: 20 + l * W,
          y: 24 + (i + 0.5) * H + (maxL - col.length) * (H / 2),
        });
      });
    }
    const edges: [string, string][] = graph.edges.filter(
      ([a, b]) => mods.includes(a) && mods.includes(b)
    );
    return { nodes, edges };
  }, [graph]);

  const w = useMemo(() => (nodes.length ? Math.max(...nodes.map((n) => n.x)) + 220 : 400), [nodes]);
  const h = useMemo(() => (nodes.length ? Math.max(...nodes.map((n) => n.y)) + 40 : 120), [nodes]);

  const failingNorm = failingModule?.replace(/\\/g, "/").replace(/\.py$/, "").replace(/\//g, ".");
  const importersCount: Record<string, number> = {};
  for (const [a, b] of edges) importersCount[b] = (importersCount[b] || 0) + 1;

  return (
    <div className="overflow-x-auto">
      <svg width={w} height={h} className="min-w-full">
        {edges.map(([a, b], i) => {
          const na = nodes.find((n) => n.id === a);
          const nb = nodes.find((n) => n.id === b);
          if (!na || !nb) return null;
          const involved = failingNorm && (a === failingNorm || b === failingNorm);
          return (
            <line
              key={i}
              x1={na.x + 95}
              y1={na.y}
              x2={nb.x - 95}
              y2={nb.y}
              stroke={involved ? "#f85149" : "#30363d"}
              strokeWidth={involved ? 1.6 : 1}
              strokeDasharray={involved ? "none" : "3 3"}
            />
          );
        })}
        {nodes.map((n) => {
          const active = selected === n.id;
          const involved = failingNorm && n.id === failingNorm;
          const parents = importersCount[n.id] || 0;
          return (
            <g
              key={n.id}
              transform={`translate(${n.x - 95},${n.y - 15})`}
              className="cursor-pointer"
              onClick={() => {
                setSelected(active ? null : n.id);
                onSelect?.(n.id);
              }}
            >
              <rect
                width="190"
                height="30"
                rx="6"
                fill={active ? "#1f6feb26" : involved ? "#f8514915" : "#161b22"}
                stroke={active ? "#58a6ff" : involved ? "#f85149" : "#30363d"}
                strokeWidth={1}
              />
              <text
                x="95"
                y="19"
                textAnchor="middle"
                fontSize="10.5"
                fontFamily="JetBrains Mono, monospace"
                fill={involved ? "#f85149" : active ? "#58a6ff" : "#8b949e"}
              >
                {n.label}
              </text>
            </g>
          );
        })}
      </svg>
      {selected && (
        <div className="mt-2 rounded-md border border-border bg-panel2 px-3 py-2 text-[11.5px]">
          <div className="text-accent mono">{selected}</div>
          <div className="text-faint">
            imported by {importersCount[selected] || 0} module{importersCount[selected] === 1 ? "" : "s"}
          </div>
        </div>
      )}
    </div>
  );
}
