"""離線檢查公司標準、來源雜湊、核心及基準對照測試。"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    standard = json.loads((ROOT / "config/company_standard.json").read_text(encoding="utf-8"))
    rules = standard["approved_rules"]
    if (rules["fresh_air_lps_per_person"], rules["cooling_safety_factor"], rules["safety_factor_scope"]) != (10, 1.15, "final_raw_cooling_load_once"):
        raise ValueError("已核准的新風／安全係數規則發生改變")
    if standard["unapproved_defaults_enabled"] or any(p["runtime_default"] is not None and p["status"] != "approved" for p in standard["proposals"]):
        raise ValueError("未核准預設值不能啟用")
    manifest = json.loads((ROOT / "sources/manifest.json").read_text(encoding="utf-8"))
    checked = 0
    for record in manifest["files"]:
        path = ROOT / "data/raw" / record["name"]
        if path.exists():
            if hashlib.sha256(path.read_bytes()).hexdigest() != record["sha256"]:
                raise ValueError(f"來源雜湊改變：{path.name}")
            checked += 1
    print(f"已核准規則通過；本機來源雜湊已檢查 {checked}/{len(manifest['files'])} 份。", flush=True)
    if checked < len(manifest["files"]):
        print("未下載的原始PDF不在本次重新讀取範圍；派生資料檢查仍會執行。", flush=True)
    result = subprocess.run([sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v"], cwd=ROOT)
    return result.returncode


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ValueError, KeyError, OSError) as exc:
        print(f"驗證未完成：{exc}", file=sys.stderr)
        raise SystemExit(2)
