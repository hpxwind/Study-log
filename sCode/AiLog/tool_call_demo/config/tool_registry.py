from tools.calculator import calculator
from tools.time_tool import get_current_time

TOOL_REGISTRY = {
    "calculator": {
        "func": calculator,
        "description": "简单的四则运算器",
        "parameters": {
            "type": "object",
            "properties": {
                "num1": {
                    "type": "number",
                    "description":"运算的第一个数字",
                },
                "num2": {
                    "type": "number",
                    "description":"运算的第二个数字",
                },
                "operator": {
                    "type": "string",
                    "description":"运算符号",
                    "enum":["+", "-", "*", "/"]
                }
            }
        },
        "required":["num1", "num2","operator"]
    },
    "get_current_time": {
        "func": get_current_time,
        "description": "获取当前时间",
        "parameters": {
            "type": "object",
            "properties": {}
        },
        "required": []
    }
}

def get_openai_tools():
    """
    转换成openai工具定义格式,转换成OpenAi标准tools数组格式
    - 对于大模型API，各种兼容接口接收的参数是固定的，需要一个转换器将自定义的转换为合法的，如下：
    [
        {
            "type": "function",
            "function": {
            "name": "工具名",
            "description": "工具描述",
            "parameters": {schema结构}
            }
        }
    ]
    """
    openai_tools = [] # 对象数组
    for name, info in TOOL_REGISTRY.items():
        openai_tools.append({
            "type": "function",
            "function": {
                "name": name,
                "description": info["description"],
                "parameters": info["parameters"]
            }
        })
    return openai_tools