import json
import os
from datetime import datetime, timezone, timedelta

log_path = r'g:\blender_addon\PieCreator\pie_creator_v11\agent-work-log.json'

new_entry = {
    "timestamp": datetime.now(timezone(timedelta(hours=9))).isoformat(),
    "user_request_summary": "各メニューのショートカットキーを明示的にクリア（解除）する機能の追加依頼。",
    "task_summary": "個別のキーマップ解除機能の実装",
    "ai_interpretation": "自動切替（マスターキー）機能が完成したため、各メニューに個別に割り当てていたキーを解除し、マスターキー一本に集約したいというニーズがあると判断。UI上で簡単に解除できる『×』ボタンを追加した。",
    "status": "completed",
    "duration_minutes": 5,
    "files_changed": [
        "pie_creator_v11/ops/ui_ops.py",
        "pie_creator_v11/ui/components.py"
    ],
    "executed_actions": [
        "指定されたメニューIDのキーマップを 'NONE' に設定する PIECREATOR_OT_ClearShortcut オペレーターを追加",
        "メニューヘッダーのキー設定フィールドの横に、解除用の『×』ボタンを表示するように UI を更新"
    ],
    "notes": "マスターキー運用への移行をスムーズにするための改善。",
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
