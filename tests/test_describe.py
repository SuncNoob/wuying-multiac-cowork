from cowork.describe import describe_task
from cowork.protocol import Task


def test_describe_fetch_mentions_detail_pages():
    text = describe_task(
        Task(
            id="TASK-002",
            scenario="crawler",
            type="fetch",
            title="Fetch lienu",
            mode="browser",
            brand="lienu",
            max_images=16,
            seed_urls=["https://www.lienujewelry.com/collections/all"],
        )
    )
    assert "LIENU" in text
    assert "详情" in text
    assert "16" in text
    assert "lienujewelry.com" in text


def test_describe_coding_implement():
    text = describe_task(
        {
            "type": "implement",
            "title": "hello file",
            "path": "workspace/hello.txt",
            "content": "hello cowork",
        }
    )
    assert "workspace/hello.txt" in text
    assert "hello cowork" in text


def test_describe_extract_lists_deps():
    text = describe_task({"type": "extract", "depends_on": ["TASK-002", "TASK-003"], "title": "catalog"})
    assert "TASK-002" in text
    assert "CATALOG.md" in text
