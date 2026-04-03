import asyncio
import re
from urllib.parse import urlparse
from playwright.async_api import async_playwright
from sqlalchemy.orm import Session
from database import SessionLocal
import models
import httpx

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
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
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
    semaphore = asyncio.Semaphore(10)
    
    async def sem_check(domain):
        async with semaphore:
            return await check_if_shopify(domain, source_channel="tiktok_ads")
            
    tasks = [sem_check(domain) for domain in domains]
    return await asyncio.gather(*tasks)

async def extract_links_from_tiktok_ads(keywords: list, country: str = 'US', max_scrolls: int = 10, update_progress=None):
    print(f"\n--- Starting TikTok Ads Library Search for: {keywords} (Country: {country}) ---")
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        # TikTok has strong anti-bot, stealth-like context is needed
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            viewport={"width": 1280, "height": 800},
            locale="en-US"
        )
        page = await context.new_page()
        db: Session = SessionLocal()
        total_saved = 0
        total_found = 0

        try:
            for keyword in keywords:
                print(f"\n--- Processing keyword: {keyword} ---")
                if update_progress:
                    update_progress(keyword=keyword, text=f"TikTok Search for '{keyword}'")
                
                # TikTok Ads Library URL structure
                import urllib.parse
                encoded_kw = urllib.parse.quote(keyword)
                # target=1 is for ad library, search_type=video
                url = f"https://library.tiktok.com/ads?region={country}&q={encoded_kw}"
                
                await page.goto(url, wait_until="domcontentloaded", timeout=60000)
                print("Loaded TikTok Ads Library page. Waiting for rendering...")
                
                # TikTok is heavy, wait for initial load
                await page.wait_for_timeout(8000)
                
                # Handle possible cookie dialogs or regional popups
                try:
                    buttons = await page.locator("button").all()
                    for btn in buttons:
                        text = await btn.inner_text()
                        if 'Accept' in text or 'Agree' in text or 'Confirm' in text:
                            await btn.click()
                            await page.wait_for_timeout(2000)
                except Exception:
                    pass

                all_domains = set()
                
                for i in range(max_scrolls):
                    print(f"Scroll {i+1}/{max_scrolls}...")
                    
                    # Extract links. TikTok often puts the CTA link in an <a> tag wrapping the card or button
                    links = await page.evaluate("""() => {
                        const anchors = Array.from(document.querySelectorAll('a'));
                        return anchors.map(a => a.href);
                    }""")
                    
                    # Also look in window.__NEXT_DATA__ or similar for hidden domains
                    hidden_domains = await page.evaluate("""() => {
                        const html = document.documentElement.innerHTML;
                        const urls = html.match(/https?:\/\/(www\.)?[-a-zA-Z0-9@:%._\+~#=]{1,256}\.[a-zA-Z0-9()]{2,6}\b/g);
                        return urls || [];
                    }""")
                    
                    for link in links + hidden_domains:
                        if not link: continue
                        if 'tiktok.com' in link or 'byteoversea.com' in link or 'tiktokcdn.com' in link: continue
                        
                        try:
                            parsed = urlparse(link)
                            if parsed.scheme in ('http', 'https'):
                                if any(sd in parsed.netloc for sd in ['bit.ly', 't.co', 'tinyurl.com', 'shop.app', 'tx.to', 'snip.ly']):
                                    all_domains.add(link)
                                else:
                                    domain = f"{parsed.scheme}://{parsed.netloc}"
                                    all_domains.add(domain)
                        except:
                            pass
                    
                    # Scroll down
                    await page.keyboard.press("PageDown")
                    await page.wait_for_timeout(500)
                    await page.keyboard.press("PageDown")
                    await page.wait_for_timeout(5000)
                
                exclude_domains = ['bit.ly', 'google.com', 'apple.com', 'whatsapp.com', 'youtube.com', 'facebook.com', 'instagram.com', 'tiktok.com']
                cleaned_domains = {d for d in all_domains if not any(ex in d.lower() for ex in exclude_domains)}
                total_found += len(cleaned_domains)
                
                print(f"Found {len(cleaned_domains)} potential external domains. Verifying Shopify...")
                
                if cleaned_domains:
                    saved_count = 0
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
                                    source="tiktok_ads",
                                    source_channel="tiktok_ads"
                                )
                                db.add(new_store)
                                saved_count += 1
                                print(f"Verified & Saved new Shopify store: {clean_domain}")
                            else:
                                print(f"Store already exists in DB: {clean_domain}")
                    
                    db.commit()
                    total_saved += saved_count
                    print(f"Saved {saved_count} new Shopify stores from TikTok Ads for '{keyword}'.")
                    if update_progress:
                        update_progress(found_delta=len(cleaned_domains), saved_delta=saved_count, text=f"TikTok Search for '{keyword}': Found {len(cleaned_domains)}, Saved {saved_count}")
                
                await asyncio.sleep(4)
                
        except Exception as e:
            import traceback
            traceback.print_exc()
            print(f"Error scraping TikTok Ads: {e}")
        finally:
            await browser.close()
            db.close()
            print(f"TikTok Search completed. Total saved: {total_saved}")
            return {"total_found": total_found, "saved": total_saved}

if __name__ == "__main__":
    asyncio.run(extract_links_from_tiktok_ads(["fitness equipment"], max_scrolls=2))