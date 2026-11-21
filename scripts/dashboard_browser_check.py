"""Odbiór localhost: schemat API, screenshoty, responsive, keyboard i kontrast tekstu."""
import json
import os
import re
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT=Path(__file__).resolve().parents[1]
os.environ.setdefault('PLAYWRIGHT_BROWSERS_PATH',str(ROOT/'.runtime/dashboard/browsers'))
OUT=ROOT/'docs/dashboard/screenshots'
OUT.mkdir(parents=True,exist_ok=True)
BASE='http://127.0.0.1:8877'


def check_states(value):
    count=0
    if isinstance(value,dict):
        if {'state','source','observed_at','ttl_s'}.issubset(value):
            assert {'value','as_of','age_s','error'}.issubset(value)
            assert value['state'] in ('CONFIRMED','UNCONFIRMED','MISSING')
            count+=1
        count+=sum(check_states(v) for v in value.values())
    elif isinstance(value,list): count+=sum(check_states(v) for v in value)
    return count


if __name__=='__main__':
    report={'api':{},'screens':[],'console_errors':[]}
    with sync_playwright() as p:
        browser=p.chromium.launch(headless=True)
        context=browser.new_context(locale='pl-PL',timezone_id='Europe/Warsaw')
        page=context.new_page()
        page.clock.install()
        page.on('pageerror',lambda e:report['console_errors'].append(str(e)))
        for route in ('health','summary','bots','positions','risk','arena','funding','schedule','alpaca'):
            response=context.request.get(BASE+'/api/'+route)
            assert response.status==200,(route,response.status)
            data=response.json();report['api'][route]={'status':response.status,'data_states':check_states(data)}
        summary=context.request.get(BASE+'/api/summary').json()
        report['source_states']={k:summary[k]['state'] for k in ('account','terminal','positions','realized_today','curve','arena','alpaca')}
        report['source_errors']={k:summary[k]['error'] for k in ('account','terminal','positions','arena','alpaca')}
        for width,height in [(1440,1000),(1024,900),(390,844)]:
            page.set_viewport_size({'width':width,'height':height})
            page.goto(BASE,wait_until='networkidle')
            page.wait_for_selector('.bot-card')
            assert page.locator('.bot-card').count()==6
            assert page.locator('.agent').count()==6
            assert page.locator('.funding-card').count()==4
            assert page.locator('.card:not(:has(.badge))').count()==0
            assert not page.get_by_role('button',name=re.compile(r'BUY|SELL|CLOSE|order|włącz|zamknij|uruchom',re.I)).count()
            overflow=page.evaluate('document.documentElement.scrollWidth>innerWidth')
            assert not overflow,('horizontal_overflow',width)
            page.keyboard.press('Tab')
            assert page.evaluate('document.activeElement.tagName')!='BODY'
            page.locator('h1').click()
            # Kontrast tekstu względem najbliższego nieprzezroczystego tła.
            # Gradienty mają podkład panelu; ręczny przegląd pozostaje częścią odbioru.
            contrast=page.evaluate('''() => {
              const rgb=s=>(s.match(/[\\d.]+/g)||[]).map(Number);
              const lum=c=>{const a=c.slice(0,3).map(v=>{v/=255;return v<=.04045?v/12.92:((v+.055)/1.055)**2.4});return .2126*a[0]+.7152*a[1]+.0722*a[2]};
              let failures=[],checked=0;
              for(const e of document.querySelectorAll('span,p,h1,h2,h3,small,td,th,button,a')){
                if(!e.getClientRects().length||!e.textContent.trim()||e.children.length||e.closest('[hidden]')||e.disabled)continue;
                const style=getComputedStyle(e);if(style.visibility==='hidden')continue;
                let b=e,bg=null;
                while(b){const c=rgb(getComputedStyle(b).backgroundColor);if(c.length===3||c[3]>=.99){bg=c;break;}b=b.parentElement;}
                bg=bg||[11,15,23];if(e.closest('.card')&&b===document.documentElement)bg=[21,28,42];
                const fg=rgb(style.color),a=lum(fg),z=lum(bg),ratio=(Math.max(a,z)+.05)/(Math.min(a,z)+.05);
                const large=parseFloat(style.fontSize)>=24||(parseFloat(style.fontSize)>=18.66&&parseInt(style.fontWeight)>=700);
                checked++;if(ratio<(large?3:4.5))failures.push({text:e.textContent.slice(0,40),ratio:Math.round(ratio*100)/100});
              }return {checked,failures};
            }''')
            assert not contrast['failures'],contrast
            filename=f'dashboard-{width}.png'
            page.screenshot(path=str(OUT/filename),full_page=True)
            report['screens'].append(dict(width=width,height=height,file=filename,no_overflow=True,all_cards_badged=True,contrast=contrast))
        # Sprawdzenie ręcznego odświeżenia bez nawigacji oraz okresowego zapytania.
        requests=[]
        page.on('request',lambda req:requests.append(req.url) if req.url.endswith('/api/summary') else None)
        page.get_by_role('button',name='Odśwież dane panelu').click()
        page.wait_for_function("() => !document.getElementById('refresh').disabled")
        assert requests
        report['manual_refresh']=True
        before=len(requests)
        with page.expect_response(lambda r:r.url.endswith('/api/summary'),timeout=15000):
            page.clock.run_for(46000)
        page.wait_for_function("() => !document.getElementById('refresh').disabled")
        assert len(requests)>before
        report['auto_refresh']=True
        report['console_errors']=list(set(report['console_errors']))
        assert not report['console_errors'],report['console_errors']
        browser.close()
    report['status']='PASS'
    (ROOT/'docs/dashboard/BROWSER_CHECK.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(report,ensure_ascii=False,indent=2))
