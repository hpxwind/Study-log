import os
from dotenv import load_dotenv
from openai import OpenAI

# 加载.env
load_dotenv()

# 初始化客户端
client = OpenAI(
    api_key=os.getenv("LLM_API_KEY"),
    base_url=os.getenv("LLM_BASE_URL")
)
MODEL_NAME = os.getenv("LLM_MODEL")

def chat_completion(messages, tools=None):
    """
    调用大模型接口，支持传入tools函数定义
    :param messages: 对话上下文列表
    :param tools: 工具schema数组
    :return: openai返回完整response对象
    """
    kwargs = {
        "model": MODEL_NAME,
        "messages": messages,
    }
    # 有工具定义才带上tools参数
    if tools:
        kwargs["tools"] = tools
        kwargs["tool_choice"] = "auto"

    resp = client.chat.completions.create(**kwargs)
    return resp