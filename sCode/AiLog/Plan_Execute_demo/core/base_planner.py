"""
base_planner.py — 规划器公共基类
================================
抽取三种规划器的公共逻辑：
  - 结构化历史记录管理（RoundRecord）
  - 通用工具执行（通过 tool_registry 动态查找）
  - 历史序列化为 Prompt 可读字符串

子类只需实现 solve() 方法即可成为完整的规划 Agent。
"""

from typing import Dict, List, Union, Optional
import json
from config.tool_registry import get_tool_function
import mock_llm

# ──────────────────────────────────────
# 全局格式标签常量，所有规划器共用
# ──────────────────────────────────────
TAG_THOUGHT = "Thought"
TAG_ACTION = "Action"
TAG_OBSERVATION = "Observation"
TAG_FINAL = "FinalAnswer"
TAG_PLAN = "Plan"

# 历史轮次之间的分割线，方便 LLM 区分不同轮次
SPLIT_SEP = "\n=====单轮分割=====\n"

# 每一轮的结构化记录类型：{thought, action, observation}
RoundRecord = Dict[str, Union[str, Dict, None]]


class BasePlanner:
    """
    规划器基类，封装 Agent 的通用基础设施。

    子类：
        - ChainPlanner        链式规划（逐步 Reason→Act→Observe 循环）
        - HierarchicalPlanner 分层规划（规划→独立执行→汇总）
        - HolisticPlanner     整体规划（含依赖规划→自动传参执行→直接输出）

    参数:
        max_tool_loop: int  — 最大工具调用轮数，防止死循环
    """

    def __init__(self, max_tool_loop: int = 5):
        self.MAX_TOOL_LOOP = max_tool_loop
        # 结构化历史列表，每项是一个 RoundRecord 字典
        self.history: List[RoundRecord] = []

    # ──────────────────────────────────────
    # 历史管理
    # ──────────────────────────────────────

    def clear_history(self):
        """清空历史记录，通常在每次 solve() 开始时调用"""
        self.history = []

    def format_history_for_prompt(self) -> str:
        """
        将内存中的结构化历史转为 LLM 可读的文本。

        逻辑：遍历 self.history 列表，把每轮的 thought/action/observation
        拼成标准 ReAct 格式字符串，轮次之间用 SPLIT_SEP 分隔。

        返回:
            str — 可直接嵌入 prompt 的历史上下文文本
        """
        block_list = []
        for rec in self.history:
            # action 字典转 JSON 字符串，ensure_ascii=False 保留中文
            act_str = json.dumps(rec["action"], ensure_ascii=False) if rec["action"] else ""
            block = (
                f"{TAG_THOUGHT}:{rec['thought']}\n"
                f"{TAG_ACTION}:{act_str}\n"
                f"{TAG_OBSERVATION}:{rec['observation']}"
            )
            block_list.append(block)
        return SPLIT_SEP.join(block_list)

    # ──────────────────────────────────────
    # 工具执行
    # ──────────────────────────────────────

    def run_tool_and_get_obs(self, tool_name: str, params: dict) -> str:
        """
        通用工具执行入口。根据工具名从 TOOL_REGISTRY 查找函数并调用。

        参数:
            tool_name: str   — 工具名（需与 TOOL_REGISTRY 中的 key 一致）
            params: dict     — 工具参数字典，会以 **params 解包传给工具函数

        返回:
            str — 工具执行结果字符串；异常时返回错误信息

        调用方:
            ChainPlanner.solve()        每轮 Act 阶段调用
            HierarchicalPlanner.solve() 执行阶段逐条调用
        """
        tool_func = get_tool_function(tool_name)
        if not callable(tool_func):
            return f"{TAG_OBSERVATION}错误：不存在工具 {tool_name}"
        try:
            result = tool_func(**params)
            return str(result)
        except Exception as e:
            return f"{TAG_OBSERVATION}执行异常：{repr(e)}"

    # ──────────────────────────────────────
    # 抽象方法：子类必须实现
    # ──────────────────────────────────────

    def solve(self, question: str) -> str:
        """
        规划+执行主入口，子类必须实现。

        参数:
            question: str — 用户原始问题

        返回:
            str — 最终答案或超限提示
        """
        raise NotImplementedError("子类必须实现 solve()")
