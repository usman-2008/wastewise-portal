import os
import streamlit as st
from google import genai
from PIL import Image
import plotly.express as px
import folium
from streamlit_folium import st_folium

# 1. Page Configuration
st.set_page_config(
    page_title="WasteWise AI - Next-Gen Portal",
    page_icon="♻️",
    layout="wide"
)

# 2. Ultra-Modern Custom CSS for High-End Look & Feel
st.markdown("""
    <style>
    .main {
        background: #0f172a;
        color: #f8fafc;
    }
    .stSidebar {
        background-color: #1e293b !important;
    }
    .stButton>button {
        background: linear-gradient(135deg, #10b981, #059669);
        color: white;
        border-radius: 12px;
        padding: 0.6rem 1.5rem;
        font-weight: 600;
        border: none;
        box-shadow: 0 4px 14px rgba(16, 185, 129, 0.4);
        transition: all 0.3s ease;
    }
    .stButton>button:hover {
        background: linear-gradient(135deg, #059669, #047857);
        box-shadow: 0 6px 20px rgba(16, 185, 129, 0.6);
        transform: translateY(-2px);
    }
    .glass-card {
        background: rgba(30, 41, 59, 0.7);
        backdrop-filter: blur(12px);
        border: 1px solid rgba(255, 255, 255, 0.1);
        padding: 24px;
        border-radius: 16px;
        box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.37);
        margin-bottom: 20px;
    }
    .profile-banner {
        display: flex;
        align-items: center;
        gap: 20px;
        padding: 20px;
        background: linear-gradient(135deg, #1e293b, #0f172a);
        border-radius: 16px;
        border: 1px solid rgba(16, 185, 129, 0.3);
        margin-bottom: 25px;
    }
    </style>
""", unsafe_allow_html=True)

# 3. Session State Initialization
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
if "username" not in st.session_state:
    st.session_state.username = ""
if "profile_pic" not in st.session_state:
    st.session_state.profile_pic = None
if "history" not in st.session_state:
    st.session_state.history = []

# 4. Login Page
if not st.session_state.logged_in:
    col1, col2, col3 = st.columns([1, 1.2, 1])
    with col2:
        st.markdown("<br><br>", unsafe_allow_html=True)
        st.markdown("<div class='glass-card' style='text-align: center;'>", unsafe_allow_html=True)
        st.markdown("<h1 style='color: #10b981; font-size: 2.5rem;'>♻️ WasteWise AI</h1>", unsafe_allow_html=True)
        st.markdown("<p style='color: #94a3b8;'>Next-Generation Smart Waste & Satellite Tracking Portal</p><br>", unsafe_allow_html=True)
        
        with st.form("login_form"):
            user_input = st.text_input("Username")
            pass_input = st.text_input("Password", type="password")
            submit_btn = st.form_submit_button("Access Portal", use_container_width=True)
            
            if submit_btn:
                if user_input and pass_input:
                    st.session_state.logged_in = True
                    st.session_state.username = user_input
                    st.rerun()
                else:
                    st.error("Please fill in both fields.")
        st.markdown("</div>", unsafe_allow_html=True)
    st.stop()

# 5. Sidebar Navigation & Profile Widget
st.sidebar.markdown(f"### 👤 Welcome, {st.session_state.username}!")
if st.session_state.profile_pic:
    st.sidebar.image(st.session_state.profile_pic, width=100, caption="Profile Avatar")

menu = st.sidebar.radio(
    "Navigation Hub", 
    ["AI Waste Scanner", "User Profile & Avatar", "Scan History", "Analytics & Insights", "Live Satellite Map", "Logout"]
)

if menu == "Logout":
    st.session_state.logged_in = False
    st.session_state.username = ""
    st.rerun()

# --- Feature 1: AI Waste Scanner ---
if menu == "AI Waste Scanner":
    st.title("♻️ AI Waste Classification Scanner")
    st.markdown("<p style='color: #94a3b8;'>Instantly evaluate waste materials and receive smart AI recycling guides.</p>", unsafe_allow_html=True)

    try:
        api_key = st.secrets.get("GEMINI_API_KEY") or os.environ.get("GEMINI_API_KEY")
        client = genai.Client(api_key=api_key) if api_key else None
    except Exception as e:
        client = None

    input_method = st.radio("Select Input Mode:", ["Live Camera Capture", "Upload Image File"], horizontal=True)

    image = None
    if input_method == "Live Camera Capture":
        cam_file = st.camera_input("Capture Waste Object")
        if cam_file:
            image = Image.open(cam_file)
    else:
        up_file = st.file_uploader("Upload Waste Image", type=["jpg", "jpeg", "png"])
        if up_file:
            image = Image.open(up_file)

    if image:
        col_img, col_res = st.columns([1, 1.2])
        with col_img:
            st.image(image, caption="Target Waste Image", use_container_width=True)
        
        with col_res:
            if st.button("🚀 Run AI Analysis", use_container_width=True):
                if not client:
                    st.error("Gemini API Key missing in environment secrets!")
                else:
                    with st.spinner("Analyzing waste structure via Gemini AI..."):
                        try:
                            prompt = (
                                "Analyze this image of waste. Provide: "
                                "1. Type of waste (Plastic, Organic, Electronic, Paper, Metal, Glass). "
                                "2. Recyclability status (Recyclable / Non-recyclable / Hazardous). "
                                "3. Clear disposal instructions."
                            )
                            response = client.models.generate_content(
                                model='gemini-3.6-flash',
                                contents=[image, prompt]
                            )
                            result_text = response.text
                            
                            st.success("Analysis Complete!")
                            st.markdown(f"<div class='glass-card'><h4>📊 AI Intelligence Report</h4>{result_text}</div>", unsafe_allow_html=True)
                            
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
                            st.error(f"Error: {e}")

# --- Feature 2: User Profile & Avatar Upload ---
elif menu == "User Profile & Avatar":
    st.title("👤 User Profile Management")
    st.markdown("<p style='color: #94a3b8;'>Customize your account profile and upload a custom avatar picture.</p>", unsafe_allow_html=True)
    
    st.markdown("<div class='glass-card'>", unsafe_allow_html=True)
    col_p1, col_p2 = st.columns([1, 2])
    with col_p1:
        if st.session_state.profile_pic:
            st.image(st.session_state.profile_pic, width=150, caption="Current Avatar")
        else:
            st.info("No profile picture uploaded yet.")
    with col_p2:
        st.subheader(f"Username: {st.session_state.username}")
        st.write("Role: Portal Administrator / Eco Contributor")
        new_avatar = st.file_uploader("Upload New Profile Picture", type=["jpg", "png", "jpeg"])
        if new_avatar:
            st.session_state.profile_pic = Image.open(new_avatar)
            st.success("Profile picture updated successfully! Refreshing view...")
            st.rerun()
    st.markdown("</div>", unsafe_allow_html=True)

# --- Feature 3: Scan History ---
elif menu == "Scan History":
    st.title("📜 Detailed Scan Archive")
    if not st.session_state.history:
        st.info("No logs found. Start scanning items to see records here.")
    else:
        for i, item in enumerate(reversed(st.session_state.history)):
            st.markdown(f"<div class='glass-card'>", unsafe_allow_html=True)
            col_h1, col_h2 = st.columns([1, 2])
            with col_h1:
                st.image(item["image"], width=200)
            with col_h2:
                st.subheader(f"Category: {item.get('category', 'General')}")
                st.markdown(item['report'])
            st.markdown("</div>", unsafe_allow_html=True)

# --- Feature 4: Analytics & Insights ---
elif menu == "Analytics & Insights":
    st.title("📈 Advanced Waste Analytics")
    if not st.session_state.history:
        st.info("Perform scans to unlock deep data visualizations.")
    else:
        categories = [item.get("category", "Plastic") for item in st.session_state.history]
        cat_counts = {cat: categories.count(cat) for cat in set(categories)}
        
        fig = px.pie(
            names=list(cat_counts.keys()), 
            values=list(cat_counts.values()), 
            title="Waste Distribution Breakdown",
            hole=0.5,
            color_discrete_sequence=px.colors.sequential.Tealgrn
        )
        fig.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", font_color="white")
        st.plotly_chart(fig, use_container_width=True)

# --- Feature 5: Live Satellite Map ---
elif menu == "Live Satellite Map":
    st.title("🛰️ Live Satellite Recycling Intelligence Map")
    st.markdown("<p style='color: #94a3b8;'>Real-time satellite imagery view connected with global recycling and disposal coordinates.</p>", unsafe_allow_html=True)
    
    # Create Folium Map with Esri World Imagery (Live Satellite View)
    m = folium.Map(
        location=[33.6844, 73.0479], 
        zoom_start=14, 
        tiles='https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
        attr='Esri &mdash; Source: Esri, i-cubed, USDA, USGS, AEX, GeoEye, Getmapping, Aerogrid, IGN, IGP, UPR-EGP, and the GIS User Community'
    )
    
    centers = [
        {"name": "Satellite Eco Hub Alpha", "location": [33.6850, 73.0450], "type": "Plastic & Electronic Processing"},
        {"name": "Green Earth Satellite Node", "location": [33.6750, 73.0600], "type": "Organic & Compost Facility"}
    ]
    
    for center in centers:
        folium.Marker(
            location=center["location"],
            popup=f"<b>{center['name']}</b><br>Capabilities: {center['type']}",
            tooltip=center["name"],
            icon=folium.Icon(color="red", icon="satellite", prefix="fa")
        ).add_to(m)
        
    st_folium(m, width=1100, height=550)