from utils.llm_client import chat
from utils.prompt_builder import REVIEWER_PROMPT

class ReviewerAgent:
    def __init__(self):
        self.role = REVIEWER_PROMPT["role"]
        self.system_prompt = REVIEWER_PROMPT["prompt"]
    
    def review(self, draft: str) -> str:
        """
        执行审稿任务：接收初稿，输出定稿
        :draft: 用户输入的初稿
        """
        print(f"[{self.role}] 正在审稿 {draft} 的正文...")
        result = chat(self.system_prompt, draft)
        print(f"[{self.role}] 审稿完成，定稿如下：\n{result}")
        return result