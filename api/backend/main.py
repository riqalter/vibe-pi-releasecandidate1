from fastapi import FastAPI, UploadFile, File, Form, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session
from api.backend.db import SessionLocal, init_db, User, Message, File as DBFile
from api.backend.chroma import index_file, query_rag
from api.backend.rag import generate_answer, recommend_prompts
from datetime import datetime
from passlib.hash import bcrypt
import os
import logging

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(os.path.dirname(BASE_DIR))
UPLOAD_DIR = os.path.join(PROJECT_ROOT, "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)
logging.basicConfig(level=logging.INFO)

async def lifespan(app: FastAPI):
    init_db()
    yield

app = FastAPI(lifespan=lifespan)

app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@app.post("/register")
def register(data: dict, db: Session = Depends(get_db)):
    username = data.get("username")
    password = data.get("password")
    if not username or not password:
        raise HTTPException(status_code=400, detail="Username dan password wajib diisi.")
    if db.query(User).filter(User.username == username).first():
        return {"ok": False, "message": "Username sudah terdaftar."}
    user = User(username=username)
    user.password_hash = bcrypt.hash(password)
    db.add(user)
    db.commit()
    return {"ok": True, "message": "Registrasi berhasil."}

@app.post("/login")
def login(data: dict, db: Session = Depends(get_db)):
    username = data.get("username")
    password = data.get("password")
    user = db.query(User).filter(User.username == username).first()
    if not user or not bcrypt.verify(password, getattr(user, 'password_hash', '')):
        return {"ok": False, "message": "Username atau password salah."}
    return {"ok": True, "user_id": user.id, "message": "Login berhasil."}

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
    index_file(file_path, file.content_type, metadata={"user_id": user_id, "filename": filename})
    return {"file_id": db_file.id, "filename": filename}

@app.post("/chat/")
def chat(user_id: int = Form(...), message: str = Form(...), file_id: int = Form(None), history: str = Form(None), db: Session = Depends(get_db)):
    msg = Message(user_id=user_id, content=message, timestamp=datetime.now(), role='user')
    db.add(msg)
    db.commit()

    if file_id:
        file = db.query(DBFile).filter(DBFile.id == file_id, DBFile.user_id == user_id).first()
        if not file:
            return {"answer": "File tidak ditemukan."}
        file_path = os.path.join(UPLOAD_DIR, str(file.filename))
        docs = query_rag(message, top_k=3, file_path=file_path)
    else:
        docs = query_rag(message)
    
    answer = generate_answer(message, docs, history)
    bot_msg = Message(user_id=user_id, content=answer, timestamp=datetime.now(), role='assistant')
    db.add(bot_msg)
    db.commit()
    return {"answer": answer}

@app.get("/recommend_prompt/{user_id}")
def recommend_prompt(user_id: int, file_id: int = None, n: int = 6, db: Session = Depends(get_db)):
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
    
    prompts = recommend_prompts(docs, n=n)
    return {"prompts": prompts}

@app.get("/history/{user_id}")
def get_history(user_id: int, db: Session = Depends(get_db)):
    messages = db.query(Message).filter(Message.user_id == user_id).order_by(Message.timestamp).all()
    return [{"role": m.role, "content": m.content} for m in messages]

@app.delete("/history/{user_id}")
def delete_history(user_id: int, db: Session = Depends(get_db)):
    db.query(Message).filter(Message.user_id == user_id).delete()
    db.commit()
    return {"message": "History berhasil dihapus."}

@app.get("/files/{user_id}")
def list_files(user_id: int, db: Session = Depends(get_db)):
    files = db.query(DBFile).filter(DBFile.user_id == user_id).order_by(DBFile.upload_time.desc()).all()
    return [{"id": f.id, "filename": f.filename} for f in files]

@app.delete("/file/{file_id}")
def delete_file(file_id: int, user_id: int, db: Session = Depends(get_db)):
    file = db.query(DBFile).filter(DBFile.id == file_id, DBFile.user_id == user_id).first()
    if not file:
        raise HTTPException(status_code=404, detail="File tidak ditemukan.")
    
    file_path = os.path.join(UPLOAD_DIR, file.filename)
    if os.path.exists(file_path):
        os.remove(file_path)
        
    db.delete(file)
    db.commit()
    return {"message": "File berhasil dihapus."}