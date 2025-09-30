import os
import requests
from dotenv import load_dotenv

# .env 読み込み
load_dotenv()

NOTION_TOKEN = os.getenv("NOTION_TOKEN")
NOTION_DB_ID = os.getenv("NOTION_DB_ID")
SLACK_WEBHOOK_URL = os.getenv("SLACK_WEBHOOK_URL")

# 起動時バリデーション
missing_envs = [name for name, val in {
    "NOTION_TOKEN": NOTION_TOKEN,
    "NOTION_DB_ID": NOTION_DB_ID,
    "SLACK_WEBHOOK_URL": SLACK_WEBHOOK_URL,
}.items() if not val]
if missing_envs:
    raise RuntimeError(
        "必須の環境変数が未設定です: " + ", ".join(missing_envs) +
        "\n.env に以下を設定してください:\nNOTION_TOKEN, NOTION_DB_ID, SLACK_WEBHOOK_URL"
    )

headers = {
    "Authorization": f"Bearer {NOTION_TOKEN}",
    "Content-Type": "application/json",
    "Notion-Version": "2022-06-28"
}

# Notion 認証確認
def verify_notion_auth():
    url = "https://api.notion.com/v1/users/me"
    res = requests.get(url, headers=headers)
    if res.status_code == 401:
        raise RuntimeError(
            "Notion 認証に失敗しました (401 Unauthorized)。"\
            "\n確認事項:"\
            "\n- NOTION_TOKEN が正しい（`secret_` で始まる内部統合トークン）"\
            "\n- 対象データベースを Notion の「共有」でこの統合に共有済み"\
            "\n- トークンに必要な権限がある"\
        )
    res.raise_for_status()

# Notion DB クエリ関数
def notion_query():
    url = f"https://api.notion.com/v1/databases/{NOTION_DB_ID}/query"
    res = requests.post(url, headers=headers)
    res.raise_for_status()
    return res.json()

def format_notion_results(data):
    results = data.get("results", [])
    tasks = []
    for r in results:
        props = r.get("properties", {})

        # タイトル列
        title_prop = props.get("Title", {}).get("title", [])
        name_text = title_prop[0]["plain_text"] if title_prop else "No Title"

        # ステータス列
        status = props.get("Status", {}).get("select", {}).get("name", "No Status")

        # Notes列
        notes_prop = props.get("Notes", {}).get("rich_text", [])
        notes_text = notes_prop[0]["plain_text"] if notes_prop else ""

        # ★ 未着手のみフィルタ
        if not status == "完了":
            line = f"- {name_text} ({status})"
            if notes_text:
                line += f" : {notes_text}"
            tasks.append(line)

    return tasks

# Slack 通知関数
def send_to_slack(message):
    payload = {"text": message}
    res = requests.post(SLACK_WEBHOOK_URL, json=payload)
    res.raise_for_status()
    return res.text

if __name__ == "__main__":
    data = notion_query()
    tasks = format_notion_results(data)

    count = len(tasks)
    msg = f"✅ Notion DB に {count} 件のレコードがあります。\n\n"
    msg += "\n".join(tasks[:5])  # 上位5件だけ表示（長すぎ防止）

    print(msg)
    send_to_slack(msg)
