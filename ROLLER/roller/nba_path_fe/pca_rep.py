"""PCA on A+B+C only. Pin PC1=impulse, PC2=thin-book. Period excluded."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from roller.nba_path_fe.config import DEFAULT, PathFeConfig
from roller.nba_path_fe.errors import PathFeError
from roller.nba_path_fe.mathutil import apply_z, zscore
from roller.nba_path_fe.registry import pca_names


PIN_PC1 = ("velocity_ratio_1_5", "max_uptick_gap_5m")
PIN_PC2_POS = ("spread_own", "spread_opp")
PIN_PC2_NEG = ("size_own_bid", "size_opp_bid")


@dataclass
class PcaFit:
    columns: tuple[str, ...]
    mu: pd.Series
    sd: pd.Series
    components: np.ndarray  # (m, p)
    evr: np.ndarray
    m: int
    flips: dict[str, int]


def _complete(frame: pd.DataFrame, cols: list[str]) -> pd.DataFrame:
    return frame.loc[frame[cols].notna().all(axis=1), cols].astype(float)


def fit_pca(train: pd.DataFrame, cfg: PathFeConfig = DEFAULT) -> PcaFit:
    cols = [c for c in pca_names() if c in train.columns]
    if any(c in cols for c in ("period", "clock_bucket", "rest_days")):
        cols = [c for c in cols if c not in {"period", "clock_bucket", "rest_days"}]
    # Do not invent missing L2. Drop columns that are mostly absent.
    cols = [c for c in cols if float(train[c].notna().mean()) >= 0.50]
    if not cols:
        raise PathFeError("PCA_DATA_REQUIRED", "no A/B/C columns with coverage")
    mat = _complete(train, cols)
    if len(mat) < 30:
        raise PathFeError("PCA_DATA_REQUIRED", f"complete A+B+C rows {len(mat)}")
    z, mu, sd = zscore(mat)
    x = z.to_numpy(dtype=float)
    u, s, vt = np.linalg.svd(x, full_matrices=False)
    evr = (s**2) / (s**2).sum()
    m = min(int(cfg.m_pcs_max), int(vt.shape[0]), int(cfg.max_pcs))
    comps = vt[:m].copy()
    flips: dict[str, int] = {}
    name_idx = {c: i for i, c in enumerate(cols)}
    if m >= 1:
        sign = 0.0
        for n in PIN_PC1:
            if n in name_idx:
                sign += float(comps[0, name_idx[n]])
        if sign < 0:
            comps[0] *= -1
            flips["pc1"] = -1
        else:
            flips["pc1"] = 1
    if m >= 2:
        pos = 0.0
        for n in PIN_PC2_POS:
            if n in name_idx:
                pos += float(comps[1, name_idx[n]])
        neg = 0.0
        for n in PIN_PC2_NEG:
            if n in name_idx:
                neg += float(comps[1, name_idx[n]])
        # want pos>=0 and size loadings <=0; flip if pos < 0 or (pos~0 and neg>0)
        if pos < 0 or (abs(pos) < 1e-9 and neg > 0):
            comps[1] *= -1
            flips["pc2"] = -1
        else:
            flips["pc2"] = 1
    return PcaFit(tuple(cols), mu, sd, comps, evr[:m], m, flips)


def transform_pca(frame: pd.DataFrame, fit: PcaFit) -> pd.DataFrame:
    sub = frame.reindex(columns=list(fit.columns))
    z = apply_z(sub.astype(float), fit.mu, fit.sd)
    # missing rows stay NaN
    out = pd.DataFrame(index=frame.index)
    ok = z.notna().all(axis=1)
    scores = np.full((len(frame), fit.m), np.nan)
    if int(ok.sum()) > 0:
        scores[ok.to_numpy()] = z.loc[ok].to_numpy(dtype=float) @ fit.components.T
    for i in range(fit.m):
        out[f"pc{i+1}"] = scores[:, i]
    return out


def pca_stability(frames: list[pd.DataFrame], cfg: PathFeConfig = DEFAULT) -> dict:
    """Sign-invariant absolute cosine of PC1/PC2 loadings across eras."""
    fits = []
    for fr in frames:
        try:
            fits.append(fit_pca(fr, cfg))
        except PathFeError:
            continue
    if len(fits) < 2:
        return {"n_fits": len(fits), "pc1_mean_abs_cos": None, "pc2_mean_abs_cos": None}
    # align columns
    cols = list(fits[0].columns)
    c1 = []
    c2 = []
    for a in range(len(fits)):
        for b in range(a + 1, len(fits)):
            if list(fits[b].columns) != cols:
                continue
            v1 = fits[a].components[0]
            w1 = fits[b].components[0]
            c1.append(abs(float(np.dot(v1, w1) / (np.linalg.norm(v1) * np.linalg.norm(w1)))))
            if fits[a].m >= 2 and fits[b].m >= 2:
                v2 = fits[a].components[1]
                w2 = fits[b].components[1]
                c2.append(abs(float(np.dot(v2, w2) / (np.linalg.norm(v2) * np.linalg.norm(w2)))))
    return {
        "n_fits": len(fits),
        "pc1_mean_abs_cos": float(np.mean(c1)) if c1 else None,
        "pc2_mean_abs_cos": float(np.mean(c2)) if c2 else None,
    }
