import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime

from app.core.config import settings

# Without this every call inherits the default socket timeout of None, so an
# unresponsive relay blocks the calling thread forever. Orders are committed
# before the email is sent, so a hang here strands a request on an order that
# already exists.
SMTP_TIMEOUT_SECONDS = 20


def _send(to: str, subject: str, html: str) -> None:
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = settings.SMTP_FROM
    msg["To"]      = to
    msg.attach(MIMEText(html, "html"))

    with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=SMTP_TIMEOUT_SECONDS) as server:
        server.ehlo()
        server.starttls()
        server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
        server.sendmail(settings.SMTP_FROM, to, msg.as_string())


def _slot_text(delivery_date, delivery_time: str | None) -> str:
    """Human-readable delivery slot, or an em dash when none was captured."""
    if not delivery_date and not delivery_time:
        return "—"
    parts = []
    if delivery_date:
        parts.append(delivery_date.strftime("%d %b %Y") if hasattr(delivery_date, "strftime") else str(delivery_date))
    if delivery_time:
        parts.append(str(delivery_time))
    return " · ".join(parts)


def send_order_notification(
    customer_name: str,
    customer_email: str,
    customer_phone: str,
    customer_address: str,
    order_id: int,
    items: list[dict],
    total: float,
    subtotal: float | None = None,
    tax: float | None = None,
    shop_name: str = "SmartMarket",
    delivery_date=None,
    delivery_time: str | None = None,
    delivery_notes: str | None = None,
    payment_method: str | None = None,
) -> None:
    # Whoever reads this has to know whether to collect money at the door, so it
    # goes at the very top rather than among the customer details.
    cash_banner = ""
    if payment_method == "cod":
        cash_banner = (
            '<div style="background:#fef3c7;border-left:5px solid #d97706;'
            'padding:14px 18px;margin:0 0 18px">'
            '<p style="margin:0;font-size:16px;color:#78350f">'
            f'<strong>COLLECT ${total:.2f} IN CASH ON DELIVERY</strong></p>'
            '<p style="margin:4px 0 0;font-size:13px;color:#92400e">'
            'This order has not been paid for online.</p></div>'
        )
    elif payment_method in ("stripe", "paypal"):
        label = "card" if payment_method == "stripe" else "PayPal"
        cash_banner = (
            '<div style="background:#ecfdf5;border-left:5px solid #10b981;'
            'padding:12px 18px;margin:0 0 18px">'
            f'<p style="margin:0;font-size:14px;color:#065f46">Already paid online by {label}. '
            'Nothing to collect.</p></div>'
        )

    rows = "".join(
        f"""<tr>
              <td style="padding:8px;border-bottom:1px solid #f0f0f0">{i['product_name']}</td>
              <td style="padding:8px;border-bottom:1px solid #f0f0f0;text-align:center">{i['quantity']} {i['unit']}</td>
              <td style="padding:8px;border-bottom:1px solid #f0f0f0;text-align:right">${i['subtotal']:.2f}</td>
            </tr>"""
        for i in items
    )

    html = f"""
    <div style="font-family:Arial,sans-serif;max-width:600px;margin:auto;color:#333">
      <div style="background:#1e293b;padding:24px;border-radius:12px 12px 0 0">
        <h1 style="color:#f97316;margin:0;font-size:20px">🛒 New Job Received</h1>
        <p style="color:#94a3b8;margin:4px 0 0">Job #{order_id} · {datetime.now().strftime('%d %b %Y, %H:%M')}</p>
      </div>
      <div style="background:#fff;padding:24px;border:1px solid #f0f0f0">
        {cash_banner}
        <h3 style="margin-top:0">Customer Details</h3>
        <table style="width:100%">
          <tr><td style="color:#666;padding:4px 0">Name</td><td><strong>{customer_name}</strong></td></tr>
          <tr><td style="color:#666;padding:4px 0">Email</td><td>{customer_email}</td></tr>
          <tr><td style="color:#666;padding:4px 0">Phone</td><td>{customer_phone or '—'}</td></tr>
          <tr><td style="color:#666;padding:4px 0">Address / Location</td><td>{customer_address or '—'}</td></tr>
          <tr><td style="color:#666;padding:4px 0">Delivery Slot</td><td><strong>{_slot_text(delivery_date, delivery_time)}</strong></td></tr>
          <tr><td style="color:#666;padding:4px 0">Delivery Notes</td><td>{(delivery_notes or '').strip() or '—'}</td></tr>
        </table>
        <h3>Job Items</h3>
        <table style="width:100%;border-collapse:collapse">
          <thead>
            <tr style="background:#f1f5f9">
              <th style="padding:8px;text-align:left">Service</th>
              <th style="padding:8px;text-align:center">Qty</th>
              <th style="padding:8px;text-align:right">Subtotal</th>
            </tr>
          </thead>
          <tbody>{rows}</tbody>
          <tfoot>
            <tr>
              <td colspan="2" style="padding:6px 12px;text-align:right;color:#666">Subtotal</td>
              <td style="padding:6px 12px;text-align:right;color:#666">${(subtotal if subtotal is not None else total):.2f}</td>
            </tr>
            <tr>
              <td colspan="2" style="padding:6px 12px;text-align:right;color:#666">Tax</td>
              <td style="padding:6px 12px;text-align:right;color:#666">${(tax or 0):.2f}</td>
            </tr>
            <tr>
              <td colspan="2" style="padding:12px;text-align:right;font-weight:bold">Job Total</td>
              <td style="padding:12px;text-align:right;font-weight:bold;color:#f97316">${total:.2f}</td>
            </tr>
          </tfoot>
        </table>
      </div>
      <div style="background:#f9f9f9;padding:16px;border-radius:0 0 12px 12px;text-align:center;color:#aaa;font-size:12px">
        {shop_name} AI Ordering System
      </div>
    </div>
    """
    # The subject is what gets read on a phone before anything is opened, so the
    # cash case says so there too.
    subject = (
        f"New order #{order_id} from {customer_name} - COLLECT ${total:.2f} CASH"
        if payment_method == "cod"
        else f"New order #{order_id} from {customer_name}"
    )
    _send(settings.AI_ORDER_EMAIL, subject, html)


def send_customer_confirmation(
    customer_email: str,
    customer_name: str,
    order_id: int,
    items: list[dict],
    total: float,
    subtotal: float | None = None,
    tax: float | None = None,
    shop_name: str = "SmartMarket",
    delivery_date=None,
    delivery_time: str | None = None,
    delivery_notes: str | None = None,
    payment_method: str | None = None,
) -> None:
    # Whoever reads this has to know whether to collect money at the door, so it
    # goes at the very top rather than among the customer details.
    cash_banner = ""
    if payment_method == "cod":
        cash_banner = (
            '<div style="background:#fef3c7;border-left:5px solid #d97706;'
            'padding:14px 18px;margin:0 0 18px">'
            '<p style="margin:0;font-size:16px;color:#78350f">'
            f'<strong>COLLECT ${total:.2f} IN CASH ON DELIVERY</strong></p>'
            '<p style="margin:4px 0 0;font-size:13px;color:#92400e">'
            'This order has not been paid for online.</p></div>'
        )
    elif payment_method in ("stripe", "paypal"):
        label = "card" if payment_method == "stripe" else "PayPal"
        cash_banner = (
            '<div style="background:#ecfdf5;border-left:5px solid #10b981;'
            'padding:12px 18px;margin:0 0 18px">'
            f'<p style="margin:0;font-size:14px;color:#065f46">Already paid online by {label}. '
            'Nothing to collect.</p></div>'
        )

    rows = "".join(
        f"""<tr>
              <td style="padding:8px;border-bottom:1px solid #f0f0f0">{i['product_name']}</td>
              <td style="padding:8px;border-bottom:1px solid #f0f0f0;text-align:center">{i['quantity']} {i['unit']}</td>
              <td style="padding:8px;border-bottom:1px solid #f0f0f0;text-align:right">${i['subtotal']:.2f}</td>
            </tr>"""
        for i in items
    )

    slot_block = ""
    if delivery_date or delivery_time or (delivery_notes or "").strip():
        note_line = ""
        if (delivery_notes or "").strip():
            note_line = (
                '<br><span style="color:#9a3412;font-size:13px">Your notes: </span>'
                f'<span style="color:#7c2d12;font-size:13px">{delivery_notes.strip()}</span>'
            )
        slot_block = f"""
        <div style="background:#fff7ed;border:1px solid #fed7aa;border-radius:8px;padding:12px 16px;margin:16px 0">
          <span style="color:#9a3412;font-size:13px">Scheduled delivery</span><br>
          <strong style="color:#7c2d12;font-size:15px">{_slot_text(delivery_date, delivery_time)}</strong>{note_line}
        </div>"""

    html = f"""
    <div style="font-family:Arial,sans-serif;max-width:600px;margin:auto;color:#333">
      <div style="background:linear-gradient(135deg,#f97316,#ef4444);padding:24px;border-radius:12px 12px 0 0">
        <h1 style="color:#fff;margin:0;font-size:20px">Job Confirmed!</h1>
        <p style="color:rgba(255,255,255,0.85);margin:4px 0 0">Job #{order_id} · {datetime.now().strftime('%d %b %Y, %H:%M')}</p>
      </div>
      <div style="background:#fff;padding:24px;border:1px solid #f0f0f0">
        <p>Hi <strong>{customer_name}</strong>, thank you for your order! We have received it and will process it shortly.</p>
        {slot_block}
        <h3>Job Summary</h3>
        <table style="width:100%;border-collapse:collapse">
          <thead>
            <tr style="background:#f1f5f9">
              <th style="padding:8px;text-align:left">Service</th>
              <th style="padding:8px;text-align:center">Qty</th>
              <th style="padding:8px;text-align:right">Subtotal</th>
            </tr>
          </thead>
          <tbody>{rows}</tbody>
          <tfoot>
            <tr>
              <td colspan="2" style="padding:6px 12px;text-align:right;color:#666">Subtotal</td>
              <td style="padding:6px 12px;text-align:right;color:#666">${(subtotal if subtotal is not None else total):.2f}</td>
            </tr>
            <tr>
              <td colspan="2" style="padding:6px 12px;text-align:right;color:#666">Tax</td>
              <td style="padding:6px 12px;text-align:right;color:#666">${(tax or 0):.2f}</td>
            </tr>
            <tr>
              <td colspan="2" style="padding:12px;text-align:right;font-weight:bold">Total</td>
              <td style="padding:12px;text-align:right;font-weight:bold;color:#f97316">${total:.2f}</td>
            </tr>
          </tfoot>
        </table>
      </div>
      <div style="background:#f9f9f9;padding:16px;border-radius:0 0 12px 12px;text-align:center;color:#aaa;font-size:12px">
        {shop_name} · AI Ordering System
      </div>
    </div>
    """
    _send(customer_email, f"Your order #{order_id} is confirmed!", html)
