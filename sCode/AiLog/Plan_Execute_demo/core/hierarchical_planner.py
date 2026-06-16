"""
hierarchical_planner.py — 分层规划器（Hierarchical Planning）
============================================================
将"规划"和"执行"分为两个独立阶段：

  阶段1 — Planning（规划）：
      LLM 一次性生成完整的步骤列表（Plan），每步指定工具名和参数。
      例如：[{"step":1, "tool":"calculator", "params":{"num1":123,"num2":45,"operator":"*"}},
             {"step":2, "tool":"info_search", "params":{"keyword":"react"}}]

  阶段2 — Execution（执行）：
      Agent 按顺序逐条执行 Plan 中的步骤，收集每步的 Observation。

  阶段3 — Synthesis（汇总）：
      将所有 Observation 交给 LLM，由 LLM 整合生成最终答案。

特点：
  - 规划与执行解耦，步骤一次性确定，中途不调整
  - 规划只需 1 次 LLM 调用，执行阶段不调 LLM，节省 token
  - 适合"步骤间无依赖、可预判"的任务；不适合"上一步结果决定下一步"的场景

继承 BasePlanner，复用历史管理和工具执行能力。
"""

from core.base_planner import BasePlanner, TAG_OBSERVATION, TAG_FINAL
from core.prompt_builder import build_hierarchical_plan_prompt, build_hierarchical_synthesis_prompt
from core.output_parser import parse_plan_response
import mock_llm


class HierarchicalPlanner(BasePlanner):
    """
    分层规划器：先整体规划，再顺序执行，最后汇总。
    继承:
        BasePlanner（历史管理、工具执行）

    新增属性:
        无额外属性

    调用方:
        test_main.py 中通过 mode="hierarchical" 选择实例化
    """

    def solve(self, question: str) -> str:
        """
        分层规划主流程：规划 → 执行 → 汇总。

        流程:
            1. 清空历史
            2. 【规划阶段】构造规划 prompt → 调 LLM → 解析出步骤列表
            3. 【执行阶段】遍历步骤列表，逐条执行工具，收集 observation
            4. 【汇总阶段】将所有 observation 拼入汇总 prompt → 调 LLM → 返回最终答案

        参数:
            question: str — 用户原始问题

        返回:
            str — 最终答案 或 错误/超限提示
        """
        self.clear_history()
        print(f"===== 【分层规划】开始处理问题：{question} =====\n")

        # ═══════════════════════════════════════
        # 阶段1：Planning — 让 LLM 一次性生成完整计划
        # ═══════════════════════════════════════
        print("【阶段1：规划】生成执行计划...")
        plan_prompt = build_hierarchical_plan_prompt(question)
        plan_raw = mock_llm.call_model(plan_prompt)

        # 解析 LLM 输出，提取步骤列表
        # 每个步骤格式: {"step": int, "tool": str, "params": dict, "reason": str}
        plan_steps = parse_plan_response(plan_raw)

        if not plan_steps:
            # LLM 未生成有效计划，可能认为无需工具，直接尝试从原始输出中提取答案
            print(f"⚠️ 未解析到有效计划，LLM 原始输出：\n{plan_raw}\n")
            return f"⚠️ 规划失败，LLM 未能生成有效的执行步骤"

        # 打印规划结果
        print(f"📋 生成 {len(plan_steps)} 个步骤：")
        for step in plan_steps:
            print(f"   步骤{step['step']}: 工具={step['tool']}, 参数={step['params']}, 原因={step.get('reason', '')}")

        # ═══════════════════════════════════════
        # 阶段2：Execution — 按顺序执行每个步骤
        # ═══════════════════════════════════════
        print(f"\n【阶段2：执行】按序执行 {len(plan_steps)} 个步骤...")
        observations = []  # 收集每步的执行结果

        for step in plan_steps:
            tool_name = step["tool"]
            params = step["params"]
            step_num = step["step"]

            print(f"\n   ▶ 步骤{step_num}: 调用 {tool_name}({params})")

            # 调用基类的通用工具执行方法
            obs = self.run_tool_and_get_obs(tool_name, params)
            print(f"   ◀ 结果: {obs}")

            # 记录到结构化历史和观察列表
            observations.append({
                "step": step_num,
                "tool": tool_name,
                "params": params,
                "observation": obs
            })
            self.history.append({
                "thought": f"执行步骤{step_num}: {step.get('reason', '')}",
                "action": {"name": tool_name, "parameters": params},
                "observation": obs
            })

        # ═══════════════════════════════════════
        # 阶段3：Synthesis — 汇总所有观察，生成最终答案
        # ═══════════════════════════════════════
        print("\n【阶段3：汇总】整合所有观察结果...")
        synthesis_prompt = build_hierarchical_synthesis_prompt(question, observations)
        synthesis_raw = mock_llm.call_model(synthesis_prompt)

        # 尝试提取 FinalAnswer 行；若无则直接返回全部文本
        final_answer = self._extract_final_answer(synthesis_raw)
        print(f"\n✅ {TAG_FINAL}：{final_answer}")
        return final_answer

    def _extract_final_answer(self, text: str) -> str:
        """
        从汇总阶段的 LLM 输出中提取 FinalAnswer。

        逻辑:
            逐行扫描文本，查找 "FinalAnswer:" 开头的行；
            若找不到，则返回整段文本作为答案（兜底）。

        参数:
            text: str — LLM 的原始输出文本

        返回:
            str — 提取到的最终答案

        调用方:
            self.solve() 阶段3 汇总后调用
        """
        for line in text.strip().split("\n"):
            line = line.strip()
            if line.startswith(f"{TAG_FINAL}:"):
                return line.replace(f"{TAG_FINAL}:", "").strip()
        # 兜底：找不到标签则返回原文
        return text.strip()
