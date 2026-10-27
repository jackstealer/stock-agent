import json

import yaml

from src.news.collect import append_items, parse_feed, run

SAMPLE = """<rss><channel>
<item><title>Reliance profit rises - Mint</title><link>http://x/1</link>
<pubDate>Tue, 27 Oct 2026 08:30:00 GMT</pubDate><source url="http://m">Mint</source></item>
<item><title>Reliance launches plant - ET</title><link>http://x/2</link>
<pubDate>garbage</pubDate><source>ET</source></item>
<item><title></title><link>http://x/3</link></item>
</channel></rss>"""
EMPTY = "<rss><channel></channel></rss>"
AT = "2026-10-27T13:00:00+00:00"


def test_parse_feed_extracts_fields_and_skips_blank_titles():
    items = parse_feed(SAMPLE, "A.NS", AT)
    assert len(items) == 2
    assert items[0]["published_at"] == "2026-10-27T08:30:00+00:00"
    assert items[0]["collected_at"] == AT and items[0]["source"] == "Mint"
    assert items[1]["published_at"] is None          # bad date must not crash


def test_append_is_deduplicated_and_monthly(tmp_path):
    items = parse_feed(SAMPLE, "A.NS", AT)
    assert append_items(items, tmp_path) == 2
    assert append_items(items, tmp_path) == 0
    lines = (tmp_path / "2026-10.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2 and json.loads(lines[0])["ticker"] == "A.NS"


def write_cfg(tmp_path):
    p = tmp_path / "cfg.yaml"
    p.write_text(yaml.dump({"tickers": ["A.NS", "B.NS"],
                            "news_names": {"A.NS": "Alpha", "B.NS": "Beta"}}))
    return p


def test_run_stores_headlines_and_stays_quiet_on_rerun(tmp_path, monkeypatch):
    monkeypatch.setattr("src.news.collect.time.sleep", lambda s: None)
    alerts = []
    cfg = write_cfg(tmp_path)
    kw = dict(config_path=cfg, root=tmp_path / "news", fetch=lambda q: SAMPLE,
              alert=alerts.append)
    assert run(**kw) == 0
    assert run(**kw) == 0                  # re-run: all duplicates, still not an error
    assert alerts == []


def test_one_failing_feed_alerts_but_others_are_saved(tmp_path, monkeypatch):
    monkeypatch.setattr("src.news.collect.time.sleep", lambda s: None)

    def fetch(q):
        if q == "Beta":
            raise RuntimeError("boom")
        return SAMPLE

    alerts = []
    code = run(config_path=write_cfg(tmp_path), root=tmp_path / "news",
               fetch=fetch, alert=alerts.append)
    assert code == 1 and "B.NS" in alerts[0]
    assert list((tmp_path / "news").glob("*.jsonl"))       # Alpha's items were kept


def test_empty_feeds_trigger_the_broken_feed_alert(tmp_path, monkeypatch):
    monkeypatch.setattr("src.news.collect.time.sleep", lambda s: None)
    monkeypatch.setattr("src.news.collect.datetime", _WeekdayClock)
    alerts = []
    code = run(config_path=write_cfg(tmp_path), root=tmp_path / "news",
               fetch=lambda q: EMPTY, alert=alerts.append)
    assert code == 1 and "broken" in alerts[0]


class _WeekdayClock:
    """Pretend today is a Wednesday so the test doesn't depend on the weekday."""
    from datetime import datetime as _dt, timezone as _tz

    @classmethod
    def now(cls, tz=None):
        return cls._dt(2026, 10, 28, 12, 0, tzinfo=tz or cls._tz.utc)