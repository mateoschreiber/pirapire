"""Smart browser worker for Aposta.LA LoL discovery."""
import os, uvicorn, json, time
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import PlainTextResponse, JSONResponse
from urllib.parse import urlparse

ALLOWED_HOSTS = {'aposta.la', 'api.aposta.la', 'www.aposta.la'}

# Phase 4B2: public, visible football pages allowed for the render fallback.
# Public, CAPTCHA-free pages only; never private/undocumented endpoints.
RENDER_ALLOWED_HOSTS = {'www.thesportsdb.com', 'thesportsdb.com'}

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
    p = urlparse(url)
    return p.hostname in ALLOWED_HOSTS

@app.get('/discover-lol')
async def discover_lol():
    """Discover LoL API endpoints by intercepting XHR/fetch requests."""
    browser = await _get_browser()
    
    xhr_calls = []
    
    async def on_request(request):
        if request.resource_type in ('xhr', 'fetch'):
            xhr_calls.append({
                'url': request.url,
                'method': request.method,
                'resource_type': request.resource_type,
                'headers': dict(request.headers),
            })
    
    async def on_response(response):
        for i, xhr in enumerate(xhr_calls):
            if xhr['url'] == response.url and 'status' not in xhr:
                xhr['status'] = response.status
                xhr['content_type'] = response.headers.get('content-type', '')
                try:
                    body = await response.text()
                    if len(body) < 50000:
                        xhr['body_preview'] = body[:500]
                except:
                    pass

    context = await browser.new_context(
        user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/131.0.0.0 Safari/537.36',
        viewport={'width': 1920, 'height': 1080},
        locale='es-PY',
    )
    page = await context.new_page()
    page.on('request', on_request)
    page.on('response', on_response)
    
    try:
        # Step 1: Load page
        await page.goto('https://aposta.la/bets', wait_until='domcontentloaded', timeout=30000)
        await page.wait_for_timeout(3000)
        
        # Step 2: Look for eSports in nav
        nav_links = await page.evaluate('''() => {
            const links = document.querySelectorAll('a, button, [role="tab"]');
            const found = [];
            links.forEach(l => {
                const text = l.textContent?.trim() || '';
                const href = l.getAttribute('href') || '';
                if (text) found.push({text: text.substring(0,30), href: href.substring(0,80)});
            });
            return found;
        }''')
        
        # Step 3: Try to click eSports if found
        esports_found = False
        for link in nav_links:
            if 'esport' in link['text'].lower() or 'esport' in link['href'].lower():
                esports_found = True
                break
        
        # Step 4: Navigate via hash if possible
        if not esports_found:
            try:
                await page.evaluate('window.location.hash = "sports-hub/esports"')
                await page.wait_for_timeout(5000)
            except:
                pass
        
        # Step 5: Capture state
        page_content = await page.content()
        
    except Exception as e:
        page_content = f"Error: {e}"
    finally:
        await context.close()
    
    # Filter interesting XHR calls
    interesting = []
    for xhr in xhr_calls:
        url = xhr.get('url', '')
        if any(kw in url.lower() for kw in ['apuesta', 'deporte', 'sport', 'esport', 'event', 'jogo', 'league', 'lol', 'game', 'match', 'tournament', 'competition', 'mercado', 'odd']):
            interesting.append(xhr)
    
    return JSONResponse({
        'xhr_count': len(xhr_calls),
        'interesting_xhr': len(interesting),
        'xhr_samples': interesting[:20],
        'nav_links': nav_links[:30],
        'esports_found': esports_found,
        'page_size': len(page_content) if isinstance(page_content, str) else 0,
    })

@app.get('/snapshot')
async def snapshot(target: str = Query(...), timeout: int = Query(60000)):
    allowed_targets = {
        'aposta_football': 'https://api.aposta.la/apuestas/standard/hoy',
        'aposta_world_cup': 'https://api.aposta.la/apuestas/deporte/1/4',
        'aposta_lol': 'https://aposta.la/bets',
    }
    url = allowed_targets.get(target)
    if not url:
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
    
    # Capture XHR for LoL target
    xhr_data = []
    if target == 'aposta_lol':
        async def capture_xhr(response):
            if response.request.resource_type in ('xhr', 'fetch'):
                try:
                    body = await response.text()
                    if len(body) < 100000:
                        ct = response.headers.get('content-type', '')
                        if 'json' in ct:
                            try:
                                parsed = json.loads(body)
                                xhr_data.append({'url': response.url, 'status': response.status, 'keys': list(parsed.keys()) if isinstance(parsed, dict) else f'list({len(parsed)})', 'preview': str(parsed)[:300]})
                            except:
                                xhr_data.append({'url': response.url, 'status': response.status, 'body_len': len(body)})
                except:
                    pass
        page.on('response', capture_xhr)
    
    try:
        await page.goto(url, wait_until='domcontentloaded', timeout=30000)
        if target == 'aposta_lol':
            # Wait for Angular to load
            await page.wait_for_timeout(5000)
            # Try hash navigation to esports
            try:
                await page.evaluate('window.location.hash = "sports-hub/esports"')
                await page.wait_for_timeout(5000)
            except:
                pass
            # Wait for any content
            try:
                await page.wait_for_selector('app-root, .sport-list, .event-card, .match-row', timeout=10000)
            except:
                pass
            await page.wait_for_timeout(3000)
        else:
            await page.wait_for_timeout(2000)
        
        html = await page.content()
        result = {'html': html, 'xhr': xhr_data[:30]} if target == 'aposta_lol' else html
        return PlainTextResponse(html, media_type='text/html') if target != 'aposta_lol' else JSONResponse(result)
    except Exception as e:
        return JSONResponse({'error': str(e), 'xhr': xhr_data[:30]}, status_code=500)
    finally:
        await context.close()

@app.get('/render')
async def render(url: str = Query(...), timeout: int = Query(30000)):
    """Render a single public, allowlisted page and return its HTML.

    Probe mode: read-only, sequential, no CAPTCHA solving, no login, and no
    loop retries. One navigation per call.
    """
    p = urlparse(url)
    if p.scheme not in ('http', 'https') or p.hostname not in RENDER_ALLOWED_HOSTS:
        raise HTTPException(403, f'Host not allowed: {url}')
    browser = await _get_browser()
    context = await browser.new_context(
        user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/131.0.0.0 Safari/537.36',
        viewport={'width': 1920, 'height': 1080},
        locale='es-PY',
    )
    page = await context.new_page()
    try:
        await page.goto(url, wait_until='domcontentloaded', timeout=min(timeout, 45000))
        await page.wait_for_timeout(3000)
        html = await page.content()
        return JSONResponse({'url': url, 'html': html, 'length': len(html)})
    except Exception as e:
        return JSONResponse({'url': url, 'error': str(e), 'html': None}, status_code=502)
    finally:
        await context.close()

if __name__ == '__main__':
    uvicorn.run(app, host='0.0.0.0', port=int(os.environ.get('PORT', '8080')), log_level='info')
