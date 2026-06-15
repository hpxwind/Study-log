"""
tools/__init__.py — 工具包初始化

【模块作用】
将 tools 包下的所有工具模块导入到包命名空间，使其在被 import 时
触发各工具模块级别的 @register_tool 装饰器执行，完成工具注册。

【设计说明】
Python 的 import 机制保证：当执行 `import tools.order_check` 时，
会先执行 `tools/__init__.py`，再执行 `tools/order_check.py`。
因此这里 from .order_check import check_order 的目的不是"使用" check_order，
而是触发 order_check.py 模块加载，使其 @register_tool 装饰器执行，
将工具注册到 TOOL_REGISTRY。

同理，core/react_agent.py 中也有 `import tools.order_check` 的写法，
目的是相同的——确保在 Agent 运行前所有工具已注册完毕。

【被谁依赖】
- core/react_agent.py → `import tools.order_check` / `import tools.schedule_query`
  触发此 __init__.py 执行（如果之前未 import 过 tools 包）
"""

from .order_check import check_order        # 触发 @register_tool → 注册 check_order
from .schedule_query import get_schedule    # 触发 @register_tool → 注册 get_schedule

__all__ = ["check_order", "get_schedule"]
