"""Offline HTTPS fixtures: all routes intercepted, no employer contacted."""
import asyncio

import pytest
from playwright.async_api import async_playwright

from careerpilot.forms import apply_form
from careerpilot.profile import Profile


def scenario(tmp_path, html, expected):
    async def exercise():
        data = {'name':'Example Candidate','email':'candidate@example.org','location':'Berlin, Germany','cv_path':'unused.txt'}
        profile = Profile(tmp_path/'careerpilot.yaml',data,'Fictional candidate CV for a local test.',{})
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context()
            await context.route('**/*',lambda route: route.fulfill(status=200,content_type='text/html',body=html))
            url = 'https://jobs.lever.co/fictional/test'
            result = await apply_form(profile,context,{'url':url,'title':'Video Editor'},'ats',url)
            await browser.close()
            assert result[0] == expected, result
            if expected == 'submitted':
                assert list(profile.state.glob('proof-*.png'))
    asyncio.run(exercise())


def test_fixture_actual_submit_then_confirmation(tmp_path):
    scenario(tmp_path,'''<html><body><form onsubmit="event.preventDefault();document.body.innerHTML='Thank you for applying'">
      <label>Full name<input name="name" required></label>
      <label>Email<input name="email" type="email" required></label>
      <button type="submit">Submit Application</button></form></body></html>''','submitted')


@pytest.mark.parametrize('html',[
    '<body>Thank you for applying</body>',
    '<body><form><label>Unknown required question<input required></label><button>Submit</button></form></body>',
    '<body><form><label>Consent to privacy terms<input type="checkbox" required></label><button>Submit</button></form></body>',
    '<body>Please verify you are human<button>Submit</button></body>',
    '<body><form><label>Email<input type="email" required></label>By submitting you agree to terms<button>Submit</button></form></body>',
])
def test_fixture_does_not_send_without_owned_confirmation_or_answers(tmp_path,html):
    scenario(tmp_path,html,'needs_user')
