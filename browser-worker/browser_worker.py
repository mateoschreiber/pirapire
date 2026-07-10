"""Browser worker for Aposta.LA eSports/LoL pages. Internal only - no port exposed."""
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import PlainTextResponse
import uvicorn
import os

app = FastAPI(title="Pirapire Browser Worker", docs_url=None, redoc_url=None)

@app.get("/health")
async def health():
    return {"status": "ok"}

@app.get("/fetch")
async def fetch(url: str = Query(...), wait_selector: str = Query(None), timeout: int = Query(30000)):
    """Fetch a rendered page using headless Chromium."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        raise HTTPException(500, "Playwright not installed")
    
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True, args=[
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-dev-shm-usage",
                "--disable-gpu",
                "--disable-web-security",
                "--disable-features=VizDisplayCompositor",
            ])
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
                viewport={"width": 1920, "height": 1080},
                locale="es-PY",
                timezone_id="America/Asuncion",
            )
            page = context.new_page()
            page.goto(url, wait_until="networkidle", timeout=timeout)
            
            if wait_selector:
                page.wait_for_selector(wait_selector, timeout=timeout)
            
            # Wait a bit for dynamic content
            page.wait_for_timeout(3000)
            
            html = page.content()
            browser.close()
            return PlainTextResponse(html, media_type="text/html")
    except Exception as e:
        raise HTTPException(500, str(e))

@app.get("/screenshot")
async def screenshot(url: str = Query(...), full_page: bool = Query(True)):
    """Take a screenshot for debugging."""
    from playwright.sync_api import sync_playwright
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--no-sandbox", "--disable-setuid-sandbox"])
        page = browser.new_page()
        page.goto(url, wait_until="networkidle", timeout=30000)
        page.wait_for_timeout(3000)
        screenshot = page.screenshot(full_page=full_page)
        browser.close()
        from fastapi.responses import Response
        return Response(content=screenshot, media_type="image/png")

if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8080"))
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="warning")
