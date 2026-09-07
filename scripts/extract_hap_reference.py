"""Strict extraction of the approved Morais PDF reports; never runs legacy code.

Historical printed values (including 10% safety factors) are immutable evidence.
This parser is deliberately report-specific and fails closed on changed layouts.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

from pypdf import PdfReader

ROOT = Path(__file__).resolve().parents[1]
COMPONENTS = ["Window & Skylight Solar Loads", "Wall Transmission", "Roof Transmission",
              "Window Transmission", "Skylight Transmission", "Door Loads", "Floor Transmission",
              "Partitions", "Ceiling", "Overhead Lighting", "Task Lighting", "Electric Equipment",
              "People", "Infiltration", "Miscellaneous"]


def one(pattern, text):
    matches = list(re.finditer(pattern, text, re.M))
    if len(matches) != 1:
        raise ValueError(f"Expected exactly one match for {pattern!r}, found {len(matches)}")
    return matches[0]


def number(value):
    return None if value == "-" else float(value)


def row(text, label):
    raw = one(r"^\s*" + re.escape(label) + r"\s+(.+)$", text).group(1).strip()
    # Two details columns, with optional m2/W/L/s units, then sensible/latent.
    pattern = r"(-?\d+(?:\.\d+)?|-)(?:\s*(m2|W|L/s|%))?\s+(-?\d+|-)\s+(-?\d+|-)\s+(-?\d+(?:\.\d+)?|-)(?:\s*(m2|W|L/s|%))?\s+(-?\d+|-)\s+(-?\d+|-)"
    m = re.fullmatch(pattern, raw)
    if not m:
        raise ValueError(f"Unrecognised row {label}: {raw}")
    return {"detail": number(m[1]), "detail_unit": m[2],
            "cooling_sensible_W": number(m[3]), "cooling_latent_W": number(m[4]),
            "heating_detail": number(m[5]), "heating_detail_unit": m[6],
            "heating_sensible_W": number(m[7]), "heating_latent_W": number(m[8]),
            "source_text": raw}


def common(text):
    version = one(r"Hourly Analysis Program v\.([\d.]+)", text)[1]
    peak = one(r"COOLING DATA AT ([A-Za-z]+)\s+(\d{4})", text)
    conditions = one(r"COOLING OA DB / WB\s+([\d.]+) °C / ([\d.]+) °C HEATING OA DB / WB\s+([\d.]+) °C / ([\d.]+) °C", text)
    sf = one(r"Safety Factor\s+(\d+)% / (\d+)%\s+(\d+)\s+(\d+)\s+(\d+)%\s+(\d+)\s+(\d+)", text)
    return {"hap_version": version, "peak": {"month": peak[1], "hour_hhmm": peak[2]},
            "conditions": dict(zip(["cooling_oa_db_C", "cooling_oa_wb_C", "heating_oa_db_C", "heating_oa_wb_C"], map(float, conditions.groups()))),
            "safety_factor": dict(zip(["sensible_percent", "latent_percent", "sensible_W", "latent_W", "heating_percent", "heating_sensible_W", "heating_latent_W"], map(int, sf.groups())))}


def parse_space(text, page, source):
    header = one(r"Page\s+(\d+)\s*of\s*(\d+)\s+\d+", text)
    if (int(header[1]), int(header[2])) != (page, 55):
        raise ValueError(f"Page identity mismatch: physical {page}, printed {header.groups()}")
    title = one(r"TABLE ([\d.]+)A\.\s+COMPONENT LOADS FOR SPACE\s+'' (.+?) ''\s+IN ZONE\s+'' Zone (\d+) ''", text)
    result = common(text)
    result.update({"reference_id": f"hap-room-{page:03d}", "name": title[2], "zone": int(title[3]),
                   "table_id": title[1] + "A", "provenance": {**source, "page": page}})
    section = text.split("SPACE LOADS Details (W) (W) Details (W) (W)")
    if len(section) != 2:
        raise ValueError("Missing or repeated space table")
    components = {label: row(section[1].split("TABLE")[0], label) for label in COMPONENTS}
    total = row(text, ">> Total Zone Loads")
    # Printed integer components can each round by 0.5 W; residual is recorded.
    residuals = {}
    for key, sf_key in [("cooling_sensible_W", "sensible_W"), ("cooling_latent_W", "latent_W")]:
        residual = total[key] - sum(c[key] or 0 for c in components.values()) - result["safety_factor"][sf_key]
        if abs(residual) > (len(components) + 2) * 0.5:
            raise ValueError(f"Page {page} component sum inconsistent: {key}, {residual} W")
        residuals[key] = residual
    tstat = one(r"OCCUPIED T-STAT ([\d.]+) °C OCCUPIED T-STAT ([\d.]+) °C", text)
    result["conditions"].update(cooling_tstat_C=float(tstat[1]), heating_tstat_C=float(tstat[2]))
    result.update(components=components, floor_area_m2=components["Floor Transmission"]["detail"],
                  people=components["People"]["detail"], cooling_sensible_W=total["cooling_sensible_W"],
                  cooling_latent_W=total["cooling_latent_W"], historical_totals_include_safety_factor=True,
                  printed_component_rounding_residual_W=residuals,
                  total_row=total)
    envelope = []
    direction = None
    for line in text.split("ENVELOPE LOADS FOR SPACE", 1)[1].splitlines():
        if m := re.fullmatch(r"\s*([NSEW]{1,2})\s+EXPOSURE\s*", line):
            direction = m[1]
        elif re.match(r"\s*(WALL|WINDOW|ROOF|DOOR|SKYLIGHT)\b", line):
            m = re.fullmatch(r"\s*(WALL|WINDOW \d+|ROOF|DOOR|SKYLIGHT \d+)\s+(\d+)\s+([\d.]+)\s+([\d.]+|-)\s+(\d+|-)\s+(\d+|-)\s+(\d+|-)\s*", line)
            if not m or not direction:
                raise ValueError(f"Unrecognised envelope row on page {page}: {line}")
            envelope.append(dict(zip(["kind", "area_m2", "u_W_m2K", "shading_coefficient", "cooling_transmission_W", "cooling_solar_W", "heating_transmission_W"], [m[1]] + [number(v) for v in m.groups()[1:]]), orientation=direction, source_text=line.strip()))
    result["envelope"] = envelope
    return result


def source_info(path):
    return {"file": str(path.relative_to(ROOT)).replace("\\", "/"), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def extract(space_pdf, system_pdf):
    pages = PdfReader(space_pdf).pages
    if len(pages) != 55:
        raise ValueError(f"Expected 55 space pages; got {len(pages)}")
    source = source_info(space_pdf)
    spaces = [parse_space(p.extract_text() or "", i, source) for i, p in enumerate(pages, 1)]
    if len({(s["zone"], s["name"]) for s in spaces}) != 55:
        raise ValueError("Duplicate space identity")
    pages = PdfReader(system_pdf).pages
    if len(pages) != 1:
        raise ValueError("Expected one system page")
    text = pages[0].extract_text() or ""
    one(r"Air System Design Load Summary for Morais GF AC", text)
    system = common(text)
    system.update(name="Morais GF AC", provenance={**source_info(system_pdf), "page": 1},
                  components={label: row(text, label) for label in COMPONENTS},
                  totals={label: row(text, label) for label in [">> Total Zone Loads", ">> Total System Loads", ">> Total Conditioning"]},
                  conditioning={label: row(text, label) for label in ["Cooling Coil", "Terminal Unit Cooling", "Terminal Unit Heating", "Ventilation Load", "Exhaust Fan Load", "Ventilation Fan Load", "Zone Conditioning", "Plenum Wall Load", "Plenum Roof Load", "Plenum Lighting Load", "Space Fan Coil Fans", "Duct Heat Gain / Loss"]})
    return {"schema_version": 1, "status": "extracted_historical_evidence_not_engine_validation", "spaces": spaces, "system": system,
            "rules": ["Historical 10% remains unchanged; do not apply new 15% to these totals.", "Space peaks occur at different month/hour; their sum is not the simultaneous system peak."]}


def exact_candidates(name, records):
    # Punctuation/case normalization is not identity confirmation.
    def norm(x):
        return re.sub(r"\s+", " ", x.strip()).casefold()
    return [r for r in records if norm(r["name"]) == norm(name)]


# Review-only translations anchored to source names, never accepted automatically.
ALIASES = {"24Hr Self-Serv. Area": ["24小時自助服務區"], "E-Government Display": ["電子政務展示區"],
           "CN Notarized Doc": ["公證文書辦公室(6人)"], "CN Signing Room": ["簽契室"],
           "CN Notory": ["公證員室"], "CN Studio": ["工作室"], "PR Lounge": ["公關休息室"],
           "Public Photocopy Area": ["公眾影印區"], "Nursing Room": ["哺乳室"],
           "Toilet(Parent-Child)": ["親子廁所"], "Security Room": ["保安室1", "保安室2"],
           "Security Room(CCTV)": ["保安室1", "保安室2"], "CN Storage Room": ["儲存室", "儲存室2", "儲存室3"],
           "CN Storage": ["儲存室", "儲存室2", "儲存室3"]}


def reconcile(reference, legacy_dir):
    ref_path = legacy_dir / "01_knowledge/HAP_Ref_Morais.json"
    project = legacy_dir / "04_projects/2026_Morais_GF_1F"
    bp_path, calc_path = project / "building_params.json", project / "calc_results.json"
    old = json.loads(ref_path.read_text(encoding="utf-8"))["spaces"]
    rooms = json.loads(bp_path.read_text(encoding="utf-8"))["rooms"]
    calc = json.loads(calc_path.read_text(encoding="utf-8"))["zones"]
    if len({x["room_id"] for x in rooms}) != len(rooms) or len({x["room_id"] for x in calc}) != len(calc):
        raise ValueError("Duplicate legacy room IDs")
    fields = {"floor_m2": "floor_area_m2", "people": "people", "sensible_W": "cooling_sensible_W", "latent_W": "cooling_latent_W"}
    old_matches, mappings = [], []
    for s in reference["spaces"]:
        found = exact_candidates(s["name"], old)
        diffs = []
        if len(found) == 1:
            for old_key, new_key in fields.items():
                if found[0].get(old_key) != s[new_key]:
                    diffs.append({"field": old_key, "legacy": found[0].get(old_key), "pdf": s[new_key]})
            for old_key, label, key in [("ceiling_m2", "Ceiling", "detail"), ("lighting_W", "Overhead Lighting", "detail"), ("equipment_W", "Electric Equipment", "detail"), ("wall_m2", "Wall Transmission", "detail"), ("window_m2", "Window Transmission", "detail")]:
                if found[0].get(old_key) != s["components"][label][key]:
                    diffs.append({"field": old_key, "legacy": found[0].get(old_key), "pdf": s["components"][label][key]})
            for old_key, key in [("tstat_C", "cooling_tstat_C"), ("oa_db_C", "cooling_oa_db_C"), ("oa_wb_C", "cooling_oa_wb_C")]:
                if found[0].get(old_key) != s["conditions"][key]:
                    diffs.append({"field": old_key, "legacy": found[0].get(old_key), "pdf": s["conditions"][key]})
        old_matches.append({"reference_id": s["reference_id"], "name": s["name"], "match_count": len(found), "differences": diffs,
                            "status": "exact_name_values_equal" if len(found) == 1 and not diffs else "requires_review"})
        candidates = []
        exact = exact_candidates(s["name"], rooms)
        for r in rooms:
            if r in exact or r["name"] in ALIASES.get(s["name"], []):
                cr = [c for c in calc if c["room_id"] == r["room_id"]]
                candidates.append({"room_id": r["room_id"], "name": r["name"], "floor": r.get("floor"),
                                   "reason": "exact_name_only" if r in exact else "translation_candidate_only",
                                   "floor_scope_compatible": r.get("floor") == "GF", "legacy_area_m2": r.get("area"),
                                   "area_difference_m2": r.get("area") - s["floor_area_m2"] if r.get("area") is not None else None,
                                   "legacy_input_people": r.get("occupancy"), "legacy_calculated_people": cr[0].get("occupancy") if len(cr) == 1 else None,
                                   "legacy_cooling_kW": cr[0].get("Q_cooling_kW") if len(cr) == 1 else None,
                                   "comparison_allowed": False})
        mappings.append({"reference_id": s["reference_id"], "name": s["name"], "status": "ambiguous" if len(candidates) > 1 else "candidate_pending_geometry_review" if candidates else "unmapped", "candidates": candidates})
    candidate_ids = {c["room_id"] for m in mappings for c in m["candidates"]}
    return {"schema_version": 1, "provenance": [source_info(p) for p in [ref_path, bp_path, calc_path]],
            "legacy_reference_comparison": old_matches, "building_mapping": mappings,
            "unmapped_legacy_room_ids": [r["room_id"] for r in rooms if r["room_id"] not in candidate_ids],
            "counts": {"pdf_spaces": len(reference["spaces"]), "legacy_reference_spaces": len(old), "legacy_input_rooms": len(rooms), "legacy_calc_rooms": len(calc),
                       "verified_same_scope_engine_comparisons": 0, "legacy_reference_equal": sum(x["status"] == "exact_name_values_equal" for x in old_matches)},
            "limits": ["Name equality is not geometry/scope equivalence.", "GF PDF cannot validate 1F loads.", "No engine accuracy percentage is computed until mapping and input conditions are approved."]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    args = parser.parse_args()
    r = args.root
    reference = extract(r / "data/raw/慕拉士_冷量計算_2_20231118.pdf", r / "data/raw/慕拉士_冷量計算_1_20231118.pdf")
    comparison = reconcile(reference, r / "data/local/legacy")
    out = r / "data/reference"
    out.mkdir(parents=True, exist_ok=True)
    for name, data in [("hap_reference.json", reference), ("hap_reconciliation.json", comparison)]:
        (out / name).write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(comparison["counts"], ensure_ascii=False))


if __name__ == "__main__":
    main()
