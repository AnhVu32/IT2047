import os
import unittest
from unittest.mock import Mock, patch

try:
    import numpy as np
except ImportError:  # Parser-only environments may not install numeric dependencies.
    np = None


@unittest.skipUnless(np is not None, "numpy is not installed in this test environment")
class EmbeddingApiTests(unittest.TestCase):
    @patch("src.search.embedding.requests.post")
    def test_lmstudio_calls_embeddings_api_and_normalizes_vectors(self, post):
        from src.search.embedding import E5EmbeddingModel

        first = [0.0] * 1024
        first[0] = 3.0
        first[1] = 4.0
        second = [0.0] * 1024
        second[2] = 2.0
        response = Mock()
        response.json.return_value = {
            "data": [
                {"index": 1, "embedding": second},
                {"index": 0, "embedding": first},
            ]
        }
        post.return_value = response
        with patch.dict(
            os.environ,
            {
                "SEARCH_EMBEDDING_PROVIDER": "lmstudio",
                "SEARCH_EMBEDDING_MODEL": "test-e5",
                "SEARCH_EMBEDDING_BASE_URL": "http://localhost:1234/v1",
                "SEARCH_EMBEDDING_API_KEY": "secret",
            },
            clear=True,
        ):
            model = E5EmbeddingModel()
            vectors = model.encode(["căn hộ", "nhà phố"], kind="passage")

        self.assertEqual(vectors.shape, (2, 1024))
        np.testing.assert_allclose(np.linalg.norm(vectors, axis=1), [1.0, 1.0])
        post.assert_called_once_with(
            "http://localhost:1234/v1/embeddings",
            headers={"Content-Type": "application/json", "Authorization": "Bearer secret"},
            json={"model": "test-e5", "input": ["passage: căn hộ", "passage: nhà phố"]},
            timeout=60.0,
        )

    @patch("src.search.embedding.requests.post")
    def test_lmstudio_rejects_vectors_with_wrong_dimension(self, post):
        from src.search.embedding import E5EmbeddingModel

        response = Mock()
        response.json.return_value = {"data": [{"index": 0, "embedding": [1.0, 2.0]}]}
        post.return_value = response
        with patch.dict(os.environ, {"SEARCH_EMBEDDING_PROVIDER": "lmstudio"}, clear=True):
            model = E5EmbeddingModel()
            self.assertIsNone(model.encode_query("test"))

    @patch("src.search.embedding.requests.post")
    def test_lmstudio_can_request_schema_dimension(self, post):
        from src.search.embedding import E5EmbeddingModel

        response = Mock()
        response.json.return_value = {"data": [{"index": 0, "embedding": [1.0] * 1024}]}
        post.return_value = response
        with patch.dict(
            os.environ,
            {
                "SEARCH_EMBEDDING_PROVIDER": "lmstudio",
                "SEARCH_EMBEDDING_REQUEST_DIMENSIONS": "1024",
            },
            clear=True,
        ):
            model = E5EmbeddingModel()
            vectors = model.encode_query("test")

        self.assertEqual(vectors.shape, (1024,))
        self.assertEqual(post.call_args.kwargs["json"]["dimensions"], 1024)


if __name__ == "__main__":
    unittest.main()
