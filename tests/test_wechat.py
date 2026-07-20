import unittest
from unittest.mock import patch

from wechat_news.models import EditedArticle
from wechat_news.wechat import WeChatAPIError, WeChatOfficialAccount


class FakeResponse:
    def __init__(self, data: dict) -> None:
        self._data = data

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return self._data


class WeChatTests(unittest.TestCase):
    def setUp(self) -> None:
        self.client = WeChatOfficialAccount("app", "secret")
        self.client._access_token = "token"
        self.client._token_expires_at = 10**12

    @patch("wechat_news.wechat.requests.post")
    def test_add_draft_and_publish(self, post) -> None:
        post.side_effect = [FakeResponse({"media_id": "draft-1"}), FakeResponse({"publish_id": "pub-1"})]
        article = EditedArticle("标题", "摘要", "<p>正文</p>", "作者")
        self.assertEqual(self.client.add_draft(article, "thumb-1"), "draft-1")
        self.assertEqual(self.client.publish("draft-1"), "pub-1")
        self.assertTrue(post.call_args_list[0].args[0].endswith("/cgi-bin/draft/add"))
        self.assertTrue(post.call_args_list[1].args[0].endswith("/cgi-bin/freepublish/submit"))

    def test_wechat_error_is_not_ignored(self) -> None:
        with self.assertRaises(WeChatAPIError):
            self.client._validate({"errcode": 48001, "errmsg": "api unauthorized"})


if __name__ == "__main__":
    unittest.main()

