from unittest.mock import MagicMock, patch

from griffin.etsy.auth import EtsyAuthError
from griffin.etsy.client import EtsyClient, EtsyError
from tests.etsy_test_support import EtsyTestCase


def _resp(status_code=200, json_data=None, content=b"{}"):
    resp = MagicMock(status_code=status_code, content=content, ok=200 <= status_code < 300)
    resp.json.return_value = json_data if json_data is not None else {}
    return resp


@patch("griffin.etsy.client.get_access_token", return_value="access-token")
@patch("griffin.etsy.client.ETSY_API_KEY", "test-keystring")
@patch("griffin.etsy.client.ETSY_SHOP_ID", "12345")
class EtsyClientTests(EtsyTestCase):
    def test_list_active_listings_sends_authenticated_get(self, _get_token):
        client = EtsyClient()
        with patch(
            "griffin.etsy.client.requests.request",
            return_value=_resp(json_data={"results": [{"listing_id": 1, "title": "Mug"}]}),
        ) as request:
            listings = client.list_active_listings(limit=10)

        self.assertEqual(listings, [{"listing_id": 1, "title": "Mug"}])
        args, kwargs = request.call_args
        self.assertEqual(args[0], "GET")
        self.assertIn("/shops/12345/listings/active", args[1])
        self.assertEqual(kwargs["headers"]["x-api-key"], "test-keystring")
        self.assertEqual(kwargs["headers"]["Authorization"], "Bearer access-token")

    def test_create_and_activate_listing(self, _get_token):
        client = EtsyClient()
        create_resp = _resp(json_data={"listing_id": 999})
        activate_resp = _resp(json_data={"listing_id": 999, "state": "active"})
        with patch(
            "griffin.etsy.client.requests.request", side_effect=[create_resp, activate_resp]
        ) as request:
            created = client.create_draft_listing(
                title="Mug",
                description="A mug",
                price=12.5,
                quantity=3,
                who_made="i_did",
                when_made="made_to_order",
                taxonomy_id=1,
            )
            client.activate_listing(created["listing_id"])

        self.assertEqual(created["listing_id"], 999)
        first_call, second_call = request.call_args_list
        self.assertEqual(first_call.args[0], "POST")
        self.assertEqual(first_call.kwargs["json"]["state"], "draft")
        self.assertEqual(second_call.args[0], "PATCH")
        self.assertEqual(second_call.kwargs["json"], {"state": "active"})

    def test_missing_shop_id_raises_before_any_request(self, _get_token):
        client = EtsyClient()
        with patch("griffin.etsy.client.ETSY_SHOP_ID", None):
            with patch("griffin.etsy.client.requests.request") as request:
                with self.assertRaises(EtsyError):
                    client.list_active_listings()
        request.assert_not_called()

    def test_401_raises_etsy_error(self, _get_token):
        client = EtsyClient()
        with patch("griffin.etsy.client.requests.request", return_value=_resp(status_code=401)):
            with self.assertRaises(EtsyError):
                client.list_active_listings()

    def test_auth_error_is_wrapped_as_etsy_error(self, get_token):
        get_token.side_effect = EtsyAuthError("no shop connected")
        client = EtsyClient()
        with self.assertRaises(EtsyError):
            client.list_active_listings()

    def test_mark_receipt_shipped_posts_tracking(self, _get_token):
        client = EtsyClient()
        with patch(
            "griffin.etsy.client.requests.request", return_value=_resp(json_data={"receipt_id": 55})
        ) as request:
            client.mark_receipt_shipped(55, "1Z999", "ups")

        args, kwargs = request.call_args
        self.assertEqual(args[0], "POST")
        self.assertIn("/receipts/55/tracking", args[1])
        self.assertEqual(kwargs["json"], {"tracking_code": "1Z999", "carrier_name": "ups"})
