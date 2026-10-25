import importlib.util
from pathlib import Path
import unittest
from unittest.mock import patch

SOURCE = Path(__file__).resolve().parents[1] / "server.py"
spec = importlib.util.spec_from_file_location("chromium_homepage_status", SOURCE)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

class TelemetryTests(unittest.TestCase):
    def test_count_pages_without_disclosing_metadata(self):
        pages = [
            {"type": "page", "title": "secret", "url": "https://private.invalid", "id": "private"},
            {"type": "browser_ui"},
            {"type": "page"},
            {"type": "service_worker"},
        ]
        with patch.object(module, "MCP_URL", "http://localhost:8933/mcp"), patch.object(module, "get_json", side_effect=[{"Browser": "Chromium"}, pages]), patch.object(module, "mcp_responding", return_value=True), patch.object(module, "process_running", return_value=True):
            result = module.summary()
        self.assertEqual(result, {"browser": "Ready", "open_tabs": 2, "mcp": "Healthy", "process": "Running"})
        for private in ("private", "url", "title", "id"):
            self.assertNotIn(private, str(result).lower())

    def test_cdp_failure_is_unavailable_not_zero_tabs(self):
        with patch.object(module, "MCP_URL", "http://localhost:8933/mcp"), patch.object(module, "get_json", side_effect=TimeoutError()), patch.object(module, "process_running", return_value=False):
            result = module.summary()
        self.assertEqual(result, {"browser": "Offline", "open_tabs": None, "mcp": "Unavailable", "process": "Stopped"})

    def test_unknown_process_visibility_remains_unknown(self):
        with patch.object(module, "MCP_URL", "http://localhost:8933/mcp"), patch.object(module, "get_json", side_effect=[{}, []]), patch.object(module, "mcp_responding", return_value=False), patch.object(module, "process_running", return_value=None):
            result = module.summary()
        self.assertEqual(result["open_tabs"], 0)
        self.assertEqual(result["process"], "Unknown")

    def test_unreachable_mcp_is_unavailable(self):
        with patch.object(module.urllib.request, "urlopen", side_effect=ConnectionRefusedError()):
            self.assertFalse(module.mcp_responding())

if __name__ == "__main__":
    unittest.main()
