# ReAct_demo
## 目录结构
```
react_agent_demo/
├── config/
│   ├── __init__.py
│   └── tool_registry.py       # 统一管理所有可用工具元数据
├── tools/
│   ├── __init__.py
│   ├── calculator.py          # 数学计算工具
│   └── info_search.py         # 知识库检索工具
├── core/
│   ├── __init__.py
│   ├── prompt_builder.py      # 生成标准ReAct格式System Prompt
│   ├── output_parser.py       # 解析LLM输出Thought/Action/FinalAnswer
│   └── react_agent.py         # 核心：ReAct三轮循环调度引擎
├── mock_llm.py                # 模拟大模型（完全遵循ReAct输出格式）
└── test_main.py               # 测试入口，直观打印每一轮循环步骤
```

## ReAct执行流程图
```
用户 → LLM：提交问题
LLM 第一轮推理判断
├─ 无需调用任何工具
│   LLM → 用户：输出FinalAnswer，流程结束
└─ 需要调用工具
    LLM → Agent调度层：输出标准化Action调用参数
    调度层 → 工具函数：校验参数合法性、执行工具逻辑
    工具函数 → 调度层：返回Observation结果/运行异常信息
    调度层 → LLM：把Thought、Action、Observation存入历史上下文
    LLM 二次推理判断
    ├─ 信息充足完备 → LLM→用户：整合内容输出FinalAnswer，结束
    ├─ 信息缺失且未达最大循环轮数 → 回到【LLM输出Action】重复工具流程
    └─ 已用尽最大迭代轮数 → LLM→用户：返回超限提示+现有有限结果
```