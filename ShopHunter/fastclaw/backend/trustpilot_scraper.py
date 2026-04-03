import asyncio
from playwright.async_api import async_playwright
import urllib.parse
import re
from fb_ads_scraper import check_if_shopify

# The playwright-stealth package might not export stealth_async directly in this version
# We can use the standard stealth if available or fallback to custom headers
try:
    from playwright_stealth import stealth_async
except ImportError:
    # If stealth_async is not available, we'll proceed without it 
    # but use our custom user agent and viewport to blend in
    stealth_async = None

async def extract_links_from_trustpilot(keywords: list, max_pages: int = 2, update_progress=None, task_id=None):
    """
    Search Trustpilot for keywords and extract company domains.
    Trustpilot has strong anti-bot protections, so we use Playwright with Stealth.
    """
    print(f"\n--- Starting Trustpilot Search for: {keywords} ---")
    
    all_domains = set()
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        # Setup context to look as human as possible
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            viewport={"width": 1280, "height": 800},
            locale="en-US",
            timezone_id="America/New_York"
        )
        
        page = await context.new_page()
        
        if stealth_async:
            await stealth_async(page)
        else:
            # Fallback stealth measures
            await page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        
        for keyword in keywords:
            # Check if task was stopped
            if task_id:
                from database import SessionLocal
                from models import Task
                db_local = SessionLocal()
                t = db_local.query(Task).filter(Task.id == task_id).first()
                is_stopped = t and t.status == "stopped"
                db_local.close()
                if is_stopped:
                    print("Task stopped by user. Aborting Trustpilot search.")
                    break
            
            if update_progress:
                update_progress(keyword=keyword, text=f"Searching Trustpilot for '{keyword}'...")
                
            # Convert spaces to underscores for category URLs, or use semantic search
            encoded_query = urllib.parse.quote(keyword)
            category_slug = keyword.lower().replace(' ', '_')
            
            for page_num in range(1, max_pages + 1):
                # Try the new semantic search URL which is more robust
                url = f"https://www.trustpilot.com/search?query={encoded_query}&experiment=semantic_search_enabled&page={page_num}"
                print(f"Fetching Trustpilot page {page_num} for '{keyword}'...")
                
                try:
                    await page.goto(url, wait_until="domcontentloaded", timeout=30000)
                    await asyncio.sleep(2)
                    
                    # If semantic search returns no results, try category URL as fallback
                    content = await page.content()
                    if "We couldn't find any results" in content or "0 results" in content.lower():
                        url = f"https://www.trustpilot.com/categories/{category_slug}?page={page_num}"
                        print(f"Fallback to Trustpilot category: {url}")
                        await page.goto(url, wait_until="domcontentloaded", timeout=30000)
                        await asyncio.sleep(2)
                        
                    # Simulate human scrolling to bypass simple behavioral checks
                    await page.mouse.wheel(0, 500)
                    await asyncio.sleep(2)
                    
                    # Extract business URLs from the search results
                    # Trustpilot search results link to /review/domain.com
                    # Also extract raw text because sometimes the domain is just printed in the UI
                    data = await page.evaluate("""() => {
                        const anchors = Array.from(document.querySelectorAll('a[href^="/review/"]'));
                        const links = anchors.map(a => a.getAttribute('href'));
                        const text = document.body.innerText;
                        return { links, text };
                    }""")
                    
                    links = data.get('links', [])
                    text = data.get('text', '')
                    
                    page_domains = set()
                    
                    # 1. Extract from /review/ links
                    for link in links:
                        # Extract domain from /review/domain.com
                        match = re.search(r'/review/([^?]+)', link)
                        if match:
                            domain = match.group(1).lower()
                            if domain and '.' in domain and domain != "www.trustpilot.com":
                                # Prepend https:// and strip www.
                                if domain.startswith('www.'):
                                    domain = domain[4:]
                                page_domains.add(f"https://{domain}")
                                
                    # 2. Extract domain-like patterns from raw text (e.g. www.rarecarat.com from the UI)
                    raw_domains = re.findall(r'\b(?:www\.)?[-a-zA-Z0-9@:%._\+~#=]{1,256}\.[a-zA-Z0-9()]{2,6}\b', text)
                    for d in raw_domains:
                        d = d.lower()
                        if 'trustpilot' not in d and 'cloudflare' not in d:
                            if d.startswith('www.'):
                                d = d[4:]
                            page_domains.add(f"https://{d}")
                                
                    print(f"Found {len(page_domains)} domains on page {page_num}.")
                    all_domains.update(page_domains)
                    
                    # If no links found, we might have hit a captcha or end of results
                    if not links:
                        content = await page.content()
                        if "Cloudflare" in content or "robot" in content.lower():
                            print("Warning: Possible Cloudflare/bot challenge encountered on Trustpilot.")
                            break # Skip to next keyword
                        
                except Exception as e:
                    print(f"Error fetching Trustpilot for '{keyword}' (page {page_num}): {e}")
                    break
                    
                # Small delay between pages
                await asyncio.sleep(1.5)

        await browser.close()
        
    # Verify if they are Shopify stores
    unique_domains = list(all_domains)
    print(f"Found {len(unique_domains)} unique domains from Trustpilot. Verifying Shopify...")
    
    if update_progress:
        update_progress(text=f"Verifying {len(unique_domains)} domains from Trustpilot...", found_delta=len(unique_domains))
        
    semaphore = asyncio.Semaphore(10)
    
    async def sem_check(domain):
        async with semaphore:
            return await check_if_shopify(domain, source_channel="trustpilot")
            
    tasks = [sem_check(domain) for domain in unique_domains]
    results = await asyncio.gather(*tasks)
    
    saved_count = sum(1 for r in results if r)
    print(f"Trustpilot Search complete. Saved {saved_count} new Shopify stores.")
    
    if update_progress:
        update_progress(text=f"Trustpilot search complete. Saved {saved_count} stores.", saved_delta=saved_count)
        
    return {
        "total_found": len(unique_domains),
        "saved": saved_count
    }

if __name__ == "__main__":
    async def test():
        res = await extract_links_from_trustpilot(["furniture"], max_pages=1)
        print(res)
    asyncio.run(test())