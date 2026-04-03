import asyncio
from fb_ads_scraper import extract_links_from_ad_library

async def test():
    print("Testing Playwright FB Ads...")
    res = await extract_links_from_ad_library(['jewelry'], max_scrolls=1, use_api=False)
    print("Result:", res)

asyncio.run(test())
