import asyncio
from playwright.async_api import async_playwright
from bs4 import BeautifulSoup
import re

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        )
        await page.goto("https://www.dillards.com", wait_until="domcontentloaded", timeout=20000)
        await page.wait_for_timeout(3000)
        html = await page.content()
        text = BeautifulSoup(html, "html.parser").get_text(separator=' ')
        
        print("Finding phones...")
        # basic regex for 1-817-831-5482
        for match in re.finditer(r'1-\d{3}-\d{3}-\d{4}', text):
            print("Found:", match.group(0))
            
        print("Finding call 1-817...")
        for match in re.finditer(r'call\s+1-\d{3}-\d{3}-\d{4}', text, re.IGNORECASE):
            print("Found:", match.group(0))

        await browser.close()

asyncio.run(main())
