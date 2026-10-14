import re
import json
import html
from datetime import datetime, timezone, timedelta
from urllib.parse import urlsplit
import xml.etree.ElementTree as ET
import httpx
from bs4 import BeautifulSoup

ATS_HOSTS = {'jobs.lever.co','jobs.eu.lever.co','jobs.ashbyhq.com','job-boards.greenhouse.io','job-boards.eu.greenhouse.io','boards.greenhouse.io'}

def plain(value):
    return BeautifulSoup(html.unescape(str(value or '')), 'html.parser').get_text(' ', strip=True)

def description_text(value):
    soup = BeautifulSoup(html.unescape(str(value or '')), 'html.parser')
    for a in soup.select('a[href]'):
        href = a['href']
        if href.startswith('https://') and href not in a.get_text():
            a.append(' '+href)
    return soup.get_text(' ',strip=True)

def job(title, company, location, description, url, source, application_url=None, compensation=None):
    return {'title':plain(title),'company':plain(company),'location':plain(location),
            'description':description_text(description),'url':url,'source':source,
            'application_url':application_url or url,'compensation':compensation,
            'fetched_at':datetime.now(timezone.utc).isoformat()}

async def collect(profile):
    jobs, errors = [], []
    async with httpx.AsyncClient(timeout=30, follow_redirects=True, headers={'User-Agent':'CareerPilotLocal/0.2 job search'}) as client:
        async def get(url, source=None):
            # Remotive asks consumers not to exceed four reads per day.
            cache = profile.state/('source-cache-'+str(source)+'.json') if source == 'remotive' else None
            if cache and cache.exists():
                stored = json.loads(cache.read_text(encoding='utf-8'))
                if datetime.fromisoformat(stored['time']) > datetime.now(timezone.utc)-timedelta(hours=6):
                    return httpx.Response(200,json=stored['data'])
            response = await client.get(url)
            response.raise_for_status()
            if cache:
                cache.write_text(json.dumps({'time':datetime.now(timezone.utc).isoformat(),'data':response.json()}),encoding='utf-8')
            return response
        for source in profile.data.get('sources', ['remotive']):
            try:
                if source == 'remotive':
                    data = (await get('https://remotive.com/api/remote-jobs','remotive')).json()
                    jobs += [job(j['title'],j['company_name'],j['candidate_required_location'],j['description'],j['url'],source,compensation={'raw':j['salary']} if j.get('salary') else None) for j in data['jobs']]
                elif source == 'remoteok':
                    data = (await get('https://remoteok.com/api')).json()
                    jobs += [job(j['position'],j.get('company',''),j.get('location',''),j.get('description',''),j['url'],source,j.get('apply_url'),compensation={'min':j['salary_min'],'currency':'USD','period':'annual'} if j.get('salary_min') else None) for j in data if j.get('position')]
                elif source == 'wwr':
                    data = ET.fromstring((await get('https://weworkremotely.com/remote-jobs.rss')).content)
                    for j in data.findall('./channel/item'):
                        title = j.findtext('title','')
                        company, _, role = title.partition(': ')
                        region = next((x.text for x in j if x.tag.split('}')[-1] == 'region'), '')
                        jobs.append(job(role or title,company,region,j.findtext('description'),j.findtext('link'),source))
                elif source == 'himalayas':
                    data = (await get('https://himalayas.app/jobs/api')).json()
                    for j in data.get('jobs', []):
                        locations = j.get('locationRestrictions', [])
                        jobs.append(job(j['title'],j.get('companyName',''),', '.join(locations),j.get('description',j.get('excerpt','')),j.get('guid') or j.get('applicationLink'),source,j.get('applicationLink')))
                        jobs[-1]['location_restrictions'] = locations
                        if j.get('minSalary') is not None:
                            jobs[-1]['compensation'] = {'min':j['minSalary'],'currency':j.get('currency'),'period':j.get('salaryPeriod')}
                else:
                    raise ValueError('Unsupported search source')
            except Exception as exc:
                errors.append({'source':source,'error':type(exc).__name__})
        for channel in profile.data.get('telegram_channels', []):
            try:
                if not re.fullmatch(r'[A-Za-z0-9_]{5,32}', channel):
                    raise ValueError('Invalid public channel')
                soup = BeautifulSoup((await get('https://t.me/s/' + channel)).text,'html.parser')
                for m in soup.select('.tgme_widget_message'):
                    text, date = m.select_one('.tgme_widget_message_text'), m.select_one('.tgme_widget_message_date')
                    if text and date:
                        timestamp = date.select_one('time[datetime]')
                        if not timestamp:
                            continue
                        published = datetime.fromisoformat(timestamp['datetime'].replace('Z','+00:00'))
                        if published.tzinfo is None or published < datetime.now(timezone.utc) - timedelta(days=int(profile.data.get('telegram_max_age_days',7))):
                            continue
                        body = description_text(text)
                        jobs.append(job(body[:120],channel,'',body,date.get('href'), 'telegram'))
            except Exception as exc:
                errors.append({'source':channel,'error':type(exc).__name__})
        for board in profile.data.get('ats_boards', []):
            try:
                kind, name = board['kind'], board['name']
                if not re.fullmatch(r'[A-Za-z0-9_-]+', name):
                    raise ValueError('Invalid board name')
                if kind == 'ashby':
                    data = (await get(f'https://api.ashbyhq.com/posting-api/job-board/{name}')).json()
                    jobs += [job(j['title'],name,j.get('location',''),j.get('descriptionPlain',''),j['jobUrl'],kind,j.get('applyUrl')) for j in data['jobs'] if j.get('isListed',True)]
                elif kind == 'lever':
                    data = (await get(f'https://api.lever.co/v0/postings/{name}?mode=json')).json()
                    jobs += [job(j['text'],name,j.get('categories',{}).get('location',''),j.get('descriptionPlain','')+'\n'+ '\n'.join(description_text(x.get('content','')) for x in j.get('lists',[])),j['hostedUrl'],kind,j.get('applyUrl')) for j in data]
                elif kind == 'greenhouse':
                    data = (await get(f'https://boards-api.greenhouse.io/v1/boards/{name}/jobs?content=true')).json()
                    jobs += [job(j['title'],name,j.get('location',{}).get('name',''),j.get('content',''),j['absolute_url'],kind) for j in data['jobs']]
                else:
                    raise ValueError('Unsupported ATS board')
            except Exception as exc:
                errors.append({'source':str(board),'error':type(exc).__name__})
    patterns = profile.data.get('target_patterns', [])
    unique = {j['url']:j for j in jobs if j.get('url') and patterns and any(re.search(p,j['title'],re.I) for p in patterns)}
    return list(unique.values()), errors

def eligible(profile, j):
    filters = profile.data.get('filters', {})
    text = j['location'] + '\n' + j['title'] + '\n' + j.get('description','')
    restricted = j.get('location_restrictions')
    countries = {str(profile.data.get('country','')).casefold(), *[str(x).casefold() for x in profile.data.get('country_aliases',[])]}
    if restricted and not countries.intersection(str(x).casefold() for x in restricted):
        return False
    if filters.get('exclude') and re.search(filters['exclude'], text, re.I):
        return False
    if not re.search(filters.get('location_allow', r'worldwide|global remote|work from anywhere'), text, re.I):
        return False
    if re.search(r'pay to apply|buy connects|application fee|платный отклик', text, re.I):
        return False
    comp = j.get('compensation')
    # Do not turn a known but unparsed salary into "unknown allowed".
    if comp and comp.get('raw') and filters.get('min_salary'):
        return False
    if comp and comp.get('min') is not None and filters.get('min_salary') is not None:
        if comp.get('currency') != filters.get('salary_currency') or comp.get('period') != filters.get('salary_period','monthly'):
            return False  # No invented FX conversion or salary period.
        if float(comp['min']) < float(filters.get('min_salary',0)):
            return False
    elif not comp and filters.get('min_salary') and re.search(r'(?:[$€₽]\s*\d|\d[\d,. ]*\s*(?:USD|EUR|RUB|руб))',text,re.I):
        return False  # Salary text exists but has not been normalized safely.
    elif not comp and not filters.get('allow_unknown_salary', True):
        return False
    return True

def route(j):
    for url in (j.get('application_url'),j.get('url')):
        p = urlsplit(str(url or ''))
        if p.scheme == 'https' and not p.username and p.hostname in ATS_HOSTS:
            return 'ats', url
        if p.scheme == 'https' and p.hostname in ('forms.gle','docs.google.com') and ('/forms/' in p.path or p.hostname == 'forms.gle'):
            return 'google', url
    urls = [url.rstrip('.,;)') for url in re.findall(r'https://[^\s<>]+', j.get('description',''))]
    candidates = {(kind,url) for url in urls for kind in ('ats','google') if route_url(url,kind)}
    if len(candidates) == 1:
        return next(iter(candidates))
    if j.get('source') == 'telegram':
        clauses = re.findall(r'(?:apply|contact|отклик\w*|контакт\w*|пишите|писать)([^\n!?]{0,180})',j.get('description',''),re.I)
        matches = {handle for clause in clauses for handle in re.findall(r'(?:@|(?:https://)?t\.me/)([A-Za-z][A-Za-z0-9_]{4,31})',clause,re.I)}
        if len(matches) == 1:
            return 'telegram', next(iter(matches))
    return None, None

def route_url(url, kind):
    p = urlsplit(url.rstrip('.,;)'))
    return p.scheme == 'https' and not p.username and ((kind == 'ats' and p.hostname in ATS_HOSTS) or (kind == 'google' and (p.hostname == 'forms.gle' or (p.hostname == 'docs.google.com' and '/forms/' in p.path))))
