import chromadb
from chromadb.config import Settings
from langchain_chroma import Chroma
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.docstore.document import Document
from PyPDF2 import PdfReader
from PIL import Image
from docx import Document as DocxDocument
from pptx import Presentation
import os
import logging
import pytesseract

from dotenv import load_dotenv

load_dotenv()

CHROMA_DIR = "chroma_db"

# Inisialisasi ChromaDB
chroma_client = chromadb.Client(Settings(persist_directory=CHROMA_DIR))

# Embedding Google GenAI
embedding = GoogleGenerativeAIEmbeddings(
    model="models/text-embedding-004",
    GOOGLE_API_KEY=os.getenv("GOOGLE_API_KEY", "")
    )

# LangChain VectorStore
vectorstore = Chroma(
    client=chroma_client,
    collection_name="rag_docs",
    embedding_function=embedding,
)

logging.basicConfig(level=logging.INFO)

def extract_text_from_pdf(file_path):
    reader = PdfReader(file_path)
    docs = []
    for i, page in enumerate(reader.pages):
        content = page.extract_text() or ""
        if content:
            docs.append(Document(page_content=content, metadata={"page_number": i + 1}))
    return docs

def extract_text_from_image(file_path):
    image = Image.open(file_path)
    text = pytesseract.image_to_string(image, lang='eng')
    if text:
        return [Document(page_content=text, metadata={"page_number": 1})]
    return []

def extract_text_from_docx(file_path):
    doc = DocxDocument(file_path)
    docs = []
    for i, para in enumerate(doc.paragraphs):
        if para.text:
            docs.append(Document(page_content=para.text, metadata={"paragraph_number": i + 1}))
    return docs

def extract_text_from_pptx(file_path):
    prs = Presentation(file_path)
    docs = []
    for i, slide in enumerate(prs.slides):
        slide_text = ""
        for shape in slide.shapes:
            if hasattr(shape, "text"):
                slide_text += shape.text + "\n"
        if slide_text:
            docs.append(Document(page_content=slide_text, metadata={"slide_number": i + 1}))
    return docs

def index_file(file_path, filetype, metadata=None):
    logging.info(f"[ChromaDB] Mulai indexing file: {file_path} ({filetype}) dengan metadata: {metadata}")
    docs = []
    if filetype == "application/pdf":
        docs = extract_text_from_pdf(file_path)
    elif filetype.startswith("image/"):
        docs = extract_text_from_image(file_path)
    elif filetype == "application/vnd.openxmlformats-officedocument.wordprocessingprocessingml.document" or file_path.endswith(".docx"):
        docs = extract_text_from_docx(file_path)
    elif filetype == "application/vnd.openxmlformats-officedocument.presentationml.presentation" or file_path.endswith(".pptx"):
        docs = extract_text_from_pptx(file_path)
    else:
        logging.warning(f"[ChromaDB] Filetype tidak didukung: {filetype}")
        return False

    if not docs:
        logging.warning(f"[ChromaDB] Tidak ada teks yang diekstrak dari file: {file_path}")
        return False

    # Add user and file metadata to each document
    for doc in docs:
        doc.metadata.update(metadata or {})

    splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=100)
    chunks = splitter.split_documents(docs)
    
    logging.info(f"[ChromaDB] Jumlah chunk yang akan di-embedding: {len(chunks)}")
    if chunks:
        vectorstore.add_documents(chunks)
        logging.info(f"[ChromaDB] Selesai indexing dan embedding file: {file_path}")
        return True
    else:
        logging.warning(f"[ChromaDB] Tidak ada chunk yang dihasilkan setelah splitting: {file_path}")
        return False

def query_rag(query, top_k=3, file_path=None):
    if file_path:
        from langchain.text_splitter import RecursiveCharacterTextSplitter
        from langchain.docstore.document import Document
        if file_path.endswith('.pdf'):
            text = extract_text_from_pdf(file_path)
        elif file_path.endswith('.docx'):
            text = extract_text_from_docx(file_path)
        elif file_path.endswith('.pptx'):
            text = extract_text_from_pptx(file_path)
        elif file_path.lower().endswith(('.png', '.jpg', '.jpeg', '.bmp', '.gif')):
            text = extract_text_from_image(file_path)
        else:
            text = ""
        splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=100)
        docs = [Document(page_content=chunk) for chunk in splitter.split_text(text)]
        results = [(doc, 0) for doc in docs if query.lower() in doc.page_content.lower()][:top_k]
        return [doc for doc, _ in results]
    else:
        docs = vectorstore.similarity_search(query, k=top_k)
        return docs
