"""
test_main.py — 测试入口

【模块作用】
创建 LLM 和 Agent 实例，分别以"开启 Reflection"和"关闭 Reflection"两种模式
运行同一个用户问题，对比两种模式的结果差异。

【执行方式】
python Reflection_demo/test_main.py

【被谁依赖】
此文件是项目入口，不被其他模块依赖。

【预期结果】
- 开启 Reflection：Agent 在 check_order 返回"金额不匹配"后，LLM 反思发现
  pay_amount=300 是错误的，修正为 299 重新调用，最终给出正确答案
- 关闭 Reflection：Agent 无法自我纠错，可能以错误金额返回结果
"""

from mock_llm import MockLLM
from core.react_agent import ReActAgentWithReflection

if __name__ == "__main__":
    # 创建 LLM 实例——从 .env 读取 API 配置
    llm = MockLLM()

    # 测试问题：包含一个"陷阱"——付款金额 300 是错误的（实际应为 299）
    # 这正是 Reflection 最有价值的场景：LLM 需要从"金额不匹配"的 Observation 中
    # 反思出 pay_amount 填错了，然后修正
    user_question = "帮我核对ORD001订单信息,付款金额为300，同时查询张三6月15号的日程安排"

    # ---- 测试 1：开启 Reflection 自省纠错模式 ----
    print("===== 【开启Reflection 自省纠错模式】 =====")
    # max_loop=6  → 最多 6 轮循环（两个任务 + 可能的重试）
    # debug=True   → 打印 LLM 原始输出，方便排查解析问题
    agent_reflect = ReActAgentWithReflection(llm, enable_reflection=True, max_loop=6, debug=True)
    res1 = agent_reflect.run(user_question)
    print(f"\n开启反射最终结果：{res1}\n")

    # ---- 测试 2：关闭 Reflection 原生 ReAct 模式 ----
    print("===== 【关闭Reflection 原生ReAct模式】 =====")
    # 同样的参数，只是 enable_reflection=False
    agent_no_reflect = ReActAgentWithReflection(llm, enable_reflection=False, max_loop=6, debug=True)
    res2 = agent_no_reflect.run(user_question)
    print(f"\n关闭反射最终结果：{res2}")
