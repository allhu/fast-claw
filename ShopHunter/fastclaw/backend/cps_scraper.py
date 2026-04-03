import asyncio
import re
import urllib.parse
from playwright.async_api import async_playwright
from fb_ads_scraper import check_if_shopify

# Import stealth if available, otherwise fallback
try:
    from playwright_stealth import stealth_async
except ImportError:
    stealth_async = None

async def extract_links_from_cps_networks(keywords: list, max_pages: int = 2, update_progress=None, task_id=None):
    """
    Search CPS (Cost Per Sale) networks like Dealmoon and RetailMeNot for deals and extract outbound affiliate links.
    """
    print(f"\n--- Starting CPS Networks Search for: {keywords} ---")
    
    all_domains = set()
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        # Use a realistic user agent and headers to bypass 406 Not Acceptable
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            viewport={"width": 1280, "height": 800},
            extra_http_headers={
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.5",
                "Upgrade-Insecure-Requests": "1"
            }
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
                    print("Task stopped by user. Aborting CPS search.")
                    break
            
            if update_progress:
                update_progress(keyword=keyword, text=f"Searching CPS networks for '{keyword}'...")
                
            encoded_query = urllib.parse.quote(keyword)
            
            # --- 1. Scrape Dealmoon ---
            for page_num in range(1, max_pages + 1):
                url = f"https://www.dealmoon.com/search?q={encoded_query}&p={page_num}"
                print(f"Fetching Dealmoon page {page_num} for '{keyword}'...")
                
                try:
                    await page.goto(url, wait_until="domcontentloaded", timeout=40000)
                    
                    # Scroll to trigger lazy loading of deals
                    for _ in range(3):
                        await page.mouse.wheel(0, 1000)
                        await asyncio.sleep(1.5)
                    
                    # Dealmoon wraps outbound links usually with /exec/j?d= or go.dealmoon.com
                    links = await page.evaluate("""() => {
                        const anchors = Array.from(document.querySelectorAll('a'));
                        return anchors.map(a => a.href);
                    }""")
                    
                    page_links = set()
                    for link in links:
                        if not link: continue
                        if 'dealmoon.com/exec' in link or 'go.dealmoon.com' in link:
                            # We don't parse the domain yet because it's a redirect link
                            # We will pass the full redirect URL to the verifier
                            page_links.add(link)
                            
                    print(f"Found {len(page_links)} Dealmoon CPS links on page {page_num}.")
                    all_domains.update(page_links)
                    
                    if len(page_links) < 5:
                        # Probably reached the end of results
                        break
                        
                except Exception as e:
                    print(f"Error on Dealmoon page {page_num} for '{keyword}': {e}")
                    break
                    
            # --- 2. Scrape RetailMeNot ---
            try:
                rmn_url = f"https://www.retailmenot.com/s/{encoded_query}"
                print(f"Fetching RetailMeNot for '{keyword}'...")
                await page.goto(rmn_url, wait_until="domcontentloaded", timeout=40000)
                
                # Scroll to load deals
                for _ in range(3):
                    await page.mouse.wheel(0, 1000)
                    await asyncio.sleep(1.5)
                
                links = await page.evaluate("() => Array.from(document.querySelectorAll('a')).map(a => a.href)")
                rmn_links = set(l for l in links if '/out/' in l or '/click/' in l)
                print(f"Found {len(rmn_links)} RetailMeNot CPS links.")
                all_domains.update(rmn_links)
            except Exception as e:
                print(f"Error on RetailMeNot for '{keyword}': {e}")

            # --- 3. Scrape Slickdeals ---
            try:
                sd_url = f"https://slickdeals.net/newsearch.php?q={encoded_query}"
                print(f"Fetching Slickdeals for '{keyword}'...")
                await page.goto(sd_url, wait_until="domcontentloaded", timeout=40000)
                
                # Scroll to load deals
                for _ in range(3):
                    await page.mouse.wheel(0, 1000)
                    await asyncio.sleep(1.5)
                
                links = await page.evaluate("() => Array.from(document.querySelectorAll('a')).map(a => a.href)")
                sd_links = set(l for l in links if 'slickdeals.net/?' in l)
                print(f"Found {len(sd_links)} Slickdeals CPS links.")
                all_domains.update(sd_links)
            except Exception as e:
                print(f"Error on Slickdeals for '{keyword}': {e}")

        await browser.close()
        
    unique_links = list(all_domains)
    print(f"Found {len(unique_links)} unique CPS links. Verifying Shopify & following redirects...")
    
    if update_progress:
        update_progress(text=f"Verifying {len(unique_links)} CPS links...", found_delta=len(unique_links))
        
    saved_count = 0
    # Process in batches
    semaphore = asyncio.Semaphore(5)
    async def sem_check(link):
        async with semaphore:
            # check_if_shopify uses httpx with follow_redirects=True
            # It will follow CPS redirect -> intermediate -> realstore.com
            # and then save realstore.com as the domain!
            return await check_if_shopify(link, source_channel="cps")

    tasks = [sem_check(link) for link in unique_links]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    for res in results:
        if res is True:
            saved_count += 1
            if update_progress:
                update_progress(saved_delta=1)
                
    print(f"CPS Networks Search complete. Saved {saved_count} new Shopify stores.")
    if update_progress:
        update_progress(text=f"CPS networks search complete. Saved {saved_count} stores.")
        
    return {"total_found": len(unique_links), "saved": saved_count}

if __name__ == "__main__":
    asyncio.run(extract_links_from_cps_networks(["shoes"], max_pages=1))