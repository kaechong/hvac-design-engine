"""唯讀取得設備快照後重建三份設計成果；回退舊快照明示日期，不改來源事實。"""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]


def choose_existing_snapshot(explicit=None):
    candidates=[Path(explicit).resolve()] if explicit else list((ROOT/'data/local').glob('equipment_snapshot_*.json'))
    valid=[]
    for path in candidates:
        try:
            data=json.loads(path.read_text(encoding='utf-8-sig'))
            if not data.get('queried_at') or not data.get('source'):continue
            if not all(isinstance(data.get(k),list) for k in ('materials','specs','certifications','documents')):continue
            valid.append((data['queried_at'],path,data))
        except (OSError,ValueError):continue
    if not valid:raise FileNotFoundError('沒有可用的設備資料快照；無法產生有來源的選型。')
    return max(valid,key=lambda item:item[0])


def main():
    if hasattr(sys.stdout,'reconfigure'):sys.stdout.reconfigure(encoding='utf-8')
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--snapshot',help='明確使用既有快照；不查即時資料庫')
    parser.add_argument('--output-dir',default='outputs/selected_20260908')
    args=parser.parse_args()
    node=os.environ.get('HVAC_NODE') or shutil.which('node') or str(Path.home()/'.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node.exe')
    mode='fallback_snapshot';notice=''
    if not args.snapshot:
        try:
            r=subprocess.run([node,'scripts/fetch_equipment_snapshot.mjs'],cwd=ROOT,check=True,capture_output=True,text=True,encoding='utf-8',timeout=180)
            info=json.loads(r.stdout.strip().splitlines()[-1]);snapshot_path=Path(info['path'])
            date,snapshot_path,data=choose_existing_snapshot(snapshot_path)
            mode='live_refresh';notice=f'本輪唯讀查詢完成；快照日期 {date}；來源 {data["source"]}。'
        except (subprocess.SubprocessError,OSError,ValueError,KeyError):
            date,snapshot_path,data=choose_existing_snapshot()
            notice=f'本輪即時查詢未成功；使用既有快照 {snapshot_path}，查詢日期 {date}，原來源 {data["source"]}；並非本輪即時資料。'
    else:
        date,snapshot_path,data=choose_existing_snapshot(args.snapshot)
        notice=f'明確使用既有快照 {snapshot_path}，查詢日期 {date}，原來源 {data["source"]}；未執行本輪即時查詢。'
    print(notice,flush=True)
    env=os.environ.copy()
    env.update(HVAC_EQUIPMENT_SNAPSHOT=str(snapshot_path),HVAC_SNAPSHOT_MODE=mode,HVAC_SNAPSHOT_NOTICE=notice,
               HVAC_OUTPUT_DIR=str((ROOT/args.output_dir).resolve()),HVAC_PYTHON=sys.executable,PYTHONIOENCODING='utf-8')
    steps=[
        [sys.executable,'scripts/build_selected_package.py'],
        [node,'scripts/build_retail_trial_workbook.mjs'],
        [node,'scripts/build_equipment_schedule.mjs'],
        [sys.executable,'scripts/build_retail_trial_narrative.py'],
        [sys.executable,'scripts/set_output_print_layout.py'],
        [sys.executable,'scripts/verify_selected_outputs.py'],
    ]
    for command in steps:subprocess.run(command,cwd=ROOT,env=env,check=True)


if __name__=='__main__':main()
