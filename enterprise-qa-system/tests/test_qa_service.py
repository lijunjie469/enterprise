"""
Comprehensive QA service tests covering all 12 exam test cases
plus additional boundary/edge cases.
"""
import pytest
from app.services.qa_service import EnterpriseQAService, IntentType


class TestIntentClassification:
    """Test intent recognition accuracy."""

    def test_db_only_employee(self, qa):
        assert qa.classify_intent("张三的部门是什么？") == IntentType.DB_ONLY

    def test_db_only_manager(self, qa):
        assert qa.classify_intent("李四的上级是谁？") == IntentType.DB_ONLY

    def test_db_only_project(self, qa):
        assert qa.classify_intent("张三负责哪些项目？") == IntentType.DB_ONLY

    def test_db_only_count(self, qa):
        assert qa.classify_intent("研发部有多少人？") == IntentType.DB_ONLY

    def test_db_only_late(self, qa):
        assert qa.classify_intent("张三2月迟到几次？") == IntentType.DB_ONLY

    def test_kb_only_policy(self, qa):
        assert qa.classify_intent("年假怎么计算？") == IntentType.KB_ONLY

    def test_kb_only_late_rules(self, qa):
        assert qa.classify_intent("迟到几次扣钱？") == IntentType.KB_ONLY

    def test_kb_only_reimbursement(self, qa):
        assert qa.classify_intent("差旅费报销标准是什么？") == IntentType.KB_ONLY

    def test_mixed_promotion(self, qa):
        assert qa.classify_intent("王五符合晋升条件吗？") == IntentType.MIXED

    def test_mixed_promotion_with_level(self, qa):
        assert qa.classify_intent("王五符合P5晋升P6条件吗？") == IntentType.MIXED

    def test_sql_injection_blocked(self, qa):
        assert qa.classify_intent("SELECT * FROM users WHERE '1'='1") == "sql_injection"
        assert qa.classify_intent("DROP TABLE employees") == "sql_injection"

    def test_ambiguous(self, qa):
        assert qa.classify_intent("最近有什么事？") == IntentType.AMBIGUOUS


# ─── T01-T04: 基础查询（必过）──────────────────────────────────────────

class TestBasicQueries:
    """T01-T04: Basic query tests."""

    def test_T01_zhangsan_department(self, qa):
        """T01: 张三的部门是什么？ -> 研发部"""
        result = qa.answer("张三的部门是什么？")
        assert "研发部" in result.answer
        assert len(result.sources) > 0
        assert any("employees" in s.detail for s in result.sources)

    def test_T01_variant_email(self, qa):
        """T01 variant: 李四的邮箱是什么？"""
        result = qa.answer("李四的邮箱是什么？")
        assert "lisi@company.com" in result.answer
        assert len(result.sources) > 0

    def test_T02_manager(self, qa):
        """T02: 李四的上级是谁？ -> CEO (EMP-000)"""
        result = qa.answer("李四的上级是谁？")
        assert "CEO" in result.answer
        assert len(result.sources) > 0

    def test_T03_annual_leave(self, qa):
        """T03: 年假怎么计算？ -> 满1年5天，每年+1，上限15天"""
        result = qa.answer("年假怎么计算？")
        assert len(result.answer) > 10
        assert len(result.sources) > 0
        # Should mention leave rules
        assert "年假" in result.answer or "入职" in result.answer

    def test_T04_late_fine(self, qa):
        """T04: 迟到几次扣钱？ -> 4-6次扣，50元/次"""
        result = qa.answer("迟到几次扣钱？")
        assert len(result.answer) > 10
        assert len(result.sources) > 0


# ─── T05-T08: 关联查询（必过）─────────────────────────────────────────

class TestCompoundQueries:
    """T05-T08: Compound/join query tests."""

    def test_T05_zhangsan_projects(self, qa):
        """T05: 张三负责哪些项目？ -> 4个项目及角色正确"""
        result = qa.answer("张三负责哪些项目？")
        assert "PRJ-001" in result.answer
        assert "PRJ-004" in result.answer
        assert "PRJ-002" in result.answer or "PRJ-003" in result.answer
        assert "lead" in result.answer.lower() or "负责人" in result.answer
        assert len(result.sources) > 0

    def test_T06_rd_dept_count(self, qa):
        """T06: 研发部有多少人？ -> 4人"""
        result = qa.answer("研发部有多少人？")
        assert "4" in result.answer
        assert "张三" in result.answer
        assert "李四" in result.answer
        assert "钱七" in result.answer
        assert "周九" in result.answer

    def test_T06_variant_product_dept(self, qa):
        """T06 variant: 产品部有多少人？ -> 3人"""
        result = qa.answer("产品部有多少人？")
        assert "3" in result.answer
        assert "王五" in result.answer

    def test_T07_wangwu_promotion(self, qa):
        """T07: 王五符合P5晋升P6条件吗？ -> 不符合"""
        result = qa.answer("王五符合P5晋升P6条件吗？")
        assert "不符合" in result.answer
        assert "KPI" in result.answer or "kpi" in result.answer.lower() or "绩效" in result.answer
        assert "项目" in result.answer
        assert len(result.sources) >= 1

    def test_T07_variant_qianqi(self, qa):
        """T07 variant: 钱七符合晋升条件吗？"""
        result = qa.answer("钱七符合晋升条件吗？")
        assert len(result.answer) > 20
        assert len(result.sources) > 0

    def test_T08_zhangsan_feb_late(self, qa):
        """T08: 张三2月迟到几次？ -> 2次"""
        result = qa.answer("张三2月迟到几次？")
        assert "2" in result.answer
        assert "迟到" in result.answer
        assert len(result.sources) > 0
        assert any("attendance" in s.detail for s in result.sources)


# ─── T09-T12: 边界情况（必过）─────────────────────────────────────────

class TestEdgeCases:
    """T09-T12: Edge case tests."""

    def test_T09_nonexistent_employee(self, qa):
        """T09: 查一下EMP-999 -> 明确告知无此员工"""
        result = qa.answer("查一下EMP-999")
        assert "未找到" in result.answer or "不存在" in result.answer or "找不到" in result.answer

    def test_T09_nonexistent_name(self, qa):
        """T09 variant: nonexistent name"""
        result = qa.answer("查一下刘二十")
        assert (
            "未找到" in result.answer
            or "不存在" in result.answer
            or "找不到" in result.answer
            or "未精确" in result.answer
        )

    def test_T10_ambiguous_question(self, qa):
        """T10: 最近有什么事？ -> 追问澄清或返回最近会议/项目"""
        result = qa.answer("最近有什么事？")
        # Should either clarify or return something useful
        assert len(result.answer) > 5

    def test_T11_sql_injection(self, qa):
        """T11: SELECT * FROM users WHERE '1'='1 -> 拦截"""
        result = qa.answer("SELECT * FROM users WHERE '1'='1")
        assert "不安全" in result.answer or "拦截" in result.answer

    def test_T11_union_injection(self, qa):
        result = qa.answer("DROP TABLE employees; --")
        assert "不安全" in result.answer or "拦截" in result.answer

    def test_T12_nonsense_query(self, qa):
        """T12: xyzabc123怎么报销 -> 告知无相关信息，不编造"""
        result = qa.answer("xyzabc123怎么报销")
        assert "未找到" in result.answer or "抱歉" in result.answer

    def test_T12_gibberish(self, qa):
        result = qa.answer("xyzabc123")
        assert "未找到" in result.answer or "抱歉" in result.answer or "模糊" in result.answer


# ─── 追加问题测试 ─────────────────────────────────────────────────────

class TestAdditionalQuestions:
    """Additional exam questions for generalization testing."""

    def test_zhangsan_performance_2025(self, qa):
        """张三2025年绩效如何？"""
        result = qa.answer("张三2025年绩效如何？")
        assert "张三" in result.answer
        assert "2025" in result.answer or "Q1" in result.answer or "Q2" in result.answer
        assert "89" in result.answer or "90" in result.answer

    def test_active_projects(self, qa):
        """有哪些在研项目？"""
        result = qa.answer("有哪些在研项目？")
        assert "PRJ-001" in result.answer
        assert "PRJ-003" in result.answer

    def test_meeting_allhands(self, qa):
        """3月全员大会说了什么？"""
        result = qa.answer("3月全员大会说了什么？")
        assert len(result.answer) > 10

    def test_reimbursement_standard(self, qa):
        """差旅费报销标准是什么？"""
        result = qa.answer("差旅费报销标准是什么？")
        assert len(result.answer) > 10
        assert len(result.sources) > 0

    def test_zhangsan_email(self, qa):
        """张三的邮箱"""
        result = qa.answer("张三的邮箱")
        assert "zhangsan@company.com" in result.answer

    def test_zhangsan_level(self, qa):
        """张三的职级"""
        result = qa.answer("张三的职级是什么？")
        assert "P6" in result.answer


# ─── 回答质量检查 ─────────────────────────────────────────────────────

class TestAnswerQuality:
    """Verify answer quality requirements."""

    def test_all_answers_have_sources(self, qa):
        """Answers with data should include source attribution."""
        test_questions = [
            "张三的部门是什么？",
            "李四的上级是谁？",
            "研发部有多少人？",
            "王五符合晋升条件吗？",
            "张三2月迟到几次？",
        ]
        for q_text in test_questions:
            result = qa.answer(q_text)
            assert len(result.sources) > 0, f"No sources for: {q_text}"

    def test_no_fabricated_data(self, qa):
        """Should not fabricate data when not available."""
        result = qa.answer("EMP-999")
        # Should indicate not found
        assert "未找到" in result.answer or "找不到" in result.answer or "不存在" in result.answer

    def test_source_format(self, qa):
        """Source attribution should be informative."""
        result = qa.answer("张三的部门是什么？")
        for s in result.sources:
            assert s.source_type in ("database", "knowledge_base")
            assert len(s.detail) > 0

    def test_natural_language_output(self, qa):
        """Answer should be in natural language, not raw data dump."""
        result = qa.answer("张三的部门是什么？")
        # Should not be a raw JSON or SQL-like output
        assert "{" not in result.answer
        assert "SELECT" not in result.answer.upper()
