# Company XYZ Employee Guide Q&A

A small Gradio chatbot that answers questions about a PDF employee handbook
(for the fictional "Company XYZ") using the OpenAI API. If the assistant can't
help, a "Need more help?" form emails HR.

**Live demo:** _add your Render URL here_ (free hosting — the first load after
a quiet period can take about a minute while the server wakes up)

## How it works

1. At startup, the PDF is read once with `pypdf` and its text is held in memory.
2. Each question is sent to `gpt-4o-mini` along with the full document text and
   the chat history, with instructions to answer only from the document.
3. The "Need more help?" form validates input and emails HR through Brevo's
   HTTPS API (or SMTP when running locally).

Limitations: the whole document is sent with every question, so it suits short
documents (the text is capped at 60,000 characters). Retrieval over chunks
would be the next step for longer documents.

## Run locally

```bash
pip install -r requirements.txt
export OPENAI_API_KEY="sk-..."
python app.py
```

Open http://127.0.0.1:7860.

## Configuration (environment variables)

| Variable | Required | Purpose |
| --- | --- | --- |
| `OPENAI_API_KEY` | yes | OpenAI access |
| `HR_EMAIL` | for email | Where help requests are sent |
| `BREVO_API_KEY`, `BREVO_SENDER_EMAIL` | for email on Render | Send via Brevo's HTTPS API (the sender must be verified in Brevo) |
| `SMTP_USERNAME`, `SMTP_PASSWORD` | alternative for local use | Send via SMTP (`SMTP_HOST`/`SMTP_PORT` default to Gmail) |

Never commit keys; `.gitignore` excludes `.env`.

## Deploying on Render (free)

- Build command: `pip install -r requirements.txt`
- Start command: `python app.py`
- Add the environment variables above in the Render dashboard.

Render's free tier blocks SMTP ports, which is why the Brevo API option exists.
The app binds to Render's `PORT` automatically.
