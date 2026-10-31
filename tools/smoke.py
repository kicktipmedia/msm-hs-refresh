"""Headless smoke: HS hub, bracket (both views) at 320/390/1280 + home. Exit 1 on any failure."""
import sys, json
from playwright.sync_api import sync_playwright
B = sys.argv[1].rstrip('/'); res = {}; ok = True
with sync_playwright() as p:
    b = p.chromium.launch()
    for w in (320, 390, 1280):
        pg = b.new_page(viewport={'width': w, 'height': 900}); errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
        r1 = pg.goto(B + '/high-school/standings/', wait_until='domcontentloaded'); pg.wait_for_timeout(800)
        pg.click('#v-6a-f'); pg.wait_for_timeout(300)
        tr = pg.evaluate("""[...document.querySelectorAll('.fbx .gm,.fbx .nm,.bk .gm,.bk .nm')].filter(e=>e.offsetParent&&e.scrollWidth>e.clientWidth+1).map(e=>e.textContent)""")
        fv = pg.evaluate("!document.getElementById('p-6a-f').hidden")
        r2 = pg.goto(B + '/high-school/', wait_until='domcontentloaded'); pg.wait_for_timeout(800)
        tr += pg.evaluate("""[...document.querySelectorAll('article.c1 .cd b,article.c1 .cd i,article.c1 .kt,.hsn')].filter(e=>e.offsetParent&&e.scrollWidth>e.clientWidth+1).map(e=>e.textContent)""")
        ov = pg.evaluate('document.documentElement.scrollWidth-innerWidth')
        tk = pg.evaluate("(()=>{var t=document.querySelector('.ticker[data-lvl=hs]');return t?!t.hidden:false})()")
        r3 = pg.goto(B + '/', wait_until='domcontentloaded')
        res[w] = dict(status=[r1.status, r2.status, r3.status], truncated=tr, overflow=ov, ticker_visible=tk, full_view=fv, errors=errs)
        ok &= all(s == 200 for s in res[w]['status']) and not tr and ov <= 0 and fv and not errs
    b.close()
print(json.dumps(res, indent=1)); sys.exit(0 if ok else 1)
