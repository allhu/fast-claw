import asyncio
import re
from urllib.parse import urlparse, urljoin
from sqlalchemy.orm import Session
from playwright.async_api import async_playwright
import models
from database import SessionLocal

EMAIL_REGEX = r'[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+'

def extract_social_links(hrefs):
    socials = {
        'instagram': None,
        'facebook': None,
        'whatsapp': None
    }
    for href in hrefs:
        if not href:
            continue
        href_lower = href.lower()
        if 'instagram.com' in href_lower and not socials['instagram']:
            socials['instagram'] = href
        elif 'facebook.com' in href_lower and not socials['facebook']:
            socials['facebook'] = href
        elif ('wa.me' in href_lower or 'api.whatsapp.com' in href_lower) and not socials['whatsapp']:
            socials['whatsapp'] = href
    return socials

async def scrape_store(page, store_url):
    print(f"Scraping {store_url}...")
    try:
        await page.goto(store_url, timeout=30000, wait_until="domcontentloaded")
    except Exception as e:
        print(f"Failed to load {store_url}: {e}")
        return None

    # Try to find contact info on the home page
    content = await page.content()
    
    # Check if it's Shopify
    is_shopify = 'cdn.shopify.com' in content or 'Shopify.theme' in content
    if not is_shopify:
        print(f"{store_url} might not be a Shopify store.")

    # Find emails
    emails = list(set(re.findall(EMAIL_REGEX, content)))
    
    # Exclude common image/asset false positives like user@2x.png
    emails = [e for e in emails if not e.endswith(('.png', '.jpg', '.jpeg', '.gif', '.webp', '.svg', '.js', '.css'))]
    
    email = emails[0] if emails else None

    # Extract all links
    links = await page.evaluate("() => Array.from(document.querySelectorAll('a')).map(a => a.href)")
    
    # Find social links
    socials = extract_social_links(links)

    # Find phone numbers (simple tel: extraction)
    phone = None
    for link in links:
        if link and link.startswith('tel:'):
            phone = link.replace('tel:', '').strip()
            break

    # If no email, maybe try finding a 'Contact' page
    if not email:
        contact_links = [l for l in links if l and 'contact' in l.lower()]
        if contact_links:
            # Sort to prefer actual /contact or /pages/contact-us over just random links with contact in name
            contact_links.sort(key=lambda x: len(x))
            contact_url = contact_links[0]
            if not contact_url.startswith('http'):
                contact_url = urljoin(store_url, contact_url)
            print(f"Checking contact page: {contact_url}")
            try:
                await page.goto(contact_url, timeout=20000, wait_until="domcontentloaded")
                contact_content = await page.content()
                new_emails = list(set(re.findall(EMAIL_REGEX, contact_content)))
                new_emails = [e for e in new_emails if not e.endswith(('.png', '.jpg', '.jpeg', '.gif', '.webp', '.svg', '.js', '.css'))]
                
                if new_emails:
                    email = new_emails[0]
                
                # If still no email, check for "mailto:" links which might not match simple regex if obfuscated
                mailto_links = await page.evaluate("() => Array.from(document.querySelectorAll('a[href^=\"mailto:\"]')).map(a => a.href)")
                if mailto_links and not email:
                    email = mailto_links[0].replace('mailto:', '').split('?')[0].strip()
                    
            except Exception as e:
                pass

    return {
        "email": email,
        "phone": phone,
        "instagram": socials['instagram'],
        "facebook": socials['facebook'],
        "whatsapp": socials['whatsapp']
    }

async def run_contact_scraping_task(task_id=None, update_progress=None):
    db: Session = SessionLocal()
    
    if task_id:
        task = db.query(models.Task).filter(models.Task.id == task_id).first()
        if task and task.status == "stopped":
            print(f"Task {task_id} was stopped. Aborting execution.")
            db.close()
            return

    pending_stores = db.query(models.Store).filter(models.Store.status == "pending").all()
    
    if not pending_stores:
        print("No pending stores to scrape.")
        db.close()
        return

    print(f"Found {len(pending_stores)} pending stores.")

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = await context.new_page()

        saved_count = 0
        total_scraped = 0
        for store in pending_stores:
            store.status = "scraping"
            db.commit()

            # Ensure URL has scheme
            url = store.url
            if not url.startswith('http'):
                url = 'https://' + url

            result = await scrape_store(page, url)
            total_scraped += 1

            if result:
                contact = models.Contact(
                    store_id=store.id,
                    email=result.get("email"),
                    phone=result.get("phone"),
                    instagram=result.get("instagram"),
                    facebook=result.get("facebook"),
                    whatsapp=result.get("whatsapp")
                )
                db.add(contact)
                store.status = "completed"
                saved_count += 1
            else:
                store.status = "failed"
            
            db.commit()
            print(f"Finished {store.url}: {store.status}")

        await browser.close()
    
    db.close()
    print("Scraping cycle completed.")
    return {"total": total_scraped, "saved": saved_count}

if __name__ == "__main__":
    asyncio.run(run_contact_scraping_task())