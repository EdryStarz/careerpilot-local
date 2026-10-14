import os
import re
import hashlib
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit
import yaml
from dotenv import dotenv_values

@dataclass
class Profile:
    path: Path
    data: dict
    cv: str
    env: dict

    @classmethod
    def load(cls, path='careerpilot.yaml'):
        path = Path(path).resolve()
        data = yaml.safe_load(path.read_text(encoding='utf-8'))
        if not isinstance(data, dict):
            raise ValueError('Profile must be a YAML object')
        for field in ('name', 'email', 'location', 'country', 'cv_path'):
            if not data.get(field):
                raise ValueError('Missing candidate field: ' + field)
        cv_path = cls.resolve_path(path, data['cv_path'])
        if cv_path.suffix.lower() == '.docx':
            from docx import Document
            cv = '\n'.join(p.text for p in Document(cv_path).paragraphs)
        elif cv_path.suffix.lower() == '.pdf':
            from pypdf import PdfReader
            cv = '\n'.join(p.extract_text() or '' for p in PdfReader(cv_path).pages)
        else:
            cv = cv_path.read_text(encoding='utf-8')
        if not cv.strip():
            raise ValueError('CV has no readable text; provide a text CV')
        if len(cv) > 40000:
            raise ValueError('CV exceeds 40000 characters; provide a concise factual CV')
        if not data.get('target_patterns'):
            raise ValueError('Set target_patterns; never scan/apply to every role by default')
        if not 1 <= int(data.get('max_daily_applications',5)) <= 200:
            raise ValueError('max_daily_applications must be between 1 and 200')
        for pattern in data.get('target_patterns', []):
            re.compile(pattern)
        for item in data.get('answers', []) + data.get('portfolios', []):
            re.compile(item['pattern'])
        for value in [data.get('website'), *[x['url'] for x in data.get('portfolios',[])]]:
            if value:
                url = urlsplit(value)
                if url.scheme != 'https' or not url.hostname or url.username:
                    raise ValueError('Portfolio links must be public HTTPS URLs without credentials')
        env = {**dotenv_values(path.parent / '.env'), **os.environ}
        return cls(path, data, cv, env)

    @staticmethod
    def resolve_path(profile_path, value):
        p = Path(value)
        return p if p.is_absolute() else profile_path.parent / p

    @property
    def state(self):
        p = self.resolve_path(self.path, self.data.get('state_dir', '.careerpilot'))
        p.mkdir(parents=True, exist_ok=True)
        owner = hashlib.sha256((str(self.path)+'\n'+self.data['email']).encode()).hexdigest()
        marker = p / '.profile-owner'
        try:
            with marker.open('x',encoding='utf-8') as f:
                f.write(owner)
        except FileExistsError:
            if marker.read_text(encoding='utf-8') != owner:
                raise ValueError('State directory belongs to another profile; set a separate state_dir')
        return p

    @property
    def resume(self):
        p = self.resolve_path(self.path, self.data.get('resume_path', self.data['cv_path']))
        if not p.is_file():
            raise ValueError('Resume file missing')
        if p.suffix.lower() == '.md':
            p = self.state / 'resume.txt'
            p.write_text(self.cv,encoding='utf-8')
        return p

    def portfolio(self, title):
        for item in self.data.get('portfolios', []):
            if re.search(item['pattern'], title, re.I):
                return item['url']
        return self.data.get('website')

    def answer(self, label, options=(), title=''):
        label = re.sub(r'Required question|[✱*]', '', label, flags=re.I).strip()
        label = re.sub(r'\s+', ' ', label)
        key = label.casefold()
        basic = {'name': self.data['name'], 'full name': self.data['name'],
                 'legal full name': self.data['name'], 'email': self.data['email'],
                 'email address': self.data['email'], 'phone': self.data.get('phone'),
                 'phone number': self.data.get('phone'), 'location': self.data['location'],
                 'current location': self.data['location'], 'where are you based?': self.data['location'],
                 'first name': self.data.get('first_name'), 'last name': self.data.get('last_name'),
                 'current company': self.data.get('current_company'),
                 'current / most recent job title': self.data.get('current_title'),
                 'current / most recent company url': self.data.get('company_url')}
        value = basic.get(key)
        if re.fullmatch(r'(?:your |you |personal )?linkedin(?: url| profile| link| profile url)?', label, re.I):
            value = self.data.get('linkedin')
        elif re.fullmatch(r'(github|twitter|x)(?: url| profile| link)?', label, re.I):
            value = self.data.get(key.split()[0])
        elif re.fullmatch(r'(?:portfolio|porfolio|portolio)(?: url| link|/work example \(link\))?|(?:personal |other )?website', label, re.I):
            value = self.portfolio(title)
        # Only explicitly configured confirmations; never infer legal consent.
        for item in self.data.get('answers', []):
            if re.search(item['pattern'], label, re.I):
                if re.search(r'consent|agree|terms|privacy|паспорт|соглас', label, re.I):
                    return None
                value = item['answer']
                break
        if options:
            if isinstance(value,list):
                if not value or not all(x in options for x in value):
                    return None
            elif value not in options:
                return None
        return value

    def model_endpoint(self):
        value = self.env.get('OLLAMA_URL', 'http://127.0.0.1:11434/api/chat').replace('/api/generate', '/api/chat')
        p = urlsplit(value)
        if p.hostname not in ('localhost', '127.0.0.1', '::1') or p.scheme not in ('http', 'https') or p.username:
            raise ValueError('Multi-source inference requires a loopback local model endpoint')
        return value
