import unittest

from fastapi.testclient import TestClient

from src.exceptions import AppError
from src.main import app as main_app
from src.resources.exceptions import UnsupportedResourceUrlError


class AppExceptionTests(unittest.TestCase):
    def test_unsupported_resource_url_error_inherits_app_error(self) -> None:
        error = UnsupportedResourceUrlError(platform="YouTube", url="https://youtube.com/watch?v=1")

        self.assertIsInstance(error, AppError)
        self.assertEqual(error.status_code, 422)
        self.assertEqual(error.detail[0]["loc"], ["query", "resource_url"])

    def test_app_error_handler_translates_to_422_response(self) -> None:
        async def boom() -> None:
            raise UnsupportedResourceUrlError(platform="Instagram", url="https://instagram.com/reel/1")

        main_app.add_api_route("/boom", boom)
        response = TestClient(main_app).get("/boom")

        self.assertEqual(response.status_code, 422)
        self.assertEqual(
            response.json(),
            {
                "detail": [
                    {
                        "type": "unsupported_resource_url",
                        "loc": ["query", "resource_url"],
                        "msg": "Instagram URLs are not supported yet",
                        "input": "https://instagram.com/reel/1",
                    }
                ]
            },
        )
