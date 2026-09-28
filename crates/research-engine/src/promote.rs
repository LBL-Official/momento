use chrono::Utc;
use uuid::Uuid;

use crate::error::EngineError;
use crate::store::EngineStore;
use crate::types::{LifecycleStatus, PromotionRecord};

/// Explicit promotion graph. CANDIDATE cannot jump to PRODUCTION.
pub fn allowed_transition(from: LifecycleStatus, to: LifecycleStatus) -> bool {
    use LifecycleStatus::*;
    if from == to {
        return true;
    }
    if to == Retired
        && matches!(
            from,
            Approved | Production | Paper | Shadow | RobustCandidate
        )
    {
        return true;
    }
    if to == Rejected
        && matches!(
            from,
            Completed | Hypothesis | Candidate | RobustCandidate | Paper | Shadow
        )
    {
        return true;
    }
    matches!(
        (from, to),
        (Draft, Running)
            | (Running, Completed)
            | (Running, Failed)
            | (Failed, Draft)
            | (Completed, Hypothesis)
            | (Completed, Candidate)
            | (Hypothesis, Candidate)
            | (Candidate, RobustCandidate)
            | (Candidate, Hypothesis)
            | (RobustCandidate, Paper)
            | (Paper, Shadow)
            | (Shadow, Approved)
            | (Approved, Production)
    )
}

pub fn promote(
    store: &EngineStore,
    experiment_id: &str,
    to: LifecycleStatus,
    reason: &str,
    created_by: &str,
) -> Result<PromotionRecord, EngineError> {
    let mut exp = store.get_experiment(experiment_id)?;
    let from = LifecycleStatus::parse(&exp.status)
        .ok_or_else(|| EngineError::validation("STATUS", exp.status.clone()))?;
    if !allowed_transition(from, to) {
        return Err(EngineError::ForbiddenPromotion {
            from: from.as_str().into(),
            to: to.as_str().into(),
        });
    }
    if from == LifecycleStatus::Candidate && to == LifecycleStatus::Production {
        return Err(EngineError::ForbiddenPromotion {
            from: from.as_str().into(),
            to: to.as_str().into(),
        });
    }
    let rec = PromotionRecord {
        id: format!("PROMO_{}", Uuid::new_v4().simple()),
        experiment_id: experiment_id.into(),
        from_status: from.as_str().into(),
        to_status: to.as_str().into(),
        reason: reason.into(),
        created_at: Utc::now().to_rfc3339(),
        created_by: created_by.into(),
    };
    store.insert_promotion(&rec)?;
    exp.status = to.as_str().into();
    exp.updated_at = rec.created_at.clone();
    store.update_experiment(&exp)?;
    Ok(rec)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn candidate_cannot_skip_to_production() {
        assert!(!allowed_transition(
            LifecycleStatus::Candidate,
            LifecycleStatus::Production
        ));
        assert!(allowed_transition(
            LifecycleStatus::Approved,
            LifecycleStatus::Production
        ));
    }
}
