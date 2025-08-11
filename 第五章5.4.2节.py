import subprocess
import re
from mcp.server.fastmcp import FastMCP
from mcp.server.fastmcp.prompts import base
from netmiko import ConnectHandler

mcp = FastMCP("Network Engineer Toolkit", dependencies=["netmiko"])

def create_netmiko_connection(ip_address):
    device = {
        "device_type": "cisco_ios",
        "host": ip_address,
        "username": "这里放个人的username",
        "password": "这里放个人的password",
    }
    return ConnectHandler(**device)

@mcp.tool
def get_device_config(ip_address):
    try:
        with create_netmiko_connection(ip_address) as conn:
            config = conn.send_command("show running-config")
            return config
    except Exception as e:
        return f"Error retrieving configuration for {ip_address}: {str(e)}"

@mcp.tool()
def ping_host(host, count=4):
    try:
        cmd = f"ping -n {count} {host}"
        result = subprocess.run(
            cmd,
            shell=True,
            capture_output=True,
            text=True,
            timeout=10
        )
        output = result.stdout
        packets = re.search(r"Sent = (\d+), Received = (\d+), Lost = (\d+)", output)
        if packets:
            sent, received, lost = packets.groups()
            loss = (int(lost) / int(sent)) * 100
            return f"Ping results for {host}:\n{output}\nPacket loss: {loss:.1f}%"
        return f"Ping results for {host}:\n{output}"
    except subprocess.TimeoutExpired:
        return f"Error: Ping to {host} timed out"
    except Exception as e:
        return f"Error pinging {host}: {str(e)}"

@mcp.tool()
def get_interface_status(ip_address, interface):
    try:
        with create_netmiko_connection(ip_address) as conn:
            status = conn.send_command(f"show interfaces {interface}")
            return f"Interface {interface} status on {ip_address}:\n{status}"
    except Exception as e:
        return f"Error retrieving interface status for {ip_address}: {str(e)}"

@mcp.prompt()
def document_network(ip_address, ctx):
    config = get_device_config(ip_address, ctx)
    return [
        base.UserMessage(f"Create documentation for device at {ip_address}"),
        base.UserMessage(f"Configuration:\n{config}"),
        base.AssistantMessage(
            "I'll help create structured documentation. What specific aspects would you like to document? (e.g., interfaces, routing, VLANs)")
    ]

if __name__ == "__main__":
    mcp.run()
