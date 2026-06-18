from utils.llm_client import chat
from utils.prompt_builder import WRITER_PROMPT

class WriterAgent:
    def __init__(self):
        self.role = WRITER_PROMPT["role"]
        self.system_prompt = WRITER_PROMPT["prompt"]
    
    def write(self, outline: str) -> str:
        """
        执行写作任务：接收大纲，输出正文
        :outline: 用户输入的写作大纲
        """
        print(f"[{self.role}] 正在撰写 {outline} 的正文...")
        result = chat(self.system_prompt, outline)
        print(f"[{self.role}] 写作完成，正文如下：\n{result}")
        return result
