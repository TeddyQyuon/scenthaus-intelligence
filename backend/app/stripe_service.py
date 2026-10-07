"""Stripe credentials and network operations stay exclusively on the server."""
import stripe
from .config import settings


def client():
    return stripe.StripeClient(settings.stripe_secret_key.get_secret_value(),
                               http_client=stripe.RequestsClient(timeout=10),
                               max_network_retries=1)


def create_session(params, key):
    return client().v1.checkout.sessions.create(params, {"idempotency_key": key})


def retrieve_session(session_id):
    return client().v1.checkout.sessions.retrieve(session_id)


def expire_session(session_id):
    return client().v1.checkout.sessions.expire(session_id)


def find_session(order):
    # A lost creation response can still have created a session. Only a complete
    # Stripe listing can establish absence; a truncated page is inconclusive.
    from datetime import timezone
    result = client().v1.checkout.sessions.list({"created": {
        "gte": int(order.created_at.replace(tzinfo=timezone.utc).timestamp()) - 60,
        "lte": int(order.expires_at.replace(tzinfo=timezone.utc).timestamp()) + 60}, "limit": 100})
    match = next((session for session in result.data if session.client_reference_id == order.id), None)
    return match, not result.has_more


def verify_event(payload, signature):
    return stripe.Webhook.construct_event(
        payload, signature, settings.stripe_webhook_secret.get_secret_value(),
        tolerance=300).to_dict()
