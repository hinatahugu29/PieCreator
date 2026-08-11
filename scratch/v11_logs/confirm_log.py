import json
import os
from datetime import datetime, timezone, timedelta

log_path = r'g:\blender_addon\PieCreator\pie_creator_v10_2\agent-work-log.json'

new_entry = {
    "timestamp": datetime.now(timezone(timedelta(hours=9))).isoformat(),
    "user_request_summary": "修正内容が Blender 5.1 で正常に動作することを確認。",
    "task_summary": "修正後の動作確認完了",
    "ai_interpretation": "ユーザーから修正が正常に機能したとの報告を受けた。Blender 5.1 におけるメニュー検索および初期化処理の安定化が達成されたことを確認。",
    "status": "completed",
    "duration_minutes": 1,
    "files_changed": [],
    "executed_actions": [
        "ユーザーによる動作確認の受領"
    ],
    "notes": "本件（Menu ID が空になる問題）はこれにて完了。",
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
