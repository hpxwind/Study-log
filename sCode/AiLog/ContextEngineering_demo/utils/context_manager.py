from langchain_openai import ChatOpenAI
from langchain_core.prompts import PromptTemplate
from config.settings import LLM_API_KEY, LLM_BASE_URL, LLM_MODEL_NAME

class ContextManager:
    def __init__(self):
        self.llm = ChatOpenAI(
            model=LLM_MODEL_NAME,
            api_key=LLM_API_KEY,
            base_url=LLM_BASE_URL
        )

    def filter_relevant_docs(self, all_docs: list, query: str) -> list:
        """步骤1：上下文过滤，剔除无关文档，只保留相关内容"""
        result = []
        for doc in all_docs:
            if "退款" in doc or "会员" in doc:
                result.append(doc)
        return result

    def compress_chat_history(self, history: list) -> str:
        """步骤2：长对话压缩摘要，减少 Token，防止上下文溢出"""
        if not history:
            return "暂无历史对话"
        history_text = "\n".join(history)
        prompt = PromptTemplate.from_template(
            "用50字以内精简总结下面聊天记录：\n{text}"
        )
        resp = self.llm.invoke(prompt.format(text=history_text))
        return resp.content

    def build_structured_context(self, summary, docs, query, template):
        """步骤3：结构化组装最终 Prompt（核心 Context Engineering）"""
        doc_content = "\n".join(docs) if docs else "无匹配参考资料"
        final_prompt = template.format(
            chat_summary=summary,
            related_docs=doc_content,
            user_query=query
        )
        return final_prompt

    def chat_with_context(self, prompt: str):
        """传入构造好的上下文，调用真实大模型接口"""
        return self.llm.invoke(prompt).content