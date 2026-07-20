import unittest

from wechat_news.editor import _article_from_raw, _is_responses_compatibility_error, sanitize_wechat_html


class EditorSafetyTests(unittest.TestCase):
    def test_removes_active_content_and_unsafe_links(self) -> None:
        value = '<h2>安全标题</h2><script>alert(1)</script><a href="javascript:bad">链接</a>'
        cleaned = sanitize_wechat_html(value)
        self.assertIn("安全标题", cleaned)
        self.assertNotIn("script", cleaned.lower())
        self.assertNotIn("javascript", cleaned.lower())

    def test_parses_structured_article(self) -> None:
        raw = '{"title":"标题","digest":"摘要","content_html":"<p>正文</p>","source_notes":[]}'
        article = _article_from_raw(raw, "作者")
        self.assertEqual(article.title, "标题")
        self.assertEqual(article.author, "作者")

    def test_falls_back_only_for_compatible_endpoint_errors(self) -> None:
        class EndpointError(Exception):
            status_code = 404

        class AuthError(Exception):
            status_code = 401

        self.assertTrue(_is_responses_compatibility_error(EndpointError("not found")))
        self.assertFalse(_is_responses_compatibility_error(AuthError("unauthorized")))


if __name__ == "__main__":
    unittest.main()
