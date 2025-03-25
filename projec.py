import streamlit as st
import google.generativeai as genai
import speech_recognition as sr
import pyaudio
import datetime
import uuid
import io
import base64
from PIL import Image
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib import colors
from streamlit_option_menu import option_menu
import random
import qrcode

# Initialize Gemini AI
genai.configure(api_key="AIzaSyDBvol5FW3D1aqdNRg0fwiDqn_z1rnS8ic")  # Replace with your actual API key
model = genai.GenerativeModel('gemini-1.5-flash')

# --- Utility Functions ---

def speak_text(text, lang_code):
    """Convert text to speech using browser's speech synthesis with specified language."""
    try:
        js_code = f"""
        <script>
            var utterance = new SpeechSynthesisUtterance("{text}");
            utterance.lang = "{lang_code}";
            utterance.pitch = {st.session_state.voice_pitch};
            utterance.rate = {st.session_state.voice_rate};
            window.speechSynthesis.speak(utterance);
        </script>
        """
        st.components.v1.html(js_code, height=0)
    except Exception as e:
        st.error(f"Speech synthesis error: {e}")

def recognize_speech(language_code):
    """Recognize speech input from microphone with improved accuracy and user feedback."""
    recognizer = sr.Recognizer()
    with sr.Microphone() as source:
        st.info(f"🎙️ Listening in {st.session_state.selected_language}... Speak clearly.")
        recognizer.adjust_for_ambient_noise(source, duration=1)
        try:
            audio = recognizer.listen(source, timeout=5, phrase_time_limit=15)
            text = recognizer.recognize_google(audio, language=language_code)
            st.success(f"Transcribed: '{text}' - Edit below if incorrect.")
            return text
        except sr.WaitTimeoutError:
            st.error("🎙️ No speech detected. Please try again.")
            return None
        except sr.UnknownValueError:
            st.error("🎙️ Could not understand. Please repeat clearly.")
            return None
        except sr.RequestError as e:
            st.error(f"🎙️ Speech recognition error: {e}")
            return None

def transcribe_audio_file(audio_file, language_code):
    """Transcribe an uploaded audio file."""
    recognizer = sr.Recognizer()
    try:
        with sr.AudioFile(audio_file) as source:
            audio = recognizer.record(source)
            text = recognizer.recognize_google(audio, language=language_code)
            return text
    except sr.UnknownValueError:
        st.error("Could not understand the audio file. Please upload a clearer recording.")
        return None
    except sr.RequestError as e:
        st.error(f"Audio transcription error: {e}")
        return None
    except Exception as e:
        st.error(f"Error processing audio file: {e}")
        return None

def translate_text(text, source_lang, target_lang):
    """Translate text to target language, returning only the translated text."""
    if source_lang == target_lang or not text:
        return text
    with st.spinner(f"Translating to {target_lang}..."):
        try:
            prompt = f"Translate this '{source_lang}' text to '{target_lang}' and provide only the translated text: '{text}'"
            response = model.generate_content(prompt)
            return response.text.strip()
        except Exception as e:
            st.error(f"Translation error: {e}")
            return text

def init_session_state():
    """Initialize session state variables."""
    defaults = {
        'chat_history': [],
        'form_data': {},
        'form_data_translated': {},
        'complaint_tickets': {},
        'questions_index': 0,
        'chatbot_active': False,
        'speech_input': "",
        'last_spoken_index': -1,
        'voice_enabled': True,
        'voice_pitch': 1.0,
        'voice_rate': 1.0,
        'selected_language': "English",
        'ready_to_submit': False,
        'translated_questions': {},
        'selected_category': None,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value

init_session_state()

# Language mappings (supporting all 23 languages)
languages = {
    "Hindi": "hi-IN", "Konkani": "kok-IN", "Kannada": "kn-IN", "Dogri": "doi-IN",
    "Bodo": "brx-IN", "Urdu": "ur-IN", "Tamil": "ta-IN", "Kashmiri": "ks-IN",
    "Assamese": "as-IN", "Bengali": "bn-IN", "Marathi": "mr-IN", "Sindhi": "sd-IN",
    "Maithili": "mai-IN", "Punjabi": "pa-IN", "Malayalam": "ml-IN", "Manipuri": "mni-IN",
    "Telugu": "te-IN", "Sanskrit": "sa-IN", "Nepali": "ne-IN", "Santali": "sat-IN",
    "Gujarati": "gu-IN", "Odia": "or-IN", "English": "en-IN"
}
tts_lang_codes = {k: v.split('-')[0] + '-' + v.split('-')[1].upper() for k, v in languages.items()}
native_commands = {
    "English": {"next": "next", "back": "back", "submit": "submit", "repeat": "repeat"},
    "Hindi": {"next": "अगला", "back": "पीछे", "submit": "जमा करें", "repeat": "दोहराएं"},
    "Tamil": {"next": "அடுத்து", "back": "பின்னால்", "submit": "சமர்ப்பி", "repeat": "மீண்டும்"},
    "Telugu": {"next": "తదుపరి", "back": "వెనక్కి", "submit": "సమర్పించు", "repeat": "పునరావృతం"},
    "Kannada": {"next": "ಮುಂದಿನ", "back": "ಹಿಂದೆ", "submit": "ಸಲ್ಲಿಸು", "repeat": "ಪುನರಾವರ್ತನೆ"},
    "Malayalam": {"next": "അടുത്തത്", "back": "പിന്നോട്ട്", "submit": "സമർപ്പിക്കുക", "repeat": "ആവർത്തിക്കുക"},
    "Marathi": {"next": "पुढील", "back": "मागे", "submit": "सादर करा", "repeat": "पुनरावृत्ती"},
    "Bengali": {"next": "পরবর্তী", "back": "পিছনে", "submit": "জমা দিন", "repeat": "পুনরাবৃত্তি"},
    "Gujarati": {"next": "આગળ", "back": "પાછળ", "submit": "સબમિટ કરો", "repeat": "પુનરાવર્તન"},
    "Punjabi": {"next": "ਅਗਲਾ", "back": "ਪਿੱਛੇ", "submit": "ਜਮ੍ਹਾ ਕਰੋ", "repeat": "ਦੁਹਰਾਓ"}
}

# Complaint categories
complaint_categories = {
    "Women/Children Related Crime": [
        "Rape/Gang Rape (RGR)-Sexually Abusive Content",
        "Sexually Obscene material",
        "Child Pornography (CP)-Child Sexual Abuse Material (CSEAM)",
        "Sexually Explicit Act"
    ],
    "Financial Fraud": [
        "UPI Fraud",
        "Credit/Debit Card Fraud",
        "Online Banking Fraud",
        "Investment Fraud",
        "Insurance Fraud"
    ],
    "Other Cyber Crime": [
        "Website Hacking",
        "IP Theft",
        "Online Gambling",
        "Cryptocurrency Fraud",
        "General Complaint"
    ]
}

# Chatbot questions
form_filling_questions = [
    {"field": "incident_datetime", "question": {"English": "What is the approximate date and time of the incident?"}, "required": True},
    {"field": "reason_delay", "question": {"English": "What is the reason for delay in reporting?"}, "required": False},
    {"field": "state_ut", "question": {"English": "Which State or Union Territory did the incident occur in?"}, "required": True},
    {"field": "district", "question": {"English": "Which district did the incident occur in?"}, "required": True},
    {"field": "police_station", "question": {"English": "Which police station is nearest to where the incident occurred?"}, "required": False},
    {"field": "incident_location", "question": {"English": "Where did the incident occur? (e.g., Email, Facebook, WhatsApp, Website URL)"}, "required": True},
    {"field": "incident_details", "question": {"English": "Please provide details about the incident (minimum 200 characters)"}, "required": True},
    {"field": "suspect_info_type", "question": {"English": "What type of information do you have about the suspect? (e.g., Email, Mobile Number, Social Media Profile URL)"}, "required": False},
    {"field": "suspect_info_value", "question": {"English": "Please provide the suspect's information based on the type selected"}, "required": False},
    {"field": "suspect_additional_info", "question": {"English": "Any additional information about the suspect?"}, "required": False},
    {"field": "name", "question": {"English": "What is your full name?"}, "required": True},
    {"field": "phone", "question": {"English": "What is your contact phone number?"}, "required": True},
    {"field": "email", "question": {"English": "What is your email address?"}, "required": True},
    {"field": "address", "question": {"English": "What is your current address?"}, "required": True},
    {"field": "id_type", "question": {"English": "What type of ID would you like to provide? Please choose from: Voter ID, Driving License, Passport, PAN Card, Aadhar Card"}, "required": True},
    {"field": "bank_wallet_merchant", "question": {"English": "What is the name of the bank, wallet, or merchant involved?"}, "required": False},
    {"field": "transaction_id", "question": {"English": "What is the 12-digit Transaction ID or UTR Number?"}, "required": False},
    {"field": "transaction_date", "question": {"English": "What is the date of the transaction?"}, "required": False},
    {"field": "fraud_amount", "question": {"English": "What is the amount of the fraud?"}, "required": False},
    {"field": "suspect_website_social", "question": {"English": "Do you have any suspected website URLs or social media handles?"}, "required": False},
    {"field": "suspect_mobile", "question": {"English": "What is the suspect's mobile number, if known?"}, "required": False},
    {"field": "suspect_email", "question": {"English": "What is the suspect's email ID, if known?"}, "required": False},
    {"field": "suspect_bank_account", "question": {"English": "What is the suspect's bank account number, if known?"}, "required": False},
    {"field": "suspect_address", "question": {"English": "What is the suspect's address, if known?"}, "required": False}
]

# --- UI Configuration ---
st.set_page_config(page_title="CyberGuard AI - National Cyber Crime Reporting Portal", page_icon="🛡️", layout="wide", initial_sidebar_state="expanded")
st.markdown(
    """
    <style>
    .stApp { background-color: #f5f7fa; }
    .header { background: linear-gradient(90deg, #0047AB 0%, #184C78 100%); color: white; padding: 1.5rem; text-align: center; border-radius: 10px; box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1); margin-bottom: 20px; }
    .content-card { background-color: white; padding: 20px; border-radius: 10px; box-shadow: 0 2px 4px rgba(0, 0, 0, 0.05); margin-bottom: 20px; }
    .dashboard-card { background-color: white; padding: 15px; border-radius: 10px; box-shadow: 0 2px 4px rgba(0, 0, 0, 0.05); text-align: center; margin: 5px; }
    .stButton>button { background-color: #0047AB; color: white; border: none; border-radius: 5px; padding: 0.5rem 1rem; font-weight: 500; }
    .stButton>button:hover { background-color: #003087; border: none; }
    .stTextInput>div>div>input, .stTextArea>div>div>textarea { border-radius: 5px; border: 1px solid #E0E0E0; }
    .status-badge { padding: 5px 10px; border-radius: 15px; font-weight: 500; display: inline-block; }
    .status-pending { background-color: #FFF9C4; color: #F57F17; }
    .status-active { background-color: #E3F2FD; color: #0D47A1; }
    .status-resolved { background-color: #E8F5E9; color: #1B5E20; }
    .chat-message { padding: 1rem; border-radius: 15px; margin-bottom: 10px; max-width: 80%; display: inline-block; }
    .user-message { background-color: #E3F2FD; float: right; clear: both; border-bottom-right-radius: 5px; }
    .bot-message { background-color: #F5F5F5; float: left; clear: both; border-bottom-left-radius: 5px; }
    .chat-container { height: calc(80vh - 200px); overflow-y: auto; padding: 20px; display: flex; flex-direction: column; }
    .helpline-badge { background-color: #E91E63; color: white; padding: 5px 10px; border-radius: 30px; font-weight: bold; margin: 5px; display: inline-block; }
    .footer { text-align: center; padding: 20px; color: #666; font-size: 0.8rem; border-top: 1px solid #eee; margin-top: 30px; }
    .language-selector { margin-bottom: 20px; text-align: right; }
    .stat-counter { font-size: 2rem; font-weight: bold; color: #0047AB; }
    @media (max-width: 768px) { .chat-message { max-width: 90%; } }
    #MainMenu {visibility: hidden;} footer {visibility: hidden;} header {visibility: hidden;}
    .progress-bar { background-color: #E0E0E0; border-radius: 5px; height: 20px; }
    .progress-fill { background-color: #0047AB; height: 100%; border-radius: 5px; }
    </style>
    """,
    unsafe_allow_html=True
)

# --- Database and PDF Functions ---

def save_to_db(data, translated_data):
    """Save complaint data and return a ticket ID."""
    ticket_id = f"CYBER-{uuid.uuid4().hex[:8].upper()}"
    st.session_state.complaint_tickets[ticket_id] = {
        "data": data,
        "translated_data": translated_data,
        "status": "Under Investigation",
        "date_filed": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "last_updated": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "assigned_to": f"Officer {random.choice(['Kumar', 'Singh', 'Sharma', 'Patel', 'Gupta'])}",
        "priority": random.choice(["High", "Medium", "Low"])
    }
    return ticket_id

def generate_complaint_pdf(data):
    """Generate a PDF with only user-provided data."""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter)
    styles = getSampleStyleSheet()
    story = []

    story.append(Paragraph("CYBER CRIME COMPLAINT REPORT", styles['Heading1']))
    story.append(Spacer(1, 12))

    complaint_data = [
        ["Field", "Details"],
        ["Ticket Number", data.get('ticket_id', '')],
        ["Date Filed", data.get('date_filed', '')],
        ["Name", data.get('name', '')],
        ["Phone", data.get('phone', '')],
        ["Email", data.get('email', '')],
        ["Address", data.get('address', '')],
        ["ID Type", data.get('id_type', '')],
        ["ID Number", data.get('id_number', '')],
        ["Incident Date", data.get('incident_datetime', '')],
        ["Description", data.get('incident_details', '')],
        ["Financial Loss", data.get('fraud_amount', 'N/A')],
        ["Suspect Details", data.get('suspect_additional_info', 'N/A')],
        ["Category", f"{data.get('category', '')} - {data.get('sub_category', '')}"],
        ["Status", data.get('status', '')],
        ["Assigned Officer", data.get('assigned_to', '')],
        ["Priority", data.get('priority', '')]
    ]

    table = Table(complaint_data, colWidths=[150, 400])
    table.setStyle(TableStyle([
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
    ]))
    story.append(table)
    doc.build(story)
    buffer.seek(0)
    return buffer

# --- Chatbot Functions ---

def get_question_text(question_dict, lang):
    """Get or cache translated question text."""
    if lang in question_dict:
        return question_dict[lang]
    if (lang, question_dict["English"]) in st.session_state.translated_questions:
        return st.session_state.translated_questions[(lang, question_dict["English"])]
    translated_text = translate_text(question_dict["English"], "English", lang)
    question_dict[lang] = translated_text
    st.session_state.translated_questions[(lang, question_dict["English"])] = translated_text
    return translated_text

def process_chatbot_input(user_input, current_question):
    """Process user input with precise extraction."""
    lang = st.session_state.selected_language
    commands = native_commands.get(lang, native_commands["English"])

    if user_input.lower() in [commands["next"], "next"]:
        st.session_state.questions_index += 1
        return None
    elif user_input.lower() in [commands["back"], "back"]:
        st.session_state.questions_index = max(0, st.session_state.questions_index - 1)
        return None
    elif user_input.lower() in [commands["submit"], "submit"]:
        st.session_state.chatbot_active = False
        st.session_state.ready_to_submit = True
        return "Please review your details below."
    elif user_input.lower() in [commands["repeat"], "repeat"]:
        return get_question_text(current_question['question'], lang)

    with st.spinner("Processing your response..."):
        if current_question['field'] == "id_type":
            prompt = f"Identify the ID type from this '{lang}' input. Options are: Voter ID, Driving License, Passport, PAN Card, Aadhar Card. Provide only the selected ID type or 'Unknown' if unclear: '{user_input}'"
        else:
            prompt = f"Extract the {current_question['field']} from this '{lang}' input and provide only the extracted value: '{user_input}'"
        try:
            response = model.generate_content(prompt)
            extracted_value = response.text.strip()
            if current_question['field'] == "id_type" and extracted_value not in ["Voter ID", "Driving License", "Passport", "PAN Card", "Aadhar Card"]:
                return "Please specify ID type from: Voter ID, Driving License, Passport, PAN Card, Aadhar Card."
        except Exception as e:
            st.error(f"Extraction error: {e}")
            extracted_value = user_input

    st.session_state.form_data[current_question['field']] = extracted_value
    st.session_state.form_data_translated[current_question['field']] = translate_text(extracted_value, lang, "English")
    st.session_state.questions_index += 1
    if st.session_state.questions_index >= len(form_filling_questions):
        st.session_state.chatbot_active = False
        st.session_state.ready_to_submit = True
        return "Please review your details below."
    return None

def display_chat_message(message, is_user=False):
    """Display chat messages with styling."""
    message_class = "user-message" if is_user else "bot-message"
    st.markdown(f'<div class="chat-message {message_class}">{message}</div>', unsafe_allow_html=True)

# --- Main Application ---

with st.sidebar:
    selected = option_menu(
        "Main Menu",
        ["Home", "Register Complaint", "Track Complaint", "Contact Us"],
        icons=['house', 'file-earmark-text', 'search', 'telephone'],
        menu_icon="shield-lock",
        default_index=0,
        styles={
            "container": {"padding": "5px", "background-color": "#f5f7fa"},
            "icon": {"color": "#0047AB", "font-size": "25px"},
            "nav-link": {"font-size": "16px", "text-align": "left", "margin": "0px", "--hover-color": "#eee"},
            "nav-link-selected": {"background-color": "#0047AB"},
        }
    )

st.markdown(
    """
    <div class="header">
        <h1>CyberGuard AI - National Cyber Crime Reporting Portal</h1>
        <p>File and Track Cyber Crime Complaints with Ease | Powered by AI</p>
        <div class="helpline-badge">National Cyber Crime Helpline: 1930</div>
    </div>
    """,
    unsafe_allow_html=True
)

st.session_state.selected_language = st.selectbox(
    "Select Language / भाषा चुनें",
    list(languages.keys()),
    index=list(languages.keys()).index("English"),
    key="language_selector"
)
language_code = languages[st.session_state.selected_language]
tts_lang = tts_lang_codes[st.session_state.selected_language]

if selected == "Home":
    st.image(r"C:\Users\user\Downloads\cybe1.jpeg", width=300)
    st.markdown(
        """
        <div class="content-card">
            <h2>Welcome to CyberGuard AI</h2>
            <p>India's premier portal for reporting and tracking cyber crimes, powered by Artificial Intelligence. Our mission is to provide a secure, efficient, and user-friendly platform to combat cyber threats.</p>
        </div>
        """,
        unsafe_allow_html=True
    )

    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown(
            """
            <div class="dashboard-card">
                <h3>Total Complaints</h3>
                <div class="stat-counter">{}</div>
            </div>
            """.format(len(st.session_state.complaint_tickets)),
            unsafe_allow_html=True
        )
    with col2:
        st.markdown(
            """
            <div class="dashboard-card">
                <h3>Resolved Cases</h3>
                <div class="stat-counter">{}</div>
            </div>
            """.format(sum(1 for ticket in st.session_state.complaint_tickets.values() if ticket['status'] == "Resolved")),
            unsafe_allow_html=True
        )
    with col3:
        st.markdown(
            """
            <div class="dashboard-card">
                <h3>Active Cases</h3>
                <div class="stat-counter">{}</div>
            </div>
            """.format(sum(1 for ticket in st.session_state.complaint_tickets.values() if ticket['status'] == "Under Investigation")),
            unsafe_allow_html=True
        )

elif selected == "Register Complaint":
    st.image(r"C:\Users\user\Downloads\cybe2.png", width=200)
    st.markdown(
        """
        <div class="content-card">
            <h2>File a New Complaint</h2>
            <p>Please select a complaint category to proceed.</p>
        </div>
        """,
        unsafe_allow_html=True
    )

    # Category selection
    category_options = list(complaint_categories.keys())
    st.session_state.selected_category = st.selectbox(
        "Select Complaint Category",
        category_options,
        index=0 if st.session_state.selected_category is None else category_options.index(st.session_state.selected_category),
        key="category_selector"
    )

    with st.expander("Voice Settings"):
        st.session_state.voice_enabled = st.checkbox("Enable Voice", value=True)
        st.session_state.voice_pitch = st.slider("Pitch", 0.5, 2.0, 1.0)
        st.session_state.voice_rate = st.slider("Speed", 0.5, 2.0, 1.0)

    use_chatbot = st.checkbox("Use AI Chatbot to Fill Form", value=False)

    # Filter questions based on selected category
    if st.session_state.selected_category == "Women/Children Related Crime":
        relevant_questions = [q for q in form_filling_questions if q['field'] not in ["name", "phone", "email", "address", "id_type", "bank_wallet_merchant", "transaction_id", "transaction_date", "fraud_amount"]]
    elif st.session_state.selected_category == "Financial Fraud":
        relevant_questions = [q for q in form_filling_questions if q['field'] not in ["reason_delay", "state_ut", "district", "police_station", "incident_location"]]
    else:  # Other Cyber Crime
        relevant_questions = [q for q in form_filling_questions if q['field'] not in ["reason_delay", "state_ut", "district", "police_station", "incident_location", "bank_wallet_merchant", "transaction_id", "transaction_date", "fraud_amount"]]

    if use_chatbot:
        st.session_state.chatbot_active = True if not st.session_state.ready_to_submit else False
        st.markdown('<div class="chat-container">', unsafe_allow_html=True)

        progress = st.session_state.questions_index / len(relevant_questions) * 100
        st.markdown(f'<div class="progress-bar"><div class="progress-fill" style="width:{progress}%"></div></div>', unsafe_allow_html=True)

        for chat in st.session_state.chat_history:
            display_chat_message(chat['message'], chat['is_user'])

        if st.session_state.chatbot_active and st.session_state.questions_index < len(relevant_questions):
            current_question = relevant_questions[st.session_state.questions_index]
            q_text = get_question_text(current_question['question'], st.session_state.selected_language)

            if st.session_state.voice_enabled and st.session_state.questions_index > st.session_state.last_spoken_index:
                speak_text(q_text, tts_lang)
                st.session_state.last_spoken_index = st.session_state.questions_index

            display_chat_message(q_text)

            # Audio upload for this specific question
            audio_file = st.file_uploader(
                f"Upload audio for '{q_text}'",
                type=['wav', 'mp3'],
                key=f"audio_upload_{st.session_state.questions_index}"
            )
            if audio_file:
                with st.spinner("Transcribing audio..."):
                    transcribed_text = transcribe_audio_file(audio_file, language_code)
                    if transcribed_text:
                        st.session_state.speech_input = transcribed_text
                        st.success(f"Transcribed ({st.session_state.selected_language}): {transcribed_text}")

            col1, col2 = st.columns([4, 1])
            with col1:
                user_input = st.text_input(
                    "Your response",
                    value=st.session_state.speech_input,
                    key=f"chat_input_{st.session_state.questions_index}"
                )
            with col2:
                if st.button("🎙️", key=f"mic_{st.session_state.questions_index}"):
                    speech_text = recognize_speech(language_code)
                    if speech_text:
                        st.session_state.speech_input = speech_text
                        st.rerun()

            if user_input:
                display_chat_message(user_input, is_user=True)
                st.session_state.chat_history.append({"message": q_text, "is_user": False})
                st.session_state.chat_history.append({"message": user_input, "is_user": True})
                response = process_chatbot_input(user_input, current_question)
                if response:
                    display_chat_message(response)
                st.session_state.speech_input = ""
                st.rerun()

        st.markdown('</div>', unsafe_allow_html=True)

        if st.session_state.ready_to_submit:
            st.subheader("Review Your Details")
            with st.form("review_form"):
                for q in relevant_questions:
                    field = q['field']
                    label = get_question_text(q['question'], st.session_state.selected_language)
                    if field == "id_type":
                        value = st.selectbox(
                            label,
                            ["Voter ID", "Driving License", "Passport", "PAN Card", "Aadhar Card"],
                            index=["Voter ID", "Driving License", "Passport", "PAN Card", "Aadhar Card"].index(
                                st.session_state.form_data.get(field, "Voter ID")
                            ) if st.session_state.form_data.get(field) in ["Voter ID", "Driving License", "Passport", "PAN Card", "Aadhar Card"] else 0
                        )
                    else:
                        value = st.text_input(label, value=st.session_state.form_data.get(field, ""))
                    st.session_state.form_data[field] = value
                    st.session_state.form_data_translated[field] = translate_text(value, st.session_state.selected_language, "English")
                sub_category = st.selectbox("Sub Category", complaint_categories[st.session_state.selected_category])
                st.session_state.form_data['category'] = st.session_state.selected_category
                st.session_state.form_data['sub_category'] = sub_category
                st.session_state.form_data_translated['category'] = st.session_state.selected_category
                st.session_state.form_data_translated['sub_category'] = sub_category

                if st.form_submit_button("Confirm and Submit"):
                    ticket_id = save_to_db(st.session_state.form_data, st.session_state.form_data_translated)
                    translated_data = st.session_state.form_data_translated.copy()
                    translated_data.update({
                        "ticket_id": ticket_id,
                        "status": "Under Investigation",
                        "date_filed": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        "assigned_to": st.session_state.complaint_tickets[ticket_id]["assigned_to"],
                        "priority": st.session_state.complaint_tickets[ticket_id]["priority"]
                    })
                    pdf_buffer = generate_complaint_pdf(translated_data)
                    st.success(f"✅ Complaint filed successfully! Your ticket ID is: {ticket_id}")
                    st.download_button(
                        label="Download Complaint PDF",
                        data=pdf_buffer,
                        file_name=f"Complaint_{ticket_id}.pdf",
                        mime="application/pdf"
                    )
                    st.session_state.form_data = {}
                    st.session_state.form_data_translated = {}
                    st.session_state.chat_history = []
                    st.session_state.questions_index = 0
                    st.session_state.ready_to_submit = False
                    st.session_state.selected_category = None

    else:
        with st.form(key='complaint_form'):
            if st.session_state.selected_category == "Women/Children Related Crime":
                st.info("This category allows anonymous reporting. Personal details are not required.")
                incident_datetime = st.text_input("Incident Date & Time")
                reason_delay = st.text_area("Reason for Delay in Reporting (if any)")
                state_ut = st.text_input("State/Union Territory")
                district = st.text_input("District")
                police_station = st.text_input("Nearest Police Station (if known)")
                incident_location = st.text_input("Where did the incident occur? (e.g., Email, WhatsApp)")
                incident_details = st.text_area("Incident Details (min 200 characters)", height=200)
                suspect_info_type = st.text_input("Suspect Information Type (e.g., Email, Mobile)")
                suspect_info_value = st.text_input("Suspect Information Value")
                suspect_additional_info = st.text_area("Additional Suspect Information")
            else:
                col1, col2 = st.columns(2)
                with col1:
                    name = st.text_input("Full Name")
                    phone = st.text_input("Phone Number")
                    email = st.text_input("Email Address")
                    id_type = st.selectbox("ID Type", ["Voter ID", "Driving License", "Passport", "PAN Card", "Aadhar Card"])
                    id_number = st.text_input("ID Number")
                with col2:
                    address = st.text_area("Address")
                    incident_datetime = st.text_input("Incident Date & Time")
                    if st.session_state.selected_category == "Financial Fraud":
                        bank_wallet_merchant = st.text_input("Bank/Wallet/Merchant Name")
                        transaction_id = st.text_input("Transaction ID/UTR Number")
                        transaction_date = st.text_input("Transaction Date")
                        fraud_amount = st.text_input("Fraud Amount")
                incident_details = st.text_area("Incident Details (min 200 characters)", height=200)
                suspect_website_social = st.text_area("Suspected Website/Social Media Handles")
                suspect_mobile = st.text_input("Suspect Mobile Number")
                suspect_email = st.text_input("Suspect Email ID")
                suspect_bank_account = st.text_input("Suspect Bank Account Number")
                suspect_address = st.text_area("Suspect Address")

            sub_category = st.selectbox("Sub Category", complaint_categories[st.session_state.selected_category])
            evidence_files = st.file_uploader("Upload Evidence (Screenshots, Documents, etc.)", accept_multiple_files=True, type=['jpg', 'png', 'pdf', 'docx'])
            submit_button = st.form_submit_button(label='Submit Complaint')

            if submit_button:
                complaint_data = {
                    "category": st.session_state.selected_category,
                    "sub_category": sub_category,
                    "incident_datetime": incident_datetime,
                    "incident_details": incident_details
                }
                if st.session_state.selected_category != "Women/Children Related Crime":
                    complaint_data.update({
                        "name": name, "phone": phone, "email": email, "address": address,
                        "id_type": id_type, "id_number": id_number,
                        "suspect_website_social": suspect_website_social, "suspect_mobile": suspect_mobile,
                        "suspect_email": suspect_email, "suspect_bank_account": suspect_bank_account,
                        "suspect_address": suspect_address
                    })
                    if st.session_state.selected_category == "Financial Fraud":
                        complaint_data.update({
                            "bank_wallet_merchant": bank_wallet_merchant, "transaction_id": transaction_id,
                            "transaction_date": transaction_date, "fraud_amount": fraud_amount
                        })
                else:
                    complaint_data.update({
                        "reason_delay": reason_delay, "state_ut": state_ut, "district": district,
                        "police_station": police_station, "incident_location": incident_location,
                        "suspect_info_type": suspect_info_type, "suspect_info_value": suspect_info_value,
                        "suspect_additional_info": suspect_additional_info
                    })
                translated_data = {k: translate_text(v, st.session_state.selected_language, "English") for k, v in complaint_data.items() if v}
                if evidence_files:
                    complaint_data["evidence_files"] = [{"name": f.name, "content": base64.b64encode(f.read()).decode('utf-8')} for f in evidence_files]
                ticket_id = save_to_db(complaint_data, translated_data)
                translated_data.update({
                    "ticket_id": ticket_id,
                    "status": "Under Investigation",
                    "date_filed": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "assigned_to": st.session_state.complaint_tickets[ticket_id]["assigned_to"],
                    "priority": st.session_state.complaint_tickets[ticket_id]["priority"]
                })
                pdf_buffer = generate_complaint_pdf(translated_data)
                st.success(f"✅ Complaint filed successfully! Your ticket ID is: {ticket_id}")
                st.download_button(
                    label="Download Complaint PDF",
                    data=pdf_buffer,
                    file_name=f"Complaint_{ticket_id}.pdf",
                    mime="application/pdf"
                )
                st.session_state.form_data = {}
                st.session_state.form_data_translated = {}
                st.session_state.selected_category = None

elif selected == "Track Complaint":
    st.image(r"C:\Users\user\Downloads\cybe3.png", width=200)
    st.markdown(
        """
        <div class="content-card">
            <h2>Track Your Complaint</h2>
            <p>Enter your ticket ID to check the status of your complaint.</p>
        </div>
        """,
        unsafe_allow_html=True
    )

    ticket_id = st.text_input("Enter Ticket ID (e.g., CYBER-XXXXXXXX)", "").upper()
    if ticket_id:
        if ticket_id in st.session_state.complaint_tickets:
            ticket_data = st.session_state.complaint_tickets[ticket_id]
            status_class = "status-pending" if ticket_data['status'] == "Under Investigation" else "status-resolved"
            st.markdown(
                f"""
                <div class="content-card">
                    <h3>Complaint Status</h3>
                    <p><strong>Ticket ID:</strong> {ticket_id}</p>
                    <p><strong>Status:</strong> <span class="status-badge {status_class}">{ticket_data['status']}</span></p>
                    <p><strong>Date Filed:</strong> {ticket_data['date_filed']}</p>
                    <p><strong>Last Updated:</strong> {ticket_data['last_updated']}</p>
                    <p><strong>Assigned To:</strong> {ticket_data['assigned_to']}</p>
                    <p><strong>Priority:</strong> {ticket_data['priority']}</p>
                    <p><strong>Category:</strong> {ticket_data['translated_data']['category']} - {ticket_data['translated_data']['sub_category']}</p>
                </div>
                """,
                unsafe_allow_html=True
            )
            pdf_buffer = generate_complaint_pdf(ticket_data['translated_data'])
            st.download_button(
                label="Download Complaint PDF",
                data=pdf_buffer,
                file_name=f"Complaint_{ticket_id}.pdf",
                mime="application/pdf"
            )
        else:
            st.error("❌ Invalid Ticket ID. Please check and try again.")

elif selected == "Contact Us":
    st.markdown(
        """
        <div class="content-card">
            <h2>Contact Us</h2>
            <p>For immediate assistance, please use the following contact information:</p>
            <div class="helpline-badge">National Cyber Crime Helpline: 1930</div>
            <p><strong>Email:</strong> cybercrime@nic.in</p>
            <p><strong>Website:</strong> <a href="https://cybercrime.gov.in" target="_blank">cybercrime.gov.in</a></p>
            <p><strong>Address:</strong> Ministry of Home Affairs, Cyber Crime Wing, North Block, New Delhi - 110001</p>
        </div>
        """,
        unsafe_allow_html=True
    )

st.markdown(
    """
    <div class="footer">
        <p>© 2023 CyberGuard AI | All Rights Reserved | Powered by Streamlit & Google Gemini AI</p>
        <p>Disclaimer: This is a demo application. For actual complaints, please visit the official portal at cybercrime.gov.in</p>
    </div>
    """,
    unsafe_allow_html=True
)