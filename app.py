import os
import asyncio
from typing import Optional, Dict, Any, List
from fastapi import FastAPI, Request, Form, BackgroundTasks, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from database import (
    init_db, get_jobs, get_applications, add_application, 
    update_application_status, delete_application, get_settings, 
    update_setting, save_job
)
from scrapers import run_all_scrapers
from pitch_generator import generate_pitch
from telegram_bot import send_telegram_message, format_job_alert

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TEMPLATES_DIR = os.path.join(BASE_DIR, "templates")
os.makedirs(TEMPLATES_DIR, exist_ok=True)

app = FastAPI(title="Remote Design Job Hunter & Command Center")
templates = Jinja2Templates(directory=TEMPLATES_DIR)

from apscheduler.schedulers.asyncio import AsyncIOScheduler

scheduler = AsyncIOScheduler()

async def scheduled_scan():
    print("⏰ [Background Scheduler] Running 30-minute automated job board scan...")
    try:
        results = run_all_scrapers()
        settings = get_settings()
        if settings.get("telegram_enabled") == "true":
            token = settings.get("telegram_token", "")
            chat_id = settings.get("telegram_chat_id", "")
            if token and chat_id and results.get("total_new", 0) > 0:
                new_jobs = get_jobs(limit=min(3, results.get("total_new", 0)))
                for job in new_jobs:
                    alert_text = format_job_alert(job)
                    send_telegram_message(token, chat_id, alert_text)
        print(f"✅ [Background Scheduler] Scan completed: {results}")
    except Exception as e:
        print(f"❌ [Background Scheduler] Error during scan: {e}")

# Initialize database schema and scheduler on startup
@app.on_event("startup")
async def on_startup():
    init_db()
    try:
        scheduler.add_job(scheduled_scan, "interval", minutes=30)
        scheduler.start()
        print("🚀 [Scheduler] Automated 30-minute job hunter started!")
    except Exception as e:
        print(f"Scheduler startup notice: {e}")

@app.on_event("shutdown")
async def on_shutdown():
    scheduler.shutdown()

# Models
class PitchRequest(BaseModel):
    company: str
    role: str
    category: str
    recipient: Optional[str] = "Hiring Team"

class ApplicationCreate(BaseModel):
    job_id: Optional[int] = None
    company: str
    title: str
    url: Optional[str] = ""
    salary: Optional[str] = ""
    status: Optional[str] = "bookmarked"
    category: Optional[str] = "UI/UX"
    pitch_used: Optional[str] = ""
    notes: Optional[str] = ""

class StatusUpdate(BaseModel):
    status: str
    notes: Optional[str] = None

class SettingsUpdate(BaseModel):
    telegram_token: Optional[str] = None
    telegram_chat_id: Optional[str] = None
    telegram_enabled: Optional[str] = None
    filter_category: Optional[str] = None
    filter_worldwide_only: Optional[str] = None

# Routes
@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    return templates.TemplateResponse(request=request, name="index.html")

@app.get("/api/jobs")
async def api_get_jobs(
    search: str = "", 
    category: str = "all", 
    level: str = "all", 
    worldwide_only: bool = False, 
    date_filter: str = "all",
    exclude_applied: bool = True,
    limit: int = 200
):
    jobs = get_jobs(
        search=search, 
        category=category, 
        level=level, 
        worldwide_only=worldwide_only, 
        date_filter=date_filter, 
        exclude_applied=exclude_applied,
        limit=limit
    )
    return {"jobs": jobs, "total": len(jobs)}

@app.post("/api/scan")
async def api_scan(background_tasks: BackgroundTasks):
    try:
        results = run_all_scrapers()
        settings = get_settings()
        if settings.get("telegram_enabled") == "true":
            token = settings.get("telegram_token", "")
            chat_id = settings.get("telegram_chat_id", "")
            if token and chat_id and results.get("total_new", 0) > 0:
                new_jobs = get_jobs(limit=min(3, results.get("total_new", 0)))
                for job in new_jobs:
                    alert_text = format_job_alert(job)
                    send_telegram_message(token, chat_id, alert_text)
        return {"status": "success", "results": results}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/generate-pitch")
async def api_generate_pitch(req: PitchRequest):
    pitch = generate_pitch(
        company=req.company,
        role=req.role,
        category=req.category,
        recipient=req.recipient or "Hiring Team"
    )
    return pitch

@app.get("/api/applications")
async def api_get_applications():
    apps = get_applications()
    return {"applications": apps}

@app.post("/api/applications")
async def api_add_application(app_data: ApplicationCreate):
    app_id = add_application(app_data.dict())
    return {"status": "success", "id": app_id}

@app.put("/api/applications/{app_id}/status")
async def api_update_status(app_id: int, update: StatusUpdate):
    update_application_status(app_id, update.status, update.notes)
    return {"status": "success"}

@app.delete("/api/applications/{app_id}")
async def api_delete_application(app_id: int):
    delete_application(app_id)
    return {"status": "success"}

@app.get("/api/settings")
async def api_get_settings():
    return get_settings()

@app.post("/api/settings")
async def api_update_settings(settings: SettingsUpdate):
    for k, v in settings.dict(exclude_unset=True).items():
        if v is not None:
            update_setting(k, v)
    return {"status": "success", "settings": get_settings()}

@app.post("/api/telegram/test")
async def api_test_telegram():
    from telegram_bot import auto_detect_chat_id
    settings = get_settings()
    token = settings.get("telegram_token", "")
    chat_id = settings.get("telegram_chat_id", "")
    
    if not token:
        return {"success": False, "message": "Telegram Bot Token is missing."}
        
    if not chat_id:
        chat_id = auto_detect_chat_id(token)
        
    if not chat_id:
        return {
            "success": False, 
            "message": "Chat ID not found yet! Please open @DesignJob_Machinebot on your Telegram app, press 'START', and then click this button again."
        }
        
    test_msg = """<b>🚀 Design Job Machine Connected!</b>

Your bot is now live and sending <b>100% Free Remote Design Jobs</b> directly to your phone.
Whenever new Graphic Design & UI/UX roles are posted, you will receive instant alerts here!"""
    
    success, msg = send_telegram_message(token, chat_id, test_msg)
    return {"success": success, "message": msg}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
