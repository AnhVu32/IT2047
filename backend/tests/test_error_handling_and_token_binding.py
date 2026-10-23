import os
import unittest
from unittest.mock import AsyncMock, patch

from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials

from src.api.base.http_exception import http_except_custom
from src.services.auth import dependencies
from src.services.auth.security import create_access_token
from src.services.database.postgresql.connector import PostgresConnector
from src.services.llm.llm_model import LLModel

_ENV = {"ACCESS_TOKEN_SECRET_KEY": "testsecret", "ALGORITHM": "HS256"}


class HttpExceptionStatusTests(unittest.IsolatedAsyncioTestCase):
    async def test_status_code_is_preserved(self):
        for code in (401, 403, 404, 409, 500):
            response = await http_except_custom(None, HTTPException(status_code=code, detail="x"))
            self.assertEqual(response.status_code, code)


class TokenBindingTests(unittest.IsolatedAsyncioTestCase):
    async def _resolve(self, token_username: str, db_user: dict):
        with patch.dict(os.environ, _ENV):
            token = create_access_token(1, token_username)
            credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)
            with patch.object(dependencies.repository, "get_by_id", return_value=db_user):
                return await dependencies._user_from_credentials(credentials)

    async def test_matching_username_resolves(self):
        user = {"id": 1, "username": "dat", "is_active": True}
        self.assertEqual(await self._resolve("dat", user), user)

    async def test_reused_id_with_other_username_is_rejected(self):
        user = {"id": 1, "username": "someone-else", "is_active": True}
        self.assertIsNone(await self._resolve("dat", user))


class PostgresConnectorTests(unittest.TestCase):
    def test_special_characters_in_password_and_small_pool(self):
        connector = PostgresConnector(
            config={
                "username_db": "u",
                "password_db": "p@ss/w:rd",
                "host_db": "localhost",
                "port_db": "5432",
                "database": "db",
            }
        )
        connector.start()
        try:
            self.assertEqual(connector.engine.url.password, "p@ss/w:rd")
            self.assertEqual(connector.engine.url.host, "localhost")
            self.assertEqual(connector.engine.pool.size(), 10)
            self.assertNotIn("p@ss", connector.connection_string)
        finally:
            connector.stop()


class LlmDefaultsTests(unittest.IsolatedAsyncioTestCase):
    async def test_defaults_are_bounded_and_overridable(self):
        llm = LLModel(provider="openai-compatible", base_url="http://x", api_key="k")
        llm._ask_openai_compatible = AsyncMock(return_value=(True, "ok", None))

        await llm.ask_llm("s", "u")
        args = llm._ask_openai_compatible.call_args.args
        self.assertEqual((args[3], args[4]), (2, 45))  # retries, timeout_seconds

        with patch.dict(os.environ, {"LLM_MAX_RETRIES": "1", "LLM_REQUEST_TIMEOUT_SECONDS": "10"}):
            await llm.ask_llm("s", "u")
        args = llm._ask_openai_compatible.call_args.args
        self.assertEqual((args[3], args[4]), (1, 10))


if __name__ == "__main__":
    unittest.main()
