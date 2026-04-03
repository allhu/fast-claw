import asyncio
import re
import urllib.parse
import aiohttp
from fb_ads_scraper import check_if_shopify

def extract_links_from_text(text):
    """Extract all URLs from a block of text"""
    if not text:
        return []
    # Regex to find http/https links
    url_pattern = r'https?://(?:[-\w.]|(?:%[\da-fA-F]{2}))+[/\w\.-]*'
    links = re.findall(url_pattern, text)
    return list(set(links))

def clean_domain(url):
    """Extract the base domain from a URL"""
    try:
        parsed = urllib.parse.urlparse(url)
        domain = parsed.netloc
        if domain.startswith('www.'):
            domain = domain[4:]
        if domain:
            return f"https://{domain}"
    except:
        pass
    return None

async def extract_links_from_reddit(keywords: list, max_posts: int = 50, update_progress=None, task_id=None):
    """
    Search Reddit for keywords via JSON API (if available) and extract links from posts/comments.
    Note: Reddit API has rate limits for unauthenticated requests.
    """
    print(f"\n--- Starting Reddit Search for: {keywords} ---")
    
    all_domains = set()
    
    # Reddit requires a custom User-Agent to avoid immediate 429 Too Many Requests
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36 FastClaw/1.0'
    }
    
    async with aiohttp.ClientSession(headers=headers) as session:
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
                    print("Task stopped by user. Aborting Reddit search.")
                    break
                    
            if update_progress:
                update_progress(keyword=keyword, text=f"Searching Reddit for '{keyword}'...")
                
            # Enhance search with e-commerce intent keywords rather than strict domain matching
            # People don't usually say "my shopify store", they say "my brand", "buy here", "price check"
            search_query = f"{keyword} (brand OR buy OR price OR store OR shop)"
            encoded_query = urllib.parse.quote(search_query)
            
            # Try searching in popular e-commerce subreddits or globally
            url = f"https://www.reddit.com/search.json?q={encoded_query}&limit={max_posts}&sort=new"
            
            try:
                print(f"Fetching Reddit search results for: {keyword}")
                async with session.get(url, timeout=15) as response:
                    if response.status == 429:
                        print(f"Reddit Rate Limited (429) for keyword '{keyword}'. Skipping...")
                        continue
                        
                    if response.status != 200:
                        print(f"Reddit API returned status {response.status} for keyword '{keyword}'.")
                        continue
                        
                    data = await response.json()
                    
                    if 'data' not in data or 'children' not in data['data']:
                        continue
                        
                    posts = data['data']['children']
                    print(f"Found {len(posts)} posts for '{keyword}'. Extracting links...")
                    
                    found_links = set()
                    for post in posts:
                        post_data = post.get('data', {})
                        
                        # Check the post URL itself (if it's a link post)
                        post_url = post_data.get('url', '')
                        if post_url and not post_url.startswith('https://www.reddit.com'):
                            found_links.add(post_url)
                            
                        # Check the selftext (if it's a text post)
                        selftext = post_data.get('selftext', '')
                        if selftext:
                            links = extract_links_from_text(selftext)
                            found_links.update(links)
                            
                    # Clean URLs to base domains
                    for link in found_links:
                        domain = clean_domain(link)
                        if domain and 'reddit.com' not in domain and 'redd.it' not in domain:
                            all_domains.add(domain)
                            
            except Exception as e:
                print(f"Error searching Reddit for {keyword}: {e}")
                
            # Be nice to the API
            await asyncio.sleep(2)
            
    # Verify if they are Shopify stores
    unique_domains = list(all_domains)
    print(f"Found {len(unique_domains)} unique external domains from Reddit. Verifying Shopify...")
    
    if update_progress:
        update_progress(text=f"Verifying {len(unique_domains)} domains from Reddit...", found_delta=len(unique_domains))
        
    semaphore = asyncio.Semaphore(10)
    
    async def sem_check(domain):
        async with semaphore:
            return await check_if_shopify(domain, source_channel="reddit")
            
    tasks = [sem_check(domain) for domain in unique_domains]
    results = await asyncio.gather(*tasks)
    
    saved_count = sum(1 for r in results if r)
    print(f"Reddit Search complete. Saved {saved_count} new Shopify stores.")
    
    if update_progress:
        update_progress(text=f"Reddit search complete. Saved {saved_count} stores.", saved_delta=saved_count)
        
    return {
        "total_found": len(unique_domains),
        "saved": saved_count
    }

if __name__ == "__main__":
    async def test():
        res = await extract_links_from_reddit(["shopify store review"])
        print(res)
    asyncio.run(test())