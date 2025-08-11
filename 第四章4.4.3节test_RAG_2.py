import PyPDF2
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.vectorstores import FAISS
from langchain_ollama import OllamaLLM
from langchain.callbacks.manager import CallbackManager
from langchain.callbacks.streaming_stdout import StreamingStdOutCallbackHandler
from langchain.text_splitter import RecursiveCharacterTextSplitter

callback_manager = CallbackManager([StreamingStdOutCallbackHandler()])
llm = OllamaLLM(
    model="llama3.2",
    callback_manager=callback_manager,
    base_url="http://localhost:11434",
)

#步骤1：从PDF中提取文本并构建知识库
pdf_path = "test.pdf"
def extract_text_from_pdf(pdf_path):
    with open(pdf_path, 'rb') as file:
        pdf_reader = PyPDF2.PdfReader(file)
        text = ""
        for page in pdf_reader.pages:
            text += page.extract_text() or "" 
    return text
pdf_text = extract_text_from_pdf(pdf_path)

# 使用文本分割器将 PDF 内容分割成小块
text_splitter = RecursiveCharacterTextSplitter(
    chunk_size=1000,  # 每块大小为 1000 个字符，可根据需要调整
    chunk_overlap=200,  # 每块之间重叠 200 个字符以保留上下文
    length_function=len,
)
documents = text_splitter.split_text(pdf_text)
print(f"步骤1完成：从PDF 中生成了 {len(documents)} 个文本块")

embedding_model = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")
embeddings = embedding_model.embed_documents(documents)
print(f"生成了 {len(embeddings)} 个向量")

#步骤2：构建向量数据库并加载
vector_store = FAISS.from_texts(documents, embedding_model)
vector_store.save_local("faiss_index")
vector_store = FAISS.load_local("faiss_index", embedding_model, allow_dangerous_deserialization=True)
print("步骤2完成：向量数据库已保存至faiss_index并加载完毕")

#步骤3：接收用户输入的查询
while True:
    user_input = input("\nEnter your question: ").strip()
    if user_input.lower() in ['exit', 'quit']:
        print("\nBye!")
        break
    if not user_input:
        print("Please enter a valid prompt!")
        continue
    print(f"步骤3完成：用户查询为 '{user_input}'")
    #步骤4：将查询转换为向量
    try:
        query_embedding = embedding_model.embed_query(user_input)
        print("步骤4完成：查询已转换为向量")
        #步骤5：执行语义相似性检索
        retrieved_docs = vector_store.similarity_search(user_input, k=4) 
        retrieved_texts = [doc.page_content for doc in retrieved_docs]
        print("步骤5完成：检索到以下相关文本块：")
        for i, text in enumerate(retrieved_texts, 1):
            print(f"文本块 {i}: {text[:200]}...")  # 打印每块前 200 个字符

        #步骤6：生成回答
        prompt = f"根据以下上下文回答用户的查询。\n查询：{user_input}\n上下文：{' '.join(retrieved_texts)}\n回答："
        llm.invoke(prompt)  
        print("\n步骤6完成：回答已生成")

    except Exception as e:
        print(f"\nError Detected: {str(e)}")
        print("Please check if Ollama is running properly and try again.")
        continue
