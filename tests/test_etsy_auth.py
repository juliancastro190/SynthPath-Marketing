import time
from unittest.mock import MagicMock, patch

from griffin.etsy import auth
from tests.etsy_test_support import EtsyTestCase


class GetAccessTokenTests(EtsyTestCase):
    def test_not_connected_raises(self):
        with self.assertRaises(auth.EtsyAuthError):
            auth.get_access_token()

    def test_fresh_token_is_returned_without_refreshing(self):
        auth.save_token("fresh-token", "refresh-token", expires_in=3600)
        with patch("griffin.etsy.auth.requests.post") as post:
            token = auth.get_access_token()
        post.assert_not_called()
        self.assertEqual(token, "fresh-token")

    @patch("griffin.etsy.auth.ETSY_API_KEY", "test-keystring")
    def test_expired_token_is_refreshed(self):
        auth.save_token("stale-token", "refresh-token", expires_in=-10)
        resp = MagicMock(status_code=200)
        resp.json.return_value = {
            "access_token": "new-token",
            "refresh_token": "new-refresh-token",
            "expires_in": 3600,
        }
        with patch("griffin.etsy.auth.requests.post", return_value=resp) as post:
            token = auth.get_access_token()

        post.assert_called_once()
        self.assertEqual(post.call_args.kwargs["data"]["grant_type"], "refresh_token")
        self.assertEqual(post.call_args.kwargs["data"]["refresh_token"], "refresh-token")
        self.assertEqual(token, "new-token")

        stored = auth._load()
        self.assertEqual(stored["refresh_token"], "new-refresh-token")
        self.assertGreater(stored["expires_at"], time.time())

    @patch("griffin.etsy.auth.ETSY_API_KEY", "test-keystring")
    def test_refresh_failure_raises_auth_error(self):
        auth.save_token("stale-token", "refresh-token", expires_in=-10)
        resp = MagicMock(status_code=400)
        with patch("griffin.etsy.auth.requests.post", return_value=resp):
            with self.assertRaises(auth.EtsyAuthError):
                auth.get_access_token()

    @patch("griffin.etsy.auth.ETSY_API_KEY", None)
    def test_refresh_without_api_key_raises_before_any_request(self):
        auth.save_token("stale-token", "refresh-token", expires_in=-10)
        with patch("griffin.etsy.auth.requests.post") as post:
            with self.assertRaises(auth.EtsyAuthError):
                auth.get_access_token()
        post.assert_not_called()
