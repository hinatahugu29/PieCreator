import json
import os
from datetime import datetime, timezone, timedelta

log_path = r'g:\blender_addon\PieCreator\pie_creator_v11\agent-work-log.json'

new_entry = {
    "timestamp": datetime.now(timezone(timedelta(hours=9))).isoformat(),
    "user_request_summary": "アドオン設定画面（Preferences）が表示されない問題の修正。",
    "task_summary": "アドオン設定UIの表示復旧",
    "ai_interpretation": "フォルダ名を v11 に変更した際、AddonPreferences の bl_idname が以前のバージョンのまま（pie_creator_v10_2）になっていたため、Blender が設定画面を認識できていなかった。bl_idname を動的にパッケージ名から取得するように修正した。",
    "status": "completed",
    "duration_minutes": 5,
    "files_changed": [
        "pie_creator_v11/ui/preferences.py"
    ],
    "executed_actions": [
        "PIECREATOR_Preferences の bl_idname を __package__.split('.')[0] に変更し、フォルダ名変更に追従するように修正"
    ],
    "notes": "アドオンをコピーして新バージョンを作る際は、bl_idname の整合性に注意が必要。",
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
