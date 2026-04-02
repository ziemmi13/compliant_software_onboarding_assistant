import unittest

from api.services.analysis_service import validate_input_url


class ValidateInputUrlTests(unittest.TestCase):
    def test_accepts_public_https_url(self) -> None:
        result = validate_input_url("https://example.com/terms")
        self.assertEqual(result, "https://example.com/terms")

    def test_rejects_localhost(self) -> None:
        with self.assertRaises(ValueError):
            validate_input_url("http://localhost:8000")

    def test_rejects_private_ipv4(self) -> None:
        with self.assertRaises(ValueError):
            validate_input_url("http://192.168.1.10/legal")

    def test_rejects_loopback_ipv4(self) -> None:
        with self.assertRaises(ValueError):
            validate_input_url("http://127.0.0.1")

    def test_rejects_non_http_schemes(self) -> None:
        with self.assertRaises(ValueError):
            validate_input_url("ftp://example.com")


if __name__ == "__main__":
    unittest.main()
