import os, uvicorn
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import PlainTextResponse

ALLOWED_HOSTS = {'aposta.la', 'api.aposta.la', 'oracleselixir.com', 'www.oracleselixir.com'}
ALLOWED_PATHS = {'/bets', '/apuestas/', '/tools/downloads'}

app = FastAPI(title='Pirapire Browser Worker', docs_url=None, redoc_url=None)

_browser = None
_playwright = None

async def _get_browser():
    global _browser, _playwright
    if _browser is None:
        from playwright.async_api import async_playwright
        _playwright = await async_playwright().start()
        _browser = await _playwright.chromium.launch(headless=True, args=[
            '--no-sandbox', '--disable-setuid-sandbox',
            '--disable-dev-shm-usage', '--disable-gpu',
        ])
    return _browser

@app.get('/health')
async def health():
    return {'status': 'ok'}

def _allowed(url: str) -> bool:
    from urllib.parse import urlparse
    p = urlparse(url)
    return p.hostname in ALLOWED_HOSTS and any(p.path.startswith(ap) for ap in ALLOWED_PATHS)

@app.get('/snapshot')
async def snapshot(target: str = Query(...), timeout: int = Query(60000)):
    if target == 'aposta_football':
        url = 'https://api.aposta.la/apuestas/standard/hoy'
    elif target == 'aposta_esports':
        url = 'https://aposta.la/bets'
    elif target == 'oracle_downloads':
        url = 'https://oracleselixir.com/tools/downloads'
    else:
        raise HTTPException(400, f'Unknown target: {target}')
    if not _allowed(url):
        raise HTTPException(403, f'Host not allowed: {url}')
    browser = await _get_browser()
    context = await browser.new_context(
        user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/131.0.0.0 Safari/537.36',
        viewport={'width': 1920, 'height': 1080},
        locale='es-PY',
    )
    page = await context.new_page()
    try:
        await page.goto(url, wait_until='networkidle', timeout=timeout)
        await page.wait_for_timeout(5000)
        html = await page.content()
        return PlainTextResponse(html, media_type='text/html')
    except Exception as e:
        try:
            html = await page.content()
            return PlainTextResponse(html, media_type='text/html')
        except:
            raise HTTPException(500, str(e))
    finally:
        await context.close()

if __name__ == '__main__':
    uvicorn.run(app, host='0.0.0.0', port=int(os.environ.get('PORT', '8080')), log_level='warning')
