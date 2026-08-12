from sqlalchemy import Column, BigInteger, String, Text, Numeric, JSON, Boolean, Integer, DateTime
from app.db.database import Base


class Service(Base):
    """One thing the firm does: a drain unblocked, a boiler serviced.

    Same shape as a shop's product list, deliberately. A service has a name, a
    description, a price and a category, and the matching engine does not care
    whether it is selling tinned tomatoes or a leak repair. What differs is
    `duration_minutes`, which decides how long a slot has to be, and that has no
    equivalent in a shop.
    """

    __tablename__ = "services"

    id             = Column(BigInteger, primary_key=True)
    name           = Column(String(255))
    description    = Column(Text)
    image          = Column(String(255))           # filename only
    category_id    = Column(BigInteger)
    price          = Column(Numeric(24, 2), nullable=False, default=0)
    tax            = Column(Numeric(24, 2), nullable=False, default=0)
    tax_type       = Column(String(20), default="percent")
    discount       = Column(Numeric(24, 2), default=0)
    discount_type  = Column(String(20), default="percent")
    veg            = Column(Boolean, default=False)
    status         = Column(Boolean, nullable=False, default=True)
    store_id       = Column(BigInteger)
    stock          = Column(Integer, default=0)   # unused here; kept so the shared code paths do not fork
    unit_id        = Column(BigInteger)
    slug           = Column(String(255))
    recommended    = Column(Boolean, default=False)
    organic        = Column(Boolean, default=False)
    order_count    = Column(Integer, default=0)
    avg_rating     = Column(Numeric(16, 14), default=0)
    rating_count   = Column(Integer, default=0)
    # How long a visit for this service usually takes. Decides the length of the
    # slot offered, so a tap washer does not book the same hour as a new boiler.
    duration_minutes = Column(Integer, default=60)
    # True for services the firm will attend out of hours. The assistant routes
    # these differently, because an emergency does not wait for Tuesday.
    emergency      = Column(Boolean, default=False)

    # The product's own page at the store that actually sells it, e.g.
    # "https://www.walmart.com/ip/Mina-Mild-Harissa-Sauce-10-oz/773599552".
    # Filled for products we source from outside our catalog; for the client's
    # own 25,631 products it is filled by his import process and is NULL until
    # then, so anything reading it has to cope with an empty value.
    #
    # Local only: sync_to_remote keeps just the columns both databases share,
    # so this is dropped on the way out, exactly like orders.payment_method.
    vendor_prod_prod_page_url = Column(String(1024))
    created_at     = Column(DateTime)
    updated_at     = Column(DateTime)
    item_vector = Column(JSON)                  # 384-dim embedding (our addition)

    # NOT NULL in the client's schema with no default, and absent from this
    # model until we started creating rows rather than only importing them.
    # Reading a row never needed them; inserting one does, and the server runs
    # with STRICT_TRANS_TABLES so an omission is an error, not a silent zero.
    # Every one of the 25,631 imported rows carries module_id 9 and is_approved 1.
    module_id   = Column(BigInteger)
    is_approved = Column(Boolean, default=True)

    # ── virtual helpers so the rest of the app works unchanged ──────────────
    @property
    def price_per_unit(self):
        return self.price

    @property
    def is_active(self):
        return bool(self.status)

    @property
    def image_url(self):
        return self.image

    @property
    def category(self):
        # populated by rag/products via join helper; falls back to str(category_id)
        return getattr(self, "_category_name", None) or str(self.category_id or "")

    @property
    def unit(self):
        return getattr(self, "_unit_name", None) or "unit"

    @property
    def owner_email(self):
        return getattr(self, "_owner_email", None)
