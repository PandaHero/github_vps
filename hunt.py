import json, os, time
import ddddocr
ocr = ddddocr.DdddOcr(show_ad=False)
import asyncio
from playwright.async_api import async_playwright

BASE = "https://wzyp.cn"

async def try_query(page, kw):
    try:
        await page.goto(BASE + "/order", wait_until="domcontentloaded", timeout=20000)
        await page.wait_for_timeout(1500)
        inp = await page.query_selector("input[placeholder*='预留联系方式']")
        if not inp: return None
        await inp.fill(kw)
        await (await page.query_selector("button:has-text('查询订单')")).click()
        for attempt in range(5):
            await page.wait_for_timeout(1800)
            cap_src = await page.evaluate("(() => { const v = [...document.querySelectorAll('img')].filter(i => i.offsetParent && i.src.includes('captchaImg')); return v.length ? v[0].src : null; })()")
            if not cap_src: break
            resp = await page.request.get(cap_src)
            code = ocr.classification(await resp.body())
            cap_input = await page.query_selector("input[placeholder='输入验证码']")
            if cap_input: await cap_input.fill(code)
            for b in await page.query_selector_all("button"):
                if (await b.text_content() or "").strip() == "确定" and await b.is_visible():
                    await b.click(); break
            await page.wait_for_timeout(2200)
            still = await page.evaluate('(() => { const i = document.querySelector("input[placeholder=\\"输入验证码\\"]"); return !!(i && i.offsetParent); })()')
            if not still: break
        await page.wait_for_timeout(2000)
        rows = await page.evaluate("""() => {
            const t = document.querySelector('.arco-table-body, table');
            if (!t) return '';
            const txt = t.innerText;
            return txt.includes('暂无内容') ? '' : txt.slice(0, 3000);
        }""")
        return rows
    except Exception:
        return None

async def main():
    if os.path.exists('trigger.json'):
    keywords = json.loads(open('trigger.json').read())
else:
    keywords = json.loads(os.environ.get('KEYWORDS', '[]'))
    shard = int(os.environ.get("SHARD", "0"))
    total = 20
    my = [k for i, k in enumerate(keywords) if i % total == shard]
    print(f"Shard {shard}: {len(my)} keywords", flush=True)
    hits = []
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        ctx = await browser.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/126.0.0.0 Safari/537.36")
        page = await ctx.new_page()
        for kw in my:
            result = await try_query(page, kw)
            if result and result.strip():
                hits.append({"kw": kw, "result": result[:500], "ts": time.strftime("%Y-%m-%d %H:%M:%S")})
                print(f"[HIT] {kw}: {result[:200]}", flush=True)
            with open("hits.jsonl", "a", encoding="utf-8") as f:
                f.write(json.dumps({"kw": kw, "result": (result or "")[:500]}, ensure_ascii=False) + "\n")
        await browser.close()
    print(f"Shard {shard} done: {len(hits)} hits", flush=True)

asyncio.run(main())
