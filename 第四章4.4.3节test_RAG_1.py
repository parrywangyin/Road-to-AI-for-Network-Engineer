import pandas as pd
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.vectorstores import FAISS
from langchain_ollama import OllamaLLM
from langchain.callbacks.manager import CallbackManager
from langchain.callbacks.streaming_stdout import StreamingStdOutCallbackHandler

callback_manager = CallbackManager([StreamingStdOutCallbackHandler()])
llm = OllamaLLM(
    model="llama3.2",
    callback_manager=callback_manager,
    base_url="http://localhost:11434",
)

#步骤 1：构建本地知识库
df = pd.read_excel("test_inventory.xlsx")
documents = [f"Hostname: {row['Hostname']}, Model: {row['Model']}, IP: {row['IP']}, Serial Number: {row['Serial Number']}" for index, row in df.iterrows()]
embedding_model = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")
embeddings = embedding_model.embed_documents(documents)
print(f"步骤1完成：生成了{len(embeddings)}个向量")

#步骤 2：构建向量数据库
vector_store = FAISS.from_texts(documents, embedding_model)
vector_store.save_local("faiss_index")
vector_store = FAISS.load_local("faiss_index", embedding_model, allow_dangerous_deserialization=True)
print("步骤2完成：向量数据库已保存到 faiss_index并已加载完毕")

# 步骤 3：用户向LLM输入查询
while True:
    user_input = input("\nEnter your question: ").strip()
    if user_input.lower() in ['exit', 'quit']:
        print("\nSee you!")
        break
    if not user_input:
        print("Please enter a valid prompt!")
        continue
    print(f"步骤3完成：用户查询为 '{user_input}'")
        
    #步骤 4：查询向量化
    try:
        query_embedding = embedding_model.embed_query(user_input)
        print("步骤4完成：查询已转换为向量")

        #步骤 5：语义相似性检索
        retrieved_docs = vector_store.similarity_search(user_input, k=1)  
        retrieved_texts = [doc.page_content for doc in retrieved_docs]
        print("步骤5完成：检索到以下相关文档：")
        for text in retrieved_texts:
            print(text)

        #步骤 6：生成回答
        prompt = f"根据以下上下文回答用户的查询。\n查询：{user_input}\n上下文：{' '.join(retrieved_texts)}\n回答："
        llm.invoke(prompt)  
        print("\n步骤6完成：回答已生成")

    except Exception as e:
        print(f"\nError Detected: {str(e)}")
        print("Please check if Ollama is running properly and try again.")
        continue
