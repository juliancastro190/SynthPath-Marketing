"""The Etsy seam: the only place that talks to Etsy's Open API v3 directly.

Mirrors griffin/brain/provider.py's shape on purpose — everything else
(griffin/tools/etsy.py, the heartbeat checks) calls methods on EtsyClient
and never touches `requests` or Etsy's URLs itself. That's what lets retry
logic, rate-limit handling, or a v4 migration happen in one place later.

Etsy's public API v3 has no endpoint for a third-party app to send a new
message to a buyer's inbox — messaging isn't part of the public surface.
So there's no send_buyer_message here; griffin/tools/etsy.py drafts a
reply locally instead, the same way draft_message never sends email.
"""

import requests

from griffin.config import ETSY_API_KEY, ETSY_SHOP_ID
from griffin.etsy.auth import EtsyAuthError, get_access_token

BASE_URL = "https://openapi.etsy.com/v3/application"


class EtsyError(Exception):
    """Raised on any Etsy API failure. The message is safe to show the user."""


def _require_shop_id():
    if not ETSY_SHOP_ID:
        raise EtsyError("No ETSY_SHOP_ID is set. Add it to .env (see .env.example).")
    return ETSY_SHOP_ID


class EtsyClient:
    def _headers(self):
        try:
            access_token = get_access_token()
        except EtsyAuthError as exc:
            raise EtsyError(str(exc))
        return {"x-api-key": ETSY_API_KEY, "Authorization": f"Bearer {access_token}"}

    def _request(self, method, path, **kwargs):
        try:
            resp = requests.request(method, f"{BASE_URL}{path}", headers=self._headers(), timeout=15, **kwargs)
        except requests.RequestException as exc:
            raise EtsyError(f"Couldn't reach Etsy: {exc}")

        if resp.status_code == 401:
            raise EtsyError("Etsy rejected the connection — try reconnecting with etsy_connect.py.")
        if resp.status_code == 404:
            raise EtsyError("Etsy couldn't find that — double-check the id.")
        if resp.status_code == 429:
            raise EtsyError("Etsy is rate-limiting us — wait a moment and try again.")
        if not resp.ok:
            detail = ""
            try:
                detail = resp.json().get("error", "")
            except ValueError:
                pass
            raise EtsyError(f"Etsy returned an error ({resp.status_code}){f': {detail}' if detail else ''}.")

        return resp.json() if resp.content else {}

    # ---- listings (read) ------------------------------------------------

    def list_active_listings(self, limit=25):
        shop_id = _require_shop_id()
        data = self._request(
            "GET", f"/shops/{shop_id}/listings/active", params={"limit": limit, "sort_on": "created"}
        )
        return data.get("results", [])

    def get_listing(self, listing_id):
        return self._request("GET", f"/listings/{listing_id}")

    # ---- listings (write — all consequential) ----------------------------

    def create_draft_listing(self, *, title, description, price, quantity, who_made, when_made, taxonomy_id, tags=None, materials=None):
        shop_id = _require_shop_id()
        payload = {
            "title": title,
            "description": description,
            "price": price,
            "quantity": quantity,
            "who_made": who_made,
            "when_made": when_made,
            "taxonomy_id": taxonomy_id,
            "state": "draft",
        }
        if tags:
            payload["tags"] = tags
        if materials:
            payload["materials"] = materials
        return self._request("POST", f"/shops/{shop_id}/listings", json=payload)

    def update_listing(self, listing_id, **fields):
        shop_id = _require_shop_id()
        return self._request("PATCH", f"/shops/{shop_id}/listings/{listing_id}", json=fields)

    def activate_listing(self, listing_id):
        return self.update_listing(listing_id, state="active")

    def deactivate_listing(self, listing_id):
        return self.update_listing(listing_id, state="inactive")

    # ---- orders / receipts -----------------------------------------------

    def list_receipts(self, was_shipped=None, limit=25):
        shop_id = _require_shop_id()
        params = {"limit": limit}
        if was_shipped is not None:
            params["was_shipped"] = str(was_shipped).lower()
        data = self._request("GET", f"/shops/{shop_id}/receipts", params=params)
        return data.get("results", [])

    def get_receipt(self, receipt_id):
        shop_id = _require_shop_id()
        return self._request("GET", f"/shops/{shop_id}/receipts/{receipt_id}")

    def mark_receipt_shipped(self, receipt_id, tracking_code, carrier_name):
        shop_id = _require_shop_id()
        return self._request(
            "POST",
            f"/shops/{shop_id}/receipts/{receipt_id}/tracking",
            json={"tracking_code": tracking_code, "carrier_name": carrier_name},
        )
