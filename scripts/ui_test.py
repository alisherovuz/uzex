"""Browser smoke test: ask a question through the real UI and require a rendered answer card.
Usage: python scripts/ui_test.py http://localhost:8003"""
import asyncio, sys
from playwright.async_api import async_playwright
URL = sys.argv[1]
async def main():
    errors = []
    async with async_playwright() as p:
        b = await p.chromium.launch(executable_path="/usr/bin/google-chrome", args=["--no-sandbox"])
        pg = await b.new_page()
        pg.on("pageerror", lambda e: errors.append(str(e)))
        pg.on("console", lambda m: m.type == "error" and "ERR_TUNNEL" not in m.text and errors.append(m.text))
        await pg.goto(URL)
        for i, q in enumerate(["Qaysi broker eng ko'p bitim tuzgan?", "Сколько сделок в 2024 году?"]):
            await pg.fill("#inp", q + f" #{i}")
            await pg.click("#send")
            await pg.wait_for_selector(".ans >> nth=%d" % i, timeout=90000)
            await pg.wait_for_timeout(1500)
        cards = await pg.locator(".ans").count()
        pill = await pg.locator(".ans .meta").first.inner_text()
        await pg.locator(".ans .bp").first.click()
        proof = await pg.locator(".ans .proof.open").count()
        await b.close()
    ok = cards == 2 and proof == 1 and not errors
    print("UI TEST", "PASS" if ok else "FAIL", {"cards": cards, "proof_open": proof, "pill": pill, "errors": errors})
    sys.exit(0 if ok else 1)
asyncio.run(main())
