from config.tool_registry import TOOL_REGISTRY as tool_registry
import json

def build_react_full_prompt(user_q: str, history: str):
    """拼接一整段标准化提示词，喂给大模型，约束模型严格走 ReAct 思考 - 工具 - 回答流程，绑定注册表内所有工具"""
    # 循环组装所有工具说明
    tool_text_parts = []
    for name, info in tool_registry.items():
        block = (
            f"【工具:{name}】\n"
            f"描述: {info['description']}\n"
            f"入参Schema: {json.dumps(info['parameters'], ensure_ascii=False)}"
        )
        tool_text_parts.append(block)
    tool_text = "\n\n".join(tool_text_parts)

    prompt = f"""
你是严格遵循ReAct固定格式的助手，**格式错误会无法完成任务**
可用工具列表：
{tool_text}

# 强制输出格式（只能二选一，不能混合，不能省略标签）
情况1：信息足够、不用工具回答
必须两行：
Thought: 你的推理内容
FinalAnswer: 给用户的完整答案

情况2：必须调用工具查询计算
必须两行：
Thought: 你的推理内容
Action: {{"name":"工具名","parameters":{{}}}}

# 铁则
1. 只要Observation里已经拿到全部所需数据，**下一轮必须立刻输出FinalAnswer**，不许只写Thought
2. 禁止只单独输出Thought，每一轮必须搭配Action 或 FinalAnswer
3. Action只能单行标准JSON，无换行；FinalAnswer紧跟Thought之后
4. 一轮只能调用一个工具

历史上下文：
{history}

用户问题：
{user_q}
    """.strip()
    return prompt