"""
prompt_builder.py — Prompt 构建器
==================================
为三种规划模式生成不同风格的 Prompt：

  1. build_chain_prompt()                — 链式规划（ReAct 逐步推理+执行）
  2. build_hierarchical_plan_prompt()    — 分层规划·规划阶段（生成独立步骤列表）
  3. build_hierarchical_synthesis_prompt() — 分层规划·汇总阶段（整合观察生成答案）
  4. build_holistic_plan_prompt()        — 整体规划·规划阶段（生成含步骤依赖的计划）

所有函数都从 TOOL_REGISTRY 动态读取工具信息，新增工具时无需修改此文件。
"""

from config.tool_registry import TOOL_REGISTRY as tool_registry
import json


# ════════════════════════════════════════════════════
# 公共工具说明文本生成
# ════════════════════════════════════════════════════

def _build_tool_desc_text() -> str:
    """
    从 TOOL_REGISTRY 动态拼接所有工具的描述文本。

    返回:
        str — 格式化的工具列表，如：
              【工具:calculator】
              描述: 简单的四则运算器
              入参Schema: {...}

    调用方:
        build_chain_prompt()
        build_hierarchical_plan_prompt()
    """
    parts = []
    for name, info in tool_registry.items():
        block = (
            f"【工具:{name}】\n"
            f"描述: {info['description']}\n"
            f"入参Schema: {json.dumps(info['parameters'], ensure_ascii=False)}"
        )
        parts.append(block)
    return "\n\n".join(parts)


# ════════════════════════════════════════════════════
# 1. 链式规划 Prompt
# ════════════════════════════════════════════════════

def build_chain_prompt(user_q: str, history: str) -> str:
    """
    构建链式规划（经典 ReAct）的完整 Prompt。

    Prompt 结构：
      - 角色设定：严格 ReAct 格式助手
      - 可用工具列表（动态生成）
      - 输出格式约束（Thought+Action 或 Thought+FinalAnswer 二选一）
      - 铁则（防止 LLM 只输出 Thought 不输出 Action 等）
      - 历史上下文
      - 用户问题

    参数:
        user_q: str   — 用户原始问题（来源：ChainPlanner.solve() 传入）
        history: str   — 已有序列化的历史上下文（来源：BasePlanner.format_history_for_prompt()）

    返回:
        str — 可直接传给 LLM 的完整 prompt

    调用方:
        ChainPlanner.solve()
    """
    tool_text = _build_tool_desc_text()

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


# ════════════════════════════════════════════════════
# 2. 分层规划 — 规划阶段 Prompt
# ════════════════════════════════════════════════════

def build_hierarchical_plan_prompt(user_q: str) -> str:
    """
    构建分层规划·规划阶段的 Prompt。

    要求 LLM 一次性输出 JSON 格式的步骤列表，每个步骤包含：
      - step: 步骤编号
      - tool: 工具名（必须是可用工具之一）
      - params: 工具参数字典
      - reason: 为什么需要这一步

    如果无需工具即可回答，LLM 应输出 FinalAnswer 而非步骤列表。

    参数:
        user_q: str — 用户原始问题（来源：HierarchicalPlanner.solve() 传入）

    返回:
        str — 规划阶段 prompt

    调用方:
        HierarchicalPlanner.solve() 阶段1
    """
    tool_text = _build_tool_desc_text()

    prompt = f"""
你是一个任务规划专家。请根据用户问题，制定一个完整的执行计划。

可用工具列表：
{tool_text}

# 输出格式（二选一）

情况1：需要调用工具才能回答
请输出一个JSON数组，每个元素代表一个执行步骤：
```json
[
  {{"step": 1, "tool": "工具名", "params": {{参数字典}}, "reason": "为什么需要这一步"}},
  {{"step": 2, "tool": "工具名", "params": {{参数字典}}, "reason": "为什么需要这一步"}}
]
```

情况2：无需工具，直接回答
直接输出：
FinalAnswer: 你的答案

# 规则
1. 步骤顺序必须合理，先查数据再做计算
2. tool 必须是上面列出的可用工具之一
3. params 必须符合工具的参数Schema
4. 只输出JSON或FinalAnswer，不要输出其他内容

用户问题：
{user_q}
    """.strip()
    return prompt


# ════════════════════════════════════════════════════
# 3. 分层规划 — 汇总阶段 Prompt
# ════════════════════════════════════════════════════

def build_hierarchical_synthesis_prompt(user_q: str, observations: list) -> str:
    """
    构建分层规划·汇总阶段的 Prompt。

    将所有步骤的执行结果（Observation）和原始问题一起交给 LLM，
    让 LLM 整合信息并输出 FinalAnswer。

    参数:
        user_q: str       — 用户原始问题（来源：HierarchicalPlanner.solve() 传入）
        observations: list — 执行阶段收集的观察结果列表
                             格式: [{"step":1, "tool":"...", "params":{}, "observation":"..."}]

    返回:
        str — 汇总阶段 prompt

    调用方:
        HierarchicalPlanner.solve() 阶段3
    """
    # 将 observations 格式化为可读文本
    obs_lines = []
    for obs in observations:
        obs_lines.append(
            f"步骤{obs['step']}（工具:{obs['tool']}，参数:{obs['params']}）:\n"
            f"结果: {obs['observation']}"
        )
    obs_text = "\n\n".join(obs_lines)

    prompt = f"""
你是一个答案整合助手。以下是根据用户问题执行工具后收集到的所有结果，请整合这些信息，给出完整准确的最终答案。

用户问题：{user_q}

执行结果：
{obs_text}

请输出：
FinalAnswer: 整合后的完整答案
    """.strip()
    return prompt


# ════════════════════════════════════════════════════
# 4. 整体规划 — 规划阶段 Prompt
# ════════════════════════════════════════════════════

def build_holistic_plan_prompt(user_q: str) -> str:
    """
    构建整体规划·规划阶段的 Prompt。

    与分层规划的区别：
      - 分层规划：步骤参数在规划时写死，步骤间完全独立
      - 整体规划：步骤间可以引用前序步骤的输出，使用 $step_N 语法
        例如：{"num1": "$step1", "operator": "*"} 表示 num1 取第1步的 Observation 结果

    如果无需工具即可回答，LLM 应输出 FinalAnswer 而非步骤列表。

    参数:
        user_q: str — 用户原始问题（来源：HolisticPlanner.solve() 传入）

    返回:
        str — 规划阶段 prompt

    调用方:
        HolisticPlanner.solve() 阶段1
    """
    tool_text = _build_tool_desc_text()

    prompt = f"""
你是一个任务规划专家。请根据用户问题，制定一个完整的执行计划。

可用工具列表：
{tool_text}

# 输出格式（二选一）

情况1：需要调用工具才能回答
请输出一个JSON数组，每个元素代表一个执行步骤。后续步骤的参数可以引用前序步骤的输出结果：
```json
[
  {{"step": 1, "tool": "工具名", "params": {{参数字典}}, "reason": "为什么需要这一步"}},
  {{"step": 2, "tool": "工具名", "params": {{"key1": "$step1", "key2": "固定值"}}, "reason": "为什么需要这一步"}}
]
```

参数引用语法：
- "$step1" 表示引用第1步的Observation输出结果
- "$step2" 表示引用第2步的Observation输出结果
- 只有字符串类型的参数值才能使用引用，数字和布尔值直接写
- 引用只能引用比当前步骤编号小的步骤（步骤按顺序执行）

情况2：无需工具，直接回答
直接输出：
FinalAnswer: 你的答案

# 规则
1. 步骤按顺序执行，后续步骤可引用前序步骤的结果
2. tool 必须是上面列出的可用工具之一
3. params 必须符合工具的参数Schema
4. 只输出JSON或FinalAnswer，不要输出其他内容

用户问题：
{user_q}
    """.strip()
    return prompt
