"""
test_main.py — 测试入口
========================
支持三种规划模式的切换测试：
  - chain（链式规划）：经典 ReAct 逐步推理 + 逐步执行
  - hierarchical（分层规划）：先规划独立步骤，再执行，最后汇总
  - holistic（整体规划）：一次规划含步骤依赖，执行时自动传参，无需汇总

通过 PLANNING_MODE 变量一键切换。
"""

from core.chain_planner import ChainPlanner
from core.hierarchical_planner import HierarchicalPlanner
from core.holistic_planner import HolisticPlanner


# ════════════════════════════════════════════════════
# 规划模式切换：修改此变量即可切换
#   "chain"         → 链式规划（逐步 Reason→Act→Observe，每步调LLM）
#   "hierarchical"  → 分层规划（规划→独立执行→汇总，2次LLM调用）
#   "holistic"      → 整体规划（含依赖规划→自动传参执行，1次LLM调用）
# ════════════════════════════════════════════════════
PLANNING_MODE = "holistic"


def create_agent(mode: str = PLANNING_MODE, max_loop: int = 5):
    """
    工厂函数：根据 mode 创建对应的规划器实例。

    参数:
        mode: str     — "chain" / "hierarchical" / "holistic"
                        （来源：PLANNING_MODE 常量或用户传入）
        max_loop: int — 最大执行轮数（来源：调用方指定，默认5）

    返回:
        BasePlanner 子类实例

    调用方:
        test_api_agent()
        interactive_chat()
    """
    if mode == "hierarchical":
        print("🔧 当前模式：分层规划 (Hierarchical)")
        return HierarchicalPlanner(max_tool_loop=max_loop)
    elif mode == "holistic":
        print("🔧 当前模式：整体规划 (Holistic)")
        return HolisticPlanner(max_tool_loop=max_loop)
    else:
        print("🔧 当前模式：链式规划 (Chain)")
        return ChainPlanner(max_tool_loop=max_loop)


def test_api_agent():
    """
    批量自动测试：用预设用例验证当前模式的正确性。
    """
    agent = create_agent()

    test_cases = [
        "123乘以45等于多少",
        "100除以4",
        "2026年高考时间是什么时候",
        "简单介绍一下Python"
    ]

    print(f"========== 批量测试（模式: {PLANNING_MODE}） ==========\n")
    for idx, question in enumerate(test_cases, 1):
        print(f"【测试{idx}】用户问题：{question}")
        result = agent.solve(question)
        print(f"\n【最终答案】{result}\n")
        print("-" * 60 + "\n")


def test_compare_modes():
    """
    对比测试：用同一组问题分别跑三种模式，直观比较效果差异。
    """
    test_cases = [
        "123乘以45等于多少",
        "100除以4",
    ]

    for mode in ["chain", "hierarchical", "holistic"]:
        agent = create_agent(mode)
        print(f"\n{'='*60}")
        print(f"  模式: {mode.upper()}")
        print(f"{'='*60}\n")

        for question in test_cases:
            print(f"问题：{question}")
            result = agent.solve(question)
            print(f"答案：{result}\n")
        print("-" * 60)


def interactive_chat():
    """
    交互式手动输入测试。
    """
    agent = create_agent()
    print("===== 交互式对话（输入exit退出）=====")
    while True:
        user_q = input("\n你的问题：")
        if user_q.strip().lower() == "exit":
            print("对话结束")
            break
        ans = agent.solve(user_q)
        print(f"\n回复：{ans}")


if __name__ == "__main__":
    # ── 三种运行方式，取消注释即可切换 ──

    # 1. 批量自动测试（使用 PLANNING_MODE 指定模式）
    test_api_agent()

    # 2. 三种模式对比测试
    # test_compare_modes()

    # 3. 交互式手动输入
    # interactive_chat()
