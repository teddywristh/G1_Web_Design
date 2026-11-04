import httpx
import pytest

from app.core.errors import APIError
from app.services import images


@pytest.fixture(autouse=True)
def empty_cache():
    images._cache.clear()


def test_clean_query_drops_numbers_emails_and_punctuation():
    assert images.clean_query("Land USE cert 0912345678 a@b.vn, #42!") == "land use cert"


class FakeResponse:
    def __init__(self, payload, status=200):
        self.payload, self.status_code = payload, status

    def raise_for_status(self):
        if self.status_code >= 400:
            raise httpx.HTTPStatusError("bad", request=None, response=None)

    def json(self):
        return self.payload


def test_search_sends_only_cleaned_query_and_caches(monkeypatch):
    calls = []
    payload = {
        "results": [
            {
                "title": "Certificate",
                "creator": "Ann",
                "license": "by",
                "license_version": "4.0",
                "thumbnail": "https://api.openverse.org/v1/images/x/thumb/",
                "foreign_landing_url": "https://example.org/x",
            },
            {"title": "insecure", "thumbnail": "http://x", "foreign_landing_url": "http://x"},
        ]
    }

    def fake_get(url, params, **kwargs):
        calls.append(params["q"])
        return FakeResponse(payload)

    monkeypatch.setattr(images.httpx, "get", fake_get)
    first = images.search("Land use certificate 123")
    second = images.search("land use certificate")
    assert calls == ["land use certificate"]
    assert first == second
    assert first == [
        {
            "title": "Certificate",
            "creator": "Ann",
            "license": "CC BY 4.0",
            "license_url": "",
            "landing_url": "https://example.org/x",
            "thumbnail": "https://api.openverse.org/v1/images/x/thumb/",
        }
    ]


def test_search_failure_is_an_api_error(monkeypatch):
    monkeypatch.setattr(images.httpx, "get", lambda *a, **k: FakeResponse({}, 502))
    with pytest.raises(APIError) as error:
        images.search("court")
    assert error.value.code == "image_search_unavailable"


def test_too_short_query_skips_network(monkeypatch):
    monkeypatch.setattr(images.httpx, "get", lambda *a, **k: pytest.fail("network called"))
    assert images.search("12 a") == []
