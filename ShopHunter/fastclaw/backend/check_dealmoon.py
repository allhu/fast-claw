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
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            extra_http_headers={"Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8"}
        )
        page = await context.new_page()
        if stealth_async:
            await stealth_async(page)
        
        try:
            await page.goto("https://www.dealmoon.com/search?q=sneaker", wait_until="domcontentloaded")
            await asyncio.sleep(5)
            links = await page.evaluate("() => Array.from(document.querySelectorAll('a')).map(a =import asyncio
from playwright.async_api import async_playwriglmfrom playwrig"try: