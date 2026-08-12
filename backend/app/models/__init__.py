"""Every model must be imported here.

`Base.metadata.create_all` in app/main.py only creates tables for models that
have been imported by the time it runs, and it silently skips anything it has
not seen. A model missing from this list survives only until whichever module
happened to import it stops doing so.
"""

from app.models.service import Service
from app.models.customer import Customer
from app.models.job import Job
from app.models.job_line import JobLine
from app.models.appointment import Appointment
from app.models.payment import Payment
from app.models.chat_session import ChatSession
from app.models.cart_item import CartItem

__all__ = [
    "Service", "Customer", "Job", "JobLine", "Appointment", "Payment",
    "ChatSession", "CartItem",
]
