import asyncio
import re
from urllib.parse import urlparse
import yt_dlp

# Assuming check_if_shopify is defined in google_scraper or we can import it from there
# Let's check where it actually is or define it here if needed
# From the grep result, it's defined in fb_ads_scraper.py and tiktok_ads_scraper.py
# Let's import it from fb_ads_scraper since it's already there
from fb_ads_scraper import check_if_shopify

def extract_links_from_text(text):
    """Extract all URLs from a block of text"""
    if not text:
        return []
    # Regex to find http/https links
    url_pattern = r'https?://(?:[-\w.]|(?:%[\da-fA-F]{2}))+[/\w\.-]*'
    links = re.findall(url_pattern, text)
    return list(set(links))

import urllib.parse

def clean_domain(url):
    """Extract the base domain from a URL, handling redirects if necessary"""
    try:
        # Handle YouTube redirect links explicitly
        if 'youtube.com/redirect' in url:
            qs = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)
            if 'q' in qs:
                url = qs['q'][0]
                
        parsed = urllib.parse.urlparse(url)
        domain = parsed.netloc
        if domain.startswith('www.'):
            domain = domain[4:]
            
        # Don't truncate to just domain for shortlink services because 
        # https://bit.ly vs https://bit.ly/123XYZ are different.
        # But wait, if we return just https://bit.ly, we lose the path!
        # check_if_shopify needs the FULL URL to follow the redirect!
        
        # If it's a known shortlink or redirect, return the full URL instead of just the domain
        shortlink_domains = ['bit.ly', 't.co', 'tinyurl.com', 'lnkd.in', 'amzn.to', 'shop.app']
        if any(sd in domain for sd in shortlink_domains):
            return url
            
        if domain:
            return f"https://{domain}"
    except:
        pass
    return None

async def extract_links_from_youtube(keywords: list, max_results_per_keyword: int = 20, update_progress=None, task_id=None):
    """
    Search YouTube for keywords, extract links from video descriptions,
    and verify if they are Shopify stores.
    """
    print(f"\n--- Starting YouTube Search for: {keywords} ---")
    
    ydl_opts = {
        'quiet': True,
        'extract_flat': True,  # Only get metadata, don't download videos
        'force_generic_extractor': True,
        'no_warnings': True,
        'ignoreerrors': True,
    }
    
    all_domains = set()
    
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
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
                    print("Task stopped by user. Aborting YouTube search.")
                    break
                    
            if update_progress:
                update_progress(keyword=keyword, text=f"Searching YouTube for '{keyword}'...")
                
            print(f"Searching YouTube for: {keyword}")
            search_url = f"ytsearch{max_results_per_keyword}:{keyword}"
            
            try:
                # 1. Search for videos
                search_info = ydl.extract_info(search_url, download=False)
                if not search_info or 'entries' not in search_info:
                    continue
                
                entries = list(search_info['entries'])
                print(f"Found {len(entries)} videos for '{keyword}'. Extracting descriptions...")
                
                # 2. Extract links from descriptions
                found_links = set()
                for i, entry in enumerate(entries):
                    if not entry:
                        continue
                    
                    video_url = entry.get('url')
                    if not video_url:
                        continue
                        
                    # To get the description, we need to extract info for the specific video
                    # We use a try-except block because some videos might be unavailable
                    try:
                        video_info = ydl.extract_info(video_url, download=False)
                        if video_info:
                            desc = video_info.get('description', '')
                            links = extract_links_from_text(desc)
                            found_links.update(links)
                    except Exception as e:
                        pass
                        
                print(f"Extracted {len(found_links)} raw URLs from video descriptions.")
                
                # Clean URLs to base domains
                for link in found_links:
                    domain = clean_domain(link)
                    if domain and 'youtube.com' not in domain and 'youtu.be' not in domain and 'google.com' not in domain:
                        all_domains.add(domain)
                        
            except Exception as e:
                print(f"Error searching YouTube for {keyword}: {e}")

    # 3. Verify if they are Shopify stores
    unique_domains = list(all_domains)
    print(f"Found {len(unique_domains)} unique external domains. Verifying Shopify...")
    
    if update_progress:
        update_progress(text=f"Verifying {len(unique_domains)} domains from YouTube...", found_delta=len(unique_domains))
        
    semaphore = asyncio.Semaphore(10) # 10 concurrent checks
    
    async def sem_check(domain):
        async with semaphore:
            return await check_if_shopify(domain, source_channel="youtube")
            
    tasks = [sem_check(domain) for domain in unique_domains]
    results = await asyncio.gather(*tasks)
    
    saved_count = sum(1 for r in results if r)
    print(f"YouTube Search complete. Saved {saved_count} new Shopify stores.")
    
    if update_progress:
        update_progress(text=f"YouTube search complete. Saved {saved_count} stores.", saved_delta=saved_count)
        
    return {
        "total_found": len(unique_domains),
        "saved": saved_count
    }

if __name__ == "__main__":
    # Simple test
    async def test():
        res = await extract_links_from_youtube(["sneaker review"], max_results_per_keyword=2)
        print(res)
    asyncio.run(test())