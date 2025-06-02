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
import pytesseract  # Tesseract OCR library
from PIL import Image  # For image processing
from urllib.parse import urlparse, parse_qs
from youtube_transcript_api import YouTubeTranscriptApi  # For YouTube transcript extraction

# --- Configure Tesseract Path (update the path as needed) ---
# Uncomment and update the following line if you are on Windows:
# pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

# --- API Keys (Update these with your credentials) ---
EMAIL_SENDER = "kuntals005@gmail.com"       # Replace with your sender email
EMAIL_PASSWORD = ""        # Replace with your email password or app-specific password
SMTP_SERVER = ""                # For Gmail; change if using another provider
SMTP_PORT = 465                               # For Gmail SMTP SSL

# Gemini API
genai.configure(api_key="")

# Additional API Keys
OPENWEATHER_API_KEY = ""  # Replace with your OpenWeatherMap API key
NEWS_API_KEY = ""          # Replace with your NewsAPI key
FINHUB_API_KEY = ""  # Replace with your Finhub API key

# --- Download necessary NLTK packages ---
nltk.download('punkt')
nltk.download('wordnet')
nltk.download('stopwords')
nltk.download('vader_lexicon')
from nltk.tokenize import word_tokenize
from nltk.corpus import stopwords
from nltk.stem import WordNetLemmatizer
from nltk.sentiment.vader import SentimentIntensityAnalyzer

# --- Email Validation Function ---
def is_valid_email(email):
    pattern = r'^[\w\.-]+@[\w\.-]+\.\w+$'
    return re.match(pattern, email)

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

# --- Advanced NLP: Sentiment Analysis ---
def analyze_sentiment(text):
    sid = SentimentIntensityAnalyzer()
    sentiment = sid.polarity_scores(text)
    return sentiment

# --- Advanced NLP: Simple Intent Detection ---
def detect_intent(text):
    lower_text = text.lower()
    if "remind me" in lower_text:
        return "reminder"
    elif "joke" in lower_text:
        return "joke"
    elif lower_text.startswith("search"):
        return "search"
    return "chat"

# --- Gemini API Response Function ---
def generate_api_response(prompt):
    try:
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
    today_date = datetime.datetime.now().strftime("%d:%m:%Y")
    prompt = f"""
    Extract the task, time, date, and recurring frequency from the following reminder message. 
    - Time must be in HH:MM format (24-hour). 
    - Date must be in DD:MM:YYYY format.
    - Recurring frequency should be one of: daily, weekly, monthly. If no recurrence, return 'None'.
    - If the date is relative (e.g., 'tomorrow'), convert it to absolute.
    - If no date is mentioned, use today's date ({today_date}) and mark as inferred.
    
    Return response EXACTLY as:
    Task: [task]
    Time: [HH:MM]
    Date: [DD:MM:YYYY]
    Recurrence: [daily/weekly/monthly/None]

    Message: {message}
    """
    
    response_text = generate_api_response(prompt)
    task, time_str, date_str, recurrence = None, None, None, None
    
    try:
        for line in response_text.split('\n'):
            line = line.strip()
            if line.startswith('Task:'):
                task = line.split(':', 1)[1].strip()
            elif line.startswith('Time:'):
                time_str = line.split(':', 1)[1].strip()
            elif line.startswith('Date:'):
                date_str = line.split(':', 1)[1].strip()
            elif line.startswith('Recurrence:'):
                recurrence = line.split(':', 1)[1].strip().lower()
                if recurrence == "none":
                    recurrence = None
        
        if not task or not time_str or not date_str:
            return None, None, None
        
        reminder_time = datetime.datetime.strptime(f"{date_str} {time_str}", "%d:%m:%Y %H:%M")
        now = datetime.datetime.now()
        if reminder_time < now:
            reminder_time += datetime.timedelta(days=1)
            
        return task, reminder_time, recurrence
    
    except Exception as e:
        print(f"Error parsing Gemini response: {e}")
        return None, None, None

# --- Recurring Reminder Parser ---
def parse_reminder(message):
    pattern = r"remind me to (.+?) at (\d{1,2}:\d{2})(?: on (\d{1,2}:\d{1,2}:\d{4}))?(?: (daily|weekly|monthly))?"
    match = re.search(pattern, message.lower())
    if match:
        task = match.group(1).strip()
        time_str = match.group(2).strip()
        date_str = match.group(3).strip() if match.group(3) else None
        recurrence = match.group(4).strip() if match.group(4) else None
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
            return task, reminder_time, recurrence
        except ValueError:
            return None, None, None
    return None, None, None

# --- Notification System Functions ---
def send_notification(title, message):
    notification.notify(
        title=title,
        message=message,
        app_name='Vertex Bot',
        timeout=10
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

def schedule_recurring_notification(reminder_time, task, recurrence, user_email):
    def notify_and_reschedule():
        send_notification("Reminder", task)
        send_email_notification(user_email, "Reminder", f"Reminder: {task}")
        if recurrence == "daily":
            next_time = reminder_time + datetime.timedelta(days=1)
        elif recurrence == "weekly":
            next_time = reminder_time + datetime.timedelta(weeks=1)
        elif recurrence == "monthly":
            next_time = reminder_time + datetime.timedelta(days=30)
        else:
            return
        delay = (next_time - datetime.datetime.now()).total_seconds()
        if delay < 0:
            delay = 0
        threading.Timer(delay, notify_and_reschedule).start()
    delay = (reminder_time - datetime.datetime.now()).total_seconds()
    if delay < 0:
        delay = 0
    threading.Timer(delay, notify_and_reschedule).start()

# --- Text-to-Speech Functionality ---
def play_audio_with_delay(audio_bytes, delay=10000):
    b64_audio = base64.b64encode(audio_bytes.read()).decode()
    audio_html = f"""
    <audio id="tts-audio" controls src="data:audio/mp3;base64,{b64_audio}"></audio>
    <script>
    setTimeout(function() {{
       var audio = document.getElementById("tts-audio");
       if(audio) {{
          audio.play();
       }}
    }}, {delay});
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

# --- OCR Functionality using Tesseract ---
def perform_ocr(image_file, lang="eng"):
    try:
        image = Image.open(image_file)
        extracted_text = pytesseract.image_to_string(image, lang=lang)
        return extracted_text.strip()
    except Exception as e:
        st.error(f"Error during OCR processing: {e}")
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

# --- Smart Web Search Function ---
def smart_web_search(query):
    endpoint = "https://api.duckduckgo.com/"
    params = {
        "q": query,
        "format": "json",
        "no_html": 1,
        "skip_disambig": 1
    }
    response = requests.get(endpoint, params=params)
    results = []
    if response.status_code == 200:
        data = response.json()
        if data.get("AbstractText"):
            results.append({
                "title": data.get("Heading", "Result"),
                "url": data.get("AbstractURL", ""),
                "snippet": data.get("AbstractText", "")
            })
        elif data.get("RelatedTopics"):
            for topic in data.get("RelatedTopics", []):
                if isinstance(topic, dict) and topic.get("Text") and topic.get("FirstURL"):
                    results.append({
                        "title": topic.get("Text"),
                        "url": topic.get("FirstURL"),
                        "snippet": topic.get("Text")
                    })
    return results

# --- YouTube Transcript Extraction Function ---
def extract_youtube_transcript(video_url):
    try:
        parsed_url = urlparse(video_url)
        query_params = parse_qs(parsed_url.query)
        video_id = None
        if "v" in query_params:
            video_id = query_params["v"][0]
        else:
            video_id = parsed_url.path.split("/")[-1]
        if not video_id:
            return "Could not extract video ID from URL."
        transcript_list = YouTubeTranscriptApi.get_transcript(video_id)
        transcript_text = ""
        for segment in transcript_list:
            start = str(datetime.timedelta(seconds=int(segment["start"])))
            transcript_text += f"[{start}] {segment['text']}\n"
        return transcript_text
    except Exception as e:
        return f"Error extracting transcript: {e}"

# --- Weather API Function ---
def get_weather(location):
    url = f"http://api.openweathermap.org/data/2.5/weather?q={location}&appid={OPENWEATHER_API_KEY}&units=metric"
    response = requests.get(url)
    if response.status_code == 200:
        data = response.json()
        weather_desc = data["weather"][0]["description"].capitalize()
        temp = data["main"]["temp"]
        humidity = data["main"]["humidity"]
        return f"Weather in {location}: {weather_desc} with a temperature of {temp}°C and humidity of {humidity}%."
    else:
        return "Could not retrieve weather data. Please check the location or API key."

# --- News API Function ---
def get_news(query=None):
    base_url = "https://newsapi.org/v2/top-headlines"
    params = {
        "apiKey": NEWS_API_KEY,
        "country": "us"
    }
    if query:
        params["q"] = query
    response = requests.get(base_url, params=params)
    if response.status_code == 200:
        data = response.json()
        articles = data.get("articles", [])
        if articles:
            news_str = ""
            for article in articles[:5]:
                title = article.get("title", "No Title")
                url = article.get("url", "")
                news_str += f"- [{title}]({url})\n"
            return news_str
        else:
            return "No news articles found."
    else:
        return "Could not retrieve news data. Please check your API key and parameters."

# --- Finhub Stock API Function ---
def get_stock_info(symbol):
    url = f"https://finnhub.io/api/v1/quote?symbol={symbol}&token={FINHUB_API_KEY}"
    response = requests.get(url)
    if response.status_code == 200:
        data = response.json()
        current_price = data.get("c")
        high_price = data.get("h")
        low_price = data.get("l")
        open_price = data.get("o")
        previous_close = data.get("pc")
        if current_price is not None:
            return (f"Stock: {symbol.upper()}\n"
                    f"Current Price: {current_price}\n"
                    f"High: {high_price}\n"
                    f"Low: {low_price}\n"
                    f"Open: {open_price}\n"
                    f"Previous Close: {previous_close}")
        else:
            return "Could not retrieve stock data. Please check the symbol."
    else:
        return "Error retrieving stock data."

# --- System Prompt for Vertex Bot ---
def get_system_prompt(user_name):
    return (f"You are Vertex, an everyday bot chatting with {user_name}. Provide helpful advice on productivity and time management. "
            "Do not include your name in your responses.")

# --- Chat History Analysis Function ---
def analyze_chat_history():
    if 'messages' not in st.session_state or not st.session_state.messages:
        return "No conversation history available."
    # Filter user messages
    user_messages = [msg for speaker, msg in st.session_state.messages if speaker == "user"]
    if not user_messages:
        return "No user messages to analyze."
    # Combine messages and tokenize
    all_text = " ".join(user_messages)
    tokens = word_tokenize(all_text.lower())
    stop_words = set(stopwords.words('english'))
    filtered_tokens = [token for token in tokens if token.isalnum() and token not in stop_words]
    freq_dist = nltk.FreqDist(filtered_tokens)
    most_common = freq_dist.most_common(5)
    # Calculate average sentiment of user messages
    sentiments = [analyze_sentiment(msg)['compound'] for msg in user_messages]
    avg_sentiment = sum(sentiments) / len(sentiments)
    # Generate suggestions based on sentiment and common topics
    suggestions = []
    if avg_sentiment < -0.3:
        suggestions.append("It seems like you've had some negative moments. Consider engaging in topics that boost your mood or seeking support if needed.")
    elif avg_sentiment > 0.3:
        suggestions.append("Your overall sentiment is positive. Keep up the positive interactions!")
    else:
        suggestions.append("Your sentiment appears neutral. Perhaps you might explore new topics to enrich the conversation.")
    common_topics = [word for word, count in most_common]
    if "weather" in common_topics:
        suggestions.append("You frequently ask about the weather. Consider setting daily weather notifications.")
    if "remind" in common_topics or "reminder" in common_topics:
        suggestions.append("It appears you often set reminders. Would you like to see some tips on managing your schedule?")
    if "news" in common_topics:
        suggestions.append("You seem interested in current events. How about customizing your news feed further?")
    analysis_text = (
        f"Analysis of your chat history:\n\n"
        f"Average sentiment: {avg_sentiment:.2f}\n"
        f"Common topics: {', '.join(common_topics)}\n\n"
        "Suggestions:\n" + "\n".join(f"- {s}" for s in suggestions)
    )
    return analysis_text

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
            - Use the mode selector below.
            - **Chat:** Type your queries or commands.
            - **YouTube Transcript Extraction:** Enter a YouTube URL to extract its transcript.
            - Special commands (in Chat mode):
                - `joke` - Ask for a joke.
                - `remind me to [task] at HH:MM` - Set a reminder.
                - `search [query]` - Web search.
            """
        )
        mode = st.radio("Select Mode", ["Chat", "YouTube Transcript Extraction"], key="mode_selection")
        if st.button("Clear Conversation"):
            st.session_state.messages = []
            safe_rerun()

        st.checkbox("Read bot responses aloud", key="read_aloud", value=False)
        
        # --- Audio File Uploader for Voice Commands ---
        uploaded_audio = st.file_uploader("Upload Audio File", type=["wav", "mp3", "ogg", "m4a"])
        if uploaded_audio:
            transcribed_text = transcribe_audio(uploaded_audio)
            if transcribed_text:
                st.session_state.voice_input = transcribed_text
                safe_rerun()
        
        # --- OCR Image Uploader with Language Selection ---
        ocr_language = st.selectbox("Select OCR Language", options=["eng", "spa", "fra"], index=0)
        uploaded_image = st.file_uploader("Upload Image for OCR", type=["png", "jpg", "jpeg", "tiff"])
        if uploaded_image:
            ocr_text = perform_ocr(uploaded_image, lang=ocr_language)
            if ocr_text:
                st.markdown("### Extracted OCR Text:")
                st.text_area("OCR Output", value=ocr_text, height=150)
                st.session_state.voice_input = ocr_text
                safe_rerun()
        
        # --- Web Search Section ---
        st.subheader("Web Search")
        web_query = st.text_input("Enter search query", key="web_search_query")
        if st.button("Search with Web"):
            if web_query.strip():
                results = smart_web_search(web_query.strip())
                if results:
                    st.markdown("### Search Results:")
                    for res in results:
                        title = res.get("title", "No Title")
                        url = res.get("url", "")
                        snippet = res.get("snippet", "")
                        st.markdown(f"**[{title}]({url})**  \n{snippet}")
                else:
                    st.info("No results found.")
            else:
                st.info("Please enter a query to search.")

        # --- Weather Section ---
        st.subheader("Weather")
        location = st.text_input("Enter location", key="weather_location")
        if st.button("Get Weather"):
            if location.strip():
                weather_info = get_weather(location.strip())
                st.info(weather_info)
            else:
                st.info("Please enter a location.")

        # --- News Section ---
        st.subheader("News")
        news_query = st.text_input("Enter news topic (optional)", key="news_query")
        if st.button("Get News"):
            news_info = get_news(news_query.strip() if news_query else None)
            st.markdown("### News Headlines:")
            st.markdown(news_info)

        # --- Stocks Section ---
        st.subheader("Stocks")
        stock_symbol = st.text_input("Enter stock symbol", key="stock_symbol")
        if st.button("Get Stock Info"):
            if stock_symbol.strip():
                stock_info = get_stock_info(stock_symbol.strip())
                st.info(stock_info)
            else:
                st.info("Please enter a stock symbol.")

        # --- Chat History Analysis Section ---
        st.subheader("Chat History Analysis")
        if st.button("Analyze Chat History"):
            analysis = analyze_chat_history()
            st.text_area("Chat History Analysis", value=analysis, height=200)

    # -------------------- Session State Initialization --------------------
    if 'user_name' not in st.session_state:
        st.session_state.user_name = None
    if 'user_email' not in st.session_state:
        st.session_state.user_email = None
    if 'messages' not in st.session_state:
        st.session_state.messages = []  # Each message is a tuple: (speaker, message)
    if 'voice_input' not in st.session_state:
        st.session_state.voice_input = ""
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
                if is_valid_email(email_input.strip()):
                    st.session_state.user_email = email_input.strip()
                    safe_rerun()
                else:
                    st.error("Please enter a valid email address.")
            else:
                st.error("Please enter a valid email address.")
        st.stop()

    # -------------------- Mode: YouTube Transcript Extraction --------------------
    if mode == "YouTube Transcript Extraction":
        st.subheader("YouTube Transcript Extraction")
        video_url = st.text_input("Enter YouTube Video URL", key="youtube_url")
        if st.button("Extract Transcript"):
            if video_url.strip():
                transcript = extract_youtube_transcript(video_url.strip())
                st.markdown("### Transcript:")
                st.text_area("Transcript", value=transcript, height=300)
            else:
                st.info("Please enter a valid YouTube video URL.")
        st.stop()

    # -------------------- Mode: Chat Conversation --------------------
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

    if st.session_state.tts_audio:
        components.html(st.session_state.tts_audio, height=200)

    col1, col2 = st.columns([5,1])
    with col1:
        with st.form(key="chat_form", clear_on_submit=True):
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
        intent = detect_intent(user_message)
        sentiment = analyze_sentiment(user_message)
        
        if sentiment['compound'] < -0.5:
            st.session_state.messages.append(("bot", "It sounds like you're feeling down. I'm here if you need to talk."))

        if intent == "reminder":
            task, reminder_time, recurrence = parse_reminder(user_message)
            if not task or not reminder_time:
                task, reminder_time, recurrence = extract_reminder_details_with_gemini(user_message)
            if task and reminder_time:
                if recurrence:
                    schedule_recurring_notification(reminder_time, task, recurrence, st.session_state.user_email)
                    response = (
                        f"Okay, I will remind you to {task} at {reminder_time.strftime('%H:%M')} "
                        f"on {reminder_time.strftime('%d:%m:%Y')} and then {recurrence} via desktop notification and an email to {st.session_state.user_email}."
                    )
                else:
                    schedule_notification(reminder_time, task)
                    schedule_email_notification(reminder_time, task, st.session_state.user_email)
                    response = (
                        f"Okay, I will remind you to {task} at {reminder_time.strftime('%H:%M')} "
                        f"on {reminder_time.strftime('%d:%m:%Y')} via desktop notification and an email to {st.session_state.user_email}."
                    )
            else:
                response = ("I couldn't understand the reminder. Please use the format: "
                            "'remind me to [task] at HH:MM' or "
                            "'remind me to [task] at HH:MM on DD:MM:YYYY' with an optional recurrence (daily, weekly, monthly).")
        elif intent == "joke":
            response = get_joke()
        elif intent == "search":
            search_query = user_message.lower().replace("search", "", 1).strip()
            if search_query:
                results = smart_web_search(search_query)
                if results:
                    response_lines = ["Here are the search results:"]
                    for res in results:
                        title = res.get("title", "No Title")
                        url = res.get("url", "")
                        response_lines.append(f"{title}: {url}")
                    response = "\n".join(response_lines)
                else:
                    response = "No search results found."
            else:
                response = "Please provide a query after 'search'."
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
        st.session_state.voice_input = ""
        
        if st.session_state.get("read_aloud", False):
            try:
                tts = gTTS(response)
                audio_bytes = io.BytesIO()
                tts.write_to_fp(audio_bytes)
                audio_bytes.seek(0)
                audio_html = play_audio_with_delay(audio_bytes, delay=2000)
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
