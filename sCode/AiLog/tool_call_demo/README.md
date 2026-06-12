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