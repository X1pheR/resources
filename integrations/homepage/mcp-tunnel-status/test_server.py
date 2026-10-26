import importlib.util
import json
from pathlib import Path
import unittest
from urllib.parse import urlencode

spec = importlib.util.spec_from_file_location("homepage_status", Path(__file__).with_name("server.py"))
s = importlib.util.module_from_spec(spec)
spec.loader.exec_module(s)

CONTAINERS = [
    {"Id": "a" * 64, "Names": ["/openai-tunnel-general"], "State": "running", "Health": {"Status": "healthy"}, "Env": ["SECRET=do-not-leak"], "Mounts": [{"Source": "/secrets"}], "Labels": {"private": "secret"}},
    {"Id": "b" * 64, "Names": ["/openai-tunnel-dev"], "State": "running", "Health": {"Status": "unhealthy"}, "Image": "private-image", "Labels": {"secret": "secret"}},
    {"Id": "c" * 64, "Names": ["/unrelated-sensitive-container"], "State": "running", "Health": {"Status": "healthy"}, "Labels": {"secret": "secret"}},
]
ALLOWED = {"openai-tunnel-general", "openai-tunnel-dev"}


class DockerStatusTests(unittest.TestCase):
    def test_unfiltered_output_contains_only_allowed_identity_and_state(self):
        got = s.docker_list("all=1", fetch=lambda _: CONTAINERS, allowlist=ALLOWED)
        self.assertEqual(len(got), 2)
        self.assertEqual([v["Id"] for v in got], ["a" * 64, "b" * 64])
        for obj in got:
            self.assertEqual(set(obj), {"Id", "Names", "State", "Labels"})
            self.assertEqual(obj["Labels"], {})
        self.assertNotIn("SECRET", json.dumps(got))
        self.assertNotIn("private-image", json.dumps(got))

    def test_health_filter_matches_dockerode_list_containers(self):
        q = urlencode({"all": "true", "filters": json.dumps({"health": ["healthy"]})})
        got = s.docker_list(q, fetch=lambda _: CONTAINERS, allowlist=ALLOWED)
        self.assertEqual([c["Names"] for c in got], [["/openai-tunnel-general"]])

    def test_invalid_or_extended_queries_are_refused(self):
        for q in ["filters=%7B%7D", "filters=%7B%22label%22%3A%5B%22all%22%5D%7D", "all=false", "limit=100", "filters=%7B%22health%22%3A%5B%22unknown%22%5D%7D"]:
            with self.subTest(query=q), self.assertRaises(ValueError):
                s.docker_list(q, fetch=lambda _: CONTAINERS, allowlist=ALLOWED)

    def test_empty_allowlist_fails_closed(self):
        with self.assertRaises(ValueError):
            s.docker_list("", fetch=lambda _: CONTAINERS, allowlist=set())

    def test_versioned_docker_routes_only(self):
        self.assertIsNotNone(s.DOCKER_LIST.fullmatch("/containers/json"))
        self.assertIsNotNone(s.DOCKER_LIST.fullmatch("/v1.43/containers/json"))
        for url in ["/containers/abcdef/json", "/containers/abcdef/stats", "/containers/json/other", "/images/json"]:
            self.assertIsNone(s.DOCKER_LIST.fullmatch(url))


if __name__ == "__main__":
    unittest.main()
