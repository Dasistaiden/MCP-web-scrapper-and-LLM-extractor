"""
Run Comparison
==============
Three-way comparison of extraction results:

  1. BASELINE  — Old extraction (Ollama LLM, full schema)
  2. MCP       — New extraction (MCP-native, host LLM, REQUIRED only)
  3. GROUND TRUTH — Actual record from the WHED database

Usage:
    uv run python run_comparison.py                  # all domains
    uv run python run_comparison.py www.ampa.edu.au   # single domain
"""

import json
import sys
from pathlib import Path
from datetime import datetime

from db_reference import export_ground_truth

# ─────────────────────────────────────────────────────────────────────────────
# CONFIGURATION
# ─────────────────────────────────────────────────────────────────────────────

BASELINE_DIR = "output/structured_baseline"
GROUNDED_DIR = "output/structured"
GROUND_TRUTH_DIR = "output/ground_truth"
COMPARISON_DIR = "output/comparisons"

# REQUIRED scalar fields — org_basics + contact
REQUIRED_FIELDS = {
    "org_basics": [
        "name_native", "name_english", "is_branch", "year_founded",
        "institution_type_international", "institution_type_national",
        "funding_type",
    ],
    "contact": ["city"],
}

# REQUIRED fields inside list items — key_contacts, divisions: positional; degree_programs: by level
REQUIRED_LIST_FIELDS = {
    "key_contacts": ["first_name", "surname", "job_title", "job_function"],
    "divisions": ["name", "division_type", "fields_of_study"],
}
DEGREE_PROGRAM_FIELDS = ["name", "level"]

# DEFERRED fields — shown separately for reference, not counted in accuracy
DEFERRED_FIELDS = {
    "org_basics": ["acronym"],
    "contact": ["street", "province", "post_code", "website", "email", "phone"],
    "academic": [
        "languages_of_instruction", "accrediting_body", "history",
        "student_body", "learning_modalities",
    ],
    "tuition": ["national_students", "international_students"],
}


def _load_json(path: Path) -> dict | None:
    if not path.exists():
        return None
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _get_val(data: dict, section: str, field: str):
    sec = data.get(section)
    if sec is None:
        return None
    return sec.get(field)


def _normalize(val):
    if val is None:
        return None
    if isinstance(val, str):
        return val.strip().lower()
    if isinstance(val, list):
        return sorted(str(v).strip().lower() for v in val)
    return val


def _match_status(baseline_val, grounded_val, truth_val):
    nb = _normalize(baseline_val)
    ng = _normalize(grounded_val)
    nt = _normalize(truth_val)

    if nt is None:
        return "no_truth"
    if ng == nt and nb == nt:
        return "both_correct"
    if ng == nt and nb != nt:
        return "mcp_fixed"
    if nb == nt and ng != nt:
        return "baseline_better"
    if nb != nt and ng != nt:
        return "both_wrong"
    return "unknown"


def _get_list_val(data: dict, list_key: str, index: int, field: str):
    """Get value from list item: data[list_key][index][field]"""
    items = (data or {}).get(list_key) or []
    if index >= len(items):
        return None
    item = items[index]
    if not isinstance(item, dict):
        return None
    return item.get(field)


def _compare_fields(field_map, baseline, grounded, ground_truth, is_required):
    """Compare scalar fields and return results."""
    results = []
    for section, fields in field_map.items():
        for field in fields:
            b_val = _get_val(baseline or {}, section, field)
            g_val = _get_val(grounded or {}, section, field)
            t_val = _get_val(ground_truth or {}, section, field)

            status = _match_status(b_val, g_val, t_val)
            results.append({
                "section": section,
                "field": field,
                "index": None,
                "baseline": b_val,
                "mcp": g_val,
                "ground_truth": t_val,
                "status": status,
                "required": is_required,
            })
    return results


def _compare_list_fields(list_field_map, baseline, grounded, ground_truth, is_required):
    """Compare REQUIRED fields inside list items. Uses positional alignment (index 0 vs 0).
    Uses ground_truth length as reference — each GT item is compared.
    Exception: degree_programs use level-based matching (see _compare_degree_programs)."""
    results = []
    for list_key, fields in list_field_map.items():
        if list_key == "degree_programs":
            continue  # Handled separately by _compare_degree_programs
        b_list = (baseline or {}).get(list_key) or []
        g_list = (grounded or {}).get(list_key) or []
        t_list = (ground_truth or {}).get(list_key) or []

        n = len(t_list)
        if n == 0:
            continue

        for i in range(n):
            for field in fields:
                b_val = _get_list_val(baseline or {}, list_key, i, field)
                g_val = _get_list_val(grounded or {}, list_key, i, field)
                t_val = _get_list_val(ground_truth or {}, list_key, i, field)

                status = _match_status(b_val, g_val, t_val)
                results.append({
                    "section": list_key,
                    "field": field,
                    "index": i,
                    "baseline": b_val,
                    "mcp": g_val,
                    "ground_truth": t_val,
                    "status": status,
                    "required": is_required,
                })
    return results


def _compare_degree_programs(baseline, grounded, ground_truth, is_required):
    """Compare degree_programs by LEVEL (not position).
    For each GT program, find first matching item in B and G with same level, then compare."""
    fields = DEGREE_PROGRAM_FIELDS
    b_list = (baseline or {}).get("degree_programs") or []
    g_list = (grounded or {}).get("degree_programs") or []
    t_list = (ground_truth or {}).get("degree_programs") or []

    results = []
    used_b = set()
    used_g = set()

    for gt_idx, t_item in enumerate(t_list):
        if not isinstance(t_item, dict):
            continue
        t_level = _normalize(t_item.get("level"))

        # Find first unmapped item with same level in baseline
        b_val_map = {}
        for i, b_item in enumerate(b_list):
            if i in used_b:
                continue
            if isinstance(b_item, dict) and _normalize(b_item.get("level")) == t_level:
                used_b.add(i)
                for f in fields:
                    b_val_map[f] = b_item.get(f)
                break

        # Find first unmapped item with same level in MCP
        g_val_map = {}
        for i, g_item in enumerate(g_list):
            if i in used_g:
                continue
            if isinstance(g_item, dict) and _normalize(g_item.get("level")) == t_level:
                used_g.add(i)
                for f in fields:
                    g_val_map[f] = g_item.get(f)
                break

        for field in fields:
            t_val = t_item.get(field)
            b_val = b_val_map.get(field) if b_val_map else None
            g_val = g_val_map.get(field) if g_val_map else None

            status = _match_status(b_val, g_val, t_val)
            results.append({
                "section": "degree_programs",
                "field": field,
                "index": gt_idx,
                "match_key": t_level or f"gt[{gt_idx}]",
                "baseline": b_val,
                "mcp": g_val,
                "ground_truth": t_val,
                "status": status,
                "required": is_required,
            })

    return results


def compare_one(domain: str) -> dict:
    baseline = _load_json(Path(BASELINE_DIR) / f"{domain}.json")
    grounded = _load_json(Path(GROUNDED_DIR) / f"{domain}.json")

    gt_dir = Path(GROUND_TRUTH_DIR)
    gt_dir.mkdir(parents=True, exist_ok=True)
    gt_path = gt_dir / f"{domain}.json"

    if gt_path.exists():
        ground_truth = _load_json(gt_path)
    else:
        ground_truth = export_ground_truth(domain)
        if ground_truth:
            with open(gt_path, "w", encoding="utf-8") as f:
                json.dump(ground_truth, f, ensure_ascii=False, indent=2, default=str)
            print(f"  Ground truth exported: {gt_path}")
        else:
            print(f"  WARNING: {domain} not found in WHED DB")

    sources = {
        "baseline": baseline,
        "mcp": grounded,
        "ground_truth": ground_truth,
    }
    missing = [k for k, v in sources.items() if v is None]
    if missing:
        print(f"  Missing sources: {', '.join(missing)}")

    required_scalar = _compare_fields(
        REQUIRED_FIELDS, baseline, grounded, ground_truth, is_required=True
    )
    required_list = _compare_list_fields(
        REQUIRED_LIST_FIELDS, baseline, grounded, ground_truth, is_required=True
    )
    degree_list = _compare_degree_programs(
        baseline, grounded, ground_truth, is_required=True
    )
    required_results = required_scalar + required_list + degree_list
    deferred_results = _compare_fields(
        DEFERRED_FIELDS, baseline, grounded, ground_truth, is_required=False
    )

    list_stats = {}
    for list_field in ["key_contacts", "divisions", "degree_programs"]:
        b_count = len((baseline or {}).get(list_field, []))
        g_count = len((grounded or {}).get(list_field, []))
        t_count = len((ground_truth or {}).get(list_field, []))
        list_stats[list_field] = {
            "baseline_count": b_count,
            "mcp_count": g_count,
            "ground_truth_count": t_count,
        }

    db_warnings = (grounded or {}).get("db_validation_warnings", [])

    return {
        "domain": domain,
        "compared_at": datetime.now().isoformat(timespec="seconds"),
        "sources_available": {k: v is not None for k, v in sources.items()},
        "required_fields": required_results,
        "deferred_fields": deferred_results,
        "list_counts": list_stats,
        "db_validation_warnings": db_warnings,
    }


def _count_statuses(field_list):
    counts = {}
    for f in field_list:
        s = f["status"]
        counts[s] = counts.get(s, 0) + 1
    return counts


def print_report(result: dict):
    domain = result["domain"]
    print(f"\n{'=' * 70}")
    print(f"  COMPARISON REPORT: {domain}")
    print(f"{'=' * 70}")

    # --- REQUIRED fields ---
    req = result["required_fields"]
    req_counts = _count_statuses(req)

    print(f"\n  REQUIRED FIELDS ({len(req)} fields):")
    labels = {
        "both_correct": "Both correct",
        "mcp_fixed": "MCP FIXED (improvement!)",
        "baseline_better": "Baseline was better",
        "both_wrong": "Both wrong",
        "no_truth": "No ground truth",
    }
    for status, label in labels.items():
        c = req_counts.get(status, 0)
        if c > 0 or status in ("both_correct", "both_wrong"):
            marker = " ***" if status == "mcp_fixed" and c > 0 else ""
            print(f"    {label:45s} : {c}{marker}")

    total = sum(req_counts.get(s, 0) for s in ["both_correct", "mcp_fixed", "baseline_better", "both_wrong"])
    if total > 0:
        b_ok = req_counts.get("both_correct", 0) + req_counts.get("baseline_better", 0)
        m_ok = req_counts.get("both_correct", 0) + req_counts.get("mcp_fixed", 0)
        print(f"\n    Baseline accuracy (REQUIRED) : {b_ok}/{total} ({100*b_ok/total:.0f}%)")
        print(f"    MCP accuracy     (REQUIRED) : {m_ok}/{total} ({100*m_ok/total:.0f}%)")

    # Required field details
    print(f"\n  {'-' * 66}")
    print(f"  REQUIRED FIELD DETAILS:")
    print(f"  {'-' * 66}")
    _print_fields(req)

    # --- DEFERRED fields ---
    deferred = result["deferred_fields"]
    deferred_with_truth = [f for f in deferred if f["status"] != "no_truth"]
    if deferred_with_truth:
        def_counts = _count_statuses(deferred_with_truth)
        print(f"\n  {'-' * 66}")
        print(f"  DEFERRED FIELDS (not in current scope, for reference only):")
        print(f"  {'-' * 66}")
        _print_fields(deferred_with_truth)

        baseline_has = sum(1 for f in deferred_with_truth if f["baseline"] is not None)
        mcp_has = sum(1 for f in deferred_with_truth if f["mcp"] is not None)
        print(f"\n    Baseline filled {baseline_has}/{len(deferred_with_truth)} deferred fields")
        print(f"    MCP      filled {mcp_has}/{len(deferred_with_truth)} deferred fields (expected: 0)")

    # --- List counts ---
    print(f"\n  {'-' * 66}")
    print(f"  LIST COUNTS:")
    print(f"  {'-' * 66}")
    print(f"  {'Field':<20s} {'Ground Truth':>14s} {'Baseline':>10s} {'MCP':>10s}")
    for field, stats in result["list_counts"].items():
        print(f"  {field:<20s} {stats['ground_truth_count']:>14d} {stats['baseline_count']:>10d} {stats['mcp_count']:>10d}")

    # --- DB warnings ---
    warnings = result.get("db_validation_warnings", [])
    if warnings:
        print(f"\n  {'-' * 66}")
        print(f"  DB VALIDATION WARNINGS ({len(warnings)}):")
        for w in warnings:
            print(f"    - {w}")

    print(f"\n{'=' * 70}\n")


def _print_fields(fields):
    for f in fields:
        if f["status"] == "no_truth":
            continue
        icon = {
            "both_correct": "==",
            "mcp_fixed": ">>",
            "baseline_better": "<<",
            "both_wrong": "XX",
        }.get(f["status"], "??")

        idx = f.get("index")
        field_name = f"{f['section']}[{idx}].{f['field']}" if idx is not None else f"{f['section']}.{f['field']}"
        print(f"\n  [{icon}] {field_name}")
        print(f"       Ground Truth : {_fmt(f['ground_truth'])}")
        print(f"       Baseline     : {_fmt(f['baseline'])}")
        print(f"       MCP          : {_fmt(f['mcp'])}")


def _fmt(val) -> str:
    if val is None:
        return "(null)"
    if isinstance(val, list):
        if len(val) == 0:
            return "[]"
        return f"[{', '.join(str(v) for v in val[:5])}]" + (f" +{len(val)-5} more" if len(val) > 5 else "")
    s = str(val)
    return s[:80] + "..." if len(s) > 80 else s


def main():
    domain = sys.argv[1] if len(sys.argv) > 1 else None

    if domain:
        domains = [domain]
    else:
        baseline_files = sorted(Path(BASELINE_DIR).glob("*.json"))
        grounded_files = sorted(Path(GROUNDED_DIR).glob("*.json"))
        all_stems = set(f.stem for f in baseline_files) | set(f.stem for f in grounded_files)
        domains = sorted(all_stems)

    if not domains:
        print("No files found to compare.")
        print(f"  Baseline dir: {BASELINE_DIR}/")
        print(f"  MCP dir     : {GROUNDED_DIR}/")
        sys.exit(1)

    all_results = []
    for d in domains:
        print(f"\nComparing: {d}")
        result = compare_one(d)
        print_report(result)
        all_results.append(result)

    comp_dir = Path(COMPARISON_DIR)
    comp_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = comp_dir / f"comparison_{timestamp}.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(all_results, f, ensure_ascii=False, indent=2, default=str)
    print(f"Comparison saved to: {out_path}")


if __name__ == "__main__":
    main()
