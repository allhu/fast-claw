import asyncio
from contact_scraper import scrape_store_contacts

async def main():
    print("Testing dillards.com...")
    result = await scrape_store_contacts("https://www.dillards.com")
    print(result)

asyncio.run(main())
