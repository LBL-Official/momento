export type LsSnapshot = {
  ok: boolean;
  status?: string;
  reason?: string;
  product?: string;
  observe_only?: boolean;
  submits?: boolean;
  source?: string;
  observed_at?: string;
  instance_id?: string;
  service_name?: string;
  service?: Record<string, unknown>;
  process?: Record<string, unknown>;
  hashes?: {
    binary?: string | null;
    binary_bytes?: number | null;
    unit?: string | null;
    live_toml?: string | null;
    persist?: string | null;
    snapshot?: string | null;
    baseline?: string;
    baseline_match?: boolean;
  };
  environment?: Record<string, unknown>;
  paths?: Record<string, unknown>;
  gates?: {
    live_armed?: boolean;
    reconciliation?: string | null;
    order_submission?: string | null;
    authorized_to_submit?: boolean;
    kill_switch?: boolean | null;
  };
  occupancy?: Record<string, unknown>;
  updates?: Record<string, unknown>;
  errors?: {
    n?: number | null;
    last?: string | null;
    recent?: string[];
  };
  journal?: string[];
  bankroll_cents?: number | null;
};

export type LsHealth = {
  ok: boolean;
  product: string;
  observe_only: boolean;
  submits: boolean;
  service: string;
  instance_id: string;
};
