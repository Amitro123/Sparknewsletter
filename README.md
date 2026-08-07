# Sparknewsletter

Sparknewsletter is a small event-driven publishing pipeline that sends a daily update from Google Docs to Telegram.

The content is generated and written to Google Docs by Gemini. After the document update succeeds, Gemini triggers a GitHub Actions workflow. The workflow fetches the latest daily section from the Google Doc and publishes it to Telegram.

## Flow

```text
Gemini
  |
  | 1. Generate daily news and tips
  v
Google Docs
  |
  | 2. Save the daily section successfully
  v
GitHub workflow_dispatch
  |
  | 3. Run send_update.py
  v
Telegram
```

The important design rule is that publishing is event-driven: the GitHub workflow is triggered only after Gemini successfully updates the Google Doc.

## Repository structure

```text
Sparknewsletter/
├── .github/
│   └── workflows/
│       └── send-daily-update.yml
├── send_update.py
├── requirements.txt
└── README.md
```

## Google Doc format

Every daily update must start with this exact heading:

```text
# עדכון יומי: YYYY-MM-DD
```

Example:

```text
# עדכון יומי: 2026-08-07

Your daily content starts here...
```

The publisher locates the last heading matching this format and sends that section to Telegram.

As a safety check, the date in the latest heading must match the current date in the `Asia/Jerusalem` timezone. If the latest section is stale, the workflow fails instead of sending old content.

## Google Doc access

The workflow fetches the document using the Google Docs plain-text export URL:

```text
https://docs.google.com/document/d/DOC_ID/export?format=txt
```

The document must therefore be accessible to the GitHub Actions runner through that URL. If the document requires authentication, the current implementation will fail and should be replaced with authenticated Google API access.

## GitHub Actions secrets

Create the following repository secrets in:

**Settings → Secrets and variables → Actions**

Required secrets:

- `TELEGRAM_BOT_TOKEN` — the Telegram bot token from BotFather.
- `TELEGRAM_CHAT_ID` — the target Telegram chat, group, or channel ID.

The Google Doc ID is configured in the workflow as `DOC_ID`.

Never commit Telegram tokens or GitHub access tokens to the repository.

## GitHub workflow

The workflow is located at:

```text
.github/workflows/send-daily-update.yml
```

It is triggered using `workflow_dispatch`.

The workflow:

1. Checks out the repository.
2. Installs Python 3.11.
3. Installs dependencies.
4. Fetches the latest Google Doc content.
5. Verifies that the latest update is dated today in Israel.
6. Sends the latest section to Telegram.
7. Fails clearly if any step fails.

## Gemini → GitHub dispatch

Gemini should trigger this workflow only after the Google Doc update succeeds.

Repository:

```text
Amitro123/Sparknewsletter
```

Workflow:

```text
send-daily-update.yml
```

Branch:

```text
main
```

Endpoint:

```text
POST https://api.github.com/repos/Amitro123/Sparknewsletter/actions/workflows/send-daily-update.yml/dispatches
```

Headers:

```text
Accept: application/vnd.github+json
Authorization: Bearer <GITHUB_ACTIONS_TOKEN>
X-GitHub-Api-Version: 2026-03-10
```

Body:

```json
{
  "ref": "main"
}
```

Store the token securely as `GITHUB_ACTIONS_TOKEN`.

For a fine-grained GitHub personal access token, grant access only to this repository and give it the minimum repository permission required to dispatch the workflow: **Actions: write**.

Do not place the GitHub token in the Google Doc, generated news content, Telegram messages, or logs.

## Gemini publishing instructions

The Gemini automation should follow this sequence:

1. Generate the daily personalized update.
2. Write it successfully to the configured Google Doc.
3. Use the exact heading `# עדכון יומי: YYYY-MM-DD`.
4. Confirm that the Google Doc update succeeded.
5. Trigger the GitHub `workflow_dispatch` endpoint.
6. Verify that GitHub accepted the dispatch request.
7. If either the document update or workflow dispatch fails, report the failure and do not claim the newsletter was published.

## Local development

Install dependencies:

```bash
python -m pip install -r requirements.txt
```

Set environment variables:

```bash
export TELEGRAM_BOT_TOKEN="your-telegram-bot-token"
export TELEGRAM_CHAT_ID="your-chat-id"
export DOC_ID="your-google-doc-id"
```

Run:

```bash
python send_update.py
```

## Failure behavior

The script intentionally exits with an error when:

- a required environment variable is missing;
- the Google Doc cannot be downloaded;
- no correctly formatted daily heading exists;
- the latest daily heading is not dated today in `Asia/Jerusalem`;
- Telegram rejects the message;
- an HTTP request fails.

Because the Python process exits non-zero, GitHub Actions marks the workflow as failed.

## Security

Keep all credentials in secret stores.

Do not:

- hard-code tokens in Python;
- store tokens in the Google Doc;
- print tokens to logs;
- send tokens through Telegram;
- include tokens in generated content.

Use least-privilege permissions for the GitHub token used by Gemini.
