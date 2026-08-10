import json
import os
from datetime import datetime, timezone, timedelta

log_path = r'g:\blender_addon\PieCreator\pie_creator_v11\agent-work-log.json'

new_entry = {
    "timestamp": datetime.now(timezone(timedelta(hours=9))).isoformat(),
    "user_request_summary": "Manage Modes/Areas のボタンを押すと、同じパネルが重複して開いてしまう不具合の修正。",
    "task_summary": "ダイアログ内でのオペレーター再呼び出しによる重複防止の実装",
    "ai_interpretation": "ユーザーはダイアログ内で設定を切り替える際、クリックのたびに新しいダイアログが上に重なっていく現象を報告。invoke メソッドが常にダイアログを表示するように設定されていたため、ボタンからの呼び出し（引数あり）と初期呼び出し（引数なし）を判別するように修正した。",
    "status": "completed",
    "duration_minutes": 5,
    "files_changed": [
        "pie_creator_v11/ops/ui_ops.py"
    ],
    "executed_actions": [
        "PIECREATOR_OT_ManageModes の invoke 内に、mode プロパティがセットされている場合はダイアログを出さずに execute を実行する分岐を追加",
        "PIECREATOR_OT_ManageAreas の invoke 内に、area_type プロパティがセットされている場合はダイアログを出さずに execute を実行する分岐を追加"
    ],
    "notes": "Blenderの invoke_props_dialog を使用するオペレーターで、内部ボタンから自分自身を呼び出す際の典型的な修正を適用した。",
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
