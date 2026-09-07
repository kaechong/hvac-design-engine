"""下載已登錄來源至 Git 忽略的本機快取；不修改來源或保存憑證。"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import urllib.parse
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
REFERENCE_PATHS = [
    "01_knowledge/Equipment_Catalog.json",
    "01_knowledge/Weather_Data_Macau.json",
    "01_knowledge/CLTD_SCL_Matrices.json",
    "01_knowledge/HAP_Ref_Morais.json",
    "01_knowledge/Master_Knowledge.md",
    "01_knowledge/SOP_Workflow.md",
    "02_templates/narrative_boilerplate.py",
    "02_templates/Design_Narrative_Guide.md",
    "02_templates/excel_styles.py",
    "03_scripts/hvac_calc_core.py",
    "03_scripts/export_deliverables.py",
    "03_scripts/parse_drawing.py",
    "04_projects/2026_Morais_GF_1F/building_params.json",
    "04_projects/2026_Morais_GF_1F/calc_results.json",
    "04_projects/2026_Morais_GF_1F/ade_markdown.md",
]


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--token-file", type=Path, required=True)
    args = parser.parse_args()
    manifest = json.loads((ROOT / "sources/manifest.json").read_text(encoding="utf-8"))
    token = json.loads(args.token_file.read_text(encoding="utf-8"))
    body = urllib.parse.urlencode({k: token[k] for k in ("client_id", "client_secret", "refresh_token")} | {"grant_type": "refresh_token"}).encode()
    request = urllib.request.Request("https://oauth2.googleapis.com/token", data=body)
    with urllib.request.urlopen(request, timeout=30) as response:
        access = json.load(response)["access_token"]
    for entry in manifest["files"]:
        target = ROOT / "data/raw" / entry["name"]
        if target.exists() and hashlib.sha256(target.read_bytes()).hexdigest() == entry["sha256"]:
            print(f"已驗證快取：{target.name}")
            continue
        request = urllib.request.Request(f"https://www.googleapis.com/drive/v3/files/{entry['drive_id']}?alt=media", headers={"Authorization": "Bearer " + access})
        with urllib.request.urlopen(request, timeout=60) as response:
            content = response.read()
        if hashlib.sha256(content).hexdigest() != entry["sha256"]:
            raise ValueError(f"來源雜湊改變，停止：{entry['name']}")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)
        print(f"已下載及驗證：{target.name}")
    repo = manifest["format_reference"]["repository"]
    ref = manifest["format_reference"]["commit"]
    paths = REFERENCE_PATHS + manifest["format_reference"]["paths"]
    inventory = []
    for path in paths:
        endpoint = f"repos/{repo}/contents/{urllib.parse.quote(path, safe='/')}?ref={ref}"
        result = subprocess.run(["gh", "api", endpoint], check=True, capture_output=True)
        metadata = json.loads(result.stdout)
        content = base64.b64decode(metadata["content"])
        target = ROOT / "data/local/legacy" / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)
        inventory.append({"path": path, "commit": ref, "sha256": hashlib.sha256(content).hexdigest(), "git_blob_sha": metadata["sha"]})
        print(f"已取得參考：{path}")
    (ROOT / "data/local/legacy_inventory.json").write_text(json.dumps(inventory, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
