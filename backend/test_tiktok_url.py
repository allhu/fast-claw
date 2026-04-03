import asyncio
from playwright.async_api import async_playwright

async def test():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.goto("https://library.tiktok.com/ads")
        await page.wait_for_timeout(3000)
        content = await page.content()
        with open("tiktok_debug.html", "w") as f:
            f.write(content)
        await browser.close()

asyncio.run(test())
