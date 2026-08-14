from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from app.schemas import ProtocolSource


@dataclass(frozen=True)
class KnowledgeSection:
    source_id: str
    title: str
    url: str
    reference: str
    text: str


class ProtocolRetriever:
    """Recuperação lexical local, determinística e sem envio de documentos a terceiros."""

    def __init__(self, knowledge_base_path: Path) -> None:
        self._sections = self._load_sections(knowledge_base_path)
        if not self._sections:
            raise RuntimeError(f"Nenhuma seção RAG encontrada em {knowledge_base_path}")
        self._vectorizer = TfidfVectorizer(
            lowercase=True,
            strip_accents="unicode",
            ngram_range=(1, 2),
            sublinear_tf=True,
        )
        self._matrix = self._vectorizer.fit_transform(section.text for section in self._sections)

    @staticmethod
    def _load_sections(path: Path) -> list[KnowledgeSection]:
        sections: list[KnowledgeSection] = []
        for document_path in sorted(path.glob("*.json")):
            payload = json.loads(document_path.read_text(encoding="utf-8"))
            required = {"source_id", "title", "url", "sections"}
            missing = required.difference(payload)
            if missing:
                raise ValueError(f"{document_path.name}: campos ausentes: {sorted(missing)}")
            for section in payload["sections"]:
                sections.append(
                    KnowledgeSection(
                        source_id=str(payload["source_id"]),
                        title=str(payload["title"]),
                        url=str(section.get("url", payload["url"])),
                        reference=str(section["reference"]),
                        text=" ".join(str(section["text"]).split()),
                    )
                )
        return sections

    @property
    def section_count(self) -> int:
        return len(self._sections)

    def retrieve(self, query: str, top_k: int = 4) -> list[ProtocolSource]:
        normalized_query = " ".join(query.split()) or (
            "triagem risco materno gestação pressão arterial glicemia temperatura "
            "frequência cardíaca acompanhamento pré-natal"
        )
        query_vector = self._vectorizer.transform([normalized_query])
        scores = cosine_similarity(query_vector, self._matrix).ravel()
        ranked_indices = scores.argsort()[::-1][: min(top_k, len(self._sections))]

        return [
            ProtocolSource(
                source_id=self._sections[index].source_id,
                title=self._sections[index].title,
                url=self._sections[index].url,
                reference=self._sections[index].reference,
                excerpt=self._sections[index].text,
                relevance_score=max(0.0, min(1.0, round(float(scores[index]), 6))),
            )
            for index in ranked_indices
        ]
