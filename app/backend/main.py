from fastapi import FastAPI, UploadFile, File, Form, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session
from .db import SessionLocal, init_db, User, Message, File as DBFile
from .chroma import index_file, query_rag
from .rag import generate_answer, recommend_prompts
from datetime import datetime
from passlib.hash import bcrypt
import os
import logging

BASE_DIR = os.path.dirname(os.path.abspath(__file__))  # .../app/backend
PROJECT_ROOT = os.path.dirname(os.path.dirname(BASE_DIR))  # .../ (project root)
UPLOAD_DIR = os.path.join(PROJECT_ROOT, "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)
logging.basicConfig(level=logging.INFO)
logging.info(f"UPLOAD_DIR is set to: {UPLOAD_DIR}")

async def lifespan(app: FastAPI):
    init_db()
    yield

app = FastAPI(lifespan=lifespan)

# Mount static files for uploads after UPLOAD_DIR is set
app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@app.post("/upload/")
def upload_file(user_id: int = Form(...), file: UploadFile = File(...), db: Session = Depends(get_db)):
    filename = f"{datetime.now().strftime('%Y%m%d%H%M%S')}_{file.filename}"
    file_path = os.path.join(UPLOAD_DIR, filename)
    with open(file_path, "wb") as f:
        f.write(file.file.read())
    db_file = DBFile(user_id=user_id, filename=filename, filetype=file.content_type, upload_time=datetime.now())
    db.add(db_file)
    db.commit()
    db.refresh(db_file)
    # Index file ke ChromaDB
    index_file(file_path, file.content_type, metadata={"user_id": user_id, "filename": filename})
    # Pastikan user ada
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        user = User(id=user_id, username=f"user{user_id}")
        db.add(user)
        db.flush()  # pastikan user sudah ada sebelum insert file
    return {"file_id": db_file.id, "filename": filename}

@app.post("/chat/")
def chat(user_id: int = Form(...), message: str = Form(...), file_id: int = Form(None), db: Session = Depends(get_db)):
    # Simpan pesan user
    msg = Message(user_id=user_id, content=message, timestamp=datetime.now())
    db.add(msg)
    db.commit()
    db.refresh(msg)
    # Query RAG hanya pada file tertentu jika file_id diberikan
    if file_id:
        file = db.query(DBFile).filter(DBFile.id == file_id, DBFile.user_id == user_id).first()
        if not file:
            return {"answer": "File tidak ditemukan."}
        file_path = os.path.join(UPLOAD_DIR, str(file.filename))
        docs = query_rag(message, top_k=3, file_path=file_path)
    else:
        docs = query_rag(message)
    answer = generate_answer(message, docs)
    # Simpan jawaban bot
    bot_msg = Message(user_id=user_id, content=answer, timestamp=datetime.now())
    db.add(bot_msg)
    db.commit()
    db.refresh(bot_msg)
    return {"answer": answer}

@app.get("/recommend_prompt/{user_id}")
def recommend_prompt(user_id: int, file_id: int = None, db: Session = Depends(get_db)): # type: ignore
    # Ambil dokumen terakhir user atau file tertentu
    if file_id:
        file = db.query(DBFile).filter(DBFile.id == file_id, DBFile.user_id == user_id).first()
        if not file:
            return {"prompts": []}
        file_path = os.path.join(UPLOAD_DIR, str(file.filename))
        docs = query_rag("", top_k=3, file_path=file_path)
    else:
        files = db.query(DBFile).filter(DBFile.user_id == user_id).order_by(DBFile.upload_time.desc()).limit(1).all()
        if not files:
            return {"prompts": []}
        file = files[0]
        file_path = os.path.join(UPLOAD_DIR, str(file.filename))
        docs = query_rag("", top_k=3, file_path=file_path)
    prompts = recommend_prompts(docs)
    return {"prompts": prompts}

@app.get("/history/{user_id}")
def get_history(user_id: int, db: Session = Depends(get_db)):
    messages = db.query(Message).filter(Message.user_id == user_id).order_by(Message.timestamp).all()
    return [{"content": m.content, "timestamp": m.timestamp} for m in messages]

@app.post("/register")
def register(data: dict, db: Session = Depends(get_db)):
    username = data.get("username")
    password = data.get("password")
    if not username or not password:
        raise HTTPException(status_code=400, detail="Username dan password wajib diisi.")
    if db.query(User).filter(User.username == username).first():
        return {"message": "Username sudah terdaftar."}
    user = User(username=username)
    user.password_hash = bcrypt.hash(password) # type: ignore
    db.add(user)
    db.commit()
    db.refresh(user)
    return {"message": "Registrasi berhasil."}

@app.post("/login")
def login(data: dict, db: Session = Depends(get_db)):
    username = data.get("username")
    password = data.get("password")
    user = db.query(User).filter(User.username == username).first()
    if not user or not bcrypt.verify(password, getattr(user, 'password_hash', '')): # type: ignore
        return {"message": "Username atau password salah."}
    return {"user_id": user.id, "message": "Login berhasil."}

@app.get("/files/{user_id}")
def list_files(user_id: int, db: Session = Depends(get_db)):
    files = db.query(DBFile).filter(DBFile.user_id == user_id).order_by(DBFile.upload_time.desc()).all()
    return [{"id": f.id, "filename": f.filename, "filetype": f.filetype, "upload_time": f.upload_time} for f in files]

@app.delete("/file/{file_id}")
def delete_file(file_id: int, db: Session = Depends(get_db)):
    file = db.query(DBFile).filter(DBFile.id == file_id).first()
    if not file:
        raise HTTPException(status_code=404, detail="File tidak ditemukan.")
    file_path = os.path.join(UPLOAD_DIR, file.filename) # type: ignore
    if os.path.exists(file_path):
        os.remove(file_path)
    db.delete(file)
    db.commit()
    return {"message": "File berhasil dihapus."}
