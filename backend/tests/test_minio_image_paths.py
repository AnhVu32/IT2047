import unittest

from src.services.minio.minio_client import MinioClient


class MinioImagePathTests(unittest.TestCase):
    def setUp(self):
        self.client = MinioClient(
            {
                "minio_end_point": "minio:9000",
                "minio_access_key_id": "test",
                "minio_secret_access_key": "test",
                "minio_bucket_name": "cs2307",
                "minio_secure": False,
            }
        )

    def test_extracts_object_key_from_database_url(self):
        value = "http://example:9000/cs2307/images/can-ho/45225431/photo.jpg"
        self.assertEqual(
            self.client.normalize_object_key(value),
            "images/can-ho/45225431/photo.jpg",
        )

    def test_accepts_object_key(self):
        self.assertEqual(
            self.client.normalize_object_key("images/nha-rieng/123/photo.webp"),
            "images/nha-rieng/123/photo.webp",
        )

    def test_rejects_non_property_and_traversal_paths(self):
        invalid_paths = (
            "avatars/user.jpg",
            "images/../secret",
            "",
            "images//photo.jpg",
        )
        for value in invalid_paths:
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    self.client.normalize_object_key(value)


if __name__ == "__main__":
    unittest.main()
