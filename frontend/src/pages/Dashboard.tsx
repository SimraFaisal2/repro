import { FormEvent, useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  ArrowRight,
  FlaskConical,
  FolderOpen,
  Github,
  Loader2,
  Upload,
} from "lucide-react";
import { api } from "../api";
import type { Investigation, Project } from "../types";
import { Panel } from "../components/Panel";

export default function Dashboard() {
  const nav = useNavigate();
  const [url, setUrl] = useState("");
  const [name, setName] = useState("");
  const [projects, setProjects] = useState<Project[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const fileRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    api.listProjects().then(setProjects).catch(() => setProjects([]));
  }, []);

  async function analyze() {
    if (!url.trim()) return;
    setBusy(true);
    setError("");
    try {
      const proj = await api.createProject(name.trim() || autoName(url), url.trim());
      await api.analyzeProject(proj.id);
      const inv = await api.createInvestigation(proj.id);
      await api.runInvestigation(inv.id);
      nav(`/investigation/${inv.id}`);
    } catch (e: any) {
      setError(e?.message || "failed to create project");
    } finally {
      setBusy(false);
    }
  }

  async function upload(file: File) {
    setBusy(true);
    setError("");
    try {
      const proj = await api.uploadProject(file);
      await api.analyzeProject(proj.id);
      const inv = await api.createInvestigation(proj.id);
      await api.runInvestigation(inv.id);
      nav(`/investigation/${inv.id}`);
    } catch (e: any) {
      setError(e?.message || "upload failed");
    } finally {
      setBusy(false);
    }
  }

  async function demo(bug: string) {
    setBusy(true);
    setError("");
    try {
      const res = await api.runDemo(bug);
      await api.runInvestigation(res.investigation.id);
      nav(`/investigation/${res.investigation.id}`);
    } catch (e: any) {
      setError(e?.message || "demo failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="max-w-4xl mx-auto space-y-8">
      <Panel title="Repository">
        <div className="space-y-3">
          <div className="flex gap-2">
            <div className="relative flex-1">
              <Github size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-faint" />
              <input
                className="input pl-9 font-mono text-[13px]"
                placeholder="https://github.com/user/example-project"
                value={url}
                onChange={(e) => setUrl(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && analyze()}
              />
            </div>
            <button className="btn-primary shrink-0" disabled={busy || !url.trim()} onClick={analyze}>
              {busy ? <Loader2 size={15} className="animate-spin" /> : <ArrowRight size={15} />}
              Analyze Repository
            </button>
          </div>
          <div className="flex items-center gap-2">
            <input
              className="input flex-1"
              placeholder="Display name (optional)"
              value={name}
              onChange={(e) => setName(e.target.value)}
            />
            <input
              ref={fileRef}
              type="file"
              accept=".zip"
              className="hidden"
              onChange={(e) => e.target.files?.[0] && upload(e.target.files[0])}
            />
            <button className="btn-ghost shrink-0" disabled={busy} onClick={() => fileRef.current?.click()}>
              <Upload size={15} /> Upload .zip
            </button>
          </div>
          <div className="flex flex-wrap gap-2 pt-1">
            <span className="text-[11px] text-faint mono self-center mr-1">Run demo:</span>
            {[
              ["auth", "None handling"],
              ["offbyone", "Off-by-one"],
              ["api", "API key"],
              ["sql", "SQL column"],
              ["auth2", "Auth logic"],
            ].map(([k, label]) => (
              <button
                key={k}
                className="btn-ghost !px-2.5 !py-1 text-[11.5px]"
                disabled={busy}
                onClick={() => demo(k)}
              >
                <FlaskConical size={12} /> {label}
              </button>
            ))}
          </div>
          {error && <p className="text-xs text-bad">{error}</p>}
          <p className="text-[11px] text-faint">
            Untrusted code: the repository is copied into an isolated sandbox with a
            stripped environment and a hard timeout — never executed directly on your host.
          </p>
        </div>
      </Panel>

      <Panel title="Recent repositories" right={<span className="mono text-[11px] text-faint">{projects.length}</span>}>
        {projects.length === 0 ? (
          <p className="text-xs text-faint">No projects yet — analyze a repository or run a demo.</p>
        ) : (
          <div className="divide-y divide-border">
            {projects.map((p) => (
              <RepoRow
                key={p.id}
                project={p}
                onOpen={async () => {
                  setBusy(true);
                  try {
                    const inv = await api.createInvestigation(p.id);
                    await api.runInvestigation(inv.id);
                    nav(`/investigation/${inv.id}`);
                  } catch (e: any) {
                    setError(e?.message || "failed to start investigation");
                    setBusy(false);
                  }
                }}
              />
            ))}
          </div>
        )}
      </Panel>
    </div>
  );
}

function autoName(url: string) {
  const m = url.match(/\/([^/]+?)(?:\.git)?\/?$/);
  return m ? m[1] : "repository";
}

function RepoRow({ project, onOpen }: { project: Project; onOpen: () => void }) {
  const ov = project.overview;
  return (
    <div className="flex items-center justify-between px-4 py-3">
      <div className="flex items-center gap-3 min-w-0">
        <FolderOpen size={16} className="text-accent shrink-0" />
        <div className="min-w-0">
          <div className="text-sm text-ink truncate">{project.name}</div>
          <div className="text-[11px] text-faint mono truncate">
            {ov ? `${ov.framework} · ${ov.test_framework} · ${ov.files} files` : project.source_type}
          </div>
        </div>
      </div>
      <button className="btn-ghost !py-1 text-xs shrink-0" onClick={onOpen}>
        open
      </button>
    </div>
  );
}
