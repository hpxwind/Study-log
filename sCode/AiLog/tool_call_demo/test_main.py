from core.agent import run_agent

if __name__ == "__main__":
    print("===== 测试1：计算 10乘以20 =====")
    ans1 = run_agent("帮我算10乘以20")
    print(f"最终回答：{ans1}\n")

    # print("===== 测试2：查询当前时间 =====")
    # ans2 = run_agent("现在是什么时间")
    # print(f"最终回答：{ans2}\n")

    # print("===== 测试3：普通闲聊（无工具） =====")
    # ans3 = run_agent("你好呀")
    # print(f"最终回答：{ans3}")