import os
import time
import datetime
import webbrowser
import io
import streamlit as st
import google.generativeai as genai
from config import GEMINI_API_KEY
from docx import Document
import fitz  # PyMuPDF for PDF files
import pandas as pd
import speech_recognition as sr
from pydub import AudioSegment

# --- Configure Gemini API ---
genai.configure(api_key=GEMINI_API_KEY)

# --- Safe Rerun Helper ---
def safe_rerun():
    if hasattr(st, "experimental_rerun"):
        st.experimental_rerun()
    elif hasattr(st, "rerun"):
        st.rerun()

# --- Helper Functions ---
def chat(query):
    try:
        model = genai.GenerativeModel("gemini-1.5-pro-latest")
        response = model.generate_content(query)
        return response.text.strip()
    except Exception as e:
        return f"Error generating response: {str(e)}"

def read_docx_file(file_path_or_buffer):
    try:
        doc = Document(file_path_or_buffer)
        content = [para.text for para in doc.paragraphs]
        return '\n'.join(content)
    except Exception as e:
        st.error(f"Error reading DOCX file: {e}")
        return None

def read_pdf_file(file_path_or_buffer):
    try:
        if hasattr(file_path_or_buffer, "read"):
            file_bytes = file_path_or_buffer.read()
            doc = fitz.open(stream=file_bytes, filetype="pdf")
        else:
            doc = fitz.open(file_path_or_buffer)
        content = []
        for page_num in range(doc.page_count):
            page = doc.load_page(page_num)
            content.append(page.get_text())
        return '\n'.join(content)
    except Exception as e:
        st.error(f"Error reading PDF file: {e}")
        return None

def read_txt_file(file_path_or_buffer):
    try:
        if hasattr(file_path_or_buffer, "read"):
            return file_path_or_buffer.read().decode("utf-8")
        else:
            with open(file_path_or_buffer, "r", encoding="utf-8") as file:
                return file.read()
    except Exception as e:
        st.error(f"Error reading TXT file: {e}")
        return None

def read_csv_file(file_path_or_buffer):
    try:
        if hasattr(file_path_or_buffer, "read"):
            df = pd.read_csv(file_path_or_buffer)
        else:
            df = pd.read_csv(file_path_or_buffer)
        return df.to_string()
    except Exception as e:
        st.error(f"Error reading CSV file: {e}")
        return None

def read_file(file_path):
    file_extension = os.path.splitext(file_path)[1].lower()
    if file_extension == '.docx':
        return read_docx_file(file_path)
    elif file_extension == '.pdf':
        return read_pdf_file(file_path)
    elif file_extension == '.txt':
        return read_txt_file(file_path)
    elif file_extension == '.csv':
        return read_csv_file(file_path)
    else:
        st.error(f"Unsupported file type: {file_extension}")
        return None

def file_exists(file_path):
    return os.path.exists(file_path)

def get_time():
    now = datetime.datetime.now()
    return f"The current time is {now.strftime('%H:%M:%S')}"

# --- New Recursive Search Functions ---
def find_file(file_name, search_root="C:\\"):
    """
    Recursively search for a file starting at search_root.
    Returns the full path if found; otherwise, returns None.
    """
    for root, dirs, files in os.walk(search_root):
        if file_name in files:
            return os.path.join(root, file_name)
    return None

def find_directory(dir_name, search_root="C:\\"):
    """
    Recursively search for a directory starting at search_root.
    Returns the full path if found; otherwise, returns None.
    """
    for root, dirs, files in os.walk(search_root):
        if dir_name in dirs:
            return os.path.join(root, dir_name)
    return None

# --- List files in a directory ---
def list_files_in_directory(directory_path):
    try:
        return os.listdir(directory_path)
    except Exception as e:
        return f"Error listing files in directory: {str(e)}"

# --- List scholarship files without descriptions ---
def list_scholarship_files(directory_path):
    files = list_files_in_directory(directory_path)
    if not isinstance(files, list):
        return files
    result = []
    for item in files:
        result.append(f"* **{item}**")
    return "\n".join(result)

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

# --- Encapsulate the Main Code into a Function ---
def main():
    # --- Streamlit Session State Initialization ---
    if 'messages' not in st.session_state:
        st.session_state.messages = []  # Each message is a tuple (speaker, message)
    if 'input_mode' not in st.session_state:
        st.session_state.input_mode = None  # "Text" or "Audio"

    # --- Custom CSS for Better UI ---
    st.markdown(
        """
        <style>
        .chat-container {
            height: 400px;
            overflow-y: auto;
            padding: 10px;
            border: 1px solid #ddd;
            background-color: #f9f9f9;
            border-radius: 5px;
        }
        .message {
            margin-bottom: 10px;
            padding: 8px 12px;
            border-radius: 10px;
            max-width: 80%;
        }
        .message-you {
            background-color: #d1e7dd;
            align-self: flex-end;
        }
        .message-astra {
            background-color: #cff4fc;
            align-self: flex-start;
        }
        .message p {
            margin: 0;
        }
        </style>
        """,
        unsafe_allow_html=True
    )

    # --- Sidebar with Instructions and Actions ---
    with st.sidebar:
        st.header("Astra S-1 Assistant")
        st.info(
            """
            **Instructions:**
            - Choose your input mode (Text or Audio).
            - Type your query or upload an audio file.
            - Special commands include:
                - `list of all files in scholarship`
                - `list all files in <folder>`
                - `extract data from <file>`
                - `open youtube`, `open google`, `open wikipedia`
                - `time`
            """
        )
        if st.button("Clear Conversation"):
            st.session_state.messages = []
            safe_rerun()

    # --- Main UI Layout ---
    st.title("Astra S-1: Your Personal AI Assistant")

    # Choose input mode if not already chosen
    if st.session_state.input_mode is None:
        st.subheader("Choose your input mode:")
        mode = st.radio("Select Input Mode:", options=["Text", "Audio"])
        if st.button("Confirm Mode"):
            st.session_state.input_mode = mode
            safe_rerun()

    # --- Chat Conversation Area ---
    st.markdown("### Conversation")
    chat_container = st.container()
    with chat_container:
        if st.session_state.messages:
            for speaker, message in st.session_state.messages:
                if speaker == "Astra":
                    st.markdown(
                        f'<div class="message message-astra"><p><strong>Astra:</strong> {message}</p></div>',
                        unsafe_allow_html=True,
                    )
                else:
                    st.markdown(
                        f'<div class="message message-you" style="text-align: right;"><p><strong>You:</strong> {message}</p></div>',
                        unsafe_allow_html=True,
                    )
        else:
            st.info("Your conversation will appear here.")

    # --- Processing Functions ---
    def process_query(query):
        st.session_state.messages.append(("You", query))
        with st.spinner("Astra is thinking..."):
            time.sleep(1)  # Simulate processing delay
            lower_query = query.lower()
            response = ""
            if lower_query.startswith("list of all files in scholarship"):
                # Search for the 'scholarship' directory recursively.
                scholarship_dir = find_directory("scholarship")
                if not scholarship_dir:
                    response = "The 'scholarship' folder was not found on your system."
                else:
                    response = list_scholarship_files(scholarship_dir)
            elif lower_query.startswith("list all files in"):
                folder_fragment = query[len("list all files in"):].strip()
                if not folder_fragment:
                    response = "Please provide a folder name or path after the command."
                else:
                    # If an absolute path is provided, use it; otherwise, search recursively.
                    if os.path.isabs(folder_fragment):
                        folder_path = folder_fragment
                    else:
                        folder_path = find_directory(folder_fragment)
                    if not folder_path or not os.path.isdir(folder_path):
                        response = f"The folder '{folder_fragment}' was not found on your system."
                    else:
                        files = list_files_in_directory(folder_path)
                        if isinstance(files, list):
                            response = "Files in the directory:\n" + "\n".join([f"- {f}" for f in files])
                        else:
                            response = files
            elif lower_query.startswith("extract data from"):
                file_fragment = query[len("extract data from"):].strip()
                if not file_fragment:
                    response = "Please provide a file name or path after the command."
                else:
                    # If an absolute path is provided, use it; otherwise, search recursively.
                    if os.path.isabs(file_fragment):
                        file_path = file_fragment
                    else:
                        file_path = find_file(file_fragment)
                    if not file_path or not file_exists(file_path):
                        response = f"The file '{file_fragment}' was not found on your system."
                    else:
                        file_content = read_file(file_path)
                        if file_content:
                            response = f"Content of the file:\n{file_content}"
                        else:
                            response = "Error! The file exists but could not be read (unsupported type or read error)."
            elif "open youtube" in lower_query:
                response = "Opening YouTube..."
                webbrowser.open("https://www.youtube.com")
            elif "open google" in lower_query:
                response = "Opening Google..."
                webbrowser.open("https://www.google.com")
            elif "open wikipedia" in lower_query:
                response = "Opening Wikipedia..."
                webbrowser.open("https://www.wikipedia.org")
            elif "time" in lower_query:
                response = get_time()
            else:
                response = chat(query)
            st.session_state.messages.append(("Astra", response))
        safe_rerun()

    # --- Input Section ---
    if st.session_state.input_mode == "Text":
        with st.form(key="text_form", clear_on_submit=True):
            user_input = st.text_input("Enter your query here", placeholder="Ask me anything...")
            submit_button = st.form_submit_button("Send")
        if submit_button and user_input:
            process_query(user_input)
    elif st.session_state.input_mode == "Audio":
        st.info("Upload an audio file (WAV, MP3, OGG, or M4A) for speech-to-text conversion.")
        audio_file = st.file_uploader("Upload Audio:", type=["wav", "mp3", "ogg", "m4a"])
        if audio_file is not None:
            transcribed_text = transcribe_audio(audio_file)
            if transcribed_text:
                st.success(f"Transcription: {transcribed_text}")
                if st.button("Send Query"):
                    process_query(transcribed_text)

    st.markdown("---")
    st.markdown(
        """
        **Note:** This app runs in a controlled environment. If you host it on a public server (e.g. Streamlit Cloud), 
        it will not have direct access to your local computer files. For local testing, please run this app on your own machine.
        """
    )

# --- Execution Guard ---
if __name__ == "__main__":
    main()
