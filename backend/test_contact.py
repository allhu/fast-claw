import asyncio
import re
from urllib.parse import urlparse, urljoin
import httpx
from bs4 import BeautifulSoup

EMAIL_REGEX = r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}"

async def find_contact_pages(url: str, html: str) -> set:
    soup = BeautifulSoup(html, "html.parser")
    links = set()
    for a in soup.find_all("a", href=True):
        href = a["href"].lower()
        text = a.get_text().lower()
        if "contact" in href or "about" in href or "support" in href or "contact" in text or "about" in text:
            full_url = urljoin(url, a["href"])
            parsed_full = urlparse(full_url)
            parsed_base = urlparse(url)
            if parsed_full.netloc == parsed_base.netloc:
                links.add(full_url)
    return links

def extract_social_links(html: str) -> dict:
    soup = BeautifulSoup(html, "html.parser")
    socials = {"instagram": None, "facebook": None, "whatsapp": None}
    
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if "instagram.com" in href and not socials["instagram"]:
            socials["instagram"] = href
        elif "facebook.com" in href and not socials["facebook"] and "sharer" not in href:
            socials["facebook"] = href
        elif "wa.me" in href or "api.whatsapp.com" in href and not socials["whatsapp"]:
            socials["whatsapp"] = href
            
    return socials

async def scrape_store_contacts(store_url: str) -> dict:
    result = {
        "emails": set(),
        "socials": {"instagram": None, "facebook": None, "whatsapp": None}
    }
    try:
        if not store_url.startswith("http"): store_url = "https://" + store_url
        async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
            headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
            res = await client.get(store_url, headers=headers)
            html = res.text
            result["emails"].update(re.findall(EMAIL_REGEX, html))
            
            socials = extract_social_links(html)
            for k, v in socials.items():
                if v and not result["socials"][k]: result["socials"][k] = v
                    
            contact_pages = await find_contact_pages(store_url, html)
            for page_url in list(contact_pages)[:3]:
                try:
                    c_res = await client.get(page_url, headers=headers)
                    c_html = c_res.text
                    result["emails"].update(re.findall(EMAIL_REGEX, c_html))
                    c_socials = extract_social_links(c_html)
                    for k, v in c_socials.items():
                        if v and not result["socials"][k]: result["socials"][k] = v
                except Exception:
                    pass
    except Exception as e:
        print(f"Error: {e}")
        
    clean_emails = set()
    for e in result["emails"]:
        if not e.endswith((".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", ".wix")):
            clean_emails.add(e)
    result["emails"] = list(clean_emails)
    return result

if __name__ == "__main__":
    res = asyncio.run(scrape_store_contacts("https://colourpop.com"))
    print(res)
