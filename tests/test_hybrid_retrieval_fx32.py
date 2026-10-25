from src.domain.retrieval import split_sentences
from src.infrastructure.config import settings


def test_split_sentences():
    text = "Membangun API dengan Python. Mengelola database PostgreSQL! Apakah performa tinggi tercapai? Ya tentu."
    sentences = split_sentences(text)
    assert len(sentences) == 4
    assert sentences[0] == "Membangun API dengan Python."
    assert sentences[1] == "Mengelola database PostgreSQL!"


def test_scoring_mode_configuration_and_defaults():
    assert settings.SCORING_MODE in ("rules", "hybrid")
    assert 0.5 <= settings.SEMANTIC_THRESHOLD <= 0.9
