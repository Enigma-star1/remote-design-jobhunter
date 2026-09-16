import requests
from typing import Dict, Any, Tuple, Optional
from database import update_setting, get_settings

def auto_detect_chat_id(token: str) -> Optional[str]:
    """Fetch the latest chat_id from users who pressed /start on the bot"""
    if not token:
        return None
    try:
        url = f"https://api.telegram.org/bot{token.strip()}/getUpdates"
        r = requests.get(url, timeout=10)
        data = r.json()
        if data.get("ok") and data.get("result"):
            # Get the most recent message's chat ID
            latest = data["result"][-1]
            if "message" in latest and "chat" in latest["message"]:
                chat_id = str(latest["message"]["chat"]["id"])
                update_setting("telegram_chat_id", chat_id)
                update_setting("telegram_enabled", "true")
                return chat_id
    except Exception as e:
        print(f"Error auto-detecting chat ID: {e}")
    return None

def send_telegram_message(token: str, chat_id: str, text: str) -> Tuple[bool, str]:
    if not token or not chat_id:
        return False, "Telegram Bot Token or Chat ID is missing."
    
    url = f"https://api.telegram.org/bot{token.strip()}/sendMessage"
    payload = {
        "chat_id": chat_id.strip(),
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": False
    }
    
    try:
        r = requests.post(url, json=payload, timeout=10)
        res = r.json()
        if r.status_code == 200 and res.get("ok"):
            return True, "Alert sent successfully!"
        else:
            return False, f"Telegram API error: {res.get('description', 'Unknown error')}"
    except Exception as e:
        return False, f"Connection failed: {str(e)}"

def format_job_alert(job: Dict[str, Any]) -> str:
    category_emoji = "🎨" if "Graphic" in job.get("category", "") else "📱"
    return f"""<b>{category_emoji} New 100% Free Remote Design Job!</b>

<b>Title:</b> {job.get('title', 'Design Role')}
<b>Company:</b> {job.get('company', 'Unknown')}
<b>Category:</b> {job.get('category', 'Design')}
<b>Level:</b> {job.get('level', 'All')}
<b>Location:</b> {job.get('location', 'Remote (Worldwide)')}
<b>Salary:</b> {job.get('salary', 'Disclosed on Apply')}
<b>Source:</b> {job.get('source', 'Web')}

🔗 <a href="{job.get('url', '#')}"><b>Click Here to View & Apply (Free)</b></a>
"""
