import os
import streamlit as st
from google import genai
from google.genai import types
from PIL import Image

# 1. Page Configuration
st.set_page_config(
    page_title="WasteWise AI - Smart Waste Management",
    page_icon="♻️",
    layout="centered"
)

# 2. Custom CSS for Modern UI & Buttons
st.markdown("""
    <style>
    .main {
        background-color: #f8f9fa;
    }
    .stButton>button {
        background: linear-gradient(135deg, #28a745, #218838);
        color: white;
        border-radius: 10px;
        padding: 0.6rem 1.2rem;
        font-weight: bold;
        border: none;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        transition: 0.3s;
    }
    .stButton>button:hover {
        background: linear-gradient(135deg, #218838, #1e7e34);
        box-shadow: 0 6px 8px rgba(0,0,0,0.15);
    }
    .card {
        padding: 20px;
        border-radius: 12px;
        background: white;
        box-shadow: 0 2px 5px rgba(0,0,0,0.05);
        margin-bottom: 20px;
    }
    </style>
""", unsafe_allow_html=True)

# 3. Session State Initialization for Login & History
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
if "username" not in st.session_state:
    st.session_state.username = ""
if "history" not in st.session_state:
    st.session_state.history = []

# 4. Authentication / Login Page
if not st.session_state.logged_in:
    st.markdown("<h1 style='text-align: center; color: #28a745;'>♻️ WasteWise AI Portal</h1>", unsafe_allow_html=True)
    st.markdown("<p style='text-align: center; color: gray;'>Smart AI-Powered Waste Classification & Management</p>", unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        with st.form("login_form"):
            st.subheader("Login to your account")
            user_input = st.text_input("Username")
            pass_input = st.text_input("Password", type="password")
            submit_btn = st.form_submit_button("Login")
            
            if submit_btn:
                if user_input and pass_input:
                    st.session_state.logged_in = True
                    st.session_state.username = user_input
                    st.rerun()
                else:
                    st.error("Please enter both username and password.")
    st.stop()

# 5. Main App Dashboard (After Login)
st.sidebar.title(f"Welcome, {st.session_state.username}! 👋")
menu = st.sidebar.radio("Navigation", ["AI Waste Scanner", "Scan History", "Logout"])

if menu == "Logout":
    st.session_state.logged_in = False
    st.session_state.username = ""
    st.rerun()

# --- Feature 1: AI Waste Scanner ---
if menu == "AI Waste Scanner":
    st.title("♻️ WasteWise AI Scanner")
    st.write("Take a picture or upload an image of waste to instantly classify it and get recycling recommendations.")

    # API Client Setup
    try:
        api_key = st.secrets.get("GEMINI_API_KEY") or os.environ.get("GEMINI_API_KEY")
        client = genai.Client(api_key=api_key) if api_key else None
    except Exception as e:
        client = None

    # Camera / Upload Options
    input_method = st.radio("Choose input method:", ["Live Camera Capture", "Upload Image File"], horizontal=True)

    image = None
    if input_method == "Live Camera Capture":
        cam_file = st.camera_input("Capture Waste Image")
        if cam_file:
            image = Image.open(cam_file)
    else:
        up_file = st.file_uploader("Upload Waste Image", type=["jpg", "jpeg", "png"])
        if up_file:
            image = Image.open(up_file)

    if image:
        st.image(image, caption="Selected Image", use_container_width=True)
        
        if st.button("🚀 Analyze Waste"):
            if not client:
                st.error("Gemini API Key is missing! Please configure it in Streamlit Secrets.")
            else:
                with st.spinner("Analyzing waste properties via AI..."):
                    try:
                        prompt = (
                            "Analyze this image of waste. Provide: "
                            "1. Type of waste (e.g., Plastic, Organic, Electronic, Paper, Metal, Glass). "
                            "2. Recyclability status (Recyclable / Non-recyclable / Hazardous). "
                            "3. Proper disposal or recycling instructions in a clear, concise format."
                        )
                        response = client.models.generate_content(
                            model='gemini-2.5-flash',
                            contents=[image, prompt]
                        )
                        result_text = response.text
                        
                        # Show result
                        st.success("Analysis Complete!")
                        st.markdown(f"<div class='card'><h3>📊 AI Report</h3>{result_text}</div>", unsafe_allow_html=True)
                        
                        # Save to history
                        st.session_state.history.append({"image": image, "report": result_text})
                        
                    except Exception as e:
                        st.error(f"An error occurred during analysis: {e}")

# --- Feature 2: Scan History ---
elif menu == "Scan History":
    st.title("📜 Past Scan History")
    if not st.session_state.history:
        st.info("No scan history available yet. Scan some waste items to see them here!")
    else:
        for i, item in enumerate(reversed(st.session_state.history)):
            st.markdown(f"### Scan #{len(st.session_state.history) - i}")
            st.image(item["image"], width=200)
            st.markdown(f"<div class='card'>{item['report']}</div>", unsafe_allow_html=True)
            st.divider()