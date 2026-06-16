"""
output_parser.py — LLM 输出解析器
==================================
提供两种解析能力：

  1. parse_llm_response() — 链式规划专用，解析单轮 ReAct 输出（Thought/Action/FinalAnswer）
  2. parse_plan_response() — 分层规划专用，解析规划阶段的 JSON 步骤列表

两种解析器都做了容错处理，解析失败不会抛异常，而是返回空结果。
"""
import json
import re
from typing import Tuple, Optional, Dict, List

# ──────────────────────────────────────
# 公共标签常量（与 base_planner 保持一致）
# ──────────────────────────────────────
TAG_THOUGHT = "Thought"
TAG_ACTION = "Action"
TAG_FINAL = "FinalAnswer"

# 链式解析返回类型: (thought, action_info, final_answer)
ParseResult = Tuple[str, Optional[Tuple[str, Dict]], Optional[str]]

# ════════════════════════════════════════════════════
# 1. 链式规划解析器
# ════════════════════════════════════════════════════

def parse_llm_response(content: str) -> ParseResult:
    """
    解析链式规划中 LLM 的单轮输出，提取 Thought / Action / FinalAnswer。

    解析逻辑:
        1. 按行拆分，去除空行
        2. 逐行匹配标签前缀（Thought: / Action: / FinalAnswer:）
        3. Action 行的值需是合法 JSON，格式为 {"name":"...", "parameters":{...}}

    参数:
        content: str — LLM 原始输出文本（来源：mock_llm.call_model() 返回值）

    返回:
        ParseResult — 三元组：
            - thought: str              推理内容，默认空串
            - action_info: Optional     若有则为 (tool_name, params_dict)，否则 None
            - final_answer: Optional    若有则为答案字符串，否则 None

    调用方:
        ChainPlanner.solve() 每轮解析 LLM 输出
    """
    thought = ""
    action_package: Optional[Tuple[str, Dict]] = None
    final_answer = None

    # 文本预处理：清洗空行和多余空格
    lines = [line.strip() for line in content.split("\n") if line.strip()]

    for line in lines:
        # 匹配 Thought 行
        if line.startswith(f"{TAG_THOUGHT}:"):
            thought = line.replace(f"{TAG_THOUGHT}:", "").strip()

        # 匹配 Action 行 — 需要解析 JSON
        elif line.startswith(f"{TAG_ACTION}:"):
            raw_json_str = line.replace(f"{TAG_ACTION}:", "").strip()
            try:
                data = json.loads(raw_json_str)
                real_tool_name = data["name"]
                real_params = data.get("parameters", {})
                action_package = (real_tool_name, real_params)
            except Exception as e:
                print(f"JSON解析失败:{e}, 原始内容:{raw_json_str}")
                action_package = None

        # 匹配 FinalAnswer 行
        elif line.startswith(f"{TAG_FINAL}:"):
            final_answer = line.replace(f"{TAG_FINAL}:", "").strip()

    return thought, action_package, final_answer
# ════════════════════════════════════════════════════
# 2. 分层规划解析器
# ════════════════════════════════════════════════════

def parse_plan_response(content: str) -> List[Dict]:
    """
    解析分层规划中 LLM 输出的执行计划（JSON 步骤列表）。

    支持两种格式：
      - 纯 JSON 数组：[{"step":1, "tool":"...", "params":{}, "reason":"..."}, ...]
      - Markdown 代码块包裹的 JSON：```json [...] ```

    解析逻辑:
        1. 先尝试从 markdown 代码块中提取 JSON
        2. 若无代码块，尝试用正则找第一个 [ ... ] 区间
        3. JSON 解析后校验每个步骤必须包含 step / tool / params 字段
        4. 缺少 fields 的步骤会被跳过（容错）

    参数:
        content: str — LLM 原始输出文本（来源：mock_llm.call_model() 返回值）

    返回:
        List[Dict] — 步骤字典列表，每项包含 step / tool / params / reason
                     解析失败返回空列表 []

    调用方:
        HierarchicalPlanner.solve() 阶段1 解析规划结果
    """
    steps = []

    # ── 尝试1：从 markdown 代码块中提取 ──
    code_block_match = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", content, re.DOTALL)
    if code_block_match:
        json_str = code_block_match.group(1).strip()
    else:
        # ── 尝试2：正则匹配第一个 [ ... ] 区间 ──
        bracket_match = re.search(r"\[.*\]", content, re.DOTALL)
        json_str = bracket_match.group(0) if bracket_match else ""

    if not json_str:
        return []

    # ── JSON 解析 ──
    try:
        plan_list = json.loads(json_str)
    except json.JSONDecodeError as e:
        print(f"⚠️ 计划JSON解析失败: {e}")
        return []

    # ── 逐条校验步骤字段完整性 ──
    for item in plan_list:
        if not isinstance(item, dict):
            continue
        # 必须包含 step / tool / params，缺一不可
        if "step" not in item or "tool" not in item or "params" not in item:
            print(f"⚠️ 跳过不完整步骤: {item}")
            continue
        steps.append({
            "step": item["step"],
            "tool": item["tool"],
            "params": item["params"],
            "reason": item.get("reason", "")  # reason 可选
        })

    return steps
