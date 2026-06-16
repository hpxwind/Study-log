"""
holistic_planner.py — 整体规划器（Holistic Planning）
======================================================
与分层规划的核心区别：
  - 分层规划：步骤参数在规划时就写死，步骤之间完全独立，需要额外的汇总LLM调用
  - 整体规划：步骤之间可以存在依赖关系，后续步骤的参数可以引用前序步骤的输出，
             执行时自动解析引用并传参，无需额外的汇总阶段

执行流程：
  阶段1 — Planning（规划）：
      LLM 一次性生成完整的步骤列表，步骤间可通过 $step_N 引用前序输出。
      例如：[{"step":1, "tool":"info_search", "params":{"keyword":"react"}},
             {"step":2, "tool":"calculator", "params":{"num1":"$step1","num2":45,"operator":"*"}}]

  阶段2 — Execution（执行）：
      按顺序执行每个步骤，遇到 $step_N 引用时自动替换为对应步骤的 Observation 结果。

特点：
  - 只需 1 次 LLM 调用（规划），执行阶段不调 LLM，无需汇总
  - 步骤间可传递中间结果，解决"上一步输出是下一步输入"的问题
  - 适合需要多步串联、中间结果需传递的任务

继承 BasePlanner，复用历史管理和工具执行能力。
"""

import re
from core.base_planner import BasePlanner, TAG_FINAL
from core.prompt_builder import build_holistic_plan_prompt
from core.output_parser import parse_plan_response
import mock_llm


class HolisticPlanner(BasePlanner):
    """
    整体规划器：一次性规划含步骤依赖，执行时自动传参，无需额外汇总。

    继承:
        BasePlanner（历史管理、工具执行）

    新增属性:
        无额外属性

    调用方:
        test_main.py 中通过 mode="holistic" 选择实例化
    """

    def solve(self, question: str) -> str:
        """
        整体规划主流程：规划 → 执行（含引用解析）→ 直接输出答案。

        流程:
            1. 清空历史
            2. 【规划阶段】构造规划 prompt → 调 LLM → 解析出步骤列表（含依赖引用）
            3. 【执行阶段】按序执行步骤：
               - 遇到 $step_N 引用时，自动替换为第N步的 Observation 结果
               - 将每步的 observation 存入 step_results 字典，供后续步骤引用
            4. 最后一步的 Observation 直接作为最终答案返回（无需汇总 LLM 调用）

        参数:
            question: str — 用户原始问题

        返回:
            str — 最终答案 或 错误/超限提示
        """
        self.clear_history()
        print(f"===== 【整体规划】开始处理问题：{question} =====\n")

        # ═══════════════════════════════════════
        # 阶段1：Planning — 让 LLM 一次性生成含依赖的完整计划
        # ═══════════════════════════════════════
        print("【阶段1：规划】生成执行计划（含步骤依赖）...")
        plan_prompt = build_holistic_plan_prompt(question)
        plan_raw = mock_llm.call_model(plan_prompt)

        # 复用 parse_plan_response 解析步骤列表
        plan_steps = parse_plan_response(plan_raw)

        if not plan_steps:
            print(f"⚠️ 未解析到有效计划，LLM 原始输出：\n{plan_raw}\n")
            # 尝试提取 FinalAnswer（LLM 可能认为无需工具直接回答）
            for line in plan_raw.strip().split("\n"):
                line = line.strip()
                if line.startswith(f"{TAG_FINAL}:"):
                    return line.replace(f"{TAG_FINAL}:", "").strip()
            return "⚠️ 规划失败，LLM 未能生成有效的执行步骤"

        # 打印规划结果
        print(f"📋 生成 {len(plan_steps)} 个步骤：")
        for step in plan_steps:
            print(f"   步骤{step['step']}: 工具={step['tool']}, 参数={step['params']}, 原因={step.get('reason', '')}")

        # ═══════════════════════════════════════
        # 阶段2：Execution — 按序执行，自动解析步骤间引用
        # ═══════════════════════════════════════
        print(f"\n【阶段2：执行】按序执行 {len(plan_steps)} 个步骤（自动解析依赖）...")

        # 存储每步的执行结果，key=步骤号，value=Observation字符串
        step_results: dict = {}
        final_observation = ""

        for step in plan_steps:
            tool_name = step["tool"]
            raw_params = step["params"]
            step_num = step["step"]

            # ── 核心：解析 $step_N 引用 ──
            # 将参数中所有 "$step_N" 替换为第N步的 Observation 结果
            resolved_params = self._resolve_references(raw_params, step_results)

            print(f"\n   ▶ 步骤{step_num}: 调用 {tool_name}({resolved_params})")
            if resolved_params != raw_params:
                print(f"     （引用解析: {raw_params} → {resolved_params}）")

            # 调用基类的通用工具执行方法
            obs = self.run_tool_and_get_obs(tool_name, resolved_params)
            print(f"   ◀ 结果: {obs}")

            # 记录到结果字典和历史
            step_results[step_num] = obs
            final_obsation = obs  # 不断更新，最终保留最后一步的观测
            self.history.append({
                "thought": f"执行步骤{step_num}: {step.get('reason', '')}",
                "action": {"name": tool_name, "parameters": resolved_params},
                "observation": obs
            })

        # ═══════════════════════════════════════
        # 无需汇总阶段 — 最后一步的 Observation 就是最终答案
        # ═══════════════════════════════════════
        print(f"\n✅ {TAG_FINAL}：{final_obsation}")
        return final_obsation

    def _resolve_references(self, params: dict, step_results: dict) -> dict:
        """
        解析参数中的步骤引用，将 $step_N 替换为第N步的 Observation 结果。

        引用语法：
          "$step1"  — 引用第1步的完整 Observation 字符串
          "$step2"  — 引用第2步的完整 Observation 字符串

        解析逻辑：
          1. 遍历 params 字典的每个值
          2. 若值为字符串且匹配 "$step_N" 格式，则替换为 step_results[N]
          3. 若被引用的步骤尚无结果（不应发生），保留原始引用字符串
          4. 非字符串值（int/float/bool）不做处理，直接保留

        参数:
            params: dict       — 原始参数字典（来源：parse_plan_response() 解析的步骤）
            step_results: dict — 已执行步骤的结果 {步骤号: Observation字符串}

        返回:
            dict — 引用已解析的新参数字典

        调用方:
            self.solve() 执行阶段每步调用
        """
        resolved = {}
        for key, value in params.items():
            if isinstance(value, str):
                # 匹配 $step_N 格式的引用
                match = re.match(r"^\$step(\d+)$", value.strip())
                if match:
                    ref_step = int(match.group(1))
                    # 从 step_results 中查找对应步骤的结果
                    if ref_step in step_results:
                        resolved[key] = step_results[ref_step]
                    else:
                        # 被引用步骤尚未执行，保留原始引用（不应发生）
                        print(f"   ⚠️ 引用 $step{ref_step} 未找到对应结果，保留原始值")
                        resolved[key] = value
                else:
                    resolved[key] = value
            else:
                # 非字符串类型（int/float/bool）直接保留
                resolved[key] = value
        return resolved
