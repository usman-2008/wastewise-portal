import os, json
import streamlit as st
from PIL import Image
import pandas as pd
import plotly.express as px
import folium
from streamlit_folium import st_folium
from streamlit_js_eval import get_geolocation
import requests
from google import genai
from dotenv import load_dotenv

load_dotenv()

st.set_page_config(page_title="WasteWise AI Portal", page_icon="♻️", layout="wide")

# Custom CSS
st.markdown("""
<style>
    .stApp { background-color: #090d16; color: #f1f5f9; }
    .card { background: #1e293b; padding: 18px; border-radius: 12px; margin-bottom: 12px; border-left: 4px solid #10b981; }
    .stat { background: #0f172a; padding: 12px; border-radius: 10px; text-align: center; border: 1px solid #1e293b; }
    .profile-card { background: #131d31; padding: 20px; border-radius: 14px; border: 1px solid #334155; }
</style>
""", unsafe_allow_html=True)

# ---------------------------------------------------------
# MULTI-USER DYNAMIC DATABASE
# ---------------------------------------------------------
if "users_db" not in st.session_state:
    st.session_state.users_db = {
        "usr_1": {"name": "User 1", "points": 0, "scans": 0, "co2": 0.0, "pic": None},
        "usr_2": {"name": "User 2", "points": 0, "scans": 0, "co2": 0.0, "pic": None}
    }

if "active_user_id" not in st.session_state:
    st.session_state.active_user_id = "usr_1"

if "analysis" not in st.session_state:
    st.session_state.analysis = None

# Sidebar — Profile Switcher
st.sidebar.title("👤 Select User Account")

user_list = {v["name"]: k for k, v in st.session_state.users_db.items()}
selected_user_name = st.sidebar.selectbox(
    "Active Account:",
    options=list(user_list.keys()),
    index=list(user_list.values()).index(st.session_state.active_user_id)
)

st.session_state.active_user_id = user_list[selected_user_name]
current_user = st.session_state.users_db[st.session_state.active_user_id]

# Sidebar — Create New User Profile
st.sidebar.markdown("---")
st.sidebar.subheader("➕ Add New User")

with st.sidebar.form("create_user_form", clear_on_submit=True):
    new_user_name = st.text_input("Enter New Username:")
    create_submitted = st.form_submit_button("Create Account", type="primary", width="stretch")
    if create_submitted and new_user_name.strip():
        new_id = f"usr_{len(st.session_state.users_db) + 1}"
        st.session_state.users_db[new_id] = {
            "name": new_user_name.strip(),
            "points": 0,
            "scans": 0,
            "co2": 0.0,
            "pic": None
        }
        st.session_state.active_user_id = new_id
        st.success(f"Account '{new_user_name}' created!")
        st.rerun()

api_key = st.secrets.get("GEMINI_API_KEY", os.getenv("GEMINI_API_KEY", ""))

# Helper Functions
def get_location_details(lat, lon):
    try:
        url = f"https://nominatim.openstreetmap.org/reverse?format=json&lat={lat}&lon={lon}&zoom=18&addressdetails=1"
        headers = {"User-Agent": "WasteWiseApp/1.0"}
        response = requests.get(url, headers=headers, timeout=5)
        if response.status_code == 200:
            data = response.json()
            return data.get("display_name", "Address details unavailable"), data.get("address", {})
    except Exception:
        pass
    return "Address details unavailable", {}

def analyze_waste(image):
    if not api_key:
        return {
            "object": "Plastic Bottle (PET)", "material": "Code 1 PETE",
            "value": "PKR 45-65/kg", "hazard": "Medium",
            "prep_steps": ["Rinse liquid", "Crush bottle"], "upcycling": "DIY Self-watering Planter"
        }
    prompt = "Analyze waste item image. Return strictly valid JSON with keys: object, material, value, hazard, prep_steps (list), upcycling."
    client = genai.Client(api_key=api_key)
    for model in ['gemini-2.5-flash', 'gemini-1.5-flash']:
        try:
            res = client.models.generate_content(model=model, contents=[image, prompt])
            raw = res.text.strip().replace("```json", "").replace("```", "").strip()
            return json.loads(raw)
        except Exception:
            continue
    return {"object": "Waste Item", "material": "Recyclable", "value": "PKR 30/kg", "hazard": "Low", "prep_steps": ["Clean"], "upcycling": "Recycle locally"}

# ---------------------------------------------------------
# DYNAMIC HEADER
# ---------------------------------------------------------
head_col1, head_col2 = st.columns([1, 5])

with head_col1:
    if current_user["pic"] is not None:
        st.image(current_user["pic"], width=80)
    else:
        st.markdown("<h1 style='text-align: center; margin: 0;'>👤</h1>", unsafe_allow_html=True)

with head_col2:
    st.markdown("## ♻️ WasteWise Portal")
    st.markdown(f"Active User: **{current_user['name']}**")

c1, c2, c3 = st.columns(3)
c1.markdown(f'<div class="stat">⚡ <b>User Points:</b> {current_user["points"]}</div>', unsafe_allow_html=True)
c2.markdown(f'<div class="stat">📸 <b>Total Scans:</b> {current_user["scans"]}</div>', unsafe_allow_html=True)
c3.markdown(f'<div class="stat">🛡️ <b>CO₂ Saved:</b> {current_user["co2"]:.1f} kg</div>', unsafe_allow_html=True)
st.markdown("---")

# Navigation Tabs
tab1, tab2, tab3, tab4 = st.tabs(["📷 AI Scanner", "📍 HD Satellite GPS Map", "📊 Leaderboard", "👤 Profile Settings"])

# TAB 1: AI SCANNER
with tab1:
    col1, col2 = st.columns(2)
    with col1:
        source = st.radio("Image Source:", ["Upload File", "Live Camera"], horizontal=True)
        img_file = st.file_uploader("Upload Image", type=["jpg", "png", "jpeg"]) if source == "Upload File" else st.camera_input("Take Photo")
        
        if img_file:
            img = Image.open(img_file)
            st.image(img, width="stretch")
            
            if st.button("🚀 Analyze Item", type="primary", width="stretch"):
                with st.spinner("AI analyzing waste item..."):
                    st.session_state.analysis = analyze_waste(img)
                    
                    st.session_state.users_db[st.session_state.active_user_id]["scans"] += 1
                    st.session_state.users_db[st.session_state.active_user_id]["points"] += 25
                    st.session_state.users_db[st.session_state.active_user_id]["co2"] = round(
                        st.session_state.users_db[st.session_state.active_user_id]["co2"] + 0.5, 2
                    )
                    st.rerun()

    with col2:
        res = st.session_state.analysis
        if res:
            st.markdown(f'<div class="card"><b>Detected:</b> {res.get("object")}<br><b>Material:</b> {res.get("material")}</div>', unsafe_allow_html=True)
            st.markdown(f'<div class="card"><b>Scrap Value:</b> {res.get("value")}<br><b>CO₂ Saved:</b> +0.5 kg</div>', unsafe_allow_html=True)
            st.markdown(f'**Steps:** {", ".join(res.get("prep_steps", []))}')
            st.markdown(f'**Upcycling Idea:** {res.get("upcycling")}')
        else:
            st.info("Upload/Capture photo and click 'Analyze Item'.")

# TAB 2: HD SATELLITE GPS MAP
with tab2:
    st.subheader("🛰️ HD Satellite & Ultra-Zoom Street Map")
    loc = get_geolocation()
    
    if loc and "coords" in loc:
        lat, lon = loc["coords"]["latitude"], loc["coords"]["longitude"]
        full_address, addr_dict = get_location_details(lat, lon)
        st.success(f"📍 **Live GPS Coordinates:** Latitude `{lat:.5f}`, Longitude `{lon:.5f}`")
        st.markdown(f"""
        <div class="card">
            <b>🏠 Full Address:</b> {full_address}<br>
            <b>🏙️ Village / City:</b> {addr_dict.get('village', addr_dict.get('town', addr_dict.get('city', 'N/A')))}<br>
            <b>🏛️ District:</b> {addr_dict.get('county', addr_dict.get('state_district', 'N/A'))}<br>
            <b>🗺️ Province:</b> {addr_dict.get('state', 'N/A')}
        </div>
        """, unsafe_allow_html=True)
    else:
        st.warning("⚠️ Fetching Live GPS Location... (Allow location access in browser)")
        lat, lon = 34.1989, 71.9723
        full_address = "Dargai / Badraga Region"

    m = folium.Map(location=[lat, lon], zoom_start=18, min_zoom=3, max_zoom=22)

    folium.TileLayer(
        tiles='https://{s}.google.com/vt/lyrs=y&x={x}&y={y}&z={z}',
        attr='Google Maps Hybrid',
        name='Google Satellite Hybrid',
        subdomains=['mt0', 'mt1', 'mt2', 'mt3'],
        max_zoom=22, max_native_zoom=20
    ).add_to(m)

    folium.TileLayer(
        tiles='https://{s}.google.com/vt/lyrs=m&x={x}&y={y}&z={z}',
        attr='Google Maps Street',
        name='Google Street View',
        subdomains=['mt0', 'mt1', 'mt2', 'mt3'],
        max_zoom=22, max_native_zoom=20
    ).add_to(m)

    folium.Marker(
        [lat, lon],
        popup=f"<b>📍 User: {current_user['name']}</b><br>{full_address}",
        icon=folium.Icon(color="red", icon="user", prefix="fa")
    ).add_to(m)

    folium.LayerControl(position="topright").add_to(m)
    st_folium(m, width=1100, height=500)

# TAB 3: LEADERBOARD
with tab3:
    st.subheader("🏆 Users Ranking & Points Leaderboard")
    leaderboard_data = []
    for uid, udata in st.session_state.users_db.items():
        leaderboard_data.append({
            "User Name": udata["name"],
            "Points": udata["points"],
            "Scans": udata["scans"],
            "CO2 Saved (kg)": udata["co2"]
        })
    df_users = pd.DataFrame(leaderboard_data).sort_values(by="Points", ascending=False)
    st.dataframe(df_users, width="stretch")
    
    fig = px.bar(df_users, x="User Name", y="Points", color="User Name", title="User Eco-Points Comparison")
    st.plotly_chart(fig, width="stretch")

# TAB 4: PROFILE SETTINGS
with tab4:
    st.subheader("👤 Account Settings")
    st.markdown('<div class="profile-card">', unsafe_allow_html=True)
    
    prof_col1, prof_col2 = st.columns([1, 2])
    
    with prof_col1:
        if current_user["pic"] is not None:
            st.image(current_user["pic"], caption="Profile Photo", width=140)
        else:
            st.info("No profile picture added.")

    with prof_col2:
        with st.form("profile_update_form"):
            edited_name = st.text_input("Change Username:", value=current_user["name"])
            new_prof_pic = st.file_uploader("Upload Profile Picture:", type=["jpg", "png", "jpeg"])
            save_btn = st.form_submit_button("Save Profile Settings", type="primary")
            
            if save_btn:
                if edited_name.strip():
                    st.session_state.users_db[st.session_state.active_user_id]["name"] = edited_name.strip()
                if new_prof_pic is not None:
                    st.session_state.users_db[st.session_state.active_user_id]["pic"] = Image.open(new_prof_pic)
                st.success("Profile updated successfully!")
                st.rerun()

    st.markdown(f"""
    <hr>
    <b>Account ID:</b> `{st.session_state.active_user_id}`<br>
    <b>Earned Points:</b> `{current_user['points']}`<br>
    <b>Total Scans:</b> `{current_user['scans']}`<br>
    <b>CO₂ Saved:</b> `{current_user['co2']:.2f} kg`
    """, unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)