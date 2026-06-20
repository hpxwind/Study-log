# 结构化上下文模板（Context Engineering 格式化规范）
CONTEXT_PROMPT_TPL = """
【历史对话摘要】
{chat_summary}

【参考资料（仅允许使用以下内容回答）】
{related_docs}

【用户当前提问】
{user_query}

约束：禁止编造信息，只依据上文内容回答，回答精简直白。
"""