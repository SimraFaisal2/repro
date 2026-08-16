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
      className={`inline-flex items-center gap-1.5 text-[11px] font-medium rounded-full border px-2 py-0.5 ${
        ok ? "text-good border-good/30" : ok === null ? "text-muted border-border" : "text-bad border-bad/30"
      }`}
    >
      <span className={`size-1.5 rounded-full bg-current ${ok === true ? "pulse-dot" : ""}`} />
      {ok === null ? "Connecting…" : ok ? "Agent Ready" : "Offline"}
    </span>
  );
}

export default function Layout() {
  const loc = useLocation();
  const inInvestigation = loc.pathname.startsWith("/investigation");
  return (
    <div className="min-h-screen flex flex-col">
      <header className="h-12 border-b border-border bg-panel/60 backdrop-blur sticky top-0 z-20">
        <div className="h-full max-w-[1600px] mx-auto px-4 flex items-center justify-between">
          <div className="flex items-center gap-6">
            <Link to="/" className="flex items-center gap-2 group">
              <span className="grid place-items-center size-6 rounded bg-accent/15 border border-accent/40 text-accent">
                <Bug size={14} strokeWidth={2.2} />
              </span>
              <span className="font-mono font-bold tracking-tight text-[15px]">
                REPRO
                <span className="text-faint font-normal ml-1.5 hidden sm:inline">Runtime Error Investigation &amp; Repair</span>
              </span>
            </Link>
            <nav className="hidden md:flex items-center gap-1 text-sm">
              <NavLink
                to="/dashboard"
                className={({ isActive }) =>
                  `flex items-center gap-1.5 px-3 py-1.5 rounded-md ${
                    isActive ? "text-accent bg-accent/10" : "text-muted hover:text-ink hover:bg-panel2"
                  }`
                }
              >
                <LayoutDashboard size={14} /> Repositories
              </NavLink>
            </nav>
          </div>
          <div className="flex items-center gap-3">
            {inInvestigation && (
              <span className="hidden sm:inline-flex items-center gap-1.5 text-[11px] text-faint mono">
                <Radio size={11} className="text-good" /> live
              </span>
            )}
            <AgentStatus />
          </div>
        </div>
      </header>
      <main className="flex-1 w-full max-w-[1600px] mx-auto px-4 py-6">
        <Outlet />
      </main>
      <footer className="border-t border-border py-4 text-[11px] text-faint mono max-w-[1600px] mx-auto w-full px-4">
        REPRO — untrusted repositories execute only inside an isolated sandbox.
      </footer>
    </div>
  );
}
