import asyncio
import re
import urllib.parse
from playwright.async_api import async_playwright
from database import SessionLocal
from fb_ads_scraper import check_if_shopify

# Import stealth if available, otherwise fallback
try:
    from playwright_stealth import stealth_async
except ImportError:
    stealth_async = None

async def extract_links_from_google_shopping(keywords: list, max_pages: int = 3, update_progress=None, task_id=None):
    """
    Search Google Shopping for products and extract the seller domains.
    """
    print(f"\n--- Starting Google Shopping Search for: {keywords} ---")
    
    all_domains = set()
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            viewport={"width": 1280, "height": 800},
            locale="en-US"
        )
        
        page = await context.new_page()
        if stealth_async:
            await stealth_async(page)
        
        for keyword in keywords:
            if task_id:
                from database import SessionLocal
                from models import Task
                db_local = SessionLocal()
                t = db_local.query(Task).filter(Task.id == task_id).first()
                is_stopped = t and t.status == "stopped"
                db_local.close()
                if is_stopped:
                    print("Task stopped by user. Aborting Google Shopping search.")
                    break
            
            if update_progress:
                update_progress(keyword=keyword, text=f"Searching Google Shopping for '{keyword}'...")
                
            # tbm=shop forces Google to show the Shopping tab
            encoded_query = urllib.parse.quote(keyword)
            
            for page_num in range(max_pages):
                start = page_num * 60 # Google shopping usually shows 60 results per page
                url = f"https://www.google.com/search?q={encoded_query}&tbm=shop&start={start}&gl=us&hl=en"
                print(f"Fetching Google Shopping page {page_num + 1} for '{keyword}'...")
                
                try:
                    await page.goto(url, wait_until="domcontentloaded", timeout=30000)
                    
                    # Simulate human behavior
                    await page.mouse.wheel(0, 800)
                    await asyncio.sleep(2)
                    await page.mouse.wheel(0, 1500)
                    await asyncio.sleep(1)
                    
                    # Extract URLs from shopping cards
                    # Google Shopping wraps outbound links in a redirect url like /url?q=https://realstore.com
                    links = await page.evaluate("""() => {
                        const anchors = Array.from(document.querySelectorAll('a[href^="/url?q="], a[href^="https://"]'));
                        return anchors.map(a => a.getAttribute('href'));
                    }""")
                    
                    page_domains = set()
                    for link in links:
                        if not link: continue
                        
                        target_url = link
                        if link.startswith('/url?q='):
                            qs = urllib.parse.parse_qs(urllib.parse.urlparse(link).query)
                            if 'q' in qs:
                                target_url = qs['q'][0]
                                
                        if 'google.com' in target_url:
                            continue
                            
                        try:
                            parsed = urllib.parse.urlparse(target_url)
                            domain = parsed.netloc.lower()
                            if domain:
                                if domain.startswith('www.'):
                                    domain = domain[4:]
                                page_domains.add(f"https://{domain}")
                        except:
                            pass
                            
                    print(f"Found {len(page_domains)} domains on page {page_num + 1}.")
                    all_domains.update(page_domains)
                    
                    # If we found very few links, we might have hit the end of results
                    if len(page_domains) < 5:
                        break
                        
                except Exception as e:
                    print(f"Error on Google Shopping page {page_num + 1} for '{keyword}': {e}")
                    break
                    
        await browser.close()
        
    # Verify Shopify
    unique_domains = list(all_domains)
    print(f"Found {len(unique_domains)} unique domains from Google Shopping. Verifying Shopify...")
    
    if update_progress:
        update_progress(text=f"Verifying {len(unique_domains)} domains from Google Shopping...", found_delta=len(unique_domains))
        
    saved_count = 0
    # Process in batches
    semaphore = asyncio.Semaphore(5)
    async def sem_check(domain):
        async with semaphore:
            return await check_if_shopify(domain, source_channel="google_shopping")

    tasks = [sem_check(d) for d in unique_domains]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    for res in results:
        if res is True:
            saved_count += 1
            if update_progress:
                update_progress(saved_delta=1)
                
    print(f"Google Shopping Search complete. Saved {saved_count} new Shopify stores.")
    if update_progress:
        update_progress(text=f"Google Shopping search complete. Saved {saved_count} stores.")
        
    return {"total_found": len(unique_domains), "saved": saved_count}

if __name__ == "__main__":
    asyncio.run(extract_links_from_google_shopping(["Yoga Mats"], max_pages=1))