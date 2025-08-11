from langchain.prompts import PromptTemplate
import httpx

BASE_URL = "http://xx.xx.xx.xx:8000" 
API_TOKEN = "这里放个人用secrets生成的API Token"

prompt_template = PromptTemplate(
    input_variables=["user_input"],
    template="{user_input}"
)

while True:
    user_input = input("Enter your prompt: ")
    formatted_prompt = prompt_template.format(user_input=user_input)
    headers = {"X-API-Key": API_TOKEN}
    payload = {
        "model": "llama3.2",
        "messages": [{"role": "user", "content": formatted_prompt}],
        "stream": True
    }

    with httpx.stream("POST", f"{BASE_URL}/chat/completions", json=payload, headers=headers) as response:
        for line in response.iter_lines():
            if line.startswith("data: ") and line != "data: [DONE]":
                print(line[6:], end="", flush=True)  # Print each chunk without "data: "
        print() 
