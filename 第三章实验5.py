from netmiko import ConnectHandler
from langchain.prompts import PromptTemplate
from langchain_openai import ChatOpenAI
from langchain_core.runnables import RunnableLambda

OPENAI_API_KEY = "这里放个人的OpenAI API key"
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
            results = {}
            for command in commands:
                print(f"Running command: {command}")
                output = ssh_conn.send_command(command)
                results[command] = output
            return results
    except Exception as e:
        return {"Error": str(e)}

llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.3, openai_api_key=OPENAI_API_KEY)

#Define a prompt template to request LLM to analyze the switch logs and provide suggestions.
analysis_prompt = PromptTemplate(
    input_variables=["logs"],
    template="""
    You are a network expert. Analyze the following switch logs and provide insights or recommendations:

    Logs:
    {logs}

    Suggestions should include potential issues, resolutions, and any optimization opportunities.
    """
)

def analyze_logs_with_llm(logs):
    try:
        print("Analyzing logs with LLM...")
        analysis_results = []
        response = llm.invoke(analysis_prompt.format(logs=logs))
        if hasattr(response, 'content'):
            analysis_results.append(response.content)
        else:
            analysis_results.append(str(response))
        return "\n\n".join(analysis_results)
    except Exception as e:
        return f"Error in log analysis: {str(e)}"

parse_prompt = PromptTemplate(
    input_variables=["user_query"],
    template="""
    You are a network assistant. Parse the user's query to extract the following:
    1. The commands to run on the switch (multiple commands separated by commas)
    2. The IP address of the switch
    3. Whether the user requested log analysis

    Ignore unnecessary words like 'run', 'execute', or 'please' if they are part of the command.
    Query: "{user_query}"

    Response Format:
    Commands: <command1>, <command2>, ...
    IP: <switch_ip>
    Analyze Logs: <yes/no>
    """
)

parse_chain = RunnableLambda(
    lambda inputs: llm.invoke(parse_prompt.format(user_query=inputs["user_query"]))
)

def process_query(user_query, username, password):
    print("Parsing user query...")
    parsed_response = parse_chain.invoke({"user_query": user_query})
    parsed_content = parsed_response.content
    print("Parsed Response:\n", parsed_content)
    commands, device_ip, analyze_logs = None, None, "no"
    for line in parsed_content.splitlines():
        if line.startswith("Commands:"):
            commands = [cmd.strip() for cmd in line.split("Commands:")[1].split(",")]
        elif line.startswith("IP:"):
            device_ip = line.split("IP:")[1].strip()
        elif line.startswith("Analyze Logs:"):
            analyze_logs = line.split("Analyze Logs:")[1].strip().lower()

    cleaned_commands = [cmd.replace("run ", "").replace("execute ", "").strip() for cmd in commands]

    if not cleaned_commands or not device_ip:
        return "Could not parse the query. Ensure you specify commands and device IP."

    print(f"Executing commands {cleaned_commands} on device {device_ip}...")
    command_results = run_commands_on_switch(device_ip, username, password, cleaned_commands)

    if "Error" in command_results:
        return command_results["Error"]

    logs_output = "\n".join(command_results.get(cmd, "") for cmd in cleaned_commands if "log" in cmd)

    if logs_output and analyze_logs == "yes":
        analysis = analyze_logs_with_llm(logs_output)
        return analysis

    return "\n".join(f"=== Output for '{cmd}' ===\n{output}" for cmd, output in command_results.items())

if __name__ == "__main__":
    print("\n=== LLM-Powered Network Automation ===\n")
    while True:
        user_query = input("Enter your query (e.g., 'Run show log on 192.168.1.1') or type 'exit' to quit: ")
        if user_query.lower() == 'exit':
            print("Exiting... Goodbye!")
            break

        output = process_query(user_query, USERNAME, PASSWORD)

        print("\n=== Output ===")
        print(output)
