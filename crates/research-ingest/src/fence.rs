//! Refuse writes to Data-Real, frozen W2 raw, W1 derived, and production trees.

use std::path::{Path, PathBuf};

use crate::error::IngestError;

fn absolutize(path: &Path) -> PathBuf {
    if path.is_absolute() {
        path.to_path_buf()
    } else {
        std::env::current_dir()
            .unwrap_or_else(|_| PathBuf::from("."))
            .join(path)
    }
}

fn resolve_path(path: &Path) -> PathBuf {
    let abs = absolutize(path);
    if abs.exists() {
        return std::fs::canonicalize(&abs).unwrap_or(abs);
    }
    let mut existing = PathBuf::new();
    let mut missing = PathBuf::new();
    let mut gap = false;
    for comp in abs.components() {
        if gap {
            missing.push(comp);
            continue;
        }
        existing.push(comp);
        if !existing.exists() {
            missing.push(comp);
            existing.pop();
            gap = true;
        }
    }
    let canon = if existing.as_os_str().is_empty() {
        existing
    } else {
        std::fs::canonicalize(&existing).unwrap_or(existing)
    };
    canon.join(missing)
}

fn is_under(candidate: &Path, root: &Path) -> bool {
    let c = resolve_path(candidate);
    let r = resolve_path(root);
    c == r || c.starts_with(&r)
}

/// Default production / frozen research trees relative to a workspace root.
pub fn default_forbidden_roots(workspace: &Path) -> Vec<PathBuf> {
    vec![
        workspace.join("Backtesting Suite").join("Data-Real"),
        workspace
            .join("Backtesting Suite")
            .join("Foundation")
            .join("W1"),
        workspace
            .join("Backtesting Suite")
            .join("Foundation")
            .join("W2")
            .join("raw"),
        workspace.join("strategies"),
        workspace.join("crates").join("risk"),
        workspace.join("crates").join("execution"),
        workspace.join("apps").join("trading-engine"),
        workspace.join("config").join("live.toml"),
    ]
}

pub fn assert_ingest_root_allowed(
    ingest_root: &Path,
    lake_root: &Path,
    extra_forbidden: &[PathBuf],
) -> Result<(), IngestError> {
    if is_under(ingest_root, lake_root) {
        return Err(IngestError::LakeWriteForbidden(
            ingest_root.display().to_string(),
        ));
    }
    for root in extra_forbidden {
        if is_under(ingest_root, root) {
            return Err(IngestError::PathForbidden {
                path: ingest_root.display().to_string(),
                reason: format!("ingest root is under forbidden {}", root.display()),
            });
        }
    }
    Ok(())
}

pub fn assert_not_forbidden_write(
    path: &Path,
    lake_root: &Path,
    extra_forbidden: &[PathBuf],
) -> Result<(), IngestError> {
    if is_under(path, lake_root) {
        return Err(IngestError::LakeWriteForbidden(path.display().to_string()));
    }
    for root in extra_forbidden {
        if is_under(path, root) {
            return Err(IngestError::PathForbidden {
                path: path.display().to_string(),
                reason: format!("write under forbidden {}", root.display()),
            });
        }
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::fs;

    #[test]
    fn rejects_w1_w2_raw_and_production() {
        let tmp = tempfile::tempdir().unwrap();
        let lake = tmp.path().join("Data-Real");
        fs::create_dir_all(&lake).unwrap();
        let w1 = tmp.path().join("Foundation").join("W1");
        let raw = tmp.path().join("Foundation").join("W2").join("raw");
        let strat = tmp.path().join("strategies").join("mlb");
        fs::create_dir_all(&w1).unwrap();
        fs::create_dir_all(&raw).unwrap();
        fs::create_dir_all(&strat).unwrap();
        let forbidden = vec![w1.clone(), raw.clone(), strat.clone()];
        assert!(assert_ingest_root_allowed(&w1.join("nested"), &lake, &forbidden).is_err());
        assert!(assert_ingest_root_allowed(&raw, &lake, &forbidden).is_err());
        assert!(assert_ingest_root_allowed(&strat, &lake, &forbidden).is_err());
        let ok = tmp.path().join("Foundation").join("Ingest");
        assert!(assert_ingest_root_allowed(&ok, &lake, &forbidden).is_ok());
    }
}
