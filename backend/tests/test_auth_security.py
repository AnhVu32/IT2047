import os
import unittest
from unittest.mock import patch

from src.services.auth.security import (
    create_access_token,
    decode_token,
    hash_password,
    verify_password,
)


class AuthSecurityTests(unittest.TestCase):
    def test_password_hash_roundtrip(self):
        digest = hash_password("secret123")
        self.assertNotEqual(digest, "secret123")
        self.assertTrue(verify_password("secret123", digest))
        self.assertFalse(verify_password("wrong", digest))

    def test_token_roundtrip_carries_identity(self):
        with patch.dict(os.environ, {"ACCESS_TOKEN_SECRET_KEY": "testsecret", "ALGORITHM": "HS256"}):
            token = create_access_token(42, "dat")
            payload = decode_token(token)
        self.assertIsNotNone(payload)
        self.assertEqual(payload["sub"], "42")
        self.assertEqual(payload["username"], "dat")

    def test_invalid_token_returns_none(self):
        self.assertIsNone(decode_token("not-a-jwt"))

    def test_token_rejected_under_different_secret(self):
        with patch.dict(os.environ, {"ACCESS_TOKEN_SECRET_KEY": "secret-a", "ALGORITHM": "HS256"}):
            token = create_access_token(1, "u")
        with patch.dict(os.environ, {"ACCESS_TOKEN_SECRET_KEY": "secret-b", "ALGORITHM": "HS256"}):
            self.assertIsNone(decode_token(token))


if __name__ == "__main__":
    unittest.main()
