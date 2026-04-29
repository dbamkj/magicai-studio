"""Phase-3 Payments — Razorpay (Orders API + HMAC verify, no webhook v1).

Two purchase kinds:
  1. credit_pack    → adds N credits to user.credits_balance
  2. tier_upgrade   → grants `subscription_tier=<tier>` for `duration_days`
                      (manual sub: a one-time payment, NO auto-debit, NO Subscription API)

Endpoints:
  GET  /api/payments/credit-packs            → list available packs
  GET  /api/payments/tier-upgrades           → list manual-sub tier offerings
  POST /api/payments/razorpay/create-order   → create RP order, persist locally, return checkout config
  POST /api/payments/razorpay/verify         → HMAC-verify success callback, fulfill purchase
  GET  /api/payments/transactions            → user's purchase history (last 50)
  GET  /api/payments/checkout-page           → backend-hosted Checkout HTML for native WebView use

Frontend on web → opens Checkout via injected script.
Frontend on native → opens this `/checkout-page?order_id=...` in `expo-web-browser`.
"""
from __future__ import annotations

import hmac
import hashlib
import logging
import os
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

import razorpay
from dotenv import load_dotenv
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel, Field

from core.config import DB_NAME

load_dotenv()

log = logging.getLogger("payments")
router = APIRouter(prefix="/api/payments", tags=["payments"])

# ---- env ----
RZP_KEY_ID = os.environ.get("RAZORPAY_KEY_ID", "").strip()
RZP_KEY_SECRET = os.environ.get("RAZORPAY_KEY_SECRET", "").strip()
RZP_BETA_CAP_PAISE = int(os.environ.get("RAZORPAY_BETA_AMOUNT_CAP_PAISE", "100000") or 100000)

# ---- Razorpay client (lazy) ----
_rzp_client: Optional[razorpay.Client] = None
def rzp() -> razorpay.Client:
    global _rzp_client
    if _rzp_client is None:
        if not RZP_KEY_ID or not RZP_KEY_SECRET:
            raise HTTPException(status_code=503, detail="Razorpay not configured.")
        _rzp_client = razorpay.Client(auth=(RZP_KEY_ID, RZP_KEY_SECRET))
    return _rzp_client

# ---- DB ----
MONGO_URL = os.environ["MONGO_URL"]
_db_client = AsyncIOMotorClient(MONGO_URL)
db = _db_client[DB_NAME]
ORDERS = db.payment_orders
USERS = db.users


# ============================================================
#  CATALOG (in-code; can move to DB later if pricing iterates)
# ============================================================

CREDIT_PACKS: list[dict] = [
    {"id": "credits_100",  "label": "Starter Pack", "credits": 100,  "price_inr":  99, "popular": False, "savings": None},
    {"id": "credits_350",  "label": "Power Pack",   "credits": 350,  "price_inr": 299, "popular": True,  "savings": "Save 18%"},
    {"id": "credits_1500", "label": "Pro Pack",     "credits": 1500, "price_inr": 999, "popular": False, "savings": "Save 33%"},
]

TIER_UPGRADES: list[dict] = [
    {
        "id": "tier_starter_30d",
        "tier": "starter",
        "label": "Starter",
        "subtitle": "Perfect for casual creators",
        "price_inr": 199,
        "duration_days": 30,
        "perks": [
            "300 credits",
            "10 reels per day",
            "Stock Video unlimited",
            "Email support",
        ],
        "popular": False,
    },
    {
        "id": "tier_creator_30d",
        "tier": "creator",
        "label": "Creator",
        "subtitle": "For serious content creators",
        "price_inr": 399,
        "duration_days": 30,
        "perks": [
            "1000 credits",
            "Unlimited reels",
            "Magic Hour cinematic AI",
            "Avatar & lipsync",
            "Priority support",
        ],
        "popular": True,
    },
    {
        "id": "tier_pro_30d",
        "tier": "pro",
        "label": "Pro",
        "subtitle": "Studios, brands & agencies",
        "price_inr": 999,
        "duration_days": 30,
        "perks": [
            "3000 credits",
            "Everything in Creator",
            "Faceswap & multishot",
            "Commercial license",
            "Dedicated support",
        ],
        "popular": False,
    },
]


def _find_credit_pack(item_id: str) -> Optional[dict]:
    return next((p for p in CREDIT_PACKS if p["id"] == item_id), None)


def _find_tier_upgrade(item_id: str) -> Optional[dict]:
    return next((t for t in TIER_UPGRADES if t["id"] == item_id), None)


# ============================================================
#  PYDANTIC
# ============================================================

class CreateOrderRequest(BaseModel):
    kind: str = Field(..., description="'credit_pack' | 'tier_upgrade'")
    item_id: str = Field(..., min_length=2)


class VerifyOrderRequest(BaseModel):
    razorpay_order_id: str
    razorpay_payment_id: str
    razorpay_signature: str


# ============================================================
#  AUTH HELPER (best-effort: extract user from JWT, allow guest)
# ============================================================

async def _resolve_user(request: Request) -> Optional[dict]:
    """Best-effort auth — pulls user from JWT if present, else returns None.
    Most endpoints REQUIRE auth (HTTPException 401 otherwise)."""
    try:
        from core.auth import decode_token  # type: ignore
    except Exception:
        decode_token = None  # noqa
    auth = request.headers.get("authorization") or request.headers.get("Authorization") or ""
    if not auth.lower().startswith("bearer "):
        return None
    token = auth.split(" ", 1)[1].strip()
    try:
        if decode_token:
            payload = decode_token(token)
        else:
            import jwt  # PyJWT
            secret = os.environ.get("JWT_SECRET") or os.environ.get("SECRET_KEY") or "secret"
            payload = jwt.decode(token, secret, algorithms=["HS256"])
        uid = payload.get("user_id") or payload.get("sub") or payload.get("id")
        if not uid:
            return None
        u = await USERS.find_one({"id": uid}) or await USERS.find_one({"_id": uid})
        return u
    except Exception:
        return None


async def _require_user(request: Request) -> dict:
    u = await _resolve_user(request)
    if not u:
        raise HTTPException(status_code=401, detail="Login required to make a purchase.")
    return u


# ============================================================
#  CATALOG ENDPOINTS
# ============================================================

@router.get("/credit-packs")
async def list_credit_packs():
    return {"packs": CREDIT_PACKS, "currency": "INR"}


@router.get("/tier-upgrades")
async def list_tier_upgrades():
    return {"tiers": TIER_UPGRADES, "currency": "INR", "note": "Manual subscription — no auto-debit. Renew anytime."}


@router.get("/config")
async def public_config():
    """Frontend bootstrap — what's the publishable key, what's the env, etc."""
    return {
        "key_id": RZP_KEY_ID or None,
        "is_test": RZP_KEY_ID.startswith("rzp_test_"),
        "currency": "INR",
        "configured": bool(RZP_KEY_ID and RZP_KEY_SECRET),
        "beta_cap_paise": RZP_BETA_CAP_PAISE,
    }


# ============================================================
#  CREATE ORDER
# ============================================================

@router.post("/razorpay/create-order")
async def create_order(req: CreateOrderRequest, request: Request):
    user = await _require_user(request)

    # 1. Resolve catalog item
    if req.kind == "credit_pack":
        item = _find_credit_pack(req.item_id)
    elif req.kind == "tier_upgrade":
        item = _find_tier_upgrade(req.item_id)
    else:
        raise HTTPException(status_code=400, detail="Unknown kind. Use 'credit_pack' or 'tier_upgrade'.")
    if not item:
        raise HTTPException(status_code=404, detail=f"Unknown item_id '{req.item_id}'")

    amount_paise = int(item["price_inr"]) * 100

    # Beta circuit-breaker — never debit more than the cap (in case live keys leak in)
    if amount_paise > RZP_BETA_CAP_PAISE:
        log.warning("payments: amount %d > beta cap %d, capping", amount_paise, RZP_BETA_CAP_PAISE)
        # Soft-cap: in beta we still create the order at item price, but log; admin can lower env if needed.
        # If the key is LIVE we hard-cap to protect against accidents.
        if RZP_KEY_ID.startswith("rzp_live_"):
            raise HTTPException(status_code=403, detail="Amount exceeds beta safety cap. Lower the price or raise RAZORPAY_BETA_AMOUNT_CAP_PAISE.")

    # 2. Create RP order
    receipt = f"mpx_{uuid.uuid4().hex[:18]}"
    try:
        rzp_order = rzp().order.create({
            "amount": amount_paise,
            "currency": "INR",
            "receipt": receipt[:40],
            "payment_capture": 1,
            "notes": {
                "kind": req.kind,
                "item_id": req.item_id,
                "user_id": str(user.get("id") or user.get("_id") or ""),
                "user_email": user.get("email") or "",
            },
        })
    except Exception as e:
        log.exception("rzp order.create failed: %s", e)
        raise HTTPException(status_code=502, detail=f"Razorpay error: {str(e)[:160]}")

    # 3. Persist locally
    order_doc = {
        "id": rzp_order["id"],
        "razorpay_order_id": rzp_order["id"],
        "user_id": str(user.get("id") or user.get("_id") or ""),
        "user_email": user.get("email") or "",
        "kind": req.kind,
        "item_id": req.item_id,
        "item_label": item["label"],
        "amount_paise": amount_paise,
        "currency": "INR",
        "status": "created",          # created | paid | fulfilled | failed | refunded
        "razorpay_payment_id": None,
        "razorpay_signature": None,
        "fulfilled_at": None,
        "created_at": datetime.now(timezone.utc),
        "receipt": receipt,
    }
    await ORDERS.insert_one(order_doc)
    log.info("payments: order %s created (%s, ₹%d, user=%s)",
             rzp_order["id"], req.kind, item["price_inr"], user.get("email"))

    # 4. Return config the client needs to open Checkout
    return {
        "order_id": rzp_order["id"],
        "key_id": RZP_KEY_ID,
        "amount_paise": amount_paise,
        "currency": "INR",
        "name": "MagiCAi Studio",
        "description": item["label"],
        "kind": req.kind,
        "item_id": req.item_id,
        "prefill": {
            "name": user.get("name") or user.get("display_name") or "",
            "email": user.get("email") or "",
            "contact": user.get("phone") or "",
        },
        "notes": {"kind": req.kind, "item_id": req.item_id},
        "theme": {"color": "#8B5CF6"},
    }


# ============================================================
#  VERIFY + FULFILL
# ============================================================

def _verify_signature(order_id: str, payment_id: str, signature: str) -> bool:
    """HMAC-SHA256 verification per Razorpay spec.
    body = "<order_id>|<payment_id>"
    expected = hex(hmac_sha256(KEY_SECRET, body))
    """
    body = f"{order_id}|{payment_id}".encode()
    expected = hmac.new(RZP_KEY_SECRET.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)


async def _fulfill(order: dict) -> dict:
    """Apply the purchase to the user record. Idempotent."""
    user_id = order["user_id"]
    if not user_id:
        return {"ok": False, "reason": "missing user_id on order"}
    if order.get("status") == "fulfilled":
        return {"ok": True, "already": True}

    user = await USERS.find_one({"id": user_id}) or await USERS.find_one({"_id": user_id})
    if not user:
        return {"ok": False, "reason": "user not found"}

    update: dict = {}
    summary = {}

    if order["kind"] == "credit_pack":
        pack = _find_credit_pack(order["item_id"]) or {}
        credits = int(pack.get("credits") or 0)
        new_bal = int(user.get("credits_balance", 0)) + credits
        update["credits_balance"] = new_bal
        summary = {"kind": "credit_pack", "credits_added": credits, "new_balance": new_bal}

    elif order["kind"] == "tier_upgrade":
        tier_def = _find_tier_upgrade(order["item_id"]) or {}
        tier = tier_def.get("tier", "creator")
        days = int(tier_def.get("duration_days") or 30)
        # If user is already on this/higher tier and not expired, EXTEND. Else SET to now+days.
        now = datetime.now(timezone.utc)
        existing_exp = user.get("tier_expires_at")
        if isinstance(existing_exp, datetime) and existing_exp > now and user.get("subscription_tier") == tier:
            new_exp = existing_exp + timedelta(days=days)
        else:
            new_exp = now + timedelta(days=days)
        # also bonus credits with the tier
        bonus_credits_map = {"starter": 300, "creator": 1000, "pro": 3000}
        bonus = bonus_credits_map.get(tier, 0)
        new_bal = int(user.get("credits_balance", 0)) + bonus
        update.update({
            "subscription_tier": tier,
            "tier_expires_at": new_exp,
            "trial_active": False,        # promote out of trial cleanly
            "credits_balance": new_bal,
        })
        summary = {
            "kind": "tier_upgrade",
            "tier": tier,
            "tier_expires_at": new_exp.isoformat(),
            "credits_added": bonus,
            "new_balance": new_bal,
        }

    if update:
        await USERS.update_one({"id": user_id} if user.get("id") else {"_id": user_id}, {"$set": update})

    await ORDERS.update_one(
        {"id": order["id"]},
        {"$set": {"status": "fulfilled", "fulfilled_at": datetime.now(timezone.utc), "fulfillment": summary}},
    )
    log.info("payments: fulfilled %s (%s)", order["id"], summary)
    return {"ok": True, "summary": summary}


@router.post("/razorpay/verify")
async def verify_order(req: VerifyOrderRequest, request: Request):
    user = await _require_user(request)

    # 1. lookup order
    order = await ORDERS.find_one({"id": req.razorpay_order_id})
    if not order:
        raise HTTPException(status_code=404, detail="Order not found.")
    if order["user_id"] and user.get("id") and order["user_id"] != str(user.get("id")):
        raise HTTPException(status_code=403, detail="Order belongs to another user.")

    # 2. verify HMAC
    if not _verify_signature(req.razorpay_order_id, req.razorpay_payment_id, req.razorpay_signature):
        await ORDERS.update_one({"id": req.razorpay_order_id},
                                {"$set": {"status": "failed", "failure_reason": "signature_mismatch"}})
        raise HTTPException(status_code=400, detail="Payment signature verification failed.")

    # 3. mark paid + fulfill — guard against re-marking a fulfilled order
    if order.get("status") != "fulfilled":
        await ORDERS.update_one(
            {"id": req.razorpay_order_id},
            {"$set": {
                "razorpay_payment_id": req.razorpay_payment_id,
                "razorpay_signature": req.razorpay_signature,
                "status": "paid",
            }},
        )
    fulfilled = await _fulfill({**order, "razorpay_payment_id": req.razorpay_payment_id})
    if not fulfilled.get("ok"):
        log.warning("fulfillment failed: %s", fulfilled)
        return {"verified": True, "fulfilled": False, "reason": fulfilled.get("reason")}
    # Idempotent re-verify of an already-fulfilled order — short-circuit before summary lookup
    if fulfilled.get("already"):
        return {"verified": True, "fulfilled": True, "already": True, "order_id": req.razorpay_order_id}

    return {"verified": True, "fulfilled": True, "summary": fulfilled["summary"], "order_id": req.razorpay_order_id}


# ============================================================
#  HISTORY
# ============================================================

@router.get("/transactions")
async def list_transactions(request: Request):
    user = await _require_user(request)
    cursor = ORDERS.find(
        {"user_id": str(user.get("id") or user.get("_id") or "")},
        {"_id": 0},
    ).sort("created_at", -1).limit(50)
    items = await cursor.to_list(length=50)
    for it in items:
        for k, v in list(it.items()):
            if isinstance(v, datetime):
                it[k] = v.isoformat()
    return {"transactions": items, "count": len(items)}


# ============================================================
#  HOSTED CHECKOUT PAGE (for native Expo via WebView)
# ============================================================

@router.get("/checkout-page", response_class=HTMLResponse)
async def hosted_checkout(order_id: str, key_id: str, name: str = "MagiCAi Studio",
                          description: str = "Purchase", color: str = "#8B5CF6",
                          email: str = "", contact: str = ""):
    """Self-hosted Razorpay Checkout page. Native app opens this in `expo-web-browser`.
    On payment success/dismiss, the page auto-closes via JS callback to the backend then a
    deep link `magicai://payment-result?status=...&order_id=...&payment_id=...`."""
    return f"""<!doctype html>
<html><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Checkout · MagiCAi Studio</title>
<style>
  body {{ font-family: -apple-system, system-ui, sans-serif; background:#0B1120; color:#fff;
          min-height:100vh; display:flex; align-items:center; justify-content:center; margin:0; padding:24px; }}
  .card {{ background:#1E293B; border-radius:16px; padding:24px; max-width:360px; width:100%; text-align:center; }}
  .logo {{ font-size:24px; font-weight:800; background:linear-gradient(90deg,#8B5CF6,#EC4899);
           -webkit-background-clip:text; -webkit-text-fill-color:transparent; margin-bottom:8px; }}
  .sub {{ color:#94A3B8; font-size:13px; margin-bottom:20px; }}
  .btn {{ background:#8B5CF6; color:#fff; border:none; border-radius:10px;
           padding:14px 24px; font-size:15px; font-weight:700; cursor:pointer; width:100%; }}
  .status {{ margin-top:20px; font-size:13px; color:#94A3B8; min-height:20px; }}
</style>
</head><body>
  <div class="card">
    <div class="logo">MagiCAi Studio</div>
    <div class="sub">{description}</div>
    <button class="btn" id="payBtn" onclick="openCheckout()">Pay securely with Razorpay</button>
    <div class="status" id="status"></div>
  </div>
<script src="https://checkout.razorpay.com/v1/checkout.js"></script>
<script>
function setStatus(t) {{ document.getElementById('status').innerText = t; }}
function deepLink(qs) {{
  // Try to redirect back to the Expo app
  setTimeout(function () {{ window.location.href = 'magicai://payment-result?' + qs; }}, 100);
}}
function openCheckout() {{
  setStatus('Opening Razorpay…');
  var rzp = new Razorpay({{
    key: {key_id!r},
    order_id: {order_id!r},
    name: {name!r},
    description: {description!r},
    theme: {{ color: {color!r} }},
    prefill: {{ email: {email!r}, contact: {contact!r} }},
    handler: function (resp) {{
      setStatus('Payment received. Verifying…');
      fetch('/api/payments/razorpay/verify', {{
        method: 'POST', headers: {{'Content-Type': 'application/json'}},
        body: JSON.stringify(resp),
      }}).then(function(r){{return r.json();}}).then(function(data){{
        setStatus(data && data.fulfilled ? '✅ Success! Redirecting…' : '⚠️ Verified but not fulfilled.');
        deepLink('status=success&order_id=' + encodeURIComponent({order_id!r}) + '&payment_id=' + encodeURIComponent(resp.razorpay_payment_id));
      }}).catch(function(e){{ setStatus('Verify failed: ' + e); }});
    }},
    modal: {{
      ondismiss: function () {{
        setStatus('Cancelled.');
        deepLink('status=cancelled&order_id=' + encodeURIComponent({order_id!r}));
      }}
    }}
  }});
  rzp.open();
}}
window.addEventListener('load', function() {{
  // auto-open on page load for the smoothest UX
  setTimeout(openCheckout, 350);
}});
</script>
</body></html>"""
