use std::path::{Path, PathBuf};

#[derive(Clone, Debug)]
pub struct WorkspacePaths {
    pub root: PathBuf,
    pub b1_dir: PathBuf,
    pub first83_dir: PathBuf,
    pub first83_sqlite: PathBuf,
    pub first83_universe: PathBuf,
    pub first83_rankings: PathBuf,
    pub first83_summary: PathBuf,
    pub prospective83_dir: PathBuf,
    pub engine_dir: PathBuf,
    pub engine_sqlite: PathBuf,
    pub artifacts_dir: PathBuf,
}

impl WorkspacePaths {
    pub fn new(root: impl AsRef<Path>) -> Self {
        let root = root.as_ref().to_path_buf();
        let b1_dir = root.join("Backtesting Suite/Foundation/B1");
        let first83_dir = b1_dir.join("first83");
        let prospective83_dir = b1_dir.join("prospective83");
        let engine_dir = root.join("artifacts/research-engine");
        Self {
            first83_sqlite: first83_dir.join("features.sqlite"),
            first83_universe: first83_dir.join("b1_83_universe.json"),
            first83_rankings: first83_dir.join("b1_83_exhaustive_rankings.csv"),
            first83_summary: first83_dir.join("b1_83_search_summary.json"),
            artifacts_dir: engine_dir.join("experiments"),
            engine_sqlite: engine_dir.join("engine.sqlite"),
            first83_dir,
            prospective83_dir,
            b1_dir,
            engine_dir,
            root,
        }
    }

    pub fn detect() -> Self {
        if let Ok(root) = std::env::var("MOMENTO_ROOT") {
            return Self::new(root);
        }
        let cwd = std::env::current_dir().unwrap_or_else(|_| PathBuf::from("."));
        let mut cur = cwd.as_path();
        loop {
            let cargo = cur.join("Cargo.toml");
            if cargo.exists()
                && std::fs::read_to_string(&cargo)
                    .is_ok_and(|t| t.contains("[workspace]") && t.contains("research-features"))
            {
                return Self::new(cur);
            }
            match cur.parent() {
                Some(p) => cur = p,
                None => return Self::new(cwd),
            }
        }
    }
}
