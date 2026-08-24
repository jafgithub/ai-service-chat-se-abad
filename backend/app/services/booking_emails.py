"""The two emails a booking produces.

Separate from `email_service.py`, which is the shop's. Those templates take
items, a subtotal, a tax line, a delivery slot and a "collect the cash on
delivery" banner, and none of that describes somebody coming to fix a leak. A
visit has one price, one length, one address and one time.

Two emails go out, and they are not the same email with the addresses swapped:

* the customer needs the reference, when to be in, and who is coming
* the provider needs the address, the phone number and what the job is

Both are best effort and neither can fail a booking. By the time these run the
appointment exists and the customer has been shown a confirmation; raising here
would turn a booking that worked into an error on screen.

No em dashes anywhere. These go straight to customers, and the client reads
them as machine written.
"""

import logging
from datetime import datetime

from app.core.config import settings
from app.services.email_service import _send

logger = logging.getLogger("booking")

BRAND = "Service Assistant"

#: Where the provider's copy goes when the business has no email on file, so a
#: job is never silently unannounced. Falls back to the sending address, which
#: is somebody we know reads it. On a development box that somebody is the
#: client, so `BOOKING_FALLBACK_EMAIL` exists to point it elsewhere.
FALLBACK_TO = settings.BOOKING_FALLBACK_EMAIL or settings.SMTP_FROM


def _money(amount: float | None, currency: str = "USD") -> str:
    symbols = {"USD": "$", "GBP": "£", "EUR": "€"}
    if amount is None:
        return ""
    symbol = symbols.get((currency or "USD").upper())
    return f"{symbol}{amount:.2f}" if symbol else f"{amount:.2f} {currency.upper()}"


def _duration(minutes: int | None) -> str:
    if not minutes:
        return ""
    hours, mins = divmod(int(minutes), 60)
    if not hours:
        return f"{mins} min"
    if not mins:
        return f"{hours} hr"
    return f"{hours} hr {mins} min"


def _when(starts_at: datetime | None) -> str:
    """"Wednesday 12 August, 5:00 PM", the same wording the screen uses.

    Deliberately the same format as the API's own labels and the interface, so
    the email and the page a customer is looking at cannot appear to disagree
    about the appointment they just made.
    """
    if not starts_at:
        return "To be confirmed"
    return starts_at.strftime("%A %-d %B, %-I:%M %p")


def _row(label: str, value: str, strong: bool = False) -> str:
    if not value:
        return ""
    weight = "font-weight:700;" if strong else ""
    return (
        '<tr>'
        '<td style="padding:9px 0;color:#6b7280;font-size:14px;'
        'border-bottom:1px solid #f0f0f0;width:38%">' + label + '</td>'
        '<td style="padding:9px 0;color:#18181b;font-size:14px;'
        f'border-bottom:1px solid #f0f0f0;{weight}">' + value + '</td>'
        '</tr>'
    )


def _shell(heading: str, strapline: str, body: str, footer: str) -> str:
    return f"""
    <div style="font-family:Arial,Helvetica,sans-serif;max-width:600px;margin:auto;color:#18181b">
      <div style="background:linear-gradient(135deg,#f97316,#ef4444);padding:24px;border-radius:12px 12px 0 0">
        <h1 style="color:#fff;margin:0;font-size:20px">{heading}</h1>
        <p style="color:rgba(255,255,255,0.88);margin:6px 0 0;font-size:14px">{strapline}</p>
      </div>
      <div style="background:#fff;padding:24px;border:1px solid #f0f0f0;border-top:none">
        {body}
      </div>
      <div style="background:#faf8f5;padding:16px;border-radius:0 0 12px 12px;
                  text-align:center;color:#9ca3af;font-size:12px;border:1px solid #f0f0f0;border-top:none">
        {footer}
      </div>
    </div>"""


def send_customer_confirmation(
    *,
    to: str,
    customer_name: str,
    reference: str,
    service_name: str,
    provider_name: str,
    provider_phone: str | None,
    starts_at: datetime,
    duration_minutes: int,
    price: float,
    currency: str,
    address: str | None,
    notes: str | None,
    payment_method: str = "cod",
    paid: bool = False,
) -> None:
    """What the customer keeps. The reference and the time carry the message."""
    when = _when(starts_at)

    # Says what is actually true of this booking rather than one line for all
    # three cases. Somebody paying by card who reads "you settle up with the
    # provider" will turn up expecting to pay twice.
    if paid:
        payment_line = f"Paid in full, {_money(price, currency)}. Nothing to settle on the day."
    elif payment_method == "cod":
        payment_line = (f"Nothing has been charged. You settle up with {provider_name} "
                        f"for the work itself, {_money(price, currency)}.")
    else:
        method_name = "card" if payment_method == "stripe" else "PayPal"
        payment_line = (f"Payment by {method_name} has not completed yet. You can pay from "
                        f"My bookings, or settle up with {provider_name} on the day.")

    body = f"""
        <p style="margin:0 0 18px;font-size:15px;line-height:1.55">
          Hi <strong>{customer_name or "there"}</strong>, that is booked.
          <strong>{provider_name}</strong> will attend.
        </p>

        <div style="background:#fff7ed;border:1px solid #fed7aa;border-radius:10px;
                    padding:16px;margin:0 0 20px;text-align:center">
          <span style="color:#9a3412;font-size:12px;letter-spacing:1px">YOUR REFERENCE</span><br>
          <strong style="color:#7c2d12;font-size:22px;letter-spacing:1px">{reference}</strong>
          <p style="margin:10px 0 0;color:#7c2d12;font-size:15px">{when}</p>
        </div>

        <table style="width:100%;border-collapse:collapse">
          {_row("Service", service_name)}
          {_row("Provider", provider_name)}
          {_row("Phone", provider_phone or "")}
          {_row("When", when, strong=True)}
          {_row("How long", _duration(duration_minutes))}
          {_row("Price", _money(price, currency), strong=True)}
          {_row("Where", address or "")}
          {_row("Your notes", (notes or "").strip())}
        </table>

        <p style="margin:20px 0 0;font-size:14px;line-height:1.55;color:#6b7280">
          {payment_line}
        </p>
        <p style="margin:10px 0 0;font-size:14px;line-height:1.55;color:#6b7280">
          Need to change or cancel it? Sign in and open My bookings, or ring them on the
          number above and quote {reference}.
        </p>"""

    _send(to, f"Booked: {service_name}, {when} ({reference})",
          _shell("You are booked in", f"{reference} · {when}", body,
                 f"{BRAND} · this is a confirmation, not a bill"))


def send_provider_notification(
    *,
    to: str,
    provider_name: str,
    reference: str,
    service_name: str,
    customer_name: str,
    customer_email: str | None,
    customer_phone: str | None,
    starts_at: datetime,
    duration_minutes: int,
    price: float,
    currency: str,
    address: str | None,
    notes: str | None,
    payment_method: str = "cod",
    paid: bool = False,
) -> None:
    """What the provider needs in order to turn up: where, when, and who to ring."""
    when = _when(starts_at)

    # Whether to ask for money at the door is the one operational fact a
    # provider needs from this email, so it is stated rather than implied.
    if paid:
        collect_line = (f"<strong>Already paid online, {_money(price, currency)}. "
                        "Do not collect anything.</strong>")
    elif payment_method == "cod":
        collect_line = (f"<strong>Collect {_money(price, currency)} on the day.</strong> "
                        "Nothing has been paid through us.")
    else:
        method_name = "card" if payment_method == "stripe" else "PayPal"
        collect_line = (f"They chose to pay by {method_name} and it has not completed yet. "
                        f"If it has not by the time you attend, collect {_money(price, currency)}.")

    # The address is the one thing that decides whether this job can happen, so
    # it is called out rather than sitting in the middle of a table.
    address_block = ""
    if (address or "").strip():
        address_block = f"""
        <div style="background:#eff6ff;border-left:4px solid #2563eb;padding:12px 16px;margin:0 0 18px">
          <span style="color:#1e40af;font-size:12px">ADDRESS</span><br>
          <strong style="color:#1e3a8a;font-size:15px">{address.strip()}</strong>
        </div>"""
    else:
        address_block = """
        <div style="background:#fffbeb;border-left:4px solid #d97706;padding:12px 16px;margin:0 0 18px">
          <span style="color:#92400e;font-size:14px">No address was given. Ring the customer before you set off.</span>
        </div>"""

    body = f"""
        <p style="margin:0 0 18px;font-size:15px;line-height:1.55">
          <strong>{provider_name}</strong>, you have a new booking.
        </p>

        {address_block}

        <table style="width:100%;border-collapse:collapse">
          {_row("Reference", reference)}
          {_row("Job", service_name, strong=True)}
          {_row("When", when, strong=True)}
          {_row("How long", _duration(duration_minutes))}
          {_row("Your price", _money(price, currency), strong=True)}
          {_row("Customer", customer_name)}
          {_row("Phone", customer_phone or "Not given")}
          {_row("Email", customer_email or "")}
          {_row("Their notes", (notes or "").strip())}
        </table>

        <p style="margin:20px 0 0;font-size:14px;line-height:1.55;color:#6b7280">
          This time is already blocked out in your diary. {collect_line}
        </p>"""

    _send(to, f"New booking: {service_name}, {when} ({reference})",
          _shell("New booking", f"{reference} · {when}", body,
                 f"{BRAND} · sent because a customer booked one of your times"))


def send_receipt(
    *,
    to: str,
    customer_name: str,
    reference: str,
    service_name: str,
    provider_name: str,
    starts_at: datetime,
    price: float,
    currency: str,
    method: str,
) -> None:
    """Sent only when a payment provider says the money moved.

    Never sent optimistically. The customer's browser coming back to a success
    page proves nothing, so this is triggered by the webhook and by nothing
    else.
    """
    when = _when(starts_at)
    method_name = {"stripe": "card", "paypal": "PayPal"}.get(method, method)

    body = f"""
        <p style="margin:0 0 18px;font-size:15px;line-height:1.55">
          Hi <strong>{customer_name or "there"}</strong>, your payment has gone through.
          Nothing else to do: <strong>{provider_name}</strong> will see you on
          <strong>{when}</strong>.
        </p>

        <div style="background:#ecfdf5;border:1px solid #a7f3d0;border-radius:10px;
                    padding:16px;margin:0 0 20px;text-align:center">
          <span style="color:#065f46;font-size:12px;letter-spacing:1px">PAID BY {method_name.upper()}</span><br>
          <strong style="color:#065f46;font-size:22px">{_money(price, currency)}</strong>
        </div>

        <table style="width:100%;border-collapse:collapse">
          {_row("Reference", reference)}
          {_row("Service", service_name)}
          {_row("Provider", provider_name)}
          {_row("When", when, strong=True)}
          {_row("Paid", _money(price, currency), strong=True)}
          {_row("Method", method_name)}
        </table>

        <p style="margin:20px 0 0;font-size:14px;line-height:1.55;color:#6b7280">
          Keep this as your receipt. Quote {reference} if you need to change anything.
        </p>"""

    _send(to, f"Receipt: {_money(price, currency)} for {service_name} ({reference})",
          _shell("Payment received", f"{reference} · {when}", body,
                 f"{BRAND} · this is your receipt"))


def send_cancellation(
    *,
    to: str,
    provider_name: str,
    reference: str,
    service_name: str,
    customer_name: str,
    starts_at: datetime,
) -> None:
    """Told to the provider, because a freed slot is only useful if they know.

    The customer already saw the cancellation happen on screen, so they are not
    emailed: an email that only repeats what somebody just did themselves is
    noise.
    """
    when = _when(starts_at)

    body = f"""
        <p style="margin:0 0 18px;font-size:15px;line-height:1.55">
          <strong>{provider_name}</strong>, a booking has been cancelled by the customer.
          That time is free again in your diary.
        </p>

        <table style="width:100%;border-collapse:collapse">
          {_row("Reference", reference)}
          {_row("Job", service_name)}
          {_row("Was", when, strong=True)}
          {_row("Customer", customer_name)}
        </table>"""

    _send(to, f"Cancelled: {service_name}, {when} ({reference})",
          _shell("Booking cancelled", f"{reference} · was {when}", body,
                 f"{BRAND} · that time is bookable again"))
