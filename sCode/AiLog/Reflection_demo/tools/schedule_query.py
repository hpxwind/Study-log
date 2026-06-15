"""
schedule_query.py — 日程查询工具

【模块作用】
提供 get_schedule 工具函数，根据姓名和日期查询日程安排。
此模块被 import 时，模块级别的 @register_tool 装饰器会自动执行，
将 get_schedule 注册到 config/tool_registry.py 的 TOOL_REGISTRY 中。

【核心设计】
- SCHEDULE_DB : 模拟日程数据库（实际项目中替换为真实数据库查询）
- @register_tool 的 hints 参数声明了此工具的常见坑：
  1. 日期格式必须 YYYY-MM-DD → 否则查不到数据
  2. 姓名准确性 → 子串匹配可能误匹配
  3. date 留空行为 → 返回所有日期日程
  这些 hints 会被动态注入到 prompt 中，指导 LLM 正确填写参数

【被谁依赖】
- tools/__init__.py → from .schedule_query import get_schedule（触发注册）
- core/react_agent.py → import tools.schedule_query（触发注册）
"""

from config.tool_registry import register_tool

# ---------------------------------------------------------------------------
# 模拟日程数据库
# 外层 key 为日期（YYYY-MM-DD 格式），值为该日期的日程列表
# 实际项目中替换为真实数据库查询
# ---------------------------------------------------------------------------
SCHEDULE_DB = {
    "2026-06-15": [
        {"user": "张三", "time": "09:00", "event": "项目评审会"},
        {"user": "李四", "time": "14:00", "event": "客户对接"}
    ],
    "2026-06-16": [
        {"user": "张三", "time": "10:00", "event": "技术方案编写"},
        {"user": "王五", "time": "16:00", "event": "设备调试"}
    ]
}


@register_tool(
    name="get_schedule",
    desc="查询人员日程，date必须是YYYY-MM-DD标准格式，user为姓名；date留空则返回全部日期数据",
    params={
        "user": "str 人员姓名",
        "date": "str 日期，格式YYYY-MM-DD，可空"
    },
    hints=[
        # hint 1: 日期格式——这是最常见的参数错误，用户说"6月15号"而 LLM
        #         可能写成 "6-15" 或 "06-15"，必须转为 "2026-06-15"
        "date格式必须严格为YYYY-MM-DD，其他格式会查不到数据",
        # hint 2: 姓名匹配——使用 in 操作做子串匹配，"张"会匹配"张三"
        "user为姓名全称或子串匹配，注意姓名准确性",
        # hint 3: date 留空行为——LLM 需要知道不传 date 时的默认行为
        "date留空会返回该用户所有日期日程",
    ]
)
def get_schedule(user: str, date: str = None):
    """
    查询指定人员的日程安排。

    【函数作用】
    根据姓名（必填）和日期（选填）查询日程，返回匹配的日程列表文本。
    此函数被 @register_tool 装饰后，由 tool_registry.execute_tool()
    通过 TOOL_REGISTRY["get_schedule"]["handler"] 调用。

    【参数说明】
    - user : 人员姓名，支持子串匹配（使用 in 操作符）
             来源：Agent 从 LLM 输出中解析的 action_args["user"]
    - date : 日期，格式必须为 YYYY-MM-DD；为 None 时查询所有日期
             来源：Agent 从 LLM 输出中解析的 action_args["date"]
             注意：如果 LLM 没有输出 date 参数，action_args 中不会有此 key，
             execute_tool(**kwargs) 时 date 使用默认值 None

    【谁会调用】
    - config/tool_registry.py → execute_tool() 中通过
      TOOL_REGISTRY["get_schedule"]["handler"](**kwargs) 间接调用

    【关键代码解析】
    target_dates = SCHEDULE_DB.keys() if not date else [date]
      → date 为 None 时遍历所有日期，否则只查指定日期

    if user in item["user"]:
      → 子串匹配：如 user="张" 会匹配 item["user"]="张三"
        这是有意设计——宽松匹配避免因姓名不全而查无结果

    if not res_list:
        return f"未找到{user}匹配日程"
      → 没有匹配结果时返回提示信息，而非空串或异常，
        让 Agent 通过 Observation 看到"未找到"并可能修正参数
    """
    res_list = []

    # 确定要查询的日期范围：date 为 None → 所有日期；否则只查指定日期
    target_dates = SCHEDULE_DB.keys() if not date else [date]

    for d in target_dates:
        if d not in SCHEDULE_DB:
            # 日期不在数据库中 → 提示无日程（而非跳过，让 LLM 知道日期无效）
            res_list.append(f"日期{d}无任何日程")
            continue
        for item in SCHEDULE_DB[d]:
            # 子串匹配：user 是 item["user"] 的子串即算匹配
            if user in item["user"]:
                res_list.append(f"【{d} {item['time']}】{item['event']}")

    # 没有任何匹配 → 返回提示而非空串
    if not res_list:
        return f"未找到{user}匹配日程"

    # 多条结果用换行拼接
    return "\n".join(res_list)
