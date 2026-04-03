import asyncio
from fb_ads_scraper import extract_links_from_ad_library
import json

async def test():
    token = "EAAUCKZAHJPP0BRDvWZCQnRu6pnZB7drZASjwSvPo78P3zEsPdz8tVDXMi1Ji96rEpIrvaGIP8iSD59ig8DxMJ9KJQs6ZBs1GdJQQZB9YRqUn9ZCEHf5i68hTvGhoP6OZBshiTx2plWFnQGuUPeJMnotvCFwssSO9LUZCQIYadsLMsmYsmBAtWXbAzy5P7uJY1R4pMdl2e2KBCZBN8ZAkoRsC8reflq6bEssy994ZAbx99SLKocWZBZAqZBtWgZDZD"
    res = await extract_links_from_ad_library(["Home Decor"], max_scrolls=1, max_pages=1, use_api=True, fb_token=token)
    print("API Result:", res)

asyncio.run(test())
