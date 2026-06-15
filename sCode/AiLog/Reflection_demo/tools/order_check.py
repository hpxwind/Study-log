"""
order_check.py — 订单核验工具

【模块作用】
提供 check_order 工具函数，核验订单的支付金额和状态。
此模块被 import 时，模块级别的 @register_tool 装饰器会自动执行，
将 check_order 注册到 config/tool_registry.py 的 TOOL_REGISTRY 中。

【核心设计】
- ORDER_DB : 模拟订单数据库（实际项目中替换为真实数据库查询）
- @register_tool 的 hints 参数声明了此工具的常见坑：
  1. pay_amount 必须与实际金额一致 → 否则会返回"金额不匹配"
  2. order_id 必须存在 → 否则会返回"校验失败"
  3. 注意订单状态 → 已退款/待付款等状态需关注
  这些 hints 会被动态注入到 prompt 中，替代原来硬编码的"ORD001金额=299"

【被谁依赖】
- tools/__init__.py → from .order_check import check_order（触发注册）
- core/react_agent.py → import tools.order_check（触发注册）
"""

from config.tool_registry import register_tool

# ---------------------------------------------------------------------------
# 模拟订单数据库
# 实际项目中替换为真实数据库查询（如 MySQL / MongoDB / API 调用等）
# ---------------------------------------------------------------------------
ORDER_DB = {
    "ORD001": {"goods": "机械键盘", "real_pay": 299, "status": "已付款"},
    "ORD002": {"goods": "无线鼠标", "real_pay": 89, "status": "待付款"},
    "ORD003": {"goods": "显示器支架", "real_pay": 159, "status": "已退款"}
}


@register_tool(
    name="check_order",
    desc="核验订单支付金额与状态，必须同时传入订单号order_id、用户填写金额pay_amount",
    params={
        "order_id": "str 订单编号",
        "pay_amount": "int 用户填报支付金额"
    },
    hints=[
        # hint 1: 金额匹配规则——LLM 在反思时如果看到"金额不匹配"的 Observation，
        #         应该想到"可能是 pay_amount 填错了"，而非盲目重试
        "pay_amount必须与订单实际金额完全一致，否则会金额不匹配报错",
        # hint 2: 订单号存在性——LLM 在反思时应检查 order_id 是否拼写正确
        "order_id必须存在于系统内，不存在的订单号会校验失败",
        # hint 3: 状态关注——即使金额匹配，订单状态也需要纳入最终答案
        "注意订单状态，已退款/待付款等状态需一并关注",
    ]
)
def check_order(order_id: str, pay_amount):
    """
    核验订单的支付金额与状态。

    【函数作用】
    根据订单号查找订单，比对用户填写的支付金额与实际金额是否一致，
    返回核验结果字符串。此函数被 @register_tool 装饰后，
    由 tool_registry.execute_tool() 通过 TOOL_REGISTRY["check_order"]["handler"] 调用。

    【参数说明】
    - order_id   : 订单编号，如 "ORD001"
                   来源：Agent 从 LLM 输出中解析的 action_args["order_id"]
    - pay_amount : 用户填报的支付金额
                   来源：Agent 从 LLM 输出中解析的 action_args["pay_amount"]
                   注意：LLM 输出经 output_parser 解析后，纯数字已转为 int

    【谁会调用】
    - config/tool_registry.py → execute_tool() 中通过
      TOOL_REGISTRY["check_order"]["handler"](**kwargs) 间接调用

    【关键代码解析】
    pay_amount = int(pay_amount)
      → 防御性类型转换，确保 pay_amount 是 int（即使 LLM 输出的是字符串数字）

    if order_id not in ORDER_DB:
        return f"校验失败：不存在订单{order_id}"
      → 订单不存在时直接返回失败，不抛异常，
        让 Agent 通过 Observation 看到"不存在"并可能修正订单号

    if real != pay_amount:
        return f"金额不匹配！订单标准实付{real}，用户实付{pay_amount}，订单状态：{status}"
      → 金额不匹配时返回详细信息（含实际金额），触发 LLM 反思"金额填错了"
      → 这是 Reflection 机制最有价值的场景——LLM 看到不匹配后会主动修正 pay_amount
    """
    # 防御性类型转换，保证数值比较时类型一致
    pay_amount = int(pay_amount)

    # 检查订单是否存在
    if order_id not in ORDER_DB:
        return f"校验失败：不存在订单{order_id}"

    # 取出订单的实际金额和状态
    real = ORDER_DB[order_id]["real_pay"]
    status = ORDER_DB[order_id]["status"]

    # 比对金额是否一致
    if real != pay_amount:
        # 金额不匹配 → 返回详细信息，提示 LLM 反思修正
        # 包含"标准实付"和"用户实付"的对比，帮助 LLM 理解错误原因
        return f"金额不匹配！订单标准实付{real}，用户实付{pay_amount}，订单状态：{status}"

    # 金额匹配 → 返回核验通过的完整信息
    return f"校验通过，商品：{ORDER_DB[order_id]['goods']}，标准实付{real}，用户实付{pay_amount}，订单状态：{status}"
