import json
from config.tool_registry import TOOL_REGISTRY as tool_registry

def build_system_prompt() -> str:
    """拼接工具列表生成系统提示词"""
    tool_descriptions = []
    for tool_name, tool_info in tool_registry.items():
        tool_descriptions.append({
            "name": tool_name,
            "description": tool_info["description"],
            "parameters": tool_info["parameters"]
        })
    system_prompt = """
        你是一个智能助手，可以调用以下工具来帮助用户完成任务：
        {json.dumps(tool_descriptions, indent=4, ensure_ascii=False)}
        当你需要使用工具时，请按照以下格式回复：
        1. 需要计算，查询时间必须调用工具：普通闲聊直接自然文本回答
        2. 调用工具时候只输出纯**json格式**，无多余文字，注释，换行干扰，格式如下：
        {{"tool_name": "工具名称", "parameters": {工具参数}}}
        3. 禁止输出json格式内容
        4. 工具调用后，等待工具返回结果，再继续后续对话
    """    
    return system_prompt