"""Server-authoritative ROLLER → SuperASI import. Client snapshot is not N."""

from __future__ import annotations

from typing import Any

from roller.dashboard_adapter.research_executor import execute_research_object
from roller.research_query.execute import execute_question
from roller.superasi.library import write_package
from roller.superasi.models import SuperasiError
from roller.superasi.package import new_package, sha256_hex
from roller.superasi.path_windows import apply_derived_to_trades

_SUPERASI_CELL_KEYS = {
    "W_and_not_T40",
    "W_and_T40",
    "L_and_not_T40",
    "L_and_T40",
}
_FROZEN_PATHS = {
    "frozen_reference",
    "warehouse_first80",
    "roller_first80",
}
_GENERIC_PATHS = {"generic_query", "generic"}


def authoritative_trades(envelope: dict[str, Any]) -> list[dict[str, Any]]:
    pop = envelope.get("population") or {}
    count = pop.get("count")
    trades = pop.get("trades")
    if isinstance(trades, list) and trades:
        if count is not None and len(trades) != int(count):
            raise SuperasiError(
                "POPULATION_COUNT_MISMATCH",
                f"len(trades)={len(trades)} != population.count={count}",
            )
        return list(trades)
    rows = pop.get("rows") or []
    truncated = bool(pop.get("rows_truncated"))
    if truncated or (count is not None and len(rows) != int(count)):
        raise SuperasiError(
            "SOURCE_POPULATION_UNAVAILABLE",
            "authoritative population is truncated or missing; refuse 200-row preview as N",
        )
    if not rows:
        raise SuperasiError("EMPTY_POPULATION", "source population is empty")
    return list(rows)


def _client_of(body: dict[str, Any]) -> dict[str, Any]:
    client = body.get("client_result") or body.get("result_envelope") or {}
    return client if isinstance(client, dict) else {}


def _execution_path(body: dict[str, Any], client: dict[str, Any]) -> str:
    compile_block = client.get("compile") if isinstance(client.get("compile"), dict) else {}
    prov = client.get("provenance") if isinstance(client.get("provenance"), dict) else {}
    raw = (
        body.get("execution_path")
        or compile_block.get("execution_path")
        or prov.get("path")
        or prov.get("execution_path")
        or client.get("execution_path")
        or ""
    )
    return str(raw).strip().lower()


def _research_object_id(body: dict[str, Any], client: dict[str, Any]) -> str:
    spec = body.get("research_spec") if isinstance(body.get("research_spec"), dict) else {}
    return str(
        body.get("research_object_id")
        or client.get("research_object_id")
        or spec.get("research_object_id")
        or ""
    )


def is_frozen_import(body: dict[str, Any]) -> bool:
    """Frozen FIRST80 / NCAAB P5 must re-run execute_research_object, not a drifted question."""
    client = _client_of(body)
    path = _execution_path(body, client)
    if path in _GENERIC_PATHS:
        return False
    if path in _FROZEN_PATHS or "frozen" in path:
        return True
    rid = _research_object_id(body, client)
    return rid.startswith("FIRST80") or rid.startswith("NCAAB_FIRST80")


def _importable(env: dict[str, Any]) -> bool:
    status = str(env.get("execution_status") or "")
    count = int((env.get("population") or {}).get("count") or 0)
    return status in {"COMPLETE", "PARTIAL"} and count > 0


def _generic_payloads(body: dict[str, Any]) -> list[dict[str, Any]]:
    accept = bool(body.get("accept_limitations"))
    out: list[dict[str, Any]] = []
    question = body.get("question")
    if isinstance(question, dict) and question:
        payload = {"question": question, "accept_limitations": accept}
        out.append(payload)
    draft = body.get("draft") or body.get("workflow_draft")
    if isinstance(draft, dict) and draft:
        payload = dict(draft)
        if accept:
            payload["accept_limitations"] = True
        out.append(payload)
    return out


def reexecute(body: dict[str, Any]) -> tuple[dict[str, Any], str]:
    client = _client_of(body)
    if is_frozen_import(body):
        spec = body.get("research_spec") or {}
        if not isinstance(spec, dict) or not spec:
            spec = ((client.get("compile") or {}).get("research_spec") or {}) if isinstance(
                client.get("compile"), dict
            ) else {}
        if not spec:
            raise SuperasiError(
                "SOURCE_POPULATION_UNAVAILABLE",
                "frozen import requires the executed research_spec",
            )
        env = execute_research_object(spec)
        return env, "roller_frozen"

    last: dict[str, Any] | None = None
    for payload in _generic_payloads(body):
        env = execute_question(payload)
        last = env
        if _importable(env):
            return env, "roller_generic"
    spec = body.get("research_spec") or {}
    if isinstance(spec, dict) and spec and not _generic_payloads(body):
        env = execute_research_object(spec)
        return env, "roller_frozen"
    if last is not None:
        return last, "roller_generic"
    raise SuperasiError(
        "SOURCE_POPULATION_UNAVAILABLE",
        "no executed draft, question, or research_spec for import",
    )


def _superasi_four_cell(raw: Any) -> dict[str, Any] | None:
    """ROLLER T_AND_W lists are not SuperASI cells. Do not coerce."""
    if not isinstance(raw, dict):
        return None
    cells = raw.get("cells")
    if isinstance(cells, dict) and _SUPERASI_CELL_KEYS <= set(cells):
        if any(cells[k] is None for k in _SUPERASI_CELL_KEYS):
            return None
        return raw
    return None


def layer_hashes(*objs: Any) -> dict[str, Any]:
    """First non-empty ROLLER hashes layer. UI spec fingerprints are not this."""
    for obj in objs:
        if not isinstance(obj, dict):
            continue
        hashes = obj.get("hashes")
        if isinstance(hashes, dict) and hashes:
            return dict(hashes)
    return {}


def question_hash_of(*objs: Any) -> str | None:
    hashes = layer_hashes(*objs)
    qh = hashes.get("question_hash")
    if qh:
        return str(qh)
    for obj in objs:
        if not isinstance(obj, dict):
            continue
        qh = obj.get("question_hash")
        if qh:
            return str(qh)
        compile_block = obj.get("compile") if isinstance(obj.get("compile"), dict) else {}
        qh = compile_block.get("question_hash")
        if qh:
            return str(qh)
    return None


def dataset_version_of(*objs: Any) -> str | None:
    for obj in objs:
        if not isinstance(obj, dict):
            continue
        dv = obj.get("dataset_version")
        if dv:
            return str(dv)
        prov = obj.get("provenance") if isinstance(obj.get("provenance"), dict) else {}
        dv = prov.get("dataset_version")
        if dv:
            return str(dv)
    return None


def spec_fingerprint_of(body: dict[str, Any]) -> str | None:
    """UI `fp_…` editor fingerprint. Not hashes.question_hash."""
    for key in ("spec_fingerprint", "compile_fingerprint"):
        raw = body.get(key)
        if raw:
            return str(raw)
    return None


def refuse_reexecute_hash_mismatch(
    client: dict[str, Any],
    body: dict[str, Any],
    env: dict[str, Any],
    trade_origin: str,
) -> None:
    if trade_origin != "reexecute":
        return
    client_qh = question_hash_of(body, client)
    env_qh = question_hash_of(env)
    if client_qh and env_qh and client_qh != env_qh:
        raise SuperasiError(
            "QUESTION_HASH_MISMATCH",
            "re-execute question_hash does not match the saved/executed measurement",
        )


def _handoff(body: dict[str, Any], env: dict[str, Any]) -> dict[str, Any]:
    compile_block = env.get("compile") if isinstance(env.get("compile"), dict) else {}
    hashes = layer_hashes(env, body)
    return {
        "measurements": env.get("measurements"),
        "analysis": env.get("analysis"),
        "empirical_partition": env.get("empirical_partition"),
        "base_terminal_efficiency": env.get("base_terminal_efficiency"),
        "identity": env.get("identity"),
        "funnel": env.get("funnel"),
        "compile": compile_block or None,
        "hashes": hashes,
        "dataset_version": dataset_version_of(env, body),
        "provenance": env.get("provenance"),
        "path_conditions": env.get("path_conditions"),
        "terminal_conditions": env.get("terminal_conditions"),
        "bindings": env.get("bindings"),
        "summary": env.get("summary"),
        "workflow_draft": body.get("draft") or body.get("workflow_draft"),
        "question": body.get("question") or compile_block.get("question"),
        "execution_path": _execution_path(body, env),
        "note": "ROLLER measurement copy. Not SuperASI N. Not a fill.",
    }


def _client_authoritative_trades(client: dict[str, Any]) -> list[dict[str, Any]] | None:
    """Use the executed envelope's full trades when they match N. Never use the 200-row preview."""
    pop = client.get("population") if isinstance(client.get("population"), dict) else {}
    status = str(client.get("execution_status") or "")
    if status not in {"COMPLETE", "PARTIAL"}:
        return None
    count = pop.get("count")
    if count is None:
        count = (client.get("summary") or {}).get("population_n")
    trades = pop.get("trades")
    if not isinstance(trades, list) or not count:
        return None
    if len(trades) != int(count):
        return None
    return list(trades)


def import_from_roller(body: dict[str, Any], *, root=None) -> dict[str, Any]:
    client = _client_of(body)
    reexec_err: SuperasiError | None = None
    env: dict[str, Any] | None = None
    source = "roller_generic"
    trade_origin = "reexecute"
    # Full executed envelope (trades length == N) is the measurement.
    # Never treat the 200-row preview as N. Do not rescan a completed generic run.
    envelope_trades = _client_authoritative_trades(client)
    trades: list[dict[str, Any]] | None = None
    if envelope_trades and not is_frozen_import(body):
        env = client
        source = "roller_generic"
        trade_origin = "executed_envelope"
        trades = envelope_trades
    else:
        try:
            env, source = reexecute(body)
        except SuperasiError as exc:
            reexec_err = exc
        if env is not None and _importable(env):
            trades = authoritative_trades(env)
        else:
            fallback = _client_authoritative_trades(client)
            if fallback:
                trades = fallback
                if env is None or not _importable(env):
                    env = client
                source = "roller_frozen" if is_frozen_import(body) else "roller_generic"
                trade_origin = "executed_envelope"
            elif env is not None:
                status = str(env.get("execution_status") or "")
                count = int((env.get("population") or {}).get("count") or 0)
                if status not in {"COMPLETE", "PARTIAL"}:
                    raise SuperasiError(
                        "SOURCE_POPULATION_UNAVAILABLE",
                        f"execution_status={status} is not importable",
                    )
                if count <= 0:
                    raise SuperasiError("EMPTY_POPULATION", "refusing empty import")
                trades = authoritative_trades(env)
            elif reexec_err is not None:
                pop = client.get("population") if isinstance(client.get("population"), dict) else {}
                if pop.get("count") and not pop.get("trades"):
                    raise SuperasiError(
                        "SOURCE_POPULATION_UNAVAILABLE",
                        "executed envelope has N but no full trades; re-run ROLLER then Move to SuperASI. "
                        "The 200-row preview is not N.",
                    )
                raise reexec_err
            else:
                raise SuperasiError("SOURCE_POPULATION_UNAVAILABLE", "no importable population")
    if trades is None or env is None:
        raise SuperasiError("SOURCE_POPULATION_UNAVAILABLE", "no importable population")
    status = str(env.get("execution_status") or client.get("execution_status") or "")
    if status not in {"COMPLETE", "PARTIAL"}:
        raise SuperasiError(
            "SOURCE_POPULATION_UNAVAILABLE",
            f"execution_status={status} is not importable",
        )
    refuse_reexecute_hash_mismatch(client, body, env, trade_origin)
    spec = body.get("research_spec") or (env.get("compile") or {}).get("research_spec") or {}
    spec_identity = spec.get("identity") if isinstance(spec, dict) else {}
    imported_name = (
        (str(body.get("name") or "").strip() or None)
        or (str((spec_identity or {}).get("name") or "").strip() or None)
    )
    hashes_layer = layer_hashes(env, body, client)
    qh = question_hash_of(env, body, client)
    ds_ver = dataset_version_of(env, body, client)
    spec_fp = spec_fingerprint_of(body)
    provenance = env.get("provenance") if isinstance(env.get("provenance"), dict) else {}
    definition_versions = provenance.get("definition_versions")
    if definition_versions is None and isinstance(spec, dict):
        definition_versions = spec.get("definition_versions")
    dataset_versions = provenance.get("dataset_versions")
    pkg, norm = new_package(
        source=source,
        trades=trades,
        research_spec=spec if isinstance(spec, dict) else {},
        research_object_id=env.get("research_object_id") or body.get("research_object_id"),
        name=imported_name,
        compile_fingerprint=spec_fp,
        spec_fingerprint=spec_fp,
        question_hash=qh,
        hashes=hashes_layer,
        dataset_version=ds_ver,
        trade_origin=trade_origin,
        definition_versions=definition_versions,
        dataset_versions=dataset_versions,
        analysis=env.get("analysis"),
        empirical_four_cell=_superasi_four_cell(env.get("empirical_partition")),
        provenance_copy={
            "client_used_as_n": False,
            "trade_origin": trade_origin,
            "client_fingerprint": sha256_hex(client) if client else None,
            "execution_status": status,
            "bindings": env.get("bindings"),
            "execution_path": _execution_path(body, env),
            "question_hash": qh,
            "dataset_version": ds_ver,
        },
        caveats=list(env.get("caveats") or []),
        extra={"roller_handoff": _handoff(body, env)},
    )
    if pkg.get("price_basis") == "LAST_TRADE_PRINT":
        pkg["stop_path_status"] = "DATA_REQUIRED"
        pkg["fee_status"] = "DATA_REQUIRED"
    windows: list[dict[str, Any]] = []
    norm = apply_derived_to_trades(norm, windows)
    written = write_package(pkg, norm, windows, root=root)
    written["population_n"] = pkg["population_n"]
    written["source"] = source
    written["execution_status"] = status
    written["question_hash"] = pkg.get("question_hash")
    written["dataset_version"] = pkg.get("dataset_version")
    written["trade_origin"] = trade_origin
    written["message"] = "MEASUREMENT IMPORTED"
    return written
