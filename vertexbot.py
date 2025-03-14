import os
import time
import datetime
import requests
import streamlit as st
import google.generativeai as genai
import nltk
import re
import threading
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from plyer import notification  # Desktop notification library

# --- Email Configuration (Update these with your credentials) ---
EMAIL_SENDER = ""       # Replace with your sender email
EMAIL_PASSWORD = ""        # Replace with your email password or app-specific password
SMTP_SERVER = ""                # For Gmail; change if using another provider
SMTP_PORT = 465                               # For Gmail SMTP SSL

# --- Setup Gemini API Key (Hardcoded) ---
genai.configure(api_key="")

# --- Download necessary NLTK packages ---
nltk.download('punkt')
nltk.download('wordnet')
nltk.download('stopwords')

from nltk.tokenize import word_tokenize
from nltk.corpus import stopwords
from nltk.stem import WordNetLemmatizer

# --- Safe Rerun Helper ---
def safe_rerun():
    if hasattr(st, "experimental_rerun"):
        st.experimental_rerun()
    elif hasattr(st, "rerun"):
        st.rerun()

# (Optional) Preprocessing function (not used in this example)
def preprocess_text(text):
    tokens = word_tokenize(text.lower())
    lemmatizer = WordNetLemmatizer()
    tokens = [lemmatizer.lemmatize(token) for token in tokens if token.isalnum()]
    stop_words = set(stopwords.words('english'))
    tokens = [token for token in tokens if token not in stop_words]
    return tokens

# Function to fetch a joke using an external API
def get_joke():
    url = "https://icanhazdadjoke.com/"
    headers = {"Accept": "application/json"}
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        return response.json().get("joke", "I couldn't find a joke right now.")
    else:
        return "I'm sorry, I couldn't fetch a joke right now."

# Function to generate responses using Gemini AI (Vertex bot)
def generate_api_response(prompt):
    try:
        # Using Gemini 2.0 Flash model
        model = genai.GenerativeModel("gemini-2.0-flash")
        response = model.generate_content(prompt)
        return response.text.strip()
    except Exception as e:
        error_message = str(e)
        # Check for rate limit errors by keyword or HTTP 429 status if available.
        if "rate limit" in error_message.lower() or (hasattr(e, "response") and getattr(e, "response").status_code == 429):
            return "The Gemini API rate limit has been reached. Please try again later."
        else:
            return f"Error generating response: {error_message}"

# Function to get the system prompt for the Vertex bot.
def get_system_prompt(user_name):
    return (f"You are Vertex, an everyday bot chatting with {user_name}. Provide helpful advice on productivity and time management. "
            "Do not include your name in your responses.")

# --- Notification System Functions ---

# Desktop notification using plyer
def send_notification(title, message):
    notification.notify(
        title=title,
        message=message,
        app_name='Vertex Bot',
        timeout=10  # seconds
    )

def schedule_notification(reminder_time, task):
    current_time = datetime.datetime.now()
    delay = (reminder_time - current_time).total_seconds()
    if delay < 0:
        delay = 0
    # Schedule the desktop notification in a background thread.
    threading.Timer(delay, lambda: send_notification("Reminder", task)).start()

# Email notification function using SMTP
def send_email_notification(user_email, subject, message):
    msg = MIMEMultipart()
    msg["From"] = EMAIL_SENDER
    msg["To"] = user_email
    msg["Subject"] = subject
    msg.attach(MIMEText(message, "plain"))
    try:
        with smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT) as server:
            server.login(EMAIL_SENDER, EMAIL_PASSWORD)
            server.send_message(msg)
    except Exception as e:
        print(f"Error sending email: {e}")

def schedule_email_notification(reminder_time, task, user_email):
    current_time = datetime.datetime.now()
    delay = (reminder_time - current_time).total_seconds()
    if delay < 0:
        delay = 0
    # Schedule the email notification in a background thread.
    threading.Timer(delay, lambda: send_email_notification(user_email, "Reminder", f"Reminder: {task}")).start()

def parse_reminder(message):
    """
    Expects message in one of the following formats:
    "remind me to [task] at HH:MM"
    or
    "remind me to [task] at HH:MM on DD:MM:YYYY"
    """
    pattern = r"remind me to (.+?) at (\d{1,2}:\d{2})(?: on (\d{1,2}:\d{1,2}:\d{4}))?"
    match = re.search(pattern, message.lower())
    if match:
        task = match.group(1).strip()
        time_str = match.group(2).strip()
        date_str = match.group(3).strip() if match.group(3) else None
        now = datetime.datetime.now()
        try:
            # Convert time string to a time object
            time_obj = datetime.datetime.strptime(time_str, "%H:%M").time()
            if date_str:
                # Parse the provided date in DD:MM:YYYY format
                reminder_date = datetime.datetime.strptime(date_str, "%d:%m:%Y").date()
            else:
                reminder_date = now.date()
            # Combine the date and time to get the full reminder datetime
            reminder_time = datetime.datetime.combine(reminder_date, time_obj)
            # If no date is provided and the time is already passed today, schedule for tomorrow.
            if not date_str and reminder_time < now:
                reminder_time += datetime.timedelta(days=1)
            return task, reminder_time
        except ValueError:
            return None, None
    return None, None

def main():
    # -------------------- Custom CSS --------------------
    st.markdown(
        """
        <style>
        .main {
            background-color: #f0f8ff;
            padding: 2rem;
            border-radius: 10px;
        }
        .chat-container {
            max-height: 500px;
            overflow-y: auto;
            padding: 10px;
            border: 1px solid #ddd;
            background-color: #f9f9f9;
            border-radius: 10px;
            margin-bottom: 1rem;
        }
        .message {
            margin: 10px 0;
            padding: 10px 15px;
            border-radius: 10px;
            max-width: 80%;
        }
        .message-user {
            background-color: #d1e7dd;
            text-align: right;
            margin-left: auto;
        }
        .message-vertex {
            background-color: #cff4fc;
            text-align: left;
        }
        </style>
        """,
        unsafe_allow_html=True
    )

    st.markdown('<div class="main">', unsafe_allow_html=True)
    st.title("Vertex - Everyday Bot")

    # -------------------- Sidebar Panel --------------------
    with st.sidebar:
        st.header("Vertex Assistant")
        st.markdown(
            """
            **Usage Instructions:**
            - Type your query or command in the text box.
            - Special commands you can try:
                - `joke` - Ask for a joke.
                - `remind me to [task] at HH:MM` - Set a reminder (desktop & email).
                - `remind me to [task] at HH:MM on DD:MM:YYYY` - Set a reminder for a specific date.
            """
        )
        if st.button("Clear Conversation"):
            st.session_state.messages = []
            safe_rerun()

    # -------------------- Session State Initialization --------------------
    if 'user_name' not in st.session_state:
        st.session_state.user_name = None
    if 'user_email' not in st.session_state:
        st.session_state.user_email = None
    if 'messages' not in st.session_state:
        st.session_state.messages = []  # Each message is a tuple: (speaker, message)

    # -------------------- Ask for the User's Name --------------------
    if st.session_state.user_name is None:
        user_name_input = st.text_input("Please enter your name:", key="name_input")
        if st.button("Start Chat"):
            if user_name_input.strip() != "":
                st.session_state.user_name = user_name_input.strip()
                system_prompt = get_system_prompt(st.session_state.user_name)
                greeting = "Hi, I am Vertex, your everyday bot. How can I help you today?"
                st.session_state.messages.append(("system", system_prompt))
                st.session_state.messages.append(("bot", greeting))
                safe_rerun()
            else:
                st.error("Please enter a valid name.")
        st.stop()

    # -------------------- Ask for the User's Email (for email notifications) --------------------
    if not st.session_state.user_email:
        email_input = st.text_input("Please enter your email for notifications:", key="email_input")
        if st.button("Set Email"):
            if email_input.strip() != "":
                st.session_state.user_email = email_input.strip()
                safe_rerun()
            else:
                st.error("Please enter a valid email address.")
        st.stop()

    # -------------------- Chat Conversation Area --------------------
    st.subheader("Conversation")
    chat_container = st.container()
    with chat_container:
        st.markdown('<div class="chat-container">', unsafe_allow_html=True)
        for speaker, message in st.session_state.messages:
            if speaker == "bot":
                st.markdown(f'<div class="message message-vertex"><strong>Vertex:</strong> {message}</div>', unsafe_allow_html=True)
            elif speaker == "user":
                st.markdown(f'<div class="message message-user"><strong>You:</strong> {message}</div>', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)

    # -------------------- Text-based Query Input --------------------
    with st.form(key="chat_form", clear_on_submit=True):
        user_message = st.text_input("Enter your query here", placeholder="Ask me anything...")
        submit_button = st.form_submit_button("Send")

    if submit_button and user_message.strip() != "":
        st.session_state.messages.append(("user", user_message.strip()))
        lower_msg = user_message.lower()

        # Check if the user is asking for a reminder
        if "remind me" in lower_msg:
            task, reminder_time = parse_reminder(user_message)
            if task and reminder_time:
                schedule_notification(reminder_time, task)
                # Schedule email notification using the provided email.
                schedule_email_notification(reminder_time, task, st.session_state.user_email)
                response = (f"Okay, I will remind you to {task} at {reminder_time.strftime('%H:%M')} "
                            f"on {reminder_time.strftime('%d:%m:%Y')} via desktop notification and an email to {st.session_state.user_email}.")
            else:
                response = "I couldn't understand the reminder. Please use the format: 'remind me to [task] at HH:MM' or 'remind me to [task] at HH:MM on DD:MM:YYYY'."
        else:
            # Special case: if the user asks for a joke
            if "joke" in lower_msg:
                response = get_joke()
            else:
                # Build conversation prompt using markers.
                prompt = ""
                for speaker, msg in st.session_state.messages:
                    if speaker == "user":
                        prompt += f"User: {msg}\n"
                    elif speaker == "bot":
                        prompt += f"Bot: {msg}\n"
                # Prepend the system prompt.
                system_prompt = get_system_prompt(st.session_state.user_name)
                full_prompt = system_prompt + "\n" + prompt
                response = generate_api_response(full_prompt)

        st.session_state.messages.append(("bot", response))
        safe_rerun()

    st.markdown("</div>", unsafe_allow_html=True)

# Only execute the bot when this file is run directly.
if __name__ == "__main__":
    main()
