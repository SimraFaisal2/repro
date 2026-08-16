import { useMemo } from "react";

interface Hunk {
  file: string;
  oldStart: number;
  newStart: number;
  lines: { kind: "ctx" | "add" | "del" | "hdr"; text: string }[];
}

function parseDiff(diff: string): Hunk[] {
  const hunks: Hunk[] = [];
  let cur: Hunk | null = null;
  const fileRe = /^diff --git a\/(\S+) b\//;
  const hdrRe = /^@@ -(\d+)(?:,\d+)? \+(\d+)(?:,\d+)? @@/;
  for (const raw of diff.split("\n")) {
    const line = raw.replace(/\r$/, "");
    const fm = line.match(fileRe);
    if (fm) {
      cur = { file: fm[1], oldStart: 0, newStart: 0, lines: [] };
      hunks.push(cur);
      continue;
    }
    if (!cur) continue;
    const hm = line.match(hdrRe);
    if (hm) {
      cur.oldStart = Number(hm[1]);
      cur.newStart = Number(hm[2]);
      cur.lines.push({ kind: "hdr", text: line });
      continue;
    }
    if (line.startsWith("+++") || line.startsWith("---") || line.startsWith("index ")) continue;
    if (line.startsWith("+")) cur.lines.push({ kind: "add", text: line });
    else if (line.startsWith("-")) cur.lines.push({ kind: "del", text: line });
    else cur.lines.push({ kind: "ctx", text: line });
  }
  return hunks;
}

export default function DiffView({ diff }: { diff: string }) {
  const hunks = useMemo(() => parseDiff(diff), [diff]);
  if (!diff.trim()) {
    return <p className="text-xs text-faint mono">(no patch generated)</p>;
  }
  return (
    <div className="overflow-x-auto rounded-md border border-border font-mono text-[12px] leading-[1.5]">
      {hunks.map((h, hi) => (
        <div key={hi}>
          <div className="px-3 py-1 bg-panel2 border-b border-border text-[11px] text-accent">
            {h.file}
          </div>
          {h.lines.map((l, li) => (
            <div
              key={li}
              className={`px-3 whitespace-pre ${
                l.kind === "add"
                  ? "bg-good/10 text-good"
                  : l.kind === "del"
                  ? "bg-bad/10 text-bad"
                  : l.kind === "hdr"
                  ? "bg-panel2 text-faint"
                  : "text-ink/80"
              }`}
            >
              {l.text || " "}
            </div>
          ))}
        </div>
      ))}
    </div>
  );
}
