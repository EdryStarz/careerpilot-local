<div align="center">

![CareerPilot Local](docs/hero.svg)

# CareerPilot Local

**Your CV. Your local model. Your job search.**

HH.ru job search with local AI, Telegram review and optional applications.

![Python](https://img.shields.io/badge/Python-3.11%2B-3776AB)
![MIT](https://img.shields.io/badge/License-MIT-34d399)
![Preview](https://img.shields.io/badge/Release-public_preview-fbbf24)

[Quick start](#quick-start) · [Русский](#по-русски) · [Full guide](README.upstream.md) · [Contribute](CONTRIBUTING.md)

</div>

## What it does

- Searches HH.ru using **your own** profile and target roles.
- Uses Ollama locally to evaluate jobs and draft personalized letters.
- Sends candidates to your private Telegram bot for review.
- Supports dry-run, approval and explicitly enabled automatic applications.
- Maintains a local application ledger and limits.

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
python setup_wizard.py
python main.py --once
```

The wizard creates private `.env` and `profile.yaml` files. Start with **Ollama + dry_run**. See [the full configuration guide](README.upstream.md) for model setup, browser login, resume selection, Telegram and application modes.

## Safety and privacy

| Mode | Real applications | Purpose |
|---|---|---|
| `dry_run` | No | Test matching and letters |
| `approval` | With explicit real-apply settings and your approval | Review individually |
| Optional auto-apply | Yes, when enabled | Tested workflows with limits |

Never invent credentials, work authorization, languages, employers, achievements or consent. Review the generated content before enabling applications. Platform rules still apply; there is no CAPTCHA bypass.

Your profile is local, but submitted applications go to employers, and bot messages go to Telegram. Optional cloud-model providers receive prompts; choose Ollama for local inference. Local AI does not make the whole workflow offline or eliminate hardware costs.

## Included / not included

This distribution includes the upstream HH agent, setup wizard, examples and tests. It does **not** contain the maintainer's CVs, tokens, browser sessions, logs or application history.

Generic LinkedIn, Upwork, personal-account Telegram outreach and multi-site ATS adapters are **not included**. The personalized multi-site worker is not yet a reusable public product. Interviews, offers and popularity are not guaranteed.

## По-русски

Локальный помощник для поиска работы на HH.ru. Добавьте свой профиль, подключите Ollama и Telegram, проверьте подбор и письма в `dry_run`. Это предварительная публичная версия, а не универсальный автоотклик на все сайты.

Пошаговая настройка — в [полной инструкции](README.upstream.md). Не публикуйте `.env`, резюме, cookies, базы или переписки. Не повторяйте отправку, если предыдущий результат неизвестен.

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
