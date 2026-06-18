# MultiAgent
## 目录结构
```
simple-multiagent-demo/
├── main.py                 # 程序入口：总控调度器，编排Agent协作流程
├── .env                    # 环境变量配置（API密钥、地址、模型，不提交Git）
├── .env.example            # 环境变量参考模板
├── requirements.txt        # 项目依赖清单
├── agents/                 # 智能体模块：每个Agent独立文件，职责解耦
│   ├── __init__.py         # 模块导出
│   ├── planner_agent.py    # 规划Agent：拆解任务、生成写作大纲
│   ├── writer_agent.py     # 写作Agent：根据大纲撰写正文
│   └── reviewer_agent.py   # 校对Agent：审核纠错、优化润色
├── utils/
│   ├── __init__.py
│   ├── llm_client.py       # 真实大模型API统一封装，从.env读取配置
│   └── prompt_builder.py   # Prompt模板管理，从prompts目录读取
└── README.md               # 项目说明
```