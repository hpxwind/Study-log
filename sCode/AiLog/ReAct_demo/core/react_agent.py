from typing import Dict, List, Union, Optional
import json
from core.prompt_builder import build_react_full_prompt
from core.output_parser import parse_llm_response
from config.tool_registry import get_tool_function
import mock_llm
from dotenv import load_dotenv

load_dotenv()

# 全局标记常量，统一管控格式
TAG_THOUGHT = "Thought"
TAG_ACTION = "Action"
TAG_OBSERVATION = "Observation"
TAG_FINAL = "FinalAnswer"
SPLIT_SEP = "\n=====单轮分割=====\n"

# 结构化历史单轮类型
RoundRecord = Dict[str, Union[str, Dict, None]]

class ReActCoreAgent:
    def __init__(self, max_tool_loop: int=3):
        self.MAX_TOOL_LOOP = max_tool_loop
        # 结构化历史：每一轮 {thought, action, observation}
        self.history: List[RoundRecord] = []

    def format_history_for_prompt(self) -> str:
        """结构化历史转为Prompt可读字符串"""
        block_list = []
        # 内存里存的是字典列表，大模型只能读字符串，所以需要序列化拼接
        for rec in self.history:
            act_str = json.dumps(rec["action"], ensure_ascii=False) if rec["action"] else ""
            block = (
                f"{TAG_THOUGHT}:{rec['thought']}\n"
                f"{TAG_ACTION}:{act_str}\n"
                f"{TAG_OBSERVATION}:{rec['observation']}"
            )
            block_list.append(block)
        return SPLIT_SEP.join(block_list)

    def run_tool_and_get_obs(self, tool_name: str, params: dict) -> str:
        """通用工具执行，动态解参，无硬编码if"""
        tool_func = get_tool_function(tool_name) # 拿到工具的函数名
        if not callable(tool_func):
            return f"{TAG_OBSERVATION}错误：不存在工具 {tool_name}"
        try:
            # 字典参数一键解包传给工具函数
            result = tool_func(**params)
            return str(result)
        except Exception as e:
            return f"{TAG_OBSERVATION}执行异常：{repr(e)}"

    def solve(self, question: str) -> str:
        # 完整 ReAct 循环
        print(f"=====开始处理问题：{question}=====\n")
        for loop_step in range(self.MAX_TOOL_LOOP):
            step_num = loop_step + 1
            print(f"----------第{step_num}轮ReAct迭代----------")
            try:
                # 1. Reason 推理
                hist_str = self.format_history_for_prompt()
                prompt = build_react_full_prompt(question, hist_str)
                llm_raw_out = mock_llm.call_model(prompt)
                thought, action_info, final_ans = parse_llm_response(llm_raw_out)
                print(f"【{TAG_THOUGHT}】{thought}")

                # 分支1：直接给出最终答案，结束循环
                if final_ans is not None and final_ans.strip():
                    print(f"\n✅ ReAct迭代结束，{TAG_FINAL}：{final_ans}")
                    return final_ans.strip()

                # 分支2：调用工具
                if action_info is not None:
                    tool_name, params = action_info
                    print(f"【{TAG_ACTION}】工具:{tool_name} 参数:{params}")
                    # 2.Act + 3.Observe
                    observation = self.run_tool_and_get_obs(tool_name, params)
                    print(f"【{TAG_OBSERVATION}】{observation}\n")

                    # 存入结构化历史
                    self.history.append({
                        "thought": thought,
                        "action": {"name": tool_name, "parameters": params},
                        "observation": observation
                    })

            except Exception as e:
                err_msg = f"本轮推理异常跳过：{repr(e)}"
                print(f"⚠️ {err_msg}\n")
                # 异常填充空记录防止流程断裂
                self.history.append({
                    "thought": f"解析出错:{e}",
                    "action": None,
                    "observation": err_msg
                })
        # 循环耗尽
        return f"⚠️ 已达最大{self.MAX_TOOL_LOOP}轮迭代，未能生成有效答案"