from fastapi import FastAPI, HTTPException, Depends
from fastapi.security import APIKeyHeader
from fastapi.responses import StreamingResponse
from langchain_ollama import OllamaLLM
from langchain.callbacks.manager import CallbackManager
from langchain.callbacks.streaming_stdout import StreamingStdOutCallbackHandler
import uvicorn
from pydantic import BaseModel
from typing import List, Optional

#初始化FastAPI，设置要验证的API Token 
app = FastAPI()
VALID_API_TOKEN = "这里放个人用secrets生成的API Token"
#指定客户端使用API密钥（即API Token），并且需要客户端在HTTP头部设置”X-API-Key”这个字段
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)

#创建异步验证API密钥的自定义函数
async def verify_api_key(api_key: str = Depends(api_key_header)):
    if api_key != VALID_API_TOKEN:
        raise HTTPException(status_code=403, detail="Invalid API Token")
    return api_key

callback_manager = CallbackManager([StreamingStdOutCallbackHandler()])
llm = OllamaLLM(
    model="llama3.2",
    callback_manager=callback_manager,
    base_url="http://localhost:11434",
    temperature=0.7
)

#结构化定义消息格式
class ChatMessage(BaseModel):
    role: str
    content: str

#结构化定义请求体格式
class ChatCompletionRequest(BaseModel):
    model: str
    messages: List[ChatMessage]
    temperature: Optional[float] = 0.7 


#对客户端流式输出LLM的回复内容
def generate_stream(prompt):
    for chunk in llm.stream(prompt):
        yield f"data: {chunk}\n\n"
    yield "data: [DONE]\n\n"

@app.post("/chat/completions")
async def chat_completions(request: ChatCompletionRequest, api_key = Depends(verify_api_key)):
    try:
        prompt = next(msg.content for msg in request.messages if msg.role == "user")
        return StreamingResponse(generate_stream(prompt), media_type="text/event-stream")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")

uvicorn.run(app, host="这里放个人运行Ollama主机的IP地址", port=8000)
