"""建立2024零售展廳試點的顯式24小時負荷輸入。

圖紙只提供空間分布和局部尺寸；本檔內每一項推定均寫入來源與假設，
用於端到端流程測試，不可替代竣工資料或設備選型表。
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TIMES = [f"2026-07-15T{hour:02}:00" for hour in range(24)]
PEOPLE = [0, 0, 0, 0, 0, 0, 0, 0.1, 0.3, 0.5, 0.65, 0.75,
          0.85, 0.9, 0.95, 1, 1, 0.9, 0.75, 0.55, 0.3, 0.1, 0, 0]
LIGHTS = [0, 0, 0, 0, 0, 0, 0, 0.1, 0.4, 0.8, 1, 1, 1, 1, 1, 1,
          1, 1, 0.85, 0.6, 0.3, 0.1, 0, 0]
EQUIPMENT = [0.1, 0.1, 0.1, 0.1, 0.1, 0.1, 0.1, 0.2, 0.4, 0.6, 0.8, 0.9,
             1, 1, 1, 1, 1, 1, 0.8, 0.6, 0.4, 0.2, 0.1, 0.1]
ENVELOPE = [0.20, 0.20, 0.20, 0.20, 0.20, 0.20, 0.25, 0.30, 0.40, 0.52,
            0.65, 0.76, 0.86, 0.94, 1.00, 1.00, 0.96, 0.88, 0.76, 0.63,
            0.50, 0.40, 0.30, 0.24]


def component(name: str, sensible_peak_kw: float, latent_peak_kw: float = 0.0):
    """將已明示的試點輪廓轉為冷負荷分項；並非動態傳熱模型。"""
    return {
        "name": name,
        "sensible_kw": [round(sensible_peak_kw * factor, 4) for factor in ENVELOPE],
        "latent_kw": [round(latent_peak_kw * factor, 4) for factor in ENVELOPE],
        "has_sf": False,
        "source_zh": "測試假設：圖紙未提供U值、SHGC、方位或逐時氣象；以明示峰值及24小時輪廓佔位。"
    }


def room(room_id: str, system_id: str, floor: str, name: str, area: float, people: int,
         function: str, envelope_kw: float, *, toilet: bool = False, equipment_w_m2: float = 0.0,
         lighting_w_m2: float = 0.0, person_sensible: float = 0.0, person_latent: float = 0.0):
    lighting = area * lighting_w_m2
    equipment = area * equipment_w_m2
    return {
        "room_id": room_id,
        "system_id": system_id,
        "time_keys": TIMES,
        "has_sf": False,
        "needs_fresh_air": not toilet,
        "people": people,
        "volume_m3": round(area * 3.0, 2),
        "exhaust_ach": 15.0 if toilet else 0.0,
        "components": [component("圍護及日射暫定負荷", envelope_kw)],
        "internal_gains": {
            "name": "按用途發熱參考的測試輸入",
            "time_keys": TIMES,
            "has_sf": False,
            "people": people,
            "person_sensible_w": person_sensible,
            "person_latent_w": person_latent,
            "lighting_w": round(lighting, 2),
            "equipment_sensible_w": round(equipment, 2),
            "equipment_latent_w": 0.0,
            "people_schedule": [0.05 if toilet else value for value in PEOPLE],
            "lighting_schedule": LIGHTS,
            "equipment_schedule": EQUIPMENT,
            "source_zh": "人員：ASHRAE 2025 Fundamentals SI Ch18 Table 4；照明：Table 5/90.1-2022限值參考；設備及排程為本測試明示假設。",
        },
        "room_metadata": {
            "floor": floor,
            "name_zh": name,
            "function": function,
            "area_m2": area,
            "area_basis_zh": "由A3 1:50圖紙局部尺寸及平面邊界估算，待量度原CAD或現場覆核。",
            "height_basis_zh": "圖紙未提供淨高；本試點明示假設3.0m。",
            "envelope_basis_zh": "圖紙未提供牆窗性能、方位及遮陽；此分項僅為端到端測試輸入。",
            "review_status": "測試假設，待項目覆核",
        },
    }


def main():
    retail = dict(lighting_w_m2=9.1, equipment_w_m2=5.0, person_sensible=73.0, person_latent=59.0)
    seated = dict(lighting_w_m2=9.5, equipment_w_m2=4.91, person_sensible=72.0, person_latent=45.0)
    storage = dict(lighting_w_m2=3.8, equipment_w_m2=0.0, person_sensible=0.0, person_latent=0.0)
    toilet = dict(lighting_w_m2=8.0, equipment_w_m2=0.0, person_sensible=0.0, person_latent=0.0)
    rooms = [
        room("BF-01", "DX-BF", "地庫", "展廳", 46, 12, "retail", 2.30, **retail),
        room("BF-02", "DX-BF", "地庫", "倉庫", 12, 0, "storage", 0.45, **storage),
        room("BF-03", "DX-BF", "地庫", "衛生間", 4, 0, "toilet", 0.12, toilet=True, **toilet),
        room("GF-01", "DX-GF", "地面層", "零售展區", 71, 35, "retail", 7.10, **retail),
        room("GF-02", "DX-GF", "地面層", "試衣間", 8, 4, "meeting", 0.42, **seated),
        room("GF-03", "DX-GF", "地面層", "收銀台", 5, 2, "office", 0.25, **seated),
        room("GF-04", "DX-GF", "地面層", "衛生間", 3, 0, "toilet", 0.10, toilet=True, **toilet),
        room("1F-01", "DX-1F", "一樓", "零售展區", 75, 35, "retail", 7.50, **retail),
        room("1F-02", "DX-1F", "一樓", "試衣間", 8, 4, "meeting", 0.42, **seated),
    ]
    payload = {
        "schema_version": 1,
        "project_id": "TRIAL-2024-06-03-RETAIL-3F",
        "source_classification": "圖紙萃取加明示測試假設",
        "notice": "端到端設計測試。圖紙提供空間分布及局部尺寸；未提供的面積、淨高、圍護性能、方位、人數、設備及排程以本檔明示假設填入。結果不得作施工或採購。",
        "time_keys": TIMES,
        "rooms": rooms,
    }
    target = ROOT / "data" / "local" / "trial_2024_06_03_retail_input.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(target)


if __name__ == "__main__":
    main()
