"""Transactional email templates and background job handlers for SCENTHAUS multi-tenant notifications."""

from collections.abc import Mapping
import html
import json
import logging
import os
from typing import Any
import urllib.request
from sqlalchemy.orm import Session as DatabaseSession

from ..jobs.queue import register_task
from ..models import AuditLog, Tenant
from ..tenancy.constants import DEFAULT_TENANT_ID

logger = logging.getLogger(__name__)


def _base_email_html(title: str, tenant_name: str, body_html: str) -> str:
    """Wrap content in a clean, responsive HTML email container with tenant branding."""
    escaped_tenant = html.escape(tenant_name)
    escaped_title = html.escape(title)
    return (
        '<!DOCTYPE html>\n'
        '<html lang="en">\n'
        '<head>\n'
        '  <meta charset="UTF-8">\n'
        '  <meta name="viewport" content="width=device-width, initial-scale=1.0">\n'
        f'  <title>{escaped_title}</title>\n'
        '</head>\n'
        '<body style="margin: 0; padding: 0; background-color: #f4f5f7; '
        'font-family: -apple-system, BlinkMacSystemFont, \'Segoe UI\', Roboto, Helvetica, Arial, sans-serif; '
        'color: #1f2937; line-height: 1.5;">\n'
        '  <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="background-color: #f4f5f7; padding: 32px 16px;">\n'
        '    <tr>\n'
        '      <td align="center">\n'
        '        <table role="presentation" width="100%" style="max-width: 600px; background-color: #ffffff; '
        'border-radius: 8px; overflow: hidden; box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);">\n'
        '          <!-- Header -->\n'
        '          <tr>\n'
        '            <td style="background-color: #111827; padding: 24px 32px; text-align: center;">\n'
        '              <h1 style="margin: 0; color: #f9fafb; font-size: 20px; font-weight: 600; '
        f'letter-spacing: 0.05em; text-transform: uppercase;">{escaped_tenant}</h1>\n'
        '            </td>\n'
        '          </tr>\n'
        '          <!-- Main Content -->\n'
        '          <tr>\n'
        '            <td style="padding: 32px 32px 24px 32px;">\n'
        f'              {body_html}\n'
        '            </td>\n'
        '          </tr>\n'
        '          <!-- Footer -->\n'
        '          <tr>\n'
        '            <td style="background-color: #f9fafb; padding: 20px 32px; text-align: center; '
        'border-top: 1px solid #e5e7eb; font-size: 12px; color: #6b7280;">\n'
        f'              <p style="margin: 0 0 4px 0;">This email was sent on behalf of {escaped_tenant}.</p>\n'
        '              <p style="margin: 0;">If you have any questions or concerns, please reply directly to this email.</p>\n'
        '            </td>\n'
        '          </tr>\n'
        '        </table>\n'
        '      </td>\n'
        '    </tr>\n'
        '  </table>\n'
        '</body>\n'
        '</html>'
    )


def _render_order_confirmed(tenant_name: str, payload: Mapping[str, Any]) -> dict[str, str]:
    order_number = str(payload.get("order_number") or payload.get("order_id") or "N/A")
    customer_name = str(payload.get("customer_name") or payload.get("name") or "Valued Customer")
    currency = str(payload.get("currency") or "SGD")

    if "total" in payload and payload["total"] is not None:
        val = payload["total"]
        total_str = f"{float(val):,.2f}" if isinstance(val, (int, float)) else str(val)
    elif "total_amount" in payload and payload["total_amount"] is not None:
        val = payload["total_amount"]
        total_str = f"{float(val):,.2f}" if isinstance(val, (int, float)) else str(val)
    elif "total_minor" in payload and payload["total_minor"] is not None:
        total_str = f"{payload['total_minor'] / 100:,.2f}"
    else:
        total_str = "0.00"

    items = payload.get("items") or []

    # Format text items
    items_text_lines = []
    if items:
        items_text_lines.append("\nOrder Items:")
        for item in items:
            if isinstance(item, Mapping):
                it_name = item.get("name") or item.get("product_name") or item.get("sku") or "Item"
                it_qty = item.get("quantity") or item.get("qty") or 1
                it_price = item.get("price") or item.get("unit_price")
                suffix = f" @ {it_price}" if it_price is not None else ""
                items_text_lines.append(f"  • {it_name} x{it_qty}{suffix}")
            else:
                items_text_lines.append(f"  • {item}")
    items_text_block = "\n".join(items_text_lines)

    # Format HTML items
    items_html_rows = []
    if items:
        for item in items:
            if isinstance(item, Mapping):
                it_name = html.escape(str(item.get("name") or item.get("product_name") or item.get("sku") or "Item"))
                it_qty = html.escape(str(item.get("quantity") or item.get("qty") or 1))
                it_price = item.get("price") or item.get("unit_price")
                price_cell = (
                    f'<td align="right" style="padding: 8px 0; color: #374151;">{html.escape(str(it_price))}</td>'
                    if it_price is not None
                    else ""
                )
                items_html_rows.append(
                    f'<tr><td style="padding: 8px 0; color: #111827;">{it_name}</td>'
                    f'<td align="center" style="padding: 8px 0; color: #4b5563;">x{it_qty}</td>'
                    f'{price_cell}</tr>'
                )
            else:
                items_html_rows.append(
                    f'<tr><td colspan="3" style="padding: 8px 0; color: #111827;">{html.escape(str(item))}</td></tr>'
                )
    items_html_block = (
        f'<table width="100%" style="border-collapse: collapse; margin-top: 16px; font-size: 14px;">'
        f'<thead><tr style="border-bottom: 1px solid #e5e7eb; color: #6b7280; font-size: 12px; text-transform: uppercase;">'
        f'<th align="left" style="padding: 8px 0;">Item</th><th align="center" style="padding: 8px 0;">Qty</th>'
        f'<th align="right" style="padding: 8px 0;">Price</th></tr></thead>'
        f'<tbody>{"".join(items_html_rows)}</tbody></table>'
        if items_html_rows
        else ""
    )

    subject = (
        f"[{tenant_name}] Order Confirmed: {order_number}"
        if order_number != "N/A"
        else f"[{tenant_name}] Order Confirmation"
    )

    text = (
        f"Hello {customer_name},\n\n"
        f"Thank you for ordering with {tenant_name}! We're delighted to confirm that your order has been received "
        f"and is being processed.\n\n"
        f"Order Summary:\n"
        f"- Order Number: {order_number}\n"
        f"- Total: {total_str} {currency}\n"
        f"{items_text_block}\n\n"
        f"We will notify you once your package ships.\n\n"
        f"Warm regards,\n"
        f"The {tenant_name} Team"
    )

    body_html = (
        f'<h2 style="margin: 0 0 16px 0; font-size: 18px; color: #111827;">Order Confirmation</h2>'
        f'<p style="margin: 0 0 16px 0; font-size: 15px; color: #374151;">'
        f'Hello <strong>{html.escape(customer_name)}</strong>,</p>'
        f'<p style="margin: 0 0 20px 0; font-size: 14px; color: #4b5563;">'
        f'Thank you for your order with <strong>{html.escape(tenant_name)}</strong>. '
        f'We have received your order and our team is preparing it for shipment.</p>'
        f'<div style="background-color: #f9fafb; border: 1px solid #e5e7eb; border-radius: 6px; padding: 16px; margin-bottom: 20px;">'
        f'<p style="margin: 0 0 8px 0; font-size: 14px; color: #111827;"><strong>Order Number:</strong> {html.escape(order_number)}</p>'
        f'<p style="margin: 0; font-size: 14px; color: #111827;"><strong>Total:</strong> {html.escape(total_str)} {html.escape(currency)}</p>'
        f'{items_html_block}'
        f'</div>'
        f'<p style="margin: 0; font-size: 14px; color: #4b5563;">'
        f'We will send another update with tracking details as soon as your items are dispatched.</p>'
    )

    return {"subject": subject, "text": text, "html": _base_email_html(subject, tenant_name, body_html)}


def _render_order_shipped(tenant_name: str, payload: Mapping[str, Any]) -> dict[str, str]:
    order_number = str(payload.get("order_number") or payload.get("order_id") or "N/A")
    customer_name = str(payload.get("customer_name") or payload.get("name") or "Valued Customer")
    carrier = str(payload.get("carrier") or "Standard Delivery")
    tracking_number = str(payload.get("tracking_number") or payload.get("tracking") or "N/A")
    tracking_url = payload.get("tracking_url") or payload.get("url")

    subject = (
        f"[{tenant_name}] Your Order Has Shipped: {order_number}"
        if order_number != "N/A"
        else f"[{tenant_name}] Your Order Has Shipped"
    )

    tracking_url_text = f"\nTrack shipment: {tracking_url}\n" if tracking_url else ""
    text = (
        f"Hello {customer_name},\n\n"
        f"Great news! Your order from {tenant_name} is on its way.\n\n"
        f"Shipment Details:\n"
        f"- Order Number: {order_number}\n"
        f"- Carrier: {carrier}\n"
        f"- Tracking Number: {tracking_number}\n"
        f"{tracking_url_text}\n"
        f"Thank you for your purchase!\n\n"
        f"Warm regards,\n"
        f"The {tenant_name} Team"
    )

    tracking_btn_html = (
        f'<p style="margin: 20px 0 0 0; text-align: center;">'
        f'<a href="{html.escape(str(tracking_url), quote=True)}" style="display: inline-block; background-color: #111827; '
        f'color: #ffffff; text-decoration: none; padding: 10px 24px; border-radius: 6px; font-weight: 500; font-size: 14px;">'
        f'Track Package</a></p>'
        if tracking_url
        else ""
    )

    body_html = (
        f'<h2 style="margin: 0 0 16px 0; font-size: 18px; color: #111827;">Your Order Is On Its Way</h2>'
        f'<p style="margin: 0 0 16px 0; font-size: 15px; color: #374151;">'
        f'Hello <strong>{html.escape(customer_name)}</strong>,</p>'
        f'<p style="margin: 0 0 20px 0; font-size: 14px; color: #4b5563;">'
        f'Good news! Your order from <strong>{html.escape(tenant_name)}</strong> has been shipped.</p>'
        f'<div style="background-color: #f9fafb; border: 1px solid #e5e7eb; border-radius: 6px; padding: 16px; margin-bottom: 20px;">'
        f'<p style="margin: 0 0 8px 0; font-size: 14px; color: #111827;"><strong>Order Number:</strong> {html.escape(order_number)}</p>'
        f'<p style="margin: 0 0 8px 0; font-size: 14px; color: #111827;"><strong>Carrier:</strong> {html.escape(carrier)}</p>'
        f'<p style="margin: 0; font-size: 14px; color: #111827;"><strong>Tracking Number:</strong> {html.escape(tracking_number)}</p>'
        f'{tracking_btn_html}'
        f'</div>'
        f'<p style="margin: 0; font-size: 14px; color: #4b5563;">'
        f'Delivery times vary depending on your destination. Thank you for shopping with us!</p>'
    )

    return {"subject": subject, "text": text, "html": _base_email_html(subject, tenant_name, body_html)}


def _render_order_refunded(tenant_name: str, payload: Mapping[str, Any]) -> dict[str, str]:
    order_number = str(payload.get("order_number") or payload.get("order_id") or "N/A")
    customer_name = str(payload.get("customer_name") or payload.get("name") or "Valued Customer")
    currency = str(payload.get("currency") or "SGD")

    if "amount" in payload and payload["amount"] is not None:
        val = payload["amount"]
        amt_str = f"{float(val):,.2f}" if isinstance(val, (int, float)) else str(val)
    elif "refund_amount" in payload and payload["refund_amount"] is not None:
        val = payload["refund_amount"]
        amt_str = f"{float(val):,.2f}" if isinstance(val, (int, float)) else str(val)
    elif "refunded_minor" in payload and payload["refunded_minor"] is not None:
        amt_str = f"{payload['refunded_minor'] / 100:,.2f}"
    elif "total" in payload and payload["total"] is not None:
        val = payload["total"]
        amt_str = f"{float(val):,.2f}" if isinstance(val, (int, float)) else str(val)
    else:
        amt_str = "0.00"

    reason = payload.get("reason")

    subject = (
        f"[{tenant_name}] Refund Confirmation for Order {order_number}"
        if order_number != "N/A"
        else f"[{tenant_name}] Refund Processed"
    )

    reason_line = f"- Reason: {reason}\n" if reason else ""
    text = (
        f"Hello {customer_name},\n\n"
        f"Your refund for order {order_number} has been processed by {tenant_name}.\n\n"
        f"Refund Details:\n"
        f"- Order Number: {order_number}\n"
        f"- Refund Amount: {amt_str} {currency}\n"
        f"{reason_line}\n"
        f"The refund will be credited to your original payment method within 5–10 business days.\n\n"
        f"Warm regards,\n"
        f"The {tenant_name} Team"
    )

    reason_html = (
        f'<p style="margin: 8px 0 0 0; font-size: 14px; color: #4b5563;">'
        f'<strong>Reason:</strong> {html.escape(str(reason))}</p>'
        if reason
        else ""
    )

    body_html = (
        f'<h2 style="margin: 0 0 16px 0; font-size: 18px; color: #111827;">Refund Processed</h2>'
        f'<p style="margin: 0 0 16px 0; font-size: 15px; color: #374151;">'
        f'Hello <strong>{html.escape(customer_name)}</strong>,</p>'
        f'<p style="margin: 0 0 20px 0; font-size: 14px; color: #4b5563;">'
        f'A refund has been issued for your order with <strong>{html.escape(tenant_name)}</strong>.</p>'
        f'<div style="background-color: #f9fafb; border: 1px solid #e5e7eb; border-radius: 6px; padding: 16px; margin-bottom: 20px;">'
        f'<p style="margin: 0 0 8px 0; font-size: 14px; color: #111827;"><strong>Order Number:</strong> {html.escape(order_number)}</p>'
        f'<p style="margin: 0; font-size: 14px; color: #111827;"><strong>Refund Amount:</strong> {html.escape(amt_str)} {html.escape(currency)}</p>'
        f'{reason_html}'
        f'</div>'
        f'<p style="margin: 0; font-size: 14px; color: #4b5563;">'
        f'Depending on your payment provider, the refunded funds typically appear on your statement within 5–10 business days.</p>'
    )

    return {"subject": subject, "text": text, "html": _base_email_html(subject, tenant_name, body_html)}


def _render_password_reset(tenant_name: str, payload: Mapping[str, Any]) -> dict[str, str]:
    customer_name = str(payload.get("customer_name") or payload.get("name") or "Valued Customer")
    reset_url = payload.get("reset_url") or payload.get("url")
    reset_token = payload.get("reset_token") or payload.get("token")
    expires = (
        payload.get("expires_in")
        or payload.get("expires_in_minutes")
        or payload.get("expires_minutes")
        or "30 minutes"
    )
    expires_str = f"{expires} minutes" if isinstance(expires, (int, float)) else str(expires)

    subject = f"[{tenant_name}] Reset Your Password"

    if reset_url:
        target_text = f"Click the link below to choose a new password:\n{reset_url}"
    elif reset_token:
        target_text = f"Use the verification token below to reset your password:\nToken: {reset_token}"
    else:
        target_text = "Please access your account security settings to proceed with the password reset."

    text = (
        f"Hello {customer_name},\n\n"
        f"We received a request to reset your password for your {tenant_name} account.\n\n"
        f"{target_text}\n\n"
        f"This link is valid for {expires_str}.\n\n"
        f"If you did not request a password reset, you can safely ignore this email. Your password will not change.\n\n"
        f"Warm regards,\n"
        f"The {tenant_name} Team"
    )

    if reset_url:
        cta_html = (
            f'<p style="margin: 24px 0; text-align: center;">'
            f'<a href="{html.escape(str(reset_url), quote=True)}" style="display: inline-block; background-color: #111827; '
            f'color: #ffffff; text-decoration: none; padding: 12px 28px; border-radius: 6px; font-weight: 600; font-size: 14px;">'
            f'Reset Password</a></p>'
            f'<p style="margin: 0 0 16px 0; font-size: 12px; color: #6b7280; word-break: break-all;">'
            f'If the button above does not work, copy and paste this link into your browser:<br>'
            f'<a href="{html.escape(str(reset_url), quote=True)}" style="color: #4b5563;">{html.escape(str(reset_url))}</a></p>'
        )
    elif reset_token:
        cta_html = (
            f'<div style="background-color: #f9fafb; border: 1px dashed #d1d5db; border-radius: 6px; padding: 16px; margin: 20px 0; text-align: center;">'
            f'<p style="margin: 0 0 6px 0; font-size: 12px; color: #6b7280; text-transform: uppercase;">Reset Token</p>'
            f'<code style="font-size: 18px; font-weight: 700; color: #111827; letter-spacing: 2px;">{html.escape(str(reset_token))}</code>'
            f'</div>'
        )
    else:
        cta_html = ""

    body_html = (
        f'<h2 style="margin: 0 0 16px 0; font-size: 18px; color: #111827;">Password Reset Request</h2>'
        f'<p style="margin: 0 0 16px 0; font-size: 15px; color: #374151;">'
        f'Hello <strong>{html.escape(customer_name)}</strong>,</p>'
        f'<p style="margin: 0 0 16px 0; font-size: 14px; color: #4b5563;">'
        f'We received a request to reset the password for your <strong>{html.escape(tenant_name)}</strong> account. '
        f'This request will expire in <strong>{html.escape(expires_str)}</strong>.</p>'
        f'{cta_html}'
        f'<p style="margin: 16px 0 0 0; font-size: 13px; color: #6b7280; border-top: 1px solid #f3f4f6; padding-top: 16px;">'
        f'If you did not make this request, please disregard this email. Your password will remain unchanged.</p>'
    )

    return {"subject": subject, "text": text, "html": _base_email_html(subject, tenant_name, body_html)}


def render_email_template(kind: str, tenant_name: str, payload: dict) -> dict[str, str]:
    """Render plain-text and escaped HTML email content for the specified notification type."""
    normalized_kind = kind.lower().strip()
    if normalized_kind.startswith("email."):
        normalized_kind = normalized_kind[len("email.") :]

    clean_tenant_name = (tenant_name or "").strip() or "SCENTHAUS"
    clean_payload = payload if isinstance(payload, Mapping) else {}

    if normalized_kind == "order_confirmed":
        return _render_order_confirmed(clean_tenant_name, clean_payload)
    if normalized_kind == "order_shipped":
        return _render_order_shipped(clean_tenant_name, clean_payload)
    if normalized_kind == "order_refunded":
        return _render_order_refunded(clean_tenant_name, clean_payload)
    if normalized_kind == "password_reset":
        return _render_password_reset(clean_tenant_name, clean_payload)

    raise ValueError(
        f"Unsupported email template kind: '{kind}'. "
        f"Expected one of: order_confirmed, order_shipped, order_refunded, password_reset"
    )


def _dispatch_transport(
    to: str | None,
    subject: str,
    text: str,
    html_content: str,
    *,
    tenant_name: str = "SCENTHAUS",
) -> bool:
    """Send transactional email via Resend or SMTP when credentials exist; otherwise log in dev/test."""
    if not to:
        logger.info("No recipient specified for email '%s' (%s); skipped transport", subject, tenant_name)
        return False

    resend_key = os.getenv("RESEND_API_KEY", "").strip()
    smtp_host = os.getenv("SMTP_HOST", "").strip()

    if resend_key:
        try:
            req_data = json.dumps({
                "from": f"{tenant_name} <notifications@scenthaus.com>",
                "to": [to],
                "subject": subject,
                "text": text,
                "html": html_content,
            }).encode("utf-8")
            req = urllib.request.Request(
                "https://api.resend.com/emails",
                data=req_data,
                headers={
                    "Authorization": f"Bearer {resend_key}",
                    "Content-Type": "application/json",
                },
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                logger.info("Email '%s' delivered to %s via Resend (status %d)", subject, to, resp.status)
                return True
        except Exception as exc:  # noqa: BLE001
            logger.warning("Failed to deliver email via Resend: %s", exc)

    if smtp_host:
        try:
            import smtplib
            from email.mime.multipart import MIMEMultipart
            from email.mime.text import MIMEText

            smtp_port = int(os.getenv("SMTP_PORT", "587"))
            smtp_user = os.getenv("SMTP_USER", "")
            smtp_pass = os.getenv("SMTP_PASSWORD", "")

            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = f"{tenant_name} <{smtp_user or 'noreply@scenthaus.com'}>"
            msg["To"] = to
            msg.attach(MIMEText(text, "plain", "utf-8"))
            msg.attach(MIMEText(html_content, "html", "utf-8"))

            with smtplib.SMTP(smtp_host, smtp_port, timeout=10) as server:
                if os.getenv("SMTP_USE_TLS", "true").lower() in ("true", "1", "yes"):
                    server.starttls()
                if smtp_user and smtp_pass:
                    server.login(smtp_user, smtp_pass)
                server.sendmail(msg["From"], [to], msg.as_string())
            logger.info("Email '%s' delivered to %s via SMTP (%s)", subject, to, smtp_host)
            return True
        except Exception as exc:  # noqa: BLE001
            logger.warning("Failed to deliver email via SMTP: %s", exc)

    logger.info("Dispatched notification [%s] to %s: %s", tenant_name, to, subject)
    return True


def _handle_email_task(
    db: DatabaseSession, tenant_id: str, kind: str, payload: dict[str, Any]
) -> dict[str, str]:
    """Common pipeline for fetching tenant, rendering template, and recording audit log."""
    tenant = db.get(Tenant, tenant_id) if tenant_id else None
    tenant_name = tenant.name if (tenant and tenant.name) else "SCENTHAUS"

    rendered = render_email_template(kind, tenant_name, payload)

    audit_entry = AuditLog(
        tenant_id=tenant_id or DEFAULT_TENANT_ID,
        actor="worker",
        action=f"notification.{kind}",
        detail={"to": payload.get("to"), "subject": rendered["subject"]},
    )
    db.add(audit_entry)
    db.flush()

    recipient = payload.get("to") or payload.get("customer_email") or payload.get("email")
    _dispatch_transport(
        to=recipient,
        subject=rendered["subject"],
        text=rendered["text"],
        html_content=rendered["html"],
        tenant_name=tenant_name,
    )

    return rendered


@register_task("email.order_confirmed")
def handle_order_confirmed(
    db: DatabaseSession, tenant_id: str, payload: dict[str, Any]
) -> dict[str, str]:
    """Background handler for order confirmation emails."""
    return _handle_email_task(db, tenant_id, "order_confirmed", payload or {})


@register_task("email.order_shipped")
def handle_order_shipped(
    db: DatabaseSession, tenant_id: str, payload: dict[str, Any]
) -> dict[str, str]:
    """Background handler for order dispatch/tracking emails."""
    return _handle_email_task(db, tenant_id, "order_shipped", payload or {})


@register_task("email.order_refunded")
def handle_order_refunded(
    db: DatabaseSession, tenant_id: str, payload: dict[str, Any]
) -> dict[str, str]:
    """Background handler for order refund confirmation emails."""
    return _handle_email_task(db, tenant_id, "order_refunded", payload or {})


@register_task("email.password_reset")
def handle_password_reset(
    db: DatabaseSession, tenant_id: str, payload: dict[str, Any]
) -> dict[str, str]:
    """Background handler for password reset emails."""
    return _handle_email_task(db, tenant_id, "password_reset", payload or {})
