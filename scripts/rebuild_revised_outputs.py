"""重建同版本三份成果，保留上一輪檔案，不產生交付 PDF。"""
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]
NODE=Path.home()/'.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node.exe'

def main():
    if not NODE.exists():raise FileNotFoundError('需由 Codex workspace dependencies 提供 Node runtime')
    steps=[
        [sys.executable,'scripts/build_design_package.py'],
        [str(NODE),'scripts/build_retail_trial_workbook.mjs'],
        [str(NODE),'scripts/build_equipment_schedule.mjs'],
        [sys.executable,'scripts/build_retail_trial_narrative.py'],
        [sys.executable,'scripts/set_output_print_layout.py'],
        [sys.executable,'scripts/verify_revised_outputs.py'],
    ]
    for command in steps:subprocess.run(command,cwd=ROOT,check=True)

if __name__=='__main__':main()
