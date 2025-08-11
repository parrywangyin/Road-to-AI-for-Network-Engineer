from netmiko import ConnectHandler
from langchain.prompts import PromptTemplate
from langchain_openai import ChatOpenAI
from langchain_core.runnables import RunnableLambda

OPENAI_API_KEY = "这里放个人的OpenAI API key"
USERNAME = "这里放个人SSH登录交换机的username"
PASSWORD = "这里放个人SSH登录交换机的password"

def run_commands_on_switch(device_ip, username, password, command):
    try:
        print(f"Connecting to {device_ip}...")
        device = {
            "device_type": "cisco_ios",
            "ip": device_ip,
            "username": username,
            "password": password,
        }
        with ConnectHandler(**device) as ssh_conn:
            print(f"Running command: {command}")
            output = ssh_conn.send_command(command)
            return f"\n=== Output for '{command}' ===\n{output}"
    except Exception as e:
        return f"Error: {str(e)}"

llm = ChatOpenAI(model="gpt-4o-mini", openai_api_key=OPENAI_API_KEY)

prompt = PromptTemplate(
    input_variables=["user_query"],
    template="""

    You are a network assistant. Parse the user's query to extract the following:
    1. The command to run on the switch
    2. The IP address of the switch

    Query: "{user_query}"
    Response Format:
    Command: <command>
    IP: <switch_ip>
    """
)

parse_chain = RunnableLambda(
    lambda inputs: llm.invoke(prompt.format(user_query=inputs["user_query"]))
)

#Process a user query, parse it, connect to the switch and run the commands.
def process_query(user_query, username, password):
    #Step 1: Parse the query using LLM
    print("Parsing user query...")
    parsed_response = parse_chain.invoke({"user_query": user_query})
    parsed_content = parsed_response.content  
    print("Parsed Response:\n", parsed_content)

    command, device_ip = None, None
    for line in parsed_content.splitlines():
        if line.startswith("Command:"):
            command = line.split("Command:")[1].strip()
        elif line.startswith("IP:"):
            device_ip = line.split("IP:")[1].strip()

    if not command or not device_ip:
        return "Could not parse the query. Ensure you specify a command and device IP."

    #Step 2: Run the command on the switch
    print(f"Executing command '{command}' on device {device_ip}...")
    result = run_command_on_switch(device_ip, username, password, command)
    return result

if __name__ == "__main__":
    print("\n=== LLM-Powered Network Automation ===\n")
    while True:
        user_query = input("Enter your query (e.g., 'Run show version on 172.16.x.x') or type 'exit' to quit: ")
        if user_query.lower() == 'exit':
            print("Exiting... Goodbye!")
            break
        output = process_query(user_query, USERNAME, PASSWORD)
        print("\n=== Command Output ===")
        print(output)
