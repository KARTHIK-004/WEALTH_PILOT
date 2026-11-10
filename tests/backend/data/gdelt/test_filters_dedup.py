"""Candidate filters (deterministic versions, exact rules) and causal duplicate/update handling."""

from __future__ import annotations

import shutil
from datetime import datetime, timedelta, timezone

import pytest

from wealthpilot.data.gdelt.dedup import DedupInput, StoryTracker, deduplicate, mark_same_batch
from wealthpilot.data.gdelt.errors import FilterSpecError
from wealthpilot.data.gdelt.filters import (
    REGISTRY,
    SPEC_DIR,
    Classifier,
    canonical_url,
    default_classifier,
    in_audit_sample,
    load_spec,
    normalise_title,
    spec_sha256,
)
from wealthpilot.data.gdelt.parser import GkgRow

STAMP = "20220301120000"


def row(title="SYNTHETIC TEST ROW: placeholder", themes=(), mentions=None, locations=(), orgs=(), url=None):
    themes = list(themes)
    mentions = mentions or {t: 1 for t in themes}
    v2 = ";".join(f"{t},{i}" for t, n in mentions.items() for i in range(n))
    return GkgRow(f"{STAMP}-1", 1, STAMP, "example.com", url or "https://www.example.com/a", ";".join(themes), v2,
                  ";".join(locations), ";".join(orgs), "0.5,1,0.5,1.5,20,0,250", title, None)


US = "3#Springfield, Illinois, United States#US#USIL#39.8#-89.6#1"
UK = "4#London, London, City of, United Kingdom#UK#UKH9#51.5#-0.1#-2601889"


@pytest.fixture(scope="module")
def clf() -> Classifier:
    return default_classifier()


# ---------------------------------------------------------------- versions

def test_spec_matches_its_registered_hash_and_is_a_candidate():
    spec = load_spec()
    assert spec.sha256 == REGISTRY["gdelt_filter_v1"]
    assert spec.raw["status"] == "candidate_for_labelled_review"


def test_edited_spec_without_new_version_is_refused(tmp_path):
    shutil.copy(SPEC_DIR / "gdelt_filter_v1.yaml", tmp_path / "gdelt_filter_v1.yaml")
    p = tmp_path / "gdelt_filter_v1.yaml"
    p.write_text(p.read_text(encoding="utf-8").replace("theme_min_mentions: 2", "theme_min_mentions: 1"), encoding="utf-8")
    with pytest.raises(FilterSpecError, match="differs from the registered"):
        load_spec(spec_dir=tmp_path)
    with pytest.raises(FilterSpecError, match="unregistered"):
        load_spec("gdelt_filter_v9")


def test_spec_marked_as_approved_is_refused_even_with_a_matching_registry(tmp_path):
    p = tmp_path / "gdelt_filter_v1.yaml"
    p.write_text((SPEC_DIR / "gdelt_filter_v1.yaml").read_text(encoding="utf-8")
                 .replace("status: candidate_for_labelled_review", "status: approved_production"), encoding="utf-8")
    with pytest.raises(FilterSpecError, match="candidate"):
        load_spec(spec_dir=tmp_path, registry={"gdelt_filter_v1": spec_sha256(p)})


def test_crlf_checkout_does_not_change_the_spec_hash(tmp_path):
    p = tmp_path / "gdelt_filter_v1.yaml"
    p.write_bytes((SPEC_DIR / "gdelt_filter_v1.yaml").read_bytes().replace(b"\n", b"\r\n"))
    assert spec_sha256(p) == REGISTRY["gdelt_filter_v1"]


# ---------------------------------------------------------------- normalisation

def test_title_normalisation_and_url_canonicalisation():
    assert normalise_title("SYNTHETIC: U.S. Stocks &amp; S&P 500!") == "synthetic u s stocks & s&p 500"
    assert normalise_title("ＳＹＮＴＨＥＴＩＣ Ｎａｓｄａｑ") == "synthetic nasdaq"          # NFKC
    assert canonical_url("HTTPS://WWW.Example.COM/Path/x/?a=1#frag") == "example.com/Path/x"
    assert canonical_url("http://example.com/Path/x") == "example.com/Path/x"


# ---------------------------------------------------------------- series rules (B2-H 4.4)

def test_equity_needs_two_mentions_and_us_relevance_or_a_us_market_title(clf):
    two_us = clf.classify(row(themes=["ECON_STOCKMARKET"], mentions={"ECON_STOCKMARKET": 2}, locations=[US]))
    one_us = clf.classify(row(themes=["ECON_STOCKMARKET"], mentions={"ECON_STOCKMARKET": 1}, locations=[US]))
    two_uk = clf.classify(row(themes=["ECON_STOCKMARKET"], mentions={"ECON_STOCKMARKET": 2}, locations=[UK]))
    title = clf.classify(row(title="SYNTHETIC TEST ROW: Wall Street closes", locations=[UK]))
    assert two_us.members["EQUITY_US"] and not one_us.members["EQUITY_US"] and not two_uk.members["EQUITY_US"]
    assert title.members["EQUITY_US"]
    assert one_us.captured and not one_us.near_miss_cue            # captured via the series theme


def test_company_notices_are_flagged_and_excluded_from_every_series(clf):
    for title in ("SYNTHETIC Acme Corp (NASDAQ:ACME) shares bought by Example LLC",
                  "SYNTHETIC $ACME price target raised on Wall Street",
                  "SYNTHETIC director sells stake in gold miner"):
        c = clf.classify(row(title=title, themes=["ECON_STOCKMARKET", "ECON_GOLDPRICE"],
                             mentions={"ECON_STOCKMARKET": 3, "ECON_GOLDPRICE": 1}, locations=[US]))
        assert c.company_item and not any(c.members.values())


def test_rates_need_us_relevance_unless_the_title_names_the_fed(clf):
    assert clf.classify(row(themes=["ECON_CENTRALBANK"], locations=[US])).members["RATES_US"]
    assert not clf.classify(row(themes=["ECON_CENTRALBANK"], locations=[UK])).members["RATES_US"]
    assert clf.classify(row(title="SYNTHETIC Federal Reserve holds", locations=[UK])).members["RATES_US"]
    broad = clf.classify(row(themes=["ECON_INFLATION"], locations=[US]))      # broad theme: flag only
    assert broad.captured and not broad.members["RATES_US"] and broad.flag_themes == ("ECON_INFLATION",)


def test_gold_anchor_theme_has_no_us_requirement_and_broad_gold_is_a_flag(clf):
    assert clf.classify(row(themes=["ECON_GOLDPRICE"], locations=[UK])).members["GOLD"]
    wb = clf.classify(row(themes=["WB_2936_GOLD"]))
    assert wb.captured and not wb.members["GOLD"] and wb.flag_themes == ("WB_2936_GOLD",)
    medal = clf.classify(row(title="SYNTHETIC athlete wins gold medal"))
    assert not medal.members["GOLD"] and not medal.captured and medal.near_miss_cue
    lookalike = clf.classify(row(themes=["TAX_TERROR_GROUP_GOLDEN_DAWN"]))
    assert not lookalike.captured and not lookalike.members["GOLD"]


def test_us_pronoun_and_fed_are_not_matches(clf):
    c = clf.classify(row(title="SYNTHETIC join us for the fed meeting"))
    assert not c.us_relevant and not c.captured and c.near_miss_cue        # "fed" is only a near-miss cue


def test_sensitivity_variants(clf):
    c = clf.classify(row(title="SYNTHETIC bonds rally", themes=["ECON_IPO"]))
    assert c.s1["EQUITY_US"] and c.s1["RATES_US"]                  # B2-F broad rule: any core theme or keyword
    assert not c.members["EQUITY_US"] and not c.members["RATES_US"]
    s2 = clf.classify(row(title="SYNTHETIC stock market falls"))
    assert s2.s2["EQUITY_US"] and not s2.members["EQUITY_US"]       # title-only variant, no US requirement


def test_classification_is_deterministic_and_audit_selection_is_content_independent(clf):
    r = row(themes=["ECON_STOCKMARKET"], mentions={"ECON_STOCKMARKET": 2}, locations=[US])
    assert clf.classify(r) == clf.classify(r)
    picks = sum(in_audit_sample(f"{STAMP}-{i}", "seed", 1000) for i in range(200_000))
    assert 140 <= picks <= 260                                      # ~1 in 1,000
    assert in_audit_sample("x-1", "seed", 1000) == in_audit_sample("x-1", "seed", 1000)


# ---------------------------------------------------------------- duplicates and updates

T0 = datetime(2022, 3, 1, 12, 15, tzinfo=timezone.utc)


def d(rid, batch, seq, at, url, th="h" * 64, wc="250"):
    return DedupInput(rid, batch, seq, at, url, th, wc)


def test_same_batch_url_and_title_duplicates():
    marks = mark_same_batch([("b-2", 2, "u1", "t1"), ("b-1", 1, "u1", "t1"), ("b-3", 3, "u2", "t1"),
                             ("b-4", 4, "u3", None), ("b-5", 5, "u4", None)])
    assert marks == {"b-1": "ORIGINAL", "b-2": "DUP_SAME_BATCH", "b-3": "SYNDICATED_SAME_BATCH",
                     "b-4": "ORIGINAL", "b-5": "ORIGINAL"}


def test_reobservation_versus_update_is_kept_not_collapsed():
    rows = [d("A-1", "A", 1, T0, "u", "t1", "250"),
            d("B-1", "B", 1, T0 + timedelta(minutes=15), "u", "t1", "250"),      # same content
            d("C-1", "C", 1, T0 + timedelta(minutes=30), "u", "t2", "300")]      # changed: an update
    res = deduplicate(rows)
    assert [r.status for r in res] == ["ORIGINAL", "REOBSERVATION", "UPDATE"]
    assert res[1].reobservation_of == "A-1" and res[2].update_of == "A-1"
    assert len(res) == 3 and not res[2].new_story                   # the update is a kept row, not a new story


def test_syndication_window_is_72_hours_by_availability():
    first = d("A-1", "A", 1, T0, "u1")
    inside = d("B-1", "B", 1, T0 + timedelta(hours=71, minutes=45), "u2")
    outside = d("C-1", "C", 1, T0 + timedelta(hours=72, minutes=15), "u3")
    res = deduplicate([first, inside])
    assert res[1].status == "SYNDICATED" and res[1].story_id == "A-1"
    res2 = deduplicate([first, outside])
    assert res2[1].status == "ORIGINAL"


def test_short_titles_never_merge_and_later_rows_never_change_earlier_ones():
    a = d("A-1", "A", 1, T0, "u1", None)
    b = d("B-1", "B", 1, T0 + timedelta(minutes=15), "u2", None)
    assert [r.status for r in deduplicate([b, a])] == ["ORIGINAL", "ORIGINAL"]
    tracker = StoryTracker()
    tracker.process(b)
    with pytest.raises(ValueError, match="availability order"):
        tracker.process(a)


def test_deduplication_is_independent_of_input_order():
    rows = [d(f"{b}-{i}", b, i, T0 + timedelta(minutes=15 * k), f"u{i % 3}", f"t{i % 2}")
            for k, b in enumerate(["A", "B", "C"]) for i in range(1, 5)]
    assert deduplicate(rows) == deduplicate(list(reversed(rows)))
