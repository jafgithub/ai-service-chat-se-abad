"""Sending a parking pass to the resident who asked for it.

The client asked for the QR to reach their email, not only their screen, and he
is right: somebody who closes the tab on the way out of the door still has to
open a barrier twenty minutes later.

The code is attached as a PNG rather than embedded as SVG, because Outlook has
never rendered inline SVG and a pass with a hole where the code should be is
worse than no email. It is attached rather than linked so it survives a phone
with no signal at the gate.
"""

import logging
import smtplib
from datetime import datetime
from email.mime.image import MIMEImage
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from app.core.config import settings
from app.services import parking

logger = logging.getLogger("parking")

SMTP_TIMEOUT_SECONDS = 20


def _when(value: datetime | None) -> str:
    return value.strftime("%d %b %Y, %H:%M") if value else ""


def _html(pass_, name: str) -> str:
    greeting = f"Hello {name.split()[0]}," if name else "Hello,"
    return f"""\
<div style="font-family:ui-sans-serif,system-ui,-apple-system,'Segoe UI',Roboto,sans-serif;
            color:#14130F;max-width:520px;margin:0 auto;padding:24px">
  <p style="font-size:11px;letter-spacing:.12em;text-transform:uppercase;
            color:#C25317;font-weight:700;margin:0 0 10px">Parking pass</p>
  <h1 style="font-size:24px;line-height:1.2;margin:0 0 14px">
    {pass_.vehicle_registration}
  </h1>
  <p style="margin:0 0 18px;color:#77726A;font-size:15px">
    {greeting} here is your parking pass. Show this code when you arrive and
    again when you leave.
  </p>

  <table style="width:100%;border-collapse:collapse;font-size:15px;margin:0 0 20px">
    <tr><td style="padding:7px 0;color:#77726A">Vehicle</td>
        <td style="padding:7px 0;text-align:right;font-weight:600">{pass_.vehicle_registration}</td></tr>
    <tr><td style="padding:7px 0;color:#77726A">Valid until</td>
        <td style="padding:7px 0;text-align:right;font-weight:600">{_when(pass_.expires_at)}</td></tr>
  </table>

  <div style="text-align:center;padding:18px;border:1px solid #E9E6E1;border-radius:12px">
    <img src="cid:parkingqr" alt="Your parking pass code" width="220" height="220"
         style="display:block;margin:0 auto">
  </div>

  <p style="margin:18px 0 0;color:#77726A;font-size:13px;line-height:1.6">
    The pass ends when you leave, or at the time above, whichever comes first.
    It is for this vehicle only. If you need another, ask for a new one rather
    than passing this on.
  </p>
</div>"""


def send_pass(pass_, to: str, name: str = "") -> bool:
    """Email the pass. Never raises: the pass exists either way.

    A failure here must not lose the pass the resident has already been given
    on screen, so this reports and returns rather than throwing back into the
    request that issued it.
    """
    if not (settings.SMTP_HOST and settings.SMTP_FROM and to):
        logger.warning("[PARKING] no mail configured; pass %s not emailed", pass_.id)
        return False

    message = MIMEMultipart("related")
    message["Subject"] = f"Your parking pass: {pass_.vehicle_registration}"
    message["From"] = settings.SMTP_FROM
    message["To"] = to

    alternative = MIMEMultipart("alternative")
    alternative.attach(MIMEText(
        f"Your parking pass for {pass_.vehicle_registration} is valid until "
        f"{_when(pass_.expires_at)}. Open this email on your phone to show the code.",
        "plain"))
    alternative.attach(MIMEText(_html(pass_, name), "html"))
    message.attach(alternative)

    image = MIMEImage(parking.qr_png(pass_.token), _subtype="png")
    image.add_header("Content-ID", "<parkingqr>")
    image.add_header("Content-Disposition", "inline", filename="parking-pass.png")
    message.attach(image)

    try:
        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT,
                          timeout=SMTP_TIMEOUT_SECONDS) as server:
            server.ehlo()
            server.starttls()
            if settings.SMTP_USER:
                server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
            server.sendmail(settings.SMTP_FROM, to, message.as_string())
        logger.info("[PARKING] pass %s emailed to %s", pass_.id, to)
        return True
    except Exception:  # noqa: BLE001 - a failed email must not lose the pass
        logger.exception("[PARKING] could not email pass %s", pass_.id)
        return False
