"""Tests for server-rendered SEO pages (law/seo.py + server routes)."""

import json
import re

import pytest

from law import seo
from law.data_loader import load_law_schools
from law.server import app

BASE = "https://opportunitylaw.test"


@pytest.fixture(scope="module")
def schools():
    return load_law_schools()


@pytest.fixture
def client():
    return app.test_client()


def _jsonld(html):
    blocks = re.findall(r'application/ld\+json">(.*?)</script>', html, re.S)
    return [json.loads(b) for b in blocks]


# --- slug helpers -----------------------------------------------------------

class TestSlugs:
    def test_state_slug_roundtrip(self):
        assert seo.state_slug("TX") == "texas"
        assert seo.state_from_slug("texas") == "TX"
        assert seo.state_slug("DC") == "district-of-columbia"
        assert seo.state_from_slug("district-of-columbia") == "DC"

    def test_state_from_slug_accepts_code(self):
        assert seo.state_from_slug("ny") == "NY"

    def test_state_from_slug_unknown(self):
        assert seo.state_from_slug("atlantis") is None

    def test_url_builders(self):
        assert seo.school_url({"id": "x-law"}) == "/law-schools/x-law"
        assert seo.state_url("CA") == "/law-schools-in/california"


# --- formatters -------------------------------------------------------------

class TestFormatters:
    def test_none_safe(self):
        assert seo._pct(None) == "—"
        assert seo._money(None) == "—"
        assert seo._num(None) == "—"

    def test_values(self):
        assert seo._pct(0.4085, 0) == "41%"
        assert seo._money(73950) == "$73,950"
        assert seo._rank(20) == "#20"
        assert seo._rank(999) == "Unranked"


# --- render_school ----------------------------------------------------------

class TestSchoolPage:
    def test_core_elements(self, schools):
        s = next(x for x in schools if x["id"] == "notre-dame-law")
        html = seo.render_school(s, schools, BASE)
        assert "<title>" in html and s["name"] in html
        assert f'canonical" href="{BASE}/law-schools/notre-dame-law"' in html
        assert "Find your matches" in html
        # links to its state page and the index
        assert "/law-schools-in/indiana" in html
        assert "/law-schools" in html

    def test_jsonld_valid(self, schools):
        s = next(x for x in schools if x["id"] == "notre-dame-law")
        blocks = _jsonld(seo.render_school(s, schools, BASE))
        types = [b["@type"] for b in blocks[0]]
        assert "CollegeOrUniversity" in types
        assert "BreadcrumbList" in types

    def test_missing_optional_fields_dont_crash(self, schools):
        # A school lacking website_url / placement_states still renders.
        s = next(x for x in schools if not x.get("website_url"))
        html = seo.render_school(s, schools, BASE)
        assert s["name"] in html and html.startswith("<!doctype html>")

    def test_special_chars_escaped(self, schools):
        s = next((x for x in schools if "'" in x["name"] or "&" in x["name"]), None)
        if s is None:
            pytest.skip("no school name with special chars")
        html = seo.render_school(s, schools, BASE)
        assert "&#x27;" in html or "&amp;" in html


class TestFaqAndProse:
    def test_intro_and_faq_render(self, schools):
        s = next(x for x in schools if x["id"] == "notre-dame-law")
        html = seo.render_school(s, schools, BASE)
        assert "is a private law school" in html
        assert "Frequently asked questions" in html

    def test_faqpage_jsonld_present_and_valid(self, schools):
        s = next(x for x in schools if x["id"] == "notre-dame-law")
        blocks = _jsonld(seo.render_school(s, schools, BASE))
        faq = next(b for b in blocks[0] if b["@type"] == "FAQPage")
        assert len(faq["mainEntity"]) >= 4
        q0 = faq["mainEntity"][0]
        assert q0["@type"] == "Question"
        assert q0["acceptedAnswer"]["text"]

    def test_all_answers_clean(self, schools):
        # Every generated answer is non-empty and free of formatting artifacts
        # from missing fields (double spaces, dangling " .").
        for s in schools:
            for q, a in seo._school_faqs(s):
                assert a and a.strip() == a
                assert "  " not in a
                assert not a.endswith(" .")

    def test_sparse_school_yields_fewer_faqs(self, schools):
        full = seo._school_faqs(next(x for x in schools if x["id"] == "notre-dame-law"))
        # A brand-new school with honest-zero outcomes should answer fewer Qs.
        sparse = seo._school_faqs(
            next(x for x in schools if x["id"] == "wilmington-university-school-of-law"))
        assert len(sparse) <= len(full)
        assert all(a for _, a in sparse)

    def test_state_faqs(self, schools):
        faqs = seo._state_faqs("Indiana", [s for s in schools if s.get("state") == "IN"])
        joined = " ".join(q for q, _ in faqs)
        assert "How many law schools are in Indiana?" in joined
        assert seo._state_faqs("Indiana", []) == []


# --- render_state -----------------------------------------------------------

class TestStatePage:
    def test_lists_located_schools(self, schools):
        html = seo.render_state("IN", schools, BASE)
        assert "Indiana" in html
        assert "/law-schools/notre-dame-law" in html

    def test_feeder_section(self, schools):
        # NY draws grads from many schools — the feeder table should appear.
        html = seo.render_state("NY", schools, BASE)
        assert "send the most grads" in html

    def test_itemlist_jsonld(self, schools):
        blocks = _jsonld(seo.render_state("IN", schools, BASE))
        itemlist = next(b for b in blocks[0] if b["@type"] == "ItemList")
        assert len(itemlist["itemListElement"]) >= 1


# --- render_index + sitemap + robots ---------------------------------------

class TestIndexSitemap:
    def test_index_links_all_schools(self, schools):
        html = seo.render_index(schools, BASE)
        assert html.count("/law-schools/") >= len(schools)

    def test_sitemap_completeness(self, schools):
        xml = seo.render_sitemap(schools, BASE)
        states = {(s.get("state") or "").upper() for s in schools if s.get("state")}
        # schools + states + "/" + "/law-schools"
        assert xml.count("<loc>") == len(schools) + len(states) + 2
        assert xml.startswith("<?xml")
        assert f"{BASE}/law-schools/notre-dame-law" in xml

    def test_robots_points_to_sitemap(self):
        txt = seo.render_robots(BASE)
        assert f"Sitemap: {BASE}/sitemap.xml" in txt
        assert "Disallow: /api/" in txt


# --- routes -----------------------------------------------------------------

class TestRoutes:
    def test_pages_serve(self, client):
        assert client.get("/law-schools").status_code == 200
        assert client.get("/law-schools/notre-dame-law").status_code == 200
        assert client.get("/law-schools-in/texas").status_code == 200
        assert client.get("/sitemap.xml").mimetype == "application/xml"
        assert client.get("/robots.txt").mimetype == "text/plain"

    def test_unknown_slug_404(self, client):
        assert client.get("/law-schools/nope").status_code == 404
        assert client.get("/law-schools-in/atlantis").status_code == 404

    def test_public_path_predicate(self):
        from law.server import _is_public_path
        assert _is_public_path("/law-schools")
        assert _is_public_path("/law-schools/notre-dame-law")
        assert _is_public_path("/law-schools-in/texas")
        assert _is_public_path("/sitemap.xml")
        assert not _is_public_path("/api/match")
        assert not _is_public_path("/stats")
        assert not _is_public_path("/")
