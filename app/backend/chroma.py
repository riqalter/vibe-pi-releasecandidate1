import chromadb
from chromadb.config import Settings
from langchain_chroma import Chroma
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.docstore.document import Document
from PyPDF2 import PdfReader
from PIL import Image
import os
import tempfile
import logging

CHROMA_DIR = "chroma_db"

# Inisialisasi ChromaDB
chroma_client = chromadb.Client(Settings(persist_directory=CHROMA_DIR))

# Embedding Google GenAI
embedding = GoogleGenerativeAIEmbeddings(model="models/text-embedding-004")

# LangChain VectorStore
vectorstore = Chroma(
    client=chroma_client,
    collection_name="rag_docs",
    embedding_function=embedding,
)

logging.basicConfig(level=logging.INFO)

def extract_text_from_pdf(file_path):
    reader = PdfReader(file_path)
    text = ""
    for page in reader.pages:
        text += page.extract_text() or ""
    return text

def extract_text_from_image(file_path):
    # Placeholder: Integrasi OCR (misal pytesseract) jika ingin support image to text
    return "[Gambar diupload: {}]".format(os.path.basename(file_path))

def index_file(file_path, filetype, metadata=None):
    logging.info(f"[ChromaDB] Mulai indexing file: {file_path} ({filetype}) dengan metadata: {metadata}")
    if filetype == "application/pdf":
        text = extract_text_from_pdf(file_path)
    elif filetype.startswith("image/"):
        text = extract_text_from_image(file_path)
    else:
        logging.warning(f"[ChromaDB] Filetype tidak didukung: {filetype}")
        return False
    splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=100)
    chunks = splitter.split_text(text)
    logging.info(f"[ChromaDB] Jumlah chunk yang akan di-embedding: {len(chunks)}")
    docs = [Document(page_content=chunk, metadata=metadata or {}) for chunk in chunks]
    # Logging sebelum embedding
    logging.info(f"[ChromaDB] Mulai proses embedding dengan Google GenAI untuk {len(docs)} dokumen...")
    vectorstore.add_documents(docs)
    logging.info(f"[ChromaDB] Selesai indexing dan embedding file: {file_path}")
    return True

def query_rag(query, top_k=3, file_path=None):
    if file_path:
        # Index file jika belum ada, lalu search hanya pada file ini
        # (Sederhana: split dan embed ulang, lalu search di dokumen file ini saja)
        from langchain.text_splitter import RecursiveCharacterTextSplitter
        from langchain.docstore.document import Document
        if file_path.endswith('.pdf'):
            text = extract_text_from_pdf(file_path)
        else:
            text = extract_text_from_image(file_path)
        splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=100)
        docs = [Document(page_content=chunk) for chunk in splitter.split_text(text)]
        # Embed dan search hanya di docs ini
        results = [(doc, 0) for doc in docs if query.lower() in doc.page_content.lower()][:top_k]
        return [doc for doc, _ in results]
    else:
        docs = vectorstore.similarity_search(query, k=top_k)
        return docs
