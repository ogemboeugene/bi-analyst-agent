import json

import src.exemplars as ex


def _seed(tmp_path, monkeypatch, pairs):
    store = tmp_path / "exemplars.jsonl"
    store.write_text(
        "".join(json.dumps(p) + "\n" for p in pairs), encoding="utf-8"
    )
    monkeypatch.setattr(ex, "_STORE", str(store))
    return str(store)


def test_retrieve_ranks_by_overlap(tmp_path, monkeypatch):
    _seed(
        tmp_path,
        monkeypatch,
        [
            {"question": "revenue by country", "sql": "SELECT 1"},
            {"question": "count of products", "sql": "SELECT 2"},
        ],
    )
    hits = ex.retrieve("total revenue per country")
    assert hits[0].question == "revenue by country"


def test_retrieve_ignores_irrelevant(tmp_path, monkeypatch):
    _seed(
        tmp_path,
        monkeypatch,
        [{"question": "zz q unrelated", "sql": "SELECT 1"}],
    )
    assert ex.retrieve("revenue by country") == []


def test_save_dedupes_identical_question(tmp_path, monkeypatch):
    store = _seed(
        tmp_path,
        monkeypatch,
        [{"question": "same q", "sql": "SELECT 1"}],
    )
    ex.save("Same Q", "SELECT 2")
    assert len(ex.load()) == 1


def test_save_appends_new(tmp_path, monkeypatch):
    _seed(tmp_path, monkeypatch, [])
    ex.save("new q", "SELECT 9")
    assert ex.load()[0].sql == "SELECT 9"


def test_few_shot_block_empty_when_no_hits(tmp_path, monkeypatch):
    _seed(tmp_path, monkeypatch, [])
    assert ex.few_shot_block("anything") == ""
