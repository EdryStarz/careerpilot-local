import hashlib
import re
from urllib.parse import urlsplit
from .sources import ATS_HOSTS
from .model import letter

SUCCESS = re.compile(r'application (?:has been |was )?(?:successfully )?(?:submitted|received)|received your application|thank you for (?:applying|your application)|thanks for applying|your response has been recorded|ответ записан',re.I)
LEGAL = re.compile(r'consent|agree|terms|privacy|passport|bank|соглас|паспорт|оплат',re.I)
GATE = re.compile(r'verify.{0,15}human|complete.{0,15}captcha|sign in|log in|pay to apply',re.I)
LABEL = '''e=>{const g=e.closest('.ashby-application-form-field-entry,.application-question,[role="listitem"],fieldset');return (g?.querySelector('.ashby-application-form-question-title,.application-label,[role="heading"],legend')?.innerText || [...(e.labels||[])].map(l=>l.innerText).join(' ') || e.getAttribute('aria-label') || e.name || e.id || '').trim()}'''

async def apply_form(profile, context, j, kind, url):
    page = await context.new_page()
    started = False
    proof = profile.state / ('proof-' + hashlib.sha256(j['url'].encode()).hexdigest()[:16] + '.png')
    try:
        await page.goto(url,wait_until='domcontentloaded',timeout=60000)
        p = urlsplit(page.url)
        if p.hostname not in ATS_HOSTS | {'forms.gle','docs.google.com'}:
            return 'needs_user','Unsupported redirect'
        for step in range(8):
            await page.locator('body').wait_for(state='visible')
            body = await page.locator('body').inner_text()
            if SUCCESS.search(body):
                if started:
                    await page.screenshot(path=str(proof),full_page=True)
                    return 'submitted','Positive confirmation; proof=' + str(proof)
                return 'needs_user','Success text appeared before this submission; do not infer ownership'
            if GATE.search(body) or await page.locator('iframe[title*="challenge" i]:visible, iframe[src*="bframe"]:visible').count():
                return 'needs_user','Login or interactive verification'
            if kind == 'ats' and not await page.locator('input:visible,textarea:visible,select:visible').count():
                apply = page.get_by_role('link',name=re.compile(r'^Apply (?:for this job|now)$',re.I))
                if not await apply.count():
                    apply = page.get_by_role('button',name=re.compile(r'^Apply(?: for this job| now)?$',re.I))
                if await apply.count() == 1:
                    await apply.click()
                    await page.wait_for_load_state('domcontentloaded')
            # Upload first; parsing can replace fields. Wait for the visible
            # completion marker on Lever, and then overwrite known facts.
            for f in await page.locator('input[type="file"]').all():
                label = await f.evaluate(LABEL)
                if re.search(r'resume|cv|резюме',label,re.I):
                    await f.set_input_files(str(profile.resume))
                    if 'lever.co' in p.hostname:
                        await page.get_by_text('Success!',exact=True).first.wait_for(state='visible',timeout=60000)
            missing = []
            if kind == 'google':
                groups = page.get_by_role('listitem')
                for g in await groups.all():
                    if not await g.is_visible():
                        continue
                    q = await g.inner_text()
                    heading = g.get_by_role('heading')
                    if await heading.count():
                        q = await heading.first.inner_text()
                    choices = g.get_by_role('radio')
                    multiple = False
                    if not await choices.count():
                        choices = g.get_by_role('checkbox')
                        multiple = True
                    if await choices.count():
                        options = [await c.get_attribute('aria-label') or '' for c in await choices.all()]
                        answer = profile.answer(q,options,j['title'])
                        selected = answer if isinstance(answer,list) else [answer]
                        if answer and all(x in options for x in selected) and (multiple or len(selected) == 1):
                            for index, option in enumerate(options):
                                control = choices.nth(index)
                                checked = await control.get_attribute('aria-checked') == 'true'
                                if (option in selected) != checked and (multiple or option in selected):
                                    await control.click()
                        elif '*' in q or 'Required' in q:
                            missing.append(q)
                        continue
                    f = g.get_by_role('textbox')
                    answer = profile.answer(q,title=j['title'])
                    if await f.count() == 1 and answer:
                        await f.fill(answer)
                    elif '*' in q or 'Required' in q:
                        missing.append(q)
            else:
                for f in await page.locator('input:not([type="hidden"]):not([type="file"]):not([type="submit"]),textarea,select').all():
                    if not await f.is_visible() or not await f.is_enabled():
                        continue
                    label = await f.evaluate(LABEL)
                    required = await f.evaluate("""e=>e.required || e.getAttribute('aria-required')==='true' || !!e.closest('.application-question,.ashby-application-form-field-entry')?.querySelector('.required,[class*="_required_"]')""")
                    type_ = await f.get_attribute('type')
                    if LEGAL.search(label):
                        if required:
                            missing.append(label or 'Required legal/choice control')
                        continue
                    if type_ in ('checkbox','radio'):
                        group = f.locator('xpath=ancestor::*[self::fieldset or contains(@class,"application-question") or contains(@class,"ashby-application-form-field-entry")][1]')
                        if await group.count() != 1:
                            if required:
                                missing.append(label or 'Unscoped choice')
                            continue
                        controls = group.locator('input[type="'+type_+'"]')
                        options = [await c.evaluate("e=>[...(e.labels||[])].map(l=>l.innerText).join(' ').trim() || e.getAttribute('aria-label') || e.value") for c in await controls.all()]
                        answer = profile.answer(label,options,j['title'])
                        selected = answer if isinstance(answer,list) else [answer]
                        if answer and (type_ == 'checkbox' or len(selected) == 1):
                            for index, option in enumerate(options):
                                if option in selected:
                                    await controls.nth(index).check()
                                elif type_ == 'checkbox':
                                    await controls.nth(index).uncheck()
                        elif required:
                            missing.append(label or 'Required choice needs confirmed answer')
                        continue
                    if await f.get_attribute('role') == 'combobox':
                        await f.click()
                        choices = page.get_by_role('option').filter(visible=True)
                        options = [await c.inner_text() for c in await choices.all()]
                        answer = profile.answer(label,options,j['title'])
                        if isinstance(answer,str) and options.count(answer) == 1:
                            await choices.nth(options.index(answer)).click()
                        else:
                            await f.press('Escape')
                            if required:
                                missing.append(label or 'Required dropdown: needs reviewed option mapping')
                        continue
                    answer = profile.answer(label,title=j['title'])
                    tag = await f.evaluate('e=>e.tagName')
                    if tag == 'TEXTAREA' and re.search(r'cover letter|сопроводитель',label,re.I):
                        answer = await letter(profile,j)
                    if answer:
                        if tag == 'SELECT':
                            await f.select_option(label=answer)
                        else:
                            await f.fill(answer)
                    elif required and not await f.input_value():
                        missing.append(label or 'Unlabelled required field')
            if missing:
                return 'needs_user','Required answers: ' + '; '.join(missing)
            if await page.locator('input:invalid,textarea:invalid,select:invalid').count():
                return 'needs_user','Native form validation failed; no submit click'
            body = await page.locator('body').inner_text()
            if re.search(r'by (?:submitting|clicking).{0,180}(?:agree|consent|terms)',body,re.I|re.S):
                return 'needs_user','Submission accepts an agreement; user action needed'
            if kind == 'google':
                next_ = page.get_by_role('button',name=re.compile(r'^Next$|^Далее$'))
                if await next_.count() == 1:
                    await next_.click()
                    continue
            submit = page.get_by_role('button',name=re.compile(r'^(Submit Application|Send Application|Submit|Отправить)$',re.I))
            if await submit.count() != 1 or not await submit.is_enabled():
                return 'needs_user','No unique enabled submit control'
            started = True
            await submit.click()
            await page.get_by_text(SUCCESS).first.wait_for(state='visible',timeout=90000)
            await page.screenshot(path=str(proof),full_page=True)
            return 'submitted','Positive confirmation; proof=' + str(proof)
        return 'needs_user','Form step limit reached'
    except Exception as exc:
        try:
            await page.screenshot(path=str(proof),full_page=True)
            text = await page.locator('body').inner_text(timeout=5000)
            if started and SUCCESS.search(text):
                return 'submitted','Delayed positive confirmation; proof=' + str(proof)
        except Exception:
            pass
        return ('uncertain' if started else 'retry'),type(exc).__name__ + '; proof=' + str(proof)
    finally:
        await page.close()
