import asyncio
import json
import os
import sys
from pathlib import Path
from datetime import datetime, timezone
from contextlib import contextmanager
from .sources import collect, eligible, route
from .model import review, letter
from .forms import apply_form
from .telegram import send_application, notify_confirmation

@contextmanager
def process_lock(profile):
    f = (profile.state/'run.lock').open('a+b')
    locked = False
    try:
        if os.name == 'nt':
            import msvcrt
            if f.tell() == 0:
                f.write(b'0'); f.flush()
            f.seek(0)
            msvcrt.locking(f.fileno(),msvcrt.LK_NBLCK,1)
        else:
            import fcntl
            fcntl.flock(f.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
        locked = True
        yield
    finally:
        if locked and os.name == 'nt':
            f.seek(0)
            msvcrt.locking(f.fileno(),msvcrt.LK_UNLCK,1)
        f.close()

async def run(profile, ledger, send=False):
    if send and not profile.data.get('enable_applications',False):
        raise ValueError('Set enable_applications=true yourself after reviewing a dry run')
    with process_lock(profile):
        jobs, source_errors = await collect(profile)
        report = {'generated_at':datetime.now(timezone.utc).isoformat(),'source_errors':source_errors,'jobs':[]}
        browser = playwright = None
        reviewed = 0
        try:
            for j in jobs:
                if not eligible(profile,j) or ledger.status(j['url']) not in (None,'retry'):
                    continue
                if reviewed >= int(profile.data.get('max_review_per_run',20)):
                    break
                reviewed += 1
                try:
                    decision = await review(profile,j)
                    item = dict(j,decision=decision,status='reviewed')
                    report['jobs'].append(item)
                    if not decision['suitable'] or decision['score'] < int(profile.data.get('min_score',85)):
                        if send:
                            ledger.finish(j['url'],'skipped',str(decision.get('reason','')))
                        continue
                    kind, destination = route(j)
                    if not kind:
                        item['status'] = 'needs_adapter'
                        continue
                    if not send:
                        item['status'] = 'dry_run'
                        continue
                    if not ledger.claim(j['url'],int(profile.data.get('max_daily_applications',5))):
                        item['status'] = 'blocked_by_ledger'
                        continue
                    started_adapter = False
                    try:
                        if kind == 'telegram':
                            with ledger.connect() as db:
                                pause = db.execute("SELECT value FROM controls WHERE name='telegram_until'").fetchone()
                            if pause and datetime.fromisoformat(pause[0]) > datetime.now(timezone.utc):
                                status, detail = 'retry','Telegram still rate-limited'
                            else:
                                proposal = await letter(profile,j)
                                started_adapter = True
                                status, detail = await send_application(profile,ledger,j,destination,proposal)
                        else:
                            if browser is None:
                                from playwright.async_api import async_playwright
                                playwright = await async_playwright().start()
                                browser = await playwright.chromium.launch_persistent_context(str(profile.state/'public-browser'),headless=bool(profile.data.get('headless',False)))
                            started_adapter = True
                            status, detail = await apply_form(profile,browser,j,kind,destination)
                        ledger.finish(j['url'],status,detail)
                        item.update(status=status,detail=detail)
                        await notify_confirmation(profile,ledger,j,status)
                    except Exception as exc:
                        status = 'uncertain' if started_adapter else 'retry'
                        ledger.finish(j['url'],status,type(exc).__name__)
                        item.update(status=status,detail=type(exc).__name__)
                    await asyncio.sleep(max(1,int(profile.data.get('seconds_between_applications',60))))
                except Exception as exc:
                    report['jobs'].append({'url':j['url'],'status':'review_failed','detail':type(exc).__name__})
            if profile.data.get('hh_enabled'):
                # HH remains its own configured adapter; --once does not start
                # a second Telegram poller. Real-apply settings belong to HH.
                if not send:
                    report['hh'] = 'Not invoked in dry-run; run main.py separately in HH dry_run mode'
                elif ledger.is_paused():
                    report['hh'] = 'Not invoked: applications are paused'
                else:
                    root = Path(__file__).resolve().parents[1]
                    proc = await asyncio.create_subprocess_exec(sys.executable,str(root/'main.py'),'--once',cwd=str(root),env={**os.environ,'CAREERPILOT_ONLY_CONFIRMED':'1'})
                    report['hh'] = {'exit_code':await proc.wait(),'note':'Exit code is not proof of submission'}
        finally:
            if browser:
                await browser.close()
            if playwright:
                await playwright.stop()
            (profile.state/'last-run.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
        return report
