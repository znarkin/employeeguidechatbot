# %%
from pypdf import PdfReader
import gradio as gr
from openai import OpenAI
import os
from dotenv import load_dotenv
import re
from email.mime.text import MIMEText
import smtplib
import ssl

# %%
"""
PDF Q&A App using Gradio + OpenAI (ChatGPT) API
-------------------------------------------------
Upload a PDF, then ask questions about its contents. The app extracts text
from the PDF and sends it (along with your question) to the OpenAI Chat
Completions API for an answer.

Setup:
    pip install -r requirements.txt

    Set your OpenAI API key as an environment variable before running:
        macOS/Linux:  export OPENAIa_API_KEY="sk-..."
        Windows:      setx OPENAI_API_KEY "sk-..."   (open a new terminal after)

Run:
    python pdf_qa_app.py
"""



# %%
# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

MODEL_NAME = "gpt-4o-mini"          # change to "gpt-4o", "gpt-4-turbo", etc.
MAX_CONTEXT_CHARS = 60000           # rough cap so we don't blow the context window
PDF_FILENAME = "Company_XYZ_Employee_Guide.pdf"
DOCUMENT_TITLE = "Company XYZ Employee Guide"

# --- "Need more help?" email settings -------------------------------------
# These are read from environment variables so no credentials live in this
# file. For Gmail: use an "App Password" (not your regular password) —
# https://myaccount.google.com/apppasswords — and SMTP_HOST/PORT defaults
# below already match Gmail's settings.
SMTP_HOST = os.environ.get("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.environ.get("SMTP_PORT", "587"))
SMTP_USERNAME = os.environ.get("SMTP_USERNAME")
SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD")
SMTP_FROM_EMAIL = os.environ.get("SMTP_FROM_EMAIL", SMTP_USERNAME)
HR_EMAIL = os.environ.get("HR_EMAIL", "hr@companyxyz.example")

# Resolve the PDF path relative to this script's location, so the app finds
# it regardless of the folder you launch it from.
# Resolve the PDF path relative to this script's location, so the app finds
# it regardless of the folder you launch it from. Falls back to the current
# working directory if __file__ isn't available (e.g. running in a Jupyter
# notebook, IPython shell, or certain IDE "run" modes).
try:
    SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
except NameError:
    SCRIPT_DIR = os.getcwd()
PDF_PATH = os.path.join(SCRIPT_DIR, PDF_FILENAME)

load_dotenv(override=True)

openai_api_key = os.getenv('OPENAI_API_KEY')
if openai_api_key:
    print(f"OpenAI API Key exists and begins {openai_api_key[:8]}")
else:
    print("OpenAI API Key not set")
    


client = OpenAI()  # reads OPENAI_API_KEY from the environment automatically

# %%
# ---------------------------------------------------------------------------
# PDF handling
# ---------------------------------------------------------------------------
def extract_pdf_text(path: str) -> str:
    """Extract all text from a PDF file on disk."""
    reader = PdfReader(path)
    pages_text = []
    for i, page in enumerate(reader.pages):
        text = page.extract_text() or ""
        pages_text.append(f"--- Page {i + 1} ---\n{text}")
 
    full_text = "\n\n".join(pages_text)
 
    if len(full_text) > MAX_CONTEXT_CHARS:
        full_text = full_text[:MAX_CONTEXT_CHARS] + "\n\n[...truncated, document too long...]"
 
    return full_text
 
 
if not os.path.exists(PDF_PATH):
    raise FileNotFoundError(
        f"Couldn't find '{PDF_FILENAME}' next to this script.\n"
        f"Expected it at: {PDF_PATH}\n"
        f"Make sure the PDF is in the same folder as pdf_qa_app.py, "
        f"or update PDF_FILENAME at the top of this file."
    )
 
PDF_TEXT = extract_pdf_text(PDF_PATH)
print(f"Loaded '{PDF_FILENAME}' ({len(PDF_TEXT):,} characters extracted).")
 



# %%
SYSTEM_PROMPT = (
    "You are a helpful assistant that answers questions based on "
    "the contents of the document below. You should be friendly, and you can respond to greetings such as Hi and How are you, but"
    "besides that, if the answer isn't in the document, "
    "reply by saying 'This information is not available. Feel free to use the contact button below if I can't answer your question.' rather than guessing.\n\n"
    f"DOCUMENT: {DOCUMENT_TITLE}\n\n{PDF_TEXT}")

WELCOME_MESSAGE = [{
    "role": "assistant",
    "content": (
        f"👋 Hi there! What questions can I answer about Company XYZ polies/procedures?"
    ),
}]

# %%

# ---------------------------------------------------------------------------
# Chat logic
# ---------------------------------------------------------------------------
def answer_question(question, history):
    """Send the question + fixed document context + chat history to the OpenAI API."""
    history = history or []
 
    if not question or not question.strip():
        return history, ""
 
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    messages.extend(history)
    messages.append({"role": "user", "content": question})
 
    try:
        response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=messages,
            temperature=0.3,
        )
        answer = response.choices[0].message.content
    except Exception as e:
        answer = f"Error calling OpenAI API: {e}"
 
    history = history + [
        {"role": "user", "content": question},
        {"role": "assistant", "content": answer},
    ]
    return history, ""
 
 
def clear_chat():
    return WELCOME_MESSAGE, ""


# %%
# ---------------------------------------------------------------------------
# "Need more help?" — sends a question to HR by email
# ---------------------------------------------------------------------------
 
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
 
 
def send_help_request(name: str, email: str, question: str) -> str:
    """Validate the form and email the request to HR. Returns a status message
    starting with ✅ on success or ⚠️/❌ on a problem, so the caller can tell
    them apart."""
    name = (name or "").strip()
    email = (email or "").strip()
    question = (question or "").strip()
 
    if not name or not email or not question:
        return "⚠️ Please fill in your name, email, and question before submitting."
 
    if not EMAIL_RE.match(email):
        return "⚠️ That doesn't look like a valid email address — please double-check it."
 
    if not SMTP_USERNAME or not SMTP_PASSWORD:
        return (
            "⚠️ Email sending isn't configured yet. Ask whoever runs this app to "
            "set the SMTP_USERNAME and SMTP_PASSWORD environment variables "
            "(see the comment at the top of pdf_qa_app.py)."
        )
 
    subject = f"Employee Help Request from {name}"
    body = (
        f"A user submitted a help request via the {DOCUMENT_TITLE} assistant.\n\n"
        f"Name: {name}\n"
        f"Email: {email}\n\n"
        f"Question:\n{question}\n"
    )
    msg = MIMEText(body)
    msg["Subject"] = subject
    msg["From"] = SMTP_FROM_EMAIL
    msg["To"] = HR_EMAIL
    msg["Reply-To"] = email  # so HR can hit "Reply" and go straight to the employee
 
    try:
        context = ssl.create_default_context()
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=15) as server:
            server.starttls(context=context)
            server.login(SMTP_USERNAME, SMTP_PASSWORD)
            server.sendmail(SMTP_FROM_EMAIL, [HR_EMAIL], msg.as_string())
        first_name = name.split()[0] if name.split() else name
        return f"✅ Thanks {first_name}! Your question has been sent to HR — they'll follow up at {email}."
    except Exception as e:
        return f"❌ Something went wrong sending your message: {e}"
 
 
def submit_help_request(name: str, email: str, question: str):
    """Wraps send_help_request for the UI: clears the form on success,
    keeps the user's input on failure so they don't have to retype it."""
    status = send_help_request(name, email, question)
    if status.startswith("✅"):
        return status, "", "", ""
    return status, name, email, question

# %%



# ---------------------------------------------------------------------------
# Gradio UI
# ---------------------------------------------------------------------------

with gr.Blocks(title=f"Q&A: {DOCUMENT_TITLE}") as demo:
    gr.Markdown(f"# 📄 Ask about the {DOCUMENT_TITLE}")
    # gr.Markdown(
    #     f"This assistant has already read *{DOCUMENT_TITLE}* "
    #     f"({len(PDF_TEXT):,} characters) — just ask your question below."
    # )
 
    chatbot = gr.Chatbot(label="Q&A", height=450, value=WELCOME_MESSAGE)
    question_box = gr.Textbox(
        label="Ask a question",
        placeholder="e.g. How many vacation days do I get after 3 years?",
    )
    with gr.Row():
        ask_btn = gr.Button("Ask", variant="primary")
        clear_btn = gr.Button("Clear chat")
 
    ask_btn.click(
        fn=answer_question,
        inputs=[question_box, chatbot],
        outputs=[chatbot, question_box],
    )
    question_box.submit(
        fn=answer_question,
        inputs=[question_box, chatbot],
        outputs=[chatbot, question_box],
    )
    clear_btn.click(fn=clear_chat, outputs=[chatbot, question_box])

# --- "Need more help?" section -----------------------------------------
    need_help_btn = gr.Button("🆘 Need more help?")
 
    with gr.Group(visible=False) as help_form:
        gr.Markdown("### Contact HR")
        name_box = gr.Textbox(label="Your Name")
        email_box = gr.Textbox(label="Your Email", placeholder="you@example.com")
        help_question_box = gr.Textbox(
            label="Your Question", lines=3,
            placeholder="What do you need help with?",
        )
        with gr.Row():
            submit_help_btn = gr.Button("Submit to HR", variant="primary")
            cancel_help_btn = gr.Button("Cancel")
        help_status = gr.Markdown("")
 
    need_help_btn.click(fn=lambda: gr.update(visible=True), outputs=help_form)
 
    cancel_help_btn.click(
        fn=lambda: (gr.update(visible=False), "", "", "", ""),
        outputs=[help_form, name_box, email_box, help_question_box, help_status],
    )
 
    submit_help_btn.click(
        fn=submit_help_request,
        inputs=[name_box, email_box, help_question_box],
        outputs=[help_status, name_box, email_box, help_question_box],
    )
 
if __name__ == "__main__":
    # Force dark mode automatically: Gradio reads the `__theme` URL parameter
    # on page load, so this redirects once (on first load) to add it.
    force_dark_theme_js = """
    () => {
        const url = new URL(window.location.href);
        if (url.searchParams.get('__theme') !== 'dark') {
            url.searchParams.set('__theme', 'dark');
            window.location.href = url.toString();
        }
    }
    """
    demo.launch(js=force_dark_theme_js, share=True)



