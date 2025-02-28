import streamlit as st
import astrabot   # Make sure astrabot.py defines a main() function.
import vertexbot  # Make sure vertexbot.py defines a main() function.

# Helper function for rerunning the app
def safe_rerun():
    if hasattr(st, "experimental_rerun"):
        st.experimental_rerun()
    elif hasattr(st, "rerun"):
        st.rerun()
    else:
        # If neither is available, do nothing.
        pass

# Configure the page title and layout
st.set_page_config(page_title="Chatbot Hub", layout="centered")

# Initialize session state variable for the selected bot
if "selected_bot" not in st.session_state:
    st.session_state.selected_bot = None

# ---------------------------
# Landing Page UI
# ---------------------------
if st.session_state.selected_bot is None:
    st.title("Welcome to Chatbot Hub!")
    st.write("Below are details about our two chatbots:")

    st.subheader("Astra - Personal Desktop AI Chatbot")
    st.write("Astra is your personal desktop AI chatbot designed to help manage files, transcribe audio, and handle personalized queries.")

    st.subheader("Vertex - General AI Chatbot")
    st.write("Vertex is a general-purpose AI chatbot that provides friendly conversation, productivity tips, and helpful advice.")

    st.write("Which chatbot would you like to use?")
    # Prompt the user to select a bot.
    bot_choice = st.radio("Select a Bot", options=["Astra", "Vertex"])

    if st.button("Launch Selected Bot"):
        st.session_state.selected_bot = bot_choice
        safe_rerun()  # Rerun the app to display the chosen bot's interface.

# ---------------------------
# Launch the Selected Bot's Interface
# ---------------------------
if st.session_state.selected_bot is not None:
    if st.session_state.selected_bot == "Astra":
        astrabot.main()
    elif st.session_state.selected_bot == "Vertex":
        vertexbot.main()

# ---------------------------
# Optional: Return to Landing Page Button
# ---------------------------
st.markdown("---")
if st.button("Return to Home"):
    st.session_state.selected_bot = None
    safe_rerun()
