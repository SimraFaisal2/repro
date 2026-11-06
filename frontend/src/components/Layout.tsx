import { Link, NavLink, Outlet, useLocation } from "react-router-dom";
import { Bug, LayoutDashboard, Radio } from "lucide-react";
import { useEffect, useState } from "react";
import { api } from "../api";

function AgentStatus() {
  const [ok, setOk] = useState<boolean | null>(null);
  useEffect(() => {
    api
      .health()
      .then(() => setOk(true))
      .catch(() => setOk(false));
  }, []);
  return (
    <span
      className={`inline-flex items-center gap-1.5 text-[10.5px] tracking-wide rounded-full border px-2.5 py-1 ${
        ok ? "text-good border-good/25" : ok === null ? "text-muted border-border" : "text-bad border-bad/30"
      }`}
    >
      <span className={`size-1.5 rounded-full bg-current ${ok === true ? "pulse-dot" : ""}`} />
      {ok === null ? "Connecting" : ok ? "Agent ready" : "Offline"}
    </span>
  );
}

export default function Layout() {
  const loc = useLocation();
  const inInvestigation = loc.pathname.startsWith("/investigation");
  return (
    <div className="min-h-screen flex flex-col">
      <header className="sticky top-0 z-20 border-b border-border bg-bg/80 backdrop-blur-md">
        <div className="h-14 max-w-page mx-auto px-5 flex items-center justify-between">
          <div className="flex items-center gap-7">
            <Link to="/" className="flex items-center gap-2.5 group">
              <span className="grid place-items-center size-7 rounded-[7px] border border-border bg-panel2 text-accent transition-colors group-hover:border-accent/40">
                <Bug size={14} strokeWidth={1.8} />
              </span>
              <span className="font-display font-medium tracking-[-0.02em] text-[17px]">REPRO</span>
              <span className="hidden lg:inline text-[10.5px] tracking-[0.14em] uppercase text-faint ml-1">
                Runtime error investigation &amp; repair
              </span>
            </Link>
            <nav className="hidden md:flex items-center gap-1 text-[13px]">
              <NavLink
                to="/dashboard"
                className={({ isActive }) =>
                  `flex items-center gap-1.5 px-2.5 py-1.5 rounded-[7px] ${
                    isActive ? "text-ink bg-panel2" : "text-muted hover:text-ink"
                  }`
                }
              >
                <LayoutDashboard size={13} /> Repositories
              </NavLink>
            </nav>
          </div>
          <div className="flex items-center gap-3">
            {inInvestigation && (
              <span className="hidden sm:inline-flex items-center gap-1.5 text-[10.5px] text-faint mono">
                <Radio size={10} className="text-good" /> live
              </span>
            )}
            <AgentStatus />
          </div>
        </div>
      </header>
      <main className="flex-1 w-full max-w-page mx-auto px-5 py-6">
        <Outlet />
      </main>
      <footer className="border-t border-border">
        <div className="max-w-page mx-auto px-5 py-5 flex flex-wrap items-center justify-between gap-2 text-[11px] text-faint">
          <span>REPRO — untrusted repositories execute only inside an isolated sandbox.</span>
          <span className="mono tracking-wide">reproduce · investigate · diagnose · patch · verify</span>
        </div>
      </footer>
    </div>
  );
}
