from google import genai
import os

from dotenv import load_dotenv

load_dotenv()

genai_api_key = os.getenv("GOOGLE_API_KEY", "")
client = genai.Client(api_key=genai_api_key)

MODEL_NAME = "gemini-2.0-flash-lite"

def generate_answer(query, context_docs=None, history=None):
    if not context_docs:
        context = "No context provided."
    else:
        # Build a context string that includes metadata for citation
        context_parts = []
        for doc in context_docs:
            source_info = ""
            if "filename" in doc.metadata:
                source_info += f"Source: {doc.metadata['filename']}"
            if "page_number" in doc.metadata:
                source_info += f", Page: {doc.metadata['page_number']}"
            if "slide_number" in doc.metadata:
                source_info += f", Slide: {doc.metadata['slide_number']}"
            if "paragraph_number" in doc.metadata:
                source_info += f", Paragraph: {doc.metadata['paragraph_number']}"
            
            context_parts.append(f"[{source_info}]\n{doc.page_content}")
        
        context = "\n\n".join(context_parts)

    history_str = f"\n\nChat History:\n{history}" if history else ""
    
    prompt = f"""Anda adalah asisten AI yang membantu mahasiswa. Jawab pertanyaan pengguna berdasarkan konteks yang diberikan.
Ketika Anda menggunakan informasi dari konteks, Anda HARUS mengutip sumbernya di akhir kalimat Anda menggunakan format [Sumber: nama file, Halaman/Slide: nomor].
Jika konteks tidak memberikan jawaban, katakan Anda tidak dapat menemukan jawabannya di dokumen yang diberikan.

{history_str}

Context:
{context}

Question: {query}

Answer:
"""
    response = client.models.generate_content(
        model=MODEL_NAME,
        contents=prompt
    )
    return response.text

def recommend_prompts(context_docs, n=6):
    context = "\n\n".join([doc.page_content[:500] for doc in context_docs])
    prompt = f"Berdasarkan konteks berikut, buatkan {n} pertanyaan yang relevan untuk membantu mahasiswa belajar:\n{context}\n\nTulis dalam format list:\n1. ...\n2. ...\n3. ... anda tidak perlu menjelaskan fokus dari pertanyaan tersebut, hanya buatkan pertanyaan saja."
    response = client.models.generate_content(
        model=MODEL_NAME,
        contents=prompt
    )
    # Split the response text into lines, remove empty lines
    prompts_list = [p.strip() for p in response.text.split('\n') if p.strip()]
    # Remove numbering (e.g., "1. ", "2. ")
    cleaned_prompts = [p.split('.', 1)[-1].strip() for p in prompts_list]
    return cleaned_prompts
