"""
chain_planner.py — 链式规划器（Chain Planning）
================================================
经典 ReAct 模式：逐步推理、逐步执行。

执行流程：
  Thought → Action → Observation → Thought → Action → ... → FinalAnswer

特点：
  - 每一步都经过 LLM 推理，根据上一步 Observation 动态决定下一步
  - 灵活性高，可在中途修正方向
  - 缺点是每一步都需要调用 LLM，token 开销大

继承 BasePlanner，复用历史管理和工具执行能力。
"""

from core.base_planner import BasePlanner, TAG_THOUGHT, TAG_ACTION, TAG_OBSERVATION, TAG_FINAL
from core.prompt_builder import build_chain_prompt
from core.output_parser import parse_llm_response
import mock_llm


class ChainPlanner(BasePlanner):
    """
    链式规划器：经典 ReAct 逐步推理 + 逐步执行。

    继承:
        BasePlanner（历史管理、工具执行）

    新增:
        无额外属性，完全依赖基类

    调用方:
        test_main.py 中通过 mode="chain" 选择实例化
    """

    def solve(self, question: str) -> str:
        """
        链式规划主循环。

        流程:
            1. 清空历史
            2. 循环 MAX_TOOL_LOOP 轮：
               a. 构造 prompt（包含历史上下文）
               b. 调用 LLM 获取推理结果
               c. 解析 LLM 输出 → thought / action / final_answer
               d. 若有 final_answer → 直接返回
               e. 若有 action → 执行工具，获得 observation
               f. 存入历史，进入下一轮

        参数:
            question: str — 用户原始问题

        返回:
            str — 最终答案 或 超限提示
        """
        self.clear_history()
        print(f"===== 【链式规划】开始处理问题：{question} =====\n")

        for loop_step in range(self.MAX_TOOL_LOOP):
            step_num = loop_step + 1
            print(f"---------- 第{step_num}轮 ReAct 迭代 ----------")

            try:
                # 1) 将结构化历史序列化为文本，拼入 prompt
                hist_str = self.format_history_for_prompt()
                prompt = build_chain_prompt(question, hist_str)

                # 2) 调用 LLM，获取原始文本输出
                llm_raw_out = mock_llm.call_model(prompt)

                # 3) 解析 LLM 输出，提取 thought / action / final_answer
                thought, action_info, final_ans = parse_llm_response(llm_raw_out)
                print(f"【{TAG_THOUGHT}】{thought}")

                # ── 分支A：LLM 认为信息已足够，直接输出最终答案 ──
                if final_ans is not None and final_ans.strip():
                    print(f"\n✅ ReAct 迭代结束，{TAG_FINAL}：{final_ans}")
                    return final_ans.strip()

                # ── 分支B：LLM 需要调用工具获取更多信息 ──
                if action_info is not None:
                    tool_name, params = action_info
                    print(f"【{TAG_ACTION}】工具:{tool_name} 参数:{params}")

                    # 执行工具，获得 Observation
                    observation = self.run_tool_and_get_obs(tool_name, params)
                    print(f"【{TAG_OBSERVATION}】{observation}\n")

                    # 本轮结果存入结构化历史，供下一轮 prompt 使用
                    self.history.append({
                        "thought": thought,
                        "action": {"name": tool_name, "parameters": params},
                        "observation": observation
                    })

            except Exception as e:
                err_msg = f"本轮推理异常跳过：{repr(e)}"
                print(f"⚠️ {err_msg}\n")
                # 异常时填充空记录，防止历史断裂
                self.history.append({
                    "thought": f"解析出错:{e}",
                    "action": None,
                    "observation": err_msg
                })

        # 循环耗尽，仍未得到答案
        return f"⚠️ 已达最大{self.MAX_TOOL_LOOP}轮迭代，未能生成有效答案"
