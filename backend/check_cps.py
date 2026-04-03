import asyncio
from playwright.async_api import async_playwright
try:
    from playwright_stealth import stealth_async
except ImportError:
    stealth_async = None

async def run():
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            extra_http_headers={"Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8"}
        )
        page = await context.new_page()
        if stealth_async:
            await stealth_async(page)
        
        print("Testing Slickdeals...")
        try:
            await page.goto("https://slickdeals.net/newsearch.php?q=jewelry", wait_until="domcontentloaded", timeout=15000)
            await asyncio.sleep(5)
            sd_links = await page.evaluate("() => Array.from(document.querySelectorAll('a')).map(a => a.href)")
            sd_out = set(l for l in sd_links if 'slickdeals.net/?' in l)
            print(f"Slickdeals out links: {len(sd_out)}")
        except Exception as e:
            print("Slickdeals error:", e)
            
        print("Testing RetailMeNot...")
        try:
            await page.goto("https://www.retailmenot.com/s/jewelry", wait_until="domcontentloaded", timeout=15000)
            await asyncio.sleep(5)
            rmn_links = await page.evaluate("() => Array.from(document.querySelectorAll('a')).map(a => a.href)")
            rmn_out = set(l for l in rmn_links if '/out/' in l or '/click/' in l)
            print(f"RetailMeNot out links: {len(rmn_out)}")
        except Exception as e:
            print("RetailMeNot error:", e)

        await browser.close()

asyncio.run(run())