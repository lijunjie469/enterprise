"""
Knowledge Base retrieval service using BM25 for keyword search.
Supports searching across all markdown files in the knowledge directory.
Uses a pure-Python BM25 implementation (no external deps).
"""
import os
import re
import math
import logging
from typing import List, Dict, Optional
import jieba

logger = logging.getLogger(__name__)


def _tokenize(text: str) -> List[str]:
    """Tokenize Chinese text using jieba."""
    return list(jieba.cut(text))


class BM25:
    """Pure-Python BM25 implementation for document scoring."""

    def __init__(self, corpus: List[List[str]], k1: float = 1.5, b: float = 0.75):
        self.k1 = k1
        self.b = b
        self.corpus = corpus
        self.n_docs = len(corpus)
        self.avgdl = sum(len(d) for d in corpus) / max(self.n_docs, 1)
        self.idf_cache: Dict[str, float] = {}

        # Precompute document frequencies
        self.doc_freq: Dict[str, int] = {}
        for doc in corpus:
            seen = set()
            for token in doc:
                if token not in seen:
                    self.doc_freq[token] = self.doc_freq.get(token, 0) + 1
                    seen.add(token)

    def _idf(self, token: str) -> float:
        if token in self.idf_cache:
            return self.idf_cache[token]
        df = self.doc_freq.get(token, 0)
        if df == 0:
            return 0.0
        idf = math.log(1 + (self.n_docs - df + 0.5) / (df + 0.5))
        self.idf_cache[token] = idf
        return idf

    def get_scores(self, query_tokens: List[str]) -> List[float]:
        scores = []
        for doc in self.corpus:
            score = 0.0
            doc_len = len(doc)
            # Term frequency in this document
            tf: Dict[str, int] = {}
            for t in doc:
                tf[t] = tf.get(t, 0) + 1

            for token in query_tokens:
                if token not in tf:
                    continue
                idf = self._idf(token)
                freq = tf[token]
                numerator = freq * (self.k1 + 1)
                denominator = freq + self.k1 * (1 - self.b + self.b * doc_len / self.avgdl)
                score += idf * numerator / denominator
            scores.append(score)
        return scores


class KnowledgeBase:
    """Manages knowledge base documents with BM25 retrieval."""

    def __init__(self, kb_path: str):
        self.kb_path = kb_path
        self.documents: List[Dict] = []
        self._bm25: Optional[BM25] = None
        self._tokenized_docs: List[List[str]] = []
        self._load_all()

    def _load_all(self):
        """Load all markdown files from the knowledge directory."""
        self.documents = []
        self._tokenized_docs = []

        for root, dirs, files in os.walk(self.kb_path):
            for fname in sorted(files):
                if not fname.endswith(".md"):
                    continue
                fpath = os.path.join(root, fname)
                rel_path = os.path.relpath(fpath, self.kb_path)
                try:
                    with open(fpath, "r", encoding="utf-8") as f:
                        content = f.read()
                except Exception as e:
                    logger.warning(f"Failed to read {fpath}: {e}")
                    continue

                sections = self._split_sections(content, rel_path)
                for sec in sections:
                    self.documents.append(sec)
                    self._tokenized_docs.append(_tokenize(sec["text"]))

        logger.info(
            f"Loaded {len(self.documents)} sections from knowledge base ({self.kb_path})"
        )

    def _split_sections(self, content: str, source: str) -> List[Dict]:
        """Split a markdown file into sections by headings."""
        lines = content.split("\n")
        sections: List[Dict] = []
        current_heading = source
        current_lines: List[str] = []

        for line in lines:
            heading_match = re.match(r"^#{1,4}\s+(.+)", line)
            if heading_match:
                if current_lines:
                    text = "\n".join(current_lines).strip()
                    if text:
                        sections.append(
                            {"source": source, "heading": current_heading, "text": text}
                        )
                current_heading = f"{source} § {heading_match.group(1)}"
                current_lines = []
            else:
                current_lines.append(line)

        if current_lines:
            text = "\n".join(current_lines).strip()
            if text:
                sections.append(
                    {"source": source, "heading": current_heading, "text": text}
                )

        return sections

    def search(self, query: str, top_k: int = 5) -> List[Dict]:
        """Search knowledge base with BM25 and return top results."""
        if not self._tokenized_docs:
            return []

        query_tokens = _tokenize(query)
        if self._bm25 is None:
            self._bm25 = BM25(self._tokenized_docs)

        scores = self._bm25.get_scores(query_tokens)
        ranked = sorted(
            enumerate(scores), key=lambda x: x[1], reverse=True
        )

        results = []
        for idx, score in ranked:
            if score <= 0:
                continue
            doc = self.documents[idx].copy()
            doc["score"] = float(score)
            results.append(doc)
            if len(results) >= top_k:
                break

        return results

    def reload(self):
        """Reload all documents."""
        self._bm25 = None
        self._load_all()


# Singleton instance
_kb_instance: Optional[KnowledgeBase] = None


def get_kb(kb_path: Optional[str] = None) -> KnowledgeBase:
    global _kb_instance
    if _kb_instance is None:
        from app.core.config import settings

        path = kb_path or settings.KB_PATH
        _kb_instance = KnowledgeBase(path)
    return _kb_instance
