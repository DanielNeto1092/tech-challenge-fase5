from pathlib import Path

from app.rag.retriever import ProtocolRetriever

BACKEND_DIR = Path(__file__).resolve().parents[1]


def test_retriever_loads_traceable_official_sections() -> None:
    retriever = ProtocolRetriever(BACKEND_DIR / "data" / "knowledge_base")

    assert retriever.section_count == 16
    results = retriever.retrieve("pressão arterial 160 por 110 na gestação", top_k=4)

    assert len(results) == 4
    assert results[0].source_id == "ms-caderneta-gestante-2026"
    assert "p. 41" in results[0].reference
    assert results[0].url.startswith("https://")
    assert results[0].excerpt
    assert 0 <= results[0].relevance_score <= 1


def test_retriever_preserves_measurement_context_for_glucose() -> None:
    retriever = ProtocolRetriever(BACKEND_DIR / "data" / "knowledge_base")

    results = retriever.retrieve("glicemia jejum TOTG diabetes gestacional", top_k=6)

    combined = " ".join(source.excerpt for source in results).lower()
    assert "jejum" in combined
    assert "contexto" in combined
    assert "24 e 28 semanas" in combined
