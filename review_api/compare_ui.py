"""Build side-by-side field rows + fuzzy scores for the review GUI."""
from __future__ import annotations

import json
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any, Optional

# Project root (parent of review_api/)
ROOT = Path(__file__).resolve().parent.parent
STRUCTURED_DIR = ROOT / "output" / "structured"
GROUND_TRUTH_DIR = ROOT / "output" / "ground_truth"
STAGES_DIR = ROOT / "output" / "stages"


def _get(d: Optional[dict], *keys: str) -> Any:
    cur: Any = d
    for k in keys:
        if not isinstance(cur, dict):
            return None
        cur = cur.get(k)
    return cur


def _format_val(v: Any) -> str:
    if v is None:
        return "—"
    if isinstance(v, bool):
        return "Yes" if v else "No"
    if isinstance(v, list):
        if not v:
            return "—"
        if all(isinstance(x, str) for x in v):
            return ", ".join(v)
        return json.dumps(v, ensure_ascii=False)
    return str(v)


def _similarity_score(orig: Any, scr: Any) -> tuple[int, str]:
    """
    Return (0-100 score, css class: match | partial | mismatch).
    If both empty, treat as match. If one empty, low score.
    """
    o = _format_val(orig)
    s = _format_val(scr)
    if o == "—" and s == "—":
        return 100, "match"
    if o == "—" or s == "—":
        return 35, "mismatch"
    lo, ls = o.strip().lower(), s.strip().lower()
    if lo == ls:
        return 100, "match"
    ratio = SequenceMatcher(None, lo, ls).ratio()
    score = int(round(ratio * 100))
    if score >= 80:
        cls = "match"
    elif score >= 50:
        cls = "partial"
    else:
        cls = "mismatch"
    return score, cls


def _traffic_from_nlp(nlp: int) -> str:
    if nlp >= 80:
        return "green"
    if nlp >= 50:
        return "yellow"
    return "red"


def _avg_scores(rows: list[dict]) -> int:
    if not rows:
        return 0
    sc = [r["score"] for r in rows if r.get("score") is not None]
    return int(round(sum(sc) / len(sc))) if sc else 0


def build_field_rows(
    label_orig_scr: list[tuple[str, Any, Any]],
) -> list[dict]:
    out = []
    for label, orig, scr in label_orig_scr:
        score, cls = _similarity_score(orig, scr)
        out.append(
            {
                "label": label,
                "orig": _format_val(orig),
                "scr": _format_val(scr),
                "score": score,
                "cls": cls,
            }
        )
    return out


def institution_rows(gt: Optional[dict], ex: dict) -> list[dict]:
    specs = [
        ("Name (English)", _get(gt, "org_basics", "name_english"), _get(ex, "org_basics", "name_english")),
        ("Name (native)", _get(gt, "org_basics", "name_native"), _get(ex, "org_basics", "name_native")),
        ("City", _get(gt, "contact", "city"), _get(ex, "contact", "city")),
        ("Funding type", _get(gt, "org_basics", "funding_type"), _get(ex, "org_basics", "funding_type")),
        ("Institution type (intl.)", _get(gt, "org_basics", "institution_type_international"), _get(ex, "org_basics", "institution_type_international")),
        ("Institution type (national)", _get(gt, "org_basics", "institution_type_national"), _get(ex, "org_basics", "institution_type_national")),
        ("Year founded", _get(gt, "org_basics", "year_founded"), _get(ex, "org_basics", "year_founded")),
        ("Branch campus?", _get(gt, "org_basics", "is_branch"), _get(ex, "org_basics", "is_branch")),
        ("Street", _get(gt, "contact", "street"), _get(ex, "contact", "street")),
        ("Website", _get(gt, "contact", "website"), _get(ex, "contact", "website")),
    ]
    return build_field_rows(specs)


def division_row_pair(gt: Optional[dict], ex: dict, index: int) -> list[dict]:
    gt_list = (gt or {}).get("divisions") or []
    ex_list = ex.get("divisions") or []
    g = gt_list[index] if index < len(gt_list) else None
    e = ex_list[index] if index < len(ex_list) else None
    g = g if isinstance(g, dict) else {}
    e = e if isinstance(e, dict) else {}
    specs = [
        ("Division name", g.get("name"), e.get("name")),
        ("Division type", g.get("division_type"), e.get("division_type")),
        ("Fields of study", g.get("fields_of_study"), e.get("fields_of_study")),
    ]
    return build_field_rows(specs)


def contact_row_pair(gt: Optional[dict], ex: dict, index: int) -> list[dict]:
    gt_list = (gt or {}).get("key_contacts") or []
    ex_list = ex.get("key_contacts") or []
    g = gt_list[index] if index < len(gt_list) else None
    e = ex_list[index] if index < len(ex_list) else None
    g = g if isinstance(g, dict) else {}
    e = e if isinstance(e, dict) else {}
    g_name = " ".join(filter(None, [g.get("first_name"), g.get("surname")])).strip() or None
    e_name = " ".join(filter(None, [e.get("first_name"), e.get("surname")])).strip() or None
    specs = [
        ("Full name", g_name, e_name),
        ("Job title", g.get("job_title"), e.get("job_title")),
        ("Job function", g.get("job_function"), e.get("job_function")),
    ]
    return build_field_rows(specs)


def load_json(path: Path) -> Optional[dict]:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def list_domains() -> list[str]:
    if not STRUCTURED_DIR.is_dir():
        return []
    domains = sorted(p.stem for p in STRUCTURED_DIR.glob("*.json"))
    return domains


def load_extracted(domain: str) -> Optional[dict]:
    return load_json(STRUCTURED_DIR / f"{domain}.json")


def load_ground_truth_file(domain: str) -> Optional[dict]:
    return load_json(GROUND_TRUTH_DIR / f"{domain}.json")


def build_tab_bundle(label: str, fields: list[dict], edit_text: str, source_url: str, scraped_at: str) -> dict:
    nlp = _avg_scores(fields)
    return {
        "total": 1,
        "cursor": 1,
        "stats": {"ok": 0, "mod": 0, "man": 0},
        "tl": _traffic_from_nlp(nlp),
        "nlp": nlp,
        "sourceUrl": source_url or "—",
        "scrapedAt": scraped_at or "—",
        "decision": None,
        "fields": fields,
        "editText": edit_text,
        "_label": label,
    }


def build_ui_payload(gt: Optional[dict], ex: Optional[dict]) -> dict:
    if not ex:
        return {}

    source_url = ex.get("source_url") or "—"
    scraped_at = (ex.get("extracted_at") or "")[:10] or "—"

    inst_fields = institution_rows(gt, ex)
    inst_edit = ex.get("extraction_notes") or ""

    gt_divs = (gt or {}).get("divisions") or []
    ex_divs = ex.get("divisions") or []
    div_n = max(len(gt_divs), len(ex_divs), 0)
    division_items = []
    ex_list_div = ex.get("divisions") or []
    for i in range(div_n):
        fields = division_row_pair(gt, ex, i)
        edit = ""
        if i < len(ex_list_div) and isinstance(ex_list_div[i], dict):
            d = ex_list_div[i]
            edit = f"{_format_val(d.get('name'))} — {_format_val(d.get('division_type'))}"
        division_items.append({"fields": fields, "editText": edit})

    gt_ct = (gt or {}).get("key_contacts") or []
    ex_ct = ex.get("key_contacts") or []
    ct_n = max(len(gt_ct), len(ex_ct))
    contact_items = []
    ex_list_ct = ex.get("key_contacts") or []
    for i in range(ct_n):
        fields = contact_row_pair(gt, ex, i)
        edit = ""
        if i < len(ex_list_ct) and isinstance(ex_list_ct[i], dict):
            c = ex_list_ct[i]
            edit = " ".join(filter(None, [c.get("first_name"), c.get("surname")])).strip()
        contact_items.append({"fields": fields, "editText": edit})

    ui_inst = build_tab_bundle("institutions", inst_fields, str(inst_edit or ""), source_url, scraped_at)
    ui_inst["total"] = 1
    ui_inst["cursor"] = 1

    # Divisions: multi-record tab
    if not division_items:
        division_items = [
            {
                "fields": [
                    {
                        "label": "Divisions",
                        "orig": "—",
                        "scr": "—",
                        "score": 100,
                        "cls": "match",
                    }
                ],
                "editText": "",
            }
        ]
        div_n = 1
    if division_items:
        divnlp = int(round(sum(_avg_scores(it["fields"]) for it in division_items) / len(division_items)))
    else:
        divnlp = 100
    ui_div = {
        "total": div_n,
        "cursor": 1,
        "stats": {"ok": 0, "mod": 0, "man": 0},
        "tl": _traffic_from_nlp(divnlp),
        "nlp": divnlp,
        "sourceUrl": source_url,
        "scrapedAt": scraped_at,
        "decision": None,
        "items": division_items,
        "fields": division_items[0]["fields"],
        "editText": division_items[0]["editText"],
    }

    if not contact_items:
        contact_items = [
            {
                "fields": [
                    {
                        "label": "Contacts",
                        "orig": "—",
                        "scr": "—",
                        "score": 100,
                        "cls": "match",
                    }
                ],
                "editText": "",
            }
        ]
        ct_n = 1
    if contact_items:
        ctnlp = int(round(sum(_avg_scores(it["fields"]) for it in contact_items) / len(contact_items)))
    else:
        ctnlp = 100
    ui_ct = {
        "total": ct_n,
        "cursor": 1,
        "stats": {"ok": 0, "mod": 0, "man": 0},
        "tl": _traffic_from_nlp(ctnlp),
        "nlp": ctnlp,
        "sourceUrl": source_url,
        "scrapedAt": scraped_at,
        "decision": None,
        "items": contact_items,
        "fields": contact_items[0]["fields"],
        "editText": contact_items[0]["editText"],
    }

    return {
        "institutions": ui_inst,
        "divisions": ui_div,
        "contacts": ui_ct,
    }
