import asyncio
from playwright.async_api import async_playwright

async def run():
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()
        await page.goto("https://www.google.com/search?q=sneaker&tbm=shop")
        links = await page.evaluate("() => Array.from(document.querySelectorAll('a')).map(a => a.href)")
        print("\n".join(links[:20]))
        
        await page.goto("https://www.pinterest.com/search/pins/?q=sneaker&rs=typed")
        await asyncio.sleep(3)
        plinks = await page.evaluate("() => Array.from(document.querySelectorAll('a')).map(a => a.href)")
        print("PINTEREST")
        print("\n".join(plinks[:20]))
        await browser.close()

asyncio.run(run())
