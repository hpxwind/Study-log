# Reflection
## 目录结构
```
react_agent_demo/
├── config/
│   ├── __init__.py
│   └── tool_registry.py
├── tools/
│   ├── __init__.py
│   ├── order_check.py      # 订单核验工具（易出错，反射重调用典型）
│   └── schedule_query.py   # 日程查询工具（参数格式坑多）
├── core/
│   ├── __init__.py
│   ├── prompt_builder.py
│   ├── output_parser.py
│   └── react_agent.py
├── mock_llm.py
└── test_main.py
```

## reflection执行顺序图
```
用户 → Agent：提交问题
循环（未到最大轮数）：
    1. Reason推理阶段
        Agent拼接历史上下文 → 喂LLM
        LLM输出：Thought + Action / FinalAnswer
    2. 分支判断
    ├─ 分支A：输出FinalAnswer（即将收尾）
    │   2.1 【Reflection终答校验】LLM反思检查答案：
    │       校验点：计算对错、资料匹配、有无幻觉、是否答非所问、参数是否齐全
    │   2.2 反思两种结果：
    │       ✅ 校验无误 → 直接返回答案给用户，流程结束
    │       ❌ 发现错误/缺信息 → 作废本次答案，回到Reason重新规划工具调用
    └─ 分支B：输出Action调用工具
        2.1 执行工具，拿到Observation
        2.2 【Reflection工具反思】LLM复盘本次调用：
            检查：工具选的对不对、参数填错没、返回内容能不能回答问题
        2.3 反思判定：
            ├─ 信息充足、调用无误 → 写入完整一轮记录(Thought/Action/Observation)，进入下一轮Reason
            └─ 参数错误/工具选错/返回无效数据 → 不写入有效历史，本轮作废，重新推理修正调用
循环上限耗尽 → 返回超限提示
```