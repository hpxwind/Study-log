import os
from dotenv import load_dotenv
from mock_llm import chat_completion
from config.tool_registry import get_openai_tools
from core.parser import parse_tool_calls, execute_single_tool

load_dotenv()
MAX_LOOP = int(os.getenv("MAX_TOOL_LOOP"))

def run_agent(user_query: str):
    messages = [
        {"role": "user", "content": user_query}
    ]
    openai_tools = get_openai_tools()
    loop = 0

    while loop < MAX_LOOP:
        # 向大模型发送当前全部对话 + 工具
        resp = chat_completion(messages=messages, tools=openai_tools)
        choice = resp.choices[0]
        assistant_msg = choice.message

        # 模型 不需要调用工具，直接结束返回答案
        if not assistant_msg.tool_calls:
            return assistant_msg.content.strip()

        # 存在工具调用，解析任务
        call_tasks = parse_tool_calls(assistant_msg)
        if not call_tasks:
            return assistant_msg.content.strip()

        # 把模型助手消息加入对话历史，等待工具结果
        messages.append(assistant_msg.model_dump())

        for task in call_tasks:
            cid = task["call_id"]
            fname = task["name"]
            fargs = task["args"]
            print(f"[调用工具] {fname} 参数:{fargs}")
            res = execute_single_tool(fname, fargs)
            print(f"[工具结果] {res}\n")
            messages.append({
                "role": "tool",
                "tool_call_id": cid,
                "name": fname,
                "content": str(res)
            })

        loop += 1

    # 如果在MAX_LOOP轮次后仍未得到最终答案，则返回最后一次模型回复的内容
    final_resp = chat_completion(messages=messages)
    return final_resp.choices[0].message.content.strip()