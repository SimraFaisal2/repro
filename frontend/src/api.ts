import type { Investigation, Project } from "./types";

// Same-origin by default (Vite dev proxy / single-service Docker). When the
// frontend is hosted separately from the backend, point VITE_API_BASE at the
// backend origin, e.g. VITE_API_BASE=https://repro-backend.onrender.com
const BASE = import.meta.env.VITE_API_BASE || "/api";

async function j<T>(res: Response): Promise<T> {
  if (!res.ok) {
    let msg = res.statusText;
    try {
      const body = await res.json();
      msg = body.detail || JSON.stringify(body);
    } catch {
      /* keep statusText */
    }
    throw new Error(msg);
  }
  return res.json() as Promise<T>;
}

export const api = {
  health: () => fetch(`${BASE}/health`).then((r) => r.json()),

  listProjects: () => fetch(`${BASE}/projects`).then((r) => j<Project[]>(r)),

  createProject: (name: string, url: string) =>
    fetch(`${BASE}/projects`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name, source_type: "url", url }),
    }).then((r) => j<Project>(r)),

  analyzeProject: (id: string) =>
    fetch(`${BASE}/projects/${id}/analyze`, { method: "POST" }).then((r) => j<any>(r)),

  uploadProject: (file: File) => {
    const fd = new FormData();
    fd.append("file", file);
    return fetch(`${BASE}/projects/upload`, { method: "POST", body: fd }).then((r) => j<Project>(r));
  },

  runDemo: (bug: string) =>
    fetch(`${BASE}/demo`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ bug }),
    }).then((r) => j<{ project: Project; investigation: Investigation }>(r)),

  createInvestigation: (projectId: string) =>
    fetch(`${BASE}/investigations`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ project_id: projectId }),
    }).then((r) => j<Investigation>(r)),

  runInvestigation: (id: string) =>
    fetch(`${BASE}/investigations/${id}/run`, { method: "POST" }).then((r) => j<any>(r)),

  getInvestigation: (id: string) =>
    fetch(`${BASE}/investigations/${id}`).then((r) => j<Investigation>(r)),

  applyPatch: (id: string, confirm: boolean, approveRisk = false) =>
    fetch(`${BASE}/investigations/${id}/apply`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ confirm, approve_risk: approveRisk }),
    }).then((r) => j<any>(r)),

  verify: (id: string) =>
    fetch(`${BASE}/investigations/${id}/verify`, { method: "POST" }).then((r) => j<any>(r)),

  report: (id: string) =>
    fetch(`${BASE}/investigations/${id}/report`).then((r) => r.text()),

  eventsUrl: (id: string) => `${BASE}/investigations/${id}/events`,
};
