import streamlit as st
import requests
from urllib.parse import urlencode

API_URL = "http://localhost:8000"

def register_user(username, password):
    response = requests.post(f"{API_URL}/register", json={"username": username, "password": password})
    return response.ok, response.json().get("message", "")

def login_user(username, password):
    response = requests.post(f"{API_URL}/login", json={"username": username, "password": password})
    if response.ok:
        return True, response.json().get("user_id"), response.json().get("message", "")
    return False, None, response.json().get("message", "")

if 'user_id' not in st.session_state:
    st.session_state['user_id'] = None
if 'username' not in st.session_state:
    st.session_state['username'] = None

# Persist login via query params
if st.session_state['user_id'] and st.session_state['username']:
    st.query_params = {"user_id": st.session_state['user_id'], "username": st.session_state['username']}
else:
    params = st.query_params
    if 'user_id' in params and 'username' in params:
        st.session_state['user_id'] = int(params['user_id'])
        st.session_state['username'] = params['username']

st.title("Chatbot RAG Mahasiswa")

if st.session_state['user_id'] is None:
    st.header("Login atau Register")
    tab1, tab2 = st.tabs(["Login", "Register"])
    with tab1:
        login_username = st.text_input("Username", key="login_username")
        login_password = st.text_input("Password", type="password", key="login_password")
        if st.button("Login"):
            ok, user_id, msg = login_user(login_username, login_password)
            if ok:
                st.session_state['user_id'] = user_id
                st.session_state['username'] = login_username
                st.success("Login berhasil!")
                st.rerun()  # Refresh to show main app
            else:
                st.error(msg)
    with tab2:
        reg_username = st.text_input("Username", key="reg_username")
        reg_password = st.text_input("Password", type="password", key="reg_password")
        if st.button("Register"):
            ok, msg = register_user(reg_username, reg_password)
            if ok:
                st.success("Registrasi berhasil! Silakan login.")
            else:
                st.error(msg)
    st.stop()

user_id = st.session_state['user_id']
username = st.session_state['username']

st.write(f"Selamat datang, {username}!")

# Upload File (PDF/Gambar)
if 'upload_success' not in st.session_state:
    st.session_state['upload_success'] = False
if 'file_uploader_key' not in st.session_state:
    st.session_state['file_uploader_key'] = 0

st.header("Upload File (PDF/Gambar)")
uploaded_file = st.file_uploader("Pilih file PDF atau gambar", type=["pdf", "png", "jpg", "jpeg"], key=st.session_state['file_uploader_key'])

if uploaded_file and not st.session_state['upload_success']:
    files = {"file": (uploaded_file.name, uploaded_file.getvalue(), uploaded_file.type)}
    data = {"user_id": user_id}
    response = requests.post("http://localhost:8000/upload/", files=files, data=data)
    if response.ok:
        st.session_state['upload_success'] = True
        st.success(f"File {uploaded_file.name} berhasil diupload!")
        st.session_state['file_uploader_key'] += 1  # reset file_uploader
        st.rerun()
    else:
        st.error("Gagal upload file.")

if st.session_state['upload_success']:
    st.session_state['upload_success'] = False

# Daftar file user
st.header("File Anda")
files = requests.get(f"{API_URL}/files/{user_id}").json()
for f in files:
    col1, col2, col3, col4 = st.columns([4,2,2,2])
    with col1:
        st.write(f"{f['filename']} ({f['filetype']})")
    with col2:
        download_url = f"{API_URL}/uploads/{f['filename']}"
        st.download_button("Download", data=requests.get(download_url).content, file_name=f['filename'])
    with col3:
        if st.button(f"Hapus {f['id']}"):
            resp = requests.delete(f"{API_URL}/file/{f['id']}")
            if resp.ok:
                st.success("File dihapus!")
                st.rerun()
            else:
                st.error("Gagal hapus file.")
    with col4:
        if st.button(f"Gunakan {f['id']}"):
            st.session_state['active_file'] = f
            st.success(f"Menggunakan file: {f['filename']}")
            # Ambil rekomendasi prompt untuk file ini
            rec = requests.get(f"{API_URL}/recommend_prompt/{user_id}?file_id={f['id']}").json()
            st.session_state['prompt_recommendation'] = rec.get('prompts', '')
            st.rerun()

# Tampilkan file yang sedang aktif digunakan
active_file = st.session_state.get('active_file')
if active_file:
    st.info(f"File aktif: {active_file['filename']}")
    # Tampilkan rekomendasi prompt jika ada
    rec_prompts = st.session_state.get('prompt_recommendation', '')
    if rec_prompts:
        st.subheader("Rekomendasi Prompt:")
        for p in rec_prompts.split("\n"):
            if p.strip():
                if st.button(p.strip()):
                    st.session_state['selected_prompt'] = p.strip()
                    st.session_state['auto_send'] = True
                    st.rerun()

# Toggle untuk menampilkan/menyembunyikan riwayat pesan
show_history = st.checkbox("Tampilkan Riwayat Chat", value=False)
if show_history:
    st.header("Riwayat Pesan")
    history = requests.get(f"http://localhost:8000/history/{user_id}").json()
    for msg in history:
        st.write(f"[{msg['timestamp']}] {msg['content']}")

# Chat
st.header("Chat dengan Bot")
if 'selected_prompt' in st.session_state and st.session_state.get('auto_send'):
    st.session_state['auto_send'] = False
    st.session_state['chat_input'] = st.session_state['selected_prompt']
    st.session_state['selected_prompt'] = ""

# Handle clear input safely
if 'clear_input' not in st.session_state:
    st.session_state['clear_input'] = False

chat_input_value = st.session_state.get('chat_input', '')
if st.session_state['clear_input']:
    chat_input_value = ''
    st.session_state['clear_input'] = False

user_input = st.text_input("Tulis pertanyaan atau pilih prompt di atas", value=chat_input_value, key="chat_input")

# Tempatkan hasil chat terbaru di bawah input
if 'last_bot_answer' in st.session_state and st.session_state['last_bot_answer']:
    st.markdown(f"**Bot:** {st.session_state['last_bot_answer']}")

if st.button("Kirim") and user_input:
    data = {"user_id": user_id, "message": user_input}
    if active_file:
        data["file_id"] = active_file["id"]
    response = requests.post(f"{API_URL}/chat/", data=data)
    if response.ok:
        st.session_state['last_bot_answer'] = response.json()["answer"]
        st.session_state['clear_input'] = True
        st.session_state['auto_send'] = False
        st.rerun()
    else:
        st.error("Gagal mendapatkan jawaban dari bot.")

if st.button("Logout"):
    st.session_state['user_id'] = None
    st.session_state['username'] = None
    st.query_params = {}  # hapus query params dari URL
    st.rerun()
