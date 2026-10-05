"""The installable reader page."""

import json


def test_reader_page_is_installable(client):
    page = client.get("/app/")
    assert page.status_code == 200
    assert "text/html" in page.headers["content-type"]
    assert "Education Lens" in page.text
    assert 'href="/app/manifest.webmanifest"' in page.text
    assert "Saved" in page.text

    manifest = client.get("/app/manifest.webmanifest")
    body = manifest.json()
    assert manifest.status_code == 200
    assert "manifest" in manifest.headers["content-type"]
    assert body["name"] == "Education Lens"
    assert body["short_name"] == "Ed Lens"
    assert body["display"] == "standalone"
    assert body["start_url"] == "/app/"
    assert body["icons"]

    script = client.get("/app/app.js")
    assert script.status_code == 200
    assert "ghanaed.saved.v1" in script.text
    assert "/feed" in script.text

    worker = client.get("/app/sw.js")
    assert worker.status_code == 200
    assert "ghanaed-reader-1" in worker.text

    icon = client.get("/app/icon-192.png")
    assert icon.status_code == 200
    assert icon.content.startswith(b"\x89PNG")
    json.loads(manifest.text)
