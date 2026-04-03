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

async def extract_links_from_pinterest(keywords: list, max_scrolls: int = 15, update_progress=None, task_id=None):
    """
    Search Pinterest for keywords and extract outbound product domains.
    """
    print(f"\n--- Starting Pinterest Search for: {keywords} ---")
    
    all_domains = set()
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        # Pinterest restricts content heavily for non-logged-in users and blocks bots.
        # We need stealth and a convincing user agent
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
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
                    print("Task stopped by user. Aborting Pinterest search.")
                    break
            
            if update_progress:
                update_progress(keyword=keyword, text=f"Searching Pinterest for '{keyword}'...")
                
            encoded_query = urllib.parse.quote(keyword)
            # Pinterest Search URL
            url = f"https://www.pinterest.com/search/pins/?q={encoded_query}&rs=typed"
            
            try:
                await page.goto(url, wait_until="domcontentloaded", timeout=45000)
                print(f"Loaded Pinterest page for '{keyword}'. Handling popups and scrolling...")
                
                # Close potential login modals
                await asyncio.sleep(5)
                
                try:
                    close_btn = await page.locator("div[role='button'] svg[aria-label='close']").first
                    if close_btn:
                        await close_btn.click()
                except:
                    pass
                
                # Pinterest is a massive infinite scroll masonry layout
                pin_urls = set()
                
                for i in range(max_scrolls):
                    print(f"Pinterest Scroll {i+1}/{max_scrolls}...")
                    await page.mouse.wheel(0, 1500)
                    await asyncio.sleep(2)
                    
                    # Extract pin links
                    links = await page.evaluate("""() => {
                        const links = Array.from(document.querySelectorAll('a[href^="/pin/"]'));
                        return links.map(a => a.href);
                    }""")
                    
                    for link in links:
                        pin_urls.add(link)
                        
                    if len(pin_urls) > 30:
                        break # Enough pins to check
                
                print(f"Found {len(pin_urls)} pins. Visiting them to find outbound links...")
                
                page_domains = set()
                pin_urls = list(pin_urls)[:30] # Limit to 30 pins per keyword to save time
                
                for idx, pin_url in enumerate(pin_urls):
                    try:
                        print(f"Visiting pin {idx+1}/{len(pin_urls)}: {pin_url}")
                        await page.goto(pin_url, wait_until="domcontentloaded", timeout=15000)
                        await asyncio.sleep(1.5)
                        
                        links_and_text = await page.evaluate("""() => {
                            const links = Array.from(document.querySelectorAll('a[href^="http"]'));
                            const text = document.body.innerText;
                            return { 
                                hrefs: links.map(a => a.href), 
                                text: text 
                            };
                        }""")
                        
                        hrefs = links_and_text.get('hrefs', [])
                        text = links_and_text.get('text', '')
                        
                        # 1. Parse Hrefs
                        for link in hrefs:
                            if 'pinterest.com' in link or 'pinimg.com' in link:
                                continue
                            try:
                                parsed = urllib.parse.urlparse(link)
                                domain = parsed.netloc.lower()
                                if domain:
                                    if domain.startswith('www.'):
                                        domain = domain[4:]
                                    page_domains.add(f"https://{domain}")
                            except:
                                pass
                                
                        # 2. Parse Raw Text for domains
                        raw_domains = re.findall(r'\b(?:www\.)?[-a-zA-Z0-9@:%._\+~#=]{1,256}\.[a-zA-Z0-9()]{2,6}\b', text)
                        for d in raw_domains:
                            d = d.lower()
                            if 'pinterest' not in d and 'pinimg' not in d:
                                if d.startswith('www.'):
                                    d = d[4:]
                                page_domains.add(f"https://{d}")
                                
                    except Exception as e:
                        print(f"Error visiting pin {pin_url}: {e}")
                        
                print(f"Found {len(page_domains)} domains for '{keyword}'.")
                all_domains.update(page_domains)
                
            except Exception as e:
                print(f"Error searching Pinterest for '{keyword}': {e}")
                
        await browser.close()
        
    # Verify Shopify
    unique_domains = list(all_domains)
    print(f"Found {len(unique_domains)} unique external domains from Pinterest. Verifying Shopify...")
    
    if update_progress:
        update_progress(text=f"Verifying {len(unique_domains)} domains from Pinterest...", found_delta=len(unique_domains))
        
    saved_count = 0
    # Process in batches
    semaphore = asyncio.Semaphore(5)
    async def sem_check(domain):
        async with semaphore:
            return await check_if_shopify(domain, source_channel="pinterest")

    tasks = [sem_check(d) for d in unique_domains]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    for res in results:
        if res is True:
            saved_count += 1
            if update_progress:
                update_progress(saved_delta=1)
                
    print(f"Pinterest Search complete. Saved {saved_count} new Shopify stores.")
    if update_progress:
        update_progress(text=f"Pinterest search complete. Saved {saved_count} stores.")
        
    return {"total_found": len(unique_domains), "saved": saved_count}

if __name__ == "__main__":
    asyncio.run(extract_links_from_pinterest(["Handmade Jewelry"], max_scrolls=2))