import asyncio
from pathlib import Path
from unittest.mock import AsyncMock
from types import SimpleNamespace

import pytest
import yaml

from careerpilot.profile import Profile
from careerpilot.ledger import Ledger
from careerpilot.sources import eligible, route, job
from careerpilot import model, pipeline, telegram


@pytest.fixture
def profile(tmp_path, monkeypatch):
    monkeypatch.delenv('OLLAMA_URL', raising=False)
    (tmp_path/'cv.txt').write_text('Example Candidate\nI edit educational videos using Premiere and produce subtitles for social media.',encoding='utf-8')
    data = {'name':'Example Candidate','email':'candidate@example.org','location':'Berlin, Germany','country':'Germany',
            'cv_path':'cv.txt','target_patterns':['video editor'],'filters':{'location_allow':'worldwide|global remote'},
            'portfolios':[{'pattern':'video','url':'https://example.org/video'}],
            'answers':[{'pattern':'hours per day','answer':'8'},{'pattern':'privacy','answer':'Yes'}]}
    path = tmp_path/'careerpilot.yaml'
    path.write_text(yaml.safe_dump(data),encoding='utf-8')
    return Profile.load(path)


def vacancy(**kwargs):
    result = job('Video Editor','Example Studio','Worldwide','Worldwide remote. Edit educational videos.','https://jobs.lever.co/example/123','lever')
    result.update(kwargs)
    return result


def test_cv_profile_and_answer_bank(profile):
    assert 'Premiere' in profile.cv
    assert profile.answer('Full name *') == 'Example Candidate'
    assert profile.answer('Hours per day *',['4','8']) == '8'
    assert profile.answer('Hours per day',['4']) is None
    assert profile.answer('Privacy agreement',['Yes']) is None
    assert profile.answer('Portfolio',title='Video Editor') == 'https://example.org/video'
    assert profile.answer('Years in enterprise leadership?') is None


@pytest.mark.parametrize('endpoint',['https://model.example.org/chat','http://user@localhost:11434/chat','file:///tmp/model'])
def test_remote_model_blocked(profile, endpoint):
    profile.env['OLLAMA_URL'] = endpoint
    with pytest.raises(ValueError):
        profile.model_endpoint()


def test_location_and_pay_filters(profile):
    assert eligible(profile,vacancy())
    assert not eligible(profile,vacancy(location_restrictions=['United States']))
    assert eligible(profile,vacancy(location_restrictions=['germany']))
    assert not eligible(profile,vacancy(description='Worldwide; pay to apply'))
    profile.data['filters'].update(min_salary=60000,salary_currency='RUB',salary_period='monthly')
    assert eligible(profile,vacancy(compensation={'min':60000,'currency':'RUB','period':'monthly'}))
    assert not eligible(profile,vacancy(compensation={'min':59000,'currency':'RUB','period':'monthly'}))
    assert not eligible(profile,vacancy(compensation={'min':100000,'currency':'USD','period':'annual'}))
    assert not eligible(profile,vacancy(compensation={'raw':'50000 RUB'}))
    assert eligible(profile,vacancy())
    profile.data['filters']['allow_unknown_salary'] = False
    assert not eligible(profile,vacancy())


@pytest.mark.parametrize('url',['https://jobs.lever.co/example/123','https://jobs.ashbyhq.com/example/123','https://job-boards.greenhouse.io/example/jobs/123'])
def test_ats_routes(url):
    assert route(vacancy(url=url,application_url=url)) == ('ats',url)


def test_route_untrusted_and_telegram_contacts():
    unknown = vacancy(url='https://example.org/job',application_url='https://jobs.lever.co.evil.example/job')
    assert route(unknown) == (None,None)
    assert route(dict(unknown,source='telegram',description='Пишите @example_client')) == ('telegram','example_client')
    assert route(dict(unknown,source='telegram',description='Пишите @example_client или @another_client')) == (None,None)
    assert route(dict(unknown,description='Apply https://forms.gle/example123.')) == ('google','https://forms.gle/example123')


def test_embedded_form_link_is_preserved():
    j = vacancy(description='')
    j.update(job('Video Editor','Example','Worldwide','Apply <a href="https://forms.gle/example123">here</a>','https://example.org/job','wwr'))
    assert route(j) == ('google','https://forms.gle/example123')


def test_ledger_uncertain_duplicate_daily_limit_and_pause(tmp_path):
    ledger = Ledger(tmp_path/'test.db')
    url = 'https://example.org/1?tracking=a'
    assert ledger.claim(url,2)
    assert not ledger.claim('https://example.org/1?tracking=b',2)
    ledger.finish(url,'uncertain','No positive proof')
    assert not ledger.claim(url,2)
    assert ledger.claim('https://example.org/2',2)
    assert not ledger.claim('https://example.org/3',2)
    ledger.pause(True)
    assert not ledger.claim('https://example.org/4',200)


def test_review_rejects_invented_evidence(profile,monkeypatch):
    monkeypatch.setattr(model,'local_json',AsyncMock(return_value={'suitable':True,'score':92,'reason':'fit','candidate_evidence_ids':[999],'location_evidence_id':0}))
    with pytest.raises(ValueError,match='Candidate evidence'):
        asyncio.run(model.review(profile,vacancy()))


def test_review_location_can_use_actual_location(profile,monkeypatch):
    monkeypatch.setattr(model,'local_json',AsyncMock(return_value={'suitable':True,'score':85,'reason':'fit','candidate_evidence_ids':[0],'location_evidence_id':0}))
    assert asyncio.run(model.review(profile,vacancy(description='Edit videos.')))['suitable']


def test_letter_uses_only_cv_and_full_portfolio(profile,monkeypatch):
    monkeypatch.setattr(model,'local_json',AsyncMock(return_value={'paragraph_ids':[0]}))
    result = asyncio.run(model.letter(profile,vacancy()))
    assert 'Premiere' in result
    assert 'https://example.org/video' in result
    assert result.endswith('Example Candidate')
    monkeypatch.setattr(model,'local_json',AsyncMock(return_value={'paragraph_ids':[100]}))
    with pytest.raises(ValueError):
        asyncio.run(model.letter(profile,vacancy()))


def test_dry_run_never_claims_sends_or_notifies(profile,monkeypatch):
    ledger = Ledger(profile.state/'test.db')
    monkeypatch.setattr(pipeline,'collect',AsyncMock(return_value=([vacancy()],[])))
    monkeypatch.setattr(pipeline,'review',AsyncMock(return_value={'suitable':True,'score':90}))
    form = AsyncMock(side_effect=AssertionError('Must not send'))
    notify = AsyncMock(side_effect=AssertionError('Must not notify'))
    monkeypatch.setattr(pipeline,'apply_form',form)
    monkeypatch.setattr(pipeline,'notify_confirmation',notify)
    report = asyncio.run(pipeline.run(profile,ledger))
    assert report['jobs'][0]['status'] == 'dry_run'
    assert ledger.status(vacancy()['url']) is None
    form.assert_not_called()
    notify.assert_not_called()


def test_send_requires_opt_in(profile):
    with pytest.raises(ValueError,match='enable_applications'):
        asyncio.run(pipeline.run(profile,Ledger(profile.state/'test.db'),send=True))


@pytest.mark.parametrize('status',['dry_run','uncertain','needs_user','retry','reviewed'])
def test_notifications_only_for_submitted(profile,status,monkeypatch):
    profile.env.update(TG_BOT_TOKEN='placeholder',TG_USER_ID='1')
    monkeypatch.setattr(telegram.httpx,'AsyncClient',lambda **kw: pytest.fail('Non-confirmation reached Telegram'))
    asyncio.run(telegram.notify_confirmation(profile,Ledger(profile.state/'test.db'),vacancy(),status))


def test_followups_require_explicit_opt_in(profile):
    with pytest.raises(ValueError):
        asyncio.run(telegram.followups(profile,Ledger(profile.state/'test.db')))


def test_state_cannot_be_shared_across_candidates(profile):
    profile.state
    other = Profile(profile.path,dict(profile.data,email='other@example.org'),profile.cv,{})
    with pytest.raises(ValueError,match='another profile'):
        other.state


def fake_telegram_client(paid=0, readback=True):
    from telethon.types import User
    client = SimpleNamespace(
        get_entity=AsyncMock(return_value=User(id=42,first_name='Recruiter')),
        send_message=AsyncMock(return_value=SimpleNamespace(id=100)),
        get_messages=AsyncMock(return_value=SimpleNamespace(out=True,raw_text='Confirmed facts') if readback else None),
        disconnect=AsyncMock())
    async def call(request):
        return SimpleNamespace(full_user=SimpleNamespace(send_paid_messages_stars=paid))
    class Client:
        async def __call__(self,request):
            return await call(request)
        def __getattr__(self,name):
            return getattr(client,name)
    return Client()


def test_telegram_actual_transport_readback_and_dedup(profile,monkeypatch):
    profile.data['telegram_outreach_enabled'] = True
    client = fake_telegram_client()
    monkeypatch.setattr(telegram,'account',AsyncMock(return_value=client))
    ledger = Ledger(profile.state/'test.db')
    status, detail = asyncio.run(telegram.send_application(profile,ledger,vacancy(),'example_client','Confirmed facts'))
    assert status == 'submitted' and '100' in detail
    client.send_message.assert_awaited_once()
    with ledger.connect() as db:
        assert db.execute("SELECT 1 FROM controls WHERE name='peer:42'").fetchone()
    assert asyncio.run(telegram.send_application(profile,ledger,vacancy(),'example_client','Confirmed facts'))[0] == 'skipped'
    client.send_message.assert_awaited_once()


@pytest.mark.parametrize('paid,readback,expected',[(1,True,'skipped'),(0,False,'uncertain')])
def test_telegram_no_payment_or_unproven_success(profile,monkeypatch,paid,readback,expected):
    profile.data['telegram_outreach_enabled'] = True
    client = fake_telegram_client(paid,readback)
    monkeypatch.setattr(telegram,'account',AsyncMock(return_value=client))
    status, _ = asyncio.run(telegram.send_application(profile,Ledger(profile.state/'test.db'),vacancy(),'example_client','Confirmed facts'))
    assert status == expected
    if paid:
        client.send_message.assert_not_called()


def test_confirmations_deduplicate_and_store_telegram_message_id(profile,monkeypatch):
    import httpx
    posts = []
    def handler(request):
        posts.append(request)
        return httpx.Response(200,json={'ok':True,'result':{'message_id':101}})
    original = httpx.AsyncClient
    monkeypatch.setattr(telegram.httpx,'AsyncClient',lambda **kw: original(transport=httpx.MockTransport(handler),**kw))
    profile.env.update(TG_BOT_TOKEN='placeholder',TG_USER_ID='1')
    ledger = Ledger(profile.state/'test.db')
    asyncio.run(telegram.notify_confirmation(profile,ledger,vacancy(),'submitted'))
    asyncio.run(telegram.notify_confirmation(profile,ledger,vacancy(),'submitted'))
    assert len(posts) == 1
    with ledger.connect() as db:
        assert db.execute("SELECT value FROM controls WHERE name LIKE 'notified:%'").fetchone()[0] == '101'


def test_model_regenerates_invalid_json_once_without_remote_proxy(profile,monkeypatch):
    import httpx
    calls = []
    def handler(request):
        calls.append(request)
        content = '{"ok":' if len(calls) == 1 else '{"ok":true}'
        return httpx.Response(200,json={'message':{'content':content}})
    original = httpx.AsyncClient
    def client(**kwargs):
        assert kwargs['trust_env'] is False
        return original(transport=httpx.MockTransport(handler),**kwargs)
    monkeypatch.setattr(model.httpx,'AsyncClient',client)
    assert asyncio.run(model.local_json(profile,'Return ok',{},{})) == {'ok':True}
    assert len(calls) == 2
