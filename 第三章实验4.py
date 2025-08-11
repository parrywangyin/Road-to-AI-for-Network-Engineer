from netmiko import ConnectHandler
from langchain.prompts import PromptTemplate
from langchain_openai import ChatOpenAI
from langchain_core.runnables import RunnableLambda

OPENAI_API_KEY = "这里放个人的OpenAI API key"
USERNAME = "这里放个人SSH登录交换机的username"
PASSWORD = "这里放个人SSH登录交换机的password"

def run_command_on_switch(device_ip, username, password, commands):
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
                results.append(f"\n=== Output for '{command}' ===\n{output}")
            return "\n".join(results)
    except Exception as e:
        return f"Error: {str(e)}"

llm = ChatOpenAI(model="gpt-3.5-turbo", temperature = 0.3, openai_api_key=OPENAI_API_KEY)

prompt = PromptTemplate(
    input_variables=["user_query"],
    template="""
    You are a network assistant. Parse the user's query to extract the following:
    1. The commands to run on the switch (multiple commands separated by commas)
    2. The IP address of the switch

    Query: "{user_query}"

    Response Format:
    Commands: <command1>, <command2>, ...
    IP: <switch_ip>
    """
)

parse_chain = RunnableLambda(
    lambda inputs: llm.invoke(prompt.format(user_query=inputs["user_query"]))
)

#Define a function that counts the number of 'up' and 'down' interfaces in the output of 'show ip int brief'."""
def count_interfaces(output):
    up_count = 0
    down_count = 0
    for line in output.splitlines():
        parts = line.split()
        if len(parts) >= 6:
            if parts[4].lower() == 'up' and parts[5].lower() == 'up':
                up_count += 1
            elif parts[4].lower() == 'down' and parts[5].lower() == 'down':
                down_count += 1
    return up_count, down_count

def process_query(user_query, username, password):
    # Step 1: Parse the query using LLM
    print("Parsing user query...")
    parsed_response = parse_chain.invoke({"user_query": user_query})
    parsed_content = parsed_response.content
    print("Parsed Response:\n", parsed_content)

    commands, device_ip = None, None
    for line in parsed_content.splitlines():
        if line.startswith("Commands:"):
            commands = [cmd.strip() for cmd in line.split("Commands:")[1].split(",")]
        elif line.startswith("IP:"):
            device_ip = line.split("IP:")[1].strip()

    if not commands or not device_ip:
        return "Could not parse the query. Ensure you specify commands and device IP."

    # Step 2: Run the commands on the switch
    print(f"Executing commands {commands} on device {device_ip}...")
    result = run_command_on_switch(device_ip, username, password, commands)

    # Step 3: Post-process the output if 'show ip int brief' was run
    if "show ip int brief" in commands:
        up_count, down_count = count_interfaces(result)
        result += f"\n\nNumber of interfaces that are 'up': {up_count}"
        result += f"\nNumber of interfaces that are 'down': {down_count}"
    return result

if __name__ == "__main__":
    print("\n=== LLM-Powered Network Automation ===\n")
    while True:
        user_query = input("Enter your query or type 'exit' to quit: ")
        if user_query.lower() == 'exit':
            print("Exiting... Goodbye!")
            break
        output = process_query(user_query, USERNAME, PASSWORD)
        print("\n=== Command Output ===")
        print(output)
