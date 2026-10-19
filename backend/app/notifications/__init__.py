"""Notification domain module: email templates and background job handlers."""

from .emails import (
    handle_order_confirmed,
    handle_order_refunded,
    handle_order_shipped,
    handle_password_reset,
    render_email_template,
)

__all__ = [
    "handle_order_confirmed",
    "handle_order_refunded",
    "handle_order_shipped",
    "handle_password_reset",
    "render_email_template",
]
