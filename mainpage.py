import streamlit as st
import random
import time
import uuid
import bcrypt
import os
from sqlalchemy import create_engine, text
import astrabot   # Ensure astrabot.py defines a main() function.
import vertexbot   # Ensure vertexbot.py defines a main() function.

# Set page configuration as the very first Streamlit command.
st.set_page_config(page_title="Chatbot Access Portal", layout="centered")

# -------------------------
# Database Connection Function
# -------------------------
def get_db_engine():
    # Option 1: Hardcode credentials (for local testing)
    DB_USER = ""
    DB_PASSWORD = ""
    DB_HOST = ""
    DB_PORT = ""
    DB_NAME = ""
    
    # Option 2: Load from environment variables (recommended)
    # DB_USER = os.getenv("DB_USER", "your_username")
    # DB_PASSWORD = os.getenv("DB_PASSWORD", "your_password")
    # DB_HOST = os.getenv("DB_HOST", "localhost")
    # DB_PORT = os.getenv("DB_PORT", "5432")
    # DB_NAME = os.getenv("DB_NAME", "chatbot_db")

    engine = create_engine(f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}")
    return engine

# Create a global engine
engine = get_db_engine()

# -------------------------
# Language & Text Strings
# -------------------------
if "language" not in st.session_state:
    st.session_state.language = "en"

LANG_STRINGS = {
    "en": {
         "choose_mode": "Choose Display Mode",
         "light_mode": "Light Mode",
         "dark_mode": "Dark Mode",
         "main_title": "Chatbot Access Portal",
         "login": "Login",
         "signup": "Sign Up",
         "username": "Username",
         "password": "Password",
         "remember_me": "Remember Me",
         "forgot_password": "Forgot Password?",
         "reset_password": "Reset Password",
         "captcha_question": "What is {a} + {b}?",
         "captcha_error": "Incorrect captcha answer.",
         "reset_instructions": "Password reset instructions have been sent to your email.",
         "terms": "Terms of Service",
         "privacy": "Privacy Policy",
         "bot_facts": "Bot Facts",
         "astra_fact": "Astra Bot: Personalized AI chat bot for desktop",
         "vertex_fact": "Vertex Bot: General purpose AI chat bot",
         "click_robot": "🤖 Click me please !!!",
         "language_label": "Language",
         "logo_alt": "Your Logo Here"
    },
    "es": {
         "choose_mode": "Elija modo de visualización",
         "light_mode": "Modo claro",
         "dark_mode": "Modo oscuro",
         "main_title": "Portal de Acceso al Chatbot",
         "login": "Iniciar sesión",
         "signup": "Registrarse",
         "username": "Nombre de usuario",
         "password": "Contraseña",
         "remember_me": "Recordarme",
         "forgot_password": "¿Olvidó su contraseña?",
         "reset_password": "Restablecer contraseña",
         "captcha_question": "¿Cuánto es {a} + {b}?",
         "captcha_error": "Respuesta de captcha incorrecta.",
         "reset_instructions": "Las instrucciones para restablecer la contraseña han sido enviadas a su correo.",
         "terms": "Términos de servicio",
         "privacy": "Política de privacidad",
         "bot_facts": "Datos del Bot",
         "astra_fact": "Astra Bot: Chatbot AI personalizado para escritorio",
         "vertex_fact": "Vertex Bot: Chatbot AI de propósito general",
         "click_robot": "🤖 ¡Haz clic, por favor!",
         "language_label": "Idioma",
         "logo_alt": "Tu logo aquí"
    }
}
lang = LANG_STRINGS[st.session_state.language]

# -------------------------
# Initialization of Session State
# -------------------------
if "mode" not in st.session_state:
    st.session_state.mode = None
if "show_facts" not in st.session_state:
    st.session_state.show_facts = False
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
if "current_user" not in st.session_state:
    st.session_state.current_user = None
if "forgot_password" not in st.session_state:
    st.session_state.forgot_password = False

# Generate CAPTCHA numbers if not set
if "captcha_a" not in st.session_state or "captcha_b" not in st.session_state:
    st.session_state.captcha_a = random.randint(1, 10)
    st.session_state.captcha_b = random.randint(1, 10)
    st.session_state.captcha_answer = st.session_state.captcha_a + st.session_state.captcha_b

# -------------------------
# Language Selector (displayed at top)
# -------------------------
col_lang, _ = st.columns(2)
with col_lang:
    language_choice = st.selectbox(lang["language_label"], options=["English", "Español"], key="language_select")
    st.session_state.language = "en" if language_choice == "English" else "es"
    lang = LANG_STRINGS[st.session_state.language]

# -------------------------
# Mode Selection Buttons (if mode not yet chosen)
# -------------------------
if st.session_state.mode is None:
    st.markdown(f"<h2 style='text-align: center;'>{lang['choose_mode']}</h2>", unsafe_allow_html=True)
    col1, col2 = st.columns(2)
    with col1:
        if st.button(lang["light_mode"], key="light_mode"):
            st.session_state.mode = "Light"
    with col2:
        if st.button(lang["dark_mode"], key="dark_mode"):
            st.session_state.mode = "Dark"
    st.stop()  # Stop further rendering until a mode is chosen

# -------------------------
# CSS Injection Based on Mode
# -------------------------
def local_css(mode):
    if mode == "Dark":
        css = """
        <style>
        .stApp { animation: gradientBG 40s ease infinite; }
        @keyframes gradientBG { 0% { background: linear-gradient(135deg, #232526, #414345); }
            25% { background: linear-gradient(135deg, #1c1c1c, #3d3d3d); }
            50% { background: linear-gradient(135deg, #000428, #004e92); }
            75% { background: linear-gradient(135deg, #434343, #000000); }
            100% { background: linear-gradient(135deg, #232526, #414345); } }
        body { margin: 0; padding: 0; overflow-x: hidden; font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif; color: #fff; }
        .bubbles { position: fixed; top: 0; left: 0; width: 100%; height: 100%; overflow: hidden; z-index: -1; }
        .bubble { position: absolute; bottom: -150px; background: rgba(255,255,255,0.2); border-radius: 50%; animation: rise 10s infinite ease-in; }
        .bubble:nth-child(1) { left: 10%; width: 40px; height: 40px; animation-duration: 12s; }
        .bubble:nth-child(2) { left: 20%; width: 20px; height: 20px; animation-duration: 10s; animation-delay: 2s; }
        .bubble:nth-child(3) { left: 35%; width: 50px; height: 50px; animation-duration: 14s; animation-delay: 4s; }
        .bubble:nth-child(4) { left: 50%; width: 30px; height: 30px; animation-duration: 11s; }
        .bubble:nth-child(5) { left: 65%; width: 45px; height: 45px; animation-duration: 13s; animation-delay: 3s; }
        .bubble:nth-child(6) { left: 80%; width: 25px; height: 25px; animation-duration: 9s; animation-delay: 1s; }
        @keyframes rise { 0% { transform: translateY(0) scale(0.5); opacity: 0.7; }
                           50% { opacity: 0.5; } 100% { transform: translateY(-800px) scale(1.2); opacity: 0; } }
        .robot-button { text-align: center; margin-top: 20px; }
        .robot-button button { font-size: 70px; background: transparent; border: none; cursor: pointer; outline: none; animation: pulse 2s infinite; color: #000 !important; }
        .robot-button.clicked button { animation: none !important; }
        @keyframes pulse { 0% { transform: scale(1); } 50% { transform: scale(1.1); } 100% { transform: scale(1); } }
        .main-title { text-align: center; color: #fff; text-shadow: 2px 2px 4px rgba(0,0,0,0.7); margin-top: 20px; }
        .login-form { max-width: 350px; margin: 30px auto; padding: 20px; background: rgba(0,0,0,0.8); border-radius: 10px; box-shadow: 0 10px 20px rgba(0,0,0,0.5); color: #fff; }
        .login-form input { width: 100%; padding: 10px; margin-bottom: 10px; border: 1px solid #444; border-radius: 4px; background: #333; color: #fff; }
        .login-form input::placeholder { color: #000 !important; }
        .login-form button { width: 100%; padding: 10px; background-color: #4CAF50; border: none; border-radius: 5px; color: white; font-size: 1rem; cursor: pointer; }
        .login-form button:hover { background-color: #45a049; }
        </style>
        """
    else:
        css = """
        <style>
        .stApp { animation: gradientBG 40s ease infinite; }
        @keyframes gradientBG { 0% { background: linear-gradient(135deg, #74ebd5, #ACB6E5); }
            25% { background: linear-gradient(135deg, #FDC830, #F37335); }
            50% { background: linear-gradient(135deg, #667eea, #764ba2); }
            75% { background: linear-gradient(135deg, #00d2ff, #3a7bd5); }
            100% { background: linear-gradient(135deg, #74ebd5, #ACB6E5); } }
        body { margin: 0; padding: 0; overflow-x: hidden; font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif; color: #333; }
        .bubbles { position: fixed; top: 0; left: 0; width: 100%; height: 100%; overflow: hidden; z-index: -1; }
        .bubble { position: absolute; bottom: -150px; background: rgba(255,255,255,0.3); border-radius: 50%; animation: rise 10s infinite ease-in; }
        .bubble:nth-child(1) { left: 10%; width: 40px; height: 40px; animation-duration: 12s; }
        .bubble:nth-child(2) { left: 20%; width: 20px; height: 20px; animation-duration: 10s; animation-delay: 2s; }
        .bubble:nth-child(3) { left: 35%; width: 50px; height: 50px; animation-duration: 14s; animation-delay: 4s; }
        .bubble:nth-child(4) { left: 50%; width: 30px; height: 30px; animation-duration: 11s; }
        .bubble:nth-child(5) { left: 65%; width: 45px; height: 45px; animation-duration: 13s; animation-delay: 3s; }
        .bubble:nth-child(6) { left: 80%; width: 25px; height: 25px; animation-duration: 9s; animation-delay: 1s; }
        @keyframes rise { 0% { transform: translateY(0) scale(0.5); opacity: 0.7; }
                           50% { opacity: 0.5; } 100% { transform: translateY(-800px) scale(1.2); opacity: 0; } }
        .robot-button { text-align: center; margin-top: 20px; }
        .robot-button button { font-size: 70px; background: transparent; border: none; cursor: pointer; outline: none; animation: pulse 2s infinite; }
        .robot-button.clicked button { animation: none !important; }
        @keyframes pulse { 0% { transform: scale(1); } 50% { transform: scale(1.1); } 100% { transform: scale(1); } }
        .main-title { text-align: center; color: #fff; text-shadow: 2px 2px 4px rgba(0,0,0,0.7); margin-top: 20px; }
        .login-form { max-width: 350px; margin: 30px auto; padding: 20px; background: rgba(255,255,255,0.8); border-radius: 10px; box-shadow: 0 10px 20px rgba(0,0,0,0.2); color: #333; }
        .login-form input { width: 100%; padding: 10px; margin-bottom: 10px; border: 1px solid #ddd; border-radius: 4px; }
        .login-form button { width: 100%; padding: 10px; background-color: #4CAF50; border: none; border-radius: 5px; color: white; font-size: 1rem; cursor: pointer; }
        .login-form button:hover { background-color: #45a049; }
        </style>
        """
    st.markdown(css, unsafe_allow_html=True)

local_css(st.session_state.mode)

# -------------------------
# Dynamic Bubble Background
# -------------------------
st.markdown('<div class="bubbles">', unsafe_allow_html=True)
for _ in range(6):
    st.markdown('<div class="bubble"></div>', unsafe_allow_html=True)
st.markdown('</div>', unsafe_allow_html=True)

# -------------------------
# Robot Emoji Button & Bot Facts
# -------------------------
robot_class = "robot-button"
if st.session_state.show_facts:
    robot_class += " clicked"

with st.container():
    st.markdown(f'<div class="{robot_class}">', unsafe_allow_html=True)
    if st.button(lang["click_robot"], key="robot_button", on_click=lambda: st.session_state.update({"show_facts": not st.session_state.show_facts})):
        pass
    st.markdown('</div>', unsafe_allow_html=True)

if st.session_state.show_facts:
    st.markdown(f"""
        <div style="text-align: center; margin-top: 10px;">
            <h3>{lang["bot_facts"]}</h3>
            <p><strong>{lang["astra_fact"]}</strong></p>
            <p><strong>{lang["vertex_fact"]}</strong></p>
        </div>
    """, unsafe_allow_html=True)

# -------------------------
# Branding (Logo)
# -------------------------
st.image("https://via.placeholder.com/150", caption=lang["logo_alt"])

# -------------------------
# Main Title
# -------------------------
st.markdown(f"<h1 class='main-title'>{lang['main_title']}</h1>", unsafe_allow_html=True)

# -------------------------
# Forgot Password Toggle
# -------------------------
if st.session_state.forgot_password:
    with st.container():
        st.markdown(f"<h3 style='text-align: center;'>{lang['reset_password']}</h3>", unsafe_allow_html=True)
        email_fp = st.text_input("Enter your email to reset password", key="forgot_email")
        if st.button(lang["reset_password"], key="reset_btn"):
            st.success(lang["reset_instructions"])
            st.session_state.forgot_password = False

# -------------------------
# Custom Login/Sign Up Forms
# -------------------------
def signup():
    st.markdown(f"<h2 style='text-align: center;'>{lang['signup']}</h2>", unsafe_allow_html=True)
    with st.container():
        st.markdown('<div class="login-form">', unsafe_allow_html=True)
        email = st.text_input("Email", key="signup_email", help="Enter your email address")
        username = st.text_input(lang["username"], key="signup_username", help="Enter a unique username")
        password = st.text_input(lang["password"], type="password", key="signup_password", help="Enter a secure password")
        if st.button("Create Account", key="signup_button"):
            if not username or not password or not email:
                st.error("Username, email, and password are required.")
            else:
                query = text("SELECT * FROM users WHERE username = :username OR email = :email")
                with engine.connect() as conn:
                    result = conn.execute(query, {"username": username, "email": email}).fetchone()
                if result is not None:
                    st.error("This username or email already exists. Please choose another one.")
                else:
                    hashed = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
                    new_user_id = str(uuid.uuid4())
                    insert_query = text("""
                        INSERT INTO users (user_id, username, email, password_hash)
                        VALUES (:user_id, :username, :email, :password_hash)
                    """)
                    with engine.begin() as conn:
                        conn.execute(insert_query, {"user_id": new_user_id, "username": username, "email": email, "password_hash": hashed})
                    st.success("Account created successfully! Please log in.")
        st.markdown(f"<p style='text-align: center;'><a href='#'>{lang['terms']}</a> | <a href='#'>{lang['privacy']}</a></p>", unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)

def login():
    st.markdown(f"<h2 style='text-align: center;'>{lang['login']}</h2>", unsafe_allow_html=True)
    with st.container():
        st.markdown('<div class="login-form">', unsafe_allow_html=True)
        username = st.text_input(lang["username"], key="login_username", help="Enter your username")
        password = st.text_input(lang["password"], type="password", key="login_password", help="Enter your password")
        remember = st.checkbox(lang["remember_me"], key="remember_me")
        if st.button(lang["forgot_password"], key="forgot_pwd"):
            st.session_state.forgot_password = True
        captcha_input = st.text_input(lang["captcha_question"].format(a=st.session_state.captcha_a, b=st.session_state.captcha_b), key="captcha_input")
        if st.button("Verify CAPTCHA", key="captcha_btn"):
            try:
                if int(captcha_input) != st.session_state.captcha_answer:
                    st.error(lang["captcha_error"])
                    st.session_state.captcha_a = random.randint(1, 10)
                    st.session_state.captcha_b = random.randint(1, 10)
                    st.session_state.captcha_answer = st.session_state.captcha_a + st.session_state.captcha_b
                    return
                else:
                    st.success("CAPTCHA verified!")
            except:
                st.error(lang["captcha_error"])
                return
        with st.spinner("Processing..."):
            time.sleep(1)
        if st.button("Login", key="login_btn"):
            query = text("SELECT password_hash FROM users WHERE username = :username")
            with engine.connect() as conn:
                result = conn.execute(query, {"username": username}).mappings().fetchone()
            if result is None:
                st.error("Invalid username or password.")
            else:
                stored_hash = result["password_hash"]
                if not bcrypt.checkpw(password.encode("utf-8"), stored_hash.encode("utf-8")):
                    st.error("Invalid username or password.")
                    return
                st.session_state.logged_in = True
                st.session_state.current_user = username
                st.success(f"Welcome, {username}!")
                # After successful login, redirect to the landing page.
                import landing
                landing.main()
        st.markdown(f"<p style='text-align: center;'><a href='#'>{lang['terms']}</a> | <a href='#'>{lang['privacy']}</a></p>", unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)

# -------------------------
# Main Interface for Login/Sign Up or Landing Page
# -------------------------
if st.session_state.logged_in:
    import landing
    landing.main()
else:
    option = st.radio("Select an option", (lang["login"], lang["signup"]))
    if option == lang["login"]:
        login()
    else:
        signup()
