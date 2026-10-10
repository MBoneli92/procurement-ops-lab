"""O pipeline compara a versao do pacote (mta.yaml) com a do /health depois do deploy.
Este teste garante que as duas andam juntas, antes de chegar no deploy."""

import re
from pathlib import Path

from app.main import app


def test_app_version_matches_mta_version():
    mta = Path(__file__).resolve().parent.parent / "mta.yaml"
    match = re.search(r"^version:\s*(\S+)", mta.read_text(), re.MULTILINE)
    assert match, "version not found in mta.yaml"
    assert app.version == match.group(1)
