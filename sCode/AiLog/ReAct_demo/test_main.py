from core.react_agent import ReActCoreAgent

def test_api_agent():
    # 初始化Agent，
    agent = ReActCoreAgent()

    test_cases = [
        "123乘以45等于多少",
        "100除以4",
        "2026年高考时间是什么时候",
        "简单介绍一下Python"
    ]

    print("========== 真实API ReAct Agent 批量测试 ==========\n")
    for idx, question in enumerate(test_cases, 1):
        print(f"【测试{idx}】用户问题：{question}")
        result = agent.solve(question)
        print(f"\n【最终答案】{result}\n")
        print("-" * 60 + "\n")

def interactive_chat():
    """交互式手动输入提问"""
    agent = ReActCoreAgent(max_tool_loop=5)
    print("===== 交互式对话（输入exit退出）=====")
    while True:
        user_q = input("\n你的问题：")
        if user_q.strip().lower() == "exit":
            print("对话结束")
            break
        ans = agent.solve(user_q)
        print(f"\n回复：{ans}")

if __name__ == "__main__":
    # 二选一执行
    # 批量自动化用例
    test_api_agent()
    # 手动交互
    # interactive_chat()