"""Embedding generator for candidate profile chunks and requirements using Harrier on CPU (FX-32)."""

from __future__ import annotations

import torch
from sentence_transformers import SentenceTransformer

from src.infrastructure.config import settings
from src.infrastructure.logging import logger

_model: SentenceTransformer | None = None


def get_embedding_model() -> SentenceTransformer:
    global _model
    if _model is None:
        logger.info(f"Loading embedding model {settings.EMBEDDING_MODEL} on CPU...")
        _model = SentenceTransformer(
            settings.EMBEDDING_MODEL, device="cpu", model_kwargs={"torch_dtype": torch.float32}
        )
        logger.info(f"Embedding model loaded successfully (max_seq_length: {_model.max_seq_length}).")
    return _model


def embed_texts(texts: list[str]) -> list[list[float]]:
    """Encodes texts into normalized embedding vectors.

    Harrier supports up to 32,768 tokens context window. Texts are normalized to cosine similarity.
    """
    if not texts:
        return []
    model = get_embedding_model()
    # Batch encoding with cosine normalization
    embeddings = model.encode(texts, batch_size=32, show_progress_bar=False, normalize_embeddings=True)
    return embeddings.tolist()
