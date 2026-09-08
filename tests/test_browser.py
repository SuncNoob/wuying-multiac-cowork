from cowork.browser import brand_from_url, parse_images
from cowork.executors import pdp_page_count, required_pdp_pages, run_extract, run_fetch
from cowork.protocol import Task
from tests.conftest import make_store


def test_brand_from_url():
    assert brand_from_url("https://www.lienujewelry.com/collections/all") == "lienu"
    assert brand_from_url("https://hasuna.com/products/x") == "hasuna"
    assert brand_from_url("https://www.artidaoud.com/item?category_id=41") == "artida-oud"


def test_parse_images_picks_product_and_skips_icons():
    html = """
    <html><head><meta property="og:image" content="https://cdn.shopify.com/s/files/1/p.jpg"></head>
    <body>
      <img src="/favicon.ico">
      <img data-src="https://cdn.shopify.com/s/files/1/ring.png">
      <img srcset="https://cdn.shopify.com/s/small.jpg 320w, https://cdn.shopify.com/s/large.jpg 1200w">
    </body></html>
    """
    urls = parse_images(html, "https://www.lienujewelry.com/")
    assert "https://cdn.shopify.com/s/files/1/p.jpg" in urls
    assert "https://cdn.shopify.com/s/files/1/ring.png" in urls
    assert "https://cdn.shopify.com/s/large.jpg" in urls
    assert not any("favicon" in u for u in urls)


def test_browser_fetch_runs_codex(tmp_path, monkeypatch):
    store = make_store(tmp_path)
    pic = tmp_path / "pics" / "lienu"
    pic.mkdir(parents=True)

    def fake_codex(prompt, cwd, timeout=1200):
        assert "/products/" in prompt
        assert "DETAIL" in prompt or "详情" in prompt
        rows = []
        for i in range(4):
            name = f"0{i+1}.jpg"
            (pic / name).write_bytes(b"x" * 9000)
            rows.append(
                {
                    "file": name,
                    "source_page": f"https://www.lienujewelry.com/products/item-{i}",
                    "image_url": "https://cdn.shopify.com/x.jpg",
                }
            )
        (pic / "manifest.json").write_text(__import__("json").dumps(rows), encoding="utf-8")
        return {"ok": True, "code": 0, "stdout": "DONE\n4 detail pages", "stderr": ""}

    monkeypatch.setattr("cowork.executors.run_codex", fake_codex)
    task = Task(
        id="TASK-001",
        scenario="crawler",
        type="fetch",
        title="lienu",
        seed_urls=["https://www.lienujewelry.com/collections/all"],
        allow_hosts=["lienujewelry.com", "shopify.com"],
        mode="browser",
        brand="lienu",
        max_images=4,
    )
    result = run_fetch(store, task)
    assert result["ok"]
    assert result["fetched"][0]["engine"] == "codex"
    assert result["fetched"][0]["pdp_pages"] == 4
    assert result["fetched"][0]["images"][0]["file"] == "pics/lienu/01.jpg"


def test_listing_manifest_fails_pdp_gate():
    assert required_pdp_pages(16) == 12
    assert required_pdp_pages(4) == 4
    listing = [{"file": "01.jpg", "source_page": "https://www.lienujewelry.com/collections/all"}]
    assert pdp_page_count(listing) == 0
    pdps = [{"file": "01.jpg", "source_page": "https://www.lienujewelry.com/products/ring"}]
    assert pdp_page_count(pdps) == 1


def test_extract_writes_catalog(tmp_path, monkeypatch):
    store = make_store(tmp_path)
    fetch = Task(
        id="TASK-002",
        scenario="crawler",
        type="fetch",
        title="f",
        status="done",
    )
    store.result_dir("TASK-002").joinpath("fetch.json").write_text(
        '{"fetched":[{"url":"https://hasuna.com/","ok":true,"brand":"hasuna","engine":"chrome","images":[{"ok":true,"file":"pics/hasuna/01.jpg"}]}]}'
    )
    extract = Task(
        id="TASK-003",
        scenario="crawler",
        type="extract",
        title="e",
        depends_on=["TASK-002"],
    )
    out = run_extract(store, extract, {"TASK-002": fetch})
    assert out["ok"]
    catalog = (tmp_path / "pics/CATALOG.md").read_text()
    assert "hasuna" in catalog
    assert "pics/hasuna/01.jpg" in catalog
