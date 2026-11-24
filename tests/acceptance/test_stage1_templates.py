import re
from pathlib import Path

import pytest
from jinja2 import ChoiceLoader, DictLoader, Environment, FileSystemLoader, select_autoescape

SOURCE_ROOT = Path(__file__).resolve().parents[2] / "src" / "dashboard"
TEMPLATES_DIR = SOURCE_ROOT / "templates"
STATIC_DIR = SOURCE_ROOT / "static"
CHILD_TEMPLATE = (
    '{% extends "base.html" %}'
    "{% block title %}{{ page_title }}{% endblock %}"
    "{% block content %}<p>{{ body_text }}</p>{% endblock %}"
)


def make_environment() -> Environment:
    return Environment(
        loader=ChoiceLoader(
            [FileSystemLoader(str(TEMPLATES_DIR)), DictLoader({"child.html": CHILD_TEMPLATE})]
        ),
        autoescape=select_autoescape(["html"]),
    )


def render_base(**context: object) -> str:
    return make_environment().get_template("base.html").render(**context)


@pytest.mark.acceptance
def test_base_has_viewport_meta_and_russian_language() -> None:
    html = render_base()
    assert '<meta name="viewport" content="width=device-width, initial-scale=1">' in html
    assert '<html lang="ru"' in html


@pytest.mark.acceptance
def test_base_links_local_stylesheet_and_vendor_scripts() -> None:
    html = render_base()
    assert 'href="/static/app.css"' in html
    assert 'src="/static/vendor/htmx.min.js"' in html
    assert 'src="/static/vendor/chart.umd.min.js"' in html


@pytest.mark.acceptance
def test_base_has_no_external_script_or_link_urls() -> None:
    html = render_base()
    references = re.findall(r"<script\b[^>]*\bsrc\s*=\s*[\"']([^\"']*)[\"']", html)
    references += re.findall(r"<link\b[^>]*\bhref\s*=\s*[\"']([^\"']*)[\"']", html)
    assert len(references) >= 3
    for reference in references:
        assert not reference.lower().startswith(("http://", "https://", "//"))
        assert reference.startswith("/static/")


@pytest.mark.acceptance
def test_base_source_has_no_absolute_urls() -> None:
    source = (TEMPLATES_DIR / "base.html").read_text(encoding="utf-8")
    assert "http://" not in source
    assert "https://" not in source


@pytest.mark.acceptance
def test_navigation_is_absent_without_current_user() -> None:
    assert "<nav" not in render_base()


@pytest.mark.acceptance
def test_navigation_is_absent_when_current_user_is_none() -> None:
    assert "<nav" not in render_base(current_user=None)


@pytest.mark.acceptance
def test_navigation_is_present_when_current_user_is_defined() -> None:
    assert "<nav" in render_base(current_user={"login": "anna"})


@pytest.mark.acceptance
def test_child_template_fills_title_and_content_blocks() -> None:
    html = make_environment().get_template("child.html").render(page_title="Т1", body_text="Тело")
    assert "<title>Т1</title>" in html
    assert "<p>Тело</p>" in html
    assert 'href="/static/app.css"' in html


@pytest.mark.acceptance
def test_child_template_escapes_markup_in_blocks() -> None:
    html = (
        make_environment()
        .get_template("child.html")
        .render(page_title="<b>x</b>", body_text="<script>alert(1)</script>")
    )
    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in html
    assert "<title>&lt;b&gt;x&lt;/b&gt;</title>" in html


@pytest.mark.acceptance
def test_static_stylesheet_is_present_and_not_empty() -> None:
    stylesheet = STATIC_DIR / "app.css"
    assert stylesheet.is_file()
    assert stylesheet.stat().st_size > 0


@pytest.mark.acceptance
@pytest.mark.parametrize(
    "name",
    ["htmx.min.js", "chart.umd.min.js", "htmx.LICENSE.txt", "chart.js.LICENSE.txt"],
)
def test_vendor_file_exists_and_is_not_empty(name: str) -> None:
    path = STATIC_DIR / "vendor" / name
    assert path.is_file()
    assert path.stat().st_size > 0


@pytest.mark.acceptance
def test_vendor_scripts_look_like_the_expected_libraries() -> None:
    htmx = (STATIC_DIR / "vendor" / "htmx.min.js").read_text(encoding="utf-8")
    chart = (STATIC_DIR / "vendor" / "chart.umd.min.js").read_text(encoding="utf-8")
    assert "htmx" in htmx
    assert "Chart" in chart
