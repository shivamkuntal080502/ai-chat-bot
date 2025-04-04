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
import speech_recognition as sr
from pydub import AudioSegment
import io
import base64
from gtts import gTTS  # For text-to-speech conversion
import streamlit.components.v1 as components

# --- Email Configuration (Update these with your credentials) ---
EMAIL_SENDER = "kuntals005@gmail.com"       # Replace with your sender email
EMAIL_PASSWORD = "asbt lzzq zdjh evjr"        # Replace with your email password or app-specific password
SMTP_SERVER = "smtp.gmail.com"                # For Gmail; change if using another provider
SMTP_PORT = 465                               # For Gmail SMTP SSL

# --- Setup Gemini API Key (Hardcoded) ---
genai.configure(api_key="AIzaSyDt3AoT4n_Tin-0BvIWYv95oPbxWbyqXo8")

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

# --- (Optional) Preprocessing function (not used in this example) ---
def preprocess_text(text):
    tokens = word_tokenize(text.lower())
    lemmatizer = WordNetLemmatizer()
    tokens = [lemmatizer.lemmatize(token) for token in tokens if token.isalnum()]
    stop_words = set(stopwords.words('english'))
    tokens = [token for token in tokens if token not in stop_words]
    return tokens

# --- Gemini API Response Function ---
def generate_api_response(prompt):
    try:
        # Using Gemini 2.0 Flash model
        model = genai.GenerativeModel("gemini-2.0-flash")
        response = model.generate_content(prompt)
        return response.text.strip()
    except Exception as e:
        error_message = str(e)
        if "rate limit" in error_message.lower() or (hasattr(e, "response") and getattr(e, "response").status_code == 429):
            return "The Gemini API rate limit has been reached. Please try again later."
        else:
            return f"Error generating response: {error_message}"

# --- Extract Reminder Details using Gemini API ---
def extract_reminder_details_with_gemini(message):
    """Extracts reminder details using Gemini API."""
    today_date = datetime.datetime.now().strftime("%d:%m:%Y")
    prompt = f"""
    Extract the task, time, and date from the following reminder message. 
    - Time must be in HH:MM format (24-hour). 
    - Date must be in DD:MM:YYYY format. 
    - If the date is relative (e.g., 'tomorrow'), convert it to absolute.
    - If no date is mentioned, use today's date ({today_date}) and mark as inferred.
    
    Return response EXACTLY as:
    Task: [task]
    Time: [HH:MM]
    Date: [DD:MM:YYYY]
    DateInferred: [Yes/No]

    Message: {message}
    """
    
    response_text = generate_api_response(prompt)
    task, time_str, date_str, date_inferred = None, None, None, False
    
    try:
        # Parse Gemini's response
        for line in response_text.split('\n'):
            line = line.strip()
            if line.startswith('Task:'):
                task = line.split(':', 1)[1].strip()
            elif line.startswith('Time:'):
                time_str = line.split(':', 1)[1].strip()
            elif line.startswith('Date:'):
                date_str = line.split(':', 1)[1].strip()
            elif line.startswith('DateInferred:'):
                date_inferred = line.split(':', 1)[1].strip().lower() == 'yes'
        
        # Validate required fields
        if not task or not time_str or not date_str:
            return None, None
        
        # Parse datetime
        reminder_time = datetime.datetime.strptime(f"{date_str} {time_str}", "%d:%m:%Y %H:%M")
        now = datetime.datetime.now()
        
        # Adjust date if inferred and time is in past
        if date_inferred and reminder_time < now:
            reminder_time += datetime.timedelta(days=1)
            
        return task, reminder_time
    
    except Exception as e:
        print(f"Error parsing Gemini response: {e}")
        return None, None

# --- Notification System Functions ---
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
    threading.Timer(delay, lambda: send_notification("Reminder", task)).start()

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
    threading.Timer(delay, lambda: send_email_notification(user_email, "Reminder", f"Reminder: {task}")).start()

# --- Reminder Parsing Function (for text-based reminders) ---
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
            time_obj = datetime.datetime.strptime(time_str, "%H:%M").time()
            if date_str:
                reminder_date = datetime.datetime.strptime(date_str, "%d:%m:%Y").date()
            else:
                reminder_date = now.date()
            reminder_time = datetime.datetime.combine(reminder_date, time_obj)
            if not date_str and reminder_time < now:
                reminder_time += datetime.timedelta(days=1)
            return task, reminder_time
        except ValueError:
            return None, None
    return None, None

# --- Text-to-Speech Functionality ---
def play_audio_with_delay(audio_bytes, delay=10000):
    """
    Converts audio bytes to base64 and creates an HTML audio element that auto-plays after a delay.
    Also listens for key events: "p" to play, "s" to pause.
    Returns the HTML string so it can be stored and rendered persistently.
    """
    b64_audio = base64.b64encode(audio_bytes.read()).decode()
    audio_html = f"""
    <audio id="tts-audio" controls src="data:audio/mp3;base64,{b64_audio}"></audio>
    <script>
    // Auto-play after delay
    setTimeout(function() {{
       var audio = document.getElementById("tts-audio");
       if(audio) {{
          audio.play();
       }}
    }}, {delay});
    
    // Listen for key events: p to play, s to pause
    document.addEventListener('keydown', function(e) {{
      var audio = document.getElementById("tts-audio");
      if(!audio) return;
      if(e.key === 'p' || e.key === 'P') {{
         audio.play();
      }} else if(e.key === 's' || e.key === 'S') {{
         audio.pause();
      }}
    }});
    </script>
    """
    return audio_html

# --- Voice Command Functions ---
def transcribe_audio(audio_file):
    recognizer = sr.Recognizer()
    # Convert file to wav if necessary
    if not audio_file.name.lower().endswith('.wav'):
        try:
            audio = AudioSegment.from_file(audio_file)
            audio_file_wav = io.BytesIO()
            audio.export(audio_file_wav, format="wav")
            audio_file_wav.seek(0)
            audio_file = audio_file_wav
        except Exception as e:
            st.error(f"Error converting audio file: {e}")
            return None
    try:
        with sr.AudioFile(audio_file) as source:
            audio_data = recognizer.record(source)
            return recognizer.recognize_google(audio_data)
    except Exception as e:
        st.error(f"Error transcribing audio: {e}")
        return None

def transcribe_microphone():
    r = sr.Recognizer()
    try:
        with sr.Microphone() as source:
            with st.spinner("Listening..."):
                audio = r.listen(source, timeout=5)
        try:
            text = r.recognize_google(audio)
            return text
        except sr.UnknownValueError:
            st.error("Could not understand audio")
            return None
        except sr.RequestError as e:
            st.error(f"Error: {e}")
            return None
    except OSError:
        st.error("No microphone detected. Please ensure a microphone is connected.")
        return None

# --- Joke Function ---
def get_joke():
    url = "https://icanhazdadjoke.com/"
    headers = {"Accept": "application/json"}
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        return response.json().get("joke", "I couldn't find a joke right now.")
    else:
        return "I'm sorry, I couldn't fetch a joke right now."

# --- System Prompt for Vertex Bot ---
def get_system_prompt(user_name):
    return (f"You are Vertex, an everyday bot chatting with {user_name}. Provide helpful advice on productivity and time management. "
            "Do not include your name in your responses.")

# --- Main Function ---
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
                - `remind me to [task] at HH:MM` - Set a reminder.
                - `remind me to [task] at HH:MM on DD:MM:YYYY` - Set a reminder for a specific date.
            """
        )
        if st.button("Clear Conversation"):
            st.session_state.messages = []
            safe_rerun()

        # Checkbox for text-to-speech (TTS) option.
        st.checkbox("Read bot responses aloud", key="read_aloud", value=False)
        
        # --- Audio File Uploader for Voice Commands ---
        uploaded_audio = st.file_uploader("Upload Audio File", type=["wav", "mp3", "ogg", "m4a"])
        if uploaded_audio:
            transcribed_text = transcribe_audio(uploaded_audio)
            if transcribed_text:
                st.session_state.voice_input = transcribed_text
                safe_rerun()

    # -------------------- Session State Initialization --------------------
    if 'user_name' not in st.session_state:
        st.session_state.user_name = None
    if 'user_email' not in st.session_state:
        st.session_state.user_email = None
    if 'messages' not in st.session_state:
        st.session_state.messages = []  # Each message is a tuple: (speaker, message)
    if 'voice_input' not in st.session_state:
        st.session_state.voice_input = ""
    # Store generated TTS audio HTML so that it persists in the layout.
    if 'tts_audio' not in st.session_state:
        st.session_state.tts_audio = ""

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

    # -------------------- Ask for the User's Email (for notifications) --------------------
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

    # Render the TTS audio HTML if available.
    if st.session_state.tts_audio:
        components.html(st.session_state.tts_audio, height=200)

    # -------------------- Text & Voice Query Input --------------------
    col1, col2 = st.columns([5,1])
    with col1:
        with st.form(key="chat_form", clear_on_submit=True):
            # Prefill with any voice input if available.
            user_message = st.text_input("Enter your query here", placeholder="Ask me anything...", value=st.session_state.voice_input)
            submitted = st.form_submit_button("Send")
    with col2:
        if st.button("🎤", help="Press and speak"):
            transcribed_text = transcribe_microphone()
            if transcribed_text:
                st.session_state.voice_input = transcribed_text
                safe_rerun()

    if submitted and user_message.strip() != "":
        st.session_state.messages.append(("user", user_message.strip()))
        lower_msg = user_message.lower()

        # Check if the user is asking for a reminder using Gemini API extraction
        if "remind me" in lower_msg:
            # First try the regex parser
            task, reminder_time = parse_reminder(user_message)
            # If regex parsing fails, try using Gemini API extraction
            if not task or not reminder_time:
                task, reminder_time = extract_reminder_details_with_gemini(user_message)
            if task and reminder_time:
                schedule_notification(reminder_time, task)
                schedule_email_notification(reminder_time, task, st.session_state.user_email)
                response = (
                    f"Okay, I will remind you to {task} at {reminder_time.strftime('%H:%M')} "
                    f"on {reminder_time.strftime('%d:%m:%Y')} via desktop notification and an email to {st.session_state.user_email}."
                )
            else:
                response = ("I couldn't understand the reminder. Please use the format: "
                            "'remind me to [task] at HH:MM' or "
                            "'remind me to [task] at HH:MM on DD:MM:YYYY'.")
        elif "joke" in lower_msg:
            response = get_joke()
        else:
            prompt = ""
            for speaker, msg in st.session_state.messages:
                if speaker == "user":
                    prompt += f"User: {msg}\n"
                elif speaker == "bot":
                    prompt += f"Bot: {msg}\n"
            system_prompt = get_system_prompt(st.session_state.user_name)
            full_prompt = system_prompt + "\n" + prompt
            response = generate_api_response(full_prompt)

        st.session_state.messages.append(("bot", response))
        st.session_state.voice_input = ""  # Clear any voice input after processing

        # If the TTS option is enabled, convert the bot response to speech.
        if st.session_state.get("read_aloud", False):
            try:
                tts = gTTS(response)
                audio_bytes = io.BytesIO()
                tts.write_to_fp(audio_bytes)
                audio_bytes.seek(0)
                # Generate HTML for the audio player with delay and key controls.
                audio_html = play_audio_with_delay(audio_bytes, delay=2000)
                # Store it in session state so it persists.
                st.session_state.tts_audio = audio_html
            except Exception as e:
                st.error(f"Error in text-to-speech conversion: {e}")
        safe_rerun()

    st.markdown("</div>", unsafe_allow_html=True)
    st.markdown(
        """
        **Note:** This app runs in a controlled environment. For full file access, run locally.
        """
    )

if __name__ == "__main__":
    main()
