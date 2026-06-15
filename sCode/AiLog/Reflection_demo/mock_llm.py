"""
mock_llm.py — LLM API 适配器

【模块作用】
封装对 OpenAI 兼容 API（如 OpenAI / DeepSeek / 通义千问等）的 HTTP 调用，
提供统一的 generate(chat_history) -> str 接口，供 ReActAgentWithReflection 调用。
配置通过 .env 文件读取，支持不同的 API 提供商。

【被谁依赖】
- test_main.py → 创建 MockLLM() 实例，传入 ReActAgentWithReflection

【配置说明】
在项目根目录的 .env 文件中配置：
  LLM_API_KEY    = "sk-xxx"         # API 密钥
  LLM_BASE_URL   = "https://api.xxx.com/v1"  # API 基础 URL
  LLM_MODEL      = "gpt-4o-mini"   # 模型名称
  LLM_TEMPERATURE = "0.1"          # 生成温度（越低越确定性）
"""

import requests
import os
from dotenv import load_dotenv
from typing import List, Dict

# 加载 .env 环境变量——在模块导入时执行一次
load_dotenv()


class MockLLM:
    """
    OpenAI 兼容 API 适配器。

    【类作用】
    将 OpenAI Chat Completions API 封装为简单的 generate() 方法，
    接收对话历史列表，返回 LLM 生成的文本内容。
    所有 Agent 只需调用 generate() 即可获取 LLM 回复，无需关心 HTTP 细节。

    【为什么叫 MockLLM】
    历史命名——最初可能用于 mock 测试，后来改为调用真实 API。
    实际上这是一个真正的 LLM 客户端，不是 mock。
    """

    def __init__(self):
        """
        初始化 LLM 客户端，从环境变量读取配置。

        【参数】
        无显式参数，从 .env 文件读取：
        - LLM_API_KEY     : API 密钥，用于 Authorization 头
        - LLM_BASE_URL    : API 基础 URL，如 "https://api.openai.com/v1"
        - LLM_MODEL       : 模型名称，如 "gpt-4o-mini"
        - LLM_TEMPERATURE : 生成温度，默认 0.1（低温度 = 更确定的输出）

        【关键代码解析】
        self.headers = { "Authorization": f"Bearer {self.api_key}", ... }
          → 每次请求都携带 Bearer Token 认证
        """
        self.api_key = os.getenv("LLM_API_KEY")
        self.base_url = os.getenv("LLM_BASE_URL")
        self.model_name = os.getenv("LLM_MODEL")
        self.temperature = float(os.getenv("LLM_TEMPERATURE", "0.1"))

        # HTTP 请求头——Bearer Token 认证 + JSON 内容类型
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

    def generate(self, chat_history: List[Dict[str, str]]) -> str:
        """
        调用 LLM API 生成回复。

        【函数作用】
        将完整的对话历史发送给 LLM API，获取模型生成的回复文本。
        这是整个 Agent 系统中唯一与 LLM 交互的入口。

        【参数说明】
        - chat_history : 对话历史列表，格式为 [{"role": "system/user/assistant", "content": "..."}]
                         来源：ReActAgentWithReflection.chat_history
                         包含 system prompt、用户问题、历史 Thought/Action/Observation/Reflection

        【谁会调用】
        - core/react_agent.py → _generate_with_retry() 中调用：
          resp_text = self.llm.generate(self.chat_history)

        【返回值】
        str — LLM 生成的文本内容（已 strip）
              成功时返回模型回复文本，如 "Thought: 分析...\nAction: check_order(...)"
              失败时返回 "LLM API 请求失败: 错误信息"

        【关键代码解析】
        payload = { "model": ..., "messages": chat_history, "temperature": ..., "stream": False }
          → 构造 OpenAI Chat Completions API 的请求体
          → stream=False 表示同步请求，等待完整回复而非流式返回

        resp.raise_for_status()
          → HTTP 状态码非 2xx 时抛异常，被下方 except 捕获

        data["choices"][0]["message"]["content"].strip()
          → 从 API 响应中提取模型回复文本
          → choices[0] 取第一个候选回复（n=1 时只有一个）
          → message.content 取助手消息内容

        except Exception as e:
            return f"LLM API 请求失败: {str(e)}"
          → 所有异常统一返回错误字符串而非抛异常，
            让 Agent 循环不会被中断，LLM 可能在下一轮重试成功
        """
        # 构造 API 请求体
        payload = {
            "model": self.model_name,         # 使用的模型名称
            "messages": chat_history,          # 完整对话历史
            "temperature": self.temperature,   # 生成温度
            "stream": False                    # 非流式，等待完整响应
        }
        try:
            # 发送 POST 请求到 Chat Completions API
            resp = requests.post(
                url=f"{self.base_url}/chat/completions",  # 拼接完整 API 路径
                headers=self.headers,                       # 认证头
                json=payload,                               # 请求体
                timeout=60                                   # 60秒超时
            )
            resp.raise_for_status()  # HTTP 错误时抛异常

            # 解析 API 响应，提取模型回复内容
            data = resp.json()
            content = data["choices"][0]["message"]["content"].strip()
            return content

        except Exception as e:
            # 所有异常统一返回错误字符串，不中断 Agent 循环
            return f"LLM API 请求失败: {str(e)}"
