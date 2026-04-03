import asyncio
import re
from urllib.parse import urlparse
import httpx
from sqlalchemy.orm import Session
from database import SessionLocal
import models

# Replace with your actual valid Facebook Graph API token with ads_read permission
FB_ACCESS_TOKEN = "YOUR_FB_GRAPH_API_TOKEN"

# Common non-ecommerce domains to ignore
BLOCKLIST = {
    'msn.com', 'yahoo.com', 'google.com', 'facebook.com', 'instagram.com', 
    'tiktok.com', 'youtube.com', 'reddit.com', 'pinterest.com', 'twitter.com',
    'linkedin.com', 'amazon.com', 'ebay.com', 'walmart.com', 'aliexpress.com',
    'bing.com', 'wikipedia.org', 'apple.com', 'microsoft.com'
}

async def check_if_shopify(url: str, source_channel: str = "unknown") -> bool:
    """
    Fetch the URL and check if it contains Shopify fingerprints.
    Returns True if it's likely a Shopify store and saves it with source_channel.
    """
    try:
        # Some basic cleanup
        if not url.startswith('http'):
            url = 'https://' + url
            
        parsed_url = urlparse(url)
        domain = parsed_url.netloc.lower()
        if domain.startswith('www.'):
            domain = domain[4:]
            
        # Quick blocklist check
        for blocked in BLOCKLIST:
            if domain == blocked or domain.endswith('.' + blocked):
                return False
            
        async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
            response = await client.get(url, headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            })
            
            text = response.text
            
            # Check for strong Shopify indicators, not just casual mentions
            is_shopify = False
            
            # Extremely strong indicators
            if 'Shopify.theme' in text or 'cdn.shopify.com' in text or 'window.Shopify' in text:
                is_shopify = True
            elif 'shopify-checkout' in text or 'shopify-payment' in text:
                is_shopify = True
            # Broaden the myshopify.com fallback
            elif 'myshopify.com' in text and ('cart' in text or 'checkout' in text or 'price' in text or 'product' in text):
                is_shopify = True
                
            if is_shopify:
                final_url = str(response.url)
                parsed_uri = urlparse(final_url)
                domain = parsed_uri.netloc
                if domain.startswith('www.'):
                    domain = domain[4:]
                    
                # Save to database
                db = SessionLocal()
                try:
                    existing = db.query(models.Store).filter(models.Store.domain == domain).first()
                    if not existing:
                        new_store = models.Store(
                            domain=domain,
                            url=final_url,
                            status="pending",
                            source=source_channel,
                            source_channel=source_channel
                        )
                        db.add(new_store)
                        db.commit()
                        return True
                except Exception as e:
                    print(f"DB Error saving {domain}: {e}")
                finally:
                    db.close()
            else:
                # Uncomment to debug failed domains
                # print(f"Rejected domain (Not Shopify): {url}")
                pass
    except httpx.RequestError as e:
        # print(f"Network error checking {url}: {e}")
        pass
    except Exception as e:
        # print(f"Unexpected error checking {url}: {e}")
        pass
    return False

async def verify_domains_concurrently(domains):
    semaphore = asyncio.Semaphore(10) # limit to 10 concurrent requests
    
    async def sem_check(domain):
        async with semaphore:
            return await check_if_shopify(domain, source_channel="fb_ads")
            
    tasks = [sem_check(domain) for domain in domains]
    return await asyncio.gather(*tasks)

async def extract_links_from_ad_library_api(keywords: list, limit: int = 100, country: str = 'US', max_pages: int = 10, update_progress=None):
    """
    Extract domains from Facebook Ads Library using the official Graph API.
    """
    print(f"\n--- Starting FB Ads API Search for: {keywords} (Country: {country}) ---")
    
    if FB_ACCESS_TOKEN == "YOUR_FB_GRAPH_API_TOKEN":
        print("WARNING: FB_ACCESS_TOKEN is not set. Please provide a valid token in fb_ads_scraper.py")
        return {"total_found": 0, "saved": 0}

    api_url = "https://graph.facebook.com/v19.0/ads_archive"
    db: Session = SessionLocal()
    total_saved = 0
    total_found = 0
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            for keyword in keywords:
                print(f"Searching API for keyword: {keyword}")
                if update_progress:
                    update_progress(keyword=keyword, text=f"FB API Search for '{keyword}'")
                
                # Setup pagination cursor
                after_cursor = None
                
                for page_num in range(max_pages):
                    print(f"  -> API Page {page_num + 1}/{max_pages}")
                    if update_progress:
                        update_progress(text=f"FB API Search for '{keyword}' (Page {page_num + 1})")
                    params = {
                        "access_token": FB_ACCESS_TOKEN,
                        "search_terms": keyword,
                        "ad_type": "ALL",
                        "ad_reached_countries": f"['{country}']",
                        "fields": "ad_snapshot_url,page_id,page_name,ad_creation_time,ad_creative_link_captions,ad_creative_link_descriptions,ad_creative_link_titles",
                        "limit": limit
                    }
                    
                    if after_cursor:
                        params["after"] = after_cursor
                
                    all_domains = set()
                    response = await client.get(api_url, params=params)
                    data = response.json()
                    
                    if 'error' in data:
                        print(f"FB API Error for {keyword}: {data['error'].get('message', data['error'])}")
                        break # Stop pagination for this keyword on error
                        
                    ads = data.get('data', [])
                    print(f"     Retrieved {len(ads)} ads.")
                    
                    if not ads:
                        break # No more results
                        
                    for ad in ads:
                        texts_to_check = []
                        if 'ad_creative_link_captions' in ad:
                            texts_to_check.extend(ad['ad_creative_link_captions'])
                        if 'ad_creative_link_descriptions' in ad:
                            texts_to_check.extend(ad['ad_creative_link_descriptions'])
                            
                        for text in texts_to_check:
                            if not text: continue
                            urls = re.findall(r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\(\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+', text)
                            for u in urls:
                                try:
                                    parsed = urlparse(u)
                                    domain = f"{parsed.scheme}://{parsed.netloc}"
                                    all_domains.add(domain)
                                except:
                                    pass
                    
                    exclude_domains = ['bit.ly', 'google.com', 'apple.com', 'whatsapp.com', 'youtube.com', 'tiktok.com', 'facebook.com', 'instagram.com']
                    cleaned_domains = {d for d in all_domains if not any(ex in d for ex in exclude_domains)}
                    total_found += len(cleaned_domains)
                    
                    if cleaned_domains:
                        saved_count = 0
                        results = await verify_domains_concurrently(cleaned_domains)
                        
                        for domain, is_shopify in zip(cleaned_domains, results):
                            if is_shopify:
                                # For API results, domain is already a parsed clean domain here?
                                # Let's be sure
                                parsed = urlparse(domain)
                                clean_domain = parsed.netloc or domain
                                if clean_domain.startswith('www.'): clean_domain = clean_domain[4:]
                                clean_domain = clean_domain.replace('https://', '').replace('http://', '').split('/')[0]
                                
                                existing = db.query(models.Store).filter(models.Store.domain == clean_domain).first()
                                if not existing:
                                    new_store = models.Store(
                                        domain=clean_domain,
                                        url=domain, 
                                        source="fb_ads_api",
                                        source_channel="fb_ads"
                                    )
                                    db.add(new_store)
                                    saved_count += 1
                        
                        db.commit()
                        total_saved += saved_count
                        print(f"     Saved {saved_count} new Shopify stores in this page.")
                        if update_progress:
                            update_progress(found_delta=len(cleaned_domains), saved_delta=saved_count, text=f"FB API Search for '{keyword}': Found {len(cleaned_domains)}, Saved {saved_count}")
                    
                    # Check if there is a next page
                    paging = data.get('paging', {})
                    if 'cursors' in paging and 'after' in paging['cursors']:
                        after_cursor = paging['cursors']['after']
                        # Sleep to avoid rate limits
                        await asyncio.sleep(2)
                    else:
                        break # No more pages
                        
                # Sleep between different keywords
                await asyncio.sleep(3)
                
    except Exception as e:
        print(f"Error calling FB Ads API: {e}")
    finally:
        db.close()
        print(f"API Search completed. Total saved: {total_saved}")
        return {"total_found": total_found, "saved": total_saved}

# Keep the old Playwright version as a fallback
async def extract_links_from_ad_library_playwright(keywords: list, max_scrolls: int = 5, update_progress=None):
    """
    Experimental script to extract domains from Facebook Ads Library.
    """
    print(f"\n--- Starting FB Ads Library Search for: {keywords} ---")
    
    from playwright.async_api import async_playwright
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            viewport={"width": 1280, "height": 800}
        )
        page = await context.new_page()
        db: Session = SessionLocal()
        total_saved = 0
        total_found = 0

        try:
            for keyword in keywords:
                print(f"\n--- Processing keyword: {keyword} ---")
                if update_progress:
                    update_progress(keyword=keyword, text=f"FB Playwright Search for '{keyword}'")
                
                # Make sure we're navigating properly and waiting for the new search to render
                url = f"https://www.facebook.com/ads/library/?active_status=all&ad_type=all&country=ALL&q={keyword}&search_type=keyword_unordered&media_type=all"
                
                # Use domcontentloaded for initial load
                await page.goto(url, wait_until="domcontentloaded", timeout=60000)
                print(f"Loaded Ads Library page for '{keyword}'. Waiting for ads to render...")
                
                # FB ads library takes time to populate React components
                await page.wait_for_timeout(8000)
                
                # Try to close the cookie banner if it exists
                try:
                    cookie_buttons = await page.locator("div[role='dialog'] div[role='button']").all()
                    for btn in cookie_buttons:
                        text = await btn.inner_text()
                        if 'Allow' in text or 'Accept' in text or 'Agree' in text:
                            await btn.click()
                            await page.wait_for_timeout(2000)
                            break
                except Exception:
                    pass
                
                # Take a debug screenshot to see what's actually rendering
                await page.screenshot(path=f"debug_fb_ads_{keyword}.png")
                
                all_domains = set()
                
                for i in range(max_scrolls):
                    print(f"Scroll {i+1}/{max_scrolls}...")
                    
                    # Extract all hrefs currently on page, specifically looking for l.facebook.com or external links
                    # We target standard links and specific FB obfuscated link structures
                    links = await page.evaluate("""() => {
                        const anchors = Array.from(document.querySelectorAll('a'));
                        return anchors.map(a => a.href);
                    }""")
                    
                    # Also extract text that might be URLs in the ad copy or buttons
                    texts = await page.evaluate("""() => {
                        // Get text from standard div blocks and span blocks which often hold FB ad text
                        const elements = Array.from(document.querySelectorAll('div[dir="auto"], span[dir="auto"]'));
                        return elements.map(e => e.innerText);
                    }""")
                    
                    # Process anchor links
                    for link in links:
                        if not link:
                            continue
                        
                        # Some links in FB are wrapped in l.facebook.com/l.php?u=...
                        if 'l.facebook.com/l.php' in link:
                            import urllib.parse as up
                            qs = up.parse_qs(urlparse(link).query)
                            if 'u' in qs:
                                actual_url = qs['u'][0]
                                try:
                                    parsed = urlparse(actual_url)
                                    domain = f"{parsed.scheme}://{parsed.netloc}"
                                    all_domains.add(domain)
                                except:
                                    pass
                        elif 'facebook.com' not in link and 'instagram.com' not in link and 'fb.me' not in link:
                            # Direct external links (rare but possible)
                            try:
                                parsed = urlparse(link)
                                if parsed.scheme in ('http', 'https'):
                                    # For shortlinks, keep the full path
                                    if any(sd in parsed.netloc for sd in ['bit.ly', 't.co', 'tinyurl.com', 'shop.app']):
                                        all_domains.add(link)
                                    else:
                                        domain = f"{parsed.scheme}://{parsed.netloc}"
                                        all_domains.add(domain)
                            except:
                                pass
                                
                    # Process text for URLs (often advertisers put their link directly in the copy)
                    for text in texts:
                        if not text: continue
                        urls = re.findall(r'(?:https?:\/\/)?(?:www\.)?[-a-zA-Z0-9@:%._\+~#=]{1,256}\.[a-zA-Z0-9()]{1,6}\b(?:[-a-zA-Z0-9()@:%_\+.~#?&//=]*)', text)
                        for u in urls:
                            if not u.startswith('http'): u = 'https://' + u
                            try:
                                parsed = urlparse(u)
                                if 'facebook' not in parsed.netloc and 'instagram' not in parsed.netloc:
                                    if any(sd in parsed.netloc for sd in ['bit.ly', 't.co', 'tinyurl.com', 'shop.app']):
                                        all_domains.add(u)
                                    else:
                                        domain = f"{parsed.scheme}://{parsed.netloc}"
                                        all_domains.add(domain)
                            except:
                                pass
                    
                    # Scroll down to load more ads
                    # Use keyboard PageDown to be more reliable across different OS/Browser combos than mouse wheel
                    await page.keyboard.press("PageDown")
                    await page.wait_for_timeout(500)
                    await page.keyboard.press("PageDown")
                    await page.wait_for_timeout(4000)
                
                # Filter out common non-store domains
                exclude_domains = ['bit.ly', 'google.com', 'apple.com', 'whatsapp.com', 'youtube.com', 'tiktok.com', 'facebook.com', 'instagram.com', 'messenger.com', 'fb.me']
                cleaned_domains = {d for d in all_domains if not any(ex in d.lower() for ex in exclude_domains)}
                total_found += len(cleaned_domains)
                
                print(f"Found {len(cleaned_domains)} potential external domains from ads. Verifying Shopify...")
                
                # Save to database if verified
                if cleaned_domains:
                        saved_count = 0
                        
                        # We can verify concurrently to speed things up
                        results = await verify_domains_concurrently(cleaned_domains)
                        
                        for domain, is_shopify in zip(cleaned_domains, results):
                            if is_shopify:
                                parsed = urlparse(domain)
                                clean_domain = parsed.netloc or domain
                                if clean_domain.startswith('www.'): clean_domain = clean_domain[4:]
                                clean_domain = clean_domain.replace('https://', '').replace('http://', '').split('/')[0]
                                
                                existing = db.query(models.Store).filter(models.Store.domain == clean_domain).first()
                                if not existing:
                                    new_store = models.Store(
                                        domain=clean_domain,
                                        url=domain, 
                                        source="fb_ads_playwright",
                                        source_channel="fb_ads"
                                    )
                                    db.add(new_store)
                                    saved_count += 1
                                    print(f"Verified & Saved new Shopify store: {clean_domain}")
                                else:
                                    print(f"Store already exists in DB: {clean_domain}")
                        
                        db.commit()
                        total_saved += saved_count
                        print(f"Saved {saved_count} new Shopify stores from FB Ads (Playwright) for '{keyword}'.")
                        if update_progress:
                            update_progress(found_delta=len(cleaned_domains), saved_delta=saved_count, text=f"FB Playwright Search for '{keyword}': Found {len(cleaned_domains)}, Saved {saved_count}")
                else:
                    print("No valid external domains found.")
                    
                # Sleep between keywords
                await asyncio.sleep(3)
                
        except Exception as e:
            print(f"Error scraping FB Ads: {e}")
        finally:
            await browser.close()
            db.close()
            print(f"Playwright Search completed. Total saved: {total_saved}")
            return {"total_found": total_found, "saved": total_saved}
# The following block was duplicating the old logic, removing it.

async def extract_links_from_ad_library(keywords: list, max_scrolls: int = 5, max_pages: int = 2, country: str = 'US', use_api: bool = True, fb_token: str = None, update_progress=None):
    """
    Main entry point. Uses API by default if token is provided, otherwise falls back to Playwright.
    """
    global FB_ACCESS_TOKEN
    token_to_use = fb_token or FB_ACCESS_TOKEN
    if use_api and token_to_use and token_to_use != "YOUR_FB_GRAPH_API_TOKEN":
        # Temporarily override the global token for this run if passed via API
        original_token = FB_ACCESS_TOKEN
        FB_ACCESS_TOKEN = token_to_use
        try:
            return await extract_links_from_ad_library_api(keywords, country=country, max_pages=max_pages, update_progress=update_progress)
        finally:
            FB_ACCESS_TOKEN = original_token
    else:
        print("Using Playwright fallback for FB Ads (No valid API token found or API disabled)")
        return await extract_links_from_ad_library_playwright(keywords, max_scrolls, update_progress=update_progress)

if __name__ == "__main__":
    # Example: Searching for ads mentioning "Shopify" or specific niche products
    keywords = ["clothing brand", "jewelry store"]
    for kw in keywords:
        asyncio.run(extract_links_from_ad_library(kw, max_scrolls=3))
