"""
Enterprise QA Skill CLI — wraps the QA service for use by Claude Code Skill.
Usage: python cli.py "问题文本"
"""
import sys
import os

# Ensure project root is on the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.core.config import settings
from app.services.db_service import DBService, DBSecurityError
from app.services.kb_service import KnowledgeBase
from app.services.qa_service import EnterpriseQAService


def main():
    if len(sys.argv) < 2:
        print("用法: python cli.py <问题>")
        print('示例: python cli.py "张三的部门是什么？"')
        sys.exit(1)

    question = " ".join(sys.argv[1:]).strip()
    if not question:
        print("问题不能为空。")
        sys.exit(1)

    try:
        db = DBService(settings.DB_PATH)
        kb = KnowledgeBase(settings.KB_PATH)
        qa = EnterpriseQAService(db, kb)
        result = qa.answer(question)

        print(result.format())

        if not result.sources:
            print()
            print(
                "提示：如果未找到相关信息，请尝试换个问法，或指定更多上下文。"
            )

    except DBSecurityError as e:
        print(f"安全拦截：{e}")
        sys.exit(1)
    except Exception as e:
        print(f"查询出错：{e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
