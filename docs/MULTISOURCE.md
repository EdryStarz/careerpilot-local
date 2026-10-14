# Multi-source CareerPilot: setup and honest support matrix

The public package is configurable per candidate. No maintainer-specific CV, account, portfolio or consent is a default. Search access and ability to submit are different capabilities.

| Source | Search | Submission route |
|---|---|---|
| HH.ru | Existing HH agent | Its separately configured HH browser adapter |
| Remotive, RemoteOK, WWR, Himalayas | Public API/RSS, currently one response per run | Only when a listing exposes a supported ATS/Google Forms route |
| Ashby, Lever, Greenhouse | Public APIs for boards explicitly listed in your YAML | Generic browser adapter for supported fields |
| Public Telegram channels | Latest public web posts, maximum age configurable (7 days default) | Explicit unique recruiter contact or supported form URL |
| Personal Telegram application conversations | Only peers with a confirmed application from this package | Confirmed answer bank; optional verbatim CV paragraphs |
| Google Forms | Not a discovery engine | Explicit questions/choices with confirmed answers; unknowns stop |
| Other sites and email | May be linked by a listing | `needs_adapter`, not an invented submission |

ATS URLs are restricted to official configured domains. Redirects to an unsupported host stop. A Telegram bot token cannot send messages as your personal account.

The currently implemented public APIs/RSS endpoints returned HTTP 200 during development, including sample ATS boards. This checks discovery connectivity, **not live application submission**. Feeds may be delayed, incomplete or paginated; only one response is loaded per source. Remotive responses are cached for six hours to respect its request guidance. Preserve source attribution and source URLs in any derived displays; check each provider's API terms before republishing listings. No scraped job dataset is bundled.

## 1. Your CV and configuration

Follow the installation commands in the README. `python -m careerpilot init` collects your identity, country, readable CV, target role patterns and portfolio. PDF extraction needs a text PDF, not a scanned image. Keep an uploadable PDF/DOCX in `resume_path` when an employer does not accept text resumes.

Edit your generated `careerpilot.yaml`; [the fictional example](../examples/careerpilot.example.yaml) lists settings. Use ISO country codes or the exact country names exposed by sources; `country_aliases` can include both. Configure target roles and exclusions for location restrictions, languages, skills, filming, and other non-negotiable conditions. `Remote` alone never proves worldwide eligibility. A remote listing can still require US residency or LATAM location.

`filters.min_salary`, `salary_currency` and `salary_period` compare only an explicitly parsed matching currency/period. There is no guessed FX conversion. Known unparsed pay with a salary floor stops; unknown pay follows `allow_unknown_salary`.

Role-specific portfolios:

```yaml
portfolios:
  - pattern: 'video|editor'
    url: 'https://example.org/video'
  - pattern: 'designer|design'
    url: 'https://example.org/design'
answers:
  - pattern: '^How many hours per day can you work\??$'
    answer: '8'
  - pattern: '^Are you available for weekends\??$'
    answer: 'Yes'
```

Choose narrow answer patterns. Only put answers you have personally confirmed in this bank. A multiple-choice answer must exactly match an option. Unknown work authorization, years of experience, rates and deadlines are not guessed. Agreements, sensitive documents and legal consent require user action even when an answer bank contains “Yes.”

The local model selects numbered CV facts and posting excerpts, which the program resolves to exact text. Out-of-range IDs and invalid scores stop the review. Invalid/truncated JSON gets one bounded regeneration; timeouts do not trigger sending. Its score is not objective proof of fit, and small models can incorrectly reject a fitting job. Inspect dry-run decisions and select a sufficiently capable model for your hardware. Telegram cover letters use selected unchanged CV paragraphs and the relevant complete portfolio URL. They do not prepend model analysis. This conservative formatter avoids invented achievements but is less fluent than a human-reviewed letter.

## 2. Local model and private bot

`.env` contains `OLLAMA_URL=http://127.0.0.1:11434/api/chat`, `LLM_MODEL`, and optional `TG_BOT_TOKEN` / `TG_USER_ID`. Only loopback model endpoints are accepted by this package. `doctor` tests profile loading and local JSON inference, not employer submission.

Run `python -m careerpilot bot` with your private owner ID. Only that user's private chat can trigger actions. Commands `/status`, `/pause`, `/resume`, `/search`, `/apply` work, and ordinary text is interpreted by the local model into the same bounded actions. It cannot execute shell commands, purchase credits, edit your profile, accept contracts or invent confirmations. New filters must be edited in YAML. Chat memory is in RAM for the last eight messages, not permanent across restart.

Only one process may poll a bot token. Keep the HH bot on a different token or do not run its poller concurrently. Direct responses to your questions remain enabled; unsolicited discovered-job and error cards are not sent by the new multi-source pipeline.

## 3. Personal Telegram outreach

Supply **your own** `TG_API_ID` and `TG_API_HASH` from Telegram's developer account. Run `python -m careerpilot telegram-login` interactively. The account session is stored through OS `keyring` (Windows Credential Manager / macOS Keychain / configured Linux secret service); if no supported keyring is available, setup must be fixed, not downgraded to plaintext. Bot-token credentials are separate.

Enable `telegram_outreach_enabled` only after inspecting the profile. Recruiter contacts must be explicit and unique. The adapter checks that the recipient is a user/bot, refuses paid messages, sends once per contact, and reads back the outgoing message ID/text. It does not post to groups or channels. Readback proves transmission from your account, not that the employer read or accepted it. Telegram restrictions still apply.

For answers in already contacted conversations, opt in:

```yaml
telegram_followups_enabled: true
followups_cv_quotes: false
```

Run `python -m careerpilot followups`, or use the daily scheduler, which also checks follow-ups after sending. Enable `followups_cv_quotes: true` only if you accept sending an exact CV paragraph chosen by the model. Unknown questions are recorded locally as `needs_user`. Employer links, legal requests and document/payment requests do not trigger automatic actions. Only the latest 20 messages from recorded application peers are inspected, with at most `max_followup_replies_per_run` attempts (5 default). Do not publish the journal. Follow-up replies are journaled locally; application notifications remain limited to confirmed application submissions.

## 4. Dry run, sending, scheduling and evidence

```bash
python -m careerpilot collect
python -m careerpilot run
python -m careerpilot status
# After editing enable_applications: true yourself:
python -m careerpilot run --send
python -m careerpilot schedule --send
```

Schedule uses `timezone` and `daily_time`; defaults UTC and 01:30. It runs while this process is alive. For unattended Windows use Task Scheduler to invoke the full virtualenv Python path with `-m careerpilot run --send`, working directory set to the repository. Configure your own desired trigger/time; the public package does not modify your system tasks. To check follow-ups separately, schedule its CLI command too. Daily application ledger limits currently use UTC dates; HH has its separate ledger and daily limit, so limits are **not global across adapters**.

Sending defaults off. Maximum applications per UTC day is 1–200, with 5 default. Process locks stop overlapping multi-source runs. An SQLite reservation is committed **before** submission. `submitted` requires positive page confirmation after our submit click, or outgoing Telegram readback. Screenshots of form confirmation are private local evidence. `submitting`/`uncertain` results are not automatically retried. You must reconcile these in the employer/account UI before a deliberate retry. Telegram flood limits persist a wait-until timestamp. Account restrictions pause new applications.

Login, CAPTCHA, custom dropdowns, unsupported uploads, unknown questions and legal consent can require manual intervention. We neither bypass verification nor promise universal unattended applications. Site rules must permit the chosen workflow. Source APIs can change or rate-limit; errors appear in `.careerpilot/last-run.json`, not as fake submissions.

## 5. Optional HH bridge

Configure HH through `setup_wizard.py` and its guide first; dry run remains recommended. Set `hh_enabled: true` to invoke the repository's `main.py --once` after a sending run. The bridge does not override HH real-apply permissions. The HH `.env` lives in the repository, while a custom multi-source profile can live elsewhere. HH results remain in its own journal; a successful subprocess exit is not submission proof.

## Privacy and verification scope

CV text is sent to a loopback model. Selected application data goes to employers; Telegram communications go to Telegram. Resumes, screenshots, private chat content, `.env`, sessions and journals are never release artifacts. Keep profiles/state outside Git or use ignored defaults. Each candidate must have a separate `state_dir`; an ownership marker prevents reuse by a different profile/email. The publication scanner is a basic safeguard, not a full secret audit.

Automated tests cover matching, evidence validation, routing, opt-in gates, deduplication, dry-run behavior and notification restrictions. They use fictional candidates and mocked/offline workflows. Generic adapters still need human-supervised testing against actual employer forms; test success does not establish live support for every site's form variation.
