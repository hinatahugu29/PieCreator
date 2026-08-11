import json
import os
from datetime import datetime, timezone, timedelta

log_path = r'g:\blender_addon\PieCreator\pie_creator_v11\agent-work-log.json'

new_entry = {
    "timestamp": datetime.now(timezone(timedelta(hours=9))).isoformat(),
    "user_request_summary": "メニューの登録状況をデバッグログに出力する機能の追加依頼。",
    "task_summary": "動的メニュー登録時の詳細なログ出力機能の実装",
    "ai_interpretation": "ユーザーは、サブメニューや特定モード向けのメニューが正しく登録されているか、どのデッキに属しているかなどをトラブルシューティングするために、登録プロセスの可視化を求めていると理解。System Console で一覧できる見やすいフォーマットで出力するようにした。",
    "status": "completed",
    "duration_minutes": 5,
    "files_changed": [
        "pie_creator_v11/__init__.py"
    ],
    "executed_actions": [
        "register_dynamic_menus 内に、登録メニューの総数と現在のアクティブデッキを表示するヘッダーを追加",
        "各メニューの登録時に、メニュー名、ID、アイテム数、所属デッキを出力するようにした",
        "特定モードやエリア（Edit Mode限定など）が設定されている場合は、それも Context としてログに出力するように追加"
    ],
    "notes": "ユーザーがメニューが動作しない際の原因究明（未登録なのか、コンテキストが合っていないのか）を容易にするためのログ設計。",
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
