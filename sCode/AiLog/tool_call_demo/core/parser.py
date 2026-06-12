from config.tool_registry import TOOL_REGISTRY
import json

def parse_tool_calls(assistant_msg):
    """
    从assistant消息里提取所有工具调用\n
    assistant_msg，OpenAI SDK 返回的消息对象: response.choices[0].message 对象\n
    返回列表 [{id, name, args_dict}]
    """
    tool_calls = assistant_msg.tool_calls
    if not tool_calls:
        return []

    call_list = []
    for call in tool_calls:
        func_name = call.function.name
        args_str = call.function.arguments
        call_id = call.id

        try:
            args = json.loads(args_str)
        except json.JSONDecodeError:
            args = {}

        if func_name in TOOL_REGISTRY:
            call_list.append({
                "call_id": call_id,
                "name": func_name,
                "args": args
            })
    return call_list

def execute_single_tool(func_name: str, args: dict):
    """执行本地单个工具的函数"""
    tool_info = TOOL_REGISTRY[func_name]
    func = tool_info["func"]
    try:
        return func(**args)
    except Exception as e:
        return f"工具执行异常: {str(e)}"