"""
API edge-case tests for empty input rejection at HTTP layer.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    mock_checkpointer = MagicMock()
    mock_compiled = MagicMock()
    with (
        patch("src.main.setup_checkpointer", return_value=mock_checkpointer),
        patch("src.main.close_checkpointer"),
        patch("src.main.build_graph") as mock_build,
    ):
        mock_build.return_value.compile.return_value = mock_compiled
        from src.main import app

        with TestClient(app) as test_client:
            yield test_client


def test_e1_empty_report_rejected(client):
    response = client.post("/api/triage", json={"report": ""})
    assert response.status_code == 422


def test_e2_whitespace_only_rejected(client):
    response = client.post("/api/triage", json={"report": "   \n\n  "})
    assert response.status_code == 422
