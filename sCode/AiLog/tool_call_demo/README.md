# Tool_Call
## 目录结构
```
tool_call_demo/
├── config/
│   └── tool_registry.py     # 工具注册、元信息定义
├── tools/
│   ├── __init__.py
│   ├── calculator.py        # 计算器工具实现
│   └── time_tool.py         # 时间工具实现
├── core/
│   ├── __init__.py
│   ├── prompt_builder.py    # 构造system提示词
│   ├── parser.py            # 解析模型输出、提取工具调用
│   └── agent.py             # 主调度：对话循环、执行工具、多轮推理
├── mock_llm.py              # 模拟大模型接口（可替换真实OpenAI/本地模型）
└── test_main.py             # 独立测试入口文件
```

## tool_call执行顺序图
```
用户 → LLM：提交问题
LLM 内部判断
├─ 不需要工具 → LLM → 用户：输出答案，结束
└─ 需要工具
    LLM → 调度器：下发tool调用参数
    调度器 → 工具：校验参数、执行
    工具 → 调度器：返回结果/异常
    调度器 → LLM：回填结果到上下文
    LLM二次判断
    ├─ 信息足够 → LLM→用户：整合回答
    ├─ 信息不足、没到最大轮数 → 重复工具调用流程
    └─ 达到调用上限 → LLM→用户：有限内容回复
```