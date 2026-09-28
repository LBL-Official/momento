import { useEffect, useState } from "react";
import { DreError, fetchDre } from "./api";
import { text } from "./text";

type Member = {
  experiment_id: string;
  slice?: string;
  n_lock?: number;
  discovery_present?: boolean;
  confirmation_present?: boolean;
};

type PersistenceAudit = {
  status?: string;
  audit_id?: string;
  policy_status?: string;
  policy_selected?: string;
  confirmation_accessed?: boolean;
  confirmation_A?: string;
  confirmation_B?: string;
  note?: string;
  A?: PersistenceMember | null;
  B?: PersistenceMember | null;
  alignment?: Record<string, unknown> | null;
  interpretation?: Record<string, unknown> | null;
};

type PersistenceMember = {
  experiment_id?: string;
  economics?: {
    n_first_negative?: number;
    n_temporary?: number;
    n_persistent?: number;
    n_unresolved?: number;
    temporary?: Record<string, unknown>;
    persistent?: Record<string, unknown>;
    persistent_minus_temporary?: Record<string, { observed_delta?: unknown; ci?: unknown; classification?: unknown }>;
  };
  pit_comparison?: { feature?: string; temporary_mean?: unknown; persistent_mean?: unknown; difference?: unknown; classification?: unknown }[];
  landmarks?: { landmark?: string; N_trades?: unknown; loss_rate?: unknown; mean_pnl_hold_after_t0?: unknown; T40_rate?: unknown }[];
};

type DownfallMember = {
  experiment_id?: string;
  populations?: { core_state?: string; N_state_rows?: unknown; N_trades_entering?: unknown }[];
  economics?: {
    core_state?: string;
    N_trades?: unknown;
    loss_rate?: unknown;
    mean_pnl_hold_after_state?: unknown;
    mean_future_MAE?: unknown;
    mean_future_MFE?: unknown;
    recover_ge_80?: unknown;
    mean_adverse_cents_remaining?: unknown;
    mean_current_price?: unknown;
    mean_price_travel?: unknown;
    mean_minutes_to_worst_price?: unknown;
    mean_minutes_to_settlement?: unknown;
  }[];
  transition_economics?: {
    transition?: string;
    N_trades?: unknown;
    loss_rate?: unknown;
    mean_pnl_hold_after_state?: unknown;
    recover_ge_80?: unknown;
  }[];
  archetype_economics?: {
    archetype?: string;
    N_trades?: unknown;
    loss_rate?: unknown;
    mean_pnl_hold_after_state?: unknown;
  }[];
  remaining_damage?: {
    core_state?: string;
    N_trades?: unknown;
    mean_adverse_cents_remaining?: unknown;
    mean_minutes_to_worst_price?: unknown;
    mean_minutes_to_settlement?: unknown;
  }[];
};

type HazardMember = {
  experiment_id?: string;
  n_entries?: unknown;
  n_terminal_loss_eligible?: unknown;
  n_recovery_t1_eligible?: unknown;
  n_recovery_t2_eligible?: unknown;
  n_recovery_t3_eligible?: unknown;
  n_recovery_t1_unavailable?: unknown;
  metrics?: {
    target?: string;
    family?: string;
    eligible_N?: unknown;
    event_N?: unknown;
    brier?: unknown;
    bss_vs_H0?: unknown;
    log_loss?: unknown;
    roc_auc?: unknown;
  }[];
  by_state?: {
    core_state?: string;
    N?: unknown;
    p_terminal_loss_H1?: unknown;
    p_recovery_t1_H1?: unknown;
    p_recovery_by_t2_H1?: unknown;
    p_recovery_by_t3_H1?: unknown;
  }[];
  by_state_ci?: {
    core_state?: string;
    CI_state?: string;
    N?: unknown;
    p_terminal_loss_H2?: unknown;
    label?: string;
  }[];
  dynamic?: {
    from_state?: string;
    to_state?: string;
    N_trades?: unknown;
    mean_delta_p_loss_H1?: unknown;
    mean_delta_p_recovery_t1_H1?: unknown;
  }[];
  timing_summary?: {
    core_state?: string;
    N?: unknown;
    mean_adverse_cents_remaining?: unknown;
    mean_minutes_to_worst_price?: unknown;
    mean_p_loss?: unknown;
  }[];
  ev_vs_hazard?: { contrast?: string; n?: unknown; spearman?: unknown; ci_lo?: unknown; ci_hi?: unknown }[];
};

type PolicyCandidate = {
  candidate_id?: string;
  required_core_states?: string[];
  p_terminal_loss_condition?: { field?: string; op?: string; value?: unknown } | null;
  p_recovery_condition?: { field?: string; op?: string; value?: unknown } | null;
  rationale?: string;
};

type PolicyEconomics = {
  candidate_id?: string;
  intervention_n?: unknown;
  intervention_rate?: unknown;
  losses_intervened?: unknown;
  winners_intervened?: unknown;
  losses_avoided?: unknown;
  winners_abandoned?: unknown;
  cents_saved?: unknown;
  winner_cents_sacrificed?: unknown;
  dre_value_added?: unknown;
  scenario_b_ev?: unknown;
  delta_vs_hold?: unknown;
  delta_vs_hold_ci_lo?: unknown;
  delta_vs_hold_ci_hi?: unknown;
  median_trigger_price?: unknown;
  median_adverse_cents_remaining?: unknown;
  median_minutes_to_worst?: unknown;
  n_too_late?: unknown;
};

type PolicyPhase5A = {
  status?: string;
  policy_object?: string;
  policy_status?: string;
  policy_selected?: string;
  policy_proposed?: string;
  human_selected_policy?: string;
  freeze_evidence_status?: string;
  freeze_status?: string;
  policy_freeze_hash?: string;
  phase_6_status?: string;
  confirmation_accessed?: boolean;
  confirmation_A?: string;
  confirmation_B?: string;
  phase_2_status?: string;
  phase_3_status?: string;
  phase_4_status?: string;
  note?: string;
  phase5b_note?: string;
  phase5_finalized_status?: string;
  closeout_policy_status?: string;
  human_decision_status?: string;
  candidates?: PolicyCandidate[] | null;
  A?: { experiment_id?: string; economics?: PolicyEconomics[] } | null;
  B?: { experiment_id?: string; economics?: PolicyEconomics[] } | null;
  interpretation?: Record<string, unknown> | null;
};

type ConfirmationGatePhase6 = {
  status?: string;
  gate_id?: string;
  policy_status?: string;
  gate_status?: string;
  A_CONFIRMATION_STATUS?: string;
  B_CONFIRMATION_STATUS?: string;
  confirmation_A_expected_N?: unknown;
  confirmation_B_expected_N?: unknown;
  confirmation_accessed?: boolean;
  note?: string;
};

type ProspectivePhase7 = {
  status?: string;
  experiment_id?: string;
  policy_status?: string;
  collection_status?: string;
  eligible_n?: unknown;
  completed_n?: unknown;
  prospective_lock_hash?: string;
  page3_strategy_id?: string;
  execution_enabled?: boolean;
  note?: string;
};

type HazardPhase4 = {
  status?: string;
  model_id?: string;
  policy_status?: string;
  policy_selected?: string;
  confirmation_accessed?: boolean;
  confirmation_A?: string;
  confirmation_B?: string;
  phase_2_status?: string;
  phase_2_actionability?: string;
  phase_3_status?: string;
  phase_3_result?: string;
  note?: string;
  A?: HazardMember | null;
  B?: HazardMember | null;
  interpretation?: Record<string, unknown> | null;
};

type DownfallPhase3 = {
  status?: string;
  model_id?: string;
  policy_status?: string;
  policy_selected?: string;
  confirmation_accessed?: boolean;
  confirmation_A?: string;
  confirmation_B?: string;
  hazard_model_built?: boolean;
  phase_2_actionability_gate?: string;
  note?: string;
  A?: DownfallMember | null;
  B?: DownfallMember | null;
  interpretation?: Record<string, unknown> | null;
};

type ExperimentDetail = {
  experiment_id?: string;
  slice?: string;
  n_lock?: number;
  live_feed?: string;
  execution?: string;
  submits?: boolean;
  fill_status?: string;
  page3_n280_queried?: boolean;
  policy_freeze?: { policy_id?: string; policy_hash?: string; confirmation_read?: boolean } | null;
  confirmation?: {
    present?: boolean;
    label?: string;
    statistics?: Record<string, unknown> | null;
    report_md?: string | null;
  };
  discovery?: {
    present?: boolean;
    label?: string;
    statistics?: Record<string, unknown> | null;
    report_md?: string | null;
  };
  note?: string;
};

function Row({ label, value }: { label: string; value: unknown }) {
  return (
    <div className="row">
      <dt>{label}</dt>
      <dd>{text(value)}</dd>
    </div>
  );
}

function StatsBlock({ title, stats, discovery }: { title: string; stats: Record<string, unknown> | null | undefined; discovery?: boolean }) {
  if (!stats) {
    return (
      <article>
        <h2>{title}</h2>
        <p className="muted">{discovery ? "DISCOVERY artifacts not written yet." : "NOT RUN"}</p>
      </article>
    );
  }
  const hold = (stats.baseline_hold || {}) as Record<string, unknown>;
  const cov = (stats.coverage || {}) as Record<string, unknown>;
  const warn = (stats.warning || {}) as Record<string, unknown>;
  const policies = (stats.policies || {}) as Record<string, Record<string, unknown>>;
  return (
    <article className="wide">
      <h2>{title}</h2>
      <div className="stat-row">
        <div className="stat">
          <dt>N games</dt>
          <dd>{text(stats.N_games)}</dd>
        </div>
        <div className="stat">
          <dt>N trades</dt>
          <dd>{text(stats.N_trades)}</dd>
        </div>
        <div className="stat">
          <dt>N state observations</dt>
          <dd>{text(stats.N_state_observations)}</dd>
        </div>
        <div className="stat">
          <dt>BASELINE_HOLD EV ¢</dt>
          <dd>{text(hold.ev_cents)}</dd>
        </div>
      </div>
      <div className="stat-row second">
        <div className="stat">
          <dt>path complete</dt>
          <dd>{text(cov.N_path_complete)}</dd>
        </div>
        <div className="stat">
          <dt>path partial</dt>
          <dd>{text(cov.N_path_partial)}</dd>
        </div>
        <div className="stat">
          <dt>path unavailable</dt>
          <dd>{text(cov.N_path_unavailable)}</dd>
        </div>
        <div className="stat">
          <dt>warning median min</dt>
          <dd>{text(warn.median_minutes)}</dd>
        </div>
      </div>
      <h3>Policy economics vs BASELINE_HOLD</h3>
      <table className="data-table">
        <thead>
          <tr>
            <th>policy</th>
            <th>hyp EV ¢</th>
            <th>Δ CI</th>
            <th>intervene</th>
            <th>abandoned</th>
            <th>avoided</th>
            <th>¢ saved</th>
            <th>¢ sacrificed</th>
          </tr>
        </thead>
        <tbody>
          {Object.entries(policies).map(([id, row]) => {
            const hyp = (row.policy_hypothetical_b || {}) as Record<string, unknown>;
            const ci = ((row.delta_ci || {}) as { ci?: unknown }).ci;
            return (
              <tr key={id}>
                <td>{id}</td>
                <td>{text(hyp.ev_cents)}</td>
                <td>{text(ci)}</td>
                <td>{text(row.intervention_rate)}</td>
                <td>{text(row.winners_abandoned)}</td>
                <td>{text(row.losses_avoided)}</td>
                <td>{text(row.cents_saved)}</td>
                <td>{text(row.cents_sacrificed)}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </article>
  );
}

function DownfallBlock({ letter, member }: { letter: string; member: DownfallMember | null | undefined }) {
  if (!member?.economics) {
    return (
      <article>
        <h3>{letter}</h3>
        <p className="muted">Phase 3 artifacts not written yet.</p>
      </article>
    );
  }
  return (
    <article className="wide">
      <h3>{letter} · {text(member.experiment_id)}</h3>
      <h4>CURRENT STATE LANGUAGE</h4>
      <table className="data-table">
        <thead>
          <tr>
            <th>state</th>
            <th>N first entries</th>
            <th>loss rate</th>
            <th>mean PNL</th>
            <th>MAE</th>
            <th>MFE</th>
            <th>recover≥80</th>
          </tr>
        </thead>
        <tbody>
          {(member.economics || []).map((row) => (
            <tr key={`${letter}-${row.core_state}`}>
              <td>{text(row.core_state)}</td>
              <td>{text(row.N_trades)}</td>
              <td>{text(row.loss_rate)}</td>
              <td>{text(row.mean_pnl_hold_after_state)}</td>
              <td>{text(row.mean_future_MAE)}</td>
              <td>{text(row.mean_future_MFE)}</td>
              <td>{text(row.recover_ge_80)}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <h4>STATE TRANSITIONS</h4>
      <table className="data-table">
        <thead>
          <tr>
            <th>branch</th>
            <th>N</th>
            <th>loss rate</th>
            <th>mean PNL</th>
            <th>recover≥80</th>
          </tr>
        </thead>
        <tbody>
          {(member.transition_economics || []).map((row) => (
            <tr key={`${letter}-${row.transition}`}>
              <td>{text(row.transition)}</td>
              <td>{text(row.N_trades)}</td>
              <td>{text(row.loss_rate)}</td>
              <td>{text(row.mean_pnl_hold_after_state)}</td>
              <td>{text(row.recover_ge_80)}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <h4>PATH ARCHETYPES</h4>
      <table className="data-table">
        <thead>
          <tr>
            <th>archetype</th>
            <th>N</th>
            <th>loss rate</th>
            <th>mean PNL</th>
          </tr>
        </thead>
        <tbody>
          {(member.archetype_economics || []).map((row) => (
            <tr key={`${letter}-${row.archetype}`}>
              <td>{text(row.archetype)}</td>
              <td>{text(row.N_trades)}</td>
              <td>{text(row.loss_rate)}</td>
              <td>{text(row.mean_pnl_hold_after_state)}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <h4>REMAINING DAMAGE</h4>
      <table className="data-table">
        <thead>
          <tr>
            <th>state</th>
            <th>N</th>
            <th>adverse ¢ remaining</th>
            <th>minutes to worst</th>
            <th>minutes to settlement</th>
          </tr>
        </thead>
        <tbody>
          {(member.remaining_damage || []).map((row) => (
            <tr key={`${letter}-dmg-${row.core_state}`}>
              <td>{text(row.core_state)}</td>
              <td>{text(row.N_trades)}</td>
              <td>{text(row.mean_adverse_cents_remaining)}</td>
              <td>{text(row.mean_minutes_to_worst_price)}</td>
              <td>{text(row.mean_minutes_to_settlement)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </article>
  );
}

function HazardBlock({ letter, member }: { letter: string; member: HazardMember | null | undefined }) {
  if (!member) {
    return (
      <article>
        <h3>{letter}</h3>
        <p className="muted">DISCOVERY artifacts not written yet.</p>
      </article>
    );
  }
  const loss = (member.metrics || []).filter((r) => r.target === "TARGET_terminal_loss");
  return (
    <article className="wide">
      <h3>{letter} · {text(member.experiment_id)}</h3>
      <div className="stat-row">
        <div className="stat">
          <dt>state entries</dt>
          <dd>{text(member.n_entries)}</dd>
        </div>
        <div className="stat">
          <dt>terminal-loss N</dt>
          <dd>{text(member.n_terminal_loss_eligible)}</dd>
        </div>
        <div className="stat">
          <dt>recovery t1 N</dt>
          <dd>{text(member.n_recovery_t1_eligible)}</dd>
        </div>
        <div className="stat">
          <dt>recovery t1 unavailable</dt>
          <dd>{text(member.n_recovery_t1_unavailable)}</dd>
        </div>
      </div>
      <h4>TERMINAL LOSS</h4>
      <table className="data-table">
        <thead>
          <tr>
            <th>family</th>
            <th>N</th>
            <th>events</th>
            <th>Brier</th>
            <th>BSS vs H0</th>
            <th>log loss</th>
          </tr>
        </thead>
        <tbody>
          {loss.map((row) => (
            <tr key={`${letter}-loss-${row.family}`}>
              <td>{text(row.family)}</td>
              <td>{text(row.eligible_N)}</td>
              <td>{text(row.event_N)}</td>
              <td>{text(row.brier)}</td>
              <td>{text(row.bss_vs_H0)}</td>
              <td>{text(row.log_loss)}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <h4>STATE × RECOVERY T1/T2/T3</h4>
      <table className="data-table">
        <thead>
          <tr>
            <th>state</th>
            <th>N</th>
            <th>p loss</th>
            <th>p rec t1</th>
            <th>p rec t2</th>
            <th>p rec t3</th>
          </tr>
        </thead>
        <tbody>
          {(member.by_state || []).map((row) => (
            <tr key={`${letter}-st-${row.core_state}`}>
              <td>{text(row.core_state)}</td>
              <td>{text(row.N)}</td>
              <td>{text(row.p_terminal_loss_H1)}</td>
              <td>{text(row.p_recovery_t1_H1)}</td>
              <td>{text(row.p_recovery_by_t2_H1)}</td>
              <td>{text(row.p_recovery_by_t3_H1)}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <h4>STATE × CI</h4>
      <table className="data-table">
        <thead>
          <tr>
            <th>state</th>
            <th>CI</th>
            <th>N</th>
            <th>p loss H2</th>
            <th>label</th>
          </tr>
        </thead>
        <tbody>
          {(member.by_state_ci || []).map((row) => (
            <tr key={`${letter}-ci-${row.core_state}-${row.CI_state}`}>
              <td>{text(row.core_state)}</td>
              <td>{text(row.CI_state)}</td>
              <td>{text(row.N)}</td>
              <td>{text(row.p_terminal_loss_H2)}</td>
              <td>{text(row.label)}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <h4>TRAJECTORIES / UPDATES</h4>
      <table className="data-table">
        <thead>
          <tr>
            <th>from</th>
            <th>to</th>
            <th>N</th>
            <th>Δ p loss</th>
            <th>Δ p recovery t1</th>
          </tr>
        </thead>
        <tbody>
          {(member.dynamic || []).map((row) => (
            <tr key={`${letter}-dyn-${row.from_state}-${row.to_state}`}>
              <td>{text(row.from_state)}</td>
              <td>{text(row.to_state)}</td>
              <td>{text(row.N_trades)}</td>
              <td>{text(row.mean_delta_p_loss_H1)}</td>
              <td>{text(row.mean_delta_p_recovery_t1_H1)}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <h4>TIMING / SUPPORT</h4>
      <table className="data-table">
        <thead>
          <tr>
            <th>state</th>
            <th>N</th>
            <th>adverse ¢ remaining</th>
            <th>minutes to worst</th>
            <th>mean p loss</th>
          </tr>
        </thead>
        <tbody>
          {(member.timing_summary || []).map((row) => (
            <tr key={`${letter}-time-${row.core_state}`}>
              <td>{text(row.core_state)}</td>
              <td>{text(row.N)}</td>
              <td>{text(row.mean_adverse_cents_remaining)}</td>
              <td>{text(row.mean_minutes_to_worst_price)}</td>
              <td>{text(row.mean_p_loss)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </article>
  );
}

function PersistenceBlock({ letter, member }: { letter: string; member: PersistenceMember | null | undefined }) {
  if (!member?.economics) {
    return (
      <article>
        <h3>{letter}</h3>
        <p className="muted">DISCOVERY artifacts not written yet.</p>
      </article>
    );
  }
  const econ = member.economics;
  const temp = econ.temporary || {};
  const pers = econ.persistent || {};
  const delta = econ.persistent_minus_temporary || {};
  return (
    <article className="wide">
      <h3>{letter} · {text(member.experiment_id)}</h3>
      <div className="stat-row">
        <div className="stat">
          <dt>first negative</dt>
          <dd>{text(econ.n_first_negative)}</dd>
        </div>
        <div className="stat">
          <dt>TEMPORARY_NEGATIVE_EV</dt>
          <dd>{text(econ.n_temporary)}</dd>
        </div>
        <div className="stat">
          <dt>PERSISTENT_NEGATIVE_EV</dt>
          <dd>{text(econ.n_persistent)}</dd>
        </div>
        <div className="stat">
          <dt>UNRESOLVED</dt>
          <dd>{text(econ.n_unresolved)}</dd>
        </div>
      </div>
      <h4>ECONOMIC SEPARATION</h4>
      <table className="data-table">
        <thead>
          <tr>
            <th>class</th>
            <th>wins</th>
            <th>losses</th>
            <th>mean PNL</th>
            <th>T40</th>
            <th>MAE</th>
            <th>MFE</th>
          </tr>
        </thead>
        <tbody>
          <tr>
            <td>TEMPORARY_NEGATIVE_EV</td>
            <td>{text(temp.N_wins)}</td>
            <td>{text(temp.N_losses)}</td>
            <td>{text(temp.mean_pnl_hold_after_t0)}</td>
            <td>{text(temp.T40_rate)}</td>
            <td>{text(temp.mean_future_MAE)}</td>
            <td>{text(temp.mean_future_MFE)}</td>
          </tr>
          <tr>
            <td>PERSISTENT_NEGATIVE_EV</td>
            <td>{text(pers.N_wins)}</td>
            <td>{text(pers.N_losses)}</td>
            <td>{text(pers.mean_pnl_hold_after_t0)}</td>
            <td>{text(pers.T40_rate)}</td>
            <td>{text(pers.mean_future_MAE)}</td>
            <td>{text(pers.mean_future_MFE)}</td>
          </tr>
        </tbody>
      </table>
      <p className="muted">
        PERSISTENT − TEMPORARY Δ PNL {text(delta.pnl?.observed_delta)} CI {text(delta.pnl?.ci)} {text(delta.pnl?.classification)}
      </p>
      <h4>PIT DIFFERENCES</h4>
      <table className="data-table">
        <thead>
          <tr>
            <th>feature</th>
            <th>temporary mean</th>
            <th>persistent mean</th>
            <th>difference</th>
            <th>class</th>
          </tr>
        </thead>
        <tbody>
          {(member.pit_comparison || []).slice(0, 8).map((row) => (
            <tr key={`${letter}-${row.feature}`}>
              <td>{text(row.feature)}</td>
              <td>{text(row.temporary_mean)}</td>
              <td>{text(row.persistent_mean)}</td>
              <td>{text(row.difference)}</td>
              <td>{text(row.classification)}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <h4>PERSISTENCE LANDMARKS</h4>
      <table className="data-table">
        <thead>
          <tr>
            <th>landmark</th>
            <th>N</th>
            <th>loss rate</th>
            <th>mean PNL</th>
            <th>T40</th>
          </tr>
        </thead>
        <tbody>
          {(member.landmarks || []).map((row) => (
            <tr key={`${letter}-${row.landmark}`}>
              <td>{text(row.landmark)}</td>
              <td>{text(row.N_trades)}</td>
              <td>{text(row.loss_rate)}</td>
              <td>{text(row.mean_pnl_hold_after_t0)}</td>
              <td>{text(row.T40_rate)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </article>
  );
}

function PolicyBlock({ letter, member }: { letter: string; member: { experiment_id?: string; economics?: PolicyEconomics[] } | null | undefined }) {
  const rows = member?.economics || [];
  if (!rows.length) {
    return (
      <article>
        <h3>{letter}</h3>
        <p className="muted">DISCOVERY artifacts not written yet.</p>
      </article>
    );
  }
  return (
    <article className="wide">
      <h3>{letter} · {text(member?.experiment_id)}</h3>
      <table className="data-table">
        <thead>
          <tr>
            <th>candidate</th>
            <th>trigger N</th>
            <th>rate</th>
            <th>losses intervened</th>
            <th>winners intervened</th>
            <th>scenario B EV</th>
            <th>Δ vs baseline hold</th>
            <th>95% CI</th>
            <th>losses avoided</th>
            <th>winner ¢ sacrificed</th>
            <th>DRE value added</th>
            <th>median trigger price</th>
            <th>median adverse ¢</th>
            <th>median minutes to worst</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={`${letter}-${row.candidate_id}`}>
              <td>{text(row.candidate_id)}</td>
              <td>{text(row.intervention_n)}</td>
              <td>{text(row.intervention_rate)}</td>
              <td>{text(row.losses_intervened)}</td>
              <td>{text(row.winners_intervened)}</td>
              <td>{text(row.scenario_b_ev)}</td>
              <td>{text(row.delta_vs_hold)}</td>
              <td>[{text(row.delta_vs_hold_ci_lo)}, {text(row.delta_vs_hold_ci_hi)}]</td>
              <td>{text(row.losses_avoided)}</td>
              <td>{text(row.winner_cents_sacrificed)}</td>
              <td>{text(row.dre_value_added)}</td>
              <td>{text(row.median_trigger_price)}</td>
              <td>{text(row.median_adverse_cents_remaining)}</td>
              <td>{text(row.median_minutes_to_worst)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </article>
  );
}

export default function RiskReport() {
  const [suite, setSuite] = useState<Record<string, unknown> | null>(null);
  const [details, setDetails] = useState<ExperimentDetail[]>([]);
  const [persist, setPersist] = useState<PersistenceAudit | null>(null);
  const [phase2, setPhase2] = useState<PersistenceAudit | null>(null);
  const [phase3, setPhase3] = useState<DownfallPhase3 | null>(null);
  const [phase4, setPhase4] = useState<HazardPhase4 | null>(null);
  const [phase5, setPhase5] = useState<PolicyPhase5A | null>(null);
  const [phase6, setPhase6] = useState<ConfirmationGatePhase6 | null>(null);
  const [phase7, setPhase7] = useState<ProspectivePhase7 | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancel = false;
    fetchDre<Record<string, unknown>>("experiments")
      .then(async (payload) => {
        const members = (payload.members || []) as Member[];
        const rows = await Promise.all(
          members.map((m) => fetchDre<ExperimentDetail>(`experiments/${encodeURIComponent(m.experiment_id)}`)),
        );
        const audit = await fetchDre<PersistenceAudit>("experiments/AUSTIN_PERSISTENCE_MECHANISM_AUDIT_V1");
        const phase = await fetchDre<PersistenceAudit>("experiments/AUSTIN_PERSISTENCE_MECHANISM_V1");
        const downfall = await fetchDre<DownfallPhase3>("experiments/AUSTIN_DOWNFALL_STATE_MODEL_V1");
        const hazard = await fetchDre<HazardPhase4>("experiments/AUSTIN_LOSS_HAZARD_RECOVERY_MODEL_V1");
        const policy = await fetchDre<PolicyPhase5A>("experiments/AUSTIN_DRE_POLICY_V2");
        const gate = await fetchDre<ConfirmationGatePhase6>("experiments/AUSTIN_CONFIRMATION_GATE_V1");
        const prospective = await fetchDre<ProspectivePhase7>("experiments/AUSTIN_NBA_2026_27_PROSPECTIVE_V1");
        if (cancel) return;
        setSuite(payload);
        setDetails(rows);
        setPersist(audit);
        setPhase2(phase);
        setPhase3(downfall);
        setPhase4(hazard);
        setPhase5(policy);
        setPhase6(gate);
        setPhase7(prospective);
      })
      .catch((err: unknown) => {
        if (!cancel) setError(err instanceof DreError ? err.message : String(err));
      });
    return () => {
      cancel = true;
    };
  }, []);

  const page3 = (suite?.page3_control || {}) as Record<string, unknown>;
  const freeze = (suite?.policy_freeze || null) as { policy_id?: string; policy_hash?: string } | null;

  return (
    <div>
      {error ? <div className="banner is-bad">{error}</div> : null}
      <div className="page-meta">
        <span className="pill">AUSTIN · CONDITIONAL RISK VALIDATION</span>
        <span className="pill">CROSS-DOMAIN TRANSFER TEST</span>
        <span className="pill">PAGE 3 = CONTROL · PAGE 4 = RISK EXPERIMENT</span>
        <span className="pill">TRAINING N=604 · TEST ≠ TRAINING</span>
        <span className="pill">LIVE FEED UNAVAILABLE</span>
        <span className="pill">EXECUTION DISABLED</span>
        <span className="pill">FILL_UNAVAILABLE</span>
      </div>
      <p className="muted" style={{ marginTop: 14 }}>
        Frozen NBA Austin model queried on locked NCAAB H1_2 and H2_1. Confirmation is the headline when present.
        Discovery is labeled DISCOVERY. Members are never combined into one OOS result.
      </p>
      <div className="grid" style={{ marginTop: 18 }}>
        <article>
          <h2>Page 3 control</h2>
          <Row label="N" value={page3.n} />
          <Row label="S" value={page3.s} />
          <Row label="EV ¢" value={page3.ev_cents} />
          <Row label="book ¢" value={page3.book_cents} />
          <Row label="role" value={page3.role} />
          <Row label="queried" value={page3.queried} />
        </article>
        <article>
          <h2>Suite freeze</h2>
          <Row label="suite" value={suite?.suite_id} />
          <Row label="policy" value={freeze?.policy_id || "NOT FROZEN"} />
          <Row label="policy hash" value={freeze?.policy_hash} />
          <Row label="submits" value={suite?.submits} />
          <Row label="live feed" value={suite?.live_feed} />
          <Row label="execution" value={suite?.execution} />
        </article>
      </div>
      <section style={{ marginTop: 22 }}>
        <h2>PHASE 2 · PERSISTENCE MECHANISM</h2>
        <div className="page-meta">
          <span className="pill">DISCOVERY ONLY</span>
          <span className="pill">MODEL FROZEN</span>
          <span className="pill">POLICY UNFROZEN</span>
          <span className="pill">CONFIRMATION UNTOUCHED</span>
          <span className="pill">EXECUTION DISABLED</span>
        </div>
        <p className="muted">{phase2?.note || "Read-only. No action."}</p>
        <div className="grid" style={{ marginTop: 14 }}>
          <article>
            <h3>Phase 2 lock</h3>
            <Row label="status" value={phase2?.status} />
            <Row label="policy" value={phase2?.policy_status} />
            <Row label="selected" value={phase2?.policy_selected} />
            <Row label="confirmation accessed" value={phase2?.confirmation_accessed} />
            <Row label="confirmation A" value={phase2?.confirmation_A} />
            <Row label="confirmation B" value={phase2?.confirmation_B} />
          </article>
          <article>
            <h3>Gates</h3>
            <Row label="A economics" value={phase2?.interpretation?.gate_a_persistence_economics} />
            <Row label="B PIT" value={phase2?.interpretation?.gate_b_pit_distinguishability} />
            <Row label="C timing" value={phase2?.interpretation?.gate_c_timing} />
            <Row label="D alignment" value={phase2?.interpretation?.gate_d_data_integrity} />
            <Row label="Phase 3 justified" value={phase2?.interpretation?.phase_3_justified} />
          </article>
        </div>
        <PersistenceBlock letter="A · H1_2" member={phase2?.A} />
        <PersistenceBlock letter="B · H2_1" member={phase2?.B} />
      </section>
      <section style={{ marginTop: 22 }}>
        <h2>PHASE 3 · DOWNFALL STATE MODEL</h2>
        <div className="page-meta">
          <span className="pill">RESEARCH ONLY</span>
          <span className="pill">MODEL FROZEN</span>
          <span className="pill">POLICY UNFROZEN</span>
          <span className="pill">CONFIRMATION UNTOUCHED</span>
          <span className="pill">HAZARD MODEL NOT BUILT</span>
          <span className="pill">EXECUTION DISABLED</span>
        </div>
        <p className="muted">{phase3?.note || "Read-only. No action."}</p>
        <div className="grid" style={{ marginTop: 14 }}>
          <article>
            <h3>Phase 3 lock</h3>
            <Row label="status" value={phase3?.status} />
            <Row label="policy" value={phase3?.policy_status} />
            <Row label="selected" value={phase3?.policy_selected} />
            <Row label="confirmation accessed" value={phase3?.confirmation_accessed} />
            <Row label="confirmation A" value={phase3?.confirmation_A} />
            <Row label="confirmation B" value={phase3?.confirmation_B} />
            <Row label="hazard model" value={phase3?.hazard_model_built ? "BUILT" : "NOT BUILT"} />
            <Row label="Phase 2 actionability" value={phase3?.phase_2_actionability_gate} />
          </article>
          <article>
            <h3>Gates</h3>
            <Row label="A validity" value={phase3?.interpretation?.gate_a_state_validity} />
            <Row label="B economics" value={phase3?.interpretation?.gate_b_economic_separation} />
            <Row label="C transitions" value={phase3?.interpretation?.gate_c_transition_information} />
            <Row label="D remaining damage" value={phase3?.interpretation?.gate_d_timing_remaining_damage} />
            <Row label="Phase 4" value={phase3?.interpretation?.phase_4_decision} />
          </article>
        </div>
        <div className="grid" style={{ marginTop: 14 }}>
          <article>
            <h3>RECOVERY BRANCH</h3>
            <p className="muted">WATCH_NEGATIVE → RECOVERING and PERSISTENCE_2 → RECOVERING. Descriptive only.</p>
          </article>
          <article>
            <h3>DEEPER-DISTRESS BRANCH</h3>
            <p className="muted">WATCH_NEGATIVE → PERSISTENCE_2 and PERSISTENCE_2 → PERSISTENCE_3PLUS. Descriptive only.</p>
          </article>
        </div>
        <DownfallBlock letter="A · H1_2" member={phase3?.A} />
        <DownfallBlock letter="B · H2_1" member={phase3?.B} />
      </section>
      <section style={{ marginTop: 22 }}>
        <h2>PHASE 4 · LOSS HAZARD / RECOVERY</h2>
        <div className="page-meta">
          <span className="pill">DISCOVERY ONLY</span>
          <span className="pill">PHASE 2 FINALIZED</span>
          <span className="pill">PHASE 3 COMPLETE</span>
          <span className="pill">HAZARD MODEL RESEARCH ONLY</span>
          <span className="pill">POLICY UNFROZEN</span>
          <span className="pill">CONFIRMATION UNTOUCHED</span>
          <span className="pill">EXECUTION DISABLED</span>
        </div>
        <p className="muted">{phase4?.note || "Read-only. No action."}</p>
        <div className="grid" style={{ marginTop: 14 }}>
          <article>
            <h3>Phase 4 lock</h3>
            <Row label="status" value={phase4?.status} />
            <Row label="policy" value={phase4?.policy_status} />
            <Row label="selected" value={phase4?.policy_selected} />
            <Row label="confirmation accessed" value={phase4?.confirmation_accessed} />
            <Row label="confirmation A" value={phase4?.confirmation_A} />
            <Row label="confirmation B" value={phase4?.confirmation_B} />
            <Row label="Phase 2" value={phase4?.phase_2_status} />
            <Row label="Phase 2 actionability" value={phase4?.phase_2_actionability} />
            <Row label="Phase 3" value={phase4?.phase_3_status} />
            <Row label="Phase 3 result" value={phase4?.phase_3_result} />
          </article>
          <article>
            <h3>Gates</h3>
            <Row label="A validity" value={phase4?.interpretation?.gate_a_probability_validity} />
            <Row label="B terminal loss" value={phase4?.interpretation?.gate_b_terminal_loss_information} />
            <Row label="C recovery" value={phase4?.interpretation?.gate_c_recovery_information} />
            <Row label="D update" value={phase4?.interpretation?.gate_d_dynamic_update} />
            <Row label="E timing" value={phase4?.interpretation?.gate_e_timing} />
            <Row label="F transfer" value={phase4?.interpretation?.gate_f_transfer_support} />
            <Row label="Phase 5" value={phase4?.interpretation?.phase_5_decision} />
          </article>
        </div>
        <HazardBlock letter="A · H1_2" member={phase4?.A} />
        <HazardBlock letter="B · H2_1" member={phase4?.B} />
      </section>
      <section style={{ marginTop: 22 }}>
        <h2>PHASE 5A · DRE POLICY PREREGISTRATION</h2>
        <div className="page-meta">
          <span className="pill">DISCOVERY ONLY</span>
          <span className="pill">POLICY UNFROZEN</span>
          <span className="pill">CONFIRMATION UNTOUCHED</span>
          <span className="pill">SCENARIO ≠ FILL</span>
          <span className="pill">EXECUTION DISABLED</span>
        </div>
        <p className="muted">{phase5?.note || "Read-only. No action."}</p>
        <div className="grid" style={{ marginTop: 14 }}>
          <article>
            <h3>Phase 5A lock</h3>
            <Row label="status" value={phase5?.status} />
            <Row label="policy" value={phase5?.policy_status} />
            <Row label="selected" value={phase5?.policy_selected} />
            <Row label="proposed" value={phase5?.policy_proposed} />
            <Row label="confirmation accessed" value={phase5?.confirmation_accessed} />
            <Row label="confirmation A" value={phase5?.confirmation_A} />
            <Row label="confirmation B" value={phase5?.confirmation_B} />
            <Row label="Phase 2" value={phase5?.phase_2_status} />
            <Row label="Phase 3" value={phase5?.phase_3_status} />
            <Row label="Phase 4" value={phase5?.phase_4_status} />
          </article>
          <article>
            <h3>Gates</h3>
            <Row label="A determinism" value={phase5?.interpretation?.gate_a_determinism} />
            <Row label="B mechanism" value={phase5?.interpretation?.gate_b_mechanism_consistency} />
            <Row label="C economics" value={phase5?.interpretation?.gate_c_discovery_economics} />
            <Row label="D winner preservation" value={phase5?.interpretation?.gate_d_winner_preservation} />
            <Row label="E timing" value={phase5?.interpretation?.gate_e_timing} />
            <Row label="F transfer" value={phase5?.interpretation?.gate_f_transfer_support} />
            <Row label="human freeze justified" value={phase5?.interpretation?.human_freeze_justified} />
          </article>
        </div>
        <article style={{ marginTop: 14 }}>
          <h3>Candidate definitions</h3>
          <p className="muted">Hazard basis is frozen Phase 4 H1 only. INTERVENE is hypothetical. No action buttons.</p>
          <table className="data-table">
            <thead>
              <tr>
                <th>candidate</th>
                <th>states</th>
                <th>loss hazard</th>
                <th>recovery</th>
                <th>rationale</th>
              </tr>
            </thead>
            <tbody>
              {(phase5?.candidates || []).map((row) => (
                <tr key={row.candidate_id}>
                  <td>{text(row.candidate_id)}</td>
                  <td>{(row.required_core_states || []).join(", ")}</td>
                  <td>{row.p_terminal_loss_condition ? `${text(row.p_terminal_loss_condition.field)} ${text(row.p_terminal_loss_condition.op)} ${text(row.p_terminal_loss_condition.value)}` : "none"}</td>
                  <td>{row.p_recovery_condition ? `${text(row.p_recovery_condition.field)} ${text(row.p_recovery_condition.op)} ${text(row.p_recovery_condition.value)}` : "none"}</td>
                  <td>{text(row.rationale)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </article>
        <PolicyBlock letter="A · H1_2" member={phase5?.A} />
        <PolicyBlock letter="B · H2_1" member={phase5?.B} />
      </section>
      <section style={{ marginTop: 22 }}>
        <h2>PHASE 5B · POLICY FREEZE</h2>
        <div className="page-meta">
          <span className="pill">POLICY FREEZE GATE</span>
          <span className="pill">CONFIRMATION UNTOUCHED</span>
          <span className="pill">EXECUTION DISABLED</span>
        </div>
        <p className="muted">{phase5?.phase5b_note || "Read-only. No action."}</p>
        <div className="grid" style={{ marginTop: 14 }}>
          <article>
            <h3>Phase 5B lock</h3>
            <Row label="Phase 5A proposed policy" value={phase5?.policy_proposed} />
            <Row label="human-selected policy" value={phase5?.human_selected_policy || "UNSET"} />
            <Row label="human decision status" value={phase5?.human_decision_status} />
            <Row label="PHASE5_FINALIZED" value={phase5?.phase5_finalized_status || "NOT_WRITTEN"} />
            <Row label="closeout policy" value={phase5?.closeout_policy_status || phase5?.policy_status} />
            <Row label="freeze evidence status" value={phase5?.freeze_evidence_status} />
            <Row label="freeze status" value={phase5?.freeze_status || "NOT_WRITTEN"} />
            <Row label="policy freeze hash" value={phase5?.policy_freeze_hash} />
            <Row label="confirmation A" value={phase5?.confirmation_A} />
            <Row label="confirmation B" value={phase5?.confirmation_B} />
            <Row label="Phase 6 status" value={phase5?.phase_6_status} />
          </article>
          <article>
            <h3>Gate</h3>
            <p className="muted">Human authorization is a prompt value, not a dashboard control. No confirmation trigger.</p>
          </article>
        </div>
      </section>
      <section style={{ marginTop: 22 }}>
        <h2>PHASE 6 · CONFIRMATION SEALED</h2>
        <div className="page-meta">
          <span className="pill">NO POLICY FROZEN</span>
          <span className="pill">A 97 UNSPENT</span>
          <span className="pill">B 70 UNSPENT</span>
          <span className="pill">EXECUTION DISABLED</span>
        </div>
        <p className="muted">{phase6?.note || "Read-only. No action."}</p>
        <div className="grid" style={{ marginTop: 14 }}>
          <article>
            <h3>Phase 6 lock</h3>
            <Row label="status" value={phase6?.gate_status || phase6?.status} />
            <Row label="policy" value={phase6?.policy_status} />
            <Row label="A confirmation" value={phase6?.A_CONFIRMATION_STATUS} />
            <Row label="A expected N" value={phase6?.confirmation_A_expected_N} />
            <Row label="B confirmation" value={phase6?.B_CONFIRMATION_STATUS} />
            <Row label="B expected N" value={phase6?.confirmation_B_expected_N} />
            <Row label="confirmation accessed" value={phase6?.confirmation_accessed} />
          </article>
          <article>
            <h3>Gate</h3>
            <p className="muted">Preservation is the result. No confirmation run control.</p>
          </article>
        </div>
      </section>
      <section style={{ marginTop: 22 }}>
        <h2>PHASE 7 · SHADOW RESEARCH</h2>
        <div className="page-meta">
          <span className="pill">NO POLICY</span>
          <span className="pill">NO EXECUTION</span>
          <span className="pill">NO HISTORICAL BACKFILL</span>
          <span className="pill">LOCKED</span>
          <span className="pill">ARMED</span>
        </div>
        <p className="muted">{phase7?.note || "Read-only. No action."}</p>
        <div className="grid" style={{ marginTop: 14 }}>
          <article>
            <h3>Phase 7 lock</h3>
            <Row label="collection" value={phase7?.collection_status} />
            <Row label="policy" value={phase7?.policy_status} />
            <Row label="Page 3" value={phase7?.page3_strategy_id} />
            <Row label="eligible N" value={phase7?.eligible_n} />
            <Row label="completed N" value={phase7?.completed_n} />
            <Row label="lock hash" value={phase7?.prospective_lock_hash} />
            <Row label="execution enabled" value={phase7?.execution_enabled} />
          </article>
          <article>
            <h3>Harness</h3>
            <p className="muted">Armed waiting for data. No ingest. No trading control.</p>
          </article>
        </div>
      </section>
      <section style={{ marginTop: 22 }}>
        <h2>PERSISTENCE MECHANISM AUDIT</h2>
        <div className="page-meta">
          <span className="pill">DISCOVERY ONLY</span>
          <span className="pill">POLICY UNFROZEN</span>
          <span className="pill">CONFIRMATION UNTOUCHED</span>
          <span className="pill">EXECUTION DISABLED</span>
        </div>
        <p className="muted">{persist?.note || "Read-only. No action."}</p>
        <div className="grid" style={{ marginTop: 14 }}>
          <article>
            <h3>Audit lock</h3>
            <Row label="status" value={persist?.status} />
            <Row label="policy" value={persist?.policy_status} />
            <Row label="selected" value={persist?.policy_selected} />
            <Row label="confirmation accessed" value={persist?.confirmation_accessed} />
            <Row label="confirmation A" value={persist?.confirmation_A} />
            <Row label="confirmation B" value={persist?.confirmation_B} />
          </article>
          <article>
            <h3>H2_1 ALIGNMENT STATUS</h3>
            <Row label="status" value={persist?.alignment?.status} />
            <Row label="defect" value={persist?.alignment?.potential_data_alignment_defect} />
            <Row label="clock-wall mismatch N" value={persist?.alignment?.n_clock_wall_mismatch} />
            <Row label="aligned N" value={persist?.alignment?.n_aligned} />
          </article>
        </div>
        <PersistenceBlock letter="A · H1_2" member={persist?.A} />
        <PersistenceBlock letter="B · H2_1" member={persist?.B} />
      </section>
      {details.map((row) => (
        <section key={row.experiment_id} style={{ marginTop: 22 }}>
          <h2>
            {row.slice} · {row.experiment_id} · locked N={text(row.n_lock)}
          </h2>
          <p className="muted">{row.note}</p>
          <StatsBlock
            title="Confirmation"
            stats={row.confirmation?.statistics as Record<string, unknown> | null}
          />
          <StatsBlock
            title="DISCOVERY"
            stats={row.discovery?.statistics as Record<string, unknown> | null}
            discovery
          />
        </section>
      ))}
    </div>
  );
}
