import asyncio
import re
from urllib.parse import urlparse, urljoin
from playwright.async_api import async_playwright
import httpx
from bs4 import BeautifulSoup
from sqlalchemy.orm import Session
import models
from database import SessionLocal

EMAIL_REGEX = r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}"
# Phone regex: matches formats like 1-817-831-5482, (817) 831-5482, 817-831-5482, +1 817 831 5482, 800-345-5273
PHONE_REGEX = r"(?i)(?:call|phone)?\s*?(\b(?:\+?1[-.\s]?)?\(?[0-9]{3}\)?[-.\s]?[0-9]{3}[-.\s]?[0-9]{4}\b)"

def is_valid_phone(phone_str: str) -> bool:
    digits = re.sub(r'\D', '', phone_str)
    if len(digits) < 10 or len(digits) > 11:
        return False
    if digits.startswith('000') or digits.startswith('12345'):
        return False
    # check if it looks like a timestamp/random id rather than phone
    if len(digits) == 10 and (digits.startswith('17') or digits.startswith('16') or digits.startswith('15') or digits.startswith('14') or digits.startswith('803')):
        # Too many false positives with timestamps and random JS ids, we skip purely numeric 10-digit ones starting with these if they lack formatting
        if not re.search(r'[-.()]', phone_str):
            return False
    # Filter out common zip codes or generic numbers matched by accident
    if len(digits) == 10 and digits.endswith('0000'):
        if not re.search(r'[-.()]', phone_str) and "800" not in phone_str:
            return False
            
    # additional block to prevent matching unix timestamps with dot separators like 803717.1774
    if re.match(r'^\d{6}\.\d{4}$', phone_str):
        return False
        
    return True

async def find_contact_pages(url: str, html: str) -> set:
    soup = BeautifulSoup(html, "html.parser")
    links = set()
    # Looking for contact, about, support, and refund/return policies
    keywords = ['contact', 'about', 'support', 'refund', 'return', 'policy', 'terms']
    for a in soup.find_all("a", href=True):
        href = a["href"].lower()
        text = a.get_text().lower()
        
        if any(k in href for k in keywords) or any(k in text for k in keywords):
            full_url = urljoin(url, a["href"])
            parsed_full = urlparse(full_url)
            parsed_base = urlparse(url)
            if parsed_full.netloc == parsed_base.netloc:
                links.add(full_url)
    return links

def extract_social_links(html: str) -> dict:
    soup = BeautifulSoup(html, "html.parser")
    socials = {"instagram": None, "facebook": None, "whatsapp": None}
    
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if "instagram.com" in href and not socials["instagram"]:
            socials["instagram"] = href
        elif "facebook.com" in href and not socials["facebook"] and "sharer" not in href:
            socials["facebook"] = href
        elif "wa.me" in href or "api.whatsapp.com" in href and not socials["whatsapp"]:
            socials["whatsapp"] = href
            
    return socials

async def scrape_store_contacts(store_url: str) -> dict:
    result = {
        "emails": set(),
        "phones": set(),
        "socials": {"instagram": None, "facebook": None, "whatsapp": None}
    }
    try:
        if not store_url.startswith("http"): store_url = "https://" + store_url
        
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
                viewport={"width": 1280, "height": 800}
            )
            
            # Fetch homepage
            try:
                await page.goto(store_url, wait_until="domcontentloaded", timeout=20000)
                # Wait a bit for cloudflare to potentially clear
                await page.wait_for_timeout(3000)
                html = await page.content()
            except Exception as e:
                print(f"Error loading {store_url}: {e}")
                await browser.close()
                return result
                
            # Let's save the product title and description if requested
            # We can run AI extraction on this later or immediately
            try:
                title = await page.title()
                meta_desc_element = await page.query_selector('meta[name="description"]')
                meta_desc = await meta_desc_element.get_attribute('content') if meta_desc_element else ""
                
                # We could directly send this to an AI queue here
                # For now, let's just save it. The flywheel will pick it up
                result["title"] = title
                result["meta_desc"] = meta_desc
            except Exception as e:
                pass
                
            result["emails"].update(re.findall(EMAIL_REGEX, html))
            
            # Extract phones
            for match in re.finditer(PHONE_REGEX, html):
                phone_str = match.group(1).strip() if match.group(1) else match.group(0).strip()
                if is_valid_phone(phone_str):
                    result["phones"].add(phone_str)
                    
            if not result["phones"]:
                # Try getting plain text to avoid html tags breaking phone numbers
                text = BeautifulSoup(html, "html.parser").get_text(separator=' ')
                for match in re.finditer(r'(?i)(?:call|phone)?\s*?(\b(?:\+?1[-.\s]?)?\(?[0-9]{3}\)?[-.\s]?[0-9]{3}[-.\s]?[0-9]{4}\b)', text):
                    phone_str = match.group(1).strip() if match.group(1) else match.group(0).strip()
                    if is_valid_phone(phone_str):
                        result["phones"].add(phone_str)
                    
            # Check for alternative phone formats like 1-800-XXX-XXXX without parens
            for match in re.finditer(r'(?:Call|Phone)?\s*(\b(?:\+?1[-.\s]?)?[2-9]\d{2}[-.\s]\d{3}[-.\s]\d{4}\b)', html, re.IGNORECASE):
                phone_str = match.group(1).strip()
                if is_valid_phone(phone_str):
                    result["phones"].add(phone_str)
                    
            # Check for generic formats
            for match in re.finditer(r'1-[0-9]{3}-[0-9]{3}-[0-9]{4}', html):
                phone_str = match.group(0).strip()
                if is_valid_phone(phone_str):
                    result["phones"].add(phone_str)
                    
            # Super generic phone match as fallback for 1-800 numbers in text
            if not result["phones"]:
                for match in re.finditer(r'\b1-8[0-9]{2}-?[0-9]{3}-?[0-9]{4}\b', html):
                     phone = match.group(0).strip()
                     if is_valid_phone(phone):
                         result["phones"].add(phone)
                     
            if not result["phones"]:
                # Try to extract phone from "tel:" links
                for match in re.finditer(r'href=["\']tel:([^"\']+)["\']', html):
                     phone = match.group(1).strip()
                     if is_valid_phone(phone):
                         result["phones"].add(phone)
                         
            # Try plain text search for specific keywords near numbers
            if not result["phones"]:
                for match in re.finditer(r'(?i)(?:call(?:ing)?(?:\s*us)?(?: at)?\s*|customer\s*service:?\s*)([0-9]{1,3}[-.\s]?[0-9]{3}[-.\s]?[0-9]{4})', html):
                     phone = match.group(1).strip()
                     if is_valid_phone(phone):
                         result["phones"].add(phone)
                         
            if not result["phones"]:
                # Try finding any 10-digit number that starts with 8
                for match in re.finditer(r'\b8[0-9]{2}[-.\s]*[0-9]{3}[-.\s]*[0-9]{4}\b', html):
                     phone = match.group(0).strip()
                     if is_valid_phone(phone):
                         result["phones"].add(phone)
                         
            if not result["phones"]:
                # Look for general pattern like XXX-XXX-XXXX
                for match in re.finditer(r'(?<!\d)[2-9][0-9]{2}[-.\s][0-9]{3}[-.\s][0-9]{4}(?!\d)', html):
                     phone = match.group(0).strip()
                     if is_valid_phone(phone):
                         result["phones"].add(phone)
                         
            if not result["phones"]:
                # Try finding just 10 digits that are clustered together
                for match in re.finditer(r'\b1[-.\s]*[2-9]\d{2}[-.\s]*\d{3}[-.\s]*\d{4}\b', html):
                     phone = match.group(0).strip()
                     if is_valid_phone(phone):
                         result["phones"].add(phone)
                         
            if not result["phones"]:
                # Try finding any 10-11 digit numbers with formatting
                for match in re.finditer(r'(?:(?:\+?1\s*(?:[.-]\s*)?)?(?:\(\s*([2-9]1[02-9]|[2-9][02-8]1|[2-9][02-8][02-9])\s*\)|([2-9]1[02-9]|[2-9][02-8]1|[2-9][02-8][02-9]))\s*(?:[.-]\s*)?)?([2-9]1[02-9]|[2-9][02-9]1|[2-9][02-9]{2})\s*(?:[.-]\s*)?([0-9]{4})', html):
                     phone = match.group(0).strip()
                     if is_valid_phone(phone):
                         result["phones"].add(phone)
                     
            if not result["phones"]:
                # Try plain text with just a general phone format
                for match in re.finditer(r'(?<!\d)(?:[2-9]\d{2}[-.\s]\d{3}[-.\s]\d{4})(?!\d)', html):
                     phone = match.group(0).strip()
                     if is_valid_phone(phone):
                         result["phones"].add(phone)
            
            socials = extract_social_links(html)
            for k, v in socials.items():
                if v and not result["socials"][k]: result["socials"][k] = v
                    
            contact_pages = await find_contact_pages(store_url, html)
            # Increase limit slightly to allow checking refund/policy pages too
            for page_url in list(contact_pages)[:5]:
                try:
                    await page.goto(page_url, wait_until="domcontentloaded", timeout=15000)
                    await page.wait_for_timeout(2000)
                    c_html = await page.content()
                    
                    result["emails"].update(re.findall(EMAIL_REGEX, c_html))
                    
                    # Extract phones
                    for match in re.finditer(PHONE_REGEX, c_html):
                        phone_str = match.group(1).strip() if match.group(1) else match.group(0).strip()
                        if is_valid_phone(phone_str):
                            result["phones"].add(phone_str)
                            
                    if not result["phones"]:
                        text = BeautifulSoup(c_html, "html.parser").get_text(separator=' ')
                        for match in re.finditer(r'(?i)(?:call|phone)?\s*?(\b(?:\+?1[-.\s]?)?\(?[0-9]{3}\)?[-.\s]?[0-9]{3}[-.\s]?[0-9]{4}\b)', text):
                            phone_str = match.group(1).strip() if match.group(1) else match.group(0).strip()
                            if is_valid_phone(phone_str):
                                result["phones"].add(phone_str)
                            
                    for match in re.finditer(r'(?:Call|Phone)?\s*(\b(?:\+?1[-.\s]?)?[2-9]\d{2}[-.\s]\d{3}[-.\s]\d{4}\b)', c_html, re.IGNORECASE):
                        phone_str = match.group(1).strip()
                        if is_valid_phone(phone_str):
                            result["phones"].add(phone_str)
                            
                    for match in re.finditer(r'1-[0-9]{3}-[0-9]{3}-[0-9]{4}', c_html):
                        phone_str = match.group(0).strip()
                        if is_valid_phone(phone_str):
                            result["phones"].add(phone_str)
                            
                    # Super generic phone match as fallback for 1-800 numbers in text
                    if not result["phones"]:
                        for match in re.finditer(r'\b1-8[0-9]{2}-?[0-9]{3}-?[0-9]{4}\b', c_html):
                             phone = match.group(0).strip()
                             if is_valid_phone(phone):
                                 result["phones"].add(phone)
                             
                    if not result["phones"]:
                        # Try to extract phone from "tel:" links
                        for match in re.finditer(r'href=["\']tel:([^"\']+)["\']', c_html):
                             phone = match.group(1).strip()
                             if is_valid_phone(phone):
                                 result["phones"].add(phone)
                                 
                    # Try plain text search for specific keywords near numbers
                    if not result["phones"]:
                        for match in re.finditer(r'(?i)(?:call(?:ing)?(?:\s*us)?(?: at)?\s*|customer\s*service:?\s*)([0-9]{1,3}[-.\s]?[0-9]{3}[-.\s]?[0-9]{4})', c_html):
                             phone = match.group(1).strip()
                             if is_valid_phone(phone):
                                 result["phones"].add(phone)
                                 
                    if not result["phones"]:
                        for match in re.finditer(r'\b8[0-9]{2}[-.\s]*[0-9]{3}[-.\s]*[0-9]{4}\b', c_html):
                             phone = match.group(0).strip()
                             if is_valid_phone(phone):
                                 result["phones"].add(phone)
                                 
                    if not result["phones"]:
                        for match in re.finditer(r'(?<!\d)[2-9][0-9]{2}[-.\s][0-9]{3}[-.\s][0-9]{4}(?!\d)', c_html):
                             phone = match.group(0).strip()
                             if is_valid_phone(phone):
                                 result["phones"].add(phone)
                                 
                    if not result["phones"]:
                        for match in re.finditer(r'\b1[-.\s]*[2-9]\d{2}[-.\s]*\d{3}[-.\s]*\d{4}\b', c_html):
                             phone = match.group(0).strip()
                             if is_valid_phone(phone):
                                 result["phones"].add(phone)
                                 
                    if not result["phones"]:
                        for match in re.finditer(r'(?:(?:\+?1\s*(?:[.-]\s*)?)?(?:\(\s*([2-9]1[02-9]|[2-9][02-8]1|[2-9][02-8][02-9])\s*\)|([2-9]1[02-9]|[2-9][02-8]1|[2-9][02-8][02-9]))\s*(?:[.-]\s*)?)?([2-9]1[02-9]|[2-9][02-9]1|[2-9][02-9]{2})\s*(?:[.-]\s*)?([0-9]{4})', c_html):
                             phone = match.group(0).strip()
                             if is_valid_phone(phone):
                                 result["phones"].add(phone)
                             
                    if not result["phones"]:
                        # Try plain text with just a general phone format
                        for match in re.finditer(r'(?<!\d)(?:[2-9]\d{2}[-.\s]\d{3}[-.\s]\d{4})(?!\d)', c_html):
                             phone = match.group(0).strip()
                             if is_valid_phone(phone):
                                 result["phones"].add(phone)
                                
                    c_socials = extract_social_links(c_html)
                    for k, v in c_socials.items():
                        if v and not result["socials"][k]: result["socials"][k] = v
                except Exception:
                    pass
                    
            await browser.close()
            
    except Exception as e:
        print(f"Playwright error for {store_url}: {e}")
        
    clean_emails = set()
    for e in result["emails"]:
        if not e.endswith((".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", ".wix", ".js", ".css")):
            if e.split("@")[0] not in ["sentry", "sentry-io"]:
                clean_emails.add(e)
    result["emails"] = list(clean_emails)
    clean_phones = set()
    for p in result["phones"]:
        # double check the phone isn't a false positive timestamp
        if is_valid_phone(p):
            clean_phones.add(p)
            
    result["phones"] = list(clean_phones)
    return result

async def run_contact_scraping_task(task_id=None, store_ids=None, update_progress=None):
    db: Session = SessionLocal()
    
    if task_id:
        task = db.query(models.Task).filter(models.Task.id == task_id).first()
        if task and task.status == "stopped":
            print(f"Task {task_id} was stopped. Aborting execution.")
            db.close()
            return

    if store_ids:
        stores = db.query(models.Store).filter(models.Store.id.in_(store_ids)).all()
    else:
        stores = db.query(models.Store).filter(models.Store.status == 'pending').all()
        
    total = len(stores)
    processed = 0
    found_contacts = 0
    
    if total == 0:
        if update_progress:
            update_progress(text="No stores missing contacts.")
        return {"total_processed": 0, "found_contacts": 0}
        
    if update_progress:
        update_progress(text=f"Starting contact extraction for {total} stores...")
        
    semaphore = asyncio.Semaphore(10)
    
    async def process_store(store):
        nonlocal processed, found_contacts
        
        if task_id:
            # Check if task was stopped mid-execution
            task = db.query(models.Task).filter(models.Task.id == task_id).first()
            if task and task.status == "stopped":
                print(f"Task {task_id} stopped mid-execution.")
                return
                
        async with semaphore:
            if update_progress:
                update_progress(text=f"Extracting contacts for {store.url} ({processed}/{total})", keyword=store.url)
                
            info = await scrape_store_contacts(store.url)
            
            # Step 4 Flywheel extraction (basic keyword extraction from title/desc)
            if info.get("title") and not store.is_parsed_for_keywords:
                text_to_analyze = info["title"] + " " + info.get("meta_desc", "")
                
                # Call our internal API or use a direct function to extract keywords
                try:
                    from main import extract_keywords_from_text
                    from pydantic import BaseModel
                    class DummyReq(BaseModel):
                        text: str
                    
                    req = DummyReq(text=text_to_analyze)
                    kw_result = extract_keywords_from_text(req)
                    
                    extracted_words = kw_result.get("keywords", [])
                    added = 0
                    for w in extracted_words:
                        w = w.strip().lower()
                        if not w: continue
                        # Check if exists
                        existing = db.query(models.Keyword).filter(models.Keyword.word == w).first()
                        if not existing:
                            new_kw = models.Keyword(
                                word=w,
                                schedule_interval="monthly", # Default for scraped words to be slow
                                source="scraped_from_store"
                            )
                            db.add(new_kw)
                            added += 1
                            
                    store.is_parsed_for_keywords = True
                    if added > 0:
                        print(f"Extracted {added} new keywords from store {store.url}")
                except Exception as e:
                    print(f"Failed to extract keywords for {store.url}: {e}")
                
            if info["emails"] or info["phones"] or any(info["socials"].values()):
                contact = models.Contact(
                    store_id=store.id,
                    email=info["emails"][0] if info["emails"] else None,
                    phone=info["phones"][0] if info["phones"] else None,
                    instagram=info["socials"]["instagram"],
                    facebook=info["socials"]["facebook"],
                    whatsapp=info["socials"]["whatsapp"]
                )
                db.add(contact)
                store.status = "completed"
                # commit individually to avoid losing everything if one store errors out
                try:
                    db.commit()
                except Exception:
                    db.rollback()
                found_contacts += 1
                if update_progress:
                    update_progress(found_delta=1, saved_delta=1)
            else:
                store.status = "failed" # No contacts found
                try:
                    db.commit()
                except Exception:
                    db.rollback()
            
            processed += 1
            
    tasks = [process_store(s) for s in stores]
    await asyncio.gather(*tasks)
    
    db.close()
    
    return {"total_processed": total, "found_contacts": found_contacts}