# 🚀 Sparknewsletter: Automated Google Docs to Telegram Publishing Pipeline

A complete end-to-end (E2E), cloud-native publishing pipeline that automatically fetches daily updates from Google Docs, parses rich HTML formatting and clickable hyperlinks, validates date freshness in Israel timezone, and publishes to a Telegram channel via GitHub Actions.

---

## 📐 System Architecture Diagram

```mermaid
flowchart TD
    subgraph Gemini ["1. Content Generation (AI)"]
        G1[Gemini / AI Agent] -->|Generates Daily Newsletter| G2[Google Docs]
        G2 -->|Includes Heading: # עדכון יומי: YYYY-MM-DD| G2
    end

    subgraph GitHubActions ["2. Cloud Scheduling & Execution"]
        A1[GitHub Actions Cron Job / 08:30 AM IDT] -->|Triggers Automatically| A2[send_update.py]
        A3[workflow_dispatch / Manual Trigger] -->|Triggers On Demand| A2
    end

    subgraph Publisher ["3. Processing & Validation"]
        A2 -->|1. Fetches HTML Export| G2
        A2 -->|2. Extracts Hyperlinks & Formatting| P1[HTML Converter]
        P1 -->|3. Validates Date is Today in Israel| V1{Is Date Fresh?}
        V1 -- Yes --> P2[Telegram Bot API]
        V1 -- No --> E1[Aborts Safely - Prevents Stale Content]
    end

    subgraph Telegram ["4. Channel Publication"]
        P2 -->|Delivers Rich HTML Message with Links| T1[Telegram Channel / Group 📱]
    end

    style Gemini fill:#e8f0fe,stroke:#4285f4,stroke-width:2px
    style GitHubActions fill:#f6f8fa,stroke:#24292e,stroke-width:2px
    style Publisher fill:#e6f4ea,stroke:#34a853,stroke-width:2px
    style Telegram fill:#feefc3,stroke:#fbbc04,stroke-width:2px
```

---

## 🛠️ System Components

1. **Google Docs (Content Store):**
   - Updated daily by Gemini or content creators.
   - Each daily section must begin with a heading matching `# עדכון יומי: YYYY-MM-DD` (e.g., `# עדכון יומי: 2026-08-08`).
   - **Access Requirement:** General access set to `Anyone with the link can view`.

2. **GitHub Actions (Cloud Execution):**
   - `.github/workflows/send-daily-update.yml` triggers daily on a scheduled cron (`30 5 * * *` = 08:30 AM Israel Summer Time).
   - Runs Python 3.11, installs dependencies (`requests`, `beautifulsoup4`, `tzdata`, `python-dotenv`), and executes `send_update.py`.

3. **Python Publisher Engine (`send_update.py`):**
   - **HTML Export Fetching:** Fetches formatted HTML directly from Google Docs (`export?format=html`).
   - **Hyperlink Extraction:** Extracts clickable links and cleans Google redirect wrappers (`google.com/url?q=...`) to point directly to target URLs.
   - **Rich Formatting Preservation:** Converts headings, bold (`<b>`), italics (`<i>`), and bullet lists (`•`) into native Telegram HTML (`parse_mode="HTML"`).
   - **Date Validation:** Verifies the latest section date matches today in Israel timezone (`Asia/Jerusalem`). If stale, aborts publishing to prevent duplicate/old posts.
   - **Network Safety:** Uses explicit connect (10s) and read (30s) timeouts for HTTP calls.

---

## ⚙️ Step-by-Step Setup Guide

### Step 1: Configure GitHub Repository Secrets
Navigate to your GitHub repository:
**Settings → Secrets and variables → Actions → New repository secret**

Add the following 3 secrets:
* `TELEGRAM_BOT_TOKEN`: Bot token obtained from `@BotFather`.
* `TELEGRAM_CHAT_ID`: Target Telegram channel, group, or chat ID (e.g., `-100123456789`).
* `DOC_ID`: The Google Doc ID extracted from the document URL (between `/d/` and `/edit`).

### Step 2: Configure Workflow Schedule
The workflow file `.github/workflows/send-daily-update.yml` defines the cron schedule:
```yaml
on:
  schedule:
    # Runs daily at 08:30 AM Israel Summer Time (05:30 UTC)
    - cron: '30 5 * * *'
  workflow_dispatch:
```

### Step 3: Local Development & Testing (Optional)
To run and test the publisher script locally:
1. Create a `.env` file in the project root:
   ```env
   TELEGRAM_BOT_TOKEN=your_telegram_bot_token
   TELEGRAM_CHAT_ID=your_telegram_chat_id
   DOC_ID=your_google_doc_id
   ```
2. Set up virtual environment and run:
   ```bash
   python -m venv venv
   .\venv\Scripts\pip install -r requirements.txt
   .\venv\Scripts\python send_update.py
   ```

---

## 🛡️ Built-in Protections & Security

- **Zero Hardcoded Credentials:** Tokens and document IDs are strictly managed via GitHub Secrets.
- **Stale Content Guard:** Refuses to publish if the Google Doc update date doesn't match today's date in Israel.
- **Network Resilience:** Robust timeout handling and automatic retry protection.
