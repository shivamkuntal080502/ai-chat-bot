import os
import time
import datetime
import requests
import streamlit as st
import google.generativeai as genai
import nltk

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
        model = genai.GenerativeModel("gemini-1.5-pro-latest")  # Using Gemini-Pro model
        response = model.generate_content(prompt)
        return response.text.strip()
    except Exception as e:
        return f"Error generating response: {str(e)}"

# Function to get the system prompt for the Vertex bot.
def get_system_prompt(user_name):
    return (f"You are Vertex, an everyday bot chatting with {user_name}. Provide helpful advice on productivity and time management. "
            "Do not include your name in your responses.")

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
            """
        )
        if st.button("Clear Conversation"):
            st.session_state.messages = []
            safe_rerun()

    # -------------------- Session State Initialization --------------------
    if 'user_name' not in st.session_state:
        st.session_state.user_name = None
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

        # Show a spinner with "Vertex is thinking..." while processing.
        with st.spinner("Vertex is thinking..."):
            time.sleep(1)  # Simulate processing delay
            lower_msg = user_message.lower()
            # Special case: if the user asks for a joke
            if "joke" in lower_msg:
                response = get_joke()
            else:
                # Build conversation prompt using markers without duplicating "Vertex:".
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
