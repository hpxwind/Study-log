import os
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

API_KEY = os.getenv("LLM_API_KEY")
BASE_URL = os.getenv("LLM_BASE_URL")
MODEL_NAME = os.getenv("LLM_MODEL_NAME")

_client = OpenAI(
    api_key=API_KEY,
    base_url=BASE_URL
)


def chat(system_prompt: str, user_input: str) -> str:
    """
    大模型同步对话接口
    :param system_prompt: 系统提示词（角色设定）
    :param user_input: 用户输入内容
    :return: 模型完整回复文本
    """
    # 参数合法性校验
    if not API_KEY:
        raise ValueError("LLM_API_KEY 未配置，请检查 .env 文件")
    if not BASE_URL:
        raise ValueError("LLM_BASE_URL 未配置，请检查 .env 文件")
    if not MODEL_NAME:
        raise ValueError("LLM_MODEL_NAME 未配置，请检查 .env 文件")

    response = _client.chat.completions.create(
        model=MODEL_NAME,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_input}
        ],
        temperature=0.7,
        stream=False
    )

    return response.choices[0].message.content.strip()