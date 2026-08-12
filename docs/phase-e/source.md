# What this covers

The Service Assistant now works end to end. A customer describes a problem in their own words, sees who can do the job and what each firm charges, picks a time from that firm's real diary, and holds a booking reference. A business can register, set its own prices and hours, and watch its diary fill.

Every screenshot in this document is the running system on the development server, photographed today.

| | |
|---|---|
| **Live** | dev.agent.fordev.fun/plumber |
| **Services in the catalogue** | 32, across 6 categories |
| **Providers** | 8 seeded businesses, plus those who register |
| **Automated tests** | 154 backend, 68 frontend |
| **Captured** | 12 August 2026 |

![](build/s01_home.png)

The front page. One way in for customers, one for the businesses that do the work.

---

# The customer

![](build/d01_customer.png)

## 1. Describe the problem

No form, no categories to guess at. The words a person would actually use.

![](build/s02_assistant.png)

Each card carries what the card can honestly say: what the service is, roughly what it costs, how long it takes, and whether it is attended out of hours. **The price says "from"**, because it is a guide and the provider sets the real one.

## 2. See who can do it

![](build/s03_providers.png)

Two firms, the same job, different terms. One is an hour at $110 and can come today; the other is an hour and a half at $95 and can come tomorrow. **The order is decided by the server**, soonest first and then cheapest, and the screen says so rather than leaving it a mystery.

## 3. Pick a time

![](build/s04_times.png)

Real slots, built from that provider's working hours, their time off, how long they need for this particular job, and what is already booked. Nothing is worked out in the browser.

The day tabs count what is free. Wednesday shows two times because a third was booked a few minutes earlier.

## 4. Check, then confirm

![](build/s05_review.png)

Everything that is about to happen, on one screen, with the price labelled as the provider's own. Somebody who is not signed in signs in here, in place, and keeps the provider and the time they had already chosen.

## 5. Booked

![](build/s06_confirmed.png)

The reference is the thing a person quotes on the phone, so it gets the room. Payment reads **Not paid yet**, which is true: nothing takes money yet, and a visit that has not been paid for must never look settled.

## Afterwards

![](build/s07_bookings.png)

Upcoming, past and cancelled, with the provider's number ready to ring and a cancel button that only appears when the server would actually allow it.

![](build/s08_requests.png)

What was asked for, kept apart from what was booked, in the customer's own words. A request is recorded whether or not anybody could serve it, which is what lets the office see the gaps.

---

# The provider

![](build/d02_provider.png)

![](build/s09_dashboard.png)

Three numbers, because each one is a way of getting no work. No services listed means nobody can find you. No hours set means nobody can book you. The banner states that a pending application cannot receive bookings, and repeats it on every screen.

![](build/s10_prov_services.png)

The difference between a provider's own terms and the guide figures is shown rather than hidden. **Blocked toilet cleared** reads "Your price"; **Advice appointment** reads "Guide price", because that one has not been set.

![](build/s11_prov_hours.png)

All seven days, always, including the closed ones. A list of only the open days looks the same whether Sunday is deliberately shut or was never set up, and the difference costs a day of bookings.

---

# What it is built from

![](build/d05_stack.png)

---

# Where it runs

![](build/d03_deployment.png)

| | |
|---|---|
| **Pages** | Singapore, 54.255.130.57, served by nginx from `/var/www/plumber` |
| **API** | Oregon, 52.25.174.57, FastAPI on port 8100 under `plumber.service` |
| **Database** | MySQL on the Oregon box |
| **Address** | dev.agent.fordev.fun/plumber, with the API at /plumber-api |
| **Releases** | The two are independent. The pages are a static build; the API is a restart. |

---

# Where the code lives

![](build/d06_structure.png)

---

# Under the bonnet

![](build/d04_request.png)

| Decision | Why |
|---|---|
| The provider is picked before the time | The length of a visit is the provider's, so a slot cannot be sized until one is chosen |
| The customer comes from the sign in token, never the form | Otherwise a booking could be made in somebody else's name |
| One transaction creates the job, the appointment and the link to the request | A half written booking is worse than none |
| The booking answer carries everything | The confirmation screen makes no second call and cannot show a spinner over a booking that already exists |
| Times are read exactly as the server sends them | Converting them would make the picker disagree with the server's own labels |

---

# What was taken out

The shop this grew from is gone from what a customer sees.

| Was | Is now |
|---|---|
| Cart, and a cart icon as the main action | My bookings |
| Checkout | Book appointment |
| Delivery date and delivery time | Appointment date and time |
| Product | Service |
| Store, and other stores | Provider |
| Order | Booking, and separately, a request |
| "Added to your cart" | "Right, that. Here is who can do it, and when." |

The cart and order endpoints still exist on the server, untouched and unused, until payment moves into the booking flow.

---

# Testing

## Automated

| Suite | Count | Result |
|---|---|---|
| Backend, all of it | 154 | Pass |
| Frontend, dates and money | 35 | Pass, under three different timezones |
| Frontend, whole flows against the live server | 33 | Pass |

The flow tests are the interesting ones. They register a customer and a provider, describe a problem, find providers, read a diary, book, look at the booking, cancel it, and check that one customer cannot see or touch another's. They run against the real server, so they catch a field the screen reads and the server does not send.

## By hand, in a browser

| Checked | Result |
|---|---|
| Describe a problem, book it, get a reference | Booked, BK-00012 |
| The request appears, in the customer's words, marked booked | Yes |
| A slot booked once does not come back | Yes, the day dropped from three times to two |
| Sign in during the booking, without losing the choices | Yes |
| Register a business with its own price and slot length | Yes, $64.00 and 30 minutes came through |
| A pending provider is told they cannot be booked | Yes, on every screen |
| A pending provider is not offered to customers | Yes |
| Provider hours, services and diary | All load and save |

## Four faults found and fixed

| Fault | How it showed |
|---|---|
| Voice failed on every request | The reply model named a field that had been renamed everywhere else. Every spoken turn returned an error. |
| A provider could not read their own hours | Two web addresses overlapped, and the wrong one answered. Saving worked, so only the page looked broken. |
| The address without a trailing slash served the grocery shop | Every "home" link in the booking app pointed at it |
| A test passed each morning and failed each afternoon | It assumed one provider opened later than the others, which stops being true after two o'clock |

## Not tested

Stated plainly, because it will be asked.

| | |
|---|---|
| **A phone** | The layout rules are the ones already proven on the grocery assistant, and the new screens follow them, but the browser here would not resize small enough to check. |
| **A real payment** | Nothing takes money yet, by design. |
| **Screen by screen tests of the interface** | The project has no test runner for components. Coverage is the logic underneath plus the whole flows against a live server. |
| **More than one timezone in real use** | The system keeps no timezone per provider. Everything is the server's clock, which is correct today and will not be once providers are spread out. |

---

# What is not done yet

| | |
|---|---|
| **Payment inside the booking** | The screen is shaped for it and says what will happen. The provider is paid directly for now. |
| **The FAQ** | The knowledge document is written; answering from it is the next piece of work. |
| **Providers cancelling** | The server offers no way to, so no button is drawn. |
| **A certificate between the two servers** | The hop is inside an address rule but is still plain HTTP. |
| **Timezones** | Needs a field per provider before this can serve more than one region. |
