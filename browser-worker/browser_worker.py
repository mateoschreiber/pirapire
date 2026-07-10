"""Browser worker using Playwright async API for FastAPI compatibility."""
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import PlainTextResponse, Response
import uvicorn
import os

app = FastAPI(title="Pirapire Browser Worker", docs_url=None, redoc_url=None)

_browser = None
_playwright = None


async def _get_browser():
    global _browser, _playwright
    if _browser is None:
        from playwright.async_api import async_playwright
        _playwright = await async_playwright().start()
        _browser = await _playwright.chromium.launch(headless=True, args=[
            "--no-sandbox", "--disable-setuid-sandbox",
            "--disable-dev-shm-usage", "--disable-gpu",
        ])
    return _browser


@app.on_event("shutdown")
async def shutdown():
    global _browser, _playwright
    if _browser:
        await _browser.close()
    if _playwright:
        await _playwright.stop()


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/fetch")
async def fetch(url: str = Query(...), timeout: int = Query(30000)):
    browser = await _get_browser()
    context = await browser.new_context(
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/131.0.0.0 Safari/537.36",
        viewport={"width": 1920, "height": 1080},
        locale="es-PY",
        timezone_id="America/Asuncion",
    )
    page = await context.new_page()
    try:
        await page.goto(url, wait_until="networkidle", timeout=timeout)
        await page.wait_for_timeout(5000)
        html = await page.content()
        return PlainTextResponse(html, media_type="text/html")
    except Exception as e:
        try:
            html = await page.content()
            return PlainTextResponse(html, media_type="text/html")
        except:
            raise HTTPException(500, str(e))
    finally:
        await context.close()


@app.get("/fetch-esports")
async def fetch_esports():
    """Fetch eSports page from Aposta.LA specifically."""
    browser = await _get_browser()
    context = await browser.new_context(
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/131.0.0.0 Safari/537.36",
        viewport={"width": 1920, "height": 1080},
        locale="es-PY",
    )
    page = await context.new_page()
    try:
        await page.goto("https://aposta.la/bets", wait_until="networkidle", timeout=60000)
        # Wait for content to load
        await page.wait_for_timeout(8000)
        # Click eSports tab if visible
        try:
            esports_btn = await page.wait_for_selector("text=eSports", timeout=5000)
            if esports_btn:
                await esports_btn.click()
                await page.wait_for_timeout(5000)
        except:
            pass
        html = await page.content()
        return PlainTextResponse(html, media_type="text/html")
    except Exception as e:
        return PlainTextResponse(f"Error: {e}", media_type="text/plain")
    finally:
        await context.close()


@app.get("/screenshot")
async def screenshot(url: str = Query(...)):
    browser = await _get_browser()
    context = await browser.new_context(viewport={"width": 1920, "height": 1080})
    page = await context.new_page()
    try:
        await page.goto(url, wait_until="networkidle", timeout=30000)
        await page.wait_for_timeout(5000)
        data = await page.screenshot(full_page=True)
        return Response(content=data, media_type="image/png")
    finally:
        await context.close()


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8080"))
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="warning")
