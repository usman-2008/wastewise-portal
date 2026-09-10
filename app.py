import os
import streamlit as st
from google import genai
from PIL import Image
import plotly.express as px
import folium
from streamlit_folium import st_folium

# 1. Page Configuration
st.set_page_config(
    page_title="WasteWise AI - Smart Waste Management",
    page_icon="♻️",
    layout="centered"
)

# 2. Custom CSS for Attractive UI & Modern Buttons
st.markdown("""
    <style>
    .main {
        background-color: #f4f9f4;
    }
    .stButton>button {
        background: linear-gradient(135deg, #28a745, #20c997);
        color: white;
        border-radius: 12px;
        padding: 0.6rem 1.4rem;
        font-weight: bold;
        border: none;
        box-shadow: 0 4px 10px rgba(40, 167, 69, 0.3);
        transition: 0.3s;
    }
    .stButton>button:hover {
        background: linear-gradient(135deg, #218838, #17a2b8);
        box-shadow: 0 6px 14px rgba(40, 167, 69, 0.4);
        transform: translateY(-2px);
    }
    .card {
        padding: 22px;
        border-radius: 16px;
        background: white;
        box-shadow: 0 4px 15px rgba(0,0,0,0.06);
        margin-bottom: 20px;
        border-left: 5px solid #28a745;
    }
    .metric-card {
        background: white;
        padding: 15px;
        border-radius: 12px;
        box-shadow: 0 2px 8px rgba(0,0,0,0.05);
        text-align: center;
    }
    </style>
""", unsafe_allow_html=True)

# 3. Session State Initialization
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
if "username" not in st.session_state:
    st.session_state.username = ""
if "history" not in st.session_state:
    st.session_state.history = []

# 4. Login Page
if not st.session_state.logged_in:
    st.markdown("<h1 style='text-align: center; color: #28a745;'>♻️ WasteWise AI Portal</h1>", unsafe_allow_html=True)
    st.markdown("<p style='text-align: center; color: gray;'>Smart AI-Powered Waste Classification, Analytics & Recycling Hub</p>", unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        with st.form("login_form"):
            st.subheader("🔐 Secure Login")
            user_input = st.text_input("Username")
            pass_input = st.text_input("Password", type="password")
            submit_btn = st.form_submit_button("Login to Dashboard")
            
            if submit_btn:
                if user_input and pass_input:
                    st.session_state.logged_in = True
                    st.session_state.username = user_input
                    st.rerun()
                else:
                    st.error("Please enter both username and password.")
    st.stop()

# 5. Sidebar Navigation
st.sidebar.title(f"Welcome, {st.session_state.username}! 👋")
menu = st.sidebar.radio(
    "Navigation Hub", 
    ["AI Waste Scanner", "Scan History", "Analytics & Stats", "Recycling Centers Map", "Logout"]
)

if menu == "Logout":
    st.session_state.logged_in = False
    st.session_state.username = ""
    st.rerun()

# --- Feature 1: AI Waste Scanner ---
if menu == "AI Waste Scanner":
    st.title("♻️ AI Waste Classification Scanner")
    st.write("Capture a live photo or upload an image of waste to instantly analyze its type, recyclability, and disposal method.")

    try:
        api_key = st.secrets.get("GEMINI_API_KEY") or os.environ.get("GEMINI_API_KEY")
        client = genai.Client(api_key=api_key) if api_key else None
    except Exception as e:
        client = None

    input_method = st.radio("Choose input method:", ["Live Camera Capture", "Upload Image File"], horizontal=True)

    image = None
    if input_method == "Live Camera Capture":
        cam_file = st.camera_input("Capture Waste Image (Optimized for Mobile & iPhone)")
        if cam_file:
            image = Image.open(cam_file)
    else:
        up_file = st.file_uploader("Upload Waste Image", type=["jpg", "jpeg", "png"])
        if up_file:
            image = Image.open(up_file)

    if image:
        st.image(image, caption="Selected Waste Image", use_container_width=True)
        
        if st.button("🚀 Analyze Waste Properties"):
            if not client:
                st.error("Gemini API Key is missing! Please configure it in Streamlit Secrets.")
            else:
                with st.spinner("Analyzing waste properties via Gemini AI..."):
                    try:
                        prompt = (
                            "Analyze this image of waste. Provide: "
                            "1. Type of waste (e.g., Plastic, Organic, Electronic, Paper, Metal, Glass). "
                            "2. Recyclability status (Recyclable / Non-recyclable / Hazardous). "
                            "3. Proper disposal or recycling instructions in a clear, concise format."
                        )
                        response = client.models.generate_content(
                            model='gemini-3.6-flash',
                            contents=[image, prompt]
                        )
                        result_text = response.text
                        
                        st.success("Analysis Complete!")
                        st.markdown(f"<div class='card'><h3>📊 AI Environmental Report</h3>{result_text}</div>", unsafe_allow_html=True)
                        
                        # Guess category for stats
                        category = "Plastic"
                        txt_lower = result_text.lower()
                        if "organic" in txt_lower: category = "Organic"
                        elif "electronic" in txt_lower or "e-waste" in txt_lower: category = "Electronic"
                        elif "paper" in txt_lower: category = "Paper"
                        elif "metal" in txt_lower: category = "Metal"
                        elif "glass" in txt_lower: category = "Glass"
                        
                        st.session_state.history.append({
                            "image": image, 
                            "report": result_text, 
                            "category": category
                        })
                        
                    except Exception as e:
                        st.error(f"An error occurred during analysis: {e}")

# --- Feature 2: Scan History ---
elif menu == "Scan History":
    st.title("📜 Past Scan History")
    if not st.session_state.history:
        st.info("No scan history available yet. Start scanning items to build your history log!")
    else:
        for i, item in enumerate(reversed(st.session_state.history)):
            st.markdown(f"### 🏷️ Scan Item #{len(st.session_state.history) - i} ({item.get('category', 'General')})")
            st.image(item["image"], width=220)
            st.markdown(f"<div class='card'>{item['report']}</div>", unsafe_allow_html=True)
            st.divider()

# --- Feature 3: Analytics & Stats ---
elif menu == "Analytics & Stats":
    st.title("📈 Waste Management Analytics")
    st.write("Visualizing your scanning trends and categorized waste distribution.")
    
    if not st.session_state.history:
        st.info("Perform some waste scans to view analytics and charts here!")
    else:
        categories = [item.get("category", "Plastic") for item in st.session_state.history]
        cat_counts = {cat: categories.count(cat) for cat in set(categories)}
        
        col1, col2 = st.columns(2)
        with col1:
            st.markdown(f"<div class='metric-card'><h3>Total Scans</h3><h2>{len(st.session_state.history)}</h2></div>", unsafe_allow_html=True)
        with col2:
            st.markdown(f"<div class='metric-card'><h3>Categories Found</h3><h2>{len(cat_counts)}</h2></div>", unsafe_allow_html=True)
        
        st.markdown("<br>", unsafe_allow_html=True)
        
        # Plotly Donut Chart
        fig = px.pie(
            names=list(cat_counts.keys()), 
            values=list(cat_counts.values()), 
            title="Waste Breakdown by Category",
            hole=0.4,
            color_discrete_sequence=px.colors.sequential.Greens
        )
        st.plotly_chart(fig, use_container_width=True)

# --- Feature 4: Recycling Centers Map ---
elif menu == "Recycling Centers Map":
    st.title("🗺️ Local Recycling & Disposal Centers")
    st.write("Find nearby certified green recycling facilities and disposal drop-off points.")
    
    # Create Folium Map
    m = folium.Map(location=[33.6844, 73.0479], zoom_start=12) # Default coordinates (Islamabad/Region center)
    
    # Add dummy/sample recycling center markers
    centers = [
        {"name": "Green Eco Recycling Hub", "location": [33.7100, 73.0500], "type": "Plastic & Paper"},
        {"name": "City Clean Organic Compost Plant", "location": [33.6600, 73.0200], "type": "Organic Waste"},
        {"name": "E-Waste Safe Disposal Unit", "location": [33.6900, 73.0800], "type": "Electronics & Batteries"}
    ]
    
    for center in centers:
        folium.Marker(
            location=center["location"],
            popup=f"<b>{center['name']}</b><br>Accepts: {center['type']}",
            tooltip=center["name"],
            icon=folium.Icon(color="green", icon="recycle", prefix="fa")
        ).add_to(m)
        
    st_folium(m, width=700, height=450)