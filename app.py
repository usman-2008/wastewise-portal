import streamlit as st
import sqlite3
import hashlib
import secrets
import re
import json
import base64
import logging
import textwrap
import html
import urllib.parse
import urllib.request
import time
from datetime import datetime
from io import BytesIO

from PIL import Image, UnidentifiedImageError


# =========================================================
# OPTIONAL PACKAGES
# =========================================================

try:
    from google import genai
    from google.genai import types
except Exception:
    genai = None
    types = None

try:
    from streamlit_js_eval import streamlit_js_eval
except Exception:
    streamlit_js_eval = None

try:
    import folium
    from streamlit_folium import st_folium
except Exception:
    folium = None
    st_folium = None


# =========================================================
# PAGE CONFIG
# =========================================================

st.set_page_config(
    page_title="WasteWise AI",
    page_icon="♻️",
    layout="wide",
    initial_sidebar_state="expanded"
)


# =========================================================
# MARKDOWN / HTML HELPER
# =========================================================
# IMPORTANT:
# This forces Streamlit to render our controlled HTML instead
# of displaying HTML tags as normal text.
#
# FIX: textwrap.dedent() only removes the COMMON leading
# whitespace across all lines. Nested tags (h1, p, etc.)
# that are indented further than the outer tag keep extra
# leading spaces. When those indented lines follow a blank
# line, Markdown treats them as an INDENTED CODE BLOCK
# instead of raw HTML -> tags show up as literal text.
#
# The fix below strips ALL leading whitespace from every
# line (not just the common prefix), which prevents Markdown
# from ever seeing a 4+ space indent and falling back to a
# code block.
# =========================================================

_original_st_markdown = st.markdown


def render_markdown(body, *args, **kwargs):

    if isinstance(body, str):

        # Remove common leading whitespace + surrounding blank lines
        body = textwrap.dedent(body).strip()

        # Flatten the whole block onto a single line.
        #
        # Why: Markdown's "raw HTML block" detection requires a
        # complete opening/closing tag on one line. Our HTML is
        # written with attributes spread across multiple lines
        # for readability (e.g. <div style="\n ... \n">), which
        # Markdown does NOT recognize as a complete tag - so it
        # falls back to treating the content as plain/indented
        # text instead of HTML. Collapsing everything to a single
        # line sidesteps this entirely (harmless for HTML/CSS,
        # since whitespace between tags doesn't matter).
        body = " ".join(
            line.strip()
            for line in body.split("\n")
            if line.strip() != ""
        )

    kwargs["unsafe_allow_html"] = True

    return _original_st_markdown(
        body,
        *args,
        **kwargs
    )


# =========================================================
# LOGGING
# =========================================================

logging.basicConfig(
    filename="wastewise.log",
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)

logger = logging.getLogger("WasteWiseAI")


# =========================================================
# CONSTANTS
# =========================================================

DB_NAME = "wastewise.db"

MAX_IMAGE_SIZE_MB = 8
MAX_IMAGE_SIZE_BYTES = MAX_IMAGE_SIZE_MB * 1024 * 1024

WASTE_CATEGORIES = [
    "Plastic",
    "Paper",
    "Glass",
    "Metal",
    "Organic",
    "E-Waste",
    "Hazardous",
    "Textile",
    "Other"
]

IMPACT_RULES = {
    "Plastic": {
        "points": 10,
        "co2": 0.20
    },
    "Paper": {
        "points": 8,
        "co2": 0.15
    },
    "Glass": {
        "points": 12,
        "co2": 0.25
    },
    "Metal": {
        "points": 15,
        "co2": 0.35
    },
    "Organic": {
        "points": 7,
        "co2": 0.10
    },
    "E-Waste": {
        "points": 20,
        "co2": 0.40
    },
    "Hazardous": {
        "points": 20,
        "co2": 0.45
    },
    "Textile": {
        "points": 12,
        "co2": 0.25
    },
    "Other": {
        "points": 5,
        "co2": 0.05
    }
}


# =========================================================
# CSS
# =========================================================

render_markdown(
    """
    <style>

    html, body, [class*="css"] {
        font-family: Arial, sans-serif;
    }

    .stApp {
        background: #07111f;
        color: #f5f7fa;
    }

    .block-container {
        padding-top: 2rem;
        padding-bottom: 3rem;
        max-width: 1400px;
    }

    .brand-header {
        padding: 28px 32px;
        border-radius: 20px;
        background: linear-gradient(135deg, #10243b, #0b1728);
        border: 1px solid rgba(255,255,255,0.08);
        margin-bottom: 25px;
    }

    .brand-title {
        font-size: 38px;
        font-weight: 800;
        margin: 0;
    }

    .brand-subtitle {
        color: #aab6c5;
        margin-top: 8px;
        font-size: 16px;
    }

    .card {
        background: #101c2d;
        border: 1px solid rgba(255,255,255,0.07);
        border-radius: 18px;
        padding: 22px;
        margin-bottom: 18px;
    }

    .stat-card {
        background: linear-gradient(145deg, #101d30, #0d1828);
        border: 1px solid rgba(255,255,255,0.07);
        border-radius: 18px;
        padding: 22px;
        min-height: 130px;
    }

    .stat-title {
        color: #9aa8b8;
        font-size: 14px;
    }

    .stat-value {
        font-size: 32px;
        font-weight: 800;
        margin-top: 8px;
    }

    .result-card {
        background: linear-gradient(135deg, #0f2c39, #091826);
        border-radius: 24px;
        padding: 30px;
        border: 1px solid #38d39f;
        box-shadow: 0 0 25px rgba(56,211,159,0.15);
        margin-top: 20px;
    }

    .result-category {
        font-size: 34px;
        font-weight: 900;
        color: #ffffff;
    }

    .result-label {
        color: #38d39f;
        font-size: 12px;
        font-weight: 700;
        letter-spacing: 1px;
        margin-top: 18px;
        text-transform: uppercase;
    }

    .result-value {
        font-size: 17px;
        color: #e2e8f0;
        margin-top: 4px;
        line-height: 1.6;
    }

    .tip-card {
        background: rgba(56,211,159,0.08);
        border-left: 4px solid #38d39f;
        padding: 16px 20px;
        border-radius: 12px;
        margin-top: 20px;
        color: #d1fae5;
    }

    .auth-box {
        max-width: 650px;
        margin: 50px auto 20px auto;
        background: #0d1a2a;
        padding: 35px;
        border-radius: 24px;
        border: 1px solid rgba(255,255,255,0.08);
        text-align: center;
    }

    .small-muted {
        color: #8e9aaa;
        font-size: 13px;
    }

    .category-pill {
        display: inline-block;
        padding: 6px 14px;
        border-radius: 30px;
        background: #38d39f;
        color: #07111f;
        margin-bottom: 12px;
        font-weight: 800;
        font-size: 12px;
        letter-spacing: 0.5px;
    }

    .map-info {
        background: #101c2d;
        border: 1px solid rgba(255,255,255,0.08);
        border-radius: 14px;
        padding: 14px 18px;
        margin: 12px 0;
    }

    div.stButton > button {
        border-radius: 10px;
        font-weight: 700;
        min-height: 44px;
    }

    div.stButton > button:hover {
        border-color: #38d39f;
        color: #38d39f;
    }

    div[data-testid="stFileUploader"] {
        border-radius: 14px;
    }

    div[data-testid="stCameraInput"] {
        border-radius: 14px;
    }

    </style>
    """,
)


# =========================================================
# DATABASE
# =========================================================

def get_db():

    conn = sqlite3.connect(
        DB_NAME,
        check_same_thread=False
    )

    conn.row_factory = sqlite3.Row

    return conn


def init_db():

    conn = get_db()

    cur = conn.cursor()

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT,
            salt TEXT,
            profile_pic BLOB,
            points INTEGER DEFAULT 0,
            scans INTEGER DEFAULT 0,
            co2 REAL DEFAULT 0,
            created_at TEXT,
            google_account INTEGER DEFAULT 0
        )
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS scans (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            category TEXT,
            confidence REAL,
            description TEXT,
            disposal TEXT,
            tip TEXT,
            points INTEGER DEFAULT 0,
            co2_saved REAL DEFAULT 0,
            latitude REAL,
            longitude REAL,
            location TEXT,
            image BLOB,
            created_at TEXT,
            FOREIGN KEY(user_id) REFERENCES users(id)
        )
        """
    )

    conn.commit()
    conn.close()


init_db()


# =========================================================
# PASSWORD
# =========================================================

def hash_password(password, salt=None):

    if salt is None:
        salt = secrets.token_hex(16)

    password_hash = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        200000
    ).hex()

    return password_hash, salt


def verify_password(password, stored_hash, salt):

    if not stored_hash or not salt:
        return False

    password_hash, _ = hash_password(
        password,
        salt
    )

    return secrets.compare_digest(
        password_hash,
        stored_hash
    )


# =========================================================
# USERS
# =========================================================

def normalize_email(email):
    return email.strip().lower()


def get_user_by_email(email):

    conn = get_db()

    user = conn.execute(
        """
        SELECT *
        FROM users
        WHERE email = ?
        """,
        (normalize_email(email),)
    ).fetchone()

    conn.close()

    return user


def get_user_by_id(user_id):

    conn = get_db()

    user = conn.execute(
        """
        SELECT *
        FROM users
        WHERE id = ?
        """,
        (user_id,)
    ).fetchone()

    conn.close()

    return user


def create_user(name, email, password):

    conn = None

    try:

        password_hash, salt = hash_password(password)

        conn = get_db()

        cur = conn.execute(
            """
            INSERT INTO users
            (
                name,
                email,
                password_hash,
                salt,
                created_at,
                google_account
            )
            VALUES (?, ?, ?, ?, ?, 0)
            """,
            (
                name.strip(),
                normalize_email(email),
                password_hash,
                salt,
                datetime.now().strftime(
                    "%Y-%m-%d %H:%M:%S"
                )
            )
        )

        conn.commit()

        return cur.lastrowid

    except sqlite3.IntegrityError:

        return None

    except Exception:

        logger.exception(
            "User creation failed"
        )

        return None

    finally:

        if conn:
            conn.close()


# =========================================================
# IMAGE VALIDATION
# =========================================================

def validate_image(image_bytes):

    if not image_bytes:

        return False, "No image was provided."

    if len(image_bytes) > MAX_IMAGE_SIZE_BYTES:

        return (
            False,
            f"Image is too large. Maximum size is "
            f"{MAX_IMAGE_SIZE_MB} MB."
        )

    try:

        image = Image.open(
            BytesIO(image_bytes)
        )

        image.verify()

        return True, None

    except UnidentifiedImageError:

        return (
            False,
            "The uploaded file is not a valid image."
        )

    except Exception:

        return (
            False,
            "The image could not be validated."
        )


# =========================================================
# PROFILE PICTURE
# =========================================================

def update_profile_picture(user_id, image_bytes):

    valid, error = validate_image(
        image_bytes
    )

    if not valid:
        return False, error

    conn = None

    try:

        conn = get_db()

        conn.execute(
            """
            UPDATE users
            SET profile_pic = ?
            WHERE id = ?
            """,
            (
                image_bytes,
                user_id
            )
        )

        conn.commit()

        return True, None

    except Exception:

        logger.exception(
            "Profile picture update failed"
        )

        return (
            False,
            "Unable to save profile picture."
        )

    finally:

        if conn:
            conn.close()


def get_profile_pic_base64(user):

    if user and user["profile_pic"]:

        try:

            raw = user["profile_pic"]

            image = Image.open(
                BytesIO(raw)
            )

            fmt = (
                image.format or "JPEG"
            ).upper()

            mime = {
                "JPEG": "image/jpeg",
                "JPG": "image/jpeg",
                "PNG": "image/png",
                "WEBP": "image/webp"
            }.get(
                fmt,
                "image/jpeg"
            )

            encoded = base64.b64encode(
                raw
            ).decode("utf-8")

            return (
                f"data:{mime};base64,"
                f"{encoded}"
            )

        except Exception:

            logger.exception(
                "Profile picture encoding failed"
            )

    return None


# =========================================================
# GOOGLE OIDC
# =========================================================

def get_oidc_user():

    try:

        user = st.user

        if hasattr(user, "to_dict"):
            return user.to_dict()

        if isinstance(user, dict):
            return dict(user)

        return {
            "is_logged_in": bool(
                getattr(
                    user,
                    "is_logged_in",
                    False
                )
            ),
            "email": getattr(
                user,
                "email",
                None
            ),
            "name": getattr(
                user,
                "name",
                None
            ),
            "given_name": getattr(
                user,
                "given_name",
                None
            ),
            "preferred_username": getattr(
                user,
                "preferred_username",
                None
            )
        }

    except Exception:

        return {}


def google_is_logged_in():

    user = get_oidc_user()

    return bool(
        user.get(
            "is_logged_in",
            False
        )
    )


def google_login():

    try:

        st.login()

    except Exception:

        logger.exception(
            "Google login failed"
        )

        st.error(
            "Google Login is not configured. "
            "Configure Streamlit OIDC in "
            ".streamlit/secrets.toml."
        )


def create_or_update_google_user():

    google_user = get_oidc_user()

    if not google_user.get(
        "is_logged_in",
        False
    ):
        return None

    email = (
        google_user.get("email")
        or google_user.get(
            "preferred_username"
        )
    )

    name = (
        google_user.get("name")
        or google_user.get("given_name")
        or "Google User"
    )

    if not email:
        return None

    email = normalize_email(email)

    existing = get_user_by_email(email)

    conn = get_db()

    try:

        if existing:

            conn.execute(
                """
                UPDATE users
                SET
                    google_account = 1,
                    name = ?
                WHERE id = ?
                """,
                (
                    str(name).strip()
                    or "Google User",
                    existing["id"]
                )
            )

            conn.commit()

            return existing["id"]

        cur = conn.execute(
            """
            INSERT INTO users
            (
                name,
                email,
                password_hash,
                salt,
                created_at,
                google_account
            )
            VALUES (
                ?, ?, NULL, NULL, ?, 1
            )
            """,
            (
                str(name).strip()
                or "Google User",
                email,
                datetime.now().strftime(
                    "%Y-%m-%d %H:%M:%S"
                )
            )
        )

        conn.commit()

        return cur.lastrowid

    except Exception:

        logger.exception(
            "Google user creation failed"
        )

        return None

    finally:

        conn.close()


# =========================================================
# GEMINI MODEL DISCOVERY
# =========================================================
#
# Different API keys / Google accounts have access to different
# Gemini models (this varies by account tier, region, and rollout
# stage). Hardcoding a model name is fragile - instead, we ask
# Google directly which models THIS api key can actually use with
# generateContent, and try those first. The hardcoded list below
# is kept only as a last-resort fallback if discovery fails.

GEMINI_MODEL_FALLBACK = [
    "gemini-2.5-flash",
    "gemini-2.0-flash",
    "gemini-flash-latest",
    "gemini-1.5-flash",
]

# Terms that mean "not a normal text+image chat model" - we skip
# these even if they technically support generateContent, since
# they're not suitable for this app's use case (image -> JSON).
_EXCLUDED_MODEL_TERMS = (
    "embedding",
    "aqa",
    "tts",
    "image-generation",
    "imagen",
    "audio",
    "vision-only",
)


def discover_gemini_models(client):
    """
    Returns a list of model names (no 'models/' prefix) that
    support generateContent for this API key, flash models first.
    Falls back to an empty list if discovery itself fails (the
    caller should then use GEMINI_MODEL_FALLBACK).
    """

    cache_key = "gemini_available_models"

    if cache_key in st.session_state:
        return st.session_state[cache_key]

    discovered = []

    try:

        for model in client.models.list():

            name = getattr(model, "name", "") or ""

            # Strip the "models/" prefix if present
            clean_name = name.split("/")[-1]

            if not clean_name:
                continue

            name_lower = clean_name.lower()

            if "gemini" not in name_lower:
                continue

            if any(
                term in name_lower
                for term in _EXCLUDED_MODEL_TERMS
            ):
                continue

            supported_actions = (
                getattr(model, "supported_actions", None)
                or []
            )

            if supported_actions and (
                "generateContent" not in supported_actions
            ):
                continue

            discovered.append(clean_name)

        # Prefer flash models (cheaper/faster), then everything else,
        # newest-looking version numbers first.
        discovered.sort(
            key=lambda n: (
                "flash" not in n.lower(),
                n
            ),
            reverse=False
        )

    except Exception:

        logger.exception(
            "Gemini model discovery failed"
        )

        discovered = []

    st.session_state[cache_key] = discovered

    return discovered


# =========================================================
# IMPACT
# =========================================================

def get_impact(category):

    return IMPACT_RULES.get(
        category,
        IMPACT_RULES["Other"]
    )


# =========================================================
# SAVE SCAN
# =========================================================

def add_scan(
    user_id,
    result,
    image_bytes,
    latitude=None,
    longitude=None,
    location=""
):

    category = result["category"]

    impact = get_impact(category)

    points = impact["points"]
    co2 = impact["co2"]

    conn = get_db()

    try:

        conn.execute(
            """
            INSERT INTO scans
            (
                user_id,
                category,
                confidence,
                description,
                disposal,
                tip,
                points,
                co2_saved,
                latitude,
                longitude,
                location,
                image,
                created_at
            )
            VALUES (
                ?, ?, ?, ?, ?, ?, ?, ?,
                ?, ?, ?, ?, ?
            )
            """,
            (
                user_id,
                category,
                result["confidence"],
                result["description"],
                result["disposal"],
                result["tip"],
                points,
                co2,
                latitude,
                longitude,
                location,
                image_bytes,
                datetime.now().strftime(
                    "%Y-%m-%d %H:%M:%S"
                )
            )
        )

        conn.execute(
            """
            UPDATE users
            SET
                points = points + ?,
                scans = scans + 1,
                co2 = co2 + ?
            WHERE id = ?
            """,
            (
                points,
                co2,
                user_id
            )
        )

        conn.commit()

        return True

    except Exception:

        conn.rollback()

        logger.exception(
            "Failed to save scan"
        )

        return False

    finally:

        conn.close()


def get_user_scans(user_id):

    conn = get_db()

    rows = conn.execute(
        """
        SELECT *
        FROM scans
        WHERE user_id = ?
        ORDER BY id DESC
        """,
        (user_id,)
    ).fetchall()

    conn.close()

    return rows


def get_leaderboard():

    conn = get_db()

    rows = conn.execute(
        """
        SELECT
            name,
            points,
            scans,
            co2
        FROM users
        ORDER BY points DESC, scans DESC
        LIMIT 20
        """
    ).fetchall()

    conn.close()

    return rows


# =========================================================
# GEMINI JSON
# =========================================================

def clean_json_text(text):

    if not text:
        return ""

    text = text.strip()

    if text.startswith("```json"):
        text = text[7:]

    elif text.startswith("```"):
        text = text[3:]

    if text.endswith("```"):
        text = text[:-3]

    return text.strip()


def validate_ai_result(result):

    if not isinstance(result, dict):

        return (
            None,
            "AI returned invalid data."
        )

    category = str(
        result.get(
            "category",
            ""
        )
    ).strip()

    if category not in WASTE_CATEGORIES:

        return (
            None,
            f"AI returned invalid category: {category}"
        )

    try:

        confidence = float(
            result.get(
                "confidence",
                0
            )
        )

    except Exception:

        return (
            None,
            "AI returned invalid confidence."
        )

    if not 0 <= confidence <= 1:

        return (
            None,
            "AI confidence must be between 0 and 1."
        )

    description = str(
        result.get(
            "description",
            ""
        )
    ).strip()

    disposal = str(
        result.get(
            "disposal",
            ""
        )
    ).strip()

    tip = str(
        result.get(
            "tip",
            ""
        )
    ).strip()

    if not description:
        return None, "AI description is missing."

    if not disposal:
        return None, "AI disposal instruction is missing."

    if not tip:
        return None, "AI environmental tip is missing."

    return {
        "category": category,
        "confidence": round(
            confidence,
            4
        ),
        "description": description[:1000],
        "disposal": disposal[:1000],
        "tip": tip[:1000]
    }, None


# =========================================================
# GEMINI ANALYSIS
# =========================================================

def analyze_waste(image_bytes, mime_type):

    if genai is None or types is None:

        return (
            None,
            "Google GenAI package is missing.\n\n"
            "Install it with:\n"
            "pip install -U google-genai"
        )

    if not image_bytes:

        return None, "No image was received."

    # -----------------------------------------------------
    # IMAGE VALIDATION
    # -----------------------------------------------------

    try:

        check_image = Image.open(
            BytesIO(image_bytes)
        )

        check_image.verify()

    except UnidentifiedImageError:

        return (
            None,
            "The uploaded file is not a valid image."
        )

    except Exception as e:

        logger.exception(
            "Image validation failed"
        )

        return (
            None,
            "Image validation failed: "
            + str(e)[:300]
        )

    # -----------------------------------------------------
    # MIME TYPE
    # -----------------------------------------------------

    allowed_types = {
        "image/jpeg",
        "image/png",
        "image/webp"
    }

    if mime_type not in allowed_types:

        try:

            image_check = Image.open(
                BytesIO(image_bytes)
            )

            image_format = (
                image_check.format or "JPEG"
            ).upper()

            mime_type = {
                "JPEG": "image/jpeg",
                "JPG": "image/jpeg",
                "PNG": "image/png",
                "WEBP": "image/webp"
            }.get(
                image_format,
                "image/jpeg"
            )

        except Exception:

            mime_type = "image/jpeg"

    # -----------------------------------------------------
    # API KEY
    # -----------------------------------------------------

    try:

        api_key = st.secrets.get(
            "GEMINI_API_KEY"
        )

    except Exception:

        return (
            None,
            "Streamlit could not read GEMINI_API_KEY.\n\n"
            "Check your Streamlit Secrets."
        )

    if not api_key:

        return (
            None,
            "GEMINI_API_KEY is missing.\n\n"
            "Add GEMINI_API_KEY to Streamlit Secrets."
        )

    api_key = str(api_key).strip()

    # -----------------------------------------------------
    # CLIENT
    # -----------------------------------------------------

    try:

        client = genai.Client(
            api_key=api_key
        )

    except Exception as e:

        logger.exception(
            "Gemini client creation failed"
        )

        return (
            None,
            "Could not create Gemini client: "
            + str(e)[:500]
        )

    # -----------------------------------------------------
    # IMAGE PART
    # -----------------------------------------------------

    try:

        image_part = types.Part.from_bytes(
            data=image_bytes,
            mime_type=mime_type
        )

    except Exception as e:

        logger.exception(
            "Gemini image preparation failed"
        )

        return (
            None,
            "Could not prepare image for Gemini: "
            + str(e)[:500]
        )

    # -----------------------------------------------------
    # RESPONSE SCHEMA
    # -----------------------------------------------------

    response_schema = {
        "type": "OBJECT",
        "properties": {
            "category": {
                "type": "STRING",
                "enum": WASTE_CATEGORIES
            },
            "confidence": {
                "type": "NUMBER"
            },
            "description": {
                "type": "STRING"
            },
            "disposal": {
                "type": "STRING"
            },
            "tip": {
                "type": "STRING"
            }
        },
        "required": [
            "category",
            "confidence",
            "description",
            "disposal",
            "tip"
        ]
    }

    prompt = """
You are WasteWise AI, an intelligent waste classification assistant.

Analyze the uploaded image carefully.

Identify the single most likely visible waste item.

Use exactly one category from:

Plastic
Paper
Glass
Metal
Organic
E-Waste
Hazardous
Textile
Other

Do not invent objects that are not visible.

Return useful and practical information.

Description:
Explain what waste item is visible.

Disposal:
Explain how it should responsibly be disposed of.

Tip:
Give one useful environmental tip.

Confidence:
Return a number between 0 and 1.

If the image is unclear, choose the safest reasonable category and use a lower confidence.
"""

    # -----------------------------------------------------
    # GEMINI REQUEST
    # -----------------------------------------------------

    try:

        response = None
        last_model_error = None

        # How many times to retry a model when Google reports it's
        # temporarily overloaded (503 UNAVAILABLE), before moving on.
        MAX_RETRIES_PER_MODEL = 3
        RETRY_DELAY_SECONDS = 2

        # Rate limits (429) usually need a longer wait than a
        # simple server overload, since they're often "requests
        # per minute" caps rather than momentary congestion.
        MAX_RATE_LIMIT_RETRIES = 2
        RATE_LIMIT_DELAY_SECONDS = 20

        # Ask Google which models THIS api key can actually use,
        # then fall back to the hardcoded guesses if that fails
        # or returns nothing usable. Deduplicate while keeping order.
        discovered_models = discover_gemini_models(client)

        candidate_models = []

        for name in discovered_models + GEMINI_MODEL_FALLBACK:

            if name not in candidate_models:
                candidate_models.append(name)

        for candidate_model in candidate_models:

            model_succeeded = False

            for attempt in range(1, MAX_RETRIES_PER_MODEL + 1):

                try:

                    response = client.models.generate_content(
                        model=candidate_model,
                        contents=[
                            image_part,
                            prompt
                        ],
                        config=types.GenerateContentConfig(
                            response_mime_type="application/json",
                            response_schema=response_schema,
                            temperature=0.2
                        )
                    )

                    # Success - stop trying other models
                    model_succeeded = True
                    break

                except Exception as model_error:

                    error_str = str(model_error).lower()

                    is_model_unavailable = (
                        "not found" in error_str
                        or "404" in error_str
                        or "not available" in error_str
                        or "unsupported" in error_str
                    )

                    is_overloaded = (
                        "503" in error_str
                        or "unavailable" in error_str
                        or "overloaded" in error_str
                        or "high demand" in error_str
                    )

                    is_rate_limited = (
                        "429" in error_str
                        or "quota" in error_str
                        or "resource exhausted" in error_str
                        or "rate limit" in error_str
                    )

                    last_model_error = model_error

                    if is_model_unavailable:

                        logger.warning(
                            "Model unavailable, trying next: %s (%s)",
                            candidate_model,
                            model_error
                        )

                        # No point retrying a model that doesn't
                        # exist for this API key - move to the next.
                        break

                    if (
                        is_overloaded
                        and attempt < MAX_RETRIES_PER_MODEL
                    ):

                        logger.warning(
                            "Model overloaded, retrying (%s/%s): %s",
                            attempt,
                            MAX_RETRIES_PER_MODEL,
                            candidate_model
                        )

                        time.sleep(
                            RETRY_DELAY_SECONDS * attempt
                        )

                        continue

                    if is_overloaded:

                        # Ran out of retries for this model -
                        # try the next candidate model instead.
                        logger.warning(
                            "Model still overloaded after retries, "
                            "trying next model: %s",
                            candidate_model
                        )

                        break

                    if (
                        is_rate_limited
                        and attempt <= MAX_RATE_LIMIT_RETRIES
                    ):

                        logger.warning(
                            "Rate limited, waiting %ss then "
                            "retrying (%s/%s): %s",
                            RATE_LIMIT_DELAY_SECONDS,
                            attempt,
                            MAX_RATE_LIMIT_RETRIES,
                            candidate_model
                        )

                        with st.spinner(
                            f"⏳ Rate limit hit - waiting "
                            f"{RATE_LIMIT_DELAY_SECONDS}s "
                            f"before retrying..."
                        ):

                            time.sleep(
                                RATE_LIMIT_DELAY_SECONDS
                            )

                        continue

                    if is_rate_limited:

                        # This model's quota is exhausted for now -
                        # a different model may have separate quota,
                        # so try the next candidate.
                        logger.warning(
                            "Model still rate limited after retries, "
                            "trying next model: %s",
                            candidate_model
                        )

                        break

                    # Any other kind of error (auth, quota, etc.)
                    # should propagate immediately instead of
                    # silently trying more models.
                    raise

            if model_succeeded:
                break

        if response is None:

            if last_model_error is not None:
                raise last_model_error

            return (
                None,
                "Gemini returned no response."
            )

        response_text = getattr(
            response,
            "text",
            None
        )

        if not response_text:

            logger.error(
                "Gemini empty response: %s",
                response
            )

            return (
                None,
                "Gemini returned an empty response."
            )

        try:

            result = json.loads(
                clean_json_text(
                    response_text
                )
            )

        except json.JSONDecodeError:

            logger.error(
                "Gemini invalid JSON: %s",
                response_text
            )

            return (
                None,
                "Gemini returned invalid structured data. "
                "Please try another image."
            )

        validated_result, validation_error = (
            validate_ai_result(result)
        )

        if validation_error:

            logger.error(
                "AI validation error: %s",
                validation_error
            )

            return None, validation_error

        return validated_result, None

    except Exception as e:

        logger.exception(
            "Gemini analysis failed"
        )

        error_text = str(e)

        error_lower = error_text.lower()

        if (
            "api key" in error_lower
            or "api_key" in error_lower
            or "authentication" in error_lower
            or "unauthenticated" in error_lower
            or "401" in error_lower
        ):

            return (
                None,
                "❌ Gemini API key problem.\n\n"
                "Your GEMINI_API_KEY is invalid, "
                "missing, or not authorized."
            )

        if (
            "permission" in error_lower
            or "forbidden" in error_lower
            or "403" in error_lower
        ):

            return (
                None,
                "❌ Gemini permission denied.\n\n"
                "Check your Gemini API key and API access."
            )

        if (
            "quota" in error_lower
            or "429" in error_lower
            or "resource exhausted" in error_lower
            or "rate limit" in error_lower
        ):

            return (
                None,
                "⏳ Gemini quota/rate limit reached.\n\n"
                "We already retried automatically, but the "
                "limit is still active. This usually happens on "
                "the Gemini API free tier, which allows only a "
                "small number of requests per minute/day.\n\n"
                "Please wait a bit and try again, or check your "
                "usage/limits at "
                "https://aistudio.google.com/app/apikey"
            )

        if (
            "503" in error_lower
            or "unavailable" in error_lower
            or "overloaded" in error_lower
            or "high demand" in error_lower
        ):

            return (
                None,
                "⏳ Gemini servers are temporarily overloaded.\n\n"
                "We already retried automatically, but demand is "
                "still high right now. Please wait a moment and "
                "tap 'Analyze Waste' again."
            )

        if (
            "model" in error_lower
            and (
                "not found" in error_lower
                or "404" in error_lower
                or "unsupported" in error_lower
            )
        ):

            return (
                None,
                "❌ No compatible Gemini model found.\n\n"
                "We automatically checked every model your "
                "GEMINI_API_KEY has access to, and none of them "
                "could be used.\n\n"
                "This usually means:\n"
                "• The API key belongs to a Google Cloud/Vertex "
                "project instead of a Google AI Studio key, or\n"
                "• The key has no Gemini models enabled yet.\n\n"
                "Get a fresh key from https://aistudio.google.com/apikey "
                "and put it in Streamlit Secrets as GEMINI_API_KEY."
            )

        if (
            "timeout" in error_lower
            or "timed out" in error_lower
            or "connection" in error_lower
        ):

            return (
                None,
                "❌ Gemini connection problem.\n\n"
                "Check your internet connection and try again."
            )

        return (
            None,
            "❌ Gemini AI Error:\n\n"
            + error_text[:700]
        )


# =========================================================
# GPS
# =========================================================

def get_location():

    if streamlit_js_eval is None:

        return None, None

    try:

        location = streamlit_js_eval(
            js_expressions="""
            new Promise((resolve) => {

                if (!navigator.geolocation) {
                    resolve(null);
                    return;
                }

                navigator.geolocation.getCurrentPosition(
                    (position) => {

                        resolve({
                            latitude:
                                position.coords.latitude,

                            longitude:
                                position.coords.longitude
                        });

                    },

                    () => resolve(null),

                    {
                        enableHighAccuracy: true,
                        timeout: 15000,
                        maximumAge: 0
                    }

                );

            })
            """,
            key="wastewise_location_request"
        )

        if location:

            latitude = location.get(
                "latitude"
            )

            longitude = location.get(
                "longitude"
            )

            if (
                latitude is not None
                and longitude is not None
            ):

                return (
                    float(latitude),
                    float(longitude)
                )

    except Exception:

        logger.exception(
            "GPS location failed"
        )

    return None, None


# =========================================================
# REVERSE GEOCODING
# =========================================================

def reverse_geocode(latitude, longitude):

    if (
        latitude is None
        or longitude is None
    ):

        return ""

    try:

        params = urllib.parse.urlencode(
            {
                "lat": latitude,
                "lon": longitude,
                "format": "jsonv2",
                "zoom": 18,
                "addressdetails": 1
            }
        )

        url = (
            "https://nominatim.openstreetmap.org/reverse?"
            + params
        )

        request = urllib.request.Request(
            url,
            headers={
                "User-Agent":
                    "WasteWiseAI/1.0 "
                    "(waste classification app)",
                "Accept-Language":
                    "en"
            }
        )

        with urllib.request.urlopen(
            request,
            timeout=8
        ) as response:

            data = json.loads(
                response.read().decode("utf-8")
            )

        address = data.get(
            "address",
            {}
        )

        road = address.get("road")

        neighbourhood = (
            address.get("neighbourhood")
            or address.get("suburb")
            or address.get("village")
            or address.get("town")
            or address.get("city")
        )

        city = (
            address.get("city")
            or address.get("town")
            or address.get("village")
            or address.get("municipality")
        )

        state = address.get("state")

        country = address.get("country")

        parts = []

        for part in [
            road,
            neighbourhood,
            city,
            state,
            country
        ]:

            if part and part not in parts:
                parts.append(part)

        if parts:
            return ", ".join(parts)

        return data.get(
            "display_name",
            ""
        )

    except Exception:

        logger.exception(
            "Reverse geocoding failed"
        )

        return ""


# =========================================================
# SESSION STATE
# =========================================================

defaults = {
    "user_id": None,
    "page": "Dashboard",
    "auth_method": None,
    "last_result": None,
    "last_image": None,
    "last_location": (
        None,
        None
    ),
    "last_address": "",
    "location_requested": False
}

for key, value in defaults.items():

    if key not in st.session_state:
        st.session_state[key] = value


# =========================================================
# GOOGLE SESSION CHECK
# =========================================================

if (
    st.session_state.user_id is None
    and google_is_logged_in()
):

    google_user_id = create_or_update_google_user()

    if google_user_id:

        st.session_state.user_id = google_user_id
        st.session_state.auth_method = "google"
        st.rerun()


# =========================================================
# AUTH PAGE
# =========================================================

if st.session_state.user_id is None:

    render_markdown(
        """
        <div class="auth-box">

            <div style="font-size:58px;">
                ♻️
            </div>

            <h1 style="margin-bottom:8px;">
                Welcome to WasteWise AI
            </h1>

            <p class="small-muted">
                Smart waste detection and environmental tracking.
            </p>

        </div>
        """
    )

    login_tab, signup_tab = st.tabs(
        [
            "Login",
            "Create Account"
        ]
    )

    # =====================================================
    # LOGIN
    # =====================================================

    with login_tab:

        st.subheader("Welcome back")

        login_email = st.text_input(
            "Email",
            placeholder="you@example.com",
            key="login_email"
        )

        login_password = st.text_input(
            "Password",
            type="password",
            placeholder="Enter your password",
            key="login_password"
        )

        if st.button(
            "Login",
            type="primary",
            use_container_width=True
        ):

            email = normalize_email(
                login_email
            )

            user = get_user_by_email(email)

            if (
                user
                and verify_password(
                    login_password,
                    user["password_hash"],
                    user["salt"]
                )
            ):

                st.session_state.user_id = user["id"]
                st.session_state.auth_method = "password"
                st.session_state.page = "Dashboard"

                st.success(
                    "Login successful!"
                )

                st.rerun()

            else:

                st.error(
                    "Invalid email or password."
                )

        st.divider()

        with st.expander(
            "Forgot your password? Reset it here"
        ):

            reset_email = st.text_input(
                "Enter your registered email",
                key="reset_email_input"
            )

            new_password = st.text_input(
                "Enter new password",
                type="password",
                key="new_pass_input"
            )

            if st.button(
                "Update Password",
                use_container_width=True
            ):

                target_user = get_user_by_email(
                    reset_email
                )

                if not target_user:

                    st.error(
                        "Email not found in database."
                    )

                elif len(new_password) < 6:

                    st.error(
                        "Password must be at least 6 characters."
                    )

                else:

                    new_hash, new_salt = hash_password(
                        new_password
                    )

                    conn = get_db()

                    conn.execute(
                        """
                        UPDATE users
                        SET
                            password_hash = ?,
                            salt = ?
                        WHERE id = ?
                        """,
                        (
                            new_hash,
                            new_salt,
                            target_user["id"]
                        )
                    )

                    conn.commit()
                    conn.close()

                    st.success(
                        "Password updated successfully!"
                    )

        render_markdown(
            """
            <div style="
                text-align:center;
                color:#9aa8b8;
                margin-top:15px;
                margin-bottom:15px;
                font-weight:700;
            ">
                OR
            </div>
            """
        )

        if st.button(
            "🔵 Continue with Google",
            use_container_width=True
        ):

            google_login()

        st.caption(
            "Google login requires Google OAuth/OIDC configuration."
        )

    # =====================================================
    # SIGNUP
    # =====================================================

    with signup_tab:

        st.subheader(
            "Create your account"
        )

        name = st.text_input(
            "Full Name",
            placeholder="Muhammad Usman"
        )

        email = st.text_input(
            "Email",
            placeholder="you@example.com"
        )

        password = st.text_input(
            "Password",
            type="password",
            placeholder="Create a password"
        )

        confirm_password = st.text_input(
            "Confirm Password",
            type="password",
            placeholder="Repeat your password"
        )

        if st.button(
            "Create Account",
            type="primary",
            use_container_width=True
        ):

            name = name.strip()
            email = normalize_email(email)

            if not name:

                st.error(
                    "Please enter your full name."
                )

            elif not email:

                st.error(
                    "Please enter your email."
                )

            elif not re.match(
                r"^[^@\s]+@[^@\s]+\.[^@\s]+$",
                email
            ):

                st.error(
                    "Please enter a valid email address."
                )

            elif not password:

                st.error(
                    "Please enter a password."
                )

            elif len(password) < 6:

                st.error(
                    "Password must be at least 6 characters."
                )

            elif password != confirm_password:

                st.error(
                    "Passwords do not match."
                )

            elif get_user_by_email(email):

                st.error(
                    "An account with this email already exists."
                )

            else:

                user_id = create_user(
                    name,
                    email,
                    password
                )

                if user_id:

                    st.session_state.user_id = user_id
                    st.session_state.auth_method = "password"
                    st.session_state.page = "Dashboard"

                    st.success(
                        "Account created successfully!"
                    )

                    st.rerun()

                else:

                    st.error(
                        "Unable to create account."
                    )

    st.stop()


# =========================================================
# CURRENT USER
# =========================================================

current_user = get_user_by_id(
    st.session_state.user_id
)

if current_user is None:

    st.session_state.user_id = None
    st.rerun()


# =========================================================
# SIDEBAR
# =========================================================

with st.sidebar:

    render_markdown(
        "## ♻️ WasteWise AI"
    )

    pic_base64 = get_profile_pic_base64(
        current_user
    )

    if pic_base64:

        render_markdown(
            f"""
            <div style="
                display:flex;
                align-items:center;
                gap:14px;
                margin-bottom:12px;
                background:rgba(255,255,255,0.03);
                padding:10px;
                border-radius:14px;
                border:1px solid rgba(255,255,255,0.05);
            ">

                <img
                    src="{pic_base64}"
                    style="
                        width:54px;
                        height:54px;
                        border-radius:50%;
                        object-fit:cover;
                        border:2px solid #38d39f;
                    "
                >

                <div style="
                    font-size:13px;
                    color:#aab6c5;
                ">

                    Welcome,<br>

                    <b style="
                        color:#ffffff;
                        font-size:14px;
                    ">
                        {html.escape(str(current_user["name"]))}
                    </b>

                </div>

            </div>
            """
        )

    else:

        render_markdown(
            f"""
            <div style="
                display:flex;
                align-items:center;
                gap:14px;
                margin-bottom:12px;
                background:rgba(255,255,255,0.03);
                padding:10px;
                border-radius:14px;
                border:1px solid rgba(255,255,255,0.05);
            ">

                <div style="
                    width:54px;
                    height:54px;
                    border-radius:50%;
                    background:#1b3046;
                    display:flex;
                    align-items:center;
                    justify-content:center;
                    font-size:22px;
                    border:2px solid #38d39f;
                ">
                    👤
                </div>

                <div style="
                    font-size:13px;
                    color:#aab6c5;
                ">

                    Welcome,<br>

                    <b style="
                        color:#ffffff;
                        font-size:14px;
                    ">
                        {html.escape(str(current_user["name"]))}
                    </b>

                </div>

            </div>
            """
        )

    st.divider()

    if st.button(
        "🏠 Dashboard",
        use_container_width=True
    ):

        st.session_state.page = "Dashboard"
        st.rerun()

    if st.button(
        "📷 Scan Waste",
        use_container_width=True
    ):

        st.session_state.page = "Scan Waste"
        st.rerun()

    if st.button(
        "📜 History",
        use_container_width=True
    ):

        st.session_state.page = "History"
        st.rerun()

    if st.button(
        "🏆 Leaderboard",
        use_container_width=True
    ):

        st.session_state.page = "Leaderboard"
        st.rerun()

    if st.button(
        "👤 Profile",
        use_container_width=True
    ):

        st.session_state.page = "Profile"
        st.rerun()

    st.divider()

    if st.button(
        "🚪 Logout",
        use_container_width=True
    ):

        try:

            if google_is_logged_in():
                st.logout()

        except Exception:
            pass

        st.session_state.user_id = None
        st.session_state.auth_method = None
        st.session_state.page = "Dashboard"
        st.session_state.last_result = None
        st.session_state.last_image = None
        st.session_state.last_location = (
            None,
            None
        )
        st.session_state.last_address = ""

        st.rerun()


# =========================================================
# HEADER
# =========================================================

render_markdown(
    """
    <div class="brand-header">

        <div class="brand-title">
            ♻️ WasteWise AI
        </div>

        <div class="brand-subtitle">
            AI-powered waste classification and
            environmental impact tracking
        </div>

    </div>
    """
)


# =========================================================
# DASHBOARD
# =========================================================

if st.session_state.page == "Dashboard":

    st.title("Dashboard")

    col1, col2, col3, col4 = st.columns(4)

    with col1:

        render_markdown(
            f"""
            <div class="stat-card">

                <div class="stat-title">
                    Total Points
                </div>

                <div class="stat-value">
                    {current_user["points"]}
                </div>

            </div>
            """
        )

    with col2:

        render_markdown(
            f"""
            <div class="stat-card">

                <div class="stat-title">
                    Waste Scans
                </div>

                <div class="stat-value">
                    {current_user["scans"]}
                </div>

            </div>
            """
        )

    with col3:

        render_markdown(
            f"""
            <div class="stat-card">

                <div class="stat-title">
                    CO₂ Saved
                </div>

                <div class="stat-value">
                    {round(current_user["co2"], 2)} kg
                </div>

            </div>
            """
        )

    with col4:

        scans = get_user_scans(
            current_user["id"]
        )

        categories = {
            row["category"]
            for row in scans
        }

        render_markdown(
            f"""
            <div class="stat-card">

                <div class="stat-title">
                    Categories Found
                </div>

                <div class="stat-value">
                    {len(categories)}
                </div>

            </div>
            """
        )

    st.write("")

    render_markdown(
        """
        <div class="card">

            <h3>
                🌱 Start making an impact
            </h3>

            <p>
                Upload a waste image or take a photo
                to let AI identify the waste category
                and provide responsible disposal guidance.
            </p>

        </div>
        """
    )

    if st.button(
        "📷 Scan Waste Now",
        type="primary",
        use_container_width=True
    ):

        st.session_state.page = "Scan Waste"
        st.rerun()


# =========================================================
# SCAN WASTE
# =========================================================

elif st.session_state.page == "Scan Waste":

    st.title("📷 Scan Waste")

    st.write(
        "Upload an image or use your camera."
    )

    input_mode = st.radio(
        "Select input method:",
        [
            "Upload Image",
            "Use Camera"
        ],
        horizontal=True
    )

    selected_file = None

    if input_mode == "Upload Image":

        selected_file = st.file_uploader(
            "Upload Waste Image",
            type=[
                "jpg",
                "jpeg",
                "png",
                "webp"
            ],
            key="waste_image"
        )

    else:

        selected_file = st.camera_input(
            "Take a photo of the waste",
            key="waste_camera_input"
        )

    if selected_file:

        image_bytes = selected_file.getvalue()

        # -------------------------------------------------
        # NEW IMAGE DETECTION
        # -------------------------------------------------

        image_signature = hashlib.sha256(
            image_bytes
        ).hexdigest()

        if (
            "last_image_signature"
            not in st.session_state
            or st.session_state.last_image_signature
            != image_signature
        ):

            st.session_state.last_image_signature = (
                image_signature
            )

            st.session_state.last_result = None
            st.session_state.last_image = None
            st.session_state.last_location = (
                None,
                None
            )
            st.session_state.last_address = ""

        # -------------------------------------------------
        # IMAGE VALIDATION
        # -------------------------------------------------

        valid, image_error = validate_image(
            image_bytes
        )

        if not valid:

            st.error(image_error)

        else:

            try:

                image = Image.open(
                    BytesIO(image_bytes)
                )

                st.image(
                    image,
                    caption="Selected Waste Image",
                    use_container_width=True
                )

            except Exception:

                st.error(
                    "Unable to open this image."
                )

                st.stop()

            st.info(
                f"Image size: "
                f"{len(image_bytes) / 1024 / 1024:.2f} MB"
            )

            # -------------------------------------------------
            # LOCATION
            # -------------------------------------------------

            location_enabled = st.checkbox(
                "📍 Use my current location",
                value=False,
                key="location_checkbox"
            )

            latitude = None
            longitude = None
            address = ""

            if location_enabled:

                latitude, longitude = get_location()

                if (
                    latitude is not None
                    and longitude is not None
                ):

                    st.success(
                        "📍 GPS location detected successfully."
                    )

                    with st.spinner(
                        "Finding readable location..."
                    ):

                        address = reverse_geocode(
                            latitude,
                            longitude
                        )

                    if address:

                        render_markdown(
                            f"""
                            <div class="map-info">

                                📍 <b>Location:</b>
                                {html.escape(address)}

                            </div>
                            """
                        )

                    else:

                        st.warning(
                            "GPS coordinates were detected, "
                            "but a readable address could not be found."
                        )

                else:

                    st.warning(
                        "GPS permission was not available. "
                        "No fake location will be used."
                    )

            # -------------------------------------------------
            # ANALYZE BUTTON
            # -------------------------------------------------

            if st.button(
                "🔍 Analyze Waste",
                type="primary",
                use_container_width=True
            ):

                with st.spinner(
                    "🤖 AI is analyzing your waste..."
                ):

                    result, error = analyze_waste(
                        image_bytes,
                        getattr(
                            selected_file,
                            "type",
                            None
                        ) or "image/jpeg"
                    )

                if error:

                    st.error(error)

                elif result:

                    saved = add_scan(
                        current_user["id"],
                        result,
                        image_bytes,
                        latitude,
                        longitude,
                        address
                    )

                    if not saved:

                        st.error(
                            "AI result was generated, "
                            "but could not be saved."
                        )

                    else:

                        # -----------------------------------------
                        # STORE RESULT
                        # -----------------------------------------

                        st.session_state.last_result = result
                        st.session_state.last_image = image_bytes

                        st.session_state.last_location = (
                            latitude,
                            longitude
                        )

                        st.session_state.last_address = address

                        # -----------------------------------------
                        # SUCCESS EFFECT
                        # -----------------------------------------

                        st.balloons()

                        st.success(
                            "🎉 Waste analyzed successfully!"
                        )

                        # -----------------------------------------
                        # REFRESH USER DATA WITHOUT RERUN
                        # -----------------------------------------

                        current_user = get_user_by_id(
                            st.session_state.user_id
                        )

    # =========================================================
    # RESULT
    # =========================================================

    if st.session_state.last_result:

        result = st.session_state.last_result

        category = result.get(
            "category",
            "Other"
        )

        confidence = float(
            result.get(
                "confidence",
                0
            )
        )

        impact = get_impact(category)

        # -----------------------------------------------------
        # RESULT HEADER
        # -----------------------------------------------------

        render_markdown(
            """
            <div class="result-card">

                <div class="category-pill">
                    ✨ AI CLASSIFICATION REPORT
                </div>

                <div class="result-category">
                    ♻️ AI RESULT
                </div>

            </div>
            """
        )

        # -----------------------------------------------------
        # CATEGORY
        # -----------------------------------------------------

        render_markdown(
            f"""
            <div class="card">

                <div class="result-category">
                    ♻️ {html.escape(category)}
                </div>

            </div>
            """
        )

        # -----------------------------------------------------
        # CONFIDENCE
        # -----------------------------------------------------

        st.progress(
            confidence,
            text=(
                f"Detection Confidence: "
                f"{confidence * 100:.1f}%"
            )
        )

        # -----------------------------------------------------
        # DESCRIPTION
        # -----------------------------------------------------

        render_markdown(
            """
            <div class="result-label">
                📋 ITEM DESCRIPTION
            </div>
            """
        )

        render_markdown(
            f"""
            <div class="result-value">
                {html.escape(result["description"])}
            </div>
            """
        )

        # -----------------------------------------------------
        # DISPOSAL
        # -----------------------------------------------------

        render_markdown(
            """
            <div class="result-label">
                ♻️ SMART DISPOSAL INSTRUCTION
            </div>
            """
        )

        render_markdown(
            f"""
            <div class="result-value">
                {html.escape(result["disposal"])}
            </div>
            """
        )

        # -----------------------------------------------------
        # REWARDS
        # -----------------------------------------------------

        render_markdown(
            """
            <div class="result-label">
                🎁 EARNED IMPACT REWARDS
            </div>
            """
        )

        render_markdown(
            f"""
            <div class="result-value"
                 style="
                    font-weight:700;
                    color:#38d39f;
                 ">

                ⭐ +{impact["points"]} Points
                &nbsp;&nbsp;|&nbsp;&nbsp;
                🌱 {impact["co2"]:.2f} kg CO₂ Saved

            </div>
            """
        )

        # -----------------------------------------------------
        # TIP
        # -----------------------------------------------------

        render_markdown(
            f"""
            <div class="tip-card">

                💡 <b>Smart Eco-Tip:</b>
                {html.escape(result["tip"])}

            </div>
            """
        )

        # =====================================================
        # MAP
        # =====================================================

        latitude, longitude = (
            st.session_state.last_location
        )

        address = st.session_state.last_address

        if (
            folium is not None
            and st_folium is not None
            and latitude is not None
            and longitude is not None
        ):

            st.subheader(
                "🗺️ Scan Location"
            )

            st.caption(
                "The marker shows where this scan was made."
            )

            if address:

                render_markdown(
                    f"""
                    <div class="map-info">

                        🏠 <b>Address:</b>
                        {html.escape(address)}
                        <br><br>

                        📍 <b>Coordinates:</b>
                        {latitude:.6f},
                        {longitude:.6f}

                    </div>
                    """
                )

            else:

                render_markdown(
                    f"""
                    <div class="map-info">

                        📍 <b>Coordinates:</b>
                        {latitude:.6f},
                        {longitude:.6f}

                    </div>
                    """
                )

            # -------------------------------------------------
            # CREATE MAP
            # -------------------------------------------------

            m = folium.Map(
                location=[
                    latitude,
                    longitude
                ],
                zoom_start=17,
                tiles=None,
                control_scale=True
            )

            # -------------------------------------------------
            # STREET MAP
            # -------------------------------------------------

            folium.TileLayer(
                tiles="OpenStreetMap",
                name="🗺️ Street Map",
                control=True
            ).add_to(m)

            # -------------------------------------------------
            # SATELLITE
            # -------------------------------------------------

            folium.TileLayer(
                tiles=(
                    "https://server.arcgisonline.com/"
                    "ArcGIS/rest/services/"
                    "World_Imagery/"
                    "MapServer/tile/"
                    "{z}/{y}/{x}"
                ),
                attr=(
                    "Esri, Maxar, Earthstar "
                    "Geographics, and the GIS "
                    "User Community"
                ),
                name="🛰️ Satellite",
                control=True
            ).add_to(m)

            # -------------------------------------------------
            # LABELS
            # -------------------------------------------------

            folium.TileLayer(
                tiles=(
                    "https://services.arcgisonline.com/"
                    "ArcGIS/rest/services/"
                    "Reference/"
                    "World_Boundaries_and_Places/"
                    "MapServer/tile/"
                    "{z}/{y}/{x}"
                ),
                attr="Esri",
                name="🏷️ Labels",
                overlay=True,
                control=True
            ).add_to(m)

            # -------------------------------------------------
            # POPUP
            # -------------------------------------------------

            popup_address = (
                address
                if address
                else "Address unavailable"
            )

            popup_html = (
                '<div style="'
                'font-family:Arial;'
                'font-size:13px;'
                'width:230px;">'

                f'<b style="color:#159957;">'
                f'♻️ {html.escape(category)}'
                f'</b><br><br>'

                f'<b>Confidence:</b> '
                f'{confidence * 100:.1f}%'
                f'<br><br>'

                f'<b>Address:</b><br>'
                f'{html.escape(str(popup_address))}'
                f'<br><br>'

                f'<b>Coordinates:</b><br>'
                f'{latitude:.6f}, '
                f'{longitude:.6f}'

                '</div>'
            )

            # -------------------------------------------------
            # MARKER
            # -------------------------------------------------

            folium.Marker(
                [
                    latitude,
                    longitude
                ],
                tooltip="📍 Scan Location",
                popup=folium.Popup(
                    popup_html,
                    max_width=300
                ),
                icon=folium.Icon(
                    color="green",
                    icon="leaf",
                    prefix="fa"
                )
            ).add_to(m)

            # -------------------------------------------------
            # LAYER CONTROL
            # -------------------------------------------------

            folium.LayerControl(
                collapsed=False
            ).add_to(m)

            # -------------------------------------------------
            # DISPLAY MAP
            # -------------------------------------------------

            st_folium(
                m,
                width=None,
                height=550,
                returned_objects=[]
            )

        elif (
            latitude is not None
            and longitude is not None
        ):

            st.info(
                "Install folium and streamlit-folium "
                "to display the map."
            )


# =========================================================
# HISTORY
# =========================================================

elif st.session_state.page == "History":

    st.title("📜 Scan History")

    scans = get_user_scans(
        current_user["id"]
    )

    if not scans:

        st.info(
            "You have not scanned any waste yet."
        )

    else:

        for row in scans:

            with st.container():

                col1, col2 = st.columns(
                    [1, 3]
                )

                with col1:

                    if row["image"]:

                        try:

                            history_image = Image.open(
                                BytesIO(row["image"])
                            )

                            st.image(
                                history_image,
                                use_container_width=True
                            )

                        except Exception:

                            st.write("📷")

                with col2:

                    st.subheader(
                        f"♻️ {row['category']}"
                    )

                    st.write(
                        f"**Confidence:** "
                        f"{row['confidence'] * 100:.1f}%"
                    )

                    st.write(
                        f"**Description:** "
                        f"{row['description']}"
                    )

                    st.write(
                        f"**Disposal:** "
                        f"{row['disposal']}"
                    )

                    st.write(
                        f"**Points:** ⭐ +{row['points']}"
                    )

                    st.write(
                        f"**CO₂ Saved:** "
                        f"🌱 {row['co2_saved']:.2f} kg"
                    )

                    if row["location"]:

                        st.write(
                            f"📍 **Location:** "
                            f"{row['location']}"
                        )

                    st.caption(
                        f"Scanned: {row['created_at']}"
                    )

                st.divider()


# =========================================================
# LEADERBOARD
# =========================================================

elif st.session_state.page == "Leaderboard":

    st.title("🏆 Leaderboard")

    st.write(
        "Top WasteWise AI contributors."
    )

    leaderboard = get_leaderboard()

    if not leaderboard:

        st.info(
            "No leaderboard data available yet."
        )

    else:

        for index, row in enumerate(
            leaderboard,
            start=1
        ):

            if index == 1:
                medal = "🥇"

            elif index == 2:
                medal = "🥈"

            elif index == 3:
                medal = "🥉"

            else:
                medal = f"#{index}"

            render_markdown(
                f"""
                <div class="card">

                    <div style="
                        display:flex;
                        justify-content:space-between;
                        align-items:center;
                    ">

                        <div>

                            <div style="
                                font-size:22px;
                                font-weight:800;
                            ">
                                {medal}
                                {html.escape(str(row["name"]))}
                            </div>

                            <div class="small-muted">
                                {row["scans"]} scans
                                &nbsp;•&nbsp;
                                {row["co2"]:.2f} kg CO₂ saved
                            </div>

                        </div>

                        <div style="
                            font-size:25px;
                            font-weight:800;
                            color:#38d39f;
                        ">
                            ⭐ {row["points"]}
                        </div>

                    </div>

                </div>
                """
            )


# =========================================================
# PROFILE
# =========================================================

elif st.session_state.page == "Profile":

    st.title("👤 Profile")

    col1, col2 = st.columns(
        [1, 2]
    )

    with col1:

        pic_base64 = get_profile_pic_base64(
            current_user
        )

        if pic_base64:

            render_markdown(
                f"""
                <div style="
                    text-align:center;
                    margin-bottom:20px;
                ">

                    <img
                        src="{pic_base64}"
                        style="
                            width:150px;
                            height:150px;
                            object-fit:cover;
                            border-radius:50%;
                            border:4px solid #38d39f;
                        "
                    >

                </div>
                """
            )

        else:

            render_markdown(
                """
                <div style="
                    text-align:center;
                    font-size:100px;
                ">
                    👤
                </div>
                """
            )

        uploaded_profile = st.file_uploader(
            "Change Profile Picture",
            type=[
                "jpg",
                "jpeg",
                "png",
                "webp"
            ],
            key="profile_picture"
        )

        if uploaded_profile:

            profile_bytes = (
                uploaded_profile.getvalue()
            )

            if st.button(
                "Save Profile Picture",
                type="primary",
                use_container_width=True
            ):

                success, error = (
                    update_profile_picture(
                        current_user["id"],
                        profile_bytes
                    )
                )

                if success:

                    st.success(
                        "Profile picture updated!"
                    )

                    st.rerun()

                else:

                    st.error(error)

    with col2:

        render_markdown(
            f"""
            <div class="card">

                <h2>
                    {html.escape(str(current_user["name"]))}
                </h2>

                <p>
                    📧 {html.escape(str(current_user["email"]))}
                </p>

                <hr>

                <p>
                    ⭐ <b>Points:</b>
                    {current_user["points"]}
                </p>

                <p>
                    📷 <b>Total Scans:</b>
                    {current_user["scans"]}
                </p>

                <p>
                    🌱 <b>CO₂ Saved:</b>
                    {current_user["co2"]:.2f} kg
                </p>

                <p>
                    📅 <b>Joined:</b>
                    {current_user["created_at"]}
                </p>

            </div>
            """
        )

        st.subheader(
            "🌱 Your Mission"
        )

        st.write(
            "Every scan helps you learn about waste "
            "and encourages better environmental habits."
        )