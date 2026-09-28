//! Refuse writes into the immutable lake and refuse DEMO↔REAL mislabeling.

use std::path::{Path, PathBuf};

#[derive(Clone, Debug)]
pub struct LakeWriteGuard {
    pub lake_root: PathBuf,
}

impl LakeWriteGuard {
    pub fn new(lake_root: impl Into<PathBuf>) -> Self {
        Self {
            lake_root: lake_root.into(),
        }
    }

    pub fn assert_not_lake_path(&self, path: &Path) -> Result<(), String> {
        let lake = resolve_path(&self.lake_root);
        let candidate = resolve_path(path);
        if candidate.starts_with(&lake) {
            return Err(format!(
                "W1 refused to write {} inside lake {}",
                candidate.display(),
                lake.display()
            ));
        }
        Ok(())
    }
}

pub fn assert_output_outside_lake(out: &Path, lake: &Path) -> Result<(), String> {
    LakeWriteGuard::new(lake).assert_not_lake_path(out)
}

/// REAL must not be the LEGACY demo tree; DEMO must not be Data-Real.
pub fn assert_lake_class_honest(lake_root: &Path, lake_class: &str) -> Result<(), String> {
    let class = lake_class.trim().to_ascii_uppercase();
    let resolved = resolve_path(lake_root);
    let name = resolved.file_name().and_then(|s| s.to_str()).unwrap_or("");
    let parent = resolved
        .parent()
        .and_then(|p| p.file_name())
        .and_then(|s| s.to_str())
        .unwrap_or("");
    let is_legacy_demo = name == "Data" && parent == "Backtesting Suite";
    let is_data_real = name == "Data-Real";
    if class == "REAL" && is_legacy_demo {
        return Err(
            "W1 refused to label Backtesting Suite/Data as REAL MLB history (DEMO ≠ REAL)".into(),
        );
    }
    if class == "DEMO" && is_data_real {
        return Err("W1 refused to label Data-Real as DEMO".into());
    }
    Ok(())
}

fn absolutize(path: &Path) -> PathBuf {
    if path.is_absolute() {
        path.to_path_buf()
    } else {
        std::env::current_dir()
            .unwrap_or_else(|_| PathBuf::from("."))
            .join(path)
    }
}

/// Resolve a path that may not exist yet, using canonicalize on the existing prefix.
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
