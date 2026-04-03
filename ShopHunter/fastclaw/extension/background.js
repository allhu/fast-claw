// FastClaw background service worker
console.log("FastClaw background worker loaded.");

chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  if (request.action === 'fetchHTML') {
    fetch(request.url)
      .then(response => response.text())
      .then(text => sendResponse({ success: true, text: text }))
      .catch(error => sendResponse({ success: false, error: error.toString() }));
    return true; // Keep the message channel open for the async response
  }
});
