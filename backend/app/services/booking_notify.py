"""Sending the booking emails, outside the request that caused them.

Run as a FastAPI background task, which is why this opens its own session and
takes an appointment id rather than the objects. The request's session is closed
by `get_db`'s `finally` before background tasks run, so anything handed over
would be detached by the time it was read.

The shop learned this the hard way and the lesson is worth repeating here: the
booking is committed before any of this runs. A slow relay must not hold a
worker open on an appointment that already exists, and a failed send must not
turn a booking that worked into an error on screen. So nothing here raises, and
every outcome is logged, including the ones nobody is watching for.
"""

import logging

from app.core.config import settings
from app.db.database import SessionLocal
from app.models.appointment import Appointment
from app.models.customer import Customer
from app.models.job import Job
from app.models.provider import Provider
from app.services import booking_emails

logger = logging.getLogger("booking")


def _reference(job_id: int) -> str:
    return f"BK-{job_id:05d}"


def _job_name(job: Job) -> str:
    """What was booked, off the job's own line. A booking has exactly one."""
    items = job.items_json or []
    return (items[0].get("name") if items else None) or "Service"


def send_booking_emails(appointment_id: int) -> None:
    """Tell the customer and the provider. Never raises."""
    db = SessionLocal()
    try:
        row = (
            db.query(Appointment, Job)
            .join(Job, Job.id == Appointment.job_id)
            .filter(Appointment.id == appointment_id)
            .first()
        )
        if row is None:
            logger.warning(f"[EMAIL] appointment {appointment_id} vanished before emails were sent")
            return

        appointment, job = row
        customer = db.query(Customer).filter(Customer.id == job.customer_id).first()
        provider = db.query(Provider).filter(Provider.id == appointment.provider_id).first()

        reference = _reference(job.id)
        service_name = _job_name(job)
        duration = int((appointment.ends_at - appointment.starts_at).total_seconds() // 60)
        price = float(job.total_amount or 0)
        currency = job.currency or settings.PAYMENT_CURRENCY
        address = customer.address if customer else None

        if customer and customer.email:
            try:
                booking_emails.send_customer_confirmation(
                    to=customer.email,
                    customer_name=customer.name or "",
                    reference=reference,
                    service_name=service_name,
                    provider_name=provider.business_name if provider else "Your provider",
                    provider_phone=provider.phone if provider else None,
                    starts_at=appointment.starts_at,
                    duration_minutes=duration,
                    price=price,
                    currency=currency,
                    address=address,
                    notes=job.access_notes,
                )
                logger.info(f"[EMAIL] {reference} confirmation sent to the customer")
            except Exception as exc:  # noqa: BLE001 - best effort, already booked
                logger.warning(f"[EMAIL] {reference} customer confirmation failed: {exc}")
        else:
            # Worth a line of its own: it is not a failure, and it is not normal
            # either. Every account has an email, so this means a customer row
            # created before accounts existed.
            logger.warning(f"[EMAIL] {reference} has no customer email, nothing sent to them")

        # The provider's copy goes somewhere even when the business has no email
        # on file, because a job nobody is told about is worse than a misdirected
        # one. The fallback is the address we send from, which somebody reads.
        provider_to = (provider.email if provider and provider.email else booking_emails.FALLBACK_TO)
        if provider and not provider.email:
            logger.warning(
                f"[EMAIL] provider {provider.id} has no email; "
                f"{reference} was sent to {provider_to} instead"
            )
        try:
            booking_emails.send_provider_notification(
                to=provider_to,
                provider_name=provider.business_name if provider else "Provider",
                reference=reference,
                service_name=service_name,
                customer_name=customer.name if customer else "A customer",
                customer_email=customer.email if customer else None,
                customer_phone=customer.phone if customer else None,
                starts_at=appointment.starts_at,
                duration_minutes=duration,
                price=price,
                currency=currency,
                address=address,
                notes=job.access_notes,
            )
            logger.info(f"[EMAIL] {reference} notification sent to the provider")
        except Exception as exc:  # noqa: BLE001
            logger.warning(f"[EMAIL] {reference} provider notification failed: {exc}")

    except Exception as exc:  # noqa: BLE001 - nothing here may reach the caller
        logger.exception(f"[EMAIL] booking emails for appointment {appointment_id} failed: {exc}")
    finally:
        db.close()


def send_cancellation_email(appointment_id: int) -> None:
    """Tell the provider a time has come free. Never raises.

    Only the provider. The customer cancelled it themselves a second ago and
    watched it happen, so an email saying so is noise.
    """
    db = SessionLocal()
    try:
        row = (
            db.query(Appointment, Job)
            .join(Job, Job.id == Appointment.job_id)
            .filter(Appointment.id == appointment_id)
            .first()
        )
        if row is None:
            return

        appointment, job = row
        provider = db.query(Provider).filter(Provider.id == appointment.provider_id).first()
        if provider is None:
            return

        customer = db.query(Customer).filter(Customer.id == job.customer_id).first()
        reference = _reference(job.id)

        try:
            booking_emails.send_cancellation(
                to=provider.email or booking_emails.FALLBACK_TO,
                provider_name=provider.business_name,
                reference=reference,
                service_name=_job_name(job),
                customer_name=customer.name if customer else "A customer",
                starts_at=appointment.starts_at,
            )
            logger.info(f"[EMAIL] {reference} cancellation sent to the provider")
        except Exception as exc:  # noqa: BLE001
            logger.warning(f"[EMAIL] {reference} cancellation email failed: {exc}")

    except Exception as exc:  # noqa: BLE001
        logger.exception(f"[EMAIL] cancellation email for appointment {appointment_id} failed: {exc}")
    finally:
        db.close()
