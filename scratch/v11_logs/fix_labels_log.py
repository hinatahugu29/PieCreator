import json
import os
from datetime import datetime, timezone, timedelta

log_path = r'g:\blender_addon\PieCreator\pie_creator_v11\agent-work-log.json'

new_entry = {
    "timestamp": datetime.now(timezone(timedelta(hours=9))).isoformat(),
    "user_request_summary": "Blender 5.1 におけるラベル取得の不具合（未知の物）と、サブメニューが登録されない問題の修正。",
    "task_summary": "ラベル取得ロジックの改善と動的登録の堅牢化",
    "ai_interpretation": "ユーザーの環境において一部のオペレーター名が正しく取得できず『未知の物』と表示される問題、およびサブメニューが Broken Link となる問題を解決したいと理解。Blender 5.1 の RNA アクセスを最適化し、動的クラス登録時の衝突回避ロジックを強化した。",
    "status": "completed",
    "duration_minutes": 15,
    "files_changed": [
        "pie_creator_v11/ops/core.py",
        "pie_creator_v11/ui/menus.py",
        "pie_creator_v11/__init__.py"
    ],
    "executed_actions": [
        "get_op_label と get_label_from_command を刷新し、RNA からの名前取得をより確実に実行するように改善",
        "create_menu_class を、常に新しいクラスを作成して古いキャッシュを無視するように変更",
        "register_dynamic_menus に、登録前の明示的な unregister 処理を追加して衝突を防止",
        "エラー時のログ出力を強化"
    ],
    "notes": "V10.2 と V11 が混在する環境でも、V11 のクラスが正しく優先して登録されるように調整した。",
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
