"""
KpopNara Invoice Bot — Phase 1+2
Forwards invoice attachments to n8n webhook.
Batches ALL attachments from a message into a single webhook payload.
Listens for ✅ reaction to trigger approval webhook.

Flow: Bot sends webhook → n8n responds immediately (ack) → bot keeps 🔄 as progress
      → n8n processes in background → n8n calls bot callback when done → bot replies to original message
"""

import asyncio
import csv
import io
import os
from datetime import datetime, timezone

import discord
import aiohttp
from aiohttp import web

# Config from environment variables
DISCORD_TOKEN = os.environ["DISCORD_BOT_TOKEN"]
N8N_WEBHOOK_URL = os.environ["N8N_WEBHOOK_URL"]  # e.g. https://your-n8n.com/webhook/invoice
N8N_APPROVE_URL = os.environ.get("N8N_APPROVE_WEBHOOK_URL", "").rstrip("/")  # e.g. .../webhook/invoice-approve
INVOICE_CHANNEL = os.environ.get("INVOICE_CHANNEL_NAME", "invoices")  # channel name to watch
BOT_CALLBACK_PORT = int(os.environ.get("BOT_CALLBACK_PORT", "9090"))

# In-memory store: message_id -> approval payload (line_items, etc.)
# Cleared on bot restart. For production, use Redis or DB.
_pending_approvals: dict[str, dict] = {}

VALID_TYPES = {
    "image/png",
    "image/jpeg",
    "image/jpg",
    "image/webp",
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "application/vnd.ms-excel",
}
VALID_EXTENSIONS = {"png", "jpg", "jpeg", "webp", "pdf", "xlsx", "xls"}

intents = discord.Intents.default()
intents.message_content = True  # Required to read message content
client = discord.Client(intents=intents)


def is_valid_attachment(attachment: discord.Attachment) -> bool:
    content_type = attachment.content_type or ""
    ext = attachment.filename.lower().split(".")[-1] if "." in attachment.filename else ""
    return content_type in VALID_TYPES or ext in VALID_EXTENSIONS


def _sanitize_filename(s: str) -> str:
    """Remove/replace chars unsafe for filenames."""
    return "".join(c if c.isalnum() or c in " -_" else "_" for c in (s or "invoice"))


def _build_line_items_summary(line_items: list) -> str:
    """Format line items for Discord message review."""
    if not line_items:
        return ""
    lines = ["**Line items for review:**", "```"]
    for i, li in enumerate(line_items[:20], 1):  # cap at 20 for readability
        if isinstance(li, dict):
            sku = li.get("sku", li.get("matched_sku", "?"))
            qty = li.get("quantity", "?")
            name = (li.get("product_name", "") or li.get("matched_product_name", ""))[:40]
            variant = li.get("variant_name", "")
            lines.append(f"{i}. {sku} x{qty} | {name} {variant}".strip())
        else:
            lines.append(str(li))
    if len(line_items) > 20:
        lines.append(f"... and {len(line_items) - 20} more")
    lines.append("```")
    return "\n".join(lines)


def _build_csv_from_line_items(line_items: list) -> str:
    """Build CSV string from line items."""
    if not line_items or not isinstance(line_items[0], dict):
        return ""
    keys = ["sku", "product_name", "variant_name", "quantity", "unit_price", "total_price", "vendor_notation"]
    out = io.StringIO()
    writer = csv.DictWriter(out, fieldnames=keys, extrasaction="ignore")
    writer.writeheader()
    for li in line_items:
        if isinstance(li, dict):
            writer.writerow({k: li.get(k, "") for k in keys})
    return out.getvalue()


async def _handle_invoice_callback(request: web.Request) -> web.Response:
    """Called by n8n when parse workflow finishes. Reply with line items + CSV for review."""
    try:
        body = await request.json()
        channel_id = int(body.get("channel_id", 0))
        message_id = int(body.get("message_id", 0))
        discord_message = body.get("discord_message", "") or "Invoice processed."
        line_items = body.get("line_items", [])
        standard_vendor_id = body.get("standard_vendor_id")
        vendor_name = body.get("vendor_name", "") or "invoice"

        if not channel_id or not message_id:
            return web.json_response({"error": "channel_id and message_id required"}, status=400)

        channel = client.get_channel(channel_id)
        if not channel:
            return web.json_response({"error": "channel not found"}, status=404)

        message = await channel.fetch_message(message_id)

        # Build message with line items for review
        date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        csv_filename = f"{_sanitize_filename(vendor_name)}_{date_str}.csv"
        text_parts = [discord_message]
        if line_items:
            text_parts.append(_build_line_items_summary(line_items))

        reply_text = "\n\n".join(p for p in text_parts if p)
        if not reply_text:
            reply_text = "Invoice processed."

        files = []
        if line_items:
            csv_content = _build_csv_from_line_items(line_items)
            if csv_content:
                files.append(discord.File(io.BytesIO(csv_content.encode("utf-8")), filename=csv_filename))

        reply_msg = await message.reply(reply_text, files=files if files else None)

        if line_items and N8N_APPROVE_URL:
            first = line_items[0] if isinstance(line_items[0], dict) else {}
            _pending_approvals[str(reply_msg.id)] = {
                "line_items": line_items,
                "standard_vendor_id": first.get("standard_vendor_id", standard_vendor_id),
                "vendor_name": first.get("vendor_name", vendor_name),
            }
            await reply_msg.add_reaction("✅")
            await reply_msg.add_reaction("❌")

        await message.remove_reaction("🔄", client.user)
        await message.add_reaction("✅")
        return web.json_response({"success": True})
    except Exception as e:
        print(f"❌ Callback error: {e}", flush=True)
        return web.json_response({"error": str(e)}, status=500)


@client.event
async def on_ready():
    print(f"✅ KpopNara Invoice Bot ready as {client.user}", flush=True)
    print(f"   Watching channel: #{INVOICE_CHANNEL}", flush=True)
    print(f"   Forwarding to: {N8N_WEBHOOK_URL}", flush=True)
    print(f"   Callback server: 0.0.0.0:{BOT_CALLBACK_PORT}", flush=True)

    # Start callback server for n8n to post results when parse workflow finishes
    app = web.Application()
    app.router.add_post("/invoice-callback", _handle_invoice_callback)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", BOT_CALLBACK_PORT)
    await site.start()


@client.event
async def on_message(message):
    # Ignore bot's own messages
    if message.author == client.user:
        return

    # Only process in the invoices channel
    if message.channel.name != INVOICE_CHANNEL:
        return

    # Only process if there are attachments
    if not message.attachments:
        return

    # Collect all valid attachments
    attachments = []
    for attachment in message.attachments:
        if not is_valid_attachment(attachment):
            continue
        attachments.append({
            "attachment_url": attachment.url,
            "filename": attachment.filename,
            "content_type": attachment.content_type or "application/octet-stream",
            "file_size": attachment.size,
        })

    if not attachments:
        return

    # Single payload with all attachments
    payload = {
        "attachments": attachments,
        "channel_id": str(message.channel.id),
        "channel_name": message.channel.name,
        "guild_id": str(message.guild.id) if message.guild else None,
        "message_id": str(message.id),
        "author": message.author.display_name,
        "author_id": str(message.author.id),
        "message_content": message.content or "",
    }

    # React once before processing
    await message.add_reaction("🔄")

    print(f"Forwarding {len(attachments)} attachment(s) to n8n webhook", flush=True)
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(N8N_WEBHOOK_URL, json=payload) as resp:
                if resp.status == 200:
                    result = await resp.json() or {}
                    if result.get("status") == "accepted":
                        # New flow: n8n acked, processing in background; callback will reply when done
                        # Keep 🔄 as progress
                        pass
                    elif "line_items" in result:
                        # Fallback: old workflow returns full result inline
                        discord_message = result.get("discord_message", "") or "Invoice processed."
                        line_items = result.get("line_items", [])
                        reply_msg = await message.reply(discord_message)
                        if line_items and N8N_APPROVE_URL:
                            first = line_items[0] if isinstance(line_items[0], dict) else {}
                            _pending_approvals[str(reply_msg.id)] = {
                                "line_items": line_items,
                                "standard_vendor_id": first.get("standard_vendor_id"),
                                "vendor_name": first.get("vendor_name", ""),
                            }
                            await reply_msg.add_reaction("✅")
                            await reply_msg.add_reaction("❌")
                        await message.remove_reaction("🔄", client.user)
                        await message.add_reaction("✅")
                    else:
                        # Unknown ack format; keep 🔄, hope callback arrives
                        print(f"   n8n ack: {result}", flush=True)
                else:
                    error_text = await resp.text()
                    print(f"❌ n8n webhook error {resp.status}: {error_text}", flush=True)
                    await message.remove_reaction("🔄", client.user)
                    await message.add_reaction("❌")
                    await message.reply(
                        f"⚠️ Invoice processing failed (HTTP {resp.status}). Check n8n logs."
                    )
    except Exception as e:
        print(f"❌ Error calling n8n webhook: {e}", flush=True)
        await message.remove_reaction("🔄", client.user)
        await message.add_reaction("❌")
        await message.reply(f"⚠️ Could not reach invoice processor: {type(e).__name__}")


@client.event
async def on_raw_reaction_add(payload: discord.RawReactionActionEvent):
    """When user reacts ✅ to our reply, call approval webhook."""
    if not N8N_APPROVE_URL or str(payload.emoji) not in ("✅", "❌"):
        return
    if payload.user_id == client.user.id:
        return

    msg_id = str(payload.message_id)
    data = _pending_approvals.pop(msg_id, None)
    if not data:
        return

    approved = str(payload.emoji) == "✅"
    payload_body = {
        "approved": approved,
        "line_items": data["line_items"],
        "standard_vendor_id": data.get("standard_vendor_id"),
        "vendor_name": data.get("vendor_name"),
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(N8N_APPROVE_URL, json=payload_body) as resp:
                if resp.status == 200 and approved:
                    result = await resp.json()
                    if result.get("success"):
                        channel = client.get_channel(payload.channel_id)
                        if channel:
                            msg = await channel.fetch_message(payload.message_id)
                            await msg.reply("✅ Invoice approved and written to BigQuery.")
    except Exception as e:
        print(f"Approval webhook error: {e}", flush=True)


client.run(DISCORD_TOKEN)
