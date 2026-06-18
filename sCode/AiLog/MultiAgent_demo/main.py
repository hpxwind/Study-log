from agents import PlannerAgent, WriterAgent, ReviewerAgent


class MultiAgentOrchestrator:
    def __init__(self):
        self.planner = PlannerAgent()
        self.writer = WriterAgent()
        self.reviewer = ReviewerAgent()
    
    def run(self, user_topic: str):
        """
        多智能体流水线协作主流程
        规划 -> 写作 -> 审稿 -> 输出
        """
        print("===== 多智能体创作团队 =====")
        print(f"用户主题:{user_topic}\c")

        # Step1: 规划
        outline = self.planner.plan(user_topic)

        # Step2: 写作
        draft = self.writer.write(outline)

        # Step3: 审稿
        final_draft = self.reviewer.review(draft)

        print("===== 全部任务完成，最终输出 =====")
        return final_draft


if __name__ == "__main__":
    orchestrator = MultiAgentOrchestrator()
    orchestrator.run("树木护理指南")