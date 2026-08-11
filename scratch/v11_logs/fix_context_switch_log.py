import json
import os
from datetime import datetime, timezone, timedelta

log_path = r'g:\blender_addon\PieCreator\pie_creator_v11\agent-work-log.json'

new_entry = {
    "timestamp": datetime.now(timezone(timedelta(hours=9))).isoformat(),
    "user_request_summary": "Modes設定を行っても動作が切り替わらない問題の調査とデバッグ強化。",
    "task_summary": "CallMaster におけるモード判定処理の可視化",
    "ai_interpretation": "ユーザーはモード設定が機能していないと感じている。原因として、現在のモード（context.mode）と設定値の不一致、あるいはマスターメニュー設定による上書きが考えられるため、実行時の判定プロセスをコンソールに出力して原因を特定しやすくした。",
    "status": "completed",
    "duration_minutes": 5,
    "files_changed": [
        "pie_creator_v11/ops/core.py"
    ],
    "executed_actions": [
        "CallMaster の実行時に、現在の Blender のモード（OBJECT, EDIT_MESH など）をコンソールに表示するログを追加",
        "条件に合致したメニューが見つかった場合、および見つからずにマスターメニューにフォールバックした場合の各ステップにログを追加"
    ],
    "notes": "Blender 5.1 のモード名が従来と異なる可能性も考慮し、実際の値をログで確認できるようにした。",
    "artifacts": []
}

if os.path.exists(log_path):
    with open(log_path, 'r', encoding='utf-8') as f:
        try:
            data = json.load(f)
        except:
            data = []
else:
    data = []

data.append(new_entry)

with open(log_path, 'w', encoding='utf-8') as f:
    json.dump(data, f, indent=2, ensure_ascii=False)
