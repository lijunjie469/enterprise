"""Pytest fixtures for enterprise QA tests."""
import os
import sys
import pytest

# Ensure the project root is in the path
sys.path.insert(
    0,
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
)

# Override config before importing app modules
os.environ["ENTERPRISE_QA_DB_PATH"] = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "enterprise.db",
)
os.environ["ENTERPRISE_QA_KB_PATH"] = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "knowledge",
)
os.environ["ENTERPRISE_QA_CURRENT_DATE"] = "2026-03-27"

from app.services.db_service import DBService, get_db
from app.services.kb_service import KnowledgeBase, get_kb
from app.services.qa_service import EnterpriseQAService


@pytest.fixture
def db():
    """Provide a DB service instance."""
    return get_db()


@pytest.fixture
def kb():
    """Provide a KB service instance."""
    return get_kb()


@pytest.fixture
def qa():
    """Provide a QA service instance."""
    return EnterpriseQAService(get_db(), get_kb())
