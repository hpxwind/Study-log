def search_kb(keyword: str) -> str:
    """模拟联网知识库，提供外部真实信息"""
    knowledge_base = {
        "react": "ReAct全称Reason+Action，2022谷歌提出；核心循环：Thought思考→Action执行工具→Observation接收结果，多轮迭代回答问题，解决CoT无法获取外部实时信息的缺陷",
        "2026": "当前年份为2026年",
        "cot": "CoT仅内部思维推理，没有调用外部工具的行动能力，容易产生幻觉"
    }
    return knowledge_base.get(keyword, f"知识库无「{keyword}」内容") # 有则返回，没有返回兜底内容