import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

from ai_radar import collectors
from ai_radar.config import Config


def row(owner: str, name: str, description: str, stars: str, period_stars: str, period: str = "this week") -> str:
    """One <article class="Box-row"> as served by github.com/trending (trimmed)."""
    return f"""
<article class="Box-row">
  <div class="float-right d-flex"><a href="/login?return_to=%2F{owner}%2F{name}" rel="nofollow">Star</a></div>
  <h2 class="h3 lh-condensed">
    <a data-hydro-click="{{&quot;event_type&quot;:&quot;explore.click&quot;}}" href="/{owner}/{name}" class="Link">
      <span data-view-component="true" class="text-normal">
        {owner} /
</span>
      {name}</a>  </h2>
    <p class="col-9 color-fg-muted my-1 tmp-pr-4">
      {description}
    </p>
  <div class="f6 color-fg-muted mt-2">
      <span itemprop="programmingLanguage">TypeScript</span>
      <a href="/{owner}/{name}/stargazers" class="Link Link--muted d-inline-block"><svg></svg>
        {stars}</a>
      <a href="/{owner}/{name}/forks" class="Link Link--muted d-inline-block"><svg></svg>
        1,431</a>
      <span data-view-component="true" class="d-inline-block float-sm-right">
        <svg></svg>
        {period_stars} {period}
</span>  </div>
</article>"""


WEEKLY = "<html><body>" + "".join([
    row("backnotprop", "plannotator",
        "The workspace to stay in the loop and on top of agents - annotate, review code &amp; send feedback to agents.",
        "14,802", "2,395 stars"),
    row("someone", "css-grid-tricks", "A collection of CSS layout recipes.", "3,100", "900 stars"),
]) + "</body></html>"

DAILY = "<html><body>" + row("backnotprop", "plannotator", "Review surface for coding agents.", "14,900",
                              "410 stars", "today") + "</body></html>"


class TestTrending(unittest.TestCase):
    def setUp(self):
        self.cfg = Config(home=Path("/nonexistent"))

    def test_parse_reads_name_description_and_period_stars(self):
        repos = collectors.parse_trending(WEEKLY)
        self.assertEqual([r["full_name"] for r in repos], ["backnotprop/plannotator", "someone/css-grid-tricks"])
        p = repos[0]
        self.assertEqual(p["stars"], 14802)
        self.assertEqual(p["period_stars"], 2395)
        self.assertEqual(p["language"], "TypeScript")
        self.assertIn("review code & send feedback", p["description"])

    def test_only_ai_repos_are_kept_and_old_repos_get_recent_star_rate(self):
        pages = {"daily": DAILY, "weekly": WEEKLY}
        with mock.patch.object(collectors, "http_get",
                               side_effect=lambda url, *a, **k: pages[url.rsplit("=", 1)[1]].encode()):
            items = collectors.github_trending(self.cfg)
        self.assertEqual([i["id"] for i in items], ["repo:backnotprop/plannotator"])  # CSS repo dropped
        it = items[0]
        self.assertEqual(it["category"], "tool")
        self.assertEqual(it["source"], "GitHub Trending")
        self.assertEqual(it["url"], "https://github.com/backnotprop/plannotator")
        # Best rate of the two pages: 410/day today beats 2395/7 ≈ 342/day this week.
        self.assertEqual(it["signals"]["stars_per_day"], 410.0)
        self.assertEqual(it["signals"]["trending"], "daily")
        self.assertEqual(it["signals"]["stars"], 14900)

    def test_one_failing_page_keeps_the_other(self):
        def fake(url, *a, **k):
            if url.endswith("daily"):
                raise OSError("timeout")
            return WEEKLY.encode()
        with mock.patch.object(collectors, "http_get", side_effect=fake):
            items = collectors.github_trending(self.cfg)
        self.assertEqual(items[0]["signals"]["trending"], "weekly")
        self.assertAlmostEqual(items[0]["signals"]["stars_per_day"], 342.1)

    def test_both_pages_failing_raises(self):
        with mock.patch.object(collectors, "http_get", side_effect=OSError("down")):
            with self.assertRaises(RuntimeError):
                collectors.github_trending(self.cfg)

    def test_language_pages_are_read_and_tagged(self):
        self.cfg.trending_languages = ["java"]
        urls = []

        def fake(url, *a, **k):
            urls.append(url)
            if "/trending/java" in url:
                return ("<html>" + row("spring-projects", "spring-ai", "An application framework for AI engineering",
                                       "9,000", "120 stars", "today") + "</html>").encode()
            return b"<html></html>"
        with mock.patch.object(collectors, "http_get", side_effect=fake):
            items = collectors.github_trending(self.cfg)
        self.assertEqual(sorted(urls), sorted([
            "https://github.com/trending?since=daily", "https://github.com/trending?since=weekly",
            "https://github.com/trending/java?since=daily", "https://github.com/trending/java?since=weekly"]))
        self.assertEqual(items[0]["id"], "repo:spring-projects/spring-ai")
        self.assertEqual(items[0]["signals"]["trending"], "daily java")

    def test_registered_as_a_collector(self):
        self.assertIs(collectors.COLLECTORS["github_trending"], collectors.github_trending)
        self.assertIs(collectors.COLLECTORS["maven"], collectors.maven_releases)


def metadata(release: str, updated: str) -> bytes:
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<metadata><groupId>g</groupId><artifactId>a</artifactId><versioning><latest>{release}</latest>
<release>{release}</release><versions><version>{release}</version></versions>
<lastUpdated>{updated}</lastUpdated></versioning></metadata>""".encode()


class TestMaven(unittest.TestCase):
    def setUp(self):
        self.cfg = Config(home=Path("/nonexistent"))
        self.cfg.window_days = 14
        self.cfg.maven_watch = ["dev.langchain4j:langchain4j", "org.old:stale", "bad-coordinate"]

    def test_recent_releases_become_items_old_ones_are_skipped(self):
        recent = (datetime.now(timezone.utc) - timedelta(days=2)).strftime("%Y%m%d%H%M%S")
        pages = {
            "https://repo1.maven.org/maven2/dev/langchain4j/langchain4j/maven-metadata.xml": metadata("1.24.0", recent),
            "https://repo1.maven.org/maven2/org/old/stale/maven-metadata.xml": metadata("0.1", "20240101000000"),
        }
        with mock.patch.object(collectors, "http_get", side_effect=lambda url, *a, **k: pages[url]):
            items = collectors.maven_releases(self.cfg)
        self.assertEqual(len(items), 1)
        it = items[0]
        self.assertEqual(it["id"], "maven:dev.langchain4j:langchain4j:1.24.0")
        self.assertEqual(it["title"], "dev.langchain4j:langchain4j 1.24.0")
        self.assertEqual(it["source"], "Maven Central")
        self.assertEqual(it["url"], "https://central.sonatype.com/artifact/dev.langchain4j/langchain4j/1.24.0")
        self.assertEqual(it["signals"]["release"], "1.24.0")

    def test_failing_artifact_does_not_lose_the_others(self):
        recent = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")

        def fake(url, *a, **k):
            if "langchain4j" in url:
                raise OSError("timeout")
            return metadata("2.0", recent)
        with mock.patch.object(collectors, "http_get", side_effect=fake):
            items = collectors.maven_releases(self.cfg)
        self.assertEqual([i["id"] for i in items], ["maven:org.old:stale:2.0"])


if __name__ == "__main__":
    unittest.main()


class TestTrendingFixes(unittest.TestCase):
    def setUp(self):
        import tempfile
        from ai_radar.store import Store
        self.tmp = tempfile.TemporaryDirectory()
        self.cfg = Config(home=Path(self.tmp.name))
        self.store = Store(self.cfg.db_path)

    def tearDown(self):
        self.store.close()
        self.tmp.cleanup()

    def _row(self, id):
        r = self.store.conn.execute("SELECT signals, published_at FROM items WHERE id = ?", (id,)).fetchone()
        import json
        return json.loads(r["signals"]), r["published_at"]

    def test_trending_merges_with_github_search_item(self):
        base = {"id": "repo:a/b", "category": "tool", "title": "a/b", "url": "https://github.com/a/b",
                "source": "GitHub", "published_at": "2026-11-01T00:00:00Z",
                "signals": {"stars": 300, "stars_per_day": 100.0, "topics": ["mcp"], "awesome": False}}
        self.store.upsert(base)
        trend = {**base, "source": "GitHub Trending", "merge_signals": True,
                 "published_at": "2026-11-24T08:00:00+00:00",
                 "signals": {"stars": 320, "stars_per_day": 40.0, "trending": "daily", "language": "Java"}}
        self.store.upsert(trend)
        s, published = self._row("repo:a/b")
        self.assertEqual(s["topics"], ["mcp"])          # GitHub search signals kept
        self.assertEqual(s["stars_per_day"], 100.0)     # today's best rate kept
        self.assertEqual(s["trending"], "daily")        # trending signals added
        self.assertEqual(s["stars"], 320)
        self.assertEqual(published, "2026-11-24T08:00:00+00:00")  # date moved forward

    def test_date_never_moves_back(self):
        it = {"id": "repo:x/y", "category": "tool", "title": "x/y", "url": "https://github.com/x/y",
              "source": "GitHub Trending", "merge_signals": True, "published_at": "2026-11-24T08:00:00+00:00",
              "signals": {"stars_per_day": 5.0}}
        self.store.upsert(it)
        self.store.upsert({**it, "published_at": "2026-11-20T08:00:00+00:00"})
        self.assertEqual(self._row("repo:x/y")[1], "2026-11-24T08:00:00+00:00")

    def test_hyphenated_keyword_matches(self):
        self.cfg.github_keywords = ["langchain4j-spring"]
        self.cfg.trending_languages = []
        page = "<html>" + row("o", "r", "Starter for langchain4j_spring apps", "10", "5 stars", "today") + "</html>"
        with mock.patch.object(collectors, "http_get", return_value=page.encode()):
            self.assertEqual([i["id"] for i in collectors.github_trending(self.cfg)], ["repo:o/r"])

    def test_markup_change_is_reported(self):
        self.cfg.trending_languages = []
        with mock.patch.object(collectors, "http_get", return_value=b"<html><div>new layout</div></html>"):
            with self.assertRaises(RuntimeError):
                collectors.github_trending(self.cfg)

    def test_invalid_maven_coordinate_does_not_hide_total_failure(self):
        self.cfg.maven_watch = ["not a coordinate", "g.x:a"]
        with mock.patch.object(collectors, "http_get", side_effect=OSError("down")):
            with self.assertRaises(RuntimeError):
                collectors.maven_releases(self.cfg)
