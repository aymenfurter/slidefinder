"""Template management for SlideFinder frontend."""
from pathlib import Path

# HTML Template path
TEMPLATES_DIR = Path(__file__).parent / "html"


def get_index_template() -> str:
    """Load and return the main index.html template."""
    template_path = TEMPLATES_DIR / "index.html"
    if template_path.exists():
        return template_path.read_text()
    raise FileNotFoundError(f"Template not found: {template_path}")
