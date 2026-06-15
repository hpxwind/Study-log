"""
prompt_builder.py — 系统 Prompt 动态构建器

【模块作用】
根据是否开启 Reflection 模式，动态拼装 system prompt。
核心思路：prompt 模板中所有"业务特定内容"（工具列表、工具提示、工具数量、工具名称）
全部通过占位符 {tool_list} {tool_hints} {tool_count} {tool_names} 从 tool_registry
动态获取，而非硬编码在模板里。新增/删除工具时，无需修改此文件。

【两个模板】
- REFLECT_ON_TPL  : 开启 Reflection 的完整模板，包含三段式 Reflection 格式说明
- REFLECT_OFF_TPL : 关闭 Reflection 的精简模板，仅保留 Thought/Action/FinalAnswer 格式

【被谁依赖】
- core/react_agent.py → run() 中调用 build_system_prompt() 获取 system prompt
"""

from config.tool_registry import get_tool_prompt_desc, get_tool_hints_text, get_all_tool_names

# ---------------------------------------------------------------------------
# 开启 Reflection 的系统 prompt 模板
#
# 【设计要点】
# 1. {tool_list}  — 工具列表，由 get_tool_prompt_desc() 动态生成
# 2. {tool_hints} — 工具使用提示，由 get_tool_hints_text() 动态汇总
# 3. {tool_count} — 工具总数，由 len(get_all_tool_names()) 动态计算
# 4. {tool_names} — 工具名称枚举，由 "、".join(get_all_tool_names()) 动态拼接
#
# 以上四个占位符替代了原来写死的"ORD001金额=299""工具只有两个"等硬编码。
# 模板中的 {{key:val}} 是 Python format 的转义写法，实际输出 {key:val}，
# 用于在 prompt 中告诉 LLM "禁止使用大括号格式"。
# ---------------------------------------------------------------------------
REFLECT_ON_TPL = """
你是ReAct自省Agent，对话里的Reflection内容必须全部记住，不能遗忘之前的错误。
可用工具列表：
{tool_list}

一、调用工具输出格式（只能二选一结构）
1）调用工具：
Thought: 梳理所有任务、历史错误、下一步计划
Action: 工具名(参数名='字符串',数字参数直接写数字不加引号)
禁止使用{{key:val}}大括号格式

2）全部任务完成才可以结束：
FinalAnswer: 汇总全部任务信息

二、Reflection固定三段模板（工具返回后强制写）
Reflection:
1.本次工具调用是否成功、参数有无错误
2.已完成任务 / 待完成任务清单
3.精确写出下一轮Action

工具使用提示（各工具常见坑/校验规则）：
{tool_hints}

可用工具共{tool_count}个：{tool_names}，所有任务涉及的工具都完成后才能输出FinalAnswer。
"""

# ---------------------------------------------------------------------------
# 关闭 Reflection 的系统 prompt 模板
#
# 【设计要点】
# 与 ON 模板的区别：
# 1. 无 Reflection 格式说明，明确"禁止输出Reflection"
# 2. 格式说明更精简，只保留 Thought + Action / FinalAnswer 二选一
# 3. 仍保留 {tool_hints}，即使不反思，LLM 也需要知道工具常见坑避免犯错
#
# 不需要 {tool_count}/{tool_names}，因为非反射模式下 LLM 不需要主动追踪任务完成度
# ---------------------------------------------------------------------------
REFLECT_OFF_TPL = """
你是ReAct Agent，按固定格式调用工具完成任务。
可用工具列表：
{tool_list}

输出格式（只能二选一）：

1）调用工具：
Thought: 分析当前任务和下一步
Action: 工具名(参数名='字符串',数字参数直接写数字不加引号)

2）全部任务完成后：
FinalAnswer: 汇总全部任务结果

严格规则：
1.Action只用小括号()，禁止使用大括号{{}}格式
2.禁止输出Reflection
3.所有任务全部完成才能输出FinalAnswer

工具使用提示：
{tool_hints}
"""


def build_system_prompt(enable_reflection: bool) -> str:
    """
    根据是否开启 Reflection 模式，动态构建 system prompt。

    【函数作用】
    从 tool_registry 获取最新的工具列表、提示文本、工具名称和数量，
    填入对应的 prompt 模板占位符，返回完整的 system prompt 字符串。
    每次调用都从 registry 实时读取，保证新增工具后无需修改此函数。

    【参数说明】
    - enable_reflection : 是否开启 Reflection 自省模式
                         来源：ReActAgentWithReflection.__init__ 的 self.enable_reflection
                         True  → 使用 REFLECT_ON_TPL（含三段式 Reflection 格式）
                         False → 使用 REFLECT_OFF_TPL（精简版，禁止 Reflection）

    【谁会调用】
    - core/react_agent.py → run() 方法中调用：
      sys_prompt = build_system_prompt(self.enable_reflection)

    【关键代码解析】
    tool_text = get_tool_prompt_desc()
      → 获取格式化的工具列表文本，如:
        "- check_order: 核验订单... 参数(order_id: str, pay_amount: int)"

    tool_hints = get_tool_hints_text()
      → 获取汇总的工具提示文本，如:
        "- check_order: pay_amount必须与订单实际金额一致; order_id必须存在"

    tool_names = "、".join(get_all_tool_names())
      → 获取工具名枚举，如: "check_order、get_schedule"

    tool_count = len(get_all_tool_names())
      → 获取工具数量，如: 2

    filled = REFLECT_ON_TPL.format(tool_list=..., tool_hints=..., ...)
      → 用 str.format() 将占位符替换为实际文本，生成最终 system prompt
    """
    # 从注册表动态获取所有需要的信息——这是"去硬编码"的核心
    tool_text = get_tool_prompt_desc()      # 工具列表描述
    tool_hints = get_tool_hints_text()      # 工具使用提示汇总
    tool_names = "、".join(get_all_tool_names())  # 工具名枚举
    tool_count = len(get_all_tool_names())         # 工具总数

    if enable_reflection:
        # 开启反思模式 → 填充完整模板（含 Reflection 格式、工具数量/名称）
        filled = REFLECT_ON_TPL.format(
            tool_list=tool_text,
            tool_hints=tool_hints,
            tool_names=tool_names,
            tool_count=tool_count,
        )
    else:
        # 关闭反思模式 → 填充精简模板（无 Reflection，无工具数量/名称）
        filled = REFLECT_OFF_TPL.format(
            tool_list=tool_text,
            tool_hints=tool_hints,
        )
    return filled
