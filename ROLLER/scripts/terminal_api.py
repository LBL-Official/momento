"""ROLLER Terminal API — Phase 1–5.

Browser → this API → dashboard_adapter → authoritative Roller / Phase 0 contracts.
No math reinvention. No LLM. Orchestrates frozen empirical bindings only.
"""

from __future__ import annotations

import logging
import os
import sys
import time
from pathlib import Path
from typing import Any

# Ensure ROLLER package root is importable when launched as a script.
_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from urllib.parse import quote

from fastapi import FastAPI, Header, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, Field

from roller.dashboard_adapter.explorer import BBALL1_ID, ExplorerError, list_universe_games
from roller.dashboard_adapter.measurement_registry import list_measurements, research_capabilities
from roller.dashboard_adapter.object_inspector import ObjectInspectorError, build_object_payload
from roller.dashboard_adapter.research_executor import execute_research_object
from roller.dashboard_adapter.research_object_ops import (
    list_templates,
    preview_research_object,
    validate_for_api,
)
from roller.dashboard_adapter.vocabulary_compiler import compile_research_text, load_vocabulary
from roller.research_query.compiler import compile_draft
from roller.research_query.hashing import layer_hashes
from roller.research_query.jobs import active_counts, get_job, submit_execute

app = FastAPI(
    title="ROLLER Terminal API",
    version="0.5.0",
    description=(
        "Phase 1: What existed at I(t)? "
        "Phase 2: structural Research Object operations (validate/preview/templates). "
        "Phase 3: deterministic vocabulary compiler (no LLM). "
        "Phase 4: empirical research execution (orchestrator; frozen bindings). "
        "Phase 5: measurement registry & execution routing."
    ),
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1:5179",
        "http://localhost:5179",
        "http://127.0.0.1:5180",
        "http://localhost:5180",
        "http://127.0.0.1:5173",
        "http://localhost:5173",
        "http://127.0.0.1:5182",
        "http://localhost:5182",
        "http://127.0.0.1:5190",
        "http://localhost:5190",
        "http://127.0.0.1:5191",
        "http://localhost:5191",
        "http://127.0.0.1:5192",
        "http://localhost:5192",
        "http://127.0.0.1:5193",
        "http://localhost:5193",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

_log = logging.getLogger("roller.terminal_api")
if not logging.getLogger().handlers:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )

# Read-only live-unit inspect. Writes still require VITAL_AWS_CONTROL=1.
os.environ.setdefault("VITAL_AWS_HOST_FETCH", "ssm")


@app.middleware("http")
async def enforce_scoped_routes(request, call_next):
    """Scoped paths do not fall through. A cookie cannot replace a missing session."""
    path = request.url.path
    if not path.startswith("/scoped/"):
        return await call_next(request)
    parts = path.split("/", 3)
    if len(parts) < 4 or not parts[2] or not parts[3]:
        return JSONResponse(status_code=401, content={"code": "SCOPE_REQUIRED", "message": "scoped route missing session"})
    quadrant_id, rest = parts[2], parts[3]
    header = request.headers.get("x-momento-scope")
    query_token = request.query_params.get("momento_scope")
    from roller.systimo.errors import SystimoError
    from roller.systimo.scope import get_session, token_from_request

    try:
        token = token_from_request(header, query_token)
        session = get_session(token)
    except SystimoError as exc:
        return JSONResponse(status_code=exc.status_code, content=exc.as_dict())
    if session["quadrant_id"] != quadrant_id and session["scope_level"] != "global":
        return JSONResponse(status_code=403, content={"code": "SCOPE_DENIED", "message": "session quadrant mismatch"})
    sport = request.query_params.get("sport")
    if sport and session["scope_level"] != "global" and sport.upper() != str(session["sport"]).upper():
        return JSONResponse(status_code=403, content={"code": "SCOPE_DENIED", "message": "sport disagrees with session"})
    universe_n = request.query_params.get("n")
    if universe_n == "0":
        return JSONResponse(status_code=409, content={"code": "UNAVAILABLE", "message": "missing is UNAVAILABLE"})
    if "choosin" in rest and universe_n and universe_n != "936":
        return JSONResponse(status_code=403, content={"code": "LOCK_MISMATCH", "message": "Choosin lock is 936"})
    if "austin" in rest and universe_n and universe_n != "604":
        return JSONResponse(status_code=403, content={"code": "LOCK_MISMATCH", "message": "Austin lock is 604"})
    if request.method in {"POST", "PUT", "PATCH"}:
        body = await request.body()
        if body:
            import json

            try:
                payload = json.loads(body)
            except json.JSONDecodeError:
                payload = None
            if isinstance(payload, dict) and payload.get("sport"):
                if session["scope_level"] != "global" and str(payload["sport"]).upper() != str(session["sport"]).upper():
                    return JSONResponse(
                        status_code=403,
                        content={"code": "SCOPE_DENIED", "message": "sport disagrees with session"},
                    )
    request.scope["path"] = "/" + rest
    request.scope["raw_path"] = ("/" + rest).encode()
    return await call_next(request)


@app.middleware("http")
async def log_research_requests(request, call_next):
    path = request.url.path
    if (
        path.startswith("/research-query/")
        or path.startswith("/superasi/")
        or path.startswith("/jump/")
        or path.startswith("/vital/")
        or path.startswith("/stax")
        or path.startswith("/choosin-texas")
        or path.startswith("/austin")
        or path.startswith("/dre")
        or path.startswith("/ballhog")
        or path.startswith("/systimo")
        or path.startswith("/warehouse-research")
        or path.startswith("/momento")
    ):
        _log.info("%s %s received", request.method, path)
    started = time.perf_counter()
    response = await call_next(request)
    if (
        path.startswith("/research-query/")
        or path.startswith("/superasi/")
        or path.startswith("/jump/")
        or path.startswith("/vital/")
        or path.startswith("/stax")
        or path.startswith("/choosin-texas")
        or path.startswith("/austin")
        or path.startswith("/dre")
        or path.startswith("/ballhog")
        or path.startswith("/systimo")
        or path.startswith("/warehouse-research")
        or path.startswith("/momento")
    ):
        ms = int(round((time.perf_counter() - started) * 1000))
        qh = response.headers.get("x-roller-query-hash", "")
        n = response.headers.get("x-roller-n", "")
        term = response.headers.get("x-roller-terminal-missing", "")
        path_ex = response.headers.get("x-roller-execution-path", "")
        _log.info(
            "%s %s status=%s execution_path=%s query_hash=%s n=%s terminal_missing=%s duration_ms=%s",
            request.method,
            path,
            response.status_code,
            path_ex or "-",
            qh or "-",
            n or "-",
            term or "-",
            ms,
        )
    return response


class ExplorerQuery(BaseModel):
    universe: str = Field(default=BBALL1_ID)
    as_of: str | None = None
    information_mode: str = Field(default="POINT_IN_TIME")


class InterpretRequest(BaseModel):
    universe: str = Field(default=BBALL1_ID)
    text: str = ""
    language: str = ""  # deprecated alias for text
    base_spec: dict[str, Any] | None = None


class ResearchSpecBody(BaseModel):
    research_spec: dict[str, Any]


class ResearchQueryBody(BaseModel):
    draft: dict[str, Any] | None = None
    question: dict[str, Any] | None = None
    accept_limitations: bool = False
    # Ignored — server recompiles. Present so a malicious client cannot steer routing.
    execution_path: str | None = None
    reference_match: str | None = None
    status: str | None = None


_SETTLEMENT_HEALTH: dict[str, Any] | None = None
_SETTLEMENT_HEALTH_AT = 0.0


def _settlement_health_cached() -> dict[str, Any]:
    global _SETTLEMENT_HEALTH, _SETTLEMENT_HEALTH_AT
    now = time.monotonic()
    if _SETTLEMENT_HEALTH is not None and now - _SETTLEMENT_HEALTH_AT < 10:
        return _SETTLEMENT_HEALTH
    from roller.research_query.official_settlement import official_settlement_health

    _SETTLEMENT_HEALTH = official_settlement_health()
    _SETTLEMENT_HEALTH_AT = now
    return _SETTLEMENT_HEALTH


@app.get("/health")
async def health() -> dict:
    settlement = _settlement_health_cached()
    return {
        "status": "ok",
        "product": "ROLLER Terminal",
        "phase": 6,
        "reachable_during_execute": True,
        "jobs": active_counts(),
        "result_cache": os.environ.get("ROLLER_QUERY_RESULT_CACHE", "0") in {"1", "true", "True"},
        "capabilities": [
            "explorer_pit",
            "object_inspector",
            "research_object_validate",
            "research_object_preview",
            "research_object_templates",
            "vocabulary_compiler",
            "vocabulary_registry",
            "research_execute",
            "measurement_registry",
            "research_capabilities",
            "population_ncaab_first80_p5",
            "research_query_compile",
            "research_query_execute",
            "research_query_jobs",
            "research_query_official_settlement",
            "research_library_saves",
            "superasi_import",
            "superasi_library",
            "superasi_decompose",
            "superasi_seed_asked_six",
            "superasi_base_run",
            "superasi_base_results",
            "superasi_debase_run",
            "superasi_debase_results",
            "jump_shell",
            "jump_iti",
            "jump_bots",
            "jump_dashboard",
            "jump_catalog",
            "jump_data",
            "jump_mybots",
            "vital_shell",
            "vital_bots",
            "vital_desk",
            "superasi_iti",
            "warehouse_research_settings",
            "stax",
            "stax_library",
            "stax_automation",
            "choosin_texas_universe",
            "choosin_texas_universe_60",
            "choosin_texas_paired_replay",
            "choosin_texas_execution_validation",
            "choosin_texas_universe_75",
            "choosin_texas_universe_77",
            "choosin_texas_nba_path",
            "choosin_texas_nba_path_75",
            "choosin_texas_nba_path_77",
            "choosin_texas_dallas",
            "choosin_texas_book",
            "choosin_texas_sugarland",
            "choosin_texas_asked_six",
            "choosin_texas_universe_81",
            "choosin_texas_universe_83",
            "momento_systems",
            "dre_shell",
        ],
        "settlement": settlement,
        "note": (
            "Phase 6 authoritative population expansion "
            "(NCAAB_FIRST80_P5; NBA FIRST80 lock preserved; MEASUREMENT ≠ EDGE). "
            "Hold-to-YES uses official FIRST80 expiration_result_yes, not path WIN."
        ),
    }


@app.get("/universes")
def universes() -> list[dict]:
    return [
        {
            "id": BBALL1_ID,
            "sports": ["NBA", "WNBA", "NCAAB"],
            "label": "BBALL1 Research",
            "question": "WHAT EXISTED AT I(t)?",
        }
    ]


@app.post("/explorer/query")
def explorer_query(body: ExplorerQuery) -> dict:
    try:
        return list_universe_games(
            universe=body.universe,
            as_of=body.as_of,
            information_mode=body.information_mode,
        )
    except ExplorerError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/objects/{internal_game_id}")
def get_object(
    internal_game_id: str,
    as_of: str | None = Query(default=None),
) -> dict:
    try:
        return build_object_payload(internal_game_id, as_of=as_of)
    except ObjectInspectorError as exc:
        msg = str(exc)
        code = 404 if msg.startswith("GAME NOT FOUND") else 400
        raise HTTPException(status_code=code, detail=msg) from exc


@app.post("/query/interpret")
def interpret(body: InterpretRequest) -> dict:
    text = (body.text or body.language or "").strip()
    return compile_research_text(text, base_spec=body.base_spec)


@app.get("/vocabulary")
def vocabulary() -> dict:
    return load_vocabulary()


@app.get("/research-capabilities")
def get_research_capabilities() -> dict:
    return research_capabilities()


@app.get("/measurements")
def get_measurements() -> list[dict]:
    return list_measurements()


@app.get("/research-object-templates")
def research_object_templates() -> list[dict]:
    return list_templates()


@app.post("/research-objects/validate")
def research_objects_validate(body: ResearchSpecBody) -> dict:
    return validate_for_api(body.research_spec)


@app.post("/research-objects/preview")
def research_objects_preview(body: ResearchSpecBody) -> dict:
    return preview_research_object(body.research_spec)


@app.post("/research-objects/execute")
def research_objects_execute(body: ResearchSpecBody) -> dict:
    return execute_research_object(body.research_spec)


def _query_headers(body: dict[str, Any]) -> dict[str, str]:
    hashes = body.get("hashes") if isinstance(body.get("hashes"), dict) else {}
    summary = body.get("summary") if isinstance(body.get("summary"), dict) else {}
    ident = body.get("identity") if isinstance(body.get("identity"), dict) else {}
    compile_block = body.get("compile") if isinstance(body.get("compile"), dict) else {}
    n = summary.get("population_n")
    if n is None:
        n = ident.get("reported_n")
    missing = ident.get("terminal_missing")
    return {
        "x-roller-query-hash": str(hashes.get("question_hash") or ""),
        "x-roller-execution-path": str(
            compile_block.get("execution_path") or body.get("execution_path") or ""
        ),
        "x-roller-n": "" if n is None else str(n),
        "x-roller-terminal-missing": "" if missing is None else str(missing),
    }


class WarehouseResearchBody(BaseModel):
    question: dict[str, Any] | None = None
    draft: dict[str, Any] | None = None
    accept_limitations: bool = False
    engine_id: str = "optimized"
    include_reference: bool = False
    te_filters: dict[str, Any] | None = None
    teFilters: dict[str, Any] | None = None
    exposure_unit: str | None = None
    exposureUnit: str | None = None
    max_entries_per_unit: int | None = None
    maxEntriesPerGame: int | None = None
    exposure_enforcement_mode: str | None = None
    exposureEnforcementMode: str | None = None


@app.post("/warehouse-research/compile")
def warehouse_research_compile(body: WarehouseResearchBody) -> JSONResponse:
    """Sync handler: runs in the threadpool. Must not block the Vital event loop."""
    from roller.warehouse.frontend_contract import compile_frontend_research

    return JSONResponse(compile_frontend_research(body.model_dump()))


@app.post("/warehouse-research/execute")
def warehouse_research_execute(body: WarehouseResearchBody) -> JSONResponse:
    """Sync handler: long research stays off the event loop so /vital/* can answer."""
    from roller.warehouse.frontend_contract import execute_frontend_research

    payload = execute_frontend_research(
        body.model_dump(),
        engine_id=body.engine_id or "optimized",
        include_reference=bool(body.include_reference),
    )
    return JSONResponse(payload)


@app.get("/warehouse-research/capabilities")
def warehouse_research_capabilities() -> dict:
    from roller.warehouse.production import production_capabilities

    return production_capabilities()


class WarehouseSettingsBody(BaseModel):
    bankroll_dollars: float
    allocation_pct: float


@app.get("/warehouse-research/settings")
def warehouse_research_settings_get() -> dict:
    from roller.desk_settings import DeskSettingsError, public_settings

    try:
        return public_settings()
    except DeskSettingsError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.put("/warehouse-research/settings")
def warehouse_research_settings_put(body: WarehouseSettingsBody) -> dict:
    from roller.desk_settings import DeskSettingsError, from_ui, public_settings, save_desk_settings

    try:
        bankroll_cents, allocation_bps = from_ui(
            bankroll_dollars=body.bankroll_dollars,
            allocation_pct=body.allocation_pct,
        )
        saved = save_desk_settings(bankroll_cents=bankroll_cents, allocation_bps=allocation_bps)
        return public_settings(saved)
    except DeskSettingsError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


class WarehouseRiskBody(BaseModel):
    mode: str = "A"
    seed: int = 20260913
    research_result_hash: str = ""
    config: dict[str, Any] | None = None
    classifications: list[str] | None = None
    probabilities: list[float] | None = None
    theoretical_zero_cost: bool = False
    persist: bool = False
    controls: dict[str, Any] | None = None


@app.post("/warehouse-research/risk")
def warehouse_research_risk(body: WarehouseRiskBody) -> dict:
    from roller.desk_settings import risk_config_defaults
    from roller.risk.engine import run_risk
    from roller.risk.formulas import RiskConfigError
    from roller.risk.store import save_risk_result

    payload = body.model_dump()
    cfg = dict(payload.get("config") or {})
    desk = risk_config_defaults()
    if "initial_bankroll" not in cfg:
        cfg["initial_bankroll"] = desk["initial_bankroll"]
    if "trade_allocation" not in cfg:
        cfg["trade_allocation"] = desk["trade_allocation"]
    payload["config"] = cfg
    try:
        result = run_risk(payload)
    except RiskConfigError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if body.persist:
        result["persist"] = save_risk_result(result)
    return result


class WarehouseLabBody(BaseModel):
    name: str
    folder: str = "NBA"
    lab_id: str | None = None
    question: dict[str, Any] | None = None
    draft: dict[str, Any] | None = None
    payload: dict[str, Any] | None = None


@app.post("/warehouse-research/labs")
def warehouse_research_labs_save(body: WarehouseLabBody) -> dict:
    from roller.labs.store import rename_lab, save_lab
    from roller.warehouse.frontend_contract import execute_frontend_research

    if body.lab_id:
        renamed = rename_lab(body.lab_id, body.name)
        if renamed is None:
            raise HTTPException(status_code=404, detail="lab not found")
        return renamed
    payload = body.payload
    if payload is None:
        payload = execute_frontend_research(
            {"question": body.question, "draft": body.draft}
        )
    if payload.get("status") in {"INVALID", "DATA_REQUIRED", "OPERATION_REQUIRED"}:
        raise HTTPException(status_code=400, detail=payload)
    question = body.question or payload.get("question")
    from roller.warehouse.desk import desk_lab_folder

    return save_lab(
        name=body.name,
        payload=payload,
        folder=desk_lab_folder(question, body.folder),
        question=question,
    )


@app.get("/warehouse-research/labs")
def warehouse_research_labs_list(folder: str | None = Query(default=None)) -> dict:
    from roller.labs.store import list_labs

    items = list_labs(folder=folder)
    folders = sorted({str(i.get("folder") or "") for i in items if i.get("folder")})
    return {"labs": items, "n": len(items), "folders": folders}


@app.get("/warehouse-research/labs/{lab_id}")
def warehouse_research_labs_get(lab_id: str) -> dict:
    from roller.labs.store import get_lab

    rec = get_lab(lab_id)
    if rec is None:
        raise HTTPException(status_code=404, detail="lab not found")
    return rec


@app.get("/warehouse-research/labs/{lab_id}/csv")
def warehouse_research_labs_csv(lab_id: str) -> Response:
    from roller.labs.store import get_lab_csv_bytes

    found = get_lab_csv_bytes(lab_id)
    if found is None:
        raise HTTPException(status_code=404, detail="lab csv not found")
    filename, data = found
    return Response(
        content=data,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": _content_disposition(filename)},
    )


@app.post("/research-query/compile")
def research_query_compile(body: ResearchQueryBody) -> JSONResponse:
    from roller.research_query.compiler import compile_question
    from roller.research_query.models import ResearchQuestion

    te_filters = None
    if body.question:
        q = ResearchQuestion.from_dict(body.question)
        if body.accept_limitations:
            q = ResearchQuestion(
                universe=q.universe,
                entry_conditions=q.entry_conditions,
                path_conditions=q.path_conditions,
                terminal=q.terminal,
                requested_dimensions=q.requested_dimensions,
                accept_limitations=True,
            )
        compiled = compile_question(q)
    else:
        draft = dict(body.draft or {})
        if body.accept_limitations:
            draft["accept_limitations"] = True
        te_filters = draft.get("teFilters") or draft.get("te_filters")
        compiled = compile_draft(draft)
    out = compiled.to_dict()
    out["hashes"] = layer_hashes(compiled.question, state=te_filters if isinstance(te_filters, dict) else None)
    return JSONResponse(out, headers=_query_headers(out))


def _execute_payload(body: ResearchQueryBody) -> dict[str, Any]:
    if body.draft:
        payload = dict(body.draft)
        if body.accept_limitations:
            payload["accept_limitations"] = True
        return payload
    if body.question:
        return {"question": body.question, "accept_limitations": body.accept_limitations}
    return {}


@app.post("/research-query/execute")
async def research_query_execute(body: ResearchQueryBody) -> JSONResponse:
    """Enqueue execute. Returns 202 immediately so /health stays reachable."""
    job = submit_execute(_execute_payload(body))
    return JSONResponse(job, status_code=202, headers={"x-roller-job-id": job["job_id"]})


@app.get("/research-query/jobs/{job_id}")
async def research_query_job(job_id: str) -> JSONResponse:
    rec = get_job(job_id)
    if rec is None:
        raise HTTPException(status_code=404, detail="job not found")
    headers = {"x-roller-job-id": job_id, "x-roller-job-status": str(rec["status"])}
    if rec["status"] == "complete" and isinstance(rec.get("result"), dict):
        headers.update(_query_headers(rec["result"]))
    return JSONResponse(rec, headers=headers)


@app.post("/research-library/saves")
async def research_library_save(body: dict[str, Any]) -> dict:
    from roller.research_library.saves import write_save

    return write_save(body)


@app.get("/research-library/saves")
async def research_library_list() -> dict:
    from roller.research_library.saves import list_saves

    items = list_saves()
    return {"saves": items, "n": len(items)}


@app.get("/research-library/saves/{save_id}")
async def research_library_get(save_id: str) -> dict:
    from roller.research_library.saves import load_save

    rec = load_save(save_id)
    if rec is None:
        raise HTTPException(status_code=404, detail="save not found")
    return rec


class SuperasiDecomposeBody(BaseModel):
    fill_algorithm: str | None = None
    fee_scenario: str | None = None
    adverse_p: str | None = None


@app.post("/superasi/library/import")
async def superasi_import(body: dict[str, Any]) -> dict:
    import asyncio

    from roller.superasi.api import handle_import
    from roller.superasi.models import SuperasiError

    try:
        return await asyncio.to_thread(handle_import, body)
    except SuperasiError as exc:
        raise HTTPException(status_code=400, detail=exc.as_dict()) from exc


@app.get("/superasi/library")
def superasi_list() -> dict:
    from roller.superasi.api import handle_list

    return handle_list()


@app.get("/superasi/library/{package_id}")
def superasi_get(package_id: str) -> dict:
    from roller.superasi.api import handle_get
    from roller.superasi.models import SuperasiError

    try:
        return handle_get(package_id)
    except SuperasiError as exc:
        raise HTTPException(status_code=404, detail=exc.as_dict()) from exc


@app.post("/superasi/library/{package_id}/decompose")
def superasi_decompose(package_id: str, body: SuperasiDecomposeBody | None = None) -> dict:
    from roller.superasi.api import handle_decompose
    from roller.superasi.models import SuperasiError

    try:
        return handle_decompose(package_id, body.model_dump() if body else {})
    except SuperasiError as exc:
        raise HTTPException(status_code=400, detail=exc.as_dict()) from exc


def _stax_http(fn, *args, **kwargs):
    from roller.stax.models import StaxError

    try:
        return fn(*args, **kwargs)
    except StaxError as exc:
        if exc.code == "STAX_DUPLICATE_DEFINITION":
            code = 409
        elif exc.code in {"STAX_NOT_FOUND", "STAX_VERSION_NOT_FOUND"}:
            code = 404
        else:
            code = 400
        raise HTTPException(status_code=code, detail=exc.as_dict()) from exc


@app.post("/stax")
def stax_create(body: dict[str, Any]) -> dict:
    from roller.stax.api import handle_create

    return _stax_http(handle_create, body)


@app.get("/stax")
def stax_list() -> dict:
    from roller.stax.api import handle_list

    return handle_list()


@app.get("/stax/candidates")
def stax_candidates() -> dict:
    from roller.stax.api import handle_candidates

    return handle_candidates()


@app.post("/stax/automation/tick")
def stax_tick() -> dict:
    from roller.stax.api import handle_tick

    return _stax_http(handle_tick)


@app.get("/stax/{stax_id}")
def stax_get(stax_id: str) -> dict:
    from roller.stax.api import handle_get

    return _stax_http(handle_get, stax_id)


@app.get("/stax/{stax_id}/versions")
def stax_versions(stax_id: str) -> dict:
    from roller.stax.api import handle_versions

    return _stax_http(handle_versions, stax_id)


@app.get("/stax/{stax_id}/versions/{version}")
def stax_version(stax_id: str, version: str) -> dict:
    from roller.stax.api import handle_version

    return _stax_http(handle_version, stax_id, version)


@app.post("/stax/{stax_id}/strategies")
def stax_create_strategy(stax_id: str, body: dict[str, Any] | None = None) -> dict:
    from roller.stax.api import handle_create_in_stax

    return _stax_http(handle_create_in_stax, stax_id, body or {})


@app.post("/stax/{stax_id}/validate")
def stax_validate(stax_id: str, body: dict[str, Any] | None = None) -> dict:
    from roller.stax.api import handle_validate

    return _stax_http(handle_validate, stax_id, body or {})


@app.post("/stax/{stax_id}/run")
def stax_run(stax_id: str, body: dict[str, Any] | None = None) -> dict:
    from roller.stax.api import handle_run

    return _stax_http(handle_run, stax_id, body or {})


@app.post("/stax/{stax_id}/automation")
def stax_automation(stax_id: str, body: dict[str, Any] | None = None) -> dict:
    from roller.stax.api import handle_automation

    return _stax_http(handle_automation, stax_id, body or {})


@app.post("/stax/{stax_id}/compare")
def stax_compare(stax_id: str, body: dict[str, Any] | None = None) -> dict:
    from roller.stax.api import handle_compare

    return _stax_http(handle_compare, stax_id, body or {})


@app.get("/stax/{stax_id}/export")
def stax_export(stax_id: str, version: str | None = None) -> dict:
    from roller.stax.api import handle_export

    return _stax_http(handle_export, stax_id, version)


@app.get("/auto-roller/status")
def auto_roller_status() -> dict:
    from roller.auto_roller.status import status_payload

    return status_payload()


@app.get("/auto-roller/coverage")
def auto_roller_coverage() -> dict:
    from roller.auto_roller.status import coverage_payload

    return coverage_payload()


class AutoRollerRun(BaseModel):
    fast: bool = True


@app.post("/auto-roller/verify")
def auto_roller_verify(body: AutoRollerRun | None = None) -> dict:
    from roller.auto_roller.verify import run_verify

    fast = True if body is None else body.fast
    return run_verify(semantic=not fast)


@app.post("/auto-roller/ingest")
def auto_roller_ingest(body: AutoRollerRun | None = None) -> dict:
    from roller.auto_roller.ingest import run_ingest

    return run_ingest(rebuild_indexes=False)


def _momento_http(fn, *args, **kwargs):
    from roller.momento.api import MomentoApiError

    try:
        return fn(*args, **kwargs)
    except MomentoApiError as exc:
        raise HTTPException(
            status_code=exc.status_code,
            detail={"code": exc.code, "message": exc.message},
        ) from exc


@app.get("/momento/execution/nba/{kind}")
def momento_nba_execution(kind: str, x_momento_scope: str | None = Header(default=None)) -> dict:
    from roller.momento.execution import handle_nba_document

    return _momento_http(handle_nba_document, kind, x_momento_scope)


@app.get("/momento/season-strategy")
def momento_season_strategy() -> dict:
    from roller.momento.api import handle_season_strategy

    return _momento_http(handle_season_strategy)


@app.get("/momento/systems")
def momento_systems() -> dict:
    from roller.momento.api import handle_systems

    return handle_systems()


@app.get("/momento/systems/{system_id}")
def momento_system(system_id: str) -> dict:
    from roller.momento.api import handle_system

    return _momento_http(handle_system, system_id)


@app.get("/momento/systems/{system_id}/logic")
def momento_system_logic(system_id: str) -> dict:
    from roller.momento.api import handle_logic

    return _momento_http(handle_logic, system_id)


@app.get("/momento/systems/{system_id}/health")
def momento_system_health(system_id: str) -> dict:
    from roller.momento.api import handle_system_health

    return _momento_http(handle_system_health, system_id)


@app.get("/momento/ontologic-x/health")
def momento_ontologic_x_health() -> dict:
    from roller.ontologic_x.api import handle_health

    return handle_health()


@app.get("/momento/ontologic-x/board")
def momento_ontologic_x_board(date: str | None = None, view: str | None = None) -> dict:
    from roller.ontologic_x.api import handle_board

    return handle_board(date=date, view=view)


@app.get("/momento/ontologic-x/games/{game_id}")
def momento_ontologic_x_game(game_id: str) -> dict:
    from roller.ontologic_x.api import handle_game

    return handle_game(game_id)


@app.get("/momento/ontologic-x/history")
def momento_ontologic_x_history() -> dict:
    from roller.ontologic_x.api import handle_history

    return handle_history()


@app.get("/momento/ontologic-x/coverage")
def momento_ontologic_x_coverage() -> dict:
    from roller.ontologic_x.api import handle_coverage

    return handle_coverage()


@app.get("/momento/ontologic-x/credits")
def momento_ontologic_x_credits() -> dict:
    from roller.ontologic_x.api import handle_credits

    return handle_credits()


@app.get("/momento/ontologic-y/health")
def momento_ontologic_y_health() -> dict:
    from roller.ontologic_y.api import handle_health

    return handle_health()


@app.get("/momento/ontologic-y/board")
def momento_ontologic_y_board(
    date: str | None = None,
    view: str | None = None,
    support: str | None = None,
) -> dict:
    from roller.ontologic_y.api import handle_board

    return handle_board(date=date, view=view, support=support)


@app.get("/momento/ontologic-y/games/{game_id}")
def momento_ontologic_y_game(game_id: str) -> dict:
    from roller.ontologic_y.api import handle_game

    return handle_game(game_id)


@app.get("/momento/ontologic-z/health")
def momento_ontologic_z_health() -> dict:
    from roller.ontologic_xyz.api import handle_health

    return handle_health()


@app.get("/momento/ontologic-z/status")
def momento_ontologic_z_status(date: str = "2026-10-03") -> dict:
    from roller.ontologic_xyz.api import handle_status

    return handle_status(date)


@app.get("/momento/systems/{system_id}/schema")
def momento_system_schema(system_id: str) -> dict:
    from roller.momento.api import handle_schema

    return _momento_http(handle_schema, system_id)


@app.get("/momento/dataflow")
def momento_dataflow() -> dict:
    from roller.momento.api import handle_dataflow

    return handle_dataflow()


@app.get("/momento/health")
def momento_health() -> dict:
    from roller.momento.api import handle_health

    return handle_health()


@app.get("/momento/connection")
def momento_connection() -> dict:
    from roller.momento.api import handle_connection

    return handle_connection()


@app.get("/momento/ingestion")
def momento_ingestion() -> dict:
    from roller.momento.api import handle_ingestion

    return handle_ingestion()


@app.get("/momento/reconciliation")
def momento_reconciliation() -> dict:
    from roller.momento.api import handle_reconciliation

    return handle_reconciliation()


@app.get("/momento/lifecycle")
def momento_lifecycle() -> dict:
    from roller.momento.api import handle_lifecycle

    return handle_lifecycle()


@app.get("/momento/bdr")
def momento_bdr_catalog() -> dict:
    from roller.momento.api import handle_bdr_catalog

    return _momento_http(handle_bdr_catalog)


@app.get("/momento/bdr/{slug}")
def momento_bdr_document(slug: str) -> dict:
    from roller.momento.api import handle_bdr_document

    return _momento_http(handle_bdr_document, slug)


@app.get("/momento/tk-ultra")
def momento_tk_ultra() -> dict:
    from roller.momento.api import handle_tk_ultra

    return _momento_http(handle_tk_ultra)


@app.get("/momento/tk-ultra/assess")
def momento_tk_ultra_assess(
    wing_price: str | None = None,
    base_price: str | None = None,
    beta: str | None = None,
    wing_anchor: str | None = None,
    base_anchor: str | None = None,
    ticks_per_handle: str | None = None,
    pair: str | None = None,
    corridor_cents: str | None = None,
) -> dict:
    from roller.momento.api import handle_tk_ultra_assess

    return _momento_http(
        handle_tk_ultra_assess,
        wing_price=wing_price,
        base_price=base_price,
        beta=beta,
        wing_anchor=wing_anchor,
        base_anchor=base_anchor,
        ticks_per_handle=ticks_per_handle,
        pair=pair,
        corridor_cents=corridor_cents,
    )


@app.get("/momento/tk-ultra/health")
def momento_tk_ultra_health() -> dict:
    from roller.momento.api import handle_tk_ultra_health

    return _momento_http(handle_tk_ultra_health)


@app.get("/momento/tk-ultra/sources")
def momento_tk_ultra_sources() -> dict:
    from roller.momento.api import handle_tk_ultra_sources

    return _momento_http(handle_tk_ultra_sources)


@app.get("/momento/tk-ultra/positions")
def momento_tk_ultra_positions() -> dict:
    from roller.momento.api import handle_tk_ultra_positions

    return _momento_http(handle_tk_ultra_positions)


@app.get("/momento/tk-ultra/state/{trade_id}")
def momento_tk_ultra_state(
    trade_id: str,
    as_of: str | None = None,
    include_sibling: bool = False,
) -> dict:
    from roller.momento.api import handle_tk_ultra_state

    return _momento_http(handle_tk_ultra_state, trade_id, as_of, include_sibling)


@app.post("/momento/tk-ultra/assess")
def momento_tk_ultra_assess_v0(body: dict | None = None) -> dict:
    from roller.momento.api import handle_tk_ultra_assess_v0

    return _momento_http(handle_tk_ultra_assess_v0, body)


@app.get("/momento/tk-ultra/ballhog-context/{trade_id}")
def momento_tk_ultra_ballhog_context(trade_id: str, as_of: str | None = None) -> dict:
    from roller.momento.api import handle_tk_ultra_ballhog_context

    return _momento_http(handle_tk_ultra_ballhog_context, trade_id, as_of)


@app.get("/momento/tk-ultra-first78")
def momento_tk_ultra_first78() -> dict:
    from roller.tk_ultra_first78.api import _desk

    return _desk()


@app.get("/momento/tk-ultra-first78/assess")
def momento_tk_ultra_first78_assess(
    wing_price: str | None = None,
    base_price: str | None = None,
    beta: str | None = None,
    wing_anchor: str | None = None,
    base_anchor: str | None = None,
    ticks_per_handle: str | None = None,
    pair: str | None = None,
    corridor_cents: str | None = None,
) -> dict:
    from roller.tk_ultra_first78.api import handle_generic_assess

    return handle_generic_assess(
        wing_price=wing_price,
        base_price=base_price,
        beta=beta,
        wing_anchor=wing_anchor,
        base_anchor=base_anchor,
        ticks_per_handle=ticks_per_handle,
        pair=pair,
        corridor_cents=corridor_cents,
    )


@app.get("/momento/tk-ultra-first78/health")
def momento_tk_ultra_first78_health() -> dict:
    from roller.tk_ultra_first78.api import handle_health

    return handle_health()


@app.get("/momento/tk-ultra-first78/sources")
def momento_tk_ultra_first78_sources() -> dict:
    from roller.tk_ultra_first78.api import handle_sources

    return handle_sources()


@app.get("/momento/tk-ultra-first78/positions")
def momento_tk_ultra_first78_positions() -> dict:
    from roller.tk_ultra_first78.api import handle_positions

    return handle_positions()


@app.get("/momento/tk-ultra-first78/state/{trade_id}")
def momento_tk_ultra_first78_state(trade_id: str, as_of: str | None = None, include_sibling: bool = False) -> dict:
    from roller.tk_ultra_first78.api import handle_state

    return handle_state(trade_id, as_of=as_of, include_sibling=include_sibling)


@app.post("/momento/tk-ultra-first78/assess")
def momento_tk_ultra_first78_assess_v0(body: dict | None = None) -> dict:
    from roller.tk_ultra.errors import TkUltraV0Error
    from roller.tk_ultra_first78.api import handle_assess_v0

    try:
        return handle_assess_v0(body)
    except TkUltraV0Error as exc:
        raise HTTPException(status_code=exc.status_code, detail={"code": exc.code, "message": exc.message}) from exc


@app.get("/momento/tk-ultra-first78/ballhog-context/{trade_id}")
def momento_tk_ultra_first78_ballhog_context(trade_id: str, as_of: str | None = None) -> dict:
    from roller.tk_ultra_first78.api import handle_ballhog_context

    return handle_ballhog_context(trade_id, as_of)


def _choosin_http(fn, *args, **kwargs):
    from roller.choosin_texas.models import ChoosinTexasError

    try:
        return fn(*args, **kwargs)
    except ChoosinTexasError as exc:
        status = 409 if exc.code == "LOCK_MISMATCH" else 400
        raise HTTPException(status_code=status, detail=exc.as_dict()) from exc


@app.get("/choosin-texas/health")
def choosin_texas_health() -> dict:
    from roller.choosin_texas.api import handle_health

    return handle_health()


@app.get("/choosin-texas/first78")
def choosin_texas_first78(variant: str = "67") -> dict:
    from roller.choosin_texas.first78.api import handle_first78

    return _choosin_http(handle_first78, variant)


@app.get("/choosin-texas/universe")
def choosin_texas_universe() -> dict:
    from roller.choosin_texas.api import handle_universe

    return _choosin_http(handle_universe)


@app.get("/choosin-texas/universe-60")
def choosin_texas_universe_60() -> dict:
    from roller.choosin_texas.api import handle_universe_60

    return _choosin_http(handle_universe_60)


@app.get("/choosin-texas/paired-replay")
def choosin_texas_paired_replay() -> dict:
    from roller.choosin_texas.api import handle_paired_replay

    return _choosin_http(handle_paired_replay)


@app.get("/choosin-texas/paired-execution-validation")
def choosin_texas_execution_validation() -> dict:
    from roller.choosin_texas.api import handle_execution_validation

    return _choosin_http(handle_execution_validation)


@app.get("/choosin-texas/universe-75")
def choosin_texas_universe_75() -> dict:
    from roller.choosin_texas.api import handle_universe_75

    return _choosin_http(handle_universe_75)


@app.get("/choosin-texas/nba-path")
def choosin_texas_nba_path() -> dict:
    from roller.choosin_texas.api import handle_nba_path

    return _choosin_http(handle_nba_path)


@app.get("/choosin-texas/nba-path-75")
def choosin_texas_nba_path_75() -> dict:
    from roller.choosin_texas.api import handle_nba_path_75

    return _choosin_http(handle_nba_path_75)


@app.get("/choosin-texas/universe-77")
def choosin_texas_universe_77() -> dict:
    from roller.choosin_texas.api import handle_universe_77

    return _choosin_http(handle_universe_77)


@app.get("/choosin-texas/nba-path-77")
def choosin_texas_nba_path_77() -> dict:
    from roller.choosin_texas.api import handle_nba_path_77

    return _choosin_http(handle_nba_path_77)


@app.get("/choosin-texas/asked-six")
def choosin_texas_asked_six() -> dict:
    from roller.choosin_texas.api import handle_asked_six

    return _choosin_http(handle_asked_six)


@app.get("/choosin-texas/universe-81")
def choosin_texas_universe_81() -> dict:
    from roller.choosin_texas.api import handle_universe_81

    return _choosin_http(handle_universe_81)


@app.get("/choosin-texas/universe-83")
def choosin_texas_universe_83() -> dict:
    from roller.choosin_texas.api import handle_universe_83

    return _choosin_http(handle_universe_83)


@app.get("/choosin-texas/lubbock")
def choosin_texas_lubbock() -> dict:
    from roller.choosin_texas.api import handle_lubbock

    return _choosin_http(handle_lubbock)


@app.get("/choosin-texas/lubbock/export.csv")
def choosin_texas_lubbock_export(
    sport: str = Query(),
    season: str = Query(),
    phase: str = Query(),
    grain: str = Query(default="decile"),
) -> Response:
    from roller.choosin_texas.api import handle_lubbock_export

    filename, data = _choosin_http(handle_lubbock_export, sport, season, phase, grain)
    return Response(
        content=data,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.get("/choosin-texas/dallas")
def choosin_texas_dallas() -> dict:
    from roller.choosin_texas.api import handle_dallas

    return _choosin_http(handle_dallas)


@app.get("/choosin-texas/book")
def choosin_texas_book() -> dict:
    from roller.choosin_texas.api import handle_book

    return _choosin_http(handle_book)


@app.get("/choosin-texas/sugarland")
def choosin_texas_sugarland() -> dict:
    from roller.choosin_texas.api import handle_sugarland

    return _choosin_http(handle_sugarland)


@app.get("/choosin-texas/katy")
def choosin_texas_katy() -> dict:
    from roller.choosin_texas.api import handle_katy

    return _choosin_http(handle_katy)


@app.get("/choosin-texas/katy/{experiment_id}")
def choosin_texas_katy_experiment(experiment_id: str) -> dict:
    from roller.choosin_texas.api import handle_katy_experiment

    return _choosin_http(handle_katy_experiment, experiment_id)


def _austin_http(fn, *args, **kwargs):
    from roller.austin.errors import AustinError

    try:
        return fn(*args, **kwargs)
    except AustinError as exc:
        status = 409 if exc.code == "LOCK_MISMATCH" else 400
        raise HTTPException(status_code=status, detail=exc.as_dict()) from exc


@app.get("/austin/health")
def austin_health() -> dict:
    from roller.austin.api import handle_health

    return handle_health()


@app.get("/austin/dataset")
def austin_dataset() -> dict:
    from roller.austin.api import handle_dataset

    return _austin_http(handle_dataset)


@app.get("/austin/pca")
def austin_pca() -> dict:
    from roller.austin.api import handle_pca

    return _austin_http(handle_pca)


@app.get("/austin/validation")
def austin_validation() -> dict:
    from roller.austin.api import handle_validation

    return _austin_http(handle_validation)


@app.get("/austin/hedge")
def austin_hedge() -> dict:
    from roller.austin.api import handle_hedge

    return _austin_http(handle_hedge)


@app.get("/austin/sizing")
def austin_sizing() -> dict:
    from roller.austin.api import handle_sizing

    return _austin_http(handle_sizing)


@app.get("/austin/audit")
def austin_audit() -> dict:
    from roller.austin.api import handle_audit

    return _austin_http(handle_audit)


@app.get("/austin/lab")
def austin_lab() -> dict:
    from roller.austin.api import handle_lab

    return _austin_http(handle_lab)


@app.get("/austin/example")
def austin_example() -> dict:
    from roller.austin.api import handle_example_query

    return _austin_http(handle_example_query)


@app.get("/austin/games")
def austin_games() -> dict:
    from roller.austin.api import handle_games

    return _austin_http(handle_games)


@app.get("/austin/games/{game_id}/moments")
def austin_game_moments(game_id: str, side: str = "home") -> dict:
    from roller.austin.api import handle_game_moments

    return _austin_http(handle_game_moments, game_id, side)


@app.get("/austin/calibration")
def austin_calibration() -> dict:
    from roller.austin.api import handle_calibration

    return _austin_http(handle_calibration)


@app.get("/austin/integrity")
def austin_integrity() -> dict:
    from roller.austin.api import handle_integrity

    return _austin_http(handle_integrity)


@app.post("/austin/query")
def austin_query(body: dict) -> dict:
    from roller.austin.api import handle_query

    return _austin_http(handle_query, body)


@app.post("/austin/query/historical")
def austin_query_historical(body: dict) -> dict:
    from roller.austin.api import handle_query_historical

    return _austin_http(handle_query_historical, body)


@app.get("/austin/replay/{trade_id}")
def austin_replay(trade_id: str) -> dict:
    from roller.austin.api import handle_replay

    return _austin_http(handle_replay, trade_id)


@app.get("/austin/fort-worth/contract")
def austin_fort_worth() -> dict:
    from roller.austin.api import handle_fort_worth

    return _austin_http(handle_fort_worth)


@app.get("/austin/experiments")
def austin_experiments() -> dict:
    from roller.austin.api import handle_experiments

    return _austin_http(handle_experiments)


@app.get("/austin/experiments/{experiment_id}")
def austin_experiment(experiment_id: str) -> dict:
    from roller.austin.api import handle_experiment

    return _austin_http(handle_experiment, experiment_id)


def _austin78_http(fn, *args, **kwargs):
    from roller.austin.errors import AustinError

    try:
        return fn(*args, **kwargs)
    except AustinError as exc:
        status = 409 if exc.code == "LOCK_MISMATCH" else 400
        raise HTTPException(status_code=status, detail=exc.as_dict()) from exc


@app.get("/austin-first78/health")
def austin78_health() -> dict:
    from roller.austin_first78.api import handle_health

    return handle_health()


@app.get("/austin-first78/dataset")
def austin78_dataset() -> dict:
    from roller.austin_first78.api import handle_dataset

    return _austin78_http(handle_dataset)


@app.get("/austin-first78/pca")
def austin78_pca() -> dict:
    from roller.austin_first78.api import handle_pca

    return _austin78_http(handle_pca)


@app.get("/austin-first78/validation")
def austin78_validation() -> dict:
    from roller.austin_first78.api import handle_validation

    return _austin78_http(handle_validation)


@app.get("/austin-first78/hedge")
def austin78_hedge() -> dict:
    from roller.austin_first78.api import handle_hedge

    return _austin78_http(handle_hedge)


@app.get("/austin-first78/sizing")
def austin78_sizing() -> dict:
    from roller.austin_first78.api import handle_sizing

    return _austin78_http(handle_sizing)


@app.get("/austin-first78/audit")
def austin78_audit() -> dict:
    from roller.austin_first78.api import handle_audit

    return _austin78_http(handle_audit)


@app.get("/austin-first78/lab")
def austin78_lab() -> dict:
    from roller.austin_first78.api import handle_lab

    return _austin78_http(handle_lab)


@app.get("/austin-first78/example")
def austin78_example() -> dict:
    from roller.austin_first78.api import handle_example_query

    return _austin78_http(handle_example_query)


@app.get("/austin-first78/games")
def austin78_games() -> dict:
    from roller.austin_first78.api import handle_games

    return _austin78_http(handle_games)


@app.get("/austin-first78/games/{game_id}/moments")
def austin78_game_moments(game_id: str, side: str = "home") -> dict:
    from roller.austin_first78.api import handle_game_moments

    return _austin78_http(handle_game_moments, game_id, side)


@app.get("/austin-first78/calibration")
def austin78_calibration() -> dict:
    from roller.austin_first78.api import handle_calibration

    return _austin78_http(handle_calibration)


@app.post("/austin-first78/query")
def austin78_query(body: dict) -> dict:
    from roller.austin_first78.api import handle_query

    return _austin78_http(handle_query, body)


@app.post("/austin-first78/query/historical")
def austin78_query_historical(body: dict) -> dict:
    from roller.austin_first78.api import handle_query_historical

    return _austin78_http(handle_query_historical, body)


@app.get("/austin-first78/replay/{trade_id}")
def austin78_replay(trade_id: str) -> dict:
    from roller.austin_first78.api import handle_replay

    return _austin78_http(handle_replay, trade_id)


def _dre_http(fn, *args, **kwargs):
    from roller.austin.errors import AustinError
    from roller.choosin_texas.models import ChoosinTexasError
    from roller.dre.pit import DrePitError

    try:
        return fn(*args, **kwargs)
    except ChoosinTexasError as exc:
        status = 409 if exc.code == "LOCK_MISMATCH" else 400
        raise HTTPException(status_code=status, detail=exc.as_dict()) from exc
    except AustinError as exc:
        status = 409 if exc.code == "LOCK_MISMATCH" else 400
        raise HTTPException(status_code=status, detail=exc.as_dict()) from exc
    except DrePitError as exc:
        raise HTTPException(status_code=400, detail=exc.as_dict()) from exc


@app.get("/dre/health")
def dre_health() -> dict:
    from roller.dre.api import handle_health

    return handle_health()


@app.get("/dre")
def dre_desk() -> dict:
    from roller.dre.api import handle_desk

    return _dre_http(handle_desk)


@app.get("/dre/upstream/trade-breakdown")
def dre_trade_breakdown() -> dict:
    from roller.dre.api import handle_trade_breakdown

    return _dre_http(handle_trade_breakdown)


@app.get("/dre/upstream/stratum")
def dre_stratum() -> dict:
    from roller.dre.api import handle_stratum

    return _dre_http(handle_stratum)


@app.get("/dre/experiments")
def dre_experiments() -> dict:
    from roller.dre.api import handle_experiments

    return _dre_http(handle_experiments)


@app.get("/dre/experiments/{experiment_id}")
def dre_experiment(experiment_id: str) -> dict:
    from roller.dre.api import handle_experiment

    return _dre_http(handle_experiment, experiment_id)


@app.get("/dre/positions")
def dre_positions(slice: str | None = None, q: str | None = None, dataset_split: str | None = None) -> dict:
    from roller.dre.api import handle_positions

    return _dre_http(handle_positions, slice, q, dataset_split)


@app.get("/dre/positions/{position_id}")
def dre_position(position_id: str, as_of: str | None = None) -> dict:
    from roller.dre.api import handle_position

    return _dre_http(handle_position, position_id, as_of)


@app.get("/dre/replay/{trade_id}")
def dre_replay_position(trade_id: str, as_of: str | None = None) -> dict:
    from roller.dre.api import handle_replay_position

    return _dre_http(handle_replay_position, trade_id, as_of)


@app.get("/dre/decision/{trade_id}")
def dre_decision(trade_id: str, as_of: str | None = None) -> dict:
    from roller.dre.api import handle_decision

    return _dre_http(handle_decision, trade_id, as_of)


@app.get("/drevo/health")
def drevo_health() -> dict:
    from roller.dre.api import handle_health

    return handle_health()


@app.get("/drevo")
def drevo_desk() -> dict:
    from roller.dre.api import handle_desk

    return _dre_http(handle_desk)


@app.get("/drevo/decision/{trade_id}")
def drevo_decision(trade_id: str, as_of: str | None = None) -> dict:
    from roller.dre.api import handle_decision

    return _dre_http(handle_decision, trade_id, as_of)


def _mount_dre_first78(prefix: str) -> None:
    @app.get(f"{prefix}/health")
    def _health() -> dict:
        from roller.dre_first78.api import handle_health

        return handle_health()

    @app.get(prefix)
    def _desk() -> dict:
        from roller.dre_first78.api import handle_desk

        return _dre_http(handle_desk)

    @app.get(f"{prefix}/upstream/trade-breakdown")
    def _trade() -> dict:
        from roller.dre_first78.api import handle_trade_breakdown

        return _dre_http(handle_trade_breakdown)

    @app.get(f"{prefix}/upstream/stratum")
    def _stratum() -> dict:
        from roller.dre_first78.api import handle_stratum

        return _dre_http(handle_stratum)

    @app.get(f"{prefix}/experiments")
    def _experiments() -> dict:
        from roller.dre_first78.api import handle_experiments

        return _dre_http(handle_experiments)

    @app.get(f"{prefix}/experiments/{{experiment_id}}")
    def _experiment(experiment_id: str) -> dict:
        from roller.dre_first78.api import handle_experiment

        return _dre_http(handle_experiment, experiment_id)

    @app.get(f"{prefix}/positions")
    def _positions(slice: str | None = None, q: str | None = None, dataset_split: str | None = None) -> dict:
        from roller.dre_first78.api import handle_positions

        return _dre_http(handle_positions, slice, q, dataset_split)

    @app.get(f"{prefix}/positions/{{position_id}}")
    def _position(position_id: str, as_of: str | None = None) -> dict:
        from roller.dre_first78.api import handle_position

        return _dre_http(handle_position, position_id, as_of)

    @app.get(f"{prefix}/replay/{{trade_id}}")
    def _replay(trade_id: str, as_of: str | None = None) -> dict:
        from roller.dre_first78.api import handle_replay_position

        return _dre_http(handle_replay_position, trade_id, as_of)

    @app.get(f"{prefix}/decision/{{trade_id}}")
    def _decision(trade_id: str, as_of: str | None = None) -> dict:
        from roller.dre_first78.api import handle_decision

        return _dre_http(handle_decision, trade_id, as_of)


_mount_dre_first78("/dre-first78")
_mount_dre_first78("/drevo-first78")


def _ballhog_http(fn, *args, **kwargs):
    from roller.austin.errors import AustinError
    from roller.ballhog.errors import BallhogError
    from roller.choosin_texas.models import ChoosinTexasError
    from roller.dre.pit import DrePitError

    try:
        return fn(*args, **kwargs)
    except BallhogError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.as_dict()) from exc
    except ChoosinTexasError as exc:
        status = 409 if exc.code == "LOCK_MISMATCH" else 400
        raise HTTPException(status_code=status, detail=exc.as_dict()) from exc
    except AustinError as exc:
        status = 409 if exc.code == "LOCK_MISMATCH" else 400
        raise HTTPException(status_code=status, detail=exc.as_dict()) from exc
    except DrePitError as exc:
        raise HTTPException(status_code=400, detail=exc.as_dict()) from exc


@app.get("/ballhog/health")
def ballhog_health() -> dict:
    from roller.ballhog.api import handle_health

    return handle_health()


@app.get("/ballhog")
def ballhog_desk() -> dict:
    from roller.ballhog.api import handle_desk

    return _ballhog_http(handle_desk)


@app.get("/ballhog/sources")
def ballhog_sources() -> dict:
    from roller.ballhog.api import handle_sources

    return _ballhog_http(handle_sources)


@app.get("/ballhog/positions")
def ballhog_positions() -> dict:
    from roller.ballhog.api import handle_positions

    return _ballhog_http(handle_positions)


@app.get("/ballhog/state/{trade_id}")
def ballhog_state(trade_id: str, as_of: str | None = None, q_dir: str | None = None) -> dict:
    from roller.ballhog.api import handle_state

    return _ballhog_http(handle_state, trade_id, as_of, q_dir)


@app.post("/ballhog/surface")
def ballhog_surface(body: dict | None = None) -> dict:
    from roller.ballhog.api import handle_surface

    return _ballhog_http(handle_surface, body or {})


@app.post("/ballhog/frontier")
def ballhog_frontier(body: dict | None = None) -> dict:
    from roller.ballhog.api import handle_frontier

    return _ballhog_http(handle_frontier, body or {})


@app.post("/ballhog/decision")
def ballhog_decision(body: dict | None = None) -> dict:
    from roller.ballhog.api import handle_decision

    return _ballhog_http(handle_decision, body or {})


@app.post("/ballhog/transitions")
def ballhog_transitions_post(body: dict | None = None) -> dict:
    from roller.ballhog.api import handle_transitions

    return _ballhog_http(handle_transitions, body or {})


@app.get("/ballhog/transitions")
def ballhog_transitions_get(trade_id: str, as_of: str | None = None) -> dict:
    from roller.ballhog.api import handle_transitions

    return _ballhog_http(handle_transitions, None, trade_id, as_of)


def _positman_http(fn, *args, **kwargs):
    from roller.positman.errors import PositmanError
    from roller.systimo.errors import SystimoError

    try:
        return fn(*args, **kwargs)
    except PositmanError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.as_dict()) from exc
    except SystimoError as exc:
        raise HTTPException(status_code=exc.status_code, detail={"code": exc.code, "message": exc.message}) from exc


@app.get("/positman/health")
def positman_health() -> dict:
    from roller.positman.api import handle_health

    return handle_health()


@app.get("/positman/sources")
def positman_sources() -> dict:
    from roller.positman.api import handle_sources

    return handle_sources()


@app.get("/positman/state/{trade_id}")
def positman_state(trade_id: str, as_of: str | None = None) -> dict:
    from roller.positman.api import handle_state

    return _positman_http(handle_state, trade_id, as_of)


@app.get("/positman/plan/{trade_id}")
def positman_plan_get(trade_id: str, as_of: str | None = None) -> dict:
    from roller.positman.api import handle_plan

    return _positman_http(handle_plan, trade_id, as_of)


@app.post("/positman/plan")
def positman_plan_post(body: dict | None = None) -> dict:
    from roller.positman.api import handle_plan

    payload = body or {}
    return _positman_http(handle_plan, payload.get("trade_id"), payload.get("as_of"))


@app.get("/positman/trace/{trace_id}")
def positman_trace(trace_id: str) -> dict:
    from roller.positman.api import handle_trace

    return _positman_http(handle_trace, trace_id)


@app.get("/positman-first78/health")
def positman_first78_health() -> dict:
    from roller.positman_first78.api import handle_health

    return handle_health()


@app.get("/positman-first78/sources")
def positman_first78_sources() -> dict:
    from roller.positman_first78.api import handle_sources

    return _positman_http(handle_sources)


@app.get("/positman-first78/state/{trade_id}")
def positman_first78_state(trade_id: str, as_of: str | None = None) -> dict:
    from roller.positman_first78.api import handle_state

    return _positman_http(handle_state, trade_id, as_of)


@app.get("/positman-first78/plan/{trade_id}")
def positman_first78_plan_get(trade_id: str, as_of: str | None = None) -> dict:
    from roller.positman_first78.api import handle_plan

    return _positman_http(handle_plan, trade_id, as_of)


@app.post("/positman-first78/plan")
def positman_first78_plan_post(body: dict | None = None) -> dict:
    from roller.positman_first78.api import handle_plan

    payload = body or {}
    return _positman_http(handle_plan, payload.get("trade_id"), payload.get("as_of"))


@app.get("/positman-first78/trace/{trace_id}")
def positman_first78_trace(trace_id: str) -> dict:
    from roller.positman_first78.api import handle_trace

    return _positman_http(handle_trace, trace_id)


@app.get("/ballhog/intent/{trade_id}")
def ballhog_intent(trade_id: str, as_of: str | None = None, q_dir: str | None = None) -> dict:
    from roller.ballhog.api import handle_intent

    return _ballhog_http(handle_intent, trade_id, as_of, q_dir)


@app.get("/ballhog-first78/health")
def ballhog_first78_health() -> dict:
    from roller.ballhog_first78.api import handle_health

    return handle_health()


@app.get("/ballhog-first78")
def ballhog_first78_desk() -> dict:
    from roller.ballhog_first78.api import handle_desk

    return _ballhog_http(handle_desk)


@app.get("/ballhog-first78/sources")
def ballhog_first78_sources() -> dict:
    from roller.ballhog_first78.api import handle_sources

    return _ballhog_http(handle_sources)


@app.get("/ballhog-first78/positions")
def ballhog_first78_positions() -> dict:
    from roller.ballhog_first78.api import handle_positions

    return _ballhog_http(handle_positions)


@app.get("/ballhog-first78/state/{trade_id}")
def ballhog_first78_state(trade_id: str, as_of: str | None = None, q_dir: str | None = None) -> dict:
    from roller.ballhog_first78.api import handle_state

    return _ballhog_http(handle_state, trade_id, as_of, q_dir)


@app.post("/ballhog-first78/surface")
def ballhog_first78_surface(body: dict | None = None) -> dict:
    from roller.ballhog_first78.api import handle_surface

    return _ballhog_http(handle_surface, body or {})


@app.post("/ballhog-first78/frontier")
def ballhog_first78_frontier(body: dict | None = None) -> dict:
    from roller.ballhog_first78.api import handle_frontier

    return _ballhog_http(handle_frontier, body or {})


@app.post("/ballhog-first78/decision")
def ballhog_first78_decision(body: dict | None = None) -> dict:
    from roller.ballhog_first78.api import handle_decision

    return _ballhog_http(handle_decision, body or {})


@app.post("/ballhog-first78/transitions")
def ballhog_first78_transitions_post(body: dict | None = None) -> dict:
    from roller.ballhog_first78.api import handle_transitions

    return _ballhog_http(handle_transitions, body or {})


@app.get("/ballhog-first78/transitions")
def ballhog_first78_transitions_get(trade_id: str, as_of: str | None = None) -> dict:
    from roller.ballhog_first78.api import handle_transitions

    return _ballhog_http(handle_transitions, None, trade_id, as_of)


@app.get("/ballhog-first78/intent/{trade_id}")
def ballhog_first78_intent(trade_id: str, as_of: str | None = None, q_dir: str | None = None) -> dict:
    from roller.ballhog_first78.api import handle_intent

    return _ballhog_http(handle_intent, trade_id, as_of, q_dir)


@app.get("/superasi/seed/asked-six")
def superasi_seed() -> dict:
    from roller.superasi.api import handle_seed
    from roller.superasi.models import SuperasiError

    try:
        return handle_seed()
    except SuperasiError as exc:
        raise HTTPException(status_code=400, detail=exc.as_dict()) from exc


def _content_disposition(filename: str) -> str:
    safe = "".join(ch if ch.isascii() and ch not in {"\"", "\\"} else "_" for ch in str(filename or ""))
    fallback = safe or "download.csv"
    return f"attachment; filename=\"{fallback}\"; filename*=UTF-8''{quote(str(filename or fallback))}"


def _superasi_http(fn, *args, **kwargs):
    from roller.jump.errors import JumpError
    from roller.superasi.models import SuperasiError

    try:
        return fn(*args, **kwargs)
    except SuperasiError as exc:
        code = 404 if exc.code in {"LAB_NOT_FOUND", "RESULT_NOT_FOUND", "HANDOFF_NOT_FOUND"} else 400
        raise HTTPException(status_code=code, detail=exc.as_dict()) from exc
    except JumpError as exc:
        code = 404 if exc.code in {"RESULT_NOT_FOUND", "RUN_NOT_FOUND"} else 400
        raise HTTPException(status_code=code, detail=exc.as_dict()) from exc


@app.get("/superasi/base/sources")
def superasi_base_sources(folder: str | None = Query(default=None)) -> dict:
    from roller.superasi.base.api import handle_sources

    return handle_sources(folder=folder)


@app.get("/superasi/base/sources/{lab_id}")
def superasi_base_source(lab_id: str) -> dict:
    from roller.superasi.base.api import handle_source

    return _superasi_http(handle_source, lab_id)


@app.post("/superasi/base/run")
def superasi_base_run(body: dict[str, Any] | None = None) -> dict:
    from roller.superasi.base.api import handle_run

    return _superasi_http(handle_run, body or {})


@app.get("/superasi/base/results")
def superasi_base_results() -> dict:
    from roller.superasi.base.api import handle_results

    return handle_results()


@app.get("/superasi/base/results/{result_id}")
def superasi_base_result(result_id: str) -> dict:
    from roller.superasi.base.api import handle_result

    return _superasi_http(handle_result, result_id)


@app.get("/superasi/base/results/{result_id}/csv")
def superasi_base_result_csv(result_id: str, which: str = Query(default="base")) -> Response:
    from roller.superasi.base.api import handle_result_csv

    filename, data = _superasi_http(handle_result_csv, result_id, which=which)
    return Response(
        content=data,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": _content_disposition(filename)},
    )


@app.get("/superasi/debase/sources")
def superasi_debase_sources() -> dict:
    from roller.superasi.debase.api import handle_sources

    return handle_sources()


@app.post("/superasi/debase/run")
def superasi_debase_run(body: dict[str, Any] | None = None) -> dict:
    from roller.superasi.debase.api import handle_run

    return _superasi_http(handle_run, body or {})


@app.post("/superasi/handoff")
def superasi_handoff(body: dict[str, Any] | None = None) -> dict:
    from roller.superasi.handoff import handle_handoff

    return _superasi_http(handle_handoff, body or {})


@app.get("/superasi/handoff/latest")
def superasi_handoff_latest(lab_id: str = Query(...)) -> dict:
    from roller.superasi.handoff import handle_latest_handoff

    return _superasi_http(handle_latest_handoff, lab_id)


@app.get("/superasi/handoff/{handoff_id}")
def superasi_handoff_get(handoff_id: str) -> dict:
    from roller.superasi.handoff import handle_get_handoff

    return _superasi_http(handle_get_handoff, handoff_id)


@app.get("/superasi/debase/results")
def superasi_debase_results() -> dict:
    from roller.superasi.debase.api import handle_results

    return handle_results()


@app.get("/superasi/debase/results/{result_id}")
def superasi_debase_result(result_id: str) -> dict:
    from roller.superasi.debase.api import handle_result

    return _superasi_http(handle_result, result_id)


@app.get("/superasi/debase/results/{result_id}/csv")
def superasi_debase_result_csv(result_id: str, which: str = Query(default="debase")) -> Response:
    from roller.superasi.debase.api import handle_result_csv

    filename, data = _superasi_http(handle_result_csv, result_id, which=which)
    return Response(
        content=data,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": _content_disposition(filename)},
    )


@app.post("/superasi/iti/run")
def superasi_iti_run(body: dict[str, Any] | None = None) -> dict:
    from roller.superasi.iti.api import handle_iti_run

    return _superasi_http(handle_iti_run, body or {})


@app.get("/superasi/iti")
def superasi_iti_list(debase_result_id: str | None = None) -> dict:
    from roller.superasi.iti.api import handle_iti_list

    return handle_iti_list(debase_result_id)


@app.get("/superasi/iti/{run_id}")
def superasi_iti_get(run_id: str) -> dict:
    from roller.superasi.iti.api import handle_iti_get

    return _superasi_http(handle_iti_get, run_id)


@app.post("/superasi/iti/{run_id}/commit")
def superasi_iti_commit(run_id: str, body: dict[str, Any] | None = None) -> dict:
    from roller.superasi.iti.api import handle_iti_commit

    return _superasi_http(handle_iti_commit, run_id, body or {})


def _jump_http(fn, *args, **kwargs):
    from roller.jump.errors import JumpError

    try:
        return fn(*args, **kwargs)
    except JumpError as exc:
        code = 404 if exc.code in {"RESULT_NOT_FOUND", "RUN_NOT_FOUND", "BOT_NOT_FOUND", "WAREHOUSE_UNAVAILABLE"} else 400
        raise HTTPException(status_code=code, detail=exc.as_dict()) from exc


@app.get("/jump")
def jump_drive_root(sport: str | None = None) -> dict:
    from roller.jump.api import handle_drive_root

    return _jump_http(handle_drive_root, sport)


@app.get("/jump/sports")
def jump_drive_sports() -> dict:
    from roller.jump.api import handle_drive_sports

    return handle_drive_sports()


@app.get("/jump/research/{canonical_key}/children")
def jump_drive_research_children(canonical_key: str) -> dict:
    from roller.jump.api import handle_drive_research_children

    return _jump_http(handle_drive_research_children, canonical_key)


@app.get("/jump/research/{canonical_key}")
def jump_drive_research_object(canonical_key: str) -> dict:
    from roller.jump.api import handle_drive_research_object

    return _jump_http(handle_drive_research_object, canonical_key)


@app.get("/jump/research")
def jump_drive_research(sport: str | None = None) -> dict:
    from roller.jump.api import handle_drive_research

    return _jump_http(handle_drive_research, sport)


@app.get("/jump/documents/{doc_id}")
def jump_drive_document(doc_id: str) -> dict:
    from roller.jump.api import handle_drive_document

    return _jump_http(handle_drive_document, doc_id)


@app.post("/jump/index/refresh")
def jump_drive_refresh() -> dict:
    from roller.jump.api import handle_drive_refresh

    return handle_drive_refresh()


@app.get("/jump/warehouses")
def jump_warehouses() -> dict:
    from roller.jump.warehouse.api import handle_list

    return _jump_http(handle_list)


@app.get("/jump/warehouses/{warehouse_id}/tables/{table}/columns")
def jump_warehouse_columns(warehouse_id: str, table: str) -> dict:
    from roller.jump.warehouse.api import handle_columns

    return _jump_http(handle_columns, warehouse_id, table)


@app.get("/jump/warehouses/{warehouse_id}/tables/{table}/rows")
def jump_warehouse_rows(
    warehouse_id: str,
    table: str,
    limit: int = 100,
    page: int = 1,
    sort: str | None = None,
    order: str = "asc",
    columns: str | None = None,
    filters: str | None = None,
) -> dict:
    from roller.jump.warehouse.api import handle_rows

    return _jump_http(
        handle_rows,
        warehouse_id,
        table,
        limit=limit,
        page=page,
        sort=sort,
        order=order,
        columns=columns,
        filters=filters,
    )


@app.get("/jump/warehouses/{warehouse_id}/tables/{table}/stats")
def jump_warehouse_stats(warehouse_id: str, table: str, compute: int = 0) -> dict:
    from roller.jump.warehouse.api import handle_stats

    return _jump_http(handle_stats, warehouse_id, table, compute=bool(compute))


@app.get("/jump/warehouses/{warehouse_id}/tables/{table}/lineage")
def jump_warehouse_lineage(warehouse_id: str, table: str) -> dict:
    from roller.jump.warehouse.api import handle_lineage

    return _jump_http(handle_lineage, warehouse_id, table)


@app.get("/jump/warehouses/{warehouse_id}/tables/{table}")
def jump_warehouse_table(warehouse_id: str, table: str) -> dict:
    from roller.jump.warehouse.api import handle_table

    return _jump_http(handle_table, warehouse_id, table)


@app.get("/jump/warehouses/{warehouse_id}/tables")
def jump_warehouse_tables(warehouse_id: str) -> dict:
    from roller.jump.warehouse.api import handle_tables

    return _jump_http(handle_tables, warehouse_id)


@app.get("/jump/warehouses/{warehouse_id}/relationships")
def jump_warehouse_relationships(warehouse_id: str) -> dict:
    from roller.jump.warehouse.api import handle_relationships

    return _jump_http(handle_relationships, warehouse_id)


@app.post("/jump/warehouses/{warehouse_id}/relationships/layout")
def jump_warehouse_relationships_layout(warehouse_id: str, body: dict[str, Any] | None = None) -> dict:
    from roller.jump.warehouse.api import handle_relationships_layout

    return _jump_http(handle_relationships_layout, warehouse_id, body or {})


@app.get("/jump/warehouses/{warehouse_id}/dictionary")
def jump_warehouse_dictionary(warehouse_id: str) -> dict:
    from roller.jump.warehouse.api import handle_dictionary

    return _jump_http(handle_dictionary, warehouse_id)


@app.get("/jump/warehouses/{warehouse_id}/files")
def jump_warehouse_files(warehouse_id: str) -> dict:
    from roller.jump.warehouse.api import handle_files

    return _jump_http(handle_files, warehouse_id)


@app.get("/jump/warehouses/{warehouse_id}/views")
def jump_warehouse_views(warehouse_id: str) -> dict:
    from roller.jump.warehouse.api import handle_views

    return _jump_http(handle_views, warehouse_id)


@app.post("/jump/warehouses/{warehouse_id}/views")
def jump_warehouse_view_create(warehouse_id: str, body: dict[str, Any] | None = None) -> dict:
    from roller.jump.warehouse.api import handle_view_create

    return _jump_http(handle_view_create, warehouse_id, body or {})


@app.post("/jump/warehouses/{warehouse_id}/query")
def jump_warehouse_query(warehouse_id: str, body: dict[str, Any] | None = None) -> dict:
    from roller.jump.warehouse.api import handle_query

    return _jump_http(handle_query, warehouse_id, body or {})


@app.post("/jump/warehouses/{warehouse_id}/refresh")
def jump_warehouse_refresh(warehouse_id: str) -> dict:
    from roller.jump.warehouse.api import handle_refresh

    return _jump_http(handle_refresh, warehouse_id)


@app.post("/jump/warehouses/{warehouse_id}/validate")
def jump_warehouse_validate(warehouse_id: str) -> dict:
    from roller.jump.warehouse.api import handle_validate

    return _jump_http(handle_validate, warehouse_id)


@app.get("/jump/warehouses/{warehouse_id}")
def jump_warehouse_get(warehouse_id: str) -> dict:
    from roller.jump.warehouse.api import handle_get

    return _jump_http(handle_get, warehouse_id)


@app.get("/jump/queries")
def jump_queries(warehouse_id: str | None = None) -> dict:
    from roller.jump.warehouse.api import handle_queries_list

    return _jump_http(handle_queries_list, warehouse_id)


@app.post("/jump/queries")
def jump_query_create(body: dict[str, Any] | None = None) -> dict:
    from roller.jump.warehouse.api import handle_query_create

    return _jump_http(handle_query_create, body or {})


@app.get("/jump/queries/{query_id}")
def jump_query_get(query_id: str) -> dict:
    from roller.jump.warehouse.api import handle_query_get

    return _jump_http(handle_query_get, query_id)


@app.patch("/jump/queries/{query_id}")
def jump_query_patch(query_id: str, body: dict[str, Any] | None = None) -> dict:
    from roller.jump.warehouse.api import handle_query_patch

    return _jump_http(handle_query_patch, query_id, body or {})


@app.delete("/jump/queries/{query_id}")
def jump_query_delete(query_id: str) -> dict:
    from roller.jump.warehouse.api import handle_query_delete

    return _jump_http(handle_query_delete, query_id)


@app.get("/jump/tree")
def jump_drive_tree() -> dict:
    from roller.jump.api import handle_drive_tree

    return handle_drive_tree()


@app.get("/jump/search")
def jump_drive_search(q: str = "") -> dict:
    from roller.jump.api import handle_drive_search

    return handle_drive_search(q)


@app.get("/jump/recent")
def jump_drive_recent() -> dict:
    from roller.jump.api import handle_drive_recent

    return handle_drive_recent()


@app.get("/jump/folders/{folder_id}")
def jump_drive_folder(folder_id: str) -> dict:
    from roller.jump.api import handle_drive_folder

    return _jump_http(handle_drive_folder, folder_id)


@app.get("/jump/artifacts")
def jump_drive_artifacts() -> dict:
    from roller.jump.api import handle_drive_artifacts

    return handle_drive_artifacts()


@app.get("/jump/artifacts/{artifact_id}/preview")
def jump_drive_preview(artifact_id: str) -> dict:
    from roller.jump.api import handle_drive_preview

    return _jump_http(handle_drive_preview, artifact_id)


@app.get("/jump/artifacts/{artifact_id}/upstream")
def jump_drive_upstream(artifact_id: str) -> dict:
    from roller.jump.api import handle_drive_edges

    return _jump_http(handle_drive_edges, artifact_id, "upstream")


@app.get("/jump/artifacts/{artifact_id}/downstream")
def jump_drive_downstream(artifact_id: str) -> dict:
    from roller.jump.api import handle_drive_edges

    return _jump_http(handle_drive_edges, artifact_id, "downstream")


@app.get("/jump/artifacts/{artifact_id}")
def jump_drive_artifact(artifact_id: str) -> dict:
    from roller.jump.api import handle_drive_artifact

    return _jump_http(handle_drive_artifact, artifact_id)


@app.get("/jump/health")
def jump_health() -> dict:
    from roller.jump.api import handle_health

    return handle_health()


@app.get("/jump/research-context/austin")
def jump_research_context_austin(trade_id: str | None = None, as_of: str | None = None) -> dict:
    from roller.jump.api import handle_research_context_austin

    return handle_research_context_austin(trade_id, as_of)


@app.get("/jump/research-context/choosin")
def jump_research_context_choosin() -> dict:
    from roller.jump.api import handle_research_context_choosin

    return handle_research_context_choosin()


@app.get("/jump/data/sources")
def jump_data_sources() -> dict:
    from roller.jump.data.api import handle_sources

    return handle_sources()


@app.get("/jump/data/sources/{system_id}")
def jump_data_source(system_id: str) -> dict:
    from roller.jump.data.api import handle_source

    return _jump_http(handle_source, system_id)


@app.post("/jump/data/query")
def jump_data_query(body: dict | None = None) -> dict:
    from roller.jump.data.api import handle_query

    return _jump_http(handle_query, body or {})


@app.get("/jump/data/context/{trade_id}")
def jump_data_context(trade_id: str, as_of: str | None = None) -> dict:
    from roller.jump.data.api import handle_context

    return handle_context(trade_id, as_of)


@app.get("/jump/data/lineage/{resource_id}")
def jump_data_lineage(resource_id: str, capability: str | None = None, trade_id: str | None = None, as_of: str | None = None) -> dict:
    from roller.jump.data.api import handle_lineage

    return handle_lineage(resource_id, {"capability": capability, "trade_id": trade_id, "as_of": as_of})


@app.get("/jump/data/datasets")
def jump_data_datasets() -> dict:
    from roller.jump.data.api import handle_datasets

    return handle_datasets()


@app.post("/jump/data/export")
def jump_data_export(body: dict | None = None) -> dict:
    from roller.jump.data.api import handle_export

    return _jump_http(handle_export, body or {})


@app.post("/jump/iti/run")
def jump_iti_run(body: dict[str, Any] | None = None) -> dict:
    from roller.jump.api import handle_iti_run

    return _jump_http(handle_iti_run, body or {})


@app.get("/jump/iti")
def jump_iti_list(debase_result_id: str | None = None) -> dict:
    from roller.jump.api import handle_iti_list

    return handle_iti_list(debase_result_id)


@app.get("/jump/iti-commits")
def jump_iti_commits() -> dict:
    from roller.jump.api import handle_iti_commits

    return handle_iti_commits()


@app.get("/jump/iti/{run_id}")
def jump_iti_get(run_id: str) -> dict:
    from roller.jump.api import handle_iti_get

    return _jump_http(handle_iti_get, run_id)


@app.post("/jump/iti/{run_id}/commit")
def jump_iti_commit(run_id: str, body: dict[str, Any] | None = None) -> dict:
    from roller.jump.api import handle_iti_commit

    return _jump_http(handle_iti_commit, run_id, body or {})


@app.get("/jump/bots")
def jump_bots_list() -> dict:
    from roller.jump.api import handle_bots_list

    return handle_bots_list()


@app.get("/jump/bots/{bot_id}")
def jump_bots_get(bot_id: str) -> dict:
    from roller.jump.api import handle_bots_get

    return _jump_http(handle_bots_get, bot_id)


@app.post("/jump/bots/draft")
def jump_bots_draft(body: dict[str, Any] | None = None) -> dict:
    from roller.jump.api import handle_bots_draft

    return _jump_http(handle_bots_draft, body or {})


@app.post("/jump/bots")
def jump_bots_create(body: dict[str, Any] | None = None) -> dict:
    from roller.jump.api import handle_bots_create

    return _jump_http(handle_bots_create, body or {})


@app.post("/jump/bots/{bot_id}/production")
def jump_bots_production(bot_id: str, body: dict[str, Any] | None = None) -> dict:
    from roller.jump.api import handle_bots_production

    return _jump_http(handle_bots_production, bot_id, body or {})


@app.patch("/jump/bots/{bot_id}/profile")
def jump_bots_profile(bot_id: str, body: dict[str, Any] | None = None) -> dict:
    from roller.jump.api import handle_bots_profile

    return _jump_http(handle_bots_profile, bot_id, body or {})


@app.get("/jump/bots/{bot_id}/avatar")
def jump_bots_avatar(bot_id: str):
    from roller.jump.api import handle_bots_avatar

    data, media = _jump_http(handle_bots_avatar, bot_id)
    return Response(content=data, media_type=media)


@app.get("/jump/bots/{bot_id}/trades")
def jump_bots_trades(bot_id: str) -> dict:
    from roller.jump.api import handle_bots_trades

    return _jump_http(handle_bots_trades, bot_id)


@app.get("/jump/dashboard")
def jump_dashboard(by: str = "all", value: str = "") -> dict:
    from roller.jump.api import handle_dashboard

    return handle_dashboard(by=by, value=value)


@app.get("/jump/dashboard/logs")
def jump_dashboard_logs() -> dict:
    from roller.jump.api import handle_dashboard_logs

    return handle_dashboard_logs()


@app.get("/jump/catalog")
def jump_catalog(environment: str | None = None) -> dict:
    from roller.jump.api import handle_catalog

    return handle_catalog(environment=environment)


@app.post("/jump/catalog/refresh")
def jump_catalog_refresh(body: dict[str, Any] | None = None) -> dict:
    from roller.jump.api import handle_catalog_refresh

    return _jump_http(handle_catalog_refresh, body or {})


@app.get("/jump/kalshi")
def jump_kalshi() -> dict:
    from roller.jump.api import handle_kalshi_status

    return handle_kalshi_status()


@app.post("/jump/kalshi/sync")
def jump_kalshi_sync() -> dict:
    from roller.jump.api import handle_kalshi_sync

    return _jump_http(handle_kalshi_sync)


@app.get("/jump/mybots")
def jump_mybots() -> dict:
    from roller.jump.api import handle_mybots

    return handle_mybots()


def _vital_http(fn, *args, **kwargs):
    from roller.vital.errors import VitalError

    try:
        return fn(*args, **kwargs)
    except VitalError as exc:
        code = 404 if exc.code in {"BOT_NOT_FOUND", "TRADE_NOT_FOUND"} else 400
        raise HTTPException(status_code=code, detail=exc.as_dict()) from exc


@app.get("/vital/health")
def vital_health() -> dict:
    from roller.vital.api import handle_health

    return handle_health()


@app.get("/vital/desk")
def vital_desk(bot_id: str | None = None, surface: str = "list") -> dict:
    from roller.vital.api import handle_desk

    return _vital_http(handle_desk, bot_id, surface)


@app.get("/vital/bankroll")
def vital_bankroll() -> dict:
    from roller.vital.api import handle_bankroll_get

    return handle_bankroll_get()


@app.get("/vital/bots")
def vital_bots_list() -> dict:
    from roller.vital.api import handle_bots_list

    return handle_bots_list()


@app.get("/vital/bots/{bot_id}")
def vital_bots_get(bot_id: str) -> dict:
    from roller.vital.api import handle_bots_get

    return _vital_http(handle_bots_get, bot_id)


@app.get("/vital/bots/{bot_id}/status")
def vital_bots_status(bot_id: str) -> dict:
    from roller.vital.api import handle_status

    return _vital_http(handle_status, bot_id)


@app.get("/vital/bots/{bot_id}/health")
def vital_bots_health(bot_id: str) -> dict:
    from roller.vital.api import handle_bot_health

    return _vital_http(handle_bot_health, bot_id)


@app.get("/vital/bots/{bot_id}/runtime")
def vital_bots_runtime(bot_id: str) -> dict:
    from roller.vital.api import handle_runtime

    return _vital_http(handle_runtime, bot_id)


@app.post("/vital/bots/{bot_id}/host/observe")
def vital_bots_host_observe(bot_id: str) -> dict:
    from roller.vital.api import handle_host_observe

    return _vital_http(handle_host_observe, bot_id)


@app.get("/vital/bots/{bot_id}/integration")
def vital_bots_integration(bot_id: str) -> dict:
    from roller.vital.api import handle_integration

    return _vital_http(handle_integration, bot_id)


class VitalIntegrationBody(BaseModel):
    confirmation: str | None = None
    refresh: bool | None = None
    vital_test_id: str | None = None
    strategy_id: str | None = None
    signal_id: str | None = None
    intent_id: str | None = None
    order_id: str | None = None
    fill_id: str | None = None
    risk_decision: str | None = None
    demo_order_attempt: bool | None = None
    demo_exchange_response: str | None = None


@app.post("/vital/bots/{bot_id}/integration/demo-lifecycle")
def vital_bots_demo_lifecycle(bot_id: str, body: VitalIntegrationBody | None = None) -> dict:
    from roller.vital.api import handle_demo_lifecycle

    return _vital_http(handle_demo_lifecycle, bot_id, body.model_dump() if body else {})


@app.post("/vital/bots/{bot_id}/integration/handshake")
def vital_bots_integration_handshake(bot_id: str, body: VitalIntegrationBody | None = None) -> dict:
    from roller.vital.api import handle_integration_handshake

    return _vital_http(handle_integration_handshake, bot_id, body.model_dump() if body else {})


@app.get("/vital/bots/{bot_id}/deployment")
def vital_bots_deployment(bot_id: str) -> dict:
    from roller.vital.api import handle_deployment

    return _vital_http(handle_deployment, bot_id)


@app.get("/vital/bots/{bot_id}/logs")
def vital_bots_logs(bot_id: str) -> dict:
    from roller.vital.api import handle_logs

    return _vital_http(handle_logs, bot_id)


@app.get("/vital/bots/{bot_id}/parameters")
def vital_bots_parameters(bot_id: str) -> dict:
    from roller.vital.api import handle_parameters

    return _vital_http(handle_parameters, bot_id)


@app.patch("/vital/bots/{bot_id}/parameters")
def vital_bots_parameters_patch(bot_id: str, body: dict[str, Any] | None = None) -> dict:
    from roller.vital.api import handle_parameters_patch

    return _vital_http(handle_parameters_patch, bot_id, body or {})


@app.get("/vital/bots/{bot_id}/kalshi-health")
def vital_bots_kalshi_health(bot_id: str) -> dict:
    from roller.vital.api import handle_kalshi_health

    return _vital_http(handle_kalshi_health, bot_id)


@app.get("/vital/bots/{bot_id}/orders")
def vital_bots_orders(bot_id: str) -> dict:
    from roller.vital.api import handle_orders

    return _vital_http(handle_orders, bot_id)


@app.get("/vital/bots/{bot_id}/positions")
def vital_bots_positions(bot_id: str) -> dict:
    from roller.vital.api import handle_positions

    return _vital_http(handle_positions, bot_id)


@app.get("/vital/bots/{bot_id}/execution")
def vital_bots_execution(bot_id: str) -> dict:
    from roller.vital.api import handle_execution

    return _vital_http(handle_execution, bot_id)


@app.get("/vital/bots/{bot_id}/execution/trades")
def vital_bots_execution_trades(bot_id: str) -> dict:
    from roller.vital.api import handle_execution_trades

    return _vital_http(handle_execution_trades, bot_id)


@app.get("/vital/bots/{bot_id}/execution/fills")
def vital_bots_execution_fills(bot_id: str) -> dict:
    from roller.vital.api import handle_execution_fills

    return _vital_http(handle_execution_fills, bot_id)


@app.get("/vital/bots/{bot_id}/execution/trades/{trade_id}")
def vital_bots_execution_trade(bot_id: str, trade_id: str) -> dict:
    from roller.vital.api import handle_execution_trade

    return _vital_http(handle_execution_trade, bot_id, trade_id)


@app.get("/vital/bots/{bot_id}/events")
def vital_bots_events(bot_id: str) -> dict:
    from roller.vital.api import handle_events

    return _vital_http(handle_events, bot_id)


@app.get("/vital/bots/{bot_id}/plane")
def vital_bots_plane(bot_id: str) -> dict:
    from roller.vital.api import handle_plane

    return _vital_http(handle_plane, bot_id)


@app.get("/vital/bots/{bot_id}/configuration")
def vital_bots_configuration(bot_id: str) -> dict:
    from roller.vital.api import handle_configuration

    return _vital_http(handle_configuration, bot_id)


@app.get("/vital/bots/{bot_id}/strategy")
def vital_bots_strategy(bot_id: str) -> dict:
    from roller.vital.api import handle_strategy

    return _vital_http(handle_strategy, bot_id)


@app.get("/vital/bots/{bot_id}/risk")
def vital_bots_risk(bot_id: str) -> dict:
    from roller.vital.api import handle_risk

    return _vital_http(handle_risk, bot_id)


@app.get("/vital/bots/{bot_id}/heartbeat")
def vital_bots_heartbeat(bot_id: str) -> dict:
    from roller.vital.api import handle_heartbeat

    return _vital_http(handle_heartbeat, bot_id)


@app.get("/vital/bots/{bot_id}/controls")
def vital_bots_controls(bot_id: str) -> dict:
    from roller.vital.api import handle_controls

    return _vital_http(handle_controls, bot_id)


@app.get("/vital/bots/{bot_id}/boundary")
def vital_bots_boundary(bot_id: str) -> dict:
    from roller.vital.api import handle_boundary

    return _vital_http(handle_boundary, bot_id)


@app.get("/vital/bots/{bot_id}/worker")
def vital_bots_worker(bot_id: str) -> dict:
    from roller.vital.api import handle_worker

    return _vital_http(handle_worker, bot_id)


@app.get("/vital/bots/{bot_id}/pipeline")
def vital_bots_pipeline(bot_id: str) -> dict:
    from roller.vital.api import handle_pipeline

    return _vital_http(handle_pipeline, bot_id)


@app.get("/vital/bots/{bot_id}/kalshi")
def vital_bots_kalshi(bot_id: str) -> dict:
    from roller.vital.api import handle_kalshi

    return _vital_http(handle_kalshi, bot_id)


@app.post("/vital/bots/{bot_id}/kalshi/observe")
def vital_bots_kalshi_observe(bot_id: str, body: dict[str, Any] | None = None) -> dict:
    from roller.vital.api import handle_kalshi_observe

    return _vital_http(handle_kalshi_observe, bot_id, body or {})


@app.post("/vital/bots/{bot_id}/commands")
def vital_bots_commands(bot_id: str, body: dict[str, Any] | None = None) -> dict:
    from roller.vital.api import handle_command

    return _vital_http(handle_command, bot_id, body or {})


@app.post("/vital/bots/{bot_id}/allocation")
def vital_bots_allocation(bot_id: str, body: dict[str, Any] | None = None) -> dict:
    from roller.vital.api import handle_allocation_post

    return _vital_http(handle_allocation_post, bot_id, body or {})


@app.post("/vital/bots/{bot_id}/limits")
def vital_bots_limits(bot_id: str, body: dict[str, Any] | None = None) -> dict:
    from roller.vital.api import handle_limits_post

    return _vital_http(handle_limits_post, bot_id, body or {})


@app.post("/vital/bots/{bot_id}/activate")
def vital_bots_activate(bot_id: str, body: dict[str, Any] | None = None) -> dict:
    from roller.vital.api import handle_activate_post

    return _vital_http(handle_activate_post, bot_id, body or {})


@app.post("/vital/bots/{bot_id}/production")
def vital_bots_production(bot_id: str, body: dict[str, Any] | None = None) -> dict:
    from roller.vital.api import handle_promote_post

    return _vital_http(handle_promote_post, bot_id, body or {})


@app.get("/vital/bots/{bot_id}/diagnose")
def vital_bots_diagnose(bot_id: str) -> dict:
    from roller.vital.api import handle_diagnose

    return _vital_http(handle_diagnose, bot_id)


@app.post("/vital/bots/{bot_id}/start-if-armed")
def vital_bots_start_if_armed(bot_id: str, body: dict[str, Any] | None = None) -> dict:
    from roller.vital.api import handle_start_if_armed

    return _vital_http(handle_start_if_armed, bot_id, body or {})


def _systimo_http(fn, *args, **kwargs):
    from roller.systimo.errors import SystimoError

    try:
        return fn(*args, **kwargs)
    except SystimoError as exc:
        raise HTTPException(
            status_code=exc.status_code,
            detail={"code": exc.code, "message": exc.message},
        ) from exc


@app.get("/systimo/health")
def systimo_health() -> dict:
    from roller.systimo.api import handle_health

    return handle_health()


@app.get("/systimo/systems")
def systimo_systems() -> dict:
    from roller.systimo.api import handle_systems

    return handle_systems()


@app.get("/systimo/systems/{system_id}")
def systimo_system(system_id: str) -> dict:
    from roller.systimo.api import handle_systems

    return _systimo_http(handle_systems, system_id)


@app.get("/systimo/connections")
def systimo_connections() -> dict:
    from roller.systimo.api import handle_connections

    return handle_connections()


@app.get("/systimo/connections/{connection_id}")
def systimo_connection(connection_id: str) -> dict:
    from roller.systimo.api import handle_connections

    return _systimo_http(handle_connections, connection_id)


@app.get("/systimo/tree")
def systimo_tree() -> dict:
    from roller.systimo.api import handle_tree

    return handle_tree()


@app.get("/systimo/graph")
def systimo_graph() -> dict:
    from roller.systimo.api import handle_graph

    return handle_graph()


@app.get("/systimo/datasets")
def systimo_datasets() -> dict:
    from roller.systimo.api import handle_datasets

    return handle_datasets()


@app.get("/systimo/artifacts")
def systimo_artifacts() -> dict:
    from roller.systimo.api import handle_artifacts

    return handle_artifacts()


@app.post("/systimo/refresh")
def systimo_refresh(body: dict | None = None) -> dict:
    from roller.systimo.api import handle_refresh

    return _systimo_http(handle_refresh, body or {})


@app.post("/systimo/query")
def systimo_query(body: dict | None = None) -> dict:
    from roller.systimo.api import handle_query

    return _systimo_http(handle_query, body or {})


@app.get("/systimo/query/{query_id}")
def systimo_query_get(query_id: str) -> dict:
    from roller.systimo.api import handle_query_get

    return _systimo_http(handle_query_get, query_id)


@app.post("/systimo/query/{query_id}/artifact")
def systimo_query_artifact(query_id: str, body: dict | None = None) -> dict:
    from roller.systimo.api import handle_query_artifact

    return _systimo_http(handle_query_artifact, query_id, body or {})


@app.get("/systimo/actions")
def systimo_actions() -> dict:
    from roller.systimo.api import handle_actions

    return handle_actions()


@app.post("/systimo/actions/propose")
def systimo_actions_propose(body: dict | None = None) -> dict:
    from roller.systimo.api import handle_action_propose

    return _systimo_http(handle_action_propose, body or {})


@app.post("/systimo/actions/{action_id}/dry-run")
def systimo_action_dry_run(action_id: str) -> dict:
    from roller.systimo.api import handle_action_dry_run

    return _systimo_http(handle_action_dry_run, action_id)


@app.post("/systimo/actions/{action_id}/apply")
def systimo_action_apply(action_id: str) -> dict:
    from roller.systimo.api import handle_action_apply

    return _systimo_http(handle_action_apply, action_id)


@app.get("/systimo/agents")
def systimo_agents() -> dict:
    from roller.systimo.api import handle_agents

    return handle_agents()


@app.post("/systimo/agents/{agent_id}/run")
def systimo_agent_run(agent_id: str) -> dict:
    from roller.systimo.api import handle_agent_run

    return _systimo_http(handle_agent_run, agent_id)


@app.get("/systimo/traces")
def systimo_traces() -> dict:
    from roller.systimo.api import handle_traces

    return handle_traces()


@app.get("/systimo/traces/{trace_id}")
def systimo_trace(trace_id: str) -> dict:
    from roller.systimo.api import handle_traces

    return _systimo_http(handle_traces, trace_id)


@app.get("/systimo/orchestra/context/{trade_id}")
def systimo_orchestra_context(trade_id: str, as_of: str | None = None) -> dict:
    from roller.systimo.api import handle_orchestra_context

    return _systimo_http(handle_orchestra_context, trade_id, as_of)


@app.get("/systimo/topology")
def systimo_topology() -> dict:
    from roller.systimo.api import handle_topology

    return handle_topology()


@app.post("/systimo/scope/sessions")
def systimo_scope_session(body: dict | None = None) -> dict:
    from roller.systimo.api import handle_scope_session

    return _systimo_http(handle_scope_session, body or {})


@app.get("/systimo/runtime/endpoints")
def systimo_runtime_endpoints(session_id: str) -> dict:
    from roller.systimo.api import handle_runtime_endpoints

    return _systimo_http(handle_runtime_endpoints, session_id)


@app.get("/systimo/plan")
def systimo_plan(scope: str) -> dict:
    from roller.systimo.api import handle_plan

    return _systimo_http(handle_plan, scope)


@app.post("/systimo/run")
def systimo_run() -> dict:
    from roller.systimo.api import handle_run

    return _systimo_http(handle_run)


@app.get("/systimo/bots")
def systimo_bots(session_id: str) -> dict:
    from roller.systimo.api import handle_bots

    return _systimo_http(handle_bots, session_id)


@app.get("/systimo/nba-001/v1")
def systimo_nba001_v1() -> dict:
    from roller.systimo.api import handle_nba001_v1

    return handle_nba001_v1()


@app.get("/stryke/health")
def stryke_health() -> dict:
    from roller.stryke.api import handle_health

    return handle_health()


@app.get("/stryke/folders")
def stryke_folders() -> dict:
    from roller.stryke.api import handle_folders

    return handle_folders()


@app.get("/stryke/signal/{folder_id}")
def stryke_signal(folder_id: str) -> dict:
    from roller.stryke.api import handle_signal

    return handle_signal(folder_id)


def _enable_result_cache() -> None:
    os.environ.setdefault("ROLLER_QUERY_RESULT_CACHE", "1")
    os.environ.setdefault(
        "ROLLER_QUERY_RESULT_CACHE_DIR",
        str(_ROOT / "data" / ".cache" / "research_query"),
    )


def main() -> None:
    import uvicorn

    _enable_result_cache()
    os.environ.setdefault("VITAL_AWS_HOST_FETCH", "ssm")
    uvicorn.run(app, host="127.0.0.1", port=int(os.environ.get("MOMENTO_BIND_PORT", "8791")), reload=False)


if __name__ == "__main__":
    main()
