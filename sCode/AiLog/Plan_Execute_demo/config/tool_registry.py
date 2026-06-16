from tools.calculator import calculator
from tools.info_search import search_kb

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
    "info_search": {
        "func": search_kb,
        "description": "模拟互联网上的数据",
        "parameters": {
            "type": "object",
            "properties": {
                "keyword":{
                    "type": "string",
                    "descript":"接收的提问"
                }
            }
        },
        "required": ["keyword"]
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

def get_tool_function(tool_name:str):
    """执行查找器,根据模型给出的工具名字，去注册表匹配条目"""
    item = TOOL_REGISTRY.get(tool_name)
    if not item:
        return None
    return item["func"]