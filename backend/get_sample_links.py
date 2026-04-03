import asyncio
import sys
import fb_ads_scraper
import tiktok_ads_scraper
import youtube_scraper
import trustpilot_scraper
import reddit_scraper
import google_shopping_scraper
import pinterest_scraper

captured_links = {
    "fb_ads": [],
    "tiktok_ads": [],
    "youtube": [],
    "trustpilot": [],
    "reddit": [],
    "google_shopping": [],
    "pinterest": []
}

async def mock_check_fb(domain, source_channel="unknown"):
    # Sometimes source_channel comes as fb_ads_api, fb_ads_playwright, etc.
    key = "fb_ads" if "fb" in source_channel else source_channel
    if key not in captured_links:
        key = source_channel
        captured_links[key] = []
    
    if len(captured_links[key]) < 10:
        captured_links[key].append(domain)
    return False

async def mock_check_tiktok(domain, source_channel="unknown"):
    key = "tiktok_ads" if "tiktok" in source_channel else source_channel
    if key not in captured_links:
        key = source_channel
        captured_links[key] = []
        
    if len(captured_links[key]) < 10:
        captured_links[key].append(domain)
    return False

# Mock the functions
fb_ads_scraper.check_if_shopify = mock_check_fb
tiktok_ads_scraper.check_if_shopify = mock_check_tiktok

# These use the imported one from fb_ads_scraper
youtube_scraper.check_if_shopify = mock_check_fb
trustpilot_scraper.check_if_shopify = mock_check_fb
reddit_scraper.check_if_shopify = mock_check_fb
google_shopping_scraper.check_if_shopify = mock_check_fb
pinterest_scraper.check_if_shopify = mock_check_fb

async def run_all():
    kw = ["handmade jewelry"]
    print("--- Scraping FB Ads ---")
    await fb_ads_scraper.extract_links_from_ad_library(kw, max_pages=1, max_scrolls=2)
    
    print("\n--- Scraping TikTok Ads ---")
    await tiktok_ads_scraper.extract_links_from_tiktok_ads(kw, max_scrolls=2)
    
    print("\n--- Scraping YouTube ---")
    await youtube_scraper.extract_links_from_youtube(["handmade jewelry review"], max_results_per_keyword=10)
    
    print("\n--- Scraping Trustpilot ---")
    await trustpilot_scraper.extract_links_from_trustpilot(kw, max_pages=1)
    
    print("\n--- Scraping Reddit ---")
    await reddit_scraper.extract_links_from_reddit(kw, max_posts=10)
    
    print("\n--- Scraping Google Shopping ---")
    await google_shopping_scraper.extract_links_from_google_shopping(kw, max_pages=1)
    
    print("\n--- Scraping Pinterest ---")
    await pinterest_scraper.extract_links_from_pinterest(kw, max_scrolls=2)
    
    print("\n\n" + "="*50)
    print("SAMPLED RAW DOMAINS (Before Shopify Validation)")
    print("="*50)
    for ch, links in captured_links.items():
        unique_links = list(set(links))[:5]
        print(f"\n[{ch.upper()}] ({len(unique_links)} samples):")
        if not unique_links:
            print("  (No links found in sample run)")
        for l in unique_links:
            print(f"  - {l}")

if __name__ == "__main__":
    asyncio.run(run_all())