import json
import os
from datetime import datetime, timezone, timedelta

log_path = r'g:\blender_addon\PieCreator\pie_creator_v10_2\agent-work-log.json'

new_entry = {
    "timestamp": datetime.now(timezone(timedelta(hours=9))).isoformat(),
    "user_request_summary": "Blender 5.1 において Menu ID が空（検索結果なし）になる問題の修正依頼。",
    "task_summary": "Blender 5.1 対応のためのメニューおよびアイコン取得ロジックの改善",
    "ai_interpretation": "ユーザーは Blender 5.1 環境でメニュー検索が機能しない問題を解決したいと考えている。原因はアイコン初期化時のエラーによる処理の中断と、メニュー収集ロジックの不備にあると判断。初期化処理の分離と、継承関係に基づく確実なメニュー収集を実装した。",
    "status": "completed",
    "duration_minutes": 15,
    "files_changed": [
      "pie_creator_v10_2/__init__.py",
      "pie_creator_v10_2/ops/io.py"
    ],
    "executed_actions": [
      "__init__.py の register() 内でアイコン取得とメニュー取得を別個の try-except で保護するように修正",
      "アイコン取得時に _bpy 依存を減らし、標準 RNA アクセスを試行するように改善",
      "ops/io.py の init_blender_menus() を、issubclass(cls, bpy.types.Menu) を使用したより堅牢なロジックに刷新",
      "メニューの bl_label が空の場合でもクラス名をラベルとして表示するフォールバック処理を追加"
    ],
    "notes": "Blender 5.1 での内部仕様変更による致命的な初期化エラーを回避し、かつ検索対象となるメニューの網羅性を向上させた。",
    "artifacts": [
      "implementation_plan.md",
      "task.md"
    ]
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
