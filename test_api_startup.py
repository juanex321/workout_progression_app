"""Startup regression checks: never connect to or mutate a real database."""
import os
import ssl
import unittest
from unittest.mock import patch

from api import index
from db import _postgres_connection_options


class StartupTests(unittest.TestCase):
    def test_pg8000_neon_url_uses_verified_tls(self):
        url, args = _postgres_connection_options(
            "postgresql+pg8000://test:test@example.invalid/db?sslmode=require&channel_binding=require"
        )
        self.assertNotIn("sslmode", url.query)
        self.assertNotIn("channel_binding", url.query)
        self.assertTrue(args["ssl_context"].check_hostname)
        self.assertEqual(args["ssl_context"].verify_mode, ssl.CERT_REQUIRED)

    def test_psycopg2_options_unchanged(self):
        url, args = _postgres_connection_options(
            "postgresql://test:test@example.invalid/db?sslmode=require"
        )
        self.assertEqual(url.query["sslmode"], "require")
        self.assertEqual(args, {})

    def test_existing_deployments_still_initialize(self):
        with patch.dict(os.environ, {"SKIP_DB_INIT": ""}), \
             patch.object(index, "init_db") as init, \
             patch.object(index, "seed_default_data") as seed:
            index.startup()
            init.assert_called_once()
            seed.assert_called_once()

    def test_opted_in_startup_does_no_schema_or_seed_work(self):
        with patch.dict(os.environ, {"SKIP_DB_INIT": "true"}), \
             patch.object(index, "init_db") as init, \
             patch.object(index, "seed_default_data") as seed:
            index.startup()
            init.assert_not_called()
            seed.assert_not_called()


if __name__ == "__main__":
    unittest.main()
