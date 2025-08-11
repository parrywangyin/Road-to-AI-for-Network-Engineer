from netmiko import ConnectHandler
from langchain.prompts import PromptTemplate
from langchain_openai import ChatOpenAI
from langchain_core.runnables import RunnableLambda

openai_api_key = "这里放个人的OpenAI API key"
USERNAME = "这里放个人SSH登录交换机的username"
PASSWORD = "这里放个人SSH登录交换机的password"

def run_commands_on_switch(device_ip, username, password, commands):
    try:
        print(f"Connecting to {device_ip}...")
        device = {
            "device_type": "cisco_ios",
            "ip": device_ip,
            "username": username,
            "password": password,
        }
        with ConnectHandler(**device) as ssh_conn:
            results = []
            for command in commands:
                print(f"Running command: {command}")
                output = ssh_conn.send_command(command)
                results.append(f"\n=== Output for '{command}' on {device_ip} ===\n{output}")
            return "\n".join(results)
    except Exception as e:
        return f"Error: {str(e)}"

llm = ChatOpenAI(model="gpt-4o-mini", openai_api_key=openai_api_key)

prompt = PromptTemplate(
    input_variables=["user_query", "file_content"],
    template="""
    You are a network assistant. Process the user's query to determine:
    1. If the query is related to '9300 switch'.
    2. If yes, read the provided content of the file '9300.txt' and extract all switch IPs. Extract only the exact    Cisco command(s) the user wants to run (without extra words like 'on 9300 switches').
    3. If not, parse the query to extract the following:
       a. The commands to run on the switch (multiple commands separated by commas).
       b. The IP address of the switch.

    Ignore unnecessary words like 'run', 'execute', or 'please' if they are part of the command.

    File Content:
    {file_content}

    Query: "{user_query}"

    Response Format:
    If related to '9300 switch':
    9300 Switches: <comma-separated list of IPs from the file>

    Otherwise:
    Commands: <command1>, <command2>, ...
    IP: <switch_ip>
    """
)


parse_chain = RunnableLambda(
    lambda inputs: llm.invoke(prompt.format(user_query=inputs["user_query"], file_content=inputs["file_content"]))
)

def process_query(user_query, username, password):
    # Step 1: Read the file content
    try:
        with open("9300.txt", "r") as file:
            file_content = file.read()
    except FileNotFoundError:
        return "Error: '9300.txt' file not found. Please provide the file with switch IP addresses."

    # Step 2: Parse the query using LLM
    print("Parsing user query...")
    parsed_response = parse_chain.invoke({"user_query": user_query, "file_content": file_content})
    parsed_content = parsed_response.content
    print("Parsed Response:\n", parsed_content)

    # Check if the query is related to '9300 switch'
    if "9300 Switches:" in parsed_content:
        ips_line = parsed_content.split("9300 Switches:")[1].strip()
        switch_ips = [ip.strip() for ip in ips_line.split(",") if ip.strip()]
        
        # 获取用户输入的命令
        command_line = [line for line in parsed_content.splitlines() if line.startswith("Commands:")]
        commands = [cmd.strip() for cmd in command_line[0].split("Commands:")[1].split(",")] if command_line else ["show clock"]

        if not switch_ips:
            return "Error: No valid IP addresses found for 9300 switches."

        results = []
        for ip in switch_ips:
            print(f"Processing switch {ip}...")
            result = run_commands_on_switch(ip, username, password, commands)  # 动态执行用户命令
            results.append(result)

        return "\n\n".join(results)

    # Otherwise, process as a general query
    commands, device_ip = None, None
    for line in parsed_content.splitlines():
        if line.startswith("Commands:"):
            commands = [cmd.strip() for cmd in line.split("Commands:")[1].split(",")]
        elif line.startswith("IP:"):
            device_ip = line.split("IP:")[1].strip()

    if not commands or not device_ip:
        return "Could not parse the query. Ensure you specify commands and device IP."

    # Step 3: Run the commands on the switch
    cleaned_commands = [cmd.replace("run ", "").replace("execute ", "").strip() for cmd in commands]
    print(f"Executing commands {cleaned_commands} on device {device_ip}...")
    result = run_commands_on_switch(device_ip, username, password, cleaned_commands)
    return result

if __name__ == "__main__":
    print("\n=== LLM-Powered Network Automation ===\n")
    while True:
        user_query = input("Enter your query (e.g., 'Run show version on 172.16.x.x') or type 'exit' to quit: ")
        if user_query.lower() == "exit":
            print("Exiting... Goodbye!")
            break
        output = process_query(user_query, USERNAME, PASSWORD)
        print("\n=== Command Output ===")
        print(output)
