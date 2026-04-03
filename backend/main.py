from fastapi import FastAPI, Depends, HTTPException, BackgroundTasks
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from fastapi.middleware.cors import CORSMiddleware
from typing import List, Optional
import io
import csv
import json
import os
from datetime import datetime, timedelta
import asyncio
from contextlib import asynccontextmanager
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from pydantic import BaseModel
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

import models
import schemas
from database import engine, get_db

# Import scrapers
import scraper
import google_scraper
import fb_ads_scraper
import tiktok_ads_scraper
import youtube_scraper
import trustpilot_scraper
import reddit_scraper
import google_shopping_scraper
import pinterest_scraper
import cps_scraper

# Create database tables
models.Base.metadata.create_all(bind=engine)

# --- Scheduler Setup ---
scheduler = AsyncIOScheduler()

def log_channel_stats(channel: str, keywords: list, found: int, saved: int):
    """Log the performance metrics of a specific channel for analytics"""
    db_local = next(get_db())
    try:
        log = models.ScrapeLog(
            channel=channel,
            keyword=", ".join(keywords)[:200], # truncate just in case it's too long
            keywords_count=len(keywords),
            links_found=found,
            stores_saved=saved
        )
        db_local.add(log)
        db_local.commit()
    except Exception as e:
        print(f"Error logging channel stats: {e}")
    finally:
        db_local.close()

def check_and_run_automated_keywords():
    print("Running automated keyword scheduler check...")
    db = next(get_db())
    try:
        # Find keywords that are active and manual
        # We will only process a maximum of 2 keywords at a time to prevent crashing the server
        keywords = db.query(models.Keyword).filter(
            models.Keyword.is_active == True,
            models.Keyword.source == 'manual',
            models.Keyword.current_status != 'running'
        ).all()
        now = datetime.utcnow()
        
        due_keywords = []
        for kw in keywords:
            # If the keyword was just added (last_run_at is None) OR it's past its computed next_run_at
            if not kw.last_run_at:
                due_keywords.append(kw)
            elif kw.next_run_at and now >= kw.next_run_at:
                due_keywords.append(kw)
                
        # Sort by last_run_at to prioritize the oldest ones
        due_keywords.sort(key=lambda k: k.last_run_at if k.last_run_at else datetime.min)
        
        # Only take the first 2
        for kw in due_keywords[:2]:
            print(f"Triggering automated run for keyword: {kw.word}")
            # Create a task record
            db_task = models.Task(
                task_type="all_channels",
                parameters=json.dumps({"keywords": [kw.word]}),
                status="running",
                progress_text=f"Starting search for: {kw.word}..."
            )
            db.add(db_task)
            
            # Update keyword status
            kw.current_status = "running"
            kw.last_run_at = now
            
            # Compute the next run time based on interval
            if kw.schedule_interval == 'daily':
                kw.next_run_at = now + timedelta(days=1)
            elif kw.schedule_interval == 'weekly':
                kw.next_run_at = now + timedelta(days=7)
            elif kw.schedule_interval == 'monthly':
                kw.next_run_at = now + timedelta(days=30)
            else:
                kw.next_run_at = now + timedelta(days=7) # default fallback
                
            db.commit()
            db.refresh(db_task)
            
            # Ensure asyncio event loop handles it properly in APScheduler
            try:
                loop = asyncio.get_running_loop()
                loop.create_task(run_task_async(db_task.id, "all_channels", {"keywords": [kw.word]}))
            except RuntimeError:
                # If no running loop, we can't easily dispatch an async task from synchronous context
                # APScheduler normally runs these in threads if they are synchronous functions
                # Let's wrap it in a proper background task execution
                asyncio.run(run_task_async(db_task.id, "all_channels", {"keywords": [kw.word]}))
    except Exception as e:
        print(f"Scheduler error: {e}")
    finally:
        db.close()

def auto_expand_keywords():
    """Flywheel Step 1: Automatically expand keywords using AI"""
    print("Running automated keyword expansion...")
    db = next(get_db())
    try:
        # Create a task record to make this visible in the UI
        new_task = models.Task(
            task_type="ai_expand_keywords",
            status="running",
            parameters=json.dumps({"source": "auto_flywheel"}),
            progress_text="Starting AI keyword expansion..."
        )
        db.add(new_task)
        db.commit()
        db.refresh(new_task)
        
        try:
            # Find active manual keywords that haven't generated children or it's been a while
            # We want to expand random/different manual keywords each time, so we order by last_run_at or randomly
            # For simplicity, we can order by ID desc or randomly
            from sqlalchemy.sql.expression import func
            keywords = db.query(models.Keyword).filter(
                models.Keyword.is_active == True,
                models.Keyword.source == 'manual'
            ).order_by(func.random()).limit(5).all()
            
            if not keywords:
                new_task.status = "completed"
                new_task.progress_text = "No manual keywords found to expand."
                new_task.completed_at = datetime.utcnow()
                db.commit()
                return
                
            base_words = ", ".join([kw.word for kw in keywords])
            new_task.progress_text = f"Generating derivatives for: {base_words}"
            db.commit()
            
            # Call the existing logic (we simulate the request)
            from pydantic import BaseModel
            class DummyReq(BaseModel):
                base_keywords: str
                
            req = DummyReq(base_keywords=base_words)
            
            result = generate_keywords(req)
            new_words = result.get("keywords", "").split(", ")
            
            added = 0
            for w in new_words:
                w = w.strip().lower()
                if not w: continue
                # Check if exists
                existing = db.query(models.Keyword).filter(models.Keyword.word == w).first()
                if not existing:
                    new_kw = models.Keyword(
                        word=w,
                        schedule_interval="weekly",
                        source="ai_expanded",
                        parent_id=keywords[0].id # Assign to the first one as parent for tracking
                    )
                    db.add(new_kw)
                    added += 1
                    
            if added > 0:
                db.commit()
                new_task.items_saved = added
                new_task.result_summary = f"Expanded {added} new keywords. They will be scraped in the next cycle."
            else:
                new_task.result_summary = "No new unique keywords generated."
                
            new_task.status = "completed"
            new_task.progress_text = "Expansion finished."
            new_task.completed_at = datetime.utcnow()
            db.commit()
            
        except Exception as e:
            new_task.status = "error"
            new_task.progress_text = f"Error: {str(e)}"
            new_task.completed_at = datetime.utcnow()
            db.commit()
            print(f"Error during auto-expansion: {e}")
            
    finally:
        db.close()

def auto_scrape_contacts():
    """Flywheel Step 3: Automatically scrape contacts for pending stores"""
    print("Running automated contact scraping for pending stores...")
    db = next(get_db())
    try:
        # Check if there's already a running scrape_contacts task
        running_task = db.query(models.Task).filter(
            models.Task.task_type == "scrape_contacts",
            models.Task.status == "running"
        ).first()
        
        if running_task:
            print("Contact scraping task already running, skipping auto-trigger.")
            return
            
        # Count pending stores
        pending_count = db.query(models.Store).filter(models.Store.status == "pending").count()
        if pending_count > 0:
            print(f"Found {pending_count} pending stores. Starting contact scraper task...")
            new_task = models.Task(
                task_type="scrape_contacts",
                status="running",
                parameters=json.dumps({"source": "auto_flywheel"})
            )
            db.add(new_task)
            db.commit()
            db.refresh(new_task)
            
            # Kick off the background task
            try:
                loop = asyncio.get_running_loop()
                loop.create_task(run_task_async(new_task.id, "scrape_contacts", {"source": "auto_flywheel"}))
            except RuntimeError:
                asyncio.run(run_task_async(new_task.id, "scrape_contacts", {"source": "auto_flywheel"}))
    finally:
        db.close()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Add the flywheel jobs
    scheduler.add_job(auto_expand_keywords, 'interval', hours=24) # Step 1: Expand keywords daily
    scheduler.add_job(check_and_run_automated_keywords, 'interval', hours=6) # Step 2: Search for URLs (check more frequently)
    scheduler.add_job(auto_scrape_contacts, 'interval', hours=2) # Step 3: Extract contacts every 2 hours
    
    scheduler.start()
    yield
    # Shutdown scheduler
    scheduler.shutdown()

app = FastAPI(title="FastClaw API", description="API for Shopify store discovery and contact extraction", lifespan=lifespan)

# Configure CORS so Chrome extensions can access the API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.post("/api/stores", response_model=schemas.StoreResponse)
def create_store(store: schemas.StoreCreate, db: Session = Depends(get_db)):
    # Check if store already exists
    db_store = db.query(models.Store).filter(models.Store.url == store.url).first()
    if db_store:
        raise HTTPException(status_code=400, detail="Store URL already registered")
    
    new_store = models.Store(url=store.url, source=store.source)
    db.add(new_store)
    db.commit()
    db.refresh(new_store)
    return new_store

class KeywordGenerateRequest(BaseModel):
    base_keywords: str

class KeywordExtractRequest(BaseModel):
    text: str

@app.post("/api/system/run_scheduler")
def force_run_scheduler(background_tasks: BackgroundTasks):
    """Manually trigger the scheduler tasks for testing/immediate execution"""
    # Use background_tasks so the API returns immediately, but wrap them so async execution works
    def run_sync_wrappers():
        # Important: Order matters. 
        # Expand keywords first so new keywords are immediately available to be scraped
        auto_expand_keywords()
        
        # When forcefully triggering, we might want to bypass the schedule interval
        # so let's pass a flag or just force run a few active ones that aren't already running
        db_local = next(get_db())
        try:
            keywords = db_local.query(models.Keyword).filter(
                models.Keyword.is_active == True,
                models.Keyword.source == 'manual',  # Only run manual keywords for the top-level tasks
                models.Keyword.current_status != 'running'
            ).order_by(models.Keyword.last_run_at.asc().nulls_first()).limit(2).all()
            
            now = datetime.utcnow()
            for kw in keywords:
                print(f"Triggering forced automated run for keyword: {kw.word}")
                
                db_task = models.Task(
                    task_type="all_channels",
                    parameters=json.dumps({"keywords": [kw.word]}),
                    status="running",
                    progress_text=f"Starting search for: {kw.word}..."
                )
                db_local.add(db_task)
                
                kw.current_status = "running"
                kw.last_run_at = now
                
                if kw.schedule_interval == 'daily':
                    kw.next_run_at = now + timedelta(days=1)
                elif kw.schedule_interval == 'weekly':
                    kw.next_run_at = now + timedelta(days=7)
                elif kw.schedule_interval == 'monthly':
                    kw.next_run_at = now + timedelta(days=30)
                else:
                    kw.next_run_at = now + timedelta(days=7)
                    
                db_local.commit()
                db_local.refresh(db_task)
                
                try:
                    loop = asyncio.get_running_loop()
                    loop.create_task(run_task_async(db_task.id, "all_channels", {"keywords": [kw.word]}))
                except RuntimeError:
                    asyncio.run(run_task_async(db_task.id, "all_channels", {"keywords": [kw.word]}))
        finally:
            db_local.close()
            
        auto_scrape_contacts()
        
    background_tasks.add_task(run_sync_wrappers)
    return {"message": "All automation tasks have been triggered in the background"}

@app.post("/api/generate_keywords")
def generate_keywords(req: KeywordGenerateRequest):
    api_key = os.environ.get("MOONSHOT_API_KEY")
    if not api_key:
        raise HTTPException(status_code=400, detail="未配置 MOONSHOT_API_KEY，请在后端 .env 文件中设置。")
    
    from openai import OpenAI
    client = OpenAI(
        api_key=api_key,
        base_url="https://api.moonshot.cn/v1",
    )
    
    prompt = f"""
基于以下提供的一组基础关键词，请针对其中的**每一个**基础关键词，分别生成 50 个相关的高质量衍生关键词或长尾词（用于电商/独立站网页的搜索抓取）。

必须返回严格的 JSON 格式数据，结构如下：
{{
  "keywords": ["word1", "word2", "word3", ...]
}}

要求：
1. 必须针对输入的每一个词都进行发散，生成相关词汇。
2. 绝对不要包含任何解释性文字，不要使用 Markdown 代码块（如 ```json ），只返回纯 JSON 字符串。
3. **所有生成的衍生关键词必须全部是英文（English）**，不要输出中文或其他语言。
4. 所有的衍生词需要合并成一个扁平的数组放在 "keywords" 键下，不要按照原关键词进行嵌套或分组。

基础关键词：{req.base_keywords}
"""
    
    try:
        response = client.chat.completions.create(
            model="moonshot-v1-32k",
            messages=[
                {"role": "system", "content": "你是一个专业的电商独立站分析专家和SEO专家。你只会输出合法的JSON格式数据。"},
                {"role": "user", "content": prompt}
            ],
            response_format={"type": "json_object"},
            temperature=0.7,
        )
        result_text = response.choices[0].message.content
        
        # Clean up any potential markdown code blocks the AI might still add
        if result_text.startswith("```"):
            # Remove the first line (e.g. ```json)
            result_text = result_text.split('\n', 1)[-1]
        if result_text.endswith("```"):
            result_text = result_text.rsplit('\n', 1)[0]
            
        try:
            parsed_result = json.loads(result_text)
            
            # Handle case where AI might still nest by category despite instructions
            keywords_list = []
            if isinstance(parsed_result, dict):
                if "keywords" in parsed_result:
                    data = parsed_result["keywords"]
                    if isinstance(data, list):
                        keywords_list = data
                    elif isinstance(data, dict):
                        for k, v in data.items():
                            if isinstance(v, list):
                                keywords_list.extend(v)
                else:
                    # If it returned {"Category": ["word1", ...]}
                    for k, v in parsed_result.items():
                        if isinstance(v, list):
                            keywords_list.extend(v)
            elif isinstance(parsed_result, list):
                keywords_list = parsed_result
                            
            clean_str = ", ".join(str(w).strip() for w in keywords_list if str(w).strip())
            return {"keywords": clean_str}
        except json.JSONDecodeError:
            import re
            words = re.findall(r'"([^"]+)"', result_text)
            if words and len(words) > 1: # > 1 because "keywords" might be the first word
                if words[0].lower() == "keywords":
                    words = words[1:]
                return {"keywords": ", ".join(words)}
            return {"keywords": result_text.replace('\n', ' ').strip()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/extract_keywords")
def extract_keywords_from_text(req: KeywordExtractRequest):
    api_key = os.environ.get("MOONSHOT_API_KEY")
    if not api_key:
        raise HTTPException(status_code=400, detail="未配置 MOONSHOT_API_KEY")
    
    from openai import OpenAI
    client = OpenAI(
        api_key=api_key,
        base_url="https://api.moonshot.cn/v1",
    )
    
    prompt = f"""
基于以下提供的网站标题和描述，提取出3-5个最能代表其核心产品或品类的高质量英语关键词。
必须返回严格的 JSON 格式数据，结构如下：
{{
  "keywords": ["word1", "word2", "word3"]
}}
要求：
1. 关键词必须是英文（English）。
2. 只提取名词性的产品类别词（如 "running shoes", "wooden desk"），不要带有修饰语的整句。
3. 绝对不要包含任何解释性文字。

网站文本内容：{req.text}
"""
    try:
        response = client.chat.completions.create(
            model="moonshot-v1-8k",
            messages=[
                {"role": "system", "content": "你是一个专业的电商独立站数据分析师。你只会输出合法的JSON格式数据。"},
                {"role": "user", "content": prompt}
            ],
            response_format={"type": "json_object"},
            temperature=0.3,
        )
        result_text = response.choices[0].message.content
        
        if result_text.startswith("```"):
            result_text = result_text.split('\n', 1)[-1]
        if result_text.endswith("```"):
            result_text = result_text.rsplit('\n', 1)[0]
            
        try:
            parsed_result = json.loads(result_text)
            keywords_list = parsed_result.get("keywords", [])
            return {"keywords": keywords_list}
        except json.JSONDecodeError:
            return {"keywords": []}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/stats/channels")
def get_channel_stats(db: Session = Depends(get_db)):
    """Get the performance efficiency metrics for each channel"""
    from sqlalchemy import func
    
    stats = db.query(
        models.ScrapeLog.channel, 
        func.sum(models.ScrapeLog.links_found).label('total_found'),
        func.sum(models.ScrapeLog.stores_saved).label('total_saved'),
        func.sum(models.ScrapeLog.keywords_count).label('total_keywords')
    ).group_by(models.ScrapeLog.channel).all()
    
    result = []
    for item in stats:
        channel = item[0]
        found = item[1] or 0
        saved = item[2] or 0
        kw_count = item[3] or 1
        
        efficiency = (saved / found * 100) if found > 0 else 0
        avg_per_kw = (found / kw_count) if kw_count > 0 else 0
        
        result.append({
            "channel": channel,
            "links_found": found,
            "stores_saved": saved,
            "efficiency": round(efficiency, 2),
            "avg_per_kw": round(avg_per_kw, 2)
        })
        
    # Sort by number of stores saved
    result.sort(key=lambda x: x['stores_saved'], reverse=True)
    return result

@app.get("/api/stores")
def get_stores(skip: int = 0, limit: int = 100, status: Optional[str] = None, db: Session = Depends(get_db)):
    query = db.query(models.Store)
    if status and status != 'all':
        query = query.filter(models.Store.status == status)
        
    total = query.count()
    stores = query.order_by(models.Store.id.desc()).offset(skip).limit(limit).all()
    
    # We need to manually convert because we are returning a dict now
    return {
        "total": total,
        "items": [
            {
                "id": s.id,
                "url": s.url,
                "source": s.source,
                "source_channel": s.source_channel,
                "status": s.status,
                "created_at": s.created_at,
                "contacts": [{"email": c.email, "phone": c.phone, "instagram": c.instagram, "facebook": c.facebook, "whatsapp": c.whatsapp} for c in s.contacts]
            } for s in stores
        ]
    }

from fastapi.responses import StreamingResponse
import io
import csv

@app.get("/api/stores/export")
def export_stores(status: Optional[str] = None, db: Session = Depends(get_db)):
    query = db.query(models.Store)
    if status and status != 'all':
        query = query.filter(models.Store.status == status)
        
    stores = query.order_by(models.Store.id.desc()).all()
    
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['ID', 'URL', 'Source', 'Status', 'Created At', 'Email', 'Phone', 'Instagram', 'Facebook', 'WhatsApp'])
    
    for s in stores:
        email = ''
        phone = ''
        ig = ''
        fb = ''
        wa = ''
        
        if s.contacts:
            c = s.contacts[0]
            email = c.email or ''
            phone = c.phone or ''
            ig = c.instagram or ''
            fb = c.facebook or ''
            wa = c.whatsapp or ''
            
        writer.writerow([
            s.id,
            s.url,
            s.source,
            s.status,
            s.created_at.strftime("%Y-%m-%d %H:%M:%S"),
            email,
            phone,
            ig,
            fb,
            wa
        ])
        
    output.seek(0)
    
    filename = f"stores_export_{status or 'all'}.csv"
    
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )

@app.delete("/api/stores/{store_id}")
def delete_store(store_id: int, db: Session = Depends(get_db)):
    store = db.query(models.Store).filter(models.Store.id == store_id).first()
    if not store:
        raise HTTPException(status_code=404, detail="Store not found")
    
    db.delete(store)
    db.commit()
    return {"message": "Store deleted successfully"}

# --- Keyword Management API ---

@app.post("/api/keywords", response_model=schemas.KeywordResponse)
def add_keyword(keyword: schemas.KeywordCreate, db: Session = Depends(get_db)):
    db_kw = db.query(models.Keyword).filter(models.Keyword.word == keyword.word).first()
    if db_kw:
        raise HTTPException(status_code=400, detail="Keyword already exists")
    
    # The database already has properties or logic to calculate next_run_at, 
    # but for manual addition we might want to default it to now
    new_kw = models.Keyword(
        word=keyword.word,
        schedule_interval=keyword.schedule_interval,
        source=keyword.source,
        parent_id=keyword.parent_id
    )
    db.add(new_kw)
    db.commit()
    db.refresh(new_kw)
    return new_kw

@app.get("/api/keywords", response_model=List[schemas.KeywordResponse])
def get_keywords(db: Session = Depends(get_db)):
    return db.query(models.Keyword).order_by(models.Keyword.created_at.desc()).all()

@app.delete("/api/keywords/{kw_id}")
def delete_keyword(kw_id: int, db: Session = Depends(get_db)):
    kw = db.query(models.Keyword).filter(models.Keyword.id == kw_id).first()
    if not kw:
        raise HTTPException(status_code=404, detail="Keyword not found")
    
    db.delete(kw)
    db.commit()
    return {"message": "Keyword deleted successfully"}

@app.put("/api/keywords/{kw_id}/toggle")
def toggle_keyword(kw_id: int, db: Session = Depends(get_db)):
    kw = db.query(models.Keyword).filter(models.Keyword.id == kw_id).first()
    if not kw:
        raise HTTPException(status_code=404, detail="Keyword not found")
    
    kw.is_active = not kw.is_active
    db.commit()
    return {"message": "Keyword toggled", "is_active": kw.is_active}

import contact_scraper

async def run_task_async(task_id: int, task_type: str, parameters: dict):
    db = next(get_db())
    task = db.query(models.Task).filter(models.Task.id == task_id).first()
    if not task:
        return
        
    # Helper to extract all keywords from parameters to update their status
    import re
    def get_all_keywords():
        kws = []
        if 'keywords' in parameters:
            kw_param = parameters['keywords']
            if isinstance(kw_param, str):
                kws.extend([k.strip() for k in re.split(r'[,，]', kw_param) if k.strip()])
            elif isinstance(kw_param, list):
                for k in kw_param:
                    if isinstance(k, str):
                        kws.extend([kx.strip() for kx in re.split(r'[,，]', k) if kx.strip()])
        return kws
        
    running_kws = get_all_keywords()
    if running_kws:
        db.query(models.Keyword).filter(models.Keyword.word.in_(running_kws)).update({"current_status": "running"}, synchronize_session=False)
        db.commit()
    db.close()
    
    def update_progress(keyword=None, found_delta=0, saved_delta=0, text=None):
        # Always fetch a fresh copy of the task to ensure we don't overwrite its status
        db_local = next(get_db())
        try:
            t = db_local.query(models.Task).filter(models.Task.id == task_id).first()
            if t:
                # If it was stopped, we shouldn't update progress anymore
                if t.status == "stopped":
                    print(f"[Task {task_id} Progress Update] Blocked: Task is STOPPED.")
                    return
                if keyword is not None:
                    t.current_keyword = keyword
                if found_delta:
                    t.items_found = (t.items_found or 0) + found_delta
                if saved_delta:
                    t.items_saved = (t.items_saved or 0) + saved_delta
                if text is not None:
                    t.progress_text = text
                
                print(f"[Task {task_id} Progress Update] Status: {t.status} | Found: {t.items_found} | Saved: {t.items_saved} | Text: '{text}'")
                db_local.commit()
            else:
                print(f"[Task {task_id} Progress Update] Failed: Task not found in DB.")
        finally:
            db_local.close()
    
    try:
        print(f"[Task {task_id} Execution] Entering main try block for task_type: {task_type}")
        if task_type == 'scrape_contacts':
            from contact_scraper import run_contact_scraping_task
            res = await run_contact_scraping_task(task_id=task_id, update_progress=update_progress)
            
            # Check if stopped mid-execution
            db_final = next(get_db())
            t_final = db_final.query(models.Task).filter(models.Task.id == task_id).first()
            if t_final and t_final.status == "stopped":
                db_final.close()
                return
                
            if res and t_final:
                t_final.result_summary = f"Processed {res.get('total_processed', 0)} stores. Found contacts for {res.get('found_contacts', 0)}."
            elif t_final:
                t_final.result_summary = "Contacts scraped successfully."
            if t_final:
                db_final.commit()
            db_final.close()
        elif task_type == 'google_search':
            queries = parameters.get('queries', [])
            max_pages = int(parameters.get('max_pages', 2))
            
            import re
            def split_keywords(kw_str):
                return [k.strip() for k in re.split(r'[,，]', kw_str) if k.strip()]
                
            if isinstance(queries, str):
                queries = split_keywords(queries)
            elif isinstance(queries, list) and len(queries) > 0 and isinstance(queries[0], str):
                flat_list = []
                for q in queries:
                    flat_list.extend(split_keywords(q))
                queries = flat_list
                
            # Allow direct keyword searches
            formatted_queries = queries
                
            res = await google_scraper.run_search(formatted_queries, max_pages=max_pages, update_progress=update_progress, task_id=task_id)
            db_final = next(get_db())
            t_final = db_final.query(models.Task).filter(models.Task.id == task_id).first()
            if t_final:
                if res:
                    t_final.result_summary = f"Found {res.get('total_found', 0)} domains, saved {res.get('saved', 0)} new stores."
                else:
                    t_final.result_summary = f"Google search completed for {len(queries)} queries."
                db_final.commit()
            db_final.close()
        elif task_type == 'fb_ads':
            keywords = parameters.get('keywords', [])
            
            import re
            def split_keywords(kw_str):
                return [k.strip() for k in re.split(r'[,，]', kw_str) if k.strip()]
            
            if isinstance(keywords, str):
                keywords = split_keywords(keywords)
            elif isinstance(keywords, list) and len(keywords) > 0 and isinstance(keywords[0], str):
                flat_list = []
                for k in keywords:
                    flat_list.extend(split_keywords(k))
                keywords = flat_list
                
            max_scrolls = int(parameters.get('max_scrolls', 3))
            max_pages = int(parameters.get('max_pages', 2))
            country = parameters.get('country', 'US')
            fb_token = parameters.get('fb_token', None)
            
            res = await fb_ads_scraper.extract_links_from_ad_library(
                keywords, 
                max_scrolls=max_scrolls, 
                max_pages=max_pages,
                country=country,
                fb_token=fb_token,
                update_progress=update_progress
            )
            
            db_final = next(get_db())
            t_final = db_final.query(models.Task).filter(models.Task.id == task_id).first()
            if t_final:
                if res:
                    t_final.result_summary = f"Found {res.get('total_found', 0)} links, verified & saved {res.get('saved', 0)} Shopify stores."
                else:
                    t_final.result_summary = f"FB Ads scraped for {len(keywords)} keywords."
                db_final.commit()
            db_final.close()
        elif task_type == 'tiktok_ads':
            keywords = parameters.get('keywords', [])
            country = parameters.get('country', 'US')
            
            import re
            def split_keywords(kw_str):
                return [k.strip() for k in re.split(r'[,，]', kw_str) if k.strip()]
                
            if isinstance(keywords, str):
                keywords = split_keywords(keywords)
            elif isinstance(keywords, list) and len(keywords) > 0 and isinstance(keywords[0], str):
                flat_list = []
                for k in keywords:
                    flat_list.extend(split_keywords(k))
                keywords = flat_list
                
            max_scrolls = int(parameters.get('max_scrolls', 3))
            res = await tiktok_ads_scraper.extract_links_from_tiktok_ads(keywords, country=country, max_scrolls=max_scrolls, update_progress=update_progress)
            db_final = next(get_db())
            t_final = db_final.query(models.Task).filter(models.Task.id == task_id).first()
            if t_final:
                if res:
                    t_final.result_summary = f"Found {res.get('total_found', 0)} links, verified & saved {res.get('saved', 0)} Shopify stores."
                else:
                    t_final.result_summary = f"TikTok Ads scraped for {len(keywords)} keywords."
                db_final.commit()
            db_final.close()
        elif task_type == 'all_channels':
            keywords = parameters.get('keywords', [])
            
            import re
            def split_keywords(kw_str):
                return [k.strip() for k in re.split(r'[,，]', kw_str) if k.strip()]
            
            if isinstance(keywords, str):
                keywords = split_keywords(keywords)
            elif isinstance(keywords, list) and len(keywords) > 0 and isinstance(keywords[0], str):
                flat_list = []
                for k in keywords:
                    flat_list.extend(split_keywords(k))
                keywords = flat_list

            max_scrolls = int(parameters.get('max_scrolls', 3))
            max_pages = int(parameters.get('max_pages', 2))
            country = parameters.get('country', 'US')
            fb_token = parameters.get('fb_token', None)
            
            total_found = 0
            total_saved = 0
            
            # 1. Web Search (via Yahoo)
            # Users want to search directly by keywords without the site:myshopify.com restriction
            search_queries = keywords
            
            # Check if stopped
            db_final = next(get_db())
            t_final = db_final.query(models.Task).filter(models.Task.id == task_id).first()
            if t_final and t_final.status == "stopped":
                db_final.close()
                return
            db_final.close()
                
            res_google = await google_scraper.run_search(search_queries, max_pages=max_pages, update_progress=update_progress, task_id=task_id)
            if res_google:
                total_found += res_google.get('total_found', 0)
                total_saved += res_google.get('saved', 0)
                log_channel_stats("yahoo", keywords, res_google.get('total_found', 0), res_google.get('saved', 0))
                
            # Temporarily disabled due to heavy anti-bot CAPTCHA
            # res_gshop = await google_shopping_scraper.extract_links_from_google_shopping(keywords, max_pages=3, update_progress=update_progress, task_id=task_id)
            # if res_gshop:
            #     total_found += res_gshop.get('total_found', 0)
            #     total_saved += res_gshop.get('saved', 0)
            #     log_channel_stats("google_shopping", keywords, res_gshop.get('total_found', 0), res_gshop.get('saved', 0))
                
            res_pin = await pinterest_scraper.extract_links_from_pinterest(keywords, max_scrolls=15, update_progress=update_progress, task_id=task_id)
            if res_pin:
                total_found += res_pin.get('total_found', 0)
                total_saved += res_pin.get('saved', 0)
                log_channel_stats("pinterest", keywords, res_pin.get('total_found', 0), res_pin.get('saved', 0))

            update_progress(text="Starting CPS Networks Search...")
            res_cps = await cps_scraper.extract_links_from_cps_networks(keywords, max_pages=3, update_progress=update_progress, task_id=task_id)
            if res_cps:
                total_found += res_cps.get('total_found', 0)
                total_saved += res_cps.get('saved', 0)
                log_channel_stats("cps", keywords, res_cps.get('total_found', 0), res_cps.get('saved', 0))

            update_progress(text="Starting FB Ads Search...")
            # 2. FB Ads
            db_final = next(get_db())
            t_final = db_final.query(models.Task).filter(models.Task.id == task_id).first()
            if t_final and t_final.status == "stopped":
                db_final.close()
                return
            db_final.close()
                
            res_fb = await fb_ads_scraper.extract_links_from_ad_library(
                keywords, 
                max_scrolls=max_scrolls, 
                max_pages=max_pages,
                country=country,
                fb_token=fb_token,
                update_progress=update_progress
            )
            if res_fb:
                total_found += res_fb.get('total_found', 0)
                total_saved += res_fb.get('saved', 0)
                log_channel_stats("fb_ads", keywords, res_fb.get('total_found', 0), res_fb.get('saved', 0))
                
            # 3. TikTok Ads
            db_final = next(get_db())
            t_final = db_final.query(models.Task).filter(models.Task.id == task_id).first()
            if t_final and t_final.status == "stopped":
                db_final.close()
                return
            db_final.close()
                
            res_tiktok = await tiktok_ads_scraper.extract_links_from_tiktok_ads(keywords, country=country, max_scrolls=max_scrolls, update_progress=update_progress)
            if res_tiktok:
                total_found += res_tiktok.get('total_found', 0)
                total_saved += res_tiktok.get('saved', 0)
                log_channel_stats("tiktok_ads", keywords, res_tiktok.get('total_found', 0), res_tiktok.get('saved', 0))
                
            # 4. YouTube Search
            db_final = next(get_db())
            t_final = db_final.query(models.Task).filter(models.Task.id == task_id).first()
            if t_final and t_final.status == "stopped":
                db_final.close()
                return
            db_final.close()
            
            # For YouTube, we append "review" or "unboxing" to keywords to get better product videos
            yt_keywords = [f"{kw} review" for kw in keywords]
            res_yt = await youtube_scraper.extract_links_from_youtube(yt_keywords, max_results_per_keyword=10, update_progress=update_progress, task_id=task_id)
            if res_yt:
                total_found += res_yt.get('total_found', 0)
                total_saved += res_yt.get('saved', 0)
                log_channel_stats("youtube", keywords, res_yt.get('total_found', 0), res_yt.get('saved', 0))
                
            # 5. Trustpilot Search
            db_final = next(get_db())
            t_final = db_final.query(models.Task).filter(models.Task.id == task_id).first()
            if t_final and t_final.status == "stopped":
                db_final.close()
                return
            db_final.close()
            
            res_tp = await trustpilot_scraper.extract_links_from_trustpilot(keywords, max_pages=max_pages, update_progress=update_progress, task_id=task_id)
            if res_tp:
                total_found += res_tp.get('total_found', 0)
                total_saved += res_tp.get('saved', 0)
                log_channel_stats("trustpilot", keywords, res_tp.get('total_found', 0), res_tp.get('saved', 0))
                
            # 6. Reddit Search
            db_final = next(get_db())
            t_final = db_final.query(models.Task).filter(models.Task.id == task_id).first()
            if t_final and t_final.status == "stopped":
                db_final.close()
                return
            db_final.close()
            
            # Using specific queries for Reddit to find e-commerce stores
            # reddit_keywords = [f"review my store {kw}" for kw in keywords]
            # res_reddit = await reddit_scraper.extract_links_from_reddit(keywords, max_posts=50, update_progress=update_progress, task_id=task_id)
            # if res_reddit:
            #     total_found += res_reddit.get('total_found', 0)
            #     total_saved += res_reddit.get('saved', 0)
            #     log_channel_stats("reddit", keywords, res_reddit.get('total_found', 0), res_reddit.get('saved', 0))
                
            db_final = next(get_db())
            t_final = db_final.query(models.Task).filter(models.Task.id == task_id).first()
            if t_final:
                t_final.result_summary = f"All Channels: Found {total_found} links, saved {total_saved} Shopify stores."
                db_final.commit()
            db_final.close()
        else:
            db_final = next(get_db())
            t_final = db_final.query(models.Task).filter(models.Task.id == task_id).first()
            if t_final:
                t_final.result_summary = "Unknown task type."
                t_final.status = "failed"
                db_final.commit()
            db_final.close()
            
        db_final = next(get_db())
        t_final = db_final.query(models.Task).filter(models.Task.id == task_id).first()
        
        target_status_for_keywords = "idle"
        
        if t_final and t_final.status != "failed" and t_final.status != "stopped":
            print(f"[Task {task_id} Completion] Marking task as completed successfully.")
            t_final.status = "completed"
            t_final.completed_at = datetime.utcnow()
            
            # Check if we should block the keyword due to high false positives
            if task_type == 'all_channels' and total_found > 10 and total_saved == 0:
                print(f"[Task {task_id} Optimization] Keyword yielded {total_found} links but 0 saves. Blocking keyword to prevent wasted resources.")
                target_status_for_keywords = "blocked"
                t_final.result_summary += " (Keywords blocked due to 0 saves)"
                
            db_final.commit()
            
            # Update keyword statuses based on outcome
            if running_kws:
                db_final.query(models.Keyword).filter(models.Keyword.word.in_(running_kws)).update({"current_status": target_status_for_keywords}, synchronize_session=False)
                db_final.commit()
        elif t_final:
            print(f"[Task {task_id} Completion] Skipped marking completed because status is {t_final.status}")
        db_final.close()
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"[Task {task_id} Error] Exception caught: {str(e)}")
        db_final = next(get_db())
        t_final = db_final.query(models.Task).filter(models.Task.id == task_id).first()
        if t_final and t_final.status != "stopped":
            t_final.status = "error"
            t_final.progress_text = f"Error: {str(e)}"
            t_final.result_summary = f"Error: {str(e)}"
            t_final.completed_at = datetime.utcnow()
            db_final.commit()
        db_final.close()
    finally:
        # Set back to idle if it wasn't handled (e.g. error occurred or status was stopped)
        if running_kws:
            db_final = next(get_db())
            # Only reset to idle if they are still stuck in 'running' (don't overwrite 'blocked')
            kws = db_final.query(models.Keyword).filter(models.Keyword.word.in_(running_kws), models.Keyword.current_status == 'running').all()
            for kw in kws:
                kw.current_status = 'idle'
            db_final.commit()
            db_final.close()
        db.close()

def run_task_in_background(task_id: int, task_type: str, parameters: dict):
    # Wrapper for FastAPI BackgroundTasks which run in threadpool
    asyncio.run(run_task_async(task_id, task_type, parameters))

@app.post("/api/tasks", response_model=schemas.TaskResponse)
def create_task(task_in: schemas.TaskCreate, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    db_task = models.Task(
        task_type=task_in.task_type,
        parameters=json.dumps(task_in.parameters) if task_in.parameters else None,
        status="running"
    )
    db.add(db_task)
    db.commit()
    db.refresh(db_task)
    
    background_tasks.add_task(
        run_task_in_background, 
        task_id=db_task.id, 
        task_type=task_in.task_type, 
        parameters=task_in.parameters or {}
    )
    
    return db_task

@app.get("/api/tasks", response_model=List[schemas.TaskResponse])
def get_tasks(limit: int = 20, db: Session = Depends(get_db)):
    return db.query(models.Task).order_by(models.Task.created_at.desc()).limit(limit).all()

@app.delete("/api/tasks/{task_id}")
def delete_task(task_id: int, db: Session = Depends(get_db)):
    task = db.query(models.Task).filter(models.Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
        
    # If the task is associated with any keywords, we should mark them as idle when deleting
    if task.task_type == "all_channels" and task.parameters:
        try:
            import json
            import re
            params = json.loads(task.parameters)
            kws = []
            if 'keywords' in params:
                kw_param = params['keywords']
                if isinstance(kw_param, str):
                    kws.extend([k.strip() for k in re.split(r'[,，]', kw_param) if k.strip()])
                elif isinstance(kw_param, list):
                    for k in kw_param:
                        if isinstance(k, str):
                            kws.extend([kx.strip() for kx in re.split(r'[,，]', k) if kx.strip()])
            
            if kws:
                db.query(models.Keyword).filter(models.Keyword.word.in_(kws)).update({"current_status": "idle"}, synchronize_session=False)
        except Exception:
            pass
    
    db.delete(task)
    db.commit()
    return {"message": "Task deleted successfully"}

@app.post("/api/tasks/{task_id}/stop")
def stop_task(task_id: int, db: Session = Depends(get_db)):
    task = db.query(models.Task).filter(models.Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    if task.status == "running":
        task.status = "stopped"
        task.progress_text = "Task was manually stopped by user."
        task.completed_at = datetime.utcnow()
        db.commit()
        return {"message": "Task marked as stopped"}
    else:
        return {"message": "Task is not running"}

@app.post("/api/tasks/{task_id}/restart")
def restart_task(task_id: int, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    task = db.query(models.Task).filter(models.Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
        
    # ai_expand_keywords tasks are not long-running async tasks, they run synchronously in a single shot
    if task.task_type == "ai_expand_keywords":
        # Delete the old failed task and trigger a new one via the auto_expand function
        db.delete(task)
        db.commit()
        # Add to background to run immediately
        background_tasks.add_task(auto_expand_keywords)
        return {"message": "AI Expansion task triggered successfully"}
    
    # Reset task state for standard scraper tasks
    task.status = "running"
    task.items_found = 0
    task.items_saved = 0
    task.progress_text = "Task restarted..."
    task.completed_at = None
    task.result_summary = None
    db.commit()
    
    # Parse parameters
    params = {}
    if task.parameters:
        try:
            params = json.loads(task.parameters)
        except:
            pass
            
    # Restart background job using the correct background task wrapper
    background_tasks.add_task(
        run_task_in_background,
        task_id=task.id,
        task_type=task.task_type,
        parameters=params
    )
        
    return {"message": "Task restarted successfully"}

@app.get("/")
def read_root():
    return {"message": "Welcome to FastClaw API"}
