"""
react_agent.py — 带 Reflection 自省能力的 ReAct Agent 核心

【模块作用】
实现完整的 ReAct (Reasoning + Acting) 循环，并可选地加入 Reflection（反思/自省）
机制。Agent 在每一轮循环中：
  1. Reason  — 调用 LLM 生成 Thought + Action / FinalAnswer
  2. Act     — 执行工具获得 Observation
  3. Reflect — （可选）让 LLM 反思本次调用成败、任务进度、下一步动作
  4. 将反思结果存入对话历史，下一轮 LLM 能看到历史反思避免重复犯错

【核心设计】
- _generate_with_retry() : 带重试的安全生成器，解析失败时注入原始输出让 LLM 自行纠正
- _build_reflect_prompt() : 动态构建 reflection 提示，注入当前工具的 hints
- 对话历史完整记录 Thought/Action/Observation/Reflection，供 LLM 多轮推理

【被谁依赖】
- test_main.py → 创建 ReActAgentWithReflection 实例并调用 run()

【重要 import 说明】
import tools.order_check
import tools.schedule_query
  → 这两个 import 的目的不是"使用"这两个模块的函数，
    而是触发它们模块级别的 @register_tool 装饰器执行，
    将 check_order 和 get_schedule 注册到 TOOL_REGISTRY 中。
    如果不 import，注册表中就没有任何工具，Agent 无法调用。
"""

from typing import List, Dict

# 触发工具注册——import 即注册，不需要使用模块中的函数
import tools.order_check      # 执行 @register_tool → TOOL_REGISTRY["check_order"] = ...
import tools.schedule_query   # 执行 @register_tool → TOOL_REGISTRY["get_schedule"] = ...

from .prompt_builder import build_system_prompt
from .output_parser import parse_llm_output, ReActOutput
from config.tool_registry import execute_tool, get_tool_hints


class ReActAgentWithReflection:
    """
    带 Reflection 自省能力的 ReAct Agent。

    【类作用】
    封装完整的 ReAct+Reflection 循环逻辑：
    - 管理 chat_history 对话历史
    - 调用 LLM 生成推理和动作
    - 解析 LLM 输出，执行工具
    - 可选地触发 LLM 反思，将反思存入历史

    【实例化参数】
    - llm              : LLM 接口对象，需实现 generate(chat_history) -> str 方法
                         来源：test_main.py 中创建的 MockLLM() 实例
    - enable_reflection : 是否开启 Reflection 模式
                         True  → 每次工具调用后强制 LLM 反思，反思内容存入历史
                         False → 标准无反思 ReAct，工具返回后直接进入下一轮
    - max_loop         : 最大循环轮数，防止无限循环
    - debug            : 是否打印 LLM 原始输出，用于调试解析问题
    """

    def __init__(self, llm, enable_reflection: bool = True, max_loop: int = 5, debug: bool = False):
        self.llm = llm                                # LLM 接口，调用其 generate() 方法获取回复
        self.enable_reflection = enable_reflection     # 是否开启反思模式
        self.max_loop = max_loop                       # 最大循环次数，防止无限循环
        self.debug = debug                             # 是否打印 LLM 原始输出（调试用）
        self.chat_history: List[Dict[str, str]] = []   # 对话历史，每次 run() 时清空重建

    def _add_msg(self, role: str, content: str):
        """
        向对话历史追加一条消息。

        【函数作用】
        封装 self.chat_history.append()，统一消息格式为 {"role": ..., "content": ...}，
        与 OpenAI Chat API 的 messages 格式一致，直接传给 LLM。

        【参数说明】
        - role    : 消息角色，"system" / "user" / "assistant"
                    来源：由各调用处根据消息类型指定
        - content : 消息内容文本
                    来源：system prompt / 用户提问 / LLM 回复 / 纠错提示 / 反思提示等

        【谁会调用】
        - run()                   → 追加 system prompt、用户问题、工具调用记录、反思记录
        - _generate_with_retry()  → 追加解析失败时的原始输出和纠错提示
        """
        self.chat_history.append({"role": role, "content": content})

    def _log_debug(self, tag: str, text: str):
        """
        条件打印调试信息。

        【函数作用】
        当 self.debug=True 时，打印带标签的调试信息（截取前500字符避免刷屏）。
        主要用于观察 LLM 原始输出，排查解析器为何解析失败。

        【参数说明】
        - tag  : 调试标签，如 "LLM-RAW"，便于在输出中定位
                 来源：调用处硬编码
        - text : 要打印的内容，通常是 LLM 的原始回复
                 来源：self.llm.generate() 的返回值

        【谁会调用】
        - _generate_with_retry() → 打印 LLM 每次的原始输出
        """
        if self.debug:
            # 截取前500字符，避免超长 LLM 输出刷屏
            print(f"[DEBUG {tag}] {text[:500]}")

    def _generate_with_retry(self, enforce_reflect=False) -> tuple:
        """
        统一安全生成器——调用 LLM 并解析输出，解析失败时自动重试。

        【函数作用】
        调用 LLM 生成文本，用 parse_llm_output() 解析为 ReActOutput。
        如果解析结果不符合要求（如 Thought 为空、Reflection 为空），
        则将 LLM 原始输出注入对话历史 + 追加格式纠错提示，让 LLM 自行纠正，
        最多重试 retry_cnt 次。重试耗尽时用 LLM 原始输出构造兜底结果。

        【参数说明】
        - enforce_reflect : 是否强制要求 Reflection 输出
                            False（默认）→ 要求 Thought 或 FinalAnswer 非空
                            True          → 要求 Reflection 文本长度 > 5
                            来源：run() 主循环中根据当前阶段传入
                                  - 正常思考阶段 → enforce_reflect=False
                                  - 反思阶段     → enforce_reflect=True

        【谁会调用】
        - run() → 每轮循环调用两次：
                  1. _generate_with_retry(enforce_reflect=False) → 获取 Thought+Action
                  2. _generate_with_retry(enforce_reflect=True)   → 获取 Reflection（仅反思模式）

        【返回值】
        tuple (ReActOutput, raw_text)
          - ReActOutput : 解析后的结构化输出
          - raw_text    : LLM 最后一次的原始输出，用于兜底时注入历史

        【关键代码解析】
        self._add_msg("assistant", resp_text)
          → 解析失败时，先把 LLM 的原始输出以 assistant 角色加入历史，
            这样 LLM 在重试时能看到自己上一次写了什么，理解纠错提示的上下文

        self._add_msg("user", "格式错误！必须以 Thought: 开头...")
          → 然后追加格式纠错提示，告诉 LLM 应该怎么输出

        fallback.thought = last_raw if last_raw.strip() else "推理：..."
          → 重试耗尽时，用 LLM 的原始输出作为兜底 thought，
            而非无意义的泛文本。这样下一轮 LLM 至少能看到上次的意图
        """
        retry_cnt = 2  # 最多重试 2 次
        last_raw = ""  # 记录最后一次 LLM 原始输出，用于兜底

        for i in range(retry_cnt):
            # 调用 LLM 生成回复
            resp_text = self.llm.generate(self.chat_history)
            last_raw = resp_text  # 保存原始输出
            self._log_debug("LLM-RAW", resp_text)  # debug 模式下打印原始输出

            # 解析 LLM 输出为结构化对象
            res = parse_llm_output(resp_text)

            # ---- 普通思考阶段：检查 Thought 或 FinalAnswer ----
            if not enforce_reflect:
                if res.thought or res.final_answer:
                    # 解析成功 → 直接返回
                    return res, last_raw
                # 解析失败 → 将原始输出注入历史，让 LLM 看到自己写了什么
                self._add_msg("assistant", resp_text)
                # 追加格式纠错提示，告诉 LLM 正确的输出格式
                self._add_msg("user", "格式错误！必须以 Thought: 开头写出推理，然后 Action: 调用工具 或 FinalAnswer: 返回答案")

            # ---- 反思阶段：检查 Reflection ----
            else:
                if res.reflection and len(res.reflection.strip()) > 5:
                    # 反思内容有效（非空且超过5字符）→ 返回
                    return res, last_raw
                # 反思解析失败 → 同样注入原始输出 + 纠错提示
                self._add_msg("assistant", resp_text)
                self._add_msg("user", "格式错误！必须以 Reflection: 开头，写三段：1.调用成败 2.任务进度 3.下一步Action")

        # 重试耗尽 → 用 LLM 原始输出构造兜底结果
        # 优先使用原始输出而非无意义泛文本，让下一轮 LLM 至少能看到上次的意图
        fallback = ReActOutput()
        if enforce_reflect:
            fallback.reflection = last_raw if last_raw.strip() else "复盘：检查工具参数是否有误，核对已完成与未完成任务，修正下一步调用"
        else:
            fallback.thought = last_raw if last_raw.strip() else "推理：修正错误参数，补齐未完成任务"
        return fallback, last_raw

    def _build_reflect_prompt(self, obs: str, action_name: str) -> str:
        """
        根据当前工具调用的 Observation 和工具 hints，动态构建 reflection 提示。

        【函数作用】
        在工具执行后，构建一段"要求 LLM 反思"的提示文本。
        关键设计：动态注入当前工具的 hints（常见坑/校验规则），
        让 LLM 在反思时有明确的校验标准，而不是泛泛地"检查参数"。

        【参数说明】
        - obs        : 工具执行的 Observation 结果文本
                       来源：execute_tool(parsed.action_name, parsed.action_args) 的返回值
        - action_name: 当前调用的工具名
                       来源：Agent 解析 LLM 输出得到的 parsed.action_name

        【谁会调用】
        - run() → 开启反思模式时，工具执行后调用：
          reflect_req = self._build_reflect_prompt(obs, parsed.action_name)

        【关键代码解析】
        hints = get_tool_hints(action_name)
          → 从 tool_registry 获取当前工具的 hints 列表，
            如 check_order → ["pay_amount必须与实际金额一致", "order_id必须存在", ...]

        hints_section = "（校验提示：" + "；".join(hints) + "）"
          → 将 hints 用分号连接后加上前缀，如:
            "（校验提示：pay_amount必须与实际金额一致；order_id必须存在；注意订单状态）"
          → 如果没有 hints，hints_section 为空串，不影响提示结构

        "必须以 Reflection: 开头输出。"
          → 明确告诉 LLM 输出格式，减少解析失败概率
        """
        # 从注册表获取当前工具的 hints
        hints = get_tool_hints(action_name)
        hints_section = ""
        if hints:
            # 将 hints 拼为校验提示段落
            hints_section = "（校验提示：" + "；".join(hints) + "）"

        return f"""观测结果：{obs}
硬性三条规则：
1. 写出本次调用成功/失败原因{hints_section}；
2. 罗列已做完、没做完的所有任务；
3. 输出唯一下一步要执行的Action。
必须以 Reflection: 开头输出。"""

    def run(self, user_query: str) -> str:
        """
        Agent 主循环——执行完整的 ReAct+Reflection 推理流程。

        【函数作用】
        接收用户问题，构建 system prompt，进入 Thought→Action→Observation→(Reflection)
        循环，直到 LLM 输出 FinalAnswer 或达到最大循环次数。

        【参数说明】
        - user_query : 用户的问题文本
                       来源：test_main.py 中的 user_question

        【谁会调用】
        - test_main.py → agent_reflect.run(user_question)

        【执行流程】
        1. 清空历史，构建 system prompt，添加用户问题
        2. 循环 max_loop 次：
           a. 调用 _generate_with_retry(enforce_reflect=False) 获取 Thought+Action
           b. 如有 FinalAnswer → 直接返回
           c. 如有 Action → 执行工具获得 Observation
              - 开启反思 → 构建 reflection 提示 → 获取 Reflection → 存入历史
              - 关闭反思 → 简洁提示继续
           d. 如无 Action → 追加纠错提示
        3. 达到最大循环 → 返回超限提示

        【关键代码解析】
        self.chat_history.clear()
          → 每次 run 清空历史，避免多次调用之间历史串扰

        sys_prompt = build_system_prompt(self.enable_reflection)
          → 根据是否开启反思，动态构建不同的 system prompt

        parsed, raw = self._generate_with_retry(enforce_reflect=False)
          → 返回元组 (ReActOutput, raw_text)，raw 用于兜底

        self._add_msg("assistant", f"Thought: {parsed.thought}\nAction: ...\nObservation: {obs}")
          → 将完整的 Thought+Action+Observation 作为 assistant 消息存入历史，
            让 LLM 在后续轮次能看到之前的推理过程和工具结果

        self._add_msg("assistant", f"Reflection: {reflect_out.reflection}")
          → 将反思内容作为 assistant 消息存入历史，
            下一轮 LLM 在 Thought 阶段能看到之前的反思，避免重复犯错
        """
        # 1. 初始化：清空历史、构建 system prompt、添加用户问题
        self.chat_history.clear()
        sys_prompt = build_system_prompt(self.enable_reflection)
        self._add_msg("system", sys_prompt)   # system 消息：定义 Agent 角色和输出格式
        self._add_msg("user", user_query)      # user 消息：用户的问题

        loop = 0
        while loop < self.max_loop:
            loop += 1
            print(f"\n========== 第{loop}轮 ==========")

            # 2a. 正常思考阶段：调用 LLM 获取 Thought + Action / FinalAnswer
            parsed, raw = self._generate_with_retry(enforce_reflect=False)
            print(f"Thought: {parsed.thought}")

            # 2b. 如果 LLM 输出了 FinalAnswer → 任务完成，直接返回
            if parsed.final_answer:
                return parsed.final_answer

            # 2c. 如果 LLM 输出了 Action → 执行工具
            if parsed.action_name and parsed.action_args:
                print(f"Action: {parsed.action_name}{parsed.action_args}")

                # 执行工具，获取 Observation
                obs = execute_tool(parsed.action_name, parsed.action_args)
                print(f"Observation: {obs}")

                # 将本轮完整的 Thought+Action+Observation 记入对话历史
                # 注意：作为 assistant 消息，让 LLM 知道这是"自己的"输出
                self._add_msg("assistant", f"Thought: {parsed.thought}\nAction: {parsed.action_name}{parsed.action_args}\nObservation: {obs}")

                if self.enable_reflection:
                    # ---- 反思模式 ----
                    # 动态构建 reflection 提示（注入当前工具的 hints）
                    reflect_req = self._build_reflect_prompt(obs, parsed.action_name)
                    self._add_msg("user", reflect_req)

                    # 调用 LLM 生成 Reflection（带强校验重试）
                    reflect_out, reflect_raw = self._generate_with_retry(enforce_reflect=True)
                    print(f"Reflection: {reflect_out.reflection}")

                    # 将反思内容存入对话历史，供下一轮 Thought 参考
                    # 作为 assistant 消息，让 LLM 在下一轮能看到自己之前的反思
                    self._add_msg("assistant", f"Reflection: {reflect_out.reflection}")
                else:
                    # ---- 无反思模式 ----
                    # 简洁提示 LLM 继续思考，包含 Observation 结果
                    self._add_msg("user", f"Observation: {obs}\n继续思考下一步，必须输出 Thought: 和 Action: 或 FinalAnswer:")
                continue

            # 2d. 既没有 FinalAnswer 也没有 Action → 追加纠错提示
            self._add_msg("user", "必须输出 Thought: + Action: 调用工具，或者 FinalAnswer: 返回最终答案")

        # 达到最大循环次数，返回超限提示
        return f"达到最大循环{self.max_loop}轮，终止"
