import { apiFetch, ApiTransportError } from "./base";

export type ResearchJobStatus = "queued" | "running" | "complete" | "failed";

export type ResearchJob = {
  job_id: string;
  status: ResearchJobStatus;
  result?: unknown;
  error?: { message?: string; type?: string } | null;
};

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => {
    window.setTimeout(resolve, ms);
  });
}

export async function pollResearchJob(jobId: string): Promise<unknown> {
  for (;;) {
    const res = await apiFetch(`/research-query/jobs/${encodeURIComponent(jobId)}`);
    const body = (await res.json()) as ResearchJob & { detail?: string };
    if (res.status === 404) {
      throw new Error(body.detail || "Research job not found");
    }
    if (!res.ok) {
      throw new Error(body.detail || body.error?.message || res.statusText);
    }
    if (body.status === "complete") {
      return body.result;
    }
    if (body.status === "failed") {
      throw new Error(body.error?.message || "Research query failed");
    }
    await sleep(400);
  }
}

/** Submit execute. The API returns 202 + job_id so /health stays reachable. */
export async function executeResearchQuery(body: Record<string, unknown>): Promise<unknown> {
  const res = await apiFetch("/research-query/execute", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (res.status === 202) {
    const start = (await res.json()) as ResearchJob;
    if (!start.job_id) {
      throw new Error("Execute did not return a job_id");
    }
    return pollResearchJob(start.job_id);
  }
  const payload = await res.json();
  if (!res.ok) {
    throw new Error(payload.detail || payload.message || res.statusText);
  }
  return payload;
}

export type ServerSaveMeta = {
  id: string;
  name: string;
  folder: string;
  description: string;
  saved_at: string;
  population_n?: number | null;
  execution_status?: string | null;
  message?: string;
};

export async function saveResultToServer(body: Record<string, unknown>): Promise<ServerSaveMeta> {
  const res = await apiFetch("/research-library/saves", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  const payload = await res.json();
  if (!res.ok) {
    throw new ApiTransportError(
      res.status >= 500 ? "API_REQUEST_FAILED" : "API_REQUEST_FAILED",
      payload.detail || payload.message || res.statusText,
    );
  }
  return payload as ServerSaveMeta;
}

export async function loadServerSave(id: string): Promise<Record<string, unknown>> {
  const res = await apiFetch(`/research-library/saves/${encodeURIComponent(id)}`);
  const payload = await res.json();
  if (!res.ok) {
    throw new Error(payload.detail || payload.message || res.statusText);
  }
  return payload as Record<string, unknown>;
}
