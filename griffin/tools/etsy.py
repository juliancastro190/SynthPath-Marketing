"""Etsy — capability #4: "sell for me on Etsy."

Split the same way drafting (Tier 2) and sending (never built) were always
meant to split: anything that only writes local state — browsing what's on
the shop, drafting a new listing, drafting a reply to a buyer — runs
freely. Anything that touches the live shop — publishing a listing,
changing a price or quantity, taking a listing down, marking an order
shipped — is flagged in config.yaml's tools.requires_confirmation and goes
through Tier 6's confirmation gate, the same as `forget`. Those five are
squarely on AGENT.md's never-without-asking list: publishing spends
Etsy's listing fee and makes something public, price/quantity/visibility
changes are settings changes, and marking an order shipped emails the
buyer and can't be quietly undone.

There's no send_buyer_message tool — Etsy's public API has no endpoint for
a third-party app to originate a new buyer message, so a reply is drafted
locally (like draft_message) for the seller to paste into Etsy's own
Messages themselves.
"""

import uuid
from datetime import datetime, timezone

from griffin import storage
from griffin.etsy.client import EtsyClient, EtsyError
from griffin.tools.registry import Tool, ToolError

LISTING_DRAFTS_FILENAME = "etsy_listing_drafts.json"
REPLY_DRAFTS_FILENAME = "etsy_reply_drafts.json"

_client = None


def _get_client():
    global _client
    if _client is None:
        _client = EtsyClient()
    return _client


def _load_listing_drafts():
    return storage.load(LISTING_DRAFTS_FILENAME, [])


def _save_listing_drafts(drafts):
    storage.save(LISTING_DRAFTS_FILENAME, drafts)


def _load_reply_drafts():
    return storage.load(REPLY_DRAFTS_FILENAME, [])


def _save_reply_drafts(drafts):
    storage.save(REPLY_DRAFTS_FILENAME, drafts)


def _call_etsy(fn, *args, **kwargs):
    try:
        return fn(*args, **kwargs)
    except EtsyError as exc:
        raise ToolError(str(exc))


# ---- read-only ------------------------------------------------------------


def etsy_list_active_listings(tool_input):
    limit = int(tool_input.get("limit", 25))
    listings = _call_etsy(_get_client().list_active_listings, limit=limit)
    if not listings:
        return "No active listings on the shop."
    lines = []
    for listing in listings:
        price = listing.get("price", {})
        amount = price.get("amount", 0) / price.get("divisor", 100) if price else 0
        lines.append(
            f'- [{listing["listing_id"]}] {listing["title"]} — '
            f'${amount:.2f}, qty {listing.get("quantity", "?")}'
        )
    return "\n".join(lines)


def etsy_get_listing(tool_input):
    listing_id = tool_input.get("listing_id")
    if not listing_id:
        raise ToolError("A listing_id is required.")
    listing = _call_etsy(_get_client().get_listing, listing_id)
    price = listing.get("price", {})
    amount = price.get("amount", 0) / price.get("divisor", 100) if price else 0
    return (
        f'{listing["title"]} [id={listing["listing_id"]}] — state: {listing.get("state")}\n'
        f'Price: ${amount:.2f}  Quantity: {listing.get("quantity", "?")}\n\n'
        f'{listing.get("description", "")}'
    )


def etsy_list_orders(tool_input):
    was_shipped = tool_input.get("unshipped_only", False)
    receipts = _call_etsy(
        _get_client().list_receipts, was_shipped=(False if was_shipped else None)
    )
    if not receipts:
        return "No orders match." if was_shipped else "No orders on the shop yet."
    lines = []
    for r in receipts:
        status = "shipped" if r.get("was_shipped") else "not yet shipped"
        lines.append(
            f'- [{r["receipt_id"]}] {r.get("name", "buyer")} — '
            f'${r.get("grandtotal", {}).get("amount", 0) / 100:.2f} ({status})'
        )
    return "\n".join(lines)


def etsy_get_order(tool_input):
    receipt_id = tool_input.get("receipt_id")
    if not receipt_id:
        raise ToolError("A receipt_id is required.")
    r = _call_etsy(_get_client().get_receipt, receipt_id)
    status = "shipped" if r.get("was_shipped") else "not yet shipped"
    message = r.get("message_from_buyer") or "(none)"
    return (
        f'Order [{r["receipt_id"]}] from {r.get("name", "buyer")} — {status}\n'
        f'Total: ${r.get("grandtotal", {}).get("amount", 0) / 100:.2f}\n'
        f'Message from buyer: {message}'
    )


# ---- listing drafts (local only) -------------------------------------------


def etsy_draft_listing(tool_input):
    title = (tool_input.get("title") or "").strip()
    description = (tool_input.get("description") or "").strip()
    price = tool_input.get("price")
    quantity = tool_input.get("quantity")
    if not title or not description or price is None or quantity is None:
        raise ToolError("A listing draft needs title, description, price, and quantity.")

    drafts = _load_listing_drafts()
    draft = {
        "id": uuid.uuid4().hex[:8],
        "title": title,
        "description": description,
        "price": float(price),
        "quantity": int(quantity),
        "who_made": tool_input.get("who_made", "i_did"),
        "when_made": tool_input.get("when_made", "made_to_order"),
        "taxonomy_id": tool_input.get("taxonomy_id"),
        "tags": tool_input.get("tags", []),
        "materials": tool_input.get("materials", []),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "published_listing_id": None,
    }
    drafts.append(draft)
    _save_listing_drafts(drafts)
    return (
        f'Listing draft saved [id={draft["id"]}] — nothing has been published to Etsy.\n'
        f'{title} — ${draft["price"]:.2f}, qty {draft["quantity"]}\n\n{description}'
    )


def etsy_list_listing_drafts(tool_input):
    drafts = _load_listing_drafts()
    if not drafts:
        return "No saved listing drafts."
    lines = []
    for d in drafts:
        status = f'published as Etsy listing {d["published_listing_id"]}' if d["published_listing_id"] else "unpublished"
        lines.append(f'- [{d["id"]}] {d["title"]} — ${d["price"]:.2f}, qty {d["quantity"]} ({status})')
    return "\n".join(lines)


def _find_listing_draft(draft_id):
    for d in _load_listing_drafts():
        if d["id"] == draft_id:
            return d
    return None


# ---- reply drafts (local only) ---------------------------------------------


def etsy_draft_buyer_reply(tool_input):
    body = (tool_input.get("body") or "").strip()
    if not body:
        raise ToolError("A reply draft needs non-empty body text.")
    receipt_id = tool_input.get("receipt_id")

    drafts = _load_reply_drafts()
    draft = {
        "id": uuid.uuid4().hex[:8],
        "receipt_id": receipt_id,
        "body": body,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    drafts.append(draft)
    _save_reply_drafts(drafts)
    return (
        f'Reply draft saved [id={draft["id"]}] for order {receipt_id or "(unspecified)"} — '
        "Etsy's API doesn't let an app send a buyer message directly, so paste this into "
        "the buyer's conversation in Etsy Messages yourself:\n\n" + body
    )


def etsy_list_buyer_reply_drafts(tool_input):
    drafts = _load_reply_drafts()
    if not drafts:
        return "No saved reply drafts."
    return "\n".join(f'- [{d["id"]}] for order {d["receipt_id"] or "(unspecified)"}' for d in drafts)


# ---- consequential (confirmation-gated in config.yaml) ---------------------


def etsy_publish_listing(tool_input):
    draft_id = tool_input.get("draft_id")
    draft = _find_listing_draft(draft_id)
    if draft is None:
        raise ToolError(f"No listing draft found with id '{draft_id}'.")
    if draft["published_listing_id"]:
        raise ToolError(f"Draft [{draft_id}] was already published as Etsy listing {draft['published_listing_id']}.")
    if not draft.get("taxonomy_id"):
        raise ToolError("This draft has no taxonomy_id set — Etsy requires a category before it can publish.")

    created = _call_etsy(
        _get_client().create_draft_listing,
        title=draft["title"],
        description=draft["description"],
        price=draft["price"],
        quantity=draft["quantity"],
        who_made=draft["who_made"],
        when_made=draft["when_made"],
        taxonomy_id=draft["taxonomy_id"],
        tags=draft.get("tags"),
        materials=draft.get("materials"),
    )
    listing_id = created["listing_id"]
    _call_etsy(_get_client().activate_listing, listing_id)

    draft["published_listing_id"] = listing_id
    drafts = [draft if d["id"] == draft["id"] else d for d in _load_listing_drafts()]
    _save_listing_drafts(drafts)
    return f'Published — "{draft["title"]}" is now live on Etsy as listing {listing_id}.'


def describe_publish_listing(tool_input):
    draft = _find_listing_draft(tool_input.get("draft_id"))
    if draft is None:
        return f'publish listing draft [{tool_input.get("draft_id")}] (no such draft currently exists)'
    return (
        f'publish "{draft["title"]}" to Etsy at ${draft["price"]:.2f} — this spends '
        "Etsy's listing fee and makes it publicly visible immediately"
    )


def etsy_update_listing_price(tool_input):
    listing_id = tool_input.get("listing_id")
    price = tool_input.get("price")
    if not listing_id or price is None:
        raise ToolError("A listing_id and price are required.")
    _call_etsy(_get_client().update_listing, listing_id, price=float(price))
    return f'Updated Etsy listing {listing_id} — price is now ${float(price):.2f}.'


def describe_update_listing_price(tool_input):
    return f'change the live price of Etsy listing {tool_input.get("listing_id")} to ${float(tool_input.get("price", 0)):.2f}'


def etsy_update_listing_quantity(tool_input):
    listing_id = tool_input.get("listing_id")
    quantity = tool_input.get("quantity")
    if not listing_id or quantity is None:
        raise ToolError("A listing_id and quantity are required.")
    _call_etsy(_get_client().update_listing, listing_id, quantity=int(quantity))
    return f'Updated Etsy listing {listing_id} — quantity is now {int(quantity)}.'


def describe_update_listing_quantity(tool_input):
    return f'change the live quantity of Etsy listing {tool_input.get("listing_id")} to {tool_input.get("quantity")}'


def etsy_deactivate_listing(tool_input):
    listing_id = tool_input.get("listing_id")
    if not listing_id:
        raise ToolError("A listing_id is required.")
    _call_etsy(_get_client().deactivate_listing, listing_id)
    return f'Etsy listing {listing_id} is now inactive — no longer visible to buyers.'


def describe_deactivate_listing(tool_input):
    return f'take Etsy listing {tool_input.get("listing_id")} down (no longer visible to buyers)'


def etsy_mark_order_shipped(tool_input):
    receipt_id = tool_input.get("receipt_id")
    tracking_code = tool_input.get("tracking_code")
    carrier_name = tool_input.get("carrier_name")
    if not receipt_id or not tracking_code or not carrier_name:
        raise ToolError("A receipt_id, tracking_code, and carrier_name are required.")
    _call_etsy(_get_client().mark_receipt_shipped, receipt_id, tracking_code, carrier_name)
    return f'Order {receipt_id} marked shipped via {carrier_name}, tracking {tracking_code} — Etsy has notified the buyer.'


def describe_mark_order_shipped(tool_input):
    return (
        f'mark order {tool_input.get("receipt_id")} as shipped via {tool_input.get("carrier_name")} '
        f'(tracking {tool_input.get("tracking_code")}) — this emails the buyer and can\'t be quietly undone'
    )


TOOLS = [
    Tool(
        name="etsy_list_active_listings",
        description="List the shop's currently active Etsy listings with price and quantity. Use this to see what's live.",
        input_schema={
            "type": "object",
            "properties": {"limit": {"type": "integer", "description": "Max listings to return. Defaults to 25."}},
            "required": [],
        },
        handler=etsy_list_active_listings,
    ),
    Tool(
        name="etsy_get_listing",
        description="Get full details (price, quantity, description, state) for one Etsy listing by id.",
        input_schema={
            "type": "object",
            "properties": {"listing_id": {"type": "integer", "description": "The Etsy listing id."}},
            "required": ["listing_id"],
        },
        handler=etsy_get_listing,
    ),
    Tool(
        name="etsy_list_orders",
        description="List recent Etsy orders (receipts), optionally filtered to only unshipped ones.",
        input_schema={
            "type": "object",
            "properties": {
                "unshipped_only": {
                    "type": "boolean",
                    "description": "Only show orders that haven't shipped yet. Defaults to false.",
                }
            },
            "required": [],
        },
        handler=etsy_list_orders,
    ),
    Tool(
        name="etsy_get_order",
        description="Get full details for one Etsy order (receipt) by id, including any message from the buyer.",
        input_schema={
            "type": "object",
            "properties": {"receipt_id": {"type": "integer", "description": "The Etsy receipt (order) id."}},
            "required": ["receipt_id"],
        },
        handler=etsy_get_order,
    ),
    Tool(
        name="etsy_draft_listing",
        description=(
            "Draft a new Etsy listing (title, description, price, quantity, and optional "
            "tags/materials/category) for the user to review. This only saves a local draft — "
            "it never goes live on Etsy. Use etsy_publish_listing to actually publish it."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "title": {"type": "string"},
                "description": {"type": "string"},
                "price": {"type": "number", "description": "Price in dollars, e.g. 24.99."},
                "quantity": {"type": "integer"},
                "who_made": {"type": "string", "description": "One of: i_did, someone_else, collective. Defaults to i_did."},
                "when_made": {
                    "type": "string",
                    "description": "Etsy's production-date bucket, e.g. made_to_order, 2020_2026. Defaults to made_to_order.",
                },
                "taxonomy_id": {"type": "integer", "description": "Etsy category id — required before this draft can be published."},
                "tags": {"type": "array", "items": {"type": "string"}},
                "materials": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["title", "description", "price", "quantity"],
        },
        handler=etsy_draft_listing,
    ),
    Tool(
        name="etsy_list_listing_drafts",
        description="List saved Etsy listing drafts, with their publish status.",
        input_schema={"type": "object", "properties": {}, "required": []},
        handler=etsy_list_listing_drafts,
    ),
    Tool(
        name="etsy_draft_buyer_reply",
        description=(
            "Draft a reply to a buyer's message for the user to review and send themselves. "
            "Etsy's API doesn't allow an app to send buyer messages directly, so this only "
            "ever saves a draft — never implies the reply has been sent."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "receipt_id": {"type": "integer", "description": "The order this reply is about, if any."},
                "body": {"type": "string", "description": "The full reply text."},
            },
            "required": ["body"],
        },
        handler=etsy_draft_buyer_reply,
    ),
    Tool(
        name="etsy_list_buyer_reply_drafts",
        description="List previously saved buyer-reply drafts.",
        input_schema={"type": "object", "properties": {}, "required": []},
        handler=etsy_list_buyer_reply_drafts,
    ),
    Tool(
        name="etsy_publish_listing",
        description=(
            "Publish a saved listing draft live to Etsy (creates it and activates it). "
            "This spends Etsy's listing fee and makes it publicly visible — requires the "
            "user's confirmation."
        ),
        input_schema={
            "type": "object",
            "properties": {"draft_id": {"type": "string", "description": "The listing draft's id."}},
            "required": ["draft_id"],
        },
        handler=etsy_publish_listing,
        describe=describe_publish_listing,
    ),
    Tool(
        name="etsy_update_listing_price",
        description="Change the live price of an existing Etsy listing. Requires the user's confirmation.",
        input_schema={
            "type": "object",
            "properties": {
                "listing_id": {"type": "integer"},
                "price": {"type": "number", "description": "New price in dollars."},
            },
            "required": ["listing_id", "price"],
        },
        handler=etsy_update_listing_price,
        describe=describe_update_listing_price,
    ),
    Tool(
        name="etsy_update_listing_quantity",
        description="Change the live inventory quantity of an existing Etsy listing. Requires the user's confirmation.",
        input_schema={
            "type": "object",
            "properties": {"listing_id": {"type": "integer"}, "quantity": {"type": "integer"}},
            "required": ["listing_id", "quantity"],
        },
        handler=etsy_update_listing_quantity,
        describe=describe_update_listing_quantity,
    ),
    Tool(
        name="etsy_deactivate_listing",
        description="Take a live Etsy listing down (make it inactive). Requires the user's confirmation.",
        input_schema={
            "type": "object",
            "properties": {"listing_id": {"type": "integer"}},
            "required": ["listing_id"],
        },
        handler=etsy_deactivate_listing,
        describe=describe_deactivate_listing,
    ),
    Tool(
        name="etsy_mark_order_shipped",
        description=(
            "Mark an Etsy order as shipped with a tracking number and carrier. This emails "
            "the buyer and requires the user's confirmation."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "receipt_id": {"type": "integer"},
                "tracking_code": {"type": "string"},
                "carrier_name": {"type": "string", "description": "e.g. usps, ups, fedex, dhl."},
            },
            "required": ["receipt_id", "tracking_code", "carrier_name"],
        },
        handler=etsy_mark_order_shipped,
        describe=describe_mark_order_shipped,
    ),
]
