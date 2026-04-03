import asyncio
import re
import urllib.parse
from urllib.parse import urlparse
from sqlalchemy.orm import Session
from playwright.async_api import async_playwright
import models
from database import SessionLocal

async def run_search(queries: list, max_pages: int = 3, update_progress=None, task_id=None):
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            viewport={"width": 1280, "height": 800}
        )
        page = await context.new_page()
        
        db: Session = SessionLocal()
        total_saved = 0
        total_found = 0

        for query in queries:
            if task_id:
                # Check if stopped
                db_local = SessionLocal()
                t = db_local.query(models.Task).filter(models.Task.id == task_id).first()
                is_stopped = t and t.status == "stopped"
                db_local.close()
                if is_stopped:
                    break

            print(f"\n--- Starting Search for: {query} ---")
            if update_progress:
                update_progress(keyword=query, text=f"Searching for '{query}' (Page 1)")
            all_domains = set()
            
            # Using Yahoo search which is less strict about headless browsing than Google/DuckDuckGo
            encoded_query = urllib.parse.quote(query)
            # We'll use the pagination offset `b`
            for i in range(max_pages):
                offset = i * 10 + 1
                url = f"https://search.yahoo.com/search?p={encoded_query}&b={offset}"
                
                print(f"Fetching page {i+1}...")
                try:
                    # Use networkidle to be more forgiving than 'load' event, and add slightly longer timeout
                    await page.goto(url, wait_until="domcontentloaded", timeout=45000)
                except Exception as e:
                    print(f"Timeout or error loading Yahoo page {i+1}: {e}")
                    # If we fail to load, we can still try to extract whatever rendered, or skip
                    if i == 0:
                        # If first page fails, we might be blocked or network is bad
                        break
                    else:
                        continue
                        
                await page.wait_for_timeout(3000)
                
                # Extract links from Yahoo results
                links = await page.evaluate("""() => {
                    const anchors = Array.from(document.querySelectorAll('#web a'));
                    return anchors.map(a => a.href).filter(href => href && href.startsWith('http'));
                }""")
                
                domains = set()
                for link in links:
                    # Yahoo redirects links through their r.search.yahoo.com tracker, decode it
                    match = re.search(r'/RU=([^/]+)/', link)
                    if match:
                        actual_url = urllib.parse.unquote(match.group(1))
                    else:
                        actual_url = link
                        
                    try:
                        parsed = urlparse(actual_url)
                        if parsed.scheme in ('http', 'https') and 'yahoo' not in parsed.netloc:
                            domain = f"{parsed.scheme}://{parsed.netloc}"
                            domains.add(domain)
                    except Exception:
                        pass
                
                if not domains:
                    print("No results found on this page. Stopping.")
                    break
                    
                print(f"Found {len(domains)} unique domains on page {i+1}.")
                all_domains.update(domains)
                if update_progress:
                    update_progress(found_delta=len(domains), text=f"Found {len(domains)} domains on page {i+1}")
                
                if update_progress and i + 1 < max_pages:
                    update_progress(text=f"Searching for '{query}' (Page {i+2})")

            print(f"Total unique domains found for '{query}': {len(all_domains)}")
            total_found += len(all_domains)
            
            # Save to database
            if all_domains:
                saved_count = 0
                for domain in all_domains:
                    existing = db.query(models.Store).filter(models.Store.url == domain).first()
                    if not existing:
                        new_store = models.Store(url=domain, source="automated_search", source_channel="yahoo")
                        db.add(new_store)
                        saved_count += 1
                
                db.commit()
                total_saved += saved_count
                print(f"Saved {saved_count} new stores to database for this query.")
                if update_progress:
                    update_progress(saved_delta=saved_count, text=f"Saved {saved_count} stores for '{query}'")
                
            # Sleep between different queries to avoid getting blocked
            await asyncio.sleep(4)

        await browser.close()
        db.close()
        print(f"\nAll searches completed. Total new stores saved: {total_saved}")
        return {"total_found": total_found, "saved": total_saved}

if __name__ == "__main__":
    search_queries = [
        'site:myshopify.com "contact us" apparel',
        'site:myshopify.com "contact us" jewelry'
    ]
    asyncio.run(run_search(search_queries, max_pages=1))