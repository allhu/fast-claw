document.getElementById('extractBtn').addEventListener('click', async () => {
  document.getElementById('status').innerText = 'Extracting links from page...';
  let [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  
  chrome.scripting.executeScript({
    target: { tabId: tab.id },
    function: extractLinksFromPage,
  }, async (results) => {
    if (results && results[0] && results[0].result) {
      const links = results[0].result;
      if (links.length === 0) {
        document.getElementById('status').innerText = 'No external domains found.';
        return;
      }
      
      document.getElementById('status').innerText = `Found ${links.length} domains. Verifying Shopify...`;
      const shopifyLinks = await verifyShopifyLinks(links);
      displayLinks(shopifyLinks);
    } else {
      document.getElementById('status').innerText = 'No links found.';
    }
  });
});

async function verifyShopifyLinks(links) {
  const shopifyLinks = [];
  const statusEl = document.getElementById('status');
  
  for (let i = 0; i < links.length; i++) {
    const url = links[i];
    statusEl.innerText = `Verifying ${i+1}/${links.length}: ${url}`;
    
    try {
      // Use the background script to fetch HTML to bypass CORS restrictions
      const response = await new Promise((resolve) => {
        chrome.runtime.sendMessage({ action: 'fetchHTML', url: url }, resolve);
      });

      if (response && response.success) {
        const text = response.text;
        // Check for common Shopify fingerprints
        if (text.includes('myshopify.com') || text.includes('Shopify.theme') || text.includes('cdn.shopify.com')) {
            shopifyLinks.push(url);
        }
      } else {
        console.warn(`Failed to fetch ${url} via background script:`, response?.error);
      }
    } catch (error) {
        console.error(`Error verifying ${url}:`, error);
    }
  }
  return shopifyLinks;
}

function displayLinks(links) {
  const list = document.getElementById('linkList');
  list.innerHTML = '';
  
  if (links.length === 0) {
    document.getElementById('status').innerText = 'No external domains found.';
    document.getElementById('sendBtn').style.display = 'none';
    return;
  }

  document.getElementById('status').innerText = `Found ${links.length} potential store(s).`;
  document.getElementById('sendBtn').style.display = 'block';

  links.forEach(link => {
    const li = document.createElement('li');
    li.innerHTML = `
      <label>
        <input type="checkbox" class="url-checkbox" value="${link}" checked>
        ${link}
      </label>
    `;
    list.appendChild(li);
  });
}

document.getElementById('sendBtn').addEventListener('click', async () => {
  const checkboxes = document.querySelectorAll('.url-checkbox:checked');
  const urls = Array.from(checkboxes).map(cb => cb.value);
  
  if (urls.length === 0) {
    document.getElementById('status').innerText = 'No URLs selected.';
    return;
  }

  document.getElementById('status').innerText = `Sending ${urls.length} URLs to FastClaw API...`;
  document.getElementById('sendBtn').disabled = true;

  let successCount = 0;
  let failCount = 0;

  for (const url of urls) {
    try {
      const response = await fetch('http://127.0.0.1:8000/api/stores', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          url: url,
          source: 'chrome_extension'
        })
      });
      
      if (response.ok) {
        successCount++;
      } else {
        const data = await response.json();
        console.error(`Failed to save ${url}:`, data);
        failCount++;
      }
    } catch (error) {
      console.error(`Error saving ${url}:`, error);
      failCount++;
    }
  }

  document.getElementById('status').innerText = `Done. Success: ${successCount}, Failed: ${failCount}. (Check API logs for details)`;
  document.getElementById('sendBtn').disabled = false;
});

// This function runs in the context of the web page
function extractLinksFromPage() {
  const allLinks = Array.from(document.querySelectorAll('a')).map(a => a.href);
  
  // Filter out internal links, javascript:, mailto:, etc.
  let externalLinks = allLinks.filter(href => {
    if (!href.startsWith('http')) return false;
    try {
      const urlObj = new URL(href);
      // Ignore google internal links if on google
      if (window.location.hostname.includes('google.com') && urlObj.hostname.includes('google.com')) return false;
      if (urlObj.hostname === window.location.hostname) return false;
      return true;
    } catch(e) { return false; }
  });

  // Extract base domains
  const domains = externalLinks.map(url => {
    try {
      const urlObj = new URL(url);
      // If it's a google search redirect (e.g. /url?q=...), extract the real url
      if (urlObj.hostname.includes('google.com') && urlObj.pathname === '/url') {
        const realUrl = urlObj.searchParams.get('q');
        if (realUrl) {
           const realUrlObj = new URL(realUrl);
           return realUrlObj.origin;
        }
      }
      return urlObj.origin;
    } catch(e) { return null; }
  }).filter(Boolean);
  
  return [...new Set(domains)];
}