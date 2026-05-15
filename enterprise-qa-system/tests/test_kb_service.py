"""Tests for knowledge base retrieval service."""
import pytest
from app.services.kb_service import KnowledgeBase


class TestKnowledgeBase:
    def test_load_documents(self, kb):
        assert len(kb.documents) > 0
        # Should have loaded all .md files
        sources = {d["source"] for d in kb.documents}
        assert "hr_policies.md" in sources
        assert "promotion_rules.md" in sources
        assert "tech_docs.md" in sources
        assert "finance_rules.md" in sources
        assert "faq.md" in sources

    def test_search_annual_leave(self, kb):
        results = kb.search("年假怎么计算", top_k=3)
        assert len(results) > 0
        # Results should be about annual leave
        combined = " ".join([r["text"] for r in results])
        assert "年假" in combined or "入职" in combined

    def test_search_late_policy(self, kb):
        results = kb.search("迟到扣款", top_k=3)
        assert len(results) > 0
        combined = " ".join([r["text"] for r in results])
        assert "迟到" in combined or "扣款" in combined

    def test_search_promotion_rules(self, kb):
        results = kb.search("P5晋升P6条件", top_k=3)
        assert len(results) > 0
        combined = " ".join([r["text"] for r in results])
        assert "晋升" in combined

    def test_search_finance(self, kb):
        results = kb.search("差旅费报销标准", top_k=3)
        assert len(results) > 0
        combined = " ".join([r["text"] for r in results])
        assert "报销" in combined or "差旅" in combined

    def test_search_meeting(self, kb):
        results = kb.search("3月全员大会", top_k=3)
        assert len(results) > 0
        combined = " ".join([r["text"] for r in results])
        assert "全员" in combined or "大会" in combined or "2026" in combined

    def test_search_no_match(self, kb):
        results = kb.search("xyzabc123不存在的内容")
        if results:
            assert results[0]["score"] < 6.0

    def test_search_tech_docs(self, kb):
        results = kb.search("技术栈 Python Go", top_k=3)
        assert len(results) > 0

    def test_search_faq(self, kb):
        results = kb.search("试用期 入职 五险一金", top_k=3)
        assert len(results) > 0

    def test_section_splitting(self, kb):
        # Each document should have heading info
        for doc in kb.documents:
            assert "heading" in doc
            assert "source" in doc
            assert "text" in doc
            assert len(doc["text"]) > 0

    def test_reload(self, kb):
        original_count = len(kb.documents)
        kb.reload()
        assert len(kb.documents) == original_count
