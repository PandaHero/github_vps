# -*- coding: utf-8 -*-
# 在 GitHub Actions 上运行的卡密提取器
# 目标：wzyp.cn 的 154 个免密单（Order/result 页直接显示卡密）
import asyncio, json, os, re, time, sys
sys.path.insert(0, ".")
from playwright.async_api import async_playwright

BASE = "https://wzyp.cn"
KW = "123456@qq.com"

# 内嵌全部免密单数据（从 order_123456_all.json 提取的 222 个免密单）
FREE_ORDERS = json.loads(os.environ.get("FREE_ORDERS", "[]"))

async def main():
    print(f"目标: {len(FREE_ORDERS)} 个免密单", flush=True)
    
    results = []
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True, args=["--no-sandbox"])
        ctx = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
            locale="zh-CN")
        page = await ctx.new_page()
        
        for i, o in enumerate(FREE_ORDERS):
            tno = o.get("trade_no", "")
            goods = o.get("goods_name", "")[:40]
            
            try:
                # 直接访问 result 页（不需要登录，只需要会话）
                # 先访问 /order 建立会话
                if i == 0:
                    await page.goto(f"{BASE}/order", wait_until="domcontentloaded", timeout=30000)
                    await page.wait_for_timeout(3000)
                    # 填联系方式并查询
                    inp = await page.query_selector("input[placeholder*='预留联系方式']")
                    if inp:
                        await inp.fill(KW)
                        btn = await page.query_selector("button:has-text('查询订单')")
                        if btn:
                            await btn.click()
                            await page.wait_for_timeout(3000)
                
                # 跳 result 页
                await page.goto(f"{BASE}/order/result/{tno}", wait_until="domcontentloaded", timeout=25000)
                await page.wait_for_timeout(3000)
                
                txt = await page.evaluate("() => document.body.innerText")
                
                if "访问受限" in txt or "高风险" in txt:
                    print(f"[{i+1}] {tno} BLOCKED - 停止", flush=True)
                    break
                
                if "订单不存在" in txt:
                    continue
                
                # 提取卡密
                card_match = re.search(r"您购买的卡密\s*(\d+)\s*张,已发货\s*(\d+)\s*张", txt)
                if card_match:
                    cards = re.findall(r"第\d+张\s*\n复制\s*\n([^\n]+)", txt)
                    qq = re.search(r"QQ：\s*\n?(\d+)", txt)
                    result = {
                        "trade_no": tno, "kw": KW, "goods_name": goods,
                        "total_cards": int(card_match.group(1)),
                        "sent": int(card_match.group(2)),
                        "cards": cards,
                        "seller_qq": qq.group(1) if qq else "",
                        "ts": time.strftime("%Y-%m-%d %H:%M:%S")
                    }
                    results.append(result)
                    with open("cards_result.jsonl", "a", encoding="utf-8") as f:
                        f.write(json.dumps(result, ensure_ascii=False) + "\n")
                    print(f"[{i+1}] ✓ {tno} | {goods[:30]} | {cards[0][:60] if cards else '(空)'}", flush=True)
                elif "安全密码" in txt:
                    print(f"[{i+1}] {tno} | 需安全密码", flush=True)
                else:
                    print(f"[{i+1}] {tno} | {txt[:80]}", flush=True)
                    
                await asyncio.sleep(random.uniform(1, 3))
            except Exception as e:
                print(f"[{i+1}] {tno} ERR: {str(e)[:60]}", flush=True)
                await asyncio.sleep(2)
        
        await browser.close()
    
    print(f"\n完成: {len(results)} 个订单卡密提取", flush=True)
    
    # 保存到 GITHUB_OUTPUT
    with open(os.environ.get("GITHUB_OUTPUT", "/dev/null"), "a") as f:
        f.write(f"extracted={len(results)}\n")

import random
asyncio.run(main())
