from google import genai
import os

from dotenv import load_dotenv

load_dotenv()

genai_api_key = os.getenv("GOOGLE_API_KEY", "")
client = genai.Client(api_key=genai_api_key)

MODEL_NAME = "gemini-2.0-flash-001"

def generate_answer(query, context_docs=None):
    context = "\n\n".join([doc.page_content for doc in context_docs]) if context_docs else ""
    prompt = f"Context:\n{context}\n\nQuestion: {query}\nAnswer:"
    response = client.models.generate_content(
        model=MODEL_NAME,
        contents=prompt
    )
    return response.text

def recommend_prompts(context_docs, n=3):
    context = "\n\n".join([doc.page_content[:500] for doc in context_docs])
    prompt = f"Berdasarkan konteks berikut, buatkan 3 pertanyaan yang relevan untuk membantu mahasiswa belajar:\n{context}\n\nTulis dalam format list:\n1. ...\n2. ...\n3. ..."
    response = client.models.generate_content(
        model=MODEL_NAME,
        contents=prompt
    )
    return response.text
