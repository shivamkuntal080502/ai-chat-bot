import os
import time
import datetime
import webbrowser
import io
import base64
import streamlit as st
import google.generativeai as genai
from config import GEMINI_API_KEY
from docx import Document
import fitz  # PyMuPDF for PDF files
import pandas as pd
import speech_recognition as sr
from pydub import AudioSegment
from gtts import gTTS  # For text-to-speech conversion
import streamlit.components.v1 as components

# --- Configure Gemini API ---
genai.configure(api_key=GEMINI_API_KEY)

# --- New Helper Function for Entity Extraction ---
def extract_entity(query, instruction):
    """Uses Gemini to extract folder/file names from natural language queries."""
    try:
        prompt = f"{instruction}\nQuery: {query}\nExtracted name:"
        model = genai.GenerativeModel("gemini-2.0-flash")
        response = model.generate_content(prompt)
        cleaned_response = response.text.strip().strip('"').strip("'").split('\n')[0]
        return cleaned_response
    except Exception as e:
        st.error(f"Extraction error: {str(e)}")
        return None

# --- Safe Rerun Helper ---
def safe_rerun():
    if hasattr(st, "experimental_rerun"):
        st.experimental_rerun()
    elif hasattr(st, "rerun"):
        st.rerun()

# --- Helper Functions ---
def chat(query):
    try:
        model = genai.GenerativeModel("gemini-2.0-flash")
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

def find_file(file_name, search_root="C:\\"):
    for root, dirs, files in os.walk(search_root):
        if file_name in files:
            return os.path.join(root, file_name)
    return None

def find_directory(dir_name, search_root="C:\\"):
    for root, dirs, files in os.walk(search_root):
        if dir_name in dirs:
            return os.path.join(root, dir_name)
    return None

def list_files_in_directory(directory_path):
    try:
        return os.listdir(directory_path)
    except Exception as e:
        return f"Error listing files in directory: {str(e)}"

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

def play_audio_with_delay(audio_bytes, delay=10000):
    """
    Converts audio bytes to base64 and creates an HTML audio element that auto-plays after a delay.
    Also listens for key events: "p" to play, "s" to stop.
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

# --- Modified Process Query Function ---
def process_query(query):
    st.session_state.messages.append(("You", query))
    with st.spinner("Astra is thinking..."):
        time.sleep(0.5)
        lower_query = query.lower()
        response = ""
        
        # Handle core commands
        if "open youtube" in lower_query:
            webbrowser.open("https://www.youtube.com")
            response = "Opening YouTube..."
        elif "open google" in lower_query:
            webbrowser.open("https://www.google.com")
            response = "Opening Google..."
        elif "open wikipedia" in lower_query:
            webbrowser.open("https://www.wikipedia.org")
            response = "Opening Wikipedia..."
        elif "time" in lower_query:
            response = get_time()
            
        # Handle list files requests
        elif "list" in lower_query and "files" in lower_query:
            folder_instruction = """Extract the folder/file name from queries about listing files.
Return ONLY the name without additional text. Examples:
- Query: 'Show files in Documents' -> 'Documents'"""
                
            folder_name = extract_entity(query, folder_instruction)
            if not folder_name:
                response = "Could not determine folder name from your query."
            else:
                if os.path.isabs(folder_name):
                    target_dir = folder_name
                else:
                    target_dir = find_directory(folder_name)
                
                if not target_dir:
                    response = f"Folder '{folder_name}' not found!"
                else:
                    files = list_files_in_directory(target_dir)
                    if isinstance(files, list):
                        formatted = "\n".join([f"* **{f}**" for f in files])
                        response = f"Files in **{target_dir}**:\n{formatted}"
                    else:
                        response = files
        
        # Handle data extraction requests
        elif "extract" in lower_query and "data" in lower_query:
            file_instruction = """Extract the file/folder name from data extraction queries.
Return ONLY the name without additional text. Examples:
- Query: 'Get data from report.pdf' -> 'report.pdf'"""
            
            file_name = extract_entity(query, file_instruction)
            if not file_name:
                response = "Could not determine file name from your query."
            else:
                if os.path.isabs(file_name):
                    target_file = file_name
                else:
                    target_file = find_file(file_name)
                
                if not target_file:
                    response = f"File '{file_name}' not found!"
                else:
                    content = read_file(target_file)
                    response = f"**{target_file}** contents:\n\n{content}" if content else "Error reading file"
        
        # General Gemini response
        else:
            response = chat(query)
        
        st.session_state.messages.append(("Astra", response))
        
        # TTS Handling (if enabled)
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
        
        st.session_state.user_input = ""
        safe_rerun()

# --- Main Function ---
def main():
    # --- Session State Initialization ---
    if 'messages' not in st.session_state:
        st.session_state.messages = []
    if 'user_input' not in st.session_state:
        st.session_state.user_input = ""
    # Store generated audio HTML so that it persists in the layout.
    if 'tts_audio' not in st.session_state:
        st.session_state.tts_audio = ""

    # --- Custom CSS ---
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
        .stButton>button {
            width: 100%;
        }
        </style>
        """,
        unsafe_allow_html=True
    )

    # --- Sidebar ---
    with st.sidebar:
        st.header("Astra S-1 Assistant")
        st.info(
            """
            **Instructions:**
            - Type your query or use the microphone.
            - Special commands:
                - list of all files in scholarship
                - list all files in <folder>
                - extract data from <file>
                - open youtube, open google, open wikipedia
                - time
            """
        )
        if st.button("Clear Conversation"):
            st.session_state.messages = []
            safe_rerun()

        # Checkbox for read aloud option.
        st.checkbox("Read bot responses aloud", key="read_aloud", value=False)
        
        # Audio file uploader in sidebar.
        uploaded_audio = st.file_uploader("Upload Audio File", type=["wav", "mp3", "ogg", "m4a"])
        if uploaded_audio:
            transcribed_text = transcribe_audio(uploaded_audio)
            if transcribed_text:
                st.session_state.user_input = transcribed_text
                safe_rerun()

    # --- Main Interface ---
    st.title("Astra S-1: Your Personal AI Assistant")

    # --- Chat Display ---
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

    # Render the TTS audio HTML if available.
    if st.session_state.tts_audio:
        components.html(st.session_state.tts_audio, height=200)

    # --- Input Section ---
    col1, col2 = st.columns([5, 1])
    with col1:
        with st.form(key='text_form', clear_on_submit=True):
            user_input = st.text_input(
                "Type or speak your query",
                value=st.session_state.user_input,
                key="user_input_widget",
                placeholder="Ask me anything..."
            )
            submitted = st.form_submit_button("Send")
    with col2:
        if st.button("🎤", help="Press and speak"):
            transcribed_text = transcribe_microphone()
            if transcribed_text:
                st.session_state.user_input = transcribed_text
                safe_rerun()

    # --- Process Query ---
    if submitted and user_input:
        process_query(user_input)

    st.markdown("---")
    st.markdown(
        """
        **Note:** This app runs in a controlled environment. For full file access, run locally.
        """
    )

if __name__ == "__main__":
    main()
