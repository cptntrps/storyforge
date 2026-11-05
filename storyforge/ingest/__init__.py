"""Ingesters: each reads one presentation format and returns a deck.json dict."""

from storyforge.ingest.pptx import ingest_pptx

__all__ = ['ingest_pptx']
