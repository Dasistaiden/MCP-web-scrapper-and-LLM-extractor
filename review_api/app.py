"""
FastAPI server for the data comparison review UI.

Run from project root:
    uv run uvicorn review_api.app:app --reload --host 127.0.0.1 --port 8765

Open: http://127.0.0.1:8765/
API docs: http://127.0.0.1:8765/docs
"""
from __future__ import annotations

import json
import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

from review_api.compare_ui import (
    ROOT,
    STAGES_DIR,
    build_ui_payload,
    list_domains,
    load_extracted,
    load_ground_truth_file,
)

@asynccontextmanager
async def lifespan(application: FastAPI):
    try:
        from db_reference import ensure_staging_tables, is_db_available

        if is_db_available():
            ensure_staging_tables()
            logger.info("DB available — staging tables ready")
        else:
            logger.info("DB offline — staging will only write JSON files")
    except Exception as exc:
        logger.warning("Staging table init skipped: %s", exc)
    yield


app = FastAPI(title="WHED Data Review", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _db_available() -> bool:
    try:
        from db_reference import is_db_available

        return bool(is_db_available())
    except Exception:
        return False


def _resolve_ground_truth(domain: str) -> Optional[dict]:
    cached = load_ground_truth_file(domain)
    if cached:
        return cached
    try:
        from db_reference import export_ground_truth

        return export_ground_truth(domain)
    except Exception:
        return None


@app.get("/api/health")
def health() -> dict[str, Any]:
    return {
        "ok": True,
        "db_available": _db_available(),
        "structured_dir": str(ROOT / "output" / "structured"),
    }


@app.get("/api/domains")
def api_domains() -> dict[str, list[str]]:
    return {"domains": list_domains()}


@app.get("/api/review/{domain}")
def api_review(domain: str) -> dict[str, Any]:
    extracted = load_extracted(domain)
    if not extracted:
        raise HTTPException(
            status_code=404,
            detail=f"No extracted profile at output/structured/{domain}.json",
        )
    ground_truth = _resolve_ground_truth(domain)
    ui = build_ui_payload(ground_truth, extracted)
    domains = list_domains()
    try:
        idx = domains.index(domain)
    except ValueError:
        idx = 0

    return {
        "domain": domain,
        "domain_index": idx,
        "domain_count": len(domains),
        "db_available": _db_available(),
        "has_ground_truth": ground_truth is not None,
        "ground_truth": ground_truth,
        "extracted": extracted,
        "ui": ui,
    }


class StagePayload(BaseModel):
    """Body for POST /api/stage/{domain} — full SchoolProfile-shaped object."""

    profile: dict[str, Any] = Field(default_factory=dict)
    review_action: Optional[str] = Field(None, description="accept | modify | reject")
    notes: Optional[str] = None


@app.post("/api/stage/{domain}")
def save_stage(domain: str, body: StagePayload) -> dict[str, Any]:
    STAGES_DIR.mkdir(parents=True, exist_ok=True)
    out: dict[str, Any] = {
        "domain": domain,
        "review_action": body.review_action,
        "notes": body.notes,
        "profile": body.profile,
    }
    path = STAGES_DIR / f"{domain}.json"
    path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")

    db_ok = False
    if body.review_action in ("accept", "modify", "reject"):
        try:
            from db_reference import upsert_staging

            db_ok = upsert_staging(domain, body.review_action, body.profile, body.notes)
        except Exception:
            pass

    return {"success": True, "saved_to": str(path), "db_staged": db_ok}


@app.get("/")
def serve_index() -> FileResponse:
    html = ROOT / "data_comparison_gui_mockup.html"
    if not html.exists():
        raise HTTPException(status_code=404, detail="data_comparison_gui_mockup.html not found")
    return FileResponse(html, media_type="text/html; charset=utf-8")

