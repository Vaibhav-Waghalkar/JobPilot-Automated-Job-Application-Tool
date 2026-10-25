# JobPilot: Autonomous Local-First Job Application Agent

JobPilot is a local-first, privacy-respecting automated job application agent designed to discover, match, and apply for technical roles with human-in-the-loop oversight.

It operates strictly on your local machine, keeping credentials, resumes, and personal career facts secure. JobPilot combines multi-LLM intelligence (Gemini, Groq, and local Ollama) with Playwright browser automation, smart field resolution, and a blocker-escalation system ("Needs You").

---

## Key Features

- **Local-First & Privacy Preserving**: Your career vault, personal facts, browser profile, and database run entirely locally (SQLite + ChromaDB vector store). No external third-party cloud data harvesting.
- **Pluggable Multi-LLM Routing**:
  - **Google Gemini** (`gemini-3.5-flash-lite`)
  - **Groq** (`openai/gpt-oss-20b`)
  - **Ollama** (`qwen2.5:7b-instruct` running 100% offline)
  - Automatic fallback, cost-efficient token routing, and masked key diagnostics in the health dashboard.
- **Career Vault & Resume Intelligence**:
  - Store master profile information, parsed facts, and categorized work experiences.
  - Multi-resume tagging (e.g. Backend Developer vs Full Stack) with automatic semantic matching against job requirements.
  - Review queue to audit and approve extracted resume facts before they are ever used.
- **Platform Discovery & Filtering**:
  - Live scraping adapters (Internshala, generic career portals).
  - Hard filters: minimum salary/stipend threshold, job vs. internship filter, location preferences (Remote/Hybrid/Onsite).
  - Vector similarity + LLM contextual match scoring with transparent skip reasons.
  - **"Test with live listing" sandbox**: scrape and preview real listings and match scoring without applying or form-filling.
- **Human-in-the-Loop Blocker System ("Needs You")**:
  - If a form encounter an unknown custom question, blocker, or low-confidence field, it pauses and raises a dashboard alert.
  - Configurable timeout (default 5 minutes). If you provide the answer in the dashboard, JobPilot saves it to your Vault and resumes immediately.
  - If the timeout expires without an answer, the job is cleanly parked as "Needs You" with preserved state and screenshots, and JobPilot proceeds to the next job.
- **Safe Execution Modes**:
  - Defaults to `DRY_RUN` and `REVIEW` mode to prevent unintended submissions during first runs.
  - `AUTO` mode requires explicit user confirmation.
  - Zero password collection: dedicated "Open Internshala login" launches a persistent browser session so you log in manually once.

---

## Architecture Overview

```
                                +---------------------------+
                                |  React + Vite Frontend    |
                                |  (Local Dashboard UI)     |
                                +-------------+-------------+
                                              |
                                              | HTTP REST API
                                              v
+-------------------------------------------------------------------------------------------+
| FastAPI Backend Engine                                                                    |
|                                                                                           |
|  +---------------------+   +---------------------+   +---------------------------------+  |
|  | Vault & Fact Store  |   | LLM Router          |   | Discovery & Adapters            |  |
|  | - SQLite Storage    |   | - Gemini Provider   |   | - Internshala Adapter           |  |
|  | - ChromaDB Vectors  |   | - Groq Provider     |   | - Career Page Scraper           |  |
|  | - Master Profile    |   | - Ollama Local      |   | - Match Evaluator               |  |
|  +---------------------+   +---------------------+   +---------------------------------+  |
|                                                                                           |
|  +-------------------------------------------------------------------------------------+  |
|  | Form Filler & Execution Engine (Playwright)                                         |  |
|  | - Field Classifier & Value Generator                                                |  |
|  | - Human-in-the-Loop Event Synchronizer (Blocker Pause / Resume / Park)               |  |
|  | - Safe Submission Guard (DRY_RUN / REVIEW / AUTO)                                   |  |
|  +-------------------------------------------------------------------------------------+  |
+-------------------------------------------------------------------------------------------+
```

---

## Getting Started

### Prerequisites

- **Python 3.11+**
- **Node.js 18+** & npm
- *(Optional but recommended)*: **Ollama** running locally with `qwen2.5:7b-instruct`:
  ```bash
  ollama run qwen2.5:7b-instruct
  ```

### Installation

1. **Clone the repository**:
   ```bash
   git clone https://github.com/Vaibhav-Waghalkar/JobPilot-Automated-Job-Application-Tool.git
   cd JobPilot-Automated-Job-Application-Tool
   ```

2. **Backend Setup**:
   ```bash
   python -m venv .venv
   # Windows PowerShell:
   .venv\Scripts\Activate.ps1
   # Linux / macOS:
   source .venv/bin/activate

   pip install -e .
   playwright install chromium
   ```

3. **Frontend Setup**:
   ```bash
   cd frontend
   npm install
   cd ..
   ```

4. **Configure Environment**:
   Copy `.env.example` to `.env`:
   ```bash
   cp .env.example .env
   ```
   Edit `.env` to configure your API keys and models:
   ```ini
   GEMINI_API_KEY=your_gemini_api_key
   GROQ_API_KEY=your_groq_api_key
   OLLAMA_BASE_URL=http://localhost:11434

   GEMINI_MODEL=gemini-3.5-flash-lite
   GROQ_MODEL=openai/gpt-oss-20b
   OLLAMA_MODEL=qwen2.5:7b-instruct

   APPLICATION_MODE=DRY_RUN
   HUMAN_ALERT_TIMEOUT_SECONDS=300
   ```

---

## Running JobPilot

Start both services:

### 1. Backend Server
```bash
.venv\Scripts\python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000 --reload
```

### 2. Frontend Dashboard
```bash
cd frontend
npm run dev
```

Open `http://localhost:5173` in your browser.

---

## Workflow Guide

1. **LLM Health**: Verify all three providers (Gemini, Groq, Ollama) show operational status with masked keys.
2. **Resume Import**: Upload your PDF resume, assign a role tag (e.g. Backend Developer), and extract career facts.
3. **Review Queue**: Verify extracted claims and experiences, approve valid items into your personal Knowledge Vault.
4. **Fixed Profile & Preferences**: Enter your contact details, target titles, job type (`job` or `internship`), and salary minimums.
5. **One-Time Manual Login**: Click **Open Internshala login** to launch a browser session, sign in manually, and close the window. JobPilot never asks for or stores passwords.
6. **Test With Live Listing**: Run the live listing sandbox to inspect real-time job scraping and match scores before applying.
7. **Dry Run Testing**: Run applications in `DRY_RUN` mode to inspect field-filling accuracy and answer generation without auto-submitting.

---

## Security & Ethics

- **No Credential Harvesting**: JobPilot relies on user-authenticated local browser profiles. Never hardcode or pass passwords into configuration files or prompts.
- **Human Oversight First**: Applications are gated by review checks and human alerts to prevent spamming and hallucinated responses.
- **Local Vault Isolation**: Your master profile and resume data remain on your local filesystem under `data/`.

---

## License

This project is licensed under the [MIT License](LICENSE).
