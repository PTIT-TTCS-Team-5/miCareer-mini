import os
import time

from dotenv import load_dotenv
from langchain_anthropic import ChatAnthropic
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_openai import ChatOpenAI, OpenAIEmbeddings

from core import db

load_dotenv()


def get_query_embedding(query_text: str) -> list[float]:
    """Sử dụng text-embedding-3-small (như cấu trúc FANG) để embed prompt"""
    embeddings = OpenAIEmbeddings(model="text-embedding-3-small")
    return embeddings.embed_query(query_text)


def get_llm(model_tier: str):
    """
    Map chính xác tên model tier (có định danh như yêu cầu).
    (Tier 1, Tier 2, Tier 3)
    """
    if "Gemini Flash" in model_tier:
        # Tên model có thể chưa chính thức nhưng vẫn hardcode theo yêu cầu
        return ChatGoogleGenerativeAI(model="gemini-3.1-flash-lite-preview")
    elif "GPT-5.4 mini" in model_tier:
        return ChatOpenAI(model="gpt-5.4-mini")
    elif "Claude 4.5 Haiku" in model_tier:
        return ChatAnthropic(model="claude-4.5-haiku")
    else:
        # Dự phòng
        return ChatOpenAI(model="gpt-4o-mini")


def ask_rag(
    job_app_id: int, hr_id: int, model_tier: str, chat_history: list, new_prompt: str
) -> str:
    start_time = time.time()

    try:
        # 1. Nhúng câu prompt (Embed)
        query_vector = get_query_embedding(new_prompt)

        # 2. Tìm kiếm Vector (Top K)
        top_k = int(os.getenv("TOP_K_CHUNKS", 3))
        chunks = db.search_document_chunks(job_app_id, query_vector, top_k)

        context_text = "\n\n".join(
            [f"[Source chunk {i+1}]: {c['content']}" for i, c in enumerate(chunks)]
        )
        if not chunks:
            context_text = "Không tìm thấy dữ liệu CV nào trong hệ thống Vector."

        # 3. Chạy qua RAG pipeline
        llm = get_llm(model_tier)

        system_prompt = f"""Bạn là trợ lý AI HR giỏi nhất. Dưới đây là thông tin về ứng viên từ cơ sở dữ liệu Vector RAG (dựa trên CV của họ):
{context_text}

HÃY PHÂN TÍCH THEO CHUẨN NGHIỆP VỤ NHÂN SỰ VÀ TRẢ LỜI CÂU HỎI SAU:"""

        messages = [SystemMessage(content=system_prompt)]

        # Build chat history
        for msg in chat_history:
            if msg["role"] == "user":
                messages.append(HumanMessage(content=msg["content"]))
            elif msg["role"] == "assistant":
                messages.append(AIMessage(content=msg["content"]))

        # Append latest prompt
        messages.append(HumanMessage(content=new_prompt))

        # Invoke LLM
        res = llm.invoke(messages)
        response_text = res.content

    except Exception as e:
        response_text = f"❌ Lỗi khi gọi Model [{model_tier}]: {str(e)}"

    # Đo thời gian
    latency = int((time.time() - start_time) * 1000)

    # 4. Lưu lại Log (Ghi đè DB)
    try:
        db.log_ai_query(job_app_id, hr_id, new_prompt, response_text, top_k, latency)
    except Exception as e:
        print(f"Error logging to AIQUERYLOG: {e}")

    return response_text
