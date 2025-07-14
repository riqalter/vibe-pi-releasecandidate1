import streamlit as st
import requests
import json
import re

# --- Page and Session Configuration ---
st.set_page_config(
    page_title="Belajar dengan Chatbot",
    page_icon="🤖",
    layout="wide"
)

# --- Session State Initialization ---
if 'user_id' not in st.session_state:
    st.session_state['user_id'] = None
if 'username' not in st.session_state:
    st.session_state['username'] = None
if 'chat_history' not in st.session_state:
    st.session_state['chat_history'] = []
if 'file_id' not in st.session_state:
    st.session_state['file_id'] = None
if 'current_file_name' not in st.session_state:
    st.session_state['current_file_name'] = None

# --- Persist login via query params ---
if st.session_state['user_id'] and st.session_state['username']:
    # If logged in, make sure URL reflects the state
    st.query_params = {"user_id": st.session_state['user_id'], "username": st.session_state['username']}
else:
    # If not logged in, check if the URL has login info
    params = st.query_params
    if 'user_id' in params and 'username' in params:
        st.session_state['user_id'] = int(params['user_id'])
        st.session_state['username'] = params['username']

# --- API Configuration ---
API_URL = "http://127.0.0.1:8000"

# --- API Functions ---
def login_user(username, password):
    try:
        response = requests.post(f"{API_URL}/login", json={"username": username, "password": password})
        data = response.json()
        return data.get("ok", False), data.get("user_id"), data.get("message", "")
    except requests.RequestException as e:
        return False, None, f"Connection error: {e}"

def register_user(username, password):
    try:
        response = requests.post(f"{API_URL}/register", json={"username": username, "password": password})
        data = response.json()
        return data.get("ok", False), data.get("message", "")
    except requests.RequestException as e:
        return False, f"Connection error: {e}"

def get_chat_history(user_id):
    response = requests.get(f"{API_URL}/history/{user_id}")
    if response.status_code == 200:
        return response.json()
    return []

def upload_file(user_id, file):
    files = {'file': (file.name, file.getvalue(), file.type)}
    response = requests.post(f"{API_URL}/upload/", data={'user_id': user_id}, files=files)
    return response.json()

def get_chat_response(user_id, message, file_id=None, history=None):
    data = {'user_id': user_id, 'message': message}
    if file_id:
        data['file_id'] = file_id
    if history:
        data['history'] = json.dumps(history)
    response = requests.post(f"{API_URL}/chat/", data=data)
    return response.json()

def get_user_files(user_id):
    response = requests.get(f"{API_URL}/files/{user_id}")
    if response.status_code == 200:
        return response.json()
    return []

def get_recommended_prompts(user_id, file_id=None, n=6):
    response = requests.get(f"{API_URL}/recommend_prompt/{user_id}", params={'file_id': file_id, 'n': n})
    if response.status_code == 200:
        return response.json().get("prompts", [])
    return []

def delete_file(user_id, file_id):
    response = requests.delete(f"{API_URL}/file/{file_id}", params={"user_id": user_id})
    return response.json()

def delete_chat_history(user_id):
    response = requests.delete(f"{API_URL}/history/{user_id}")
    return response.json()

def handle_upload():
    if st.session_state.uploader:
        with st.spinner("Mengupload dan memproses file..."):
            uploaded_file = st.session_state.uploader
            user_id = st.session_state.user_id
            result = upload_file(user_id, uploaded_file)
            if "file_id" in result:
                st.session_state.file_id = result["file_id"]
                st.session_state.current_file_name = re.sub(r'^\d{14}_', '', result["filename"])
                st.sidebar.success(f"File '{st.session_state.current_file_name}' berhasil diupload!")
            else:
                st.sidebar.error("Gagal mengupload file.")

def local_css(file_name):
    try:
        with open(file_name) as f:
            st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)
    except FileNotFoundError:
        st.warning(f"CSS file not found: {file_name}")

local_css("static/style.css")

st.title("Belajar dengan Chatbot 🤖")

# --- Login/Register UI ---
if st.session_state['user_id'] is None:
    st.sidebar.title("Login / Register")
    login_tab, register_tab = st.sidebar.tabs(["Login", "Register"])
    with login_tab:
        login_username = st.text_input("Username", key="login_username")
        login_password = st.text_input("Password", type="password", key="login_password")
        if st.button("Login"):
            ok, user_id, msg = login_user(login_username, login_password)
            if ok:
                st.session_state['user_id'] = user_id
                st.session_state['username'] = login_username
                st.success("Login berhasil!")
                st.rerun()
            else:
                st.error(msg)
    with register_tab:
        reg_username = st.text_input("Username", key="reg_username")
        reg_password = st.text_input("Password", type="password", key="reg_password")
        if st.button("Register"):
            ok, msg = register_user(reg_username, reg_password)
            if ok:
                st.success("Registrasi berhasil! Silakan login.")
            else:
                st.error(msg)
    st.stop()

# --- Main Application UI ---
user_id = st.session_state['user_id']
username = st.session_state['username']

st.sidebar.write(f"Welcome, {username}!")
if st.sidebar.button("Reset History"):
    delete_chat_history(user_id)
    st.session_state.chat_history = []
    st.rerun()

if st.sidebar.button("Logout"):
    st.session_state.clear()
    st.query_params.clear()
    st.rerun()

# Load chat history once after login
if not st.session_state.chat_history:
    st.session_state.chat_history = [(msg['role'], msg['content'], msg.get('citations', [])) for msg in get_chat_history(user_id)]

# --- File Management ---
st.sidebar.title("File Anda")
st.sidebar.file_uploader(
    "Upload file baru", 
    type=['pdf', 'png', 'jpg', 'jpeg', 'docx', 'pptx'], 
    key="uploader",
    on_change=handle_upload
)

if st.sidebar.button("Refresh Daftar File"):
    st.rerun()

user_files = get_user_files(user_id)
if user_files:
    st.sidebar.subheader("Daftar File Tersimpan")
    timestamp_regex = r'^\d{14}_'
    for f in user_files:
        col1, col2, col3 = st.sidebar.columns([3, 1, 1])
        with col1:
            if st.button(f"Chat: {re.sub(timestamp_regex, '', f['filename'])[:20]}...", key=f"select_{f['id']}"):
                st.session_state.file_id = f['id']
                st.session_state.current_file_name = f['filename']
                st.rerun()
        with col2:
            download_url = f"{API_URL}/uploads/{f['filename']}"
            st.link_button("📥", download_url, help=f"Download {f['filename']}")
        with col3:
            if st.button("🗑️", key=f"delete_{f['id']}", help=f"Hapus {f['filename']}"):
                delete_file(user_id, f['id'])
                st.rerun()

# --- Chat Interface ---
st.header("Chat")
if st.session_state.current_file_name:
    timestamp_regex = r'^\d{14}_'
    st.info(f"Saat ini chat dengan file: **{re.sub(timestamp_regex, '', st.session_state.current_file_name)}**")
else:
    st.info("Upload atau pilih file untuk memulai chat.")

for author, text, citations in st.session_state.chat_history:
    with st.chat_message(author):
        st.markdown(text)
        if citations:
            with st.expander("Lihat Sumber"):
                for i, citation_text in enumerate(citations):
                    st.markdown(f"**Sumber {i+1}:** {citation_text}")

# --- Recommended Prompts ---
st.sidebar.title("Rekomendasi Prompt")
num_prompts = st.sidebar.slider("Jumlah prompt:", min_value=1, max_value=10, value=3)
if st.sidebar.button("Dapatkan Rekomendasi"):
    with st.spinner("Membuat rekomendasi..."):
        prompts = get_recommended_prompts(user_id, st.session_state.file_id, n=num_prompts)
        st.session_state.recommended_prompts = prompts

if st.session_state.get("recommended_prompts"):
    st.sidebar.subheader("Klik untuk bertanya:")
    for i, p in enumerate(st.session_state.recommended_prompts):
        if st.sidebar.button(p, key=f"prompt_{i}_{p}"):
            st.session_state.prompt_from_recommendation = p
            st.rerun()

# --- Chat Input ---
prompt = st.chat_input("Tanyakan sesuatu...")
if st.session_state.get("prompt_from_recommendation"):
    prompt = st.session_state.pop("prompt_from_recommendation")

if prompt:
    st.session_state.chat_history.append(("user", prompt, []))
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.spinner("Memikirkan jawaban..."):
        history_for_api = st.session_state.chat_history[-10:]
        response = get_chat_response(user_id, prompt, st.session_state.file_id, history_for_api)
        answer = response.get("answer", "Maaf, terjadi kesalahan.")
        citations = response.get("citations", [])

        st.session_state.chat_history.append(("assistant", answer, citations))

        st.rerun()