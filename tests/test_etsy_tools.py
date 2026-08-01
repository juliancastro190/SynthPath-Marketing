from unittest.mock import MagicMock, patch

from griffin.tools import etsy
from griffin.tools.registry import ToolError
from tests.etsy_test_support import EtsyTestCase


class EtsyToolsTests(EtsyTestCase):
    def setUp(self):
        super().setUp()
        etsy._client = None  # never let a mock from one test leak into the next
        self.addCleanup(setattr, etsy, "_client", None)
        patcher = patch("griffin.tools.etsy.EtsyClient")
        self.mock_client_cls = patcher.start()
        self.addCleanup(patcher.stop)
        self.mock_client = self.mock_client_cls.return_value

    # ---- drafts stay local ----------------------------------------------

    def test_draft_listing_never_calls_etsy(self):
        result = etsy.etsy_draft_listing(
            {"title": "Mug", "description": "A mug", "price": 12.5, "quantity": 3}
        )
        self.assertIn("Listing draft saved", result)
        self.assertIn("nothing has been published", result)
        self.mock_client.create_draft_listing.assert_not_called()

        drafts = etsy._load_listing_drafts()
        self.assertEqual(len(drafts), 1)
        self.assertIsNone(drafts[0]["published_listing_id"])

    def test_draft_listing_requires_fields(self):
        with self.assertRaises(ToolError):
            etsy.etsy_draft_listing({"title": "Mug"})

    def test_draft_buyer_reply_never_sends(self):
        result = etsy.etsy_draft_buyer_reply({"receipt_id": 42, "body": "Thanks for your order!"})
        self.assertIn("Reply draft saved", result)
        self.assertIn("paste this into", result)

    # ---- publish is the consequential path -------------------------------

    def test_publish_listing_creates_and_activates(self):
        etsy.etsy_draft_listing(
            {
                "title": "Mug",
                "description": "A mug",
                "price": 12.5,
                "quantity": 3,
                "taxonomy_id": 1234,
            }
        )
        draft_id = etsy._load_listing_drafts()[0]["id"]
        self.mock_client.create_draft_listing.return_value = {"listing_id": 999}

        result = etsy.etsy_publish_listing({"draft_id": draft_id})

        self.assertIn("999", result)
        self.mock_client.create_draft_listing.assert_called_once()
        self.mock_client.activate_listing.assert_called_once_with(999)
        self.assertEqual(etsy._load_listing_drafts()[0]["published_listing_id"], 999)

    def test_publish_listing_without_taxonomy_id_refuses(self):
        etsy.etsy_draft_listing({"title": "Mug", "description": "A mug", "price": 12.5, "quantity": 3})
        draft_id = etsy._load_listing_drafts()[0]["id"]
        with self.assertRaises(ToolError):
            etsy.etsy_publish_listing({"draft_id": draft_id})
        self.mock_client.create_draft_listing.assert_not_called()

    def test_publish_listing_twice_refuses(self):
        etsy.etsy_draft_listing(
            {"title": "Mug", "description": "A mug", "price": 12.5, "quantity": 3, "taxonomy_id": 1}
        )
        draft_id = etsy._load_listing_drafts()[0]["id"]
        self.mock_client.create_draft_listing.return_value = {"listing_id": 999}
        etsy.etsy_publish_listing({"draft_id": draft_id})

        with self.assertRaises(ToolError):
            etsy.etsy_publish_listing({"draft_id": draft_id})
        self.mock_client.create_draft_listing.assert_called_once()

    def test_publish_unknown_draft_refuses(self):
        with self.assertRaises(ToolError):
            etsy.etsy_publish_listing({"draft_id": "nonexistent"})

    def test_describe_publish_listing_names_price_and_fee(self):
        etsy.etsy_draft_listing(
            {"title": "Mug", "description": "A mug", "price": 12.5, "quantity": 3, "taxonomy_id": 1}
        )
        draft_id = etsy._load_listing_drafts()[0]["id"]
        description = etsy.describe_publish_listing({"draft_id": draft_id})
        self.assertIn("Mug", description)
        self.assertIn("12.50", description)
        self.assertIn("listing fee", description)

    # ---- other consequential tools ----------------------------------------

    def test_mark_order_shipped_calls_client_and_requires_fields(self):
        with self.assertRaises(ToolError):
            etsy.etsy_mark_order_shipped({"receipt_id": 1})

        result = etsy.etsy_mark_order_shipped(
            {"receipt_id": 1, "tracking_code": "1Z999", "carrier_name": "ups"}
        )
        self.mock_client.mark_receipt_shipped.assert_called_once_with(1, "1Z999", "ups")
        self.assertIn("marked shipped", result)

    def test_describe_mark_order_shipped_warns_it_emails_buyer(self):
        description = etsy.describe_mark_order_shipped(
            {"receipt_id": 1, "tracking_code": "1Z999", "carrier_name": "ups"}
        )
        self.assertIn("emails the buyer", description)

    def test_update_listing_price_and_quantity(self):
        etsy.etsy_update_listing_price({"listing_id": 7, "price": 19.99})
        self.mock_client.update_listing.assert_called_with(7, price=19.99)

        etsy.etsy_update_listing_quantity({"listing_id": 7, "quantity": 4})
        self.mock_client.update_listing.assert_called_with(7, quantity=4)

    def test_deactivate_listing(self):
        etsy.etsy_deactivate_listing({"listing_id": 7})
        self.mock_client.deactivate_listing.assert_called_once_with(7)

    # ---- read-only tools surface Etsy errors as ToolError ------------------

    def test_list_active_listings_wraps_etsy_error(self):
        from griffin.etsy.client import EtsyError

        self.mock_client.list_active_listings.side_effect = EtsyError("no shop connected")
        with self.assertRaises(ToolError):
            etsy.etsy_list_active_listings({})
