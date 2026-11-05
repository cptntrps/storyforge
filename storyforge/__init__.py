"""storyforge: one story contract (story.json) between diagnosis, narration, rendering and gates."""

from pathlib import Path

PKG = Path(__file__).resolve().parent
__version__ = (PKG.parent / 'VERSION').read_text().strip() if (PKG.parent / 'VERSION').exists() else '0.0.0'
