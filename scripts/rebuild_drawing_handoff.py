"""沿用既有設計快照重建四份成果，不執行即時查庫。"""
import os
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]
def main():
    env=os.environ.copy()
    env.setdefault('HVAC_OUTPUT_DIR',str(ROOT/'outputs/drawing_handoff_20260910'))
    env['HVAC_PYTHON']=sys.executable
    node=env.get('HVAC_NODE',str(Path.home()/'.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node.exe'))
    for command in [[sys.executable,'scripts/build_drawing_handoff.py'],[node,'scripts/build_retail_trial_workbook.mjs'],[node,'scripts/build_equipment_schedule.mjs'],[sys.executable,'scripts/build_retail_trial_narrative.py'],[sys.executable,'scripts/set_output_print_layout.py'],[sys.executable,'scripts/verify_drawing_handoff.py']]:
        subprocess.run(command,cwd=ROOT,env=env,check=True)

if __name__=='__main__':main()
