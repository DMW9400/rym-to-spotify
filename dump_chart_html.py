#!/usr/bin/env -S uv run

import sys
import asyncio
from nodriver import start, Browser, Tab

async def dump_chart(url):
    for attempt in range(3):
        try:
            browser: Browser = await start(sandbox=False, user_data_dir="/tmp/mcp-chrome-profile")
            break
        except Exception:
            if attempt == 2:
                raise
            print(f"Browser connection failed (attempt {attempt + 1}/3), retrying...")
            await asyncio.sleep(2)

    tab: Tab = await browser.get(url)
    await tab.wait(40)

    try:
        page_source = await tab.get_content()
    except Exception:
        await asyncio.sleep(1)
        page_source = await tab.evaluate("document.documentElement.outerHTML")

    with open("chart_dump.html", "w", encoding="utf-8") as f:
        f.write(page_source)

    print(f"Saved page HTML to chart_dump.html ({len(page_source)} bytes)")
    browser.stop()

if __name__ == "__main__":
    url = sys.argv[1] if len(sys.argv) > 1 else "https://rateyourmusic.com/charts/top/album/2010s/g:brazilian%2dmusic/"
    asyncio.run(dump_chart(url))
