from langchain_ollama import OllamaLLM
from langchain.callbacks.manager import CallbackManager
from langchain.callbacks.streaming_stdout import StreamingStdOutCallbackHandler

callback_manager = CallbackManager([StreamingStdOutCallbackHandler()])

llm = OllamaLLM(
    model="llama3.2",
    callback_manager=callback_manager,
    base_url="http://localhost:11434",
    temperature=0.7
)

while True:
    user_input = input("\nEnter your question: ").strip()
    if user_input.lower() in ['exit', 'quit']:
        print("\nSee you！")
        break
    if not user_input:
        print("Please enter a valid prompt!")
        continue
    try:
        response = llm.invoke(user_input)
    except Exception as e:
        print(f"\nError Detected: {str(e)}")
        print("Please check if Ollama is running properly and try again.")
        continue
