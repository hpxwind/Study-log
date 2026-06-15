"""
tool_registry.py — 工具注册中心

【模块作用】
整个 Reflection ReAct 框架的"工具总线"。
所有可被 Agent 调用的工具都通过 @register_tool 装饰器注册到此模块的
TOOL_REGISTRY 全局字典中。其他模块（prompt_builder、react_agent）不直接
import 具体工具函数，而是通过此模块提供的查询/执行接口间接访问工具，
从而实现"工具与框架解耦"——新增工具只需写 @register_tool，无需改框架代码。

【核心设计】
- TOOL_REGISTRY: 全局字典，key=工具名, value={handler, desc, params, hints}
- hints 机制：每个工具声明自己的"常见坑/校验规则"，由 prompt_builder 动态注入
  到 system prompt，由 react_agent 在 reflection 提示中动态引用，
  替代了原来在 prompt 中硬编码业务数据的问题。

【被谁依赖】
- tools/order_check.py    → 调用 register_tool 注册自己
- tools/schedule_query.py → 调用 register_tool 注册自己
- core/prompt_builder.py  → 调用 get_tool_prompt_desc / get_tool_hints_text / get_all_tool_names
- core/react_agent.py      → 调用 execute_tool / get_tool_hints
"""

from typing import Dict, Any, Callable, List

# ---------------------------------------------------------------------------
# 全局工具注册表
# 结构: { 工具名: { "handler": 可调用函数, "desc": 描述, "params": 参数说明, "hints": 提示列表 } }
# 所有用 @register_tool 装饰的函数都会被自动录入此字典
# ---------------------------------------------------------------------------
TOOL_REGISTRY: Dict[str, Dict[str, Any]] = {}


def register_tool(
    name: str,
    desc: str,
    params: Dict[str, str],
    hints: List[str] = None,
):
    """
    工具注册装饰器工厂——将一个普通函数注册为 Agent 可调用的工具。

    【函数作用】
    以装饰器形式将函数及其元数据（描述、参数、提示）写入 TOOL_REGISTRY，
    使 Agent 框架能自动发现、描述、调用该工具。

    【参数说明】
    - name   : 工具唯一标识名，Agent 在 Action 中以此名称调用工具。
               来源：由工具开发者自行定义，需保证全局唯一。
    - desc   : 工具功能的一句话描述，会被拼入 system prompt 告知 LLM。
               来源：由工具开发者根据工具功能撰写。
    - params : 参数说明字典 {参数名: "类型+说明"}，用于 prompt 展示和格式校验。
               来源：由工具开发者根据函数签名撰写。
    - hints  : 工具使用提示/常见坑列表，动态注入到 prompt 指导 LLM 反思。
               这是本框架解决"prompt 硬编码"问题的关键——每个工具自己声明
               自己的注意事项，框架从 registry 动态获取，无需在 prompt 模板里写死。
               来源：由工具开发者根据业务经验撰写。

    【谁会调用】
    此函数是装饰器工厂，由各工具模块在定义函数时使用：
    - tools/order_check.py    → @register_tool(name="check_order", ...)
    - tools/schedule_query.py → @register_tool(name="get_schedule", ...)

    【返回值】
    返回装饰器函数 wrapper，wrapper 返回原函数本身（不改变函数行为）。

    【关键代码解析】
    wrapper 内部：
      TOOL_REGISTRY[name] = { "handler": func, "desc": desc, "params": params, "hints": hints or [] }
      → 将函数和元数据一起存入全局注册表，key 为工具名。
      → hints 默认为空列表，工具不提供 hints 时不会报错。
    """
    def wrapper(func: Callable):
        # 将函数连同元数据一起写入全局注册表
        TOOL_REGISTRY[name] = {
            "handler": func,       # 实际可调用的函数，execute_tool 时通过此字段调用
            "desc": desc,           # 工具描述，用于 prompt 中告知 LLM 此工具的用途
            "params": params,       # 参数说明，用于 prompt 中展示参数格式
            "hints": hints or [],   # 使用提示/常见坑，用于动态注入 prompt 指导反思
        }
        return func  # 装饰器不改变原函数行为，原函数仍可正常被 Python 直接调用
    return wrapper


def get_tool_prompt_desc() -> str:
    """
    生成工具列表的 prompt 文本，用于注入到 system prompt 中告知 LLM 有哪些工具可用。

    【函数作用】
    遍历 TOOL_REGISTRY，将每个工具的名称、描述、参数格式化为
    "- check_order: 核验订单... 参数(order_id: str, pay_amount: int)" 形式，
    拼成多行文本，供 prompt_builder 填入模板的 {tool_list} 占位符。

    【参数】
    无参数，直接从全局 TOOL_REGISTRY 读取。

    【谁会调用】
    - core/prompt_builder.py → build_system_prompt() 中调用，将结果填入 prompt 模板

    【关键代码解析】
    p_str = ", ".join(f"{k}: {v}" for k, v in meta["params"].items())
      → 将 params 字典 {order_id: "str", pay_amount: "int"} 拼为
        "order_id: str 订单编号, pay_amount: int 用户填报支付金额"
    blocks.append(f"- {name}: {meta['desc']} 参数({p_str})")
      → 每个工具一行，格式: "- 工具名: 描述 参数(参数列表)"
    """
    blocks = []
    for name, meta in TOOL_REGISTRY.items():
        # 将参数字典拼接为 "key: value, key: value" 格式
        p_str = ", ".join(f"{k}: {v}" for k, v in meta["params"].items())
        # 每个工具生成一行描述
        blocks.append(f"- {name}: {meta['desc']} 参数({p_str})")
    return "\n".join(blocks)


def get_tool_hints_text() -> str:
    """
    汇总所有工具的 hints 文本，用于注入到 system prompt 的"工具使用提示"区域。

    【函数作用】
    遍历 TOOL_REGISTRY，将每个工具的 hints 列表用分号连接，
    格式化为 "- check_order: hint1; hint2; hint3" 形式。
    如果没有任何工具提供 hints，返回"无"。

    【参数】
    无参数，直接从全局 TOOL_REGISTRY 读取。

    【谁会调用】
    - core/prompt_builder.py → build_system_prompt() 中调用，将结果填入 {tool_hints} 占位符

    【关键代码解析】
    if meta["hints"]:
      → 只有提供了 hints 的工具才会被列出，没有 hints 的工具不占篇幅
    hints_str = "; ".join(meta["hints"])
      → 同一工具的多条 hints 用分号连接，避免换行过多
    return "\n".join(lines) if lines else "无"
      → 空时返回"无"而非空串，让 LLM 明确知道没有额外提示
    """
    lines = []
    for name, meta in TOOL_REGISTRY.items():
        if meta["hints"]:
            # 同一工具的多条 hints 用分号连接
            hints_str = "; ".join(meta["hints"])
            lines.append(f"- {name}: {hints_str}")
    return "\n".join(lines) if lines else "无"


def get_tool_hints(tool_name: str) -> List[str]:
    """
    获取单个工具的 hints 列表，用于 reflection 提示中动态注入当前工具的校验规则。

    【函数作用】
    根据工具名从 TOOL_REGISTRY 中取出该工具的 hints 列表。
    与 get_tool_hints_text() 不同，此函数返回原始列表（非格式化文本），
    便于 react_agent 在构建 reflection 提示时只注入当前工具的提示，
    而非全部工具的提示——避免信息过载。

    【参数说明】
    - tool_name : 要查询的工具名称，来源为 Agent 当前轮解析出的 parsed.action_name

    【谁会调用】
    - core/react_agent.py → _build_reflect_prompt() 中调用，
      将当前调用工具的 hints 注入到 reflection 提示的"校验提示"部分

    【返回值】
    List[str] — 该工具的 hints 列表；工具不存在时返回空列表 []
    """
    if tool_name in TOOL_REGISTRY:
        return TOOL_REGISTRY[tool_name].get("hints", [])
    return []


def get_all_tool_names() -> List[str]:
    """
    获取所有已注册工具的名称列表，用于 prompt 中提示 LLM 有几个工具、分别叫什么。

    【函数作用】
    从 TOOL_REGISTRY 的 keys 中提取工具名列表，
    供 prompt_builder 在模板中填充"可用工具共 N 个：xxx、yyy"。

    【参数】
    无参数。

    【谁会调用】
    - core/prompt_builder.py → build_system_prompt() 中调用，
      用 "、".join(get_all_tool_names()) 生成工具名枚举，
      用 len(get_all_tool_names()) 获取工具数量

    【返回值】
    List[str] — 所有注册工具名的列表，如 ["check_order", "get_schedule"]
    """
    return list(TOOL_REGISTRY.keys())


def execute_tool(tool_name: str, kwargs: Dict[str, Any]) -> str:
    """
    执行指定工具，并返回其结果字符串。

    【函数作用】
    Agent 解析出 Action 后，调用此函数执行对应工具。
    内部从 TOOL_REGISTRY 取出 handler 函数，用 **kwargs 展开参数调用，
    并将返回值转为字符串。异常不会上抛，而是返回 [ToolRunErr] 前缀的错误信息，
    让 Agent 能通过 Observation 感知到工具执行失败。

    【参数说明】
    - tool_name : 要执行的工具名，来源为 Agent 解析 LLM 输出得到的 parsed.action_name
    - kwargs    : 传给工具函数的参数字典，来源为 Agent 解析 LLM 输出得到的 parsed.action_args
                  如 {"order_id": "ORD001", "pay_amount": 300}

    【谁会调用】
    - core/react_agent.py → run() 主循环中，解析到 Action 后调用
      obs = execute_tool(parsed.action_name, parsed.action_args)

    【关键代码解析】
    if tool_name not in TOOL_REGISTRY:
        return f"[ToolError] 无此工具:{tool_name}"
      → 工具名不在注册表中时，返回错误信息而非抛异常，
        Agent 可在 Observation 中看到"无此工具"并自行修正

    res = TOOL_REGISTRY[tool_name]["handler"](**kwargs)
      → **kwargs 将字典展开为关键字参数传给实际函数，
        如 handler(order_id="ORD001", pay_amount=300)

    except Exception as e:
        return f"[ToolRunErr] {str(e)}"
      → 工具执行异常（如参数类型错误）同样不抛异常，
        返回 [ToolRunErr] 前缀信息，Agent 可在反思中纠正
    """
    if tool_name not in TOOL_REGISTRY:
        # 工具不存在 → 返回错误标记，让 Agent 通过 Observation 感知
        return f"[ToolError] 无此工具: {tool_name}"
    try:
        # 从注册表取出 handler 函数，用字典展开调用
        res = TOOL_REGISTRY[tool_name]["handler"](**kwargs)
        return str(res)  # 统一转为字符串，方便 Agent 作为 Observation 处理
    except Exception as e:
        # 工具执行异常 → 返回错误标记而非抛异常，保持 Agent 循环稳定
        return f"[ToolRunErr] {str(e)}"
