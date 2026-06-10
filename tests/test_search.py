from iya_bot.infrastructure.search.duckduckgo import parse_results
from iya_bot.infrastructure.search.http_fetcher import html_to_text, is_blocked_ip, url_is_blocked

_SAMPLE_DDG_HTML = """
<div class="result results_links">
  <a rel="nofollow" class="result__a" href="//duckduckgo.com/l/?uddg=https%3A%2F%2Fexample.com%2Fpage&amp;rut=abc">
    Example <b>Title</b> One
  </a>
  <a class="result__snippet" href="//duckduckgo.com/l/?uddg=x">This is the <b>first</b> snippet.</a>
</div>
<div class="result results_links">
  <a rel="nofollow" class="result__a" href="https://direct.example.org/two">Second Result</a>
  <a class="result__snippet" href="#">Second snippet &amp; text.</a>
</div>
"""


def test_parse_results_extracts_title_url_snippet():
    results = parse_results(_SAMPLE_DDG_HTML, max_results=5)
    assert len(results) == 2

    first = results[0]
    assert first.title == "Example Title One"
    assert first.url == "https://example.com/page"  # uddg-редирект раскодирован
    assert first.snippet == "This is the first snippet."

    second = results[1]
    assert second.title == "Second Result"
    assert second.url == "https://direct.example.org/two"
    assert second.snippet == "Second snippet & text."


def test_parse_results_respects_max_results():
    results = parse_results(_SAMPLE_DDG_HTML, max_results=1)
    assert len(results) == 1


def test_parse_results_handles_empty_html():
    assert parse_results("<html></html>", max_results=5) == []


def test_html_to_text_strips_tags_and_scripts():
    html = """
    <html><head><style>.x{color:red}</style><script>alert(1)</script></head>
    <body><h1>Заголовок</h1><p>Абзац с <a href="#">ссылкой</a>.</p></body></html>
    """
    text = html_to_text(html)
    assert "Заголовок" in text
    assert "Абзац с" in text
    assert "ссылкой" in text
    assert "alert" not in text
    assert "color:red" not in text
    assert "<" not in text


def test_is_blocked_ip_rejects_internal_ranges():
    assert is_blocked_ip("127.0.0.1")
    assert is_blocked_ip("10.0.0.5")
    assert is_blocked_ip("192.168.1.1")
    assert is_blocked_ip("172.16.0.1")
    assert is_blocked_ip("169.254.169.254")  # метаданные облака
    assert is_blocked_ip("0.0.0.0")
    assert is_blocked_ip("::1")
    assert is_blocked_ip("not-an-ip")


def test_is_blocked_ip_allows_public():
    assert not is_blocked_ip("93.184.216.34")
    assert not is_blocked_ip("2606:2800:220:1:248:1893:25c8:1946")


async def test_url_is_blocked_rejects_bad_scheme_and_internal_hosts():
    assert await url_is_blocked("ftp://example.com/x")
    assert await url_is_blocked("file:///etc/passwd")
    assert await url_is_blocked("http://127.0.0.1:8080/admin")
    assert await url_is_blocked("http://169.254.169.254/latest/meta-data/")
    assert await url_is_blocked("http://localhost/")
    assert await url_is_blocked("http:///no-host")
