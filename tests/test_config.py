import unittest

from wechat_news.config import normalize_openai_base_url


class ConfigTests(unittest.TestCase):
    def test_adds_v1_to_relay_domain(self) -> None:
        self.assertEqual(
            normalize_openai_base_url("https://token.yiliao.hb.cn"),
            "https://token.yiliao.hb.cn/v1",
        )

    def test_does_not_duplicate_v1(self) -> None:
        self.assertEqual(
            normalize_openai_base_url("https://token.yiliao.hb.cn/v1/"),
            "https://token.yiliao.hb.cn/v1",
        )


if __name__ == "__main__":
    unittest.main()

