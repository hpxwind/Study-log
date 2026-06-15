"""
output_parser.py — LLM 输出解析器

【模块作用】
将 LLM 的原始文本输出解析为结构化的 ReActOutput 对象。
这是 Agent 循环中"理解 LLM 想做什么"的关键环节——LLM 输出一段文本，
解析器从中提取 Thought / Action / Reflection / FinalAnswer 等结构化字段。

【核心设计：段落级解析】
旧版逐行解析存在致命缺陷：Reflection/Thought 的内容经常跨多行，
逐行解析只能捕获 "Reflection:" 后的第一行，后续行被当作"无标记行"丢弃。
新版改为"段落级解析"：
  1. 用正则找到所有段落标记（Thought: / Action: / Reflection: / FinalAnswer:）
  2. 每个段落的内容 = 从标记结束位置到下一个标记开始位置之间的全部文本
  3. 这样 Reflection: 后的多行内容全部被正确捕获

【被谁依赖】
- core/react_agent.py → _generate_with_retry() 中调用 parse_llm_output() 解析 LLM 输出
"""

import re
from typing import Optional, Dict


class ReActOutput:
    """
    LLM 输出的结构化表示对象。

    【类作用】
    将 LLM 的自由文本输出解析为 5 个结构化字段，供 Agent 主循环判断下一步动作：
    - thought      : LLM 的推理过程，决定 Agent 是否有有效输出
    - action_name  : LLM 要调用的工具名，决定 Agent 是否执行工具
    - action_args  : LLM 传给工具的参数，决定工具如何执行
    - final_answer : LLM 给出的最终答案，非空时 Agent 直接返回结果
    - reflection    : LLM 的反思内容，供下一轮 Thought 参考历史错误

    【字段默认值设计】
    - thought/final_answer 默认空/None → 区分"LLM没输出"和"LLM输出了内容"
    - reflection 默认 None（非硬编码兜底字符串）→ 让调用方能区分"没有反思"和"反思了但内容短"
    """

    def __init__(
        self,
        thought: str = "",
        action_name: Optional[str] = None,
        action_args: Optional[Dict] = None,
        final_answer: Optional[str] = None,
        reflection: Optional[str] = None,
    ):
        # thought: 推理文本，strip 去除首尾空白；空字符串表示 LLM 未输出 Thought
        self.thought = thought.strip() if thought else ""
        # action_name: 工具名，None 表示 LLM 未输出 Action
        self.action_name = action_name
        # action_args: 工具参数字典，空字典表示无参数
        self.action_args = action_args or {}
        # final_answer: 最终答案，None 表示 LLM 未输出 FinalAnswer
        self.final_answer = final_answer.strip() if final_answer else None
        # reflection: 反思文本，None 表示 LLM 未输出 Reflection
        # 注意：默认为 None 而非硬编码字符串，让调用方能判断"是否真的反思了"
        self.reflection = reflection.strip() if reflection else None


# ---------------------------------------------------------------------------
# 段落标记正则表达式
#
# 【作用】在 LLM 原始输出中定位所有段落开头标记的位置
# 【匹配模式】
#   ^(Thought\s*[:：]|Action\s*[:：]|FinalAnswer\s*[:：]|Reflection\s*[:：])
#
# ^              → 行首（配合 re.MULTILINE，每行都独立匹配 ^）
# Thought\s*[:：] → 匹配 "Thought:" 或 "Thought："（支持中英文冒号，中间可有空格）
# re.MULTILINE   → 让 ^ 匹配每行行首而非整个字符串开头
# re.IGNORECASE  → 大小写不敏感，"thought:" / "THOUGHT:" 都能匹配
#
# 为什么不用逐行 split？因为 Reflection/Thought 内容常跨多行，
# 逐行处理无法正确收集多行段落，只能用 finditer 定位标记位置再切割。
# ---------------------------------------------------------------------------
_SECTION_RE = re.compile(
    r'^(Thought\s*[:：]|Action\s*[:：]|FinalAnswer\s*[:：]|Reflection\s*[:：])',
    re.MULTILINE | re.IGNORECASE,
)


def _parse_action(action_text: str, out: ReActOutput):
    """
    解析 Action 段落文本，提取工具名和参数，写入 ReActOutput 对象。

    【函数作用】
    Action 段落格式为 "tool_name(key='val', num=123)"，
    此函数从中提取工具名和参数字典，填充到 out.action_name 和 out.action_args。

    【参数说明】
    - action_text : Action 标记后的全部内容文本
                    来源：parse_llm_output() 中，Action 标记到下一个标记之间的文本
    - out         : 待填充的 ReActOutput 对象
                    来源：parse_llm_output() 中创建的空 ReActOutput

    【谁会调用】
    - parse_llm_output() → 当解析到 label == "action" 时调用

    【关键代码解析】
    first_line = text.split('\\n')[0].strip()
      → Action 只占一行，取第一行避免多行干扰

    name_match = re.match(r"^([a-zA-Z0-9_]+)", first_line)
      → 从行首提取工具名（字母数字下划线），如 "check_order"

    if arg_part.startswith("(") and arg_part.endswith(")"):
        inner = arg_part[1:-1].strip()
      → 去掉外层小括号，得到参数内部文本
      → 也支持 {} 大括号格式（兼容 LLM 可能输出的两种格式）

    kv = re.match(r"['\"]?([a-zA-Z0-9_]+)['\"]?\s*[:=]\s*['\"]?(.*?)['\"]?$", p)
      → 匹配 "key='value'" 或 "key=value" 或 "key: value" 格式的键值对
      → 键名两端的引号可选，值两端的引号可选

    if v.isdigit():
        v = int(v)
      → 纯数字字符串转为 int，如 "300" → 300，
        保证传给工具函数时类型正确（pay_amount 需要 int）
    """
    text = action_text.strip()
    # Action 只占一行，取第一行避免后续无关内容干扰
    first_line = text.split('\n')[0].strip()

    # 从行首提取工具名（字母、数字、下划线组成）
    name_match = re.match(r"^([a-zA-Z0-9_]+)", first_line)
    if not name_match:
        return  # 无法识别工具名，跳过

    act_name = name_match.group(1)       # 提取到的工具名，如 "check_order"
    arg_part = first_line[len(act_name):].strip()  # 工具名之后的部分，如 "(order_id='ORD001', pay_amount=300)"

    # 去掉外层括号，提取参数内部文本
    inner = ""
    if arg_part.startswith("(") and arg_part.endswith(")"):
        # 小括号格式: tool(key='val')  ← 这是 prompt 要求的标准格式
        inner = arg_part[1:-1].strip()
    elif arg_part.startswith("{") and arg_part.endswith("}"):
        # 大括号格式: tool{key='val'}  ← LLM 有时会给出的格式，兼容处理
        inner = arg_part[1:-1].strip()

    # 解析参数键值对
    args = {}
    if inner:
        # 按逗号分割各参数，如 "order_id='ORD001', pay_amount=300"
        parts = re.split(r",\s*", inner)
        for p in parts:
            # 匹配 key='value' / key="value" / key=value / key: value 等格式
            kv = re.match(r"['\"]?([a-zA-Z0-9_]+)['\"]?\s*[:=]\s*['\"]?(.*?)['\"]?$", p)
            if kv:
                k = kv.group(1).strip()   # 参数名，如 "order_id"
                v = kv.group(2).strip()   # 参数值，如 "ORD001" 或 "300"
                if v.isdigit():
                    v = int(v)            # 纯数字字符串转为 int，保证类型正确
                args[k] = v

    # 将解析结果写入 ReActOutput 对象
    out.action_name = act_name
    out.action_args = args


def parse_llm_output(text: str) -> ReActOutput:
    """
    基于段落标记的多行 LLM 输出解析器。

    【函数作用】
    将 LLM 的原始文本输出解析为 ReActOutput 对象。
    核心算法：先用正则找到所有段落标记（Thought:/Action:/Reflection:/FinalAnswer:），
    再按标记位置切割文本，每个段落从标记结束到下一个标记开始之间的全部内容
    都归属于该段落。这样多行的 Reflection/Thought 内容都能被完整捕获。

    【参数说明】
    - text : LLM 的原始输出文本
             来源：self.llm.generate(self.chat_history) 返回的 resp_text

    【谁会调用】
    - core/react_agent.py → _generate_with_retry() 中调用：
      res = parse_llm_output(resp_text)

    【关键代码解析】
    matches = list(_SECTION_RE.finditer(raw))
      → 找到所有段落标记的匹配对象列表，每个 match 包含标记位置和文本

    content_start = match.end()
      → 当前段落内容从标记结束位置开始（跳过 "Thought:" 本身）

    content_end = matches[i + 1].start() if i + 1 < len(matches) else len(raw)
      → 当前段落内容到下一个标记开始位置结束（或到文本末尾）
      → 这就是"段落级解析"的核心——两个标记之间的全部文本归属前一个段落

    label = re.sub(r'[:：]', '', match.group(1).strip()).lower()
      → 去掉冒号、转小写，统一为 "thought" / "action" / "reflection" / "finalanswer"
    """
    out = ReActOutput()
    raw = text.strip()

    # 空输出 → 标记为空白，让调用方触发重试
    if not raw:
        out.thought = "输出空白，请严格按格式书写"
        return out

    # 找到所有段落标记的位置
    matches = list(_SECTION_RE.finditer(raw))

    if not matches:
        # 没找到任何已知标记 → LLM 可能输出了纯文本，整段当作 thought
        # 这样调用方至少能拿到内容，不至于完全丢弃 LLM 的输出
        out.thought = raw
        return out

    # 遍历每个段落标记，提取标记之间的内容
    for i, match in enumerate(matches):
        # 去掉冒号、转小写，统一标记名：如 "Thought:" → "thought"
        label = re.sub(r'[:：]', '', match.group(1).strip()).lower()

        # 当前段落内容 = 从标记结束位置 → 下一个标记开始位置（或文本末尾）
        content_start = match.end()
        content_end = matches[i + 1].start() if i + 1 < len(matches) else len(raw)
        content = raw[content_start:content_end].strip()

        # 根据标记类型将内容写入对应字段
        if label == "thought":
            out.thought = content
        elif label == "action":
            _parse_action(content, out)  # Action 需要额外解析工具名和参数
        elif label == "reflection":
            out.reflection = content      # Reflection 多行内容全部捕获
        elif label == "finalanswer":
            out.final_answer = content    # FinalAnswer 多行内容全部捕获

    return out
