# Inherited shop tests, quarantined

These came from the Shopping Assistant and test a flow this platform no longer
has: a cart, stock reservation, and an order that is paid for at checkout.

They are quarantined rather than deleted because several of them cover
behaviour that still matters and will matter again once payments move into the
booking flow in a later phase: cash versus card, refusing an order when
payments are switched off, and not charging twice.

Deleting them would lose that reasoning. Leaving them in the suite would mean a
red build that everybody learns to ignore, which is worse than either.

Each one needs a decision when payments are wired into booking:

* rewrite against a booking, or
* delete, because the behaviour genuinely went away with the cart

Do not simply rename the symbols until they pass. `test_stock_is_reserved_for_a_cash_order_too`
in particular tests something deliberately removed: a service cannot sell out,
and time is guarded by the slot hold instead.
