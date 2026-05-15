"""Integration tests for the QA API endpoints."""
import pytest
from fastapi.testclient import TestClient
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from main import app

client = TestClient(app)


class TestHealthEndpoint:
    def test_root_health(self):
        resp = client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"

    def test_qa_health(self):
        resp = client.get("/api/v1/qa/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == 200

    def test_get_tables(self):
        resp = client.get("/api/v1/qa/tables")
        assert resp.status_code == 200
        data = resp.json()
        assert "employees" in data["data"]


class TestQAAPI:
    """Test all 12 exam test cases via HTTP API."""

    def _ask(self, question: str) -> dict:
        resp = client.post(
            "/api/v1/qa/query",
            json={"question": question},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == 200
        return data["data"]

    # T01-T04: 基础查询
    def test_T01(self):
        data = self._ask("张三的部门是什么？")
        assert "研发部" in data["answer"]

    def test_T02(self):
        data = self._ask("李四的上级是谁？")
        assert "CEO" in data["answer"]

    def test_T03(self):
        data = self._ask("年假怎么计算？")
        assert len(data["answer"]) > 10
        assert len(data["sources"]) > 0

    def test_T04(self):
        data = self._ask("迟到几次扣钱？")
        assert len(data["answer"]) > 10

    # T05-T08: 关联查询
    def test_T05(self):
        data = self._ask("张三负责哪些项目？")
        assert "PRJ-001" in data["answer"]

    def test_T06(self):
        data = self._ask("研发部有多少人？")
        assert "4" in data["answer"]

    def test_T07(self):
        data = self._ask("王五符合P5晋升P6条件吗？")
        assert "不符合" in data["answer"]

    def test_T08(self):
        data = self._ask("张三2月迟到几次？")
        assert "2" in data["answer"]

    # T09-T12: 边界情况
    def test_T09(self):
        data = self._ask("查一下EMP-999")
        assert "未找到" in data["answer"] or "不存在" in data["answer"] or "找不到" in data["answer"]

    def test_T10(self):
        data = self._ask("最近有什么事？")
        assert len(data["answer"]) > 5

    def test_T11(self):
        data = self._ask("SELECT * FROM users WHERE '1'='1")
        assert "不安全" in data["answer"] or "拦截" in data["answer"]

    def test_T12(self):
        data = self._ask("xyzabc123怎么报销")
        assert "未找到" in data["answer"] or "抱歉" in data["answer"]


class TestGETEndpoint:
    def test_get_ask(self):
        resp = client.get("/api/v1/qa/ask?q=张三的部门")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == 200
