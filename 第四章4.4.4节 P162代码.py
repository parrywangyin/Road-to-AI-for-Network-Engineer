from langchain.tools import Tool
from langchain_ollama import OllamaLLM
from langchain.prompts import PromptTemplate
from langchain_core.runnables import RunnableSequence
from langchain.callbacks.manager import CallbackManager
from langchain.callbacks.streaming_stdout import StreamingStdOutCallbackHandler
import subprocess
import os
import re

callback_manager = CallbackManager([StreamingStdOutCallbackHandler()])
llm = OllamaLLM(
    model="llama3.2",
    callback_manager=callback_manager,
    base_url="http://localhost:11434",
)

#创建一个自定义函数用来执行ping命令
def check_device_status(ip_address):
    try:
        ping_command = ["ping", "-n" if os.name == "nt" else "-c", "4", ip_address]
        result = subprocess.run(ping_command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=10)
        if result.returncode == 0 and ("TTL=" in result.stdout or "ttl=" in result.stdout):
            return f"IP {ip_address} 可达，设备在线"
        else:
            return f"IP {ip_address} 不可达，设备可能离线"
    except subprocess.TimeoutExpired:
        return f"IP {ip_address} 检查超时，设备不可达"
    except Exception as e:
        return f"检查 IP {ip_address} 时出错: {str(e)}"

#将自定义函数封装为tool
check_device_status_tool = Tool(
    name="check_device_status",
    func=check_device_status,
    description="检查目标IP地址的可达性，返回设备是否在线"
)

prompt_template = PromptTemplate(
    input_variables=["input"],
    template="""
用户请求: {input}
你有一个工具可用：
- 工具名称: check_device_status
- 工具描述: 检查目标IP地址的可达性，返回设备是否在线。
如果用户请求中包含“ping”后跟一个IP地址（格式如“ping <IP地址>”），请严格返回格式为“[调用工具 check_device_status <IP>]”的文本，其中<IP>是用户提供的IP地址。
示例：
- 输入: ping 8.8.8.8
- 输出: [调用工具 check_device_status 8.8.8.8]
如果不涉及IP可达性，则直接简洁回答用户的问题，不要生成多余内容。
"""
)

chain = RunnableSequence(prompt_template | llm)

def process_input(user_input: str) -> str:
    response = chain.invoke({"input": user_input})
    # 匹配LLM响应的内容
    tool_pattern = r"\[调用工具 check_device_status (\d+\.\d+\.\d+\.\d+)\]"
    tool_match = re.search(tool_pattern, response)
    if tool_match:
        ip_address = tool_match.group(1)
        return check_device_status_tool.run(ip_address)
    # 如果 LLM 输出不符合预期，但包含 IP，尝试修复
    ip_pattern = r"(\d+\.\d+\.\d+\.\d+)"
    ip_match = re.search(ip_pattern, response)
    if ip_match and "ping" in user_input.lower():
        ip_address = ip_match.group(1)
        return check_device_status_tool.run(ip_address)
    return response

while True:
    user_input = input("\nEnter your question: ").strip()
    if user_input.lower() in ['exit', 'quit']:
        print("\nBye!")
        break
    if not user_input:
        print("Please enter a valid prompt!")
        continue
    result = process_input(user_input)
    print("\n", result)
