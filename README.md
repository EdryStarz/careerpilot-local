<div align="center">

![CareerPilot Local](docs/hero.svg)

# CareerPilot Local

**Your CV. Your local model. Your job search.**

CV-based job search across public boards, ATS and Telegram, with local AI and opt-in applications.

![Python](https://img.shields.io/badge/Python-3.11%2B-3776AB)
![MIT](https://img.shields.io/badge/License-MIT-34d399)
![Preview](https://img.shields.io/badge/Release-public_preview-fbbf24)

[Quick start](#quick-start) · [Русский](#по-русски) · [Full guide](README.upstream.md) · [Contribute](CONTRIBUTING.md)

</div>

## What it does

- Searches Remotive, RemoteOK, We Work Remotely, Himalayas, configured Ashby/Lever/Greenhouse boards and public Telegram channels. HH.ru remains available through its adapter.
- Imports **your** CV from PDF, DOCX or text; uses your role filters, portfolio links and confirmed questionnaire answers.
- Chats with you through a private Telegram bot using a loopback Ollama model. Ordinary text can trigger search, sending, pause and status.
- Submits supported ATS/Google Forms workflows and Telegram applications from your personal account, only after opt-in.
- Answers questions in previously contacted Telegram application conversations using confirmed answers or optional exact CV quotes.
- Keeps a private ledger, rate-limit pauses and confirmation evidence. Multi-source notifications contain **only confirmed submissions**, not found-job cards.

**Public preview, not universal unattended job applications.** Login, CAPTCHA, questionnaires, legal consent and changing websites may require intervention. A timeout is not proof of failure: never blindly retry an uncertain application.

## Quick start

Install Python 3.11+, [Ollama](https://ollama.com/), and create a Telegram bot through [BotFather](https://t.me/BotFather). Select a local model that fits your hardware.

```bash
git clone https://github.com/EdryStarz/careerpilot-local.git
cd careerpilot-local
python -m venv .venv
```

```powershell
# Windows activation
.\.venv\Scripts\Activate.ps1
```

```bash
# macOS / Linux activation
source .venv/bin/activate
```

```bash
python -m pip install -r requirements.txt
python -m playwright install chromium
ollama pull qwen3:4b
python -m careerpilot init
python -m careerpilot doctor
python -m careerpilot run
```

The wizard creates private `.env` and `careerpilot.yaml` files with sending **disabled**. Choose a model that fits your hardware; `qwen3:4b` is an example, not a quality guarantee. Configure boards, channels, filters, answers and role-specific portfolios using [the example profile](examples/careerpilot.example.yaml).

After reviewing a dry run, opt in through your private YAML:

```yaml
enable_applications: true
telegram_outreach_enabled: true  # Only if you want personal-account outreach
```

```bash
python -m careerpilot telegram-login  # Own credentials + interactive sign-in
python -m careerpilot run --send
python -m careerpilot bot             # Private owner chat; separate terminal
python -m careerpilot schedule --send # Daily runner; separate terminal
```

Read [the multi-source setup and support matrix](docs/MULTISOURCE.md) before enabling sending. For HH, use `python setup_wizard.py` and [the HH configuration guide](README.upstream.md); it has separate opt-ins, credentials and limits. Do not run two bot pollers with the same token.

## Safety and privacy

| Mode | Real applications | Purpose |
|---|---|---|
| Multi-source `run` | No | Inspect matching and routing |
| Multi-source `run --send` | Only with `enable_applications: true` | Supported forms and personal Telegram outreach |
| HH `dry_run` / `approval` / `auto_apply` | Depends on separate HH settings | Existing HH adapter |

Never invent credentials, work authorization, languages, employers, achievements or consent. Review the generated content before enabling applications. Platform rules still apply; there is no CAPTCHA bypass.

Your profile is local, but submitted applications go to employers, and bot messages go to Telegram. Optional cloud-model providers receive prompts; choose Ollama for local inference. Local AI does not make the whole workflow offline or eliminate hardware costs.

## Included / not included

This distribution includes the upstream HH agent plus the reusable `careerpilot` package, per-user setup wizard, examples and tests. It does **not** contain the maintainer's CVs, tokens, browser sessions, logs or application history.

Not every listing has a supported submission route. Unknown forms, legal consent, login, verification, custom dropdowns and required missing facts stop for review. Email, LinkedIn, Upwork, Freelancer bidding, Workday and arbitrary websites are not submission adapters. No paid bids, purchased credits, CAPTCHA bypass or automatic account creation. Generic adapters are beta, tested with fixtures; this is not proof of live submissions for every website. Interviews, offers and popularity are not guaranteed.

## По-русски

Теперь не только HH: поиск на публичных площадках, досках Ashby/Lever/Greenhouse и в Telegram; отправка через поддерживаемые формы и личный Telegram; общение с локальной моделью по вашему CV. Настройка для любого пользователя: `python -m careerpilot init`. Отправка выключена до вашего явного разрешения.

Настройка и ограничения — в [multi-source инструкции](docs/MULTISOURCE.md); отдельный HH-адаптер — в [HH-инструкции](README.upstream.md). Это beta, не обещание работы на всех сайтах без вмешательства. Не публикуйте `.env`, резюме, cookies, базы или переписки. Не повторяйте отправку, если предыдущий результат неизвестен.

## Development

```bash
python -m pip install -r requirements-dev.txt
python -m pytest -q
python scripts/check_public_files.py
```

[Contributing](CONTRIBUTING.md) · [Security](SECURITY.md)

## Credits

Based on [fikstt2/hh-ai-agent](https://github.com/fikstt2/hh-ai-agent). Original MIT copyright preserved in [LICENSE](LICENSE). Public-preview packaging and documentation by [EdryStarz](https://github.com/EdryStarz). No affiliation with HeadHunter, Telegram or Ollama.

Share a redacted demo or an honest bug report if this helps you. Stars are welcome; virality is not a product feature.
