from asyncio import sleep, create_task, CancelledError, gather
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from json import dumps
from os import environ
from pathlib import Path
from random import randint, choice, uniform, randrange

from fastapi import FastAPI
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from patchright.async_api import (
    async_playwright,
    ViewportSize,
    Geolocation,
    Page,
    BrowserContext,
    Browser, Playwright
)
from prlps_fakeua import UserAgent
from starlette.responses import Response

# задай интервал обновления в часах
UPDATE_INTERVAL_IN_HOURS = 10

# создай секрет SPACES и добавь в него ссылки на спейсы, каждую с новой строки
SPACES = [space.strip() for space in environ.get('SPACES', '').strip().split('\n') if space.strip()]

if not SPACES:
    from sys import exit
    msg = 'создай секрет SPACES и добавь в него ссылки на спейсы, каждую с новой строки!!!\nпосле этого перезапусти спейс.'
    exit(msg)
    raise RuntimeError(msg)

user_agent = UserAgent(
    browsers=['chrome', 'edge'],
    os='windows',
    min_version=138,
    platforms='pc',
    fallback='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36 Edg/140.0.0.0',
)


def random_params():
    widths = [1366, 1536, 1440, 1920, 2560]
    w = choice(widths)
    h = (w * 9) // 16
    screen = ViewportSize(width=w, height=h)
    viewport = ViewportSize(width=w, height=h - randrange(41, 101, 2))
    geo = Geolocation(
        latitude=float('47.' + str(randint(123, 754))),
        longitude=float('-122.' + str(randint(123, 754)))
    )
    return screen, viewport, geo


async def new_context(headless: bool = False, slow_mo: int = None):
    playwright = await async_playwright().start()
    screen, viewport, geo = random_params()
    browser = await playwright.chromium.launch(
        headless=headless,
        args=[
            '--disable-blink-features=AutomationControlled',
            '--disable-web-security'
        ],
        slow_mo=slow_mo
    )
    context = await browser.new_context(
        screen=screen,
        viewport=viewport,
        ignore_https_errors=True,
        java_script_enabled=True,
        bypass_csp=True,
        user_agent=user_agent.random,
        locale='en-US',
        permissions=['notifications', 'geolocation'],
        geolocation=geo,
        color_scheme='dark',
        timezone_id='America/Los_Angeles',
        accept_downloads=True,
        storage_state=None,  # можно сохранить состояние браузера или использовать уже сохраненный из файла
    )
    page = await context.new_page()

    return playwright, browser, context, page


async def go_to_page(url: str, page: Page):
    await page.goto(url, wait_until='commit')
    await page.wait_for_timeout(5 * 1000)


async def shutdown(playwright: Playwright, page: Page, context: BrowserContext, browser: Browser):
    await playwright.stop()
    try:
        await page.close()
        await context.close()
        await browser.close()
    except:
        pass


async def awake(url: str, headless: bool = False, slow_mo: int = None) -> str:
    playwright, browser, context, page = await new_context(headless=headless, slow_mo=slow_mo)
    try:
        await go_to_page(url, page)

        running_status = page.get_by_text('Running', exact=True)
        starting_status = page.get_by_text('Starting', exact=True)
        if (await running_status.is_visible(timeout=5000) or
                await starting_status.is_visible(timeout=5000)):
            return 'running'

        error_title = page.get_by_role('heading', name='runtime error', exact=True)
        error_status = page.get_by_text('Runtime error', exact=True)

        if (await error_title.is_visible(timeout=5000) or
                await error_status.is_visible(timeout=5000)):
            return 'runtime_error'

        paused_title = page.get_by_text('This Space has been paused by')
        paused_status = page.get_by_text('Paused', exact=True)
        if (await paused_title.is_visible(timeout=5000) or
                await paused_status.is_visible(timeout=5000)):
            return 'paused'

        unavailable_title = page.get_by_role('heading', name='404')
        unavailable_description = page.get_by_text('Sorry, we can\'t find the page')
        if (await unavailable_title.is_visible(timeout=5000) or
                await unavailable_description.is_visible(timeout=5000)):
            return 'unavailable'

        sleeping_status = page.get_by_text('Sleeping', exact=True)
        restart_button = page.get_by_role('button', name='Restart this Space')
        sleeping_description = page.get_by_text('This Space is sleeping due to')
        if (await sleeping_status.is_visible(timeout=5000) or
                await restart_button.is_visible(timeout=5000) or
                await sleeping_description.is_visible(timeout=5000)):
            try:
                await restart_button.click(delay=round(uniform(0.3, 1.3) * 1000))
                starting_status = await page.get_by_text('Starting', exact=True).is_visible(timeout=10000)
                if starting_status:
                    return 'success'
                else:
                    return 'error'
            except:
                return 'error'
    except Exception as e:
        print(e)
        return 'error'
    finally:
        await shutdown(playwright, page, context, browser)


def hours_repeat_interval(hours: int = UPDATE_INTERVAL_IN_HOURS) -> int:
    return max(1, min(hours, 43))


app_state = {
    'status': 'готово к запуску',
    'last_update': datetime.now(),
    'task_running': False,
    'running_spaces': set({}),
    'error_spaces': set({}),
    'runtime_error_spaces': set({}),
    'paused_by_owner': set({}),
    'require_authorization': set({}),
}


async def awake_with_retry(space_url: str, max_retries=3):
    for state_set in ['error_spaces', 'runtime_error_spaces', 'paused_by_owner', 'require_authorization',
                      'running_spaces']:
        if space_url in app_state[state_set]:
            app_state[state_set].remove(space_url)
    for attempt in range(max_retries):
        app_state['status'] = f'попытка {attempt + 1}/{max_retries}'
        try:
            result = await awake(space_url, headless=False, slow_mo=None)
            if result == 'error':
                app_state['error_spaces'].add(space_url)
            if result == 'paused':
                app_state['paused_by_owner'].add(space_url)
                return False
            elif result == 'unavailable':
                app_state['require_authorization'].add(space_url)
                return False
            elif result == 'runtime_error':
                app_state['runtime_error_spaces'].add(space_url)
                return False
            elif result == 'running':
                app_state['running_spaces'].add(space_url)
                return True
            elif result == 'success':
                app_state['running_spaces'].add(space_url)
                return True
        except Exception as e:
            app_state['status'] = f'ошибка при попытке {attempt + 1}: {str(e)}'
    app_state['status'] = 'все попытки завершились ошибкой'
    return False


async def periodic_token_updater(hours_repeat: int):
    while True:
        app_state['task_running'] = True
        tasks = []
        try:
            for space_url in SPACES:
                tasks.append(awake_with_retry(space_url))
            results = await gather(*tasks)
            app_state['status'] = 'всё успешно завершено' if all(results) else (
                'все попытки завершились ошибкой' if not any(results) else 'некоторые попытки завершились ошибкой'
            )
            app_state['last_update'] = datetime.now()
        except Exception as e:
            app_state['status'] = f'критическая ошибка: {str(e)}'
        finally:
            app_state['task_running'] = False

        await sleep(hours_repeat * 3600 + randint(-60, 60))  # вместо APScheduler!


@asynccontextmanager
async def lifespan(_: FastAPI):
    task = create_task(periodic_token_updater(hours_repeat_interval()))
    yield
    task.cancel()
    try:
        await task
    except CancelledError:
        pass


app = FastAPI(lifespan=lifespan)
static_path = Path(__file__).parent / 'static'
if static_path.is_dir():
    app.mount('/assets', StaticFiles(directory=static_path / 'assets'), name='assets')


def format_app_state(as_json: bool = False) -> dict | str:
    formated = {
        'task_running': app_state['task_running'],
        'status': app_state['status'],
        'last_update': app_state['last_update'].isoformat() if app_state['last_update'] else None,
        'next_update': (app_state['last_update'] + timedelta(hours=hours_repeat_interval())).isoformat() if app_state[
            'last_update'] else None,
        'running_spaces': list(app_state['running_spaces']),
        'error_spaces': list(app_state['error_spaces']),
        'runtime_error_spaces': list(app_state['runtime_error_spaces']),
        'paused_by_owner': list(app_state['paused_by_owner']),
        'require_authorization': list(app_state['require_authorization']),
    }
    return dumps(formated, ensure_ascii=False, indent=4) if as_json else formated


@app.get('/')
async def get_status():
    info = (f'<pre style="position:absolute; width:fit-content; display:block; bottom:0; height:100px; '
            f'box-sizing:border-box; left:50%; transform:translateX(-50%); z-index: 999; color: #6f6f6f;">'
            f'{format_app_state(as_json=True)}</pre>')

    index_file = static_path / 'index.html'
    content = index_file.read_text(encoding='utf-8') if index_file.is_file() else ''
    pos = content.find('</html>')

    if pos != -1:
        new_content = content[:pos] + info + content[pos:]
    else:
        new_content = content + info

    return HTMLResponse(new_content)


class JSONResponse(Response):
    media_type = 'application/json'

    def __init__(self, content: str | dict | list | bytes) -> None:
        super().__init__(
            content=content,
            status_code=200,
            headers={},
            media_type=self.media_type,
            background=None
        )

    def render(self, content) -> bytes:
        return dumps(
            content,
            ensure_ascii=False,
            allow_nan=False,
            indent=4,
            separators=(',', ':'),
        ).encode('utf-8')


@app.get('/status.json')
async def get_status():
    return JSONResponse(format_app_state(as_json=False))


@app.get('/{full_path:path}')
async def redirect():
    return RedirectResponse(url='/')


@app.post('/{full_path:path}')
async def post_not_allowed():
    return JSONResponse({
        'error': 'Method not allowed',
        'status': 'error',
    })


if __name__ == '__main__':
    from uvicorn import run as uvicorn_run

    uvicorn_run(app, host='0.0.0.0', port=7860)
