const API_BASE = (import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8005').replace(/\/$/, '');

export type Severity = 'blocker' | 'warning' | 'suggestion' | 'nit' | 'pass';
export type Readiness = 'blocked' | 'caution' | 'ready';

export interface Health { ok: boolean; ai_enabled: boolean; provider: string; audits: number; version: string; }
export interface UploadedRepository { session_id: string; repo_name: string; file_count: number; detected_stack: string[]; default_targets: string[]; }
export interface RepoFile { path: string; size: number; kind: string; }
export interface SkillCard { name: string; incorporated_as: string; purpose: string; }
export interface Finding { severity: Severity; agent: string; title: string; file?: string | null; evidence: string; why_it_matters: string; recommendation: string; command?: string | null; }
export interface EnvVariable { name: string; exposure: 'public' | 'server' | 'unknown'; required: boolean; source: string; note: string; }
export interface CommandBlock { label: string; command: string; purpose: string; }
export interface LaunchPlan { deployment_target: string; readiness: Readiness; environment_matrix: EnvVariable[]; build_commands: CommandBlock[]; smoke_tests: CommandBlock[]; rollback_plan: string[]; predeploy_checklist: string[]; postdeploy_checklist: string[]; }
export interface AgentTrace { agent: string; status: 'pass' | 'warn' | 'blocked'; findings: number; summary: string; }
export interface AuditResponse { session_id: string; score: number; readiness: Readiness; summary: string; findings: Finding[]; launch_plan: LaunchPlan; traces: AgentTrace[]; markdown_report: string; }

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, init);
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}: ${await res.text()}`);
  return res.json();
}

export const api = {
  health: () => request<Health>('/api/v1/shipgate/health'),
  skills: () => request<SkillCard[]>('/api/v1/shipgate/skills'),
  upload: (file: File) => {
    const form = new FormData();
    form.append('file', file);
    return request<UploadedRepository>('/api/v1/shipgate/upload', { method: 'POST', body: form });
  },
  files: (sessionId: string) => request<{ session_id: string; files: RepoFile[]; default_targets: string[] }>(`/api/v1/shipgate/files/${sessionId}`),
  audit: (payload: { session_id: string; objective: string; target_files: string[]; deployment_target: string; use_llm: boolean }) => request<AuditResponse>('/api/v1/shipgate/audit', { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify(payload) })
};
