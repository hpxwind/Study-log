from utils.llm_client import chat
from utils.prompt_builder import PLANNER_PROMPT


class PlannerAgent:
    def __init__(self):
        self.role = PLANNER_PROMPT["role"]
        self.system_prompt = PLANNER_PROMPT["prompt"]
    
    def plan(self, topic: str) -> str:
        """
        执行规划任务：接收主题，输出大纲
        :topic: 用户输入的主题
        """
        print(f"[{self.role}] 正在规划 {topic} 的写作大纲...")
        result = chat(self.system_prompt, topic)
        print(f"[{self.role}] 规划完成，大纲如下：\n{result}")
        return result