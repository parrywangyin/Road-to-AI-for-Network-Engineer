from netmiko import ConnectHandler
from langchain.prompts import PromptTemplate
from langchain_openai import ChatOpenAI
from langchain_core.runnables import RunnableLambda
import time

openai_api_key = "这里放个人的OpenAI API key"
USERNAME = "这里放个人SSH登录交换机的username"
PASSWORD = "这里放个人SSH登录交换机的password"

def clean_response(response):
    return response.strip().replace("\r", "")

def run_commands_on_router(device_ip, username, password, commands):
    try:
        print(f"Connecting to {device_ip}...")
        device = {
            "device_type": "cisco_ios",
            "ip": device_ip,
            "username": username,
            "password": password,
            "session_log": "netmiko_session.log"
        }
        with ConnectHandler(**device) as ssh_conn:
            results = []
            cleaned_commands = [cmd.replace("run ", "").replace("execute ", "").strip() for cmd in commands]
            for command in cleaned_commands:
                print(f"Running command: {command}")
                output = ssh_conn.send_command(
                    command, expect_string=r"#", read_timeout=10
                )
                cleaned_output = clean_response(output)
                results.append(f"\n=== Output for '{command}' ===\n{cleaned_output}")
            return "\n".join(results)
    except Exception as e:
        return f"Error: {str(e)}"

#Troubleshoot interfaces for discards and errors and apply fixes as needed.
def troubleshoot_interfaces(device_ip, username, password, interfaces):
    try:
        print(f"Connecting to {device_ip} for troubleshooting...")
        device = {
            "device_type": "cisco_ios",
            "ip": device_ip,
            "username": username,
            "password": password,
        }
        with ConnectHandler(**device) as ssh_conn:
            for interface in interfaces:
                print(f"Checking interface {interface}...")
                #Step 1: Check the interface for output drops and CRC errors
                command = f"show int {interface} | in (output drops|CRC)"
                output = ssh_conn.send_command(command)
                cleaned_output = clean_response(output)
                print(f"Output for {interface}:\n{cleaned_output}")

                if "output drops" in cleaned_output:
                    if "0 input errors" in cleaned_output and "0 CRC" in cleaned_output:
                        #Step 2a: Maximize the output buffer
                        ssh_conn.send_config_set([f"interface {interface}", "hold-queue 4096 out"])
                        print(f"Configured hold-queue 4096 out on {interface}.")
                        #Step 2b: Clear counters with confirmation
                        clear_command = f"clear counters {interface}"
                        clear_output = ssh_conn.send_command_timing(clear_command)
                        if "[confirm]" in clear_output:
                            ssh_conn.send_command_timing("\n")
                        print(f"Cleared counters for {interface}.")
                    else:
                        #Step 3: Perform cable diagnostics
                        ssh_conn.send_config_set([f"interface {interface}", "hold-queue 4096 out"])
                        print(f"Configured hold-queue 4096 on {interface}.")
                        clear_command = f"clear counters {interface}"
                        clear_output = ssh_conn.send_command_timing(clear_command)
                        if "[confirm]" in clear_output:
                            ssh_conn.send_command_timing("\n")
                        print(f"Cleared counters for {interface}.")

                        print(f"Running cable diagnostics on {interface}...")
                        tdr_command = f"show cable-diagnostics tdr interface {interface}"
                        tdr_output = ssh_conn.send_command_timing(tdr_command)

                        # Handle the confirmation prompt
                        if "Are you sure you want to proceed? ? [yes/no]:" in tdr_output:
                            tdr_output += ssh_conn.send_command_timing("yes", read_timeout=10)

                        # Wait for the test to complete
                        time.sleep(3)

                        # Retrieve the diagnostics result
                        tdr_result = ssh_conn.send_command(f"show cable-diagnostics tdr interface {interface}")
                        cleaned_tdr_output = clean_response(tdr_result)
                        print(f"Cable diagnostics result for {interface}:\n{cleaned_tdr_output}")

                        if "Pair status" in cleaned_tdr_output and "Normal" not in cleaned_tdr_output:
                            print(f"Faulty cable detected on {interface}, please replace the cable.")
                        else:
                            print(
                                f"Cable of {interface} is in good condition, keep monitoring the input error/CRC error.")
    except Exception as e:
        print(f"Error during troubleshooting: {str(e)}")

llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.3, openai_api_key=openai_api_key)

prompt = PromptTemplate(
    input_variables=["user_query"],
    template="""
    You are a network assistant. Parse the user's query to extract the following:
    1. The device IP address
    2. The interfaces to check (one per line)

    Ignore unnecessary words like 'run', 'execute', or 'please' if they are part of the command.

    Query: "{user_query}"

    Response Format:
    Device IP: <router_ip>
    Interfaces: <interface1>, <interface2>, ...
    """
)

parse_chain = RunnableLambda(
    lambda inputs: llm.invoke(prompt.format(user_query=inputs["user_query"]))
)

def process_query(user_query, username, password):
    print("Parsing user query...")
    parsed_response = parse_chain.invoke({"user_query": user_query})
    parsed_content = clean_response(parsed_response.content) 
    print("Parsed Response:\n", parsed_content)

    device_ips, interfaces = [], []
    for line in parsed_content.splitlines():
        if line.startswith("Device IP:"):
            device_ips = [ip.strip() for ip in line.split("Device IP:")[1].split(",")]
        elif line.startswith("Interfaces:"):
            interfaces = [iface.strip() for iface in line.split("Interfaces:")[1].split(",")]
            
    if not device_ips:
        return "Could not parse the query. Ensure you specify at least one device IP."

    results = []

    for device_ip in device_ips:
        if interfaces and interfaces[0] != "N/A":
            result = troubleshoot_interfaces(device_ip, username, password, interfaces)
        else:
            result = run_commands_on_router(device_ip, username, password, ["show clock"])
        results.append(f"Results for {device_ip}:\n{result}")

    return "\n".join(results)

if __name__ == "__main__":
    print("\n=== LLM-Powered Network Troubleshooting ===\n")
    while True:
        # Example user query
        user_query = input("Enter your query (e.g., 'Please check discards/errors for interface gix/x/x of switch 172.16.x.x' ) or type 'exit' to quit: ")
        if user_query.lower() == 'exit':
            print("Exiting... Goodbye!")
            break
        output = process_query(user_query, USERNAME, PASSWORD)
        print("\n=== Result ===")
        print(output)
