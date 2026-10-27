"""A cached greeting must not be accepted as proof of provider health."""
import unittest
from types import SimpleNamespace
from test_meterless import validate_probe


def reply(content="ready-nonce", finish="stop", cached=False):
    return SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=content), finish_reason=finish)],
        model_dump=lambda: {"meterless": {"from_cache": cached, "routed_model": "fixture/model"}},
    )


class ProbeTests(unittest.TestCase):
    def test_uncached_matching_complete_response_is_ready(self):
        self.assertEqual(validate_probe(reply(), "ready-nonce")["status"], "ready")

    def test_cached_response_is_not_provider_health(self):
        with self.assertRaises(ValueError): validate_probe(reply(cached=True), "ready-nonce")

    def test_unknown_cache_origin_is_not_accepted(self):
        with self.assertRaises(ValueError): validate_probe(reply(cached=None), "ready-nonce")

    def test_stale_or_incomplete_or_empty_response_is_rejected(self):
        for value in (reply(content="ready-old"), reply(finish="length"), reply(content=None)):
            with self.assertRaises(ValueError): validate_probe(value, "ready-nonce")


if __name__ == "__main__":
    unittest.main()
