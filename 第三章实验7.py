from netmiko import ConnectHandler
from langchain.prompts import PromptTemplate
from langchain_openai import ChatOpenAI

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
            # Enter configuration mode once
            output = ssh_conn.config_mode()
            results.append(f"Entering configuration mode:\n{output}")

            # Execute all commands in the same configuration session
            output = ssh_conn.send_config_set(commands)
            results.append(f"Configuration output:\n{output}")

            # Exit configuration mode
            output = ssh_conn.exit_config_mode()
            results.append(f"Exiting configuration mode:\n{output}")

            return "\n".join(results)
    except Exception as e:
        return f"Error: {str(e)}"


llm = ChatOpenAI(model="gpt-4o-mini", openai_api_key=openai_api_key)

# Prompt template for generating Cisco IOS-XE commands
generate_commands_prompt = PromptTemplate(
    input_variables=["user_request"],
    template="""
    You are a Cisco network configuration expert. Generate the appropriate Cisco IOS-XE commands for the following request:

    Request: {user_request}

    Important rules:
    1. Do not include 'configure terminal' or 'end' commands
    2. Provide only the exact commands needed, one per line
    3. Keep commands that should be executed in the same context together (e.g., 'vlan 100' followed by 'name test')
    4. Do not include any Markdown code blocks or backticks

    Generate only the commands:
    """
)

# Prompt template for parsing implementation requests
implement_prompt = PromptTemplate(
    input_variables=["user_query"],
    template="""
    You are a network assistant. Parse the implementation request to extract the following:
    1. The IP address of the switch where the commands should be implemented

    Query: "{user_query}"
    Response Format:
    IP: <switch_ip>
    """
)


def generate_config_commands(user_request):
    """Generate configuration commands using LLM"""
    response = llm.invoke(generate_commands_prompt.format(user_request=user_request))
    #Clean up any potential markdown or extra whitespace
    commands = [cmd.strip() for cmd in response.content.strip().split('\n')]
    commands = [cmd for cmd in commands if cmd and not cmd.startswith('```') and not cmd.endswith('```')]
    return commands


def parse_implementation_request(user_query):
    """Parse the implementation request to get the target switch IP"""
    response = llm.invoke(implement_prompt.format(user_query=user_query))
    for line in response.content.splitlines():
        if line.startswith("IP:"):
            return line.split("IP:")[1].strip()
    return None


def process_query(user_query, username, password):
    if user_query.lower().startswith("implement"):
        # This is an implementation request
        device_ip = parse_implementation_request(user_query)
        if not device_ip:
            return "Could not parse the target switch IP address."

        # Get the last generated commands from the session
        if not hasattr(process_query, 'last_commands'):
            return "No commands have been generated yet. Please generate commands first."

        print(f"\nImplementing the following commands on {device_ip}:")
        for cmd in process_query.last_commands:
            print(f"- {cmd}")

        result = run_commands_on_switch(device_ip, username, password, process_query.last_commands)
        return result
    else:
        # This is a command generation request
        generated_commands = generate_config_commands(user_query)
        # Store the generated commands for later implementation
        process_query.last_commands = generated_commands
        return "\n=== Generated Commands ===\n" + "\n".join(generated_commands)


if __name__ == "__main__":
    print("\n=== LLM-Powered Network Configuration Assistant ===\n")
    print("Usage:")
    print("1. First, describe the configuration you want (e.g., 'create VLAN 100 named Test')")
    print("2. Review the generated commands")
    print("3. Type 'implement the commands on <switch-ip>' to execute the commands")
    print("4. Type 'exit' to quit\n")

    while True:
        user_query = input("\nEnter your request or type 'exit' to quit: ")
        if user_query.lower() == 'exit':
            print("Exiting... Goodbye!")
            break

        output = process_query(user_query, USERNAME, PASSWORD)
        print(output)
