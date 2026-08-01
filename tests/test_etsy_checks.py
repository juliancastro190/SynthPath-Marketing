from datetime import datetime, timezone
from unittest.mock import patch

from griffin.etsy.client import EtsyError
from griffin.heartbeat import checks
from tests.etsy_test_support import EtsyTestCase

NOW = datetime(2026, 8, 1, 12, 0, tzinfo=timezone.utc)


class EtsyUnshippedOrdersTests(EtsyTestCase):
    def test_no_shop_connected_is_silent(self):
        with patch("griffin.heartbeat.checks.EtsyClient") as client_cls:
            client_cls.return_value.list_receipts.side_effect = EtsyError("not connected")
            self.assertEqual(checks.etsy_unshipped_orders({}, now=NOW), [])

    def test_recent_unshipped_order_does_not_alert(self):
        recent = int((NOW.timestamp()) - 60 * 60)  # 1h old
        with patch("griffin.heartbeat.checks.EtsyClient") as client_cls:
            client_cls.return_value.list_receipts.return_value = [{"receipt_id": 1, "created_timestamp": recent}]
            self.assertEqual(checks.etsy_unshipped_orders({"stale_after_hours": 48}, now=NOW), [])

    def test_stale_unshipped_order_alerts(self):
        stale = int(NOW.timestamp()) - 60 * 60 * 72  # 72h old
        with patch("griffin.heartbeat.checks.EtsyClient") as client_cls:
            client_cls.return_value.list_receipts.return_value = [{"receipt_id": 1, "created_timestamp": stale}]
            results = checks.etsy_unshipped_orders({"stale_after_hours": 48, "alert_threshold": 1}, now=NOW)
        self.assertEqual(len(results), 1)
        message, severity = results[0]
        self.assertEqual(severity, "alert")
        self.assertIn("1 Etsy order", message)

    def test_below_alert_threshold_is_info_not_alert(self):
        stale = int(NOW.timestamp()) - 60 * 60 * 72
        with patch("griffin.heartbeat.checks.EtsyClient") as client_cls:
            client_cls.return_value.list_receipts.return_value = [{"receipt_id": 1, "created_timestamp": stale}]
            results = checks.etsy_unshipped_orders({"stale_after_hours": 48, "alert_threshold": 5}, now=NOW)
        self.assertEqual(results[0][1], "info")


class EtsyLowInventoryTests(EtsyTestCase):
    def test_no_shop_connected_is_silent(self):
        with patch("griffin.heartbeat.checks.EtsyClient") as client_cls:
            client_cls.return_value.list_active_listings.side_effect = EtsyError("not connected")
            self.assertEqual(checks.etsy_low_inventory({}), [])

    def test_well_stocked_listings_do_not_alert(self):
        with patch("griffin.heartbeat.checks.EtsyClient") as client_cls:
            client_cls.return_value.list_active_listings.return_value = [{"title": "Mug", "quantity": 10}]
            self.assertEqual(checks.etsy_low_inventory({"low_quantity_threshold": 2}), [])

    def test_low_stock_listing_alerts_by_name(self):
        with patch("griffin.heartbeat.checks.EtsyClient") as client_cls:
            client_cls.return_value.list_active_listings.return_value = [{"title": "Mug", "quantity": 1}]
            results = checks.etsy_low_inventory({"low_quantity_threshold": 2})
        self.assertEqual(len(results), 1)
        message, severity = results[0]
        self.assertEqual(severity, "alert")
        self.assertIn("Mug", message)
