import streamlit as st
import sqlite3
import pandas as pd
import numpy as np
from PIL import Image
import os
import speech_recognition as sr
import pyttsx3
import threading
from gtts import gTTS
import tempfile
import pygame
import base64

# ==============================
# DATABASE SETUP (SAFE VERSION)
# ==============================
conn = sqlite3.connect("agriculture.db", check_same_thread=False)
cursor = conn.cursor()

try:
    cursor.execute("SELECT medicine FROM predictions LIMIT 1")
    cursor.execute("ALTER TABLE predictions RENAME COLUMN medicine TO treatment")
    conn.commit()
except sqlite3.OperationalError:
    pass

cursor.execute("""
CREATE TABLE IF NOT EXISTS predictions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    farmer_name TEXT,
    disease TEXT,
    treatment TEXT,
    language TEXT
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS chat_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    question TEXT,
    answer TEXT,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
)
""")
conn.commit()

# ==============================
# SAMPLE CROP DATA
# ==============================
crop_data = pd.DataFrame({
    "Crop": ["Rice", "Wheat", "Maize", "Tomato", "Sugarcane", "Jute", "Tea", "Coconut", "Banana", "Cotton", "Soybean", "Barley"],
    "Nitrogen": [120, 100, 110, 90, 140, 100, 110, 80, 150, 95, 85, 90],
    "Phosphorus": [60, 50, 55, 40, 70, 45, 50, 35, 65, 45, 40, 45],
    "Potassium": [40, 30, 35, 25, 50, 35, 40, 30, 55, 30, 28, 28],
    "Climate": ["Wet", "Cool", "Moderate", "Warm", "Wet", "Wet", "Wet", "Wet", "Wet", "Moderate", "Moderate", "Cool"]
})

def speak(text, language="English"):
    def run():
        if language == "Tamil":
            try:
                tts = gTTS(text=text, lang="ta")
                with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as f:
                    tmp_path = f.name
                tts.save(tmp_path)
                pygame.mixer.init()
                pygame.mixer.music.load(tmp_path)
                pygame.mixer.music.play()
                while pygame.mixer.music.get_busy():
                    pygame.time.Clock().tick(10)
                pygame.mixer.music.unload()
                os.remove(tmp_path)
            except Exception:
                pass
        else:
            engine = pyttsx3.init()
            engine.setProperty("rate", 150)
            engine.setProperty("volume", 1.0)
            engine.say(text)
            engine.runAndWait()
    threading.Thread(target=run, daemon=True).start()

# ==============================
# CHATBOT KNOWLEDGE BASE
# ==============================
faq_knowledge = {
    "fertilizer": {
        "English": "Fertilizers provide essential nutrients (NPK - Nitrogen, Phosphorus, Potassium) to plants. Apply based on soil test results. Use urea for nitrogen, DAP for phosphorus, and MOP for potassium.",
        "Tamil": "உரங்கள் தாவரங்களுக்கு அவசியமான NPK சத்துக்களை வழங்குகின்றன. மண் பரிசோதனை அடிப்படையில் இடவும். நைட்ரஜனுக்கு யூரியா, பாஸ்பரஸுக்கு DAP, பொட்டாசியத்திற்கு MOP பயன்படுத்தவும்."
    },
    "irrigation": {
        "English": "Water crops early morning (6-8 AM) or evening (4-6 PM). Avoid overwatering which causes root rot. Drip irrigation saves 40-60% water compared to flood irrigation.",
        "Tamil": "காலை 6-8 மணி அல்லது மாலை 4-6 மணிக்கு நீர் பாய்ச்சவும். அதிக நீர் வேர் அழுகலை ஏற்படுத்தும். சொட்டு நீர்ப்பாசனம் 40-60% நீரை மிச்சப்படுத்தும்."
    },
    "pest": {
        "English": "Common pests include aphids, whiteflies, and caterpillars. Use neem oil (5ml/liter) for organic control. Spray in evening. Remove infected plants immediately to prevent spread.",
        "Tamil": "அசுவினி, வெள்ளை ஈ, கம்பளிப்பூச்சி பொதுவான பூச்சிகள். வேப்பெண்ணெய் (5ml/லிட்டர்) இயற்கை கட்டுப்பாட்டிற்கு பயன்படுத்தவும். மாலையில் தெளிக்கவும்."
    },
    "soil": {
        "English": "Healthy soil needs organic matter. Add compost 2-3 tons/acre. Rotate crops yearly. Test soil pH annually (ideal 6-7). Use green manure crops like dhaincha.",
        "Tamil": "ஆரோக்கியமான மண்ணுக்கு கரிம பொருட்கள் தேவை. ஏக்கருக்கு 2-3 டன் உரம் இடவும். ஆண்டுதோறும் பயிர் சுழற்சி செய்யவும். மண் pH 6-7 இருக்க வேண்டும்."
    },
    "rotation": {
        "English": "Crop rotation prevents soil depletion and pest buildup. Follow: Rice-Wheat-Legumes. Legumes add nitrogen naturally. Never grow same crop continuously.",
        "Tamil": "பயிர் சுழற்சி மண் சக்தி குறைவை தடுக்கும். நெல்-கோதுமை-பயறு வகை பின்பற்றவும். பயறு வகைகள் இயற்கையாக நைட்ரஜன் சேர்க்கும்."
    },
    "organic": {
        "English": "Organic farming uses natural inputs. Apply vermicompost, cow dung manure. Use neem, garlic spray for pests. Avoid chemical fertilizers and pesticides.",
        "Tamil": "இயற்கை விவசாயம் இயற்கை உள்ளீடுகளை பயன்படுத்துகிறது. மண்புழு உரம், மாட்டு சாணம் இடவும். பூச்சிக்கு வேப்பு, பூண்டு தெளிப்பு பயன்படுத்தவும்."
    },
    "weather": {
        "English": "Check weather forecast before planting. Protect crops from frost, hail, and heavy rain. Use mulching during extreme heat. Harvest before monsoon.",
        "Tamil": "நடவு செய்வதற்கு முன் வானிலை முன்னறிவிப்பு பார்க்கவும். பனி, ஆலங்கட்டி மழையிலிருந்து பயிரை பாதுகாக்கவும். வெப்பத்தில் மல்ச்சிங் பயன்படுத்தவும்."
    },
    "harvest": {
        "English": "Harvest at right maturity: Rice when 80% grains turn golden, Wheat when moisture is 20-25%. Use proper storage to prevent fungal growth and pest damage.",
        "Tamil": "சரியான முதிர்ச்சியில் அறுவடை செய்யவும்: நெல் 80% தங்க நிறமாகும்போது, கோதுமை ஈரப்பதம் 20-25% இருக்கும்போது. பூஞ்சை மற்றும் பூச்சி சேதம் தடுக்க சரியான சேமிப்பு பயன்படுத்தவும்."
    },
    "seed": {
        "English": "Always use certified disease-free seeds from government agencies. Store seeds in cool, dry place. Treat seeds with fungicide before sowing.",
        "Tamil": "அரசு நிறுவனங்களிடமிருந்து சான்றளிக்கப்பட்ட நோயற்ற விதைகளை பயன்படுத்தவும். குளிர்ந்த, உலர்ந்த இடத்தில் சேமிக்கவும். விதைப்பதற்கு முன் பூஞ்சைக்கொல்லி கொண்டு விதை நேர்த்தி செய்யவும்."
    },
    "market": {
        "English": "Check mandi prices daily. Sell when prices are high. Consider contract farming for assured returns. Join farmer producer organizations (FPOs).",
        "Tamil": "தினமும் மண்டி விலைகளை சரிபார்க்கவும். விலை அதிகமாக இருக்கும்போது விற்கவும். உறுதியான வருமானத்திற்கு ஒப்பந்த விவசாயம் பரிசீலிக்கவும். விவசாயி உற்பத்தியாளர் அமைப்புகளில் சேரவும்."
    },
    "water": {
        "English": "Water requirement varies by crop. Rice needs 1200-1500mm, Wheat 450-650mm. Use drip/sprinkler for water efficiency. Avoid waterlogging.",
        "Tamil": "நீர் தேவை பயிரைப் பொறுத்து மாறுபடும். நெல்லுக்கு 1200-1500mm, கோதுமைக்கு 450-650mm தேவை. நீர் திறனுக்கு சொட்டு/தெளிப்பு பாசனம் பயன்படுத்தவும்."
    },
    "nitrogen": {
        "English": "Nitrogen promotes leaf growth. Deficiency causes yellowing. Apply urea 50-150 kg/ha depending on crop. Split application is better than single dose.",
        "Tamil": "நைட்ரஜன் இலை வளர்ச்சியை ஊக்குவிக்கிறது. குறைபாடு மஞ்சள் நிறத்தை ஏற்படுத்தும். பயிரைப் பொறுத்து யூரியா 50-150 kg/ha இடவும். பிரித்து இடுவது சிறந்தது."
    },
    "phosphorus": {
        "English": "Phosphorus helps root development and flowering. Apply DAP or SSP at sowing time. Deficiency causes purple leaves and stunted growth.",
        "Tamil": "பாஸ்பரஸ் வேர் வளர்ச்சி மற்றும் பூக்கலுக்கு உதவுகிறது. விதைப்பு நேரத்தில் DAP அல்லது SSP இடவும். குறைபாடு ஊதா இலைகள் மற்றும் வளர்ச்சி தடைப்படுதலை ஏற்படுத்தும்."
    },
    "potassium": {
        "English": "Potassium improves disease resistance and fruit quality. Apply MOP 30-50 kg/ha. Deficiency causes leaf edge burning.",
        "Tamil": "பொட்டாசியம் நோய் எதிர்ப்பு மற்றும் பழ தரத்தை மேம்படுத்துகிறது. MOP 30-50 kg/ha இடவும். குறைபாடு இலை விளிம்பு எரிவை ஏற்படுத்தும்."
    },
    "compost": {
        "English": "Compost improves soil structure and fertility. Mix crop residue, animal waste, and kitchen waste. Ready in 3-4 months. Apply 5-10 tons/acre.",
        "Tamil": "உரம் மண் அமைப்பு மற்றும் வளத்தை மேம்படுத்துகிறது. பயிர் கழிவு, விலங்கு கழிவு, சமையலறை கழிவு கலக்கவும். 3-4 மாதங்களில் தயாராகும். ஏக்கருக்கு 5-10 டன் இடவும்."
    },
    "loan": {
        "English": "Farmers can get Kisan Credit Card (KCC) for crop loans at 4% interest. Visit nearest bank or cooperative society. Repay after harvest.",
        "Tamil": "விவசாயிகள் 4% வட்டியில் கிசான் கிரெடிட் கார்டு (KCC) மூலம் பயிர் கடன் பெறலாம். அருகிலுள்ள வங்கி அல்லது கூட்டுறவு சங்கத்தை அணுகவும். அறுவடைக்கு பிறகு திரும்ப செலுத்தவும்."
    },
    "subsidy": {
        "English": "Government provides subsidies on seeds, fertilizers, equipment, and drip irrigation. Contact agriculture department or Krishi Vigyan Kendra (KVK).",
        "Tamil": "அரசு விதைகள், உரங்கள், உபகரணங்கள் மற்றும் சொட்டு நீர்ப்பாசனத்தில் மானியம் வழங்குகிறது. வேளாண்மை துறை அல்லது கிருஷி விஞ்ஞான் கேந்திரத்தை தொடர்பு கொள்ளவும்."
    },
    "insurance": {
        "English": "Pradhan Mantri Fasal Bima Yojana (PMFBY) covers crop loss due to natural calamities. Premium is 2% for Kharif, 1.5% for Rabi crops.",
        "Tamil": "பிரதான் மந்திரி பசல் பீமா யோஜனா (PMFBY) இயற்கை பேரிடர்களால் ஏற்படும் பயிர் இழப்பை ஈடுசெய்கிறது. காரிஃப் பயிருக்கு 2%, ரபி பயிருக்கு 1.5% பிரீமியம்."
    }
}

def chatbot_response(question, language="English"):
    q = question.lower()
    for key, value in faq_knowledge.items():
        if key in q:
            return value[language]
    for crop in crop_data["Crop"].values:
        if crop.lower() in q:
            crop_info = crop_data[crop_data["Crop"] == crop].iloc[0]
            if language == "Tamil":
                return f"{crop} பயிர் தகவல் - நைட்ரஜன்: {crop_info['Nitrogen']} kg/ha, பாஸ்பரஸ்: {crop_info['Phosphorus']} kg/ha, பொட்டாசியம்: {crop_info['Potassium']} kg/ha. சிறந்த காலநிலை: {crop_info['Climate']}. குறிப்பு: சிறந்த உறிஞ்சுதலுக்கு உரங்களை பிரித்து இடவும்."
            return f"{crop} Crop Info - Nitrogen: {crop_info['Nitrogen']} kg/ha, Phosphorus: {crop_info['Phosphorus']} kg/ha, Potassium: {crop_info['Potassium']} kg/ha. Best Climate: {crop_info['Climate']}. Tip: Apply fertilizers in split doses for better absorption."
    for disease in disease_knowledge.keys():
        if disease.lower() in q:
            return f"{disease} - {disease_knowledge[disease][language]}"
    if "wet" in q or "humid" in q or "rainy" in q:
        suitable_crops = crop_data[crop_data["Climate"] == "Wet"]["Crop"].tolist()
        if language == "Tamil":
            return f"ஈரமான/ஆர்த்திர காலநிலைக்கு ஏற்ற பயிர்கள்: {', '.join(suitable_crops)}. இந்த பயிர்கள் அதிக மழைப்பொழிவு பகுதிகளில் நன்றாக வளரும்."
        return f"For Wet/Humid climate, suitable crops are: {', '.join(suitable_crops)}. These crops thrive in high rainfall areas."
    if "cool" in q or "cold" in q or "winter" in q:
        if language == "Tamil":
            return "குளிர் காலநிலைக்கு ஏற்ற பயிர்கள்: கோதுமை, பார்லி. இவை குளிர் வெப்பநிலை தேவைப்படும் குளிர்கால பயிர்கள்."
        return "For Cool climate, suitable crops are: Wheat, Barley. These are winter crops that need cool temperatures."
    if "warm" in q or "hot" in q or "summer" in q:
        suitable_crops = crop_data[crop_data["Climate"] == "Warm"]["Crop"].tolist()
        if language == "Tamil":
            return f"வெப்பமான காலநிலைக்கு ஏற்ற பயிர்கள்: {', '.join(suitable_crops)}. இந்த பயிர்கள் அதிக வெப்பநிலையை தாங்கும்."
        return f"For Warm climate, suitable crops are: {', '.join(suitable_crops)}. These crops tolerate high temperatures."
    if any(word in q for word in ["hello", "hi", "hey", "namaste", "வணக்கம்"]):
        if language == "Tamil":
            return "வணக்கம்! நான் உங்கள் வேளாண்மை உதவியாளர். பயிர் தகவல், நோய்கள், உரங்கள், நீர்ப்பாசனம், பூச்சி கட்டுப்பாடு மற்றும் விவசாய குறிப்புகளில் உதவ தயாராக இருக்கிறேன். என்ன தெரிந்துகொள்ள விரும்புகிறீர்கள்?"
        return "Hello! I am your Agriculture Assistant. I can help you with crop information, diseases, fertilizers, irrigation, pest control, and farming tips. What would you like to know?"
    if "thank" in q or "நன்றி" in q:
        if language == "Tamil":
            return "மிக்க நன்றி! மகிழ்ச்சியான விவசாயம்! எப்போது வேண்டுமானாலும் கேள்விகள் கேட்கலாம்."
        return "You are welcome! Happy farming! Feel free to ask more questions anytime."
    if language == "Tamil":
        return "பயிர்கள், நோய்கள், உரங்கள், நீர்ப்பாசனம், பூச்சி கட்டுப்பாடு, மண் ஆரோக்கியம், விதைகள், சந்தை, கடன்கள் மற்றும் மானியங்கள் பற்றி உதவ முடியும். குறிப்பிட்ட கேள்வி கேளுங்கள்."
    return "I can help you with crops, diseases, fertilizers, irrigation, pest control, soil health, seeds, market, loans, and subsidies. Please ask a specific question."

# ==============================
# OFFLINE DISEASE KNOWLEDGE
# ==============================
disease_knowledge = {
    "Blight": {
        "English": """
Cause: Fungal infection due to humidity.
Symptoms: Brown leaf spots and drying.
Medicine: Spray Copper Oxychloride 2g/L.
Organic: Neem oil weekly.
Prevention: Avoid excess water.
""",
        "Tamil": """
காரணம்: அதிக ஈரப்பதம் காரணமாக பூஞ்சை தொற்று.
அறிகுறிகள்: பழுப்பு புள்ளிகள்.
மருந்து: Copper Oxychloride 2g/L தெளிக்கவும்.
இயற்கை: வேப்பெண்ணெய் தெளிக்கவும்.
தடுப்பு: அதிக நீர் தவிர்க்கவும்.
"""
    },
    "Leaf Spot": {
        "English": """
Cause: Bacterial infection.
Symptoms: Circular dark spots.
Medicine: Spray Mancozeb.
Organic: Buttermilk spray.
Prevention: Remove infected leaves.
""",
        "Tamil": """
காரணம்: பாக்டீரியா தொற்று.
அறிகுறிகள்: கருப்பு வட்ட புள்ளிகள்.
மருந்து: Mancozeb தெளிக்கவும்.
இயற்கை: மோர் தெளிக்கவும்.
தடுப்பு: பாதிக்கப்பட்ட இலை அகற்றவும்.
"""
    },
    "Powdery Mildew": {
        "English": """
Cause: Fungal infection in dry conditions.
Symptoms: White powdery coating on leaves.
Medicine: Spray Sulfur-based fungicide.
Organic: Milk spray (1:10 ratio with water).
Prevention: Ensure good air circulation.
""",
        "Tamil": """
காரணம்: வறண்ட சூழலில் பூஞ்சை தொற்று.
அறிகுறிகள்: இலைகளில் வெள்ளை பொடி போன்ற படலம்.
மருந்து: கந்தக பூஞ்சைக் கொல்லி தெளிக்கவும்.
இயற்கை: பால் கரைசல் (1:10 விகிதம்) தெளிக்கவும்.
தடுப்பு: காற்று சுழற்சி உறுதி செய்யவும்.
"""
    },
    "Root Rot": {
        "English": """
Cause: Overwatering and poor drainage.
Symptoms: Wilting, yellowing, root decay.
Medicine: Apply Carbendazim to soil.
Organic: Improve drainage, reduce watering.
Prevention: Avoid waterlogging.
""",
        "Tamil": """
காரணம்: அதிக நீர் மற்றும் மோசமான வடிகால்.
அறிகுறிகள்: வாடுதல், மஞ்சள் நிறம், வேர் அழுகல்.
மருந்து: Carbendazim மண்ணில் இடவும்.
இயற்கை: வடிகால் மேம்படுத்தவும், நீர் குறைக்கவும்.
தடுப்பு: நீர் தேங்குவதை தவிர்க்கவும்.
"""
    },
    "Rust": {
        "English": """
Cause: Fungal spores spread by wind.
Symptoms: Orange-brown pustules on leaves.
Medicine: Spray Propiconazole.
Organic: Garlic extract spray.
Prevention: Remove infected plant debris.
""",
        "Tamil": """
காரணம்: காற்றால் பரவும் பூஞ்சை வித்துக்கள்.
அறிகுறிகள்: இலைகளில் ஆரஞ்சு-பழுப்பு கொப்புளங்கள்.
மருந்து: Propiconazole தெளிக்கவும்.
இயற்கை: பூண்டு சாறு தெளிக்கவும்.
தடுப்பு: பாதிக்கப்பட்ட தாவர கழிவுகளை அகற்றவும்.
"""
    },
    "Mosaic Virus": {
        "English": """
Cause: Viral infection spread by insects.
Symptoms: Mottled yellow-green leaf pattern.
Medicine: No cure, remove infected plants.
Organic: Control aphids with neem spray.
Prevention: Use disease-free seeds.
""",
        "Tamil": """
காரணம்: பூச்சிகளால் பரவும் வைரஸ் தொற்று.
அறிகுறிகள்: மஞ்சள்-பச்சை புள்ளி வடிவ இலைகள்.
மருந்து: சிகிச்சை இல்லை, பாதிக்கப்பட்ட செடிகளை அகற்றவும்.
இயற்கை: வேப்பெண்ணெய் மூலம் அசுவினிகளை கட்டுப்படுத்தவும்.
தடுப்பு: நோய் இல்லாத விதைகளை பயன்படுத்தவும்.
"""
    },
    "Anthracnose": {
        "English": """
Cause: Fungal infection in warm, wet conditions.
Symptoms: Dark sunken lesions on fruits and leaves.
Medicine: Spray Chlorothalonil.
Organic: Copper soap fungicide.
Prevention: Prune for air flow, avoid overhead watering.
""",
        "Tamil": """
காரணம்: வெப்பம் மற்றும் ஈரமான சூழலில் பூஞ்சை தொற்று.
அறிகுறிகள்: பழங்கள் மற்றும் இலைகளில் கருமையான புண்கள்.
மருந்து: Chlorothalonil தெளிக்கவும்.
இயற்கை: செம்பு சோப் பூஞ்சைக் கொல்லி.
தடுப்பு: காற்று ஓட்டத்திற்கு கத்தரிக்கவும், மேல் நீர்ப்பாசனம் தவிர்க்கவும்.
"""
    },
    "Healthy": {
        "English": "Plant is healthy. Maintain proper care.",
        "Tamil": "செடி ஆரோக்கியமாக உள்ளது. பராமரிப்பு தொடரவும்."
    }
}

# ==============================
# IMAGE VALIDATION + PREDICTION
# ==============================
def predict_disease(image):
    img = image.convert("RGB")
    img_array = np.array(img.resize((150, 150)))
    red_avg = np.mean(img_array[:, :, 0])
    green_avg = np.mean(img_array[:, :, 1])
    total = red_avg + green_avg + np.mean(img_array[:, :, 2]) + 1
    green_ratio = green_avg / total
    if green_ratio < 0.35:
        return "Not Plant"
    if red_avg > green_avg:
        return "Blight"
    elif green_avg > 120:
        return "Healthy"
    else:
        return "Leaf Spot"

# ==============================
# STREAMLIT UI
# ==============================
st.set_page_config(page_title="Smart Agriculture Assistant", layout="wide")
st.markdown("""
<style>
div.stButton > button[kind="primary"] {
    background-color: #28a745;
    color: white;
    border: none;
}
</style>
""", unsafe_allow_html=True)
image_path = r"D:\Python\AI-Former-Chatbot\farm.jpg"

with open(image_path, "rb") as f:
    img = base64.b64encode(f.read()).decode()

st.markdown(f"""
<div style="
    background-image: url('data:image/jpg;base64,{img}');
    background-size: cover;
    background-position: center;
    background-color: rgba(0,0,0,0.5);
    padding: 50px;
    border-radius: 10px;
    text-align: center;
">
    <h1 style="color:white;
    text-shadow: 2px 2px 6px black;
    ">
         Smart Agriculture Chatbot
    </h1>
</div>
""", unsafe_allow_html=True)


if "menu" not in st.session_state:
    st.session_state.menu = "Farmer Chatbot"

st.sidebar.title("📋 Menu")
if st.sidebar.button("💬 Farmer Chatbot", use_container_width=True, type="primary" if st.session_state.menu == "Farmer Chatbot" else "secondary"):
    st.session_state.menu = "Farmer Chatbot"
if st.sidebar.button("📷 Plant Disease Prediction", use_container_width=True, type="primary" if st.session_state.menu == "Plant Disease Prediction" else "secondary"):
    st.session_state.menu = "Plant Disease Prediction"
if st.sidebar.button("🌱 Fertilizer Dosage", use_container_width=True,type="primary" if st.session_state.menu == "Fertilizer Dosage Prediction" else "secondary"):
    st.session_state.menu = "Fertilizer Dosage Prediction"
if st.sidebar.button("🌾 Crop Nutrient Info", use_container_width=True, type="primary" if st.session_state.menu == "Crop Nutrient Prediction" else "secondary"):
    st.session_state.menu = "Crop Nutrient Prediction"
if st.sidebar.button("⚠ Deficiency Detection", use_container_width=True, type="primary" if st.session_state.menu == "Crop Deficiency Detection" else "secondary"):
    st.session_state.menu = "Crop Deficiency Detection"
if st.sidebar.button("🌍 Crop Selection for Land", use_container_width=True, type="primary" if st.session_state.menu == "Crop Selection Assistance" else "secondary"):
    st.session_state.menu = "Crop Selection Assistance"

menu = st.session_state.menu

# ======================================
# FARMER CHATBOT
# ======================================
if menu == "Farmer Chatbot":
    st.header("💬 Ask Agriculture Questions")

    if "chat_history" not in st.session_state:
        st.session_state.chat_history = []
    if "voice_text" not in st.session_state:
        st.session_state.voice_text = ""
    if "pending_voice" not in st.session_state:
        st.session_state.pending_voice = False

    chat_language = st.selectbox("🌐 Select Language / மொழி தேர்வு", ["English", "Tamil"], key="chat_language")

    # Auto-process voice before rendering input so message stays visible
    if st.session_state.pending_voice and st.session_state.voice_text:
        question = st.session_state.voice_text
        response = chatbot_response(question, chat_language)
        st.session_state.chat_history.append({"question": question, "answer": response})
        cursor.execute("INSERT INTO chat_history (question, answer) VALUES (?, ?)", (question, response))
        conn.commit()
        speak(response, chat_language)
        st.session_state.pending_voice = False
        st.session_state.voice_text = ""

    col1, col2 = st.columns([4, 1])
    with col1:
        label = "உங்கள் கேள்வியை தட்டச்சு செய்யுங்கள்:" if chat_language == "Tamil" else "Type your question:"
        user_question = st.text_input(label, key="user_input")
    with col2:
        st.write("")
        st.write("")
        if st.button("🎤 Speak"):
            recognizer = sr.Recognizer()
            with sr.Microphone() as source:
                st.info("🎙️ Listening... Speak now!")
                recognizer.adjust_for_ambient_noise(source, duration=1)
                try:
                    audio = recognizer.listen(source, timeout=5, phrase_time_limit=10)
                    lang_code = "ta-IN" if chat_language == "Tamil" else "en-IN"
                    text = recognizer.recognize_google(audio, language=lang_code)
                    st.session_state.voice_text = text
                    st.session_state.pending_voice = True
                    st.rerun()
                except sr.WaitTimeoutError:
                    st.warning("No speech detected. Please try again.")
                except sr.UnknownValueError:
                    st.warning("Could not understand. Please speak clearly.")
                except Exception as e:
                    st.error(f"Microphone error: {e}")

    if st.button("Ask") and user_question:
        response = chatbot_response(user_question, chat_language)
        st.session_state.chat_history.append({"question": user_question, "answer": response})
        cursor.execute("INSERT INTO chat_history (question, answer) VALUES (?, ?)", (user_question, response))
        conn.commit()
        speak(response, chat_language)

    if st.session_state.chat_history:
        for chat in reversed(st.session_state.chat_history[-5:]):
            st.success(f"🧑🌾 You: {chat['question']}")
            st.info(f"🤖 Bot: {chat['answer']}")
            st.divider()

# ======================================
# PLANT DISEASE
# ======================================
elif menu == "Plant Disease Prediction":
    st.header("📷 Upload Plant Leaf Image")

    farmer_name = st.text_input("Farmer Name")
    language = st.selectbox("Select Language", ["English", "Tamil"])
    
    image = None
    
    uploaded_file = st.file_uploader("Upload Image", type=["jpg", "png", "jpeg"])
    
    if uploaded_file is not None:
        image = Image.open(uploaded_file)
   

    if image:
        st.image(image, use_container_width=True)
        if st.button("Predict Disease"):
            disease = predict_disease(image)
            if disease == "Not Plant":
                st.error("⚠ Please upload a valid plant leaf image.")
            else:
                st.success(f"Detected Disease: {disease}")
                treatment = disease_knowledge[disease][language]
                st.info(treatment)
                cursor.execute("INSERT INTO predictions (farmer_name, disease, treatment, language) VALUES (?, ?, ?, ?)",
                               (farmer_name, disease, treatment, language))
                conn.commit()

# ======================================
# FERTILIZER
# ======================================
elif menu == "Fertilizer Dosage Prediction":
    st.header("🌱 Fertilizer Dosage Prediction")
    
    st.session_state.menu = "Fertilizer Dosage Prediction"

    crop = st.selectbox("Select Crop", crop_data["Crop"].unique())
    col1, col2 = st.columns(2)
    with col1:
        n = st.number_input("Current Nitrogen (kg/ha)", 0)
        p = st.number_input("Current Phosphorus (kg/ha)", 0)
        k = st.number_input("Current Potassium (kg/ha)", 0)
    with col2:
        moisture = st.number_input("Soil Moisture Level (%)", 0, 100, 40)
        temperature = st.number_input("Temperature (°C)", 0, 60, 28)
        rainfall = st.number_input("Recent Rainfall (mm)", 0, 500, 50)

    if st.button("Calculate"):
        crop_info = crop_data[crop_data["Crop"] == crop].iloc[0]
        need_n = max(0, crop_info["Nitrogen"] - n)
        need_p = max(0, crop_info["Phosphorus"] - p)
        need_k = max(0, crop_info["Potassium"] - k)

        effective_moisture = moisture + (rainfall * 0.3)
        if effective_moisture < 30:
            water_msg = "💧 Soil is very dry. Give water for **4 hours** today."
        elif effective_moisture < 50:
            water_msg = "💧 Soil moisture is low. Give water for **3 hours** for your crop."
        elif effective_moisture < 70:
            water_msg = "💧 Soil moisture is moderate. Give water for **1.5 hours** every 2 days."
        else:
            water_msg = "✅ Soil has enough moisture. No irrigation needed today."

        if temperature > 35:
            fert_tip = "⚠️ High temperature detected. Apply fertilizers in early morning or evening to avoid evaporation loss."
        elif temperature < 15:
            fert_tip = "❄️ Low temperature detected. Nutrient absorption is slow. Reduce fertilizer dose by 20%."
        else:
            fert_tip = "✅ Temperature is ideal for fertilizer application."

        st.subheader("📊 Fertilizer Recommendation")
        col_a, col_b, col_c = st.columns(3)
        col_a.metric("Nitrogen Needed", f"{need_n} kg/ha")
        col_b.metric("Phosphorus Needed", f"{need_p} kg/ha")
        col_c.metric("Potassium Needed", f"{need_k} kg/ha")

        st.subheader("💧 Irrigation Advice")
        st.info(water_msg)
        st.warning(fert_tip)

# ======================================
# CROP NUTRIENT
# ======================================
elif menu == "Crop Nutrient Prediction":
    st.header("🌾 Crop Nutrient Information")
    crop = st.selectbox("Select Crop", crop_data["Crop"].unique())
    st.table(crop_data[crop_data["Crop"] == crop])

# ======================================
# DEFICIENCY
# ======================================
elif menu == "Crop Deficiency Detection":
    st.header("⚠ Crop Deficiency Detection")
    
    st.session_state.menu = "Fertilizer Dosage Prediction"
    nitrogen = st.number_input("Nitrogen Level", 0)
    phosphorus = st.number_input("Phosphorus Level", 0)
    potassium = st.number_input("Potassium Level", 0)
    if st.button("Check"):
        if nitrogen < 50:
            st.warning("Nitrogen Deficiency")
        if phosphorus < 30:
            st.warning("Phosphorus Deficiency")
        if potassium < 20:
            st.warning("Potassium Deficiency")
        if nitrogen >= 50 and phosphorus >= 30 and potassium >= 20:
            st.success("Nutrient Levels are Normal")

# ======================================
# CROP SELECTION FOR LAND
# ======================================
elif menu == "Crop Selection Assistance":
    st.header("🌍 Crop Selection for Your Land")

    col1, col2 = st.columns(2)
    with col1:
        soil_type = st.selectbox("Soil Type", ["Clay", "Sandy", "Loamy", "Silty", "Black", "Red"])
        rainfall_mm = st.number_input("Annual Rainfall (mm)", 100, 3000, 800)
        land_acres = st.number_input("Land Area (Acres)", 0.5, 500.0, 5.0, step=0.5)
    with col2:
        fertilizer_usage = st.selectbox("Fertilizer Usage", ["Low", "Medium", "High"])
        climate = st.selectbox("Climate", crop_data["Climate"].unique())
        farming_exp = st.selectbox("Farming Experience", ["Beginner", "Intermediate", "Expert"])

    yield_data = {
        "Rice": 2.5, "Wheat": 2.0, "Maize": 3.0, "Tomato": 8.0,
        "Sugarcane": 35.0, "Jute": 2.2, "Tea": 1.5, "Coconut": 3.5,
        "Banana": 10.0, "Cotton": 1.2, "Soybean": 1.5, "Barley": 1.8
    }
    soil_crops = {
        "Clay": ["Rice", "Wheat", "Sugarcane"],
        "Sandy": ["Maize", "Barley", "Cotton"],
        "Loamy": ["Wheat", "Maize", "Tomato", "Soybean", "Banana"],
        "Silty": ["Rice", "Wheat", "Jute"],
        "Black": ["Cotton", "Sugarcane", "Soybean", "Wheat"],
        "Red": ["Maize", "Tomato", "Tea", "Coconut"]
    }

    if st.button("🌾 Get Crop Recommendation"):
        climate_crops = crop_data[crop_data["Climate"] == climate]["Crop"].tolist()
        matched_crops = [c for c in climate_crops if c in soil_crops.get(soil_type, [])]
        if not matched_crops:
            matched_crops = climate_crops[:3]

        fert_multiplier = {"Low": 0.7, "Medium": 1.0, "High": 1.2}[fertilizer_usage]
        exp_multiplier = {"Beginner": 0.8, "Intermediate": 1.0, "Expert": 1.15}[farming_exp]

        st.subheader("✅ Recommended Crops for Your Land")
        for crop in matched_crops:
            adjusted_yield = round(yield_data.get(crop, 2.0) * fert_multiplier * exp_multiplier, 2)
            total_yield = round(adjusted_yield * land_acres, 2)
            with st.expander(f"🌾 {crop}"):
                col_a, col_b, col_c = st.columns(3)
                col_a.metric("Yield per Acre", f"{adjusted_yield} tons")
                col_b.metric("Total Yield", f"{total_yield} tons")
                col_c.metric("Land Required", f"{land_acres} Acres")
                crop_info = crop_data[crop_data["Crop"] == crop].iloc[0]
                st.write(f"**NPK Needed:** N-{crop_info['Nitrogen']} | P-{crop_info['Phosphorus']} | K-{crop_info['Potassium']} kg/ha")
                if rainfall_mm < 500:
                    st.warning(f"⚠️ Low rainfall area. {crop} may need irrigation support.")
                elif rainfall_mm > 1500:
                    st.info(f"🌧️ High rainfall area. Ensure proper drainage for {crop}.")
                else:
                    st.success(f"✅ Rainfall is suitable for {crop} cultivation.")

# ======================================
# VIEW RECORDS
# ======================================
st.sidebar.subheader("📊 View Records")

if st.sidebar.button("Show Disease Predictions"):
    data = pd.read_sql_query("SELECT * FROM predictions ORDER BY id DESC LIMIT 10", conn)
    if not data.empty:
        st.sidebar.dataframe(data)
    else:
        st.sidebar.info("No disease predictions yet.")

if st.sidebar.button("Show Chat History"):
    chat_data = pd.read_sql_query("SELECT question, answer, timestamp FROM chat_history ORDER BY id DESC LIMIT 10", conn)
    if not chat_data.empty:
        st.sidebar.subheader("💬 Recent Chats")
        for _, row in chat_data.iterrows():
            st.sidebar.text(f"Q: {row['question'][:50]}...")
            st.sidebar.caption(row['timestamp'])
            st.sidebar.divider()
    else:
        st.sidebar.info("No chat history yet.")


