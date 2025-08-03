from asyncio import CancelledError
from pathlib import Path
from patchright._impl._errors import TargetClosedError # noqa
from patchright.async_api import async_playwright

STATE_PATH = Path(__file__).parent / 'state.json'


async def save_state():
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(
            headless=False,
            args=[
                '--disable-blink-features=AutomationControlled',
                '--disable-web-security'
            ],
        )
        context = await browser.new_context(
            ignore_https_errors=True, java_script_enabled=True, bypass_csp=True, locale='ru-RU', color_scheme='dark',  timezone_id='Europe/Moscow',
            permissions=['background-sync', 'clipboard-read', 'clipboard-write', 'geolocation', 'microphone', 'notifications', 'storage-access'],
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36 Edg/140.0.0.0',
        )
        page = await context.new_page()
        page.on('dialog', lambda dialog: dialog.accept())
        await page.goto('https://huggingface.co/login', wait_until='commit', referer='https://huggingface.co')
        try:
            print('логинься и закрывай браузер')
            await page.wait_for_timeout(30 * 60 * 1000)
        except (CancelledError, KeyboardInterrupt, TargetClosedError):
            await context.storage_state(path=STATE_PATH, indexed_db=True)
        except Exception as e:
            print(f'ошибка: {e}')
        finally:
            await context.close()
            await browser.close()
            await playwright.stop()
        result = f'данные сохранены в: {STATE_PATH.resolve()}' if STATE_PATH.is_file() else 'данные не сохранены, повтори попытку'
        print(result)


if __name__ == '__main__':
    from asyncio import run

    run(save_state())