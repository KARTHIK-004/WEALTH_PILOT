"""Versioned candidate filters (B2-H section 4). Pure functions over one parsed row.

The specification file is identified by version *and* SHA-256: ``load_spec`` refuses a file whose
hash (computed over LF-normalised bytes, so a Git line-ending conversion cannot change it) differs
from the registry. Every output row carries ``filter_version``. No switch alters rule meaning.

All series here are CANDIDATES for labelled review, not approved production filters. Broad gold and
rates themes are flags only. No precision or recall is claimed.
"""

from __future__ import annotations

import hashlib
import html
import re
import unicodedata
from collections import Counter
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

import yaml

from wealthpilot.data.gdelt.errors import FilterSpecError
from wealthpilot.data.gdelt.parser import GkgRow

SPEC_DIR = Path(__file__).resolve().parent / "specs"
REGISTRY: dict[str, str] = {
    "gdelt_filter_v1": "73788c1ff7a48897863116cefc3a1d98f30a73e490f5dffbc6c8736b1341cff8",
}
SERIES = ("EQUITY_US", "RATES_US", "GOLD")
_NON_KEPT = re.compile(r"[^a-z0-9&$]+")


def spec_sha256(path: Path) -> str:
    data = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(data).hexdigest()


@dataclass(frozen=True)
class FilterSpec:
    version: str
    sha256: str
    raw: dict[str, Any]


def load_spec(version: str = "gdelt_filter_v1", *, spec_dir: Path = SPEC_DIR,
              registry: dict[str, str] | None = None) -> FilterSpec:
    registry = REGISTRY if registry is None else registry
    if version not in registry:
        raise FilterSpecError(f"unregistered filter version {version!r}")
    path = spec_dir / f"{version}.yaml"
    if not path.exists():
        raise FilterSpecError(f"spec file missing: {path}")
    digest = spec_sha256(path)
    if digest != registry[version]:
        raise FilterSpecError(f"{path.name} SHA-256 {digest} differs from the registered {registry[version]}; "
                              "a changed rule needs a new version file")
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict) or raw.get("version") != version:
        raise FilterSpecError(f"{path.name} does not declare version {version}")
    if raw.get("status") != "candidate_for_labelled_review":
        raise FilterSpecError(f"{path.name} must stay marked as a candidate for labelled review")
    return FilterSpec(version, digest, raw)


# ---------------------------------------------------------------- normalisation helpers

def normalise_title(title: str) -> str:
    text = unicodedata.normalize("NFKC", html.unescape(title)).casefold()
    return " ".join(_NON_KEPT.sub(" ", text).split())


def title_hash(title_norm: str, min_chars: int) -> str | None:
    if len(title_norm) < min_chars:
        return None  # generic or short titles never merge stories
    return hashlib.sha256(title_norm.encode("utf-8")).hexdigest()


def canonical_url(url: str) -> str:
    """Lower-case host; drop scheme, leading ``www.``, query, fragment and trailing ``/``."""
    parts = urlsplit(url.strip())
    if not parts.netloc:
        return url.strip().rstrip("/")
    host = parts.netloc.lower()
    if host.startswith("www."):
        host = host[4:]
    return (host + parts.path).rstrip("/")


def has_phrase(title_norm: str, phrase: str) -> bool:
    return f" {phrase} " in f" {title_norm} "


def matched(title_norm: str, phrases: list[str]) -> list[str]:
    return [p for p in phrases if has_phrase(title_norm, p)]


def theme_set(v1_themes: str) -> frozenset[str]:
    return frozenset(t for t in v1_themes.split(";") if t)


def theme_mentions(v2_themes: str) -> Counter[str]:
    counts: Counter[str] = Counter()
    for entry in v2_themes.split(";"):
        if entry:
            counts[entry.split(",", 1)[0]] += 1
    return counts


def org_set(v1_orgs: str) -> frozenset[str]:
    return frozenset(o.strip() for o in v1_orgs.split(";") if o.strip())


def location_info(v1_locations: str, us_types: set[int], us_code: str) -> tuple[bool, tuple[str, ...]]:
    us, countries = False, set()
    for entry in v1_locations.split(";"):
        if not entry:
            continue
        f = entry.split("#")
        if len(f) < 3:
            continue
        code = f[2]
        if code:
            countries.add(code)
        try:
            loc_type = int(f[0])
        except ValueError:
            loc_type = -1
        if loc_type in us_types or code == us_code:
            us = True
    return us, tuple(sorted(countries))


def tone_fields(tone: str) -> tuple[str, ...]:
    parts = tone.split(",")
    return tuple(parts[:7]) + ("",) * (7 - min(len(parts), 7))


# ---------------------------------------------------------------- classification

@dataclass(frozen=True)
class Classification:
    title_norm: str
    title_hash: str | None
    url_canonical: str
    us_location: bool
    us_relevant: bool
    country_codes: tuple[str, ...]
    company_item: bool
    flag_themes: tuple[str, ...]
    candidate_mentions: tuple[tuple[str, int], ...]   # candidate themes present, with V2 mention counts
    econ_themes: tuple[str, ...]
    us_market_orgs: tuple[str, ...]
    title_hits: tuple[str, ...]
    members: dict[str, bool]                          # primary series (candidates)
    s1: dict[str, bool]
    s2: dict[str, bool]
    captured: bool
    near_miss_cue: bool
    word_count: str
    tone: tuple[str, ...]


class Classifier:
    def __init__(self, spec: FilterSpec) -> None:
        r = spec.raw
        self.spec = spec
        self.min_chars = int(r["title_hash_min_chars"])
        self.us_types = set(r["us_relevance"]["location_types"])
        self.us_code = r["us_relevance"]["country_code"]
        self.us_title = list(r["us_relevance"]["title_phrases"])
        self.us_orgs = frozenset(r["us_market_orgs"])
        ci = r["company_item"]
        self.ci_tags = [t.lower() for t in ci["raw_title_tags"]]
        self.ci_cashtag = re.compile(ci["raw_title_cashtag_regex"])
        self.ci_phrases = list(ci["title_phrases"])
        self.flag_only = frozenset(r["flag_only_themes"])
        s = r["series"]
        self.eq, self.ra, self.go = s["EQUITY_US"], s["RATES_US"], s["GOLD"]
        self.rates_specific = frozenset(self.ra["specific_themes"])
        self.series_themes = frozenset({self.eq["theme"], *self.rates_specific, *self.go["themes"]})
        self.series_phrases = sorted({*self.eq["title_phrases"], *self.eq["us_conditional_title_phrases"],
                                      *self.ra["title_phrases"], *self.ra["us_conditional_title_phrases"],
                                      *self.go["title_phrases"]})
        self.s1 = r["sensitivity"]["S1"]
        cue = r["near_miss_cue"]
        self.cue_words, self.cue_prefix = list(cue["title_words"]), cue["theme_prefix"]
        self.candidate_themes = self.series_themes | self.flag_only | frozenset(
            t for v in self.s1.values() for t in v["themes"])

    def classify(self, row: GkgRow) -> Classification:
        tn = normalise_title(row.title)
        themes = theme_set(row.v1_themes)
        mentions = theme_mentions(row.v2_themes)
        orgs = org_set(row.v1_orgs)
        us_loc, countries = location_info(row.v1_locations, self.us_types, self.us_code)
        us_orgs = tuple(sorted(orgs & self.us_orgs))
        us_relevant = us_loc or bool(us_orgs) or bool(matched(tn, self.us_title))
        raw_lower = row.title.lower()
        company = (any(t in raw_lower for t in self.ci_tags) or bool(self.ci_cashtag.search(row.title))
                   or bool(matched(tn, self.ci_phrases)))

        eq_member = not company and (
            bool(matched(tn, self.eq["title_phrases"]))
            or ((mentions.get(self.eq["theme"], 0) >= int(self.eq["theme_min_mentions"])
                 or bool(matched(tn, self.eq["us_conditional_title_phrases"]))) and us_relevant))
        ra_member = not company and (
            bool(matched(tn, self.ra["title_phrases"]))
            or ((bool(themes & self.rates_specific) or bool(matched(tn, self.ra["us_conditional_title_phrases"])))
                and us_relevant))
        go_member = not company and (bool(themes & set(self.go["themes"])) or bool(matched(tn, self.go["title_phrases"])))
        members = {"EQUITY_US": eq_member, "RATES_US": ra_member, "GOLD": go_member}

        s1 = {}
        for name, rule in self.s1.items():
            kw_hit = bool(matched(tn, rule["keywords"])) or bool(orgs & set(rule["keywords"]))
            s1[name] = bool(themes & set(rule["themes"])) or kw_hit
        s2 = {
            "EQUITY_US": not company and bool(matched(tn, self.eq["title_phrases"] + self.eq["us_conditional_title_phrases"])),
            "RATES_US": not company and bool(matched(tn, self.ra["title_phrases"] + self.ra["us_conditional_title_phrases"])),
            "GOLD": not company and bool(matched(tn, self.go["title_phrases"])),
        }
        captured = (bool(themes & (self.series_themes | self.flag_only)) or bool(matched(tn, self.series_phrases))
                    or bool(us_orgs))
        econ = tuple(sorted(t for t in themes if t.startswith("ECON_")))
        cue = bool(matched(tn, self.cue_words)) or any(t.startswith(self.cue_prefix) for t in themes)
        tone = tone_fields(row.tone)
        return Classification(
            title_norm=tn, title_hash=title_hash(tn, self.min_chars), url_canonical=canonical_url(row.document_url),
            us_location=us_loc, us_relevant=us_relevant, country_codes=countries, company_item=company,
            flag_themes=tuple(sorted(themes & self.flag_only)),
            candidate_mentions=tuple(sorted((t, mentions.get(t, 0)) for t in themes & self.candidate_themes)),
            econ_themes=econ, us_market_orgs=us_orgs, title_hits=tuple(matched(tn, self.series_phrases)),
            members=members, s1=s1, s2=s2, captured=captured, near_miss_cue=(not captured) and cue,
            word_count=tone[6], tone=tone)


def in_audit_sample(record_id: str, seed: str, denominator: int) -> bool:
    """Content-independent 1-in-``denominator`` selection by record ID."""
    h = int(hashlib.sha256(f"{seed}|{record_id}".encode("ascii", "ignore")).hexdigest()[:16], 16)
    return h % denominator == 0


@lru_cache(maxsize=4)
def default_classifier(version: str = "gdelt_filter_v1") -> Classifier:
    return Classifier(load_spec(version))
