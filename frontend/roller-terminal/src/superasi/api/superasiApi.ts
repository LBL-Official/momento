import { apiFetch } from "../../api/base";
import type {
  AdverseP,
  Decomp,
  FeeScenario,
  FillAlgorithm,
  ImportResponse,
  LibraryItem,
  PackageGet,
  SuperasiBaseInspect,
  SuperasiBaseResult,
  SuperasiDebaseInspect,
  SuperasiDebaseResult,
  SuperasiErrorBody,
  SuperasiLabSource,
} from "../types/superasi";

async function parse<T>(res: Response): Promise<T> {
  const body = (await res.json()) as T & SuperasiErrorBody;
  if (!res.ok) {
    const detail = body.detail;
    const nested = typeof detail === "object" && detail ? detail : body;
    const code = nested.code || nested.status || String(res.status);
    const message =
      nested.message || (typeof detail === "string" ? detail : res.statusText);
    const err = new Error(message) as Error & SuperasiErrorBody;
    err.code = code;
    err.status = code;
    err.message = message;
    throw err;
  }
  return body;
}

export async function importMeasurement(body: Record<string, unknown>): Promise<ImportResponse> {
  const res = await apiFetch("/superasi/library/import", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  return parse<ImportResponse>(res);
}

export async function listPackages(): Promise<{ packages: LibraryItem[]; n: number }> {
  const res = await apiFetch("/superasi/library");
  return parse(res);
}

export async function getPackage(packageId: string): Promise<PackageGet> {
  const res = await apiFetch(`/superasi/library/${encodeURIComponent(packageId)}`);
  return parse(res);
}

export async function decomposePackage(
  packageId: string,
  settings: {
    fill_algorithm?: FillAlgorithm;
    fee_scenario?: FeeScenario;
    adverse_p?: AdverseP;
  },
): Promise<Decomp> {
  const res = await apiFetch(`/superasi/library/${encodeURIComponent(packageId)}/decompose`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(settings),
  });
  return parse(res);
}

export async function seedAskedSix(): Promise<ImportResponse> {
  const res = await apiFetch("/superasi/seed/asked-six");
  return parse(res);
}

export async function listBaseSources(folder?: string): Promise<{
  labs: SuperasiLabSource[];
  folders: string[];
  n: number;
}> {
  const q = folder ? `?folder=${encodeURIComponent(folder)}` : "";
  const res = await apiFetch(`/superasi/base/sources${q}`);
  return parse(res);
}

export async function getBaseSource(labId: string): Promise<SuperasiLabSource> {
  const res = await apiFetch(`/superasi/base/sources/${encodeURIComponent(labId)}`);
  return parse(res);
}

export async function runSuperasiBase(labId: string): Promise<SuperasiBaseInspect> {
  const res = await apiFetch("/superasi/base/run", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ lab_id: labId }),
  });
  return parse(res);
}

export async function listBaseResults(): Promise<{ results: SuperasiBaseResult[]; n: number }> {
  const res = await apiFetch("/superasi/base/results");
  return parse(res);
}

export async function getBaseResult(resultId: string): Promise<SuperasiBaseInspect> {
  const res = await apiFetch(`/superasi/base/results/${encodeURIComponent(resultId)}`);
  return parse(res);
}

async function downloadNamedCsv(path: string, filename: string): Promise<void> {
  const res = await apiFetch(path);
  if (!res.ok) throw new Error("CSV download failed");
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

export async function downloadBaseCsv(resultId: string, filename: string): Promise<void> {
  await downloadNamedCsv(`/superasi/base/results/${encodeURIComponent(resultId)}/csv?which=base`, filename);
}

export async function downloadRollerCopy(resultId: string, filename: string): Promise<void> {
  await downloadNamedCsv(`/superasi/base/results/${encodeURIComponent(resultId)}/csv?which=roller`, filename);
}

export type SuperasiHandoff = {
  handoff_id?: string | null;
  lab_id: string;
  status?: string;
  phase?: string;
  result_id?: string | null;
  phase_a_result_id?: string;
  strategy_name?: string;
  reused_base?: boolean;
  reused_debase?: boolean;
  ran_base?: boolean;
  ran_debase?: boolean;
  inspect?: SuperasiDebaseInspect;
  error?: string | null;
  error_code?: string | null;
};

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => window.setTimeout(resolve, ms));
}

export async function startLabHandoff(labId: string): Promise<SuperasiHandoff> {
  const res = await apiFetch("/superasi/handoff", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ lab_id: labId, reuse: true }),
  });
  return parse<SuperasiHandoff>(res);
}

export async function getLabHandoff(handoffId: string): Promise<SuperasiHandoff> {
  const res = await apiFetch(`/superasi/handoff/${encodeURIComponent(handoffId)}`);
  return parse<SuperasiHandoff>(res);
}

export async function advanceLabToFinal(
  labId: string,
  opts?: { onUpdate?: (job: SuperasiHandoff) => void },
): Promise<SuperasiHandoff> {
  let job = await startLabHandoff(labId);
  opts?.onUpdate?.(job);
  if (job.status === "COMPLETE" && job.result_id) {
    return job;
  }
  if (job.status === "FAILED") {
    throw new Error(job.error || job.error_code || "SuperASI handoff failed");
  }
  if (!job.handoff_id) {
    throw new Error("SuperASI handoff did not return a job id");
  }
  const handoffId = job.handoff_id;
  for (;;) {
    await sleep(1500);
    job = await getLabHandoff(handoffId);
    opts?.onUpdate?.(job);
    if (job.status === "COMPLETE" && job.result_id) {
      return job;
    }
    if (job.status === "FAILED") {
      throw new Error(job.error || job.error_code || "SuperASI handoff failed");
    }
  }
}

export async function runSuperasiDebase(resultId: string): Promise<SuperasiDebaseInspect> {
  const res = await apiFetch("/superasi/debase/run", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ result_id: resultId }),
  });
  return parse(res);
}

export async function listDebaseResults(): Promise<{ results: SuperasiDebaseResult[]; n: number }> {
  const res = await apiFetch("/superasi/debase/results");
  return parse(res);
}

export async function getDebaseResult(resultId: string): Promise<SuperasiDebaseInspect> {
  const res = await apiFetch(`/superasi/debase/results/${encodeURIComponent(resultId)}`);
  return parse(res);
}

export async function downloadDebaseCsv(resultId: string, filename: string): Promise<void> {
  await downloadNamedCsv(`/superasi/debase/results/${encodeURIComponent(resultId)}/csv?which=debase`, filename);
}

export async function downloadDebaseAbaseCsv(resultId: string, filename: string): Promise<void> {
  await downloadNamedCsv(`/superasi/debase/results/${encodeURIComponent(resultId)}/csv?which=abase`, filename);
}

export async function downloadDebaseRollerCsv(resultId: string, filename: string): Promise<void> {
  await downloadNamedCsv(`/superasi/debase/results/${encodeURIComponent(resultId)}/csv?which=roller`, filename);
}

export type ItiSlot = {
  slot_id: string;
  label: string;
  status: string;
  skip_reason?: string | null;
  entry_cents?: number | null;
  win_cents?: number | null;
  loss_cents?: number | null;
  population?: number | null;
  BASE_GRADE?: string | null;
  DEBASE_GRADE?: string | null;
  phase_a_result_id?: string | null;
  phase_b_result_id?: string | null;
  executed?: boolean;
};

export type ItiRun = {
  run_id: string;
  status: string;
  strategy_name?: string;
  debase_result_id?: string;
  slot_n?: number;
  progress_done?: number;
  recommended_slot_id?: string | null;
  committed_slot_id?: string | null;
  commit_path?: string | null;
  slots: ItiSlot[];
  honesty?: Record<string, string | boolean>;
  caveats?: string[];
};

export async function runIti(debaseResultId: string): Promise<ItiRun> {
  const res = await apiFetch("/superasi/iti/run", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ debase_result_id: debaseResultId }),
  });
  return parse<ItiRun>(res);
}

export async function getItiRun(runId: string): Promise<ItiRun> {
  const res = await apiFetch(`/superasi/iti/${encodeURIComponent(runId)}`);
  return parse<ItiRun>(res);
}

export async function latestIti(debaseResultId: string): Promise<ItiRun | null> {
  const res = await apiFetch(`/superasi/iti?debase_result_id=${encodeURIComponent(debaseResultId)}`);
  const body = await parse<{ latest?: ItiRun | null }>(res);
  return body.latest || null;
}

export async function commitIti(
  runId: string,
  slotId: string,
): Promise<{ path?: string; strategy_name?: string; iti_folder?: string; source_folder?: string }> {
  const res = await apiFetch(`/superasi/iti/${encodeURIComponent(runId)}/commit`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ slot_id: slotId }),
  });
  return parse(res);
}
