# core/output_parser.py
import json
from typing import Tuple, Optional, Dict

ParseResult = Tuple[str, Optional[Tuple[str, Dict]], Optional[str]]
TAG_THOUGHT = "Thought"
TAG_ACTION = "Action"
TAG_FINAL = "FinalAnswer"

def parse_llm_response(content: str) -> ParseResult:
    thought = ""
    action_package: Optional[Tuple[str, Dict]] = None
    final_answer = None

    # 文本预处理，清洗空行，多余空格
    lines = [line.strip() for line in content.split("\n") if line.strip()]

    # 逐行循环匹配标签
    for line in lines:
        # 匹配思考行
        if line.startswith(f"{TAG_THOUGHT}:"):
            thought = line.replace(f"{TAG_THOUGHT}:", "").strip()
        # 匹配工具调用行
        elif line.startswith(f"{TAG_ACTION}:"):
            raw_json_str = line.replace(f"{TAG_ACTION}:", "").strip()
            try:
                data = json.loads(raw_json_str)
                # 正确取出名字和参数
                real_tool_name = data["name"]
                real_params = data.get("parameters", {})
                action_package = (real_tool_name, real_params)
            except Exception as e:
                print(f"JSON解析失败:{e},原始内容:{raw_json_str}")
                action_package = None
        
        # 匹配最终回答行
        elif line.startswith(f"{TAG_FINAL}:"):
            final_answer = line.replace(f"{TAG_FINAL}:", "").strip()
    return thought, action_package, final_answer