from utils.context_manager import ContextManager
from config.prompt_template import CONTEXT_PROMPT_TPL

if __name__ == "__main__":
    # 模拟知识库杂乱原文
    raw_docs = [
        "商品下单后48小时内安排发货",
        "会员开通7天内未使用可全额退款",
        "会员开通超过7天不支持退款，仅可用余额抵扣消费",
        "每月1号自动发放满50减5优惠券",
        "快递破损可申请免费换货"
    ]

    # 杂乱历史聊天记录
    chat_history = [
        "用户：我的订单什么时候发货？",
        "客服：48小时内出库",
        "用户：上个月15号开通的会员，能不能退？"
    ]

    user_question = "我现在可以退会员吗？"

    ctx = ContextManager()

    # Context Engineering 完整流水线
    relevant_docs = ctx.filter_relevant_docs(raw_docs, user_question)
    history_summary = ctx.compress_chat_history(chat_history)
    final_prompt = ctx.build_structured_context(
        history_summary, relevant_docs, user_question, CONTEXT_PROMPT_TPL
    )

    print("=== 组装后送入模型的结构化上下文 ===")
    print(final_prompt)
    print("\n=== 模型返回回答 ===")
    answer = ctx.chat_with_context(final_prompt)
    print(answer)