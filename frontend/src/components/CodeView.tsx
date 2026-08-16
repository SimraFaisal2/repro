import { useMemo } from "react";

const KW =
  /\b(def|class|return|if|elif|else|for|while|import|from|as|try|except|finally|raise|with|lambda|and|or|not|in|is|None|True|False|pass|break|continue|async|await|yield|global|nonlocal|assert|del)\b/g;
const STR = /("""[\s\S]*?"""|'''[\s\S]*?'''|"(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*')/g;
const COM = /(#[^\n]*)/g;
const NUM = /\b(\d+(?:\.\d+)?)\b/g;
const DEC = /\b(def|class)\s+([A-Za-z_]\w*)/g;

function tokenize(line: string): { text: string; cls: string }[] {
  const tokens: { text: string; cls: string }[] = [];
  let i = 0;
  const re = /(#[^\n]*|"""(?:[\s\S]*?)"""|'''(?:[\s\S]*?)'''|"(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*'|\b(def|class)\s+([A-Za-z_]\w*)\b|\b(?:def|class|return|if|elif|else|for|while|import|from|as|try|except|finally|raise|with|lambda|and|or|not|in|is|None|True|False|pass|break|continue|async|await|yield|global|nonlocal|assert|del)\b|\b\d+(?:\.\d+)?\b)/g;
  let m: RegExpExecArray | null;
  while ((m = re.exec(line)) !== null) {
    if (m.index > i) tokens.push({ text: line.slice(i, m.index), cls: "text-ink" });
    const tok = m[0];
    let cls = "text-ink";
    if (tok.startsWith("#")) cls = "text-faint italic";
    else if (tok.startsWith('"') || tok.startsWith("'")) cls = "text-cy/90";
    else if (m[3]) cls = "text-vio/90"; // function/class name
    else if (m[2]) cls = "text-accent font-medium"; // keyword
    else if (/^\d/.test(tok)) cls = "text-warn";
    tokens.push({ text: tok, cls });
    i = m.index + tok.length;
  }
  if (i < line.length) tokens.push({ text: line.slice(i), cls: "text-ink" });
  return tokens;
}

export default function CodeView({
  source,
  failingLine,
  highlightLines = [],
  startLine = 1,
  className = "",
}: {
  source: string;
  failingLine?: number | null;
  highlightLines?: number[];
  startLine?: number;
  className?: string;
}) {
  const lines = useMemo(() => source.replace(/\r\n/g, "\n").split("\n"), [source]);
  return (
    <div className={`overflow-x-auto text-[12.5px] leading-[1.55] font-mono ${className}`}>
      {lines.map((line, idx) => {
        const ln = startLine + idx;
        const isFail = failingLine != null && ln === failingLine;
        const isHl = highlightLines.includes(ln);
        return (
          <div
            key={ln}
            className={`flex ${isFail ? "bg-bad/15" : isHl ? "bg-warn/10" : ""} ${
              isFail ? "border-l-2 border-bad" : "border-l-2 border-transparent"
            }`}
          >
            <span className="select-none w-10 shrink-0 pr-3 text-right text-faint/60">{ln}</span>
            <span className="whitespace-pre pr-4">
              {tokenize(line).map((t, ti) => (
                <span key={ti} className={t.cls}>
                  {t.text}
                </span>
              ))}
            </span>
          </div>
        );
      })}
    </div>
  );
}
