from netmiko import ConnectHandler
from langchain_openai import ChatOpenAI
from langchain.tools import tool
from langchain.agents import AgentExecutor, create_react_agent
from langchain.prompts import PromptTemplate
import re

OPENAI_API_KEY = "这里放个人的OpenAI API Key"
llm = ChatOpenAI(model="gpt-4o-mini", openai_api_key=OPENAI_API_KEY)

def get_device_connection(ip):
    return {
        "device_type": "cisco_ios",
        "ip": ip,
        "username": "这里放个人的SSH用户名 ",
        "password": "这里放个人的SSH密码",
    }
@tool
def check_cpu_status(ip_address):
    """检查目标设备的CPU使用情况"""
    device_params = get_device_connection(ip_address)
    try:
        with ConnectHandler(**device_params) as connection:
            output = connection.send_command("show process cpu history")
            return f"CPU status for device {ip_address}:\n{output}"
    except Exception as e:
        return f"Error connecting to {ip_address}: {str(e)}"

@tool
def check_link_utilization(ip_and_interface):
    """检查目标设备指定接口的带宽使用情况。参数格式: 'IP地址 接口名称', 例如: '172.16.xx.xx gi1/0/x'"""
    parts = ip_and_interface.strip().split() 
    if len(parts) < 2:
        return "错误: 请同时提供IP地址和接口名称，以空格分隔。例如: '172.16.xx.xx gi1/0/x'"
    ip_address = parts[0].strip("'")
    interface = parts[1].strip("'")
    print(f"DEBUG: 连接到IP: '{ip_address}', 接口: '{interface}'")
    device_params = get_device_connection(ip_address)
    try:
        with ConnectHandler(**device_params) as connection:
            output = connection.send_command(f"show int {interface}")
            txload_match = re.search(r'txload (\d+)/(\d+)', output)
            rxload_match = re.search(r'rxload (\d+)/(\d+)', output)
            if txload_match and rxload_match:
                tx_value = int(txload_match.group(1))
                tx_max = int(txload_match.group(2))
                rx_value = int(rxload_match.group(1))
                rx_max = int(rxload_match.group(2))
                tx_percentage = (tx_value / tx_max) * 100
                rx_percentage = (rx_value / rx_max) * 100
                tx_result = f"{tx_percentage:.1f}%" if tx_percentage >= 1 else "小于1%"
                rx_result = f"{rx_percentage:.1f}%" if rx_percentage >= 1 else "小于1%"
                return f"设备 {ip_address} 的端口 {interface} 带宽使用情况：\n上行带宽为 {tx_result}\n下行带宽为 {rx_result}\n\n原始输出:\n{output}"
            else:
                return f"无法从输出中提取带宽信息\n\n原始输出:\n{output}"
    except Exception as e:
        return f"Error connecting to {ip_address} or checking interface {interface}: {str(e)}"

@tool
def analysis_syslog(ip_address):
    """分析目标设备的日志"""
    device_params = get_device_connection(ip_address)
    try:
        with ConnectHandler(**device_params) as connection:
            log_output = connection.send_command("show log last 10")
            analysis_prompt = f"""
            Please analyze the following network device logs and provide a summary of any notable events, errors, warnings or potential issues:{log_output}
            Provide a concise analysis focusing on actionable information.
            """
            analysis = llm.invoke(analysis_prompt)
            if hasattr(analysis, 'content'):
                analysis_text = analysis.content
            else:
                analysis_text = str(analysis)
            return f"设备 {ip_address} 的日志分析结果：\n{analysis_text}"
    except Exception as e:
        return f"Error connecting to {ip_address}: {str(e)}"

prompt_template = """
You are a network assistant specializing in Cisco device monitoring and troubleshooting.
Analyze user requests and use the appropriate tools to gather information from network devices.

When helping users, remember:
1. For CPU utilization queries, use the check_cpu_status tool
2. For link utilization queries, use the check_link_utilization tool with BOTH the IP address AND interface name
3. For log analysis requests, use the analysis_syslog tool
4. For general network performance issues (e.g., "why is the network slow?"), use all three tools and analyze the results

IMPORTANT: When users ask about link utilization, they will specify both an IP address and an interface.
You must extract BOTH and use them correctly with the tool.

DEFAULT SETTINGS:
- If user asks a general question about network slowness (like "why is the network slow?") without specifying devices:
  - Use IP address <ip_add> as the default device
  - Use interface <interface_id> as the default interface
  - Check CPU, link utilization, and logs on this default device

For example, if the user asks "what's the link utilization of gi1/0/1 on 172.16.1.1", you should:
- Extract IP address: 172.16.1.1
- Extract interface: gi1/0/1
- Use these with check_link_utilization tool: "172.16.1.1 gi1/0/1"

Available tools: {tools}
Use the following format:
User question: The input question you must answer	
Thought: Consider what tools would help answer this question and extract any IP addresses and interfaces
Action: The action to take, should be one of [{tool_names}]
Action Input: The parameters to pass to the tool (make sure to include BOTH IP and interface for check_link_utilization)
Observation: The result of the action
Thought: I now have enough information to answer the user's question
... (this Thought/Action/Action Input/Observation can repeat multiple times)
Thought: I have collected all necessary data from the tools
Analysis: Analyze the tool outputs to determine possible reasons for the user's question (e.g., network slowness)
Final Answer: The final answer to the user's question, summarizing the tool output in a concise way
**IMPORTANT**:
- For general performance questions like "why is the network slow?", after collecting data from all three tools (CPU, link utilization, logs), analyze the outputs to identify potential causes of slowness (e.g., high CPU usage, link congestion, errors in logs).
- Once you have enough data to answer the question, provide the Analysis and Final Answer, then STOP. Do not repeat tool calls unnecessarily.

User question: {input}
{agent_scratchpad}
"""

prompt = PromptTemplate.from_template(prompt_template)
tools = [check_cpu_status, check_link_utilization, analysis_syslog]
agent = create_react_agent(llm, tools, prompt)

try:
    agent_executor = AgentExecutor(
        agent=agent,
        tools=tools,
        max_iterations=3,  
        verbose=True,  
        handle_parsing_errors = True
    )
except Exception as e:
    print(e)

def process_input(user_input):
    """处理用户输入，通过agent_executor调用agent来决定使用哪些工具"""
    try:
        # 直接将用户输入传递给agent_executor
        result = agent_executor.invoke({"input": user_input})
        if isinstance(result, dict) and "output" in result:
            return result["output"]
        else:
            return str(result)
    except Exception as e:
        return f"无法处理请求: {str(e)}\n请尝试明确指定您想查询的内容（例如CPU使用率、链路利用率或日志分析），并确保包含必要的IP地址和接口信息（如果适用）。"

while True:
    try:
        user_input = input("\nEnter your question: ").strip()
        if user_input.lower() in ['exit', 'quit']:
            print("\nBye!")
            break
        if not user_input:
            print("Please enter a valid prompt!")
            continue
        result = process_input(user_input)
        print("\n", result)
    except KeyboardInterrupt:
        print("\n程序被用户中断")
        break
    except Exception as e:
        print(f"\n发生错误: {str(e)}")
