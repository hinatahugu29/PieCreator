import json
import os
from datetime import datetime, timezone, timedelta

log_path = r'g:\blender_addon\PieCreator\pie_creator_v11\agent-work-log.json'

new_entry = {
    "timestamp": datetime.now(timezone(timedelta(hours=9))).isoformat(),
    "user_request_summary": "マスターキーを押すと『PIECREATOR_MT_submenu_1 not found』エラーが出る問題の修正。",
    "task_summary": "存在しないマスターメニューIDへの参照によるエラーの回避と整合性チェックの実装",
    "ai_interpretation": "ユーザーは以前作成して削除した、あるいは名前を変更したメニュー（submenu_1）を『マスターメニュー』として設定したままになっており、実行時に存在しないクラスを呼び出そうとしてエラーになっていたと特定。データの整合性チェックと、削除時の自動解除ロジックが必要。",
    "status": "completed",
    "duration_minutes": 10,
    "files_changed": [
        "pie_creator_v11/ops/core.py",
        "pie_creator_v11/ops/ui_ops.py"
    ],
    "executed_actions": [
        "CallMaster 実行時に、設定されている master_menu_id が現存するかチェックし、存在しない場合は最初の有効なメニューにフォールバックするロジックを追加",
        "RemoveMenu 実行時に、削除対象のメニューがマスターメニューに設定されていた場合、設定を自動的に解除するように修正",
        "MCP経由でユーザーの config.json を直接修正し、不正な master_menu_id をリセットした"
    ],
    "notes": "設定データと実データの乖離による典型的な参照エラーだったが、今後は自動で修復されるようになった。",
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
