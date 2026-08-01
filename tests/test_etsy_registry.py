from griffin.project_config import load_config
from griffin.tools.registry import build_default_registry
from tests.etsy_test_support import EtsyTestCase

CONSEQUENTIAL_ETSY_TOOLS = [
    "etsy_publish_listing",
    "etsy_update_listing_price",
    "etsy_update_listing_quantity",
    "etsy_deactivate_listing",
    "etsy_mark_order_shipped",
]

READ_AND_DRAFT_ETSY_TOOLS = [
    "etsy_list_active_listings",
    "etsy_get_listing",
    "etsy_list_orders",
    "etsy_get_order",
    "etsy_draft_listing",
    "etsy_list_listing_drafts",
    "etsy_draft_buyer_reply",
    "etsy_list_buyer_reply_drafts",
]


class EtsyRegistryTests(EtsyTestCase):
    def test_repo_config_gates_every_consequential_etsy_tool(self):
        # The actual config.yaml shipped in the repo, not a fixture — this
        # is what would run for a real user, so it's what should be tested.
        config = load_config()
        registry = build_default_registry(config)
        for name in CONSEQUENTIAL_ETSY_TOOLS:
            self.assertTrue(registry.requires_confirmation(name), f"{name} should require confirmation")
        for name in READ_AND_DRAFT_ETSY_TOOLS:
            self.assertFalse(registry.requires_confirmation(name), f"{name} should not require confirmation")

    def test_flag_does_not_leak_across_builds_with_different_config(self):
        registry = build_default_registry({"tools": {"requires_confirmation": []}})
        self.assertFalse(registry.requires_confirmation("etsy_publish_listing"))

        registry = build_default_registry({"tools": {"requires_confirmation": ["etsy_publish_listing"]}})
        self.assertTrue(registry.requires_confirmation("etsy_publish_listing"))
