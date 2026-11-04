import importlib.util
import io
from pathlib import Path

from fastapi.testclient import TestClient
from PIL import Image

path = Path(__file__).resolve().parents[1] / "app" / "main.py"
spec = importlib.util.spec_from_file_location("ocr_service", path)
service = importlib.util.module_from_spec(spec)
spec.loader.exec_module(service)


class FakeOCR:
    def predict(self, image):
        return [
            {
                "rec_texts": ["Điều 1. Phạm vi", "1. Quy định chung"],
                "rec_boxes": [[0, 0, 80, 10], [0, 20, 80, 30]],
            }
        ]


def test_ocr_endpoint_preserves_lines_and_coordinates(monkeypatch):
    monkeypatch.setattr(service.runtime, "model", FakeOCR())
    data = io.BytesIO()
    Image.new("RGB", (100, 100), "white").save(data, format="PNG")
    client = TestClient(service.app)
    response = client.post(
        "/v1/ocr", content=data.getvalue(), headers={"content-type": "image/png"}
    )
    assert response.status_code == 200
    assert response.json()["text"] == "Điều 1. Phạm vi\n1. Quy định chung"
    assert response.json()["lines"][0]["box"] == [0, 0, 80, 10]


def test_ocr_unready_is_reported(monkeypatch):
    monkeypatch.setattr(service.runtime, "model", None)
    client = TestClient(service.app)
    assert client.get("/ready").status_code == 503
