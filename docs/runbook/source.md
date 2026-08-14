# 1. Purpose

Two applications share one codebase. The Product Application is a grocery shop
where a customer searches a catalogue and fills a basket. The Plumbing
Application, called Service Agent, is a booking platform where a customer
describes a problem and books a tradesperson for a time.

The second was built from the first. This document records what carried over,
what was rewritten, what was thrown away, and how to do the same again for a
third application.

It is written to be worked from. Every command was run against the live servers
and every figure was read off them. Where a value is a secret it is shown as a
placeholder and the document names the file on the machine that holds the real
one.

**Product Application:** https://dev.agent.fordev.fun
**Plumbing Application:** https://serviceagent.fordev.fun

---

# 2. Architecture Overview

Both applications are the same four parts in the same arrangement.

| Part | What it is | Where it runs |
|---|---|---|
| Website | Next.js, exported to plain files | served by nginx, no program running |
| API | FastAPI on uvicorn | 127.0.0.1, behind nginx |
| Database | MySQL 8 | the same machine |
| Assistant | Google Gemini | called out over the internet |

nginx is the only thing listening to the internet. It serves the website from
disk and passes anything under `/api/` to the API on a local port. The API is
the only thing that talks to the database. Nothing in the website holds a server
address: it calls `/api/` on whatever host it was opened from, which is why
moving to a new subdomain needs no rebuild.

| | Product Application | Plumbing Application |
|---|---|---|
| Machine | 54.255.130.57, Singapore | 52.25.174.57, Oregon |
| Address | dev.agent.fordev.fun | serviceagent.fordev.fun |
| API port | 8000 | 8100 |
| Service name | `aiorder` | `plumber` |
| Website root | `/var/www/ai-order/frontend-dist` | `/var/www/serviceagent` |
| API folder | `/var/www/ai-order/backend` | `/home/ubuntu/plumber/backend` |
| Database | `aidata2prd_dev` | `plumber_assistant` |

Note the API folders differ. The Product Application lives under `/var/www`, the
Plumbing Application under the home folder. Worth knowing before going looking.

---

# 3. SOP: Spinning Off a New Application

Fifteen steps. Read the whole list first: steps 2 and 3 are the ones people
forget, and both must be done before a certificate will issue.

## 3.1 From Product Snapshot

Start from a copy of the working application rather than an empty machine.

```
git clone git@github.com:jafgithub/ai-service-chat-se-abad.git ~/plumber
```

Or take the files straight off a running machine:

```
scp -i key.pem -r ubuntu@OLD.IP:~/plumber/backend ~/plumber/
```

Copy the code, never the `.env`. That file carries the old machine's database
password, payment keys and admin token, and every one of them should be new.

## 3.2 New Server

In the Lightsail console: **Create instance**, Linux, **Ubuntu 22.04 LTS**, the
2 GB plan or larger. Attach a static IP afterwards, or the address changes when
the machine restarts and the subdomain stops working.

```
chmod 600 ~/Downloads/your-key.pem
ssh -i ~/Downloads/your-key.pem ubuntu@NEW.IP.ADDRESS
```

Open the ports. Lightsail blocks everything but SSH until told otherwise. Under
**Networking**, add HTTP on TCP 80 and HTTPS on TCP 443. Leave 3306 closed: the
API reaches the database on the same machine.

Point the subdomain at it. Add an **A record** in the DNS for `fordev.fun`, the
name being the subdomain and the value the new static IP. Wait for it to answer
before going on, because the certificate step checks that the name really points
at the machine:

```
dig +short yoursubdomain.fordev.fun
```

Then install what is needed:

```
sudo apt update
sudo apt install -y nginx mysql-server ffmpeg git curl
curl -LsSf https://astral.sh/uv/install.sh | sh
```

`ffmpeg` is required. It converts the audio from voice bookings.

## 3.3 Database

```
sudo mysql -e "CREATE DATABASE plumber_assistant CHARACTER SET utf8mb4;"
sudo mysql -e "CREATE USER 'aiorder'@'localhost' IDENTIFIED BY 'CHOOSE_A_STRONG_PASSWORD';"
sudo mysql -e "GRANT ALL ON plumber_assistant.* TO 'aiorder'@'localhost';"
sudo mysql -e "FLUSH PRIVILEGES;"
```

Use `'aiorder'@'localhost'`, not `'aiorder'@'%'`. The second form lets the user
sign in from anywhere on the internet. Section 10.1 explains why that matters.

Move the data across:

```
mysqldump -h 127.0.0.1 -u aiorder -p plumber_assistant > plumber.sql
scp -i key.pem plumber.sql ubuntu@NEW.IP:~
ssh -i key.pem ubuntu@NEW.IP
mysql -h 127.0.0.1 -u aiorder -p plumber_assistant < plumber.sql
```

![The 18 tables, listed from the live database](t01_tables.png)

## 3.4 Application Files

```
cd ~/plumber/backend
uv venv .venv --python 3.12
uv pip install --python .venv/bin/python -r requirements.txt
```

The environment is made by `uv` and has **no `pip` inside it**. Use
`uv pip install --python .venv/bin/python`. `.venv/bin/pip` does not exist.

## 3.5 Environment Configuration

```
nano ~/plumber/backend/.env
chmod 600 ~/plumber/backend/.env
```

The full list is in the appendix. These are the ones that must change on a new
machine:

| Setting | Why |
|---|---|
| `DB_PASSWORD` | The one chosen in 3.3 |
| `ADMIN_TOKEN` | Opens the admin screens. Generate a new one. |
| `SMTP_FROM`, `AI_ORDER_EMAIL` | Sender, and the address that gets copies |
| `STRIPE_SECRET_KEY`, `STRIPE_PUBLISHABLE_KEY`, `STRIPE_WEBHOOK_SECRET` | Card payments |
| `PAYPAL_CLIENT_ID`, `PAYPAL_SECRET`, `PAYPAL_BASE_URL`, `PAYPAL_WEBHOOK_ID` | PayPal |

Carry over unchanged: `GEMINI_API_KEY`, `GEMINI_MODEL`, the `SMTP_HOST` group,
`FFMPEG_PATH`, `FFPROBE_PATH`.

Then apply the database changes:

```
cd ~/plumber/backend
for m in migrations/00*.py; do .venv/bin/python "$m"; done
```

Each checks before it changes anything, so running them twice is safe.

## 3.6 Systemd

```
sudo nano /etc/systemd/system/plumber.service
```

```
[Unit]
Description=Service Assistant API
After=network-online.target mysql.service
Wants=network-online.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/home/ubuntu/plumber/backend
EnvironmentFile=/home/ubuntu/plumber/backend/.env
ExecStart=/home/ubuntu/plumber/backend/.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8100
MemoryMax=700M
Restart=always
RestartSec=3
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
```

```
sudo systemctl daemon-reload
sudo systemctl enable --now plumber
systemctl status plumber
```

![The API running, as reported by the machine itself](t02_service.png)

On a 1 GB machine raise `MemoryMax` or drop it entirely on a larger one. See
section 10.2.

## 3.7 Nginx

```
sudo nano /etc/nginx/sites-available/serviceagent
```

```
server {
    listen 80;
    server_name yoursubdomain.fordev.fun;

    client_max_body_size 20M;
    root /var/www/serviceagent;
    index index.html;

    location /api/ {
        proxy_pass http://127.0.0.1:8100;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-For $remote_addr;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 180s;
    }
    location = /health { proxy_pass http://127.0.0.1:8100/health; }

    location /_next/static/ { add_header Cache-Control "public, max-age=31536000, immutable"; try_files $uri =404; }
    location / { try_files $uri $uri.html $uri/index.html /index.html; add_header Cache-Control "no-store, must-revalidate"; }
}
```

```
sudo mkdir -p /var/www/serviceagent
sudo ln -sf /etc/nginx/sites-available/serviceagent /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

`proxy_read_timeout 180s` matters. Voice bookings run longer than the minute
nginx allows by default and fail halfway through without it.

## 3.8 SSL

```
sudo apt install -y certbot python3-certbot-nginx
sudo certbot --nginx -d yoursubdomain.fordev.fun --agree-tos -m you@example.com --redirect
```

Certbot edits the nginx file itself and installs a renewal timer.

![The certificates held on the machine](t03_certs.png)

**A wildcard certificate instead.** One certificate for every subdomain cannot
be issued the same way: proving ownership of `*.fordev.fun` needs a DNS record
rather than a web page.

```
sudo certbot certonly --manual --preferred-challenges dns \
  -d "*.fordev.fun" -d fordev.fun --agree-tos -m you@example.com
```

Certbot prints a `_acme-challenge.fordev.fun` TXT record. Add it in the DNS,
confirm it answers, then press enter:

```
dig +short TXT _acme-challenge.fordev.fun
```

Point nginx at it:

```
ssl_certificate     /etc/letsencrypt/live/fordev.fun/fullchain.pem;
ssl_certificate_key /etc/letsencrypt/live/fordev.fun/privkey.pem;
```

The trade: a wildcard covers everything, but a manual certificate does not renew
on its own and must be reissued every 90 days unless the DNS provider offers an
automatic plugin. For one or two subdomains, 3.8 is less work and less risk.

## 3.9 Frontend

Built on your own computer. The server has no Node installed.

```
cd frontend
npm install
npm run build:serviceagent
rsync -az --delete out/ ubuntu@NEW.IP:/tmp/fe-stage/
ssh ubuntu@NEW.IP 'sudo rsync -a --delete /tmp/fe-stage/ /var/www/serviceagent/ \
  && sudo chown -R www-data:www-data /var/www/serviceagent/'
```

Use `build:serviceagent`, not `build`. The plain build is made for the older
address where the app sat in a folder called `/plumber`, and its pages look for
their files in the wrong place on a subdomain.

## 3.10 Verification

```
curl -s -o /dev/null -w "home    %{http_code}\n" https://yoursubdomain.fordev.fun/
curl -s -o /dev/null -w "health  %{http_code}\n" https://yoursubdomain.fordev.fun/health
curl -s https://yoursubdomain.fordev.fun/api/v1/services | head -c 200
```

Three 200s and a list of services means website, API and database are all
talking to each other.

![The checks passing on the live server](t04_verify.png)

![The Plumbing Application, running](s01_home.png)

---

# 4. Product Application

## 4.1 Current Architecture

A conversational grocery shop. A shopper types or speaks, the assistant searches
the catalogue of 25,631 products, and results fill a basket. When the catalogue
has nothing, a paid search through SerpApi looks at other shops and those
results can be adopted into the catalogue.

Search does not touch the database. All 25,631 products and their embeddings are
held in memory and rebuilt on a 20 second delay after a change, which is what
makes a search answer in about 200 milliseconds.

## 4.2 Snapshot Components

| Component | Purpose |
|---|---|
| `services/catalog_index.py` | The whole catalogue in memory, searched by vector |
| `services/rag.py` | Turns a phrase into a vector and ranks matches |
| `services/conversation.py`, `intent.py`, `response.py` | Understanding the turn and wording the reply |
| `services/gemini_service.py`, `voice_service.py` | The assistant, speech in and speech out |
| `services/cart_service.py` | The basket, shared by chat, voice and buttons |
| `services/shopping/` | SerpApi search and the store comparison |
| `services/browser/` | Rendering a retailer page inside ours. Built, then switched off. |
| `api/products.py`, `shopping.py`, `orders.py` | Catalogue, outside search, checkout |

## 4.3 Configuration

70 settings. The ones unique to this application are the shopping group:
`SERPAPI_KEY`, `SHOPPING_PROVIDER`, `SHOPPING_COUNTRY`,
`SHOPPING_REFRESH_BUDGET_PER_DAY`, `STORE_COMPARISON_TTL_DAYS`,
`AUTO_ADOPT_SEARCH_RESULTS`, `ADOPTED_ITEM_ID_BASE`, and the six `BROWSE_`
settings for the switched off in-app browser.

## 4.4 Database

26 working tables. The ones that matter: `items` for the catalogue,
`external_offers` and `external_items` for what outside search found, `orders`
and `order_details`, `carts` and `cart_items`, `customers`, `stores`,
`categories`.

Two flows connect it to the client's own system. `items` is pulled one way from
his live database and overwrites anything written locally. `sync_to_remote.py`
pushes customers and orders back, and never items.

---

# 5. Plumbing Application

## 5.1 Architecture

The same shape, a different transaction. A customer describes a problem, the
assistant matches it to a service, shows which providers do it and what they
charge, offers real times from each provider's diary, and books one. Providers
register, set their hours, and see their appointments.

## 5.2 Database Changes

18 tables. Four migrations built them, each safe to re-run:

| Migration | Adds |
|---|---|
| `001_providers_and_accounts` | `providers`, `provider_services`, `provider_availability`, `accounts`, `sessions` |
| `002_provider_time_off` | `provider_time_off` |
| `003_service_requests` | `service_requests` |
| `004_booking_payments` | `jobs.payment_status` |

`items` became `services`, keeping the same columns and gaining
`duration_minutes` and `emergency`. `orders` became `jobs`, `order_details`
became `job_lines`, and `appointments` is new.

## 5.3 New Files

27 new Python files and 33 new frontend files.

| Area | Files |
|---|---|
| Booking | `services/booking_service.py`, `job_service.py`, `booking_emails.py`, `booking_notify.py` |
| Providers | `models/provider.py`, `api/providers.py`, `services/discovery.py` |
| Accounts | `models/account.py`, `api/auth.py`, `services/auth.py`, `api/deps.py`, `services/rate_limit.py` |
| Diary | `models/appointment.py`, `services/calendly/` with four providers |
| Matching | `services/phrase_index.py` |
| Frontend, customer | `booking/BookingFlow.tsx`, `SlotPicker.tsx`, `ProviderCard.tsx`, `BookingReview.tsx`, `BookingConfirmation.tsx`, `ServiceCard.tsx`, `ProviderProfilePanel.tsx` |
| Frontend, provider | `provider/ProviderShell.tsx` and six provider screens |
| Frontend, shared | `auth/AuthPanel.tsx`, `auth/AuthProvider.tsx`, `layout/PageShell.tsx`, `layout/AccountMenu.tsx`, `ui/Field.tsx`, `Sheet.tsx`, `States.tsx`, `HoverCard.tsx`, `ServiceImage.tsx` |

Routes went from 3 to 15: the shop had `/`, `/chat` and `/admin`; the booking
platform adds `/book`, `/bookings`, `/requests`, `/login`, `/register` and six
under `/provider`.

## 5.4 Modified Files

24 of the 41 shared Python files were changed. 17 came across untouched.

| File | Change |
|---|---|
| `core/config.py` | Shopping settings out, booking settings in |
| `main.py` | Routers swapped |
| `services/catalog_index.py` | Reads `services` not `items`, carries `duration_minutes` and `emergency` |
| `services/rag.py`, `intent.py`, `response.py` | Wording and matching moved from products to services |
| `services/cart_service.py` | Kept, holds a service before it becomes a booking |
| `api/chat.py`, `voice.py` | Same machinery, booking vocabulary |
| `api/payments.py` | Pays for a booking rather than an order |

Untouched and carried straight over: `services/media.py`, `email_service.py`,
`ai.py`, `reindex_queue.py`, and the database and schema helpers.

## 5.5 Removed / Deprecated Files

23 Python files and 21 frontend files did not come across.

| Area | Removed |
|---|---|
| Outside search | `services/shopping/` all five files, `offer_store.py`, `adopt_service.py`, `auto_adopt.py` |
| In-app browser | `services/browser/` all four files, `api/browse.py` |
| Shop domain | `api/products.py`, `orders.py`, `partners.py`, `models/product.py`, `order.py`, `order_detail.py`, `external_item.py`, `external_offer.py`, `services/order_service.py` |
| Shop interface | `ProductCard.tsx`, `ProductDetailsModal.tsx`, `CartDrawer.tsx`, `StoreComparison.tsx`, `SourcedPanel.tsx`, `VendorProductModal.tsx`, `StoreBrowserModal.tsx`, `VisitingStoreBar.tsx`, `OrderConfirmation.tsx` and five more |

## 5.6 Configuration Changes

14 settings removed, 14 added. The count matching is a coincidence.

| Added | Meaning |
|---|---|
| `BOOKING_OPEN_HOUR` = 8, `BOOKING_CLOSE_HOUR` = 17 | The working day |
| `BOOKING_WEEKENDS` = false | Saturdays and Sundays offered or not |
| `BOOKING_SLOT_STEP_MINUTES` = 60 | Spacing between offered times |
| `BOOKING_LEAD_HOURS` = 3 | How soon the first slot can be |
| `BOOKING_DAYS_AHEAD` = 14 | How far ahead the diary runs |
| `BOOKING_HOLD_MINUTES` = 10 | How long a slot is held during checkout |
| `PROVIDER_RANKING` = soonest | How providers are ordered |
| `SESSION_DAYS` = 30 | How long a sign-in lasts |
| `CALENDAR_PROVIDER` and four `CALENDLY_` settings | Outside diary, when used |

## 5.7 Provider / Booking Changes

A provider is a business with an address, a travel radius, a set of services with
their own prices, weekly hours and time off. Ranking is by who can come soonest,
which is why `provider_availability` and `provider_time_off` are read on every
search rather than only at booking time.

A booking holds a slot for ten minutes while the customer confirms, so two
people cannot take the same time. Payment is cash, card through Stripe, or
PayPal, and only a signed webhook marks a booking paid.

---

# 6. Product to Plumbing Conversion

## 6.1 What Was Reused

Everything that was not about selling groceries. The assistant, speech in and
out, the in-memory search index, the vector matching, the design system and its
tokens, authentication patterns, the email sender, the payment providers, the
media helper, and the deployment shape of nginx plus a static export plus a
local API.

Of 41 shared backend files, 17 were carried across byte for byte.

## 6.2 What Was Changed

24 shared files. The pattern throughout: the machinery stayed, the vocabulary
and the domain changed. `catalog_index.py` is the clearest example. It still
holds every row in memory and still ranks by dot product, but it reads the
`services` table and carries two extra columns the service card needs.

## 6.3 What Was Added

The booking domain, which has no equivalent in a shop: providers, their diaries,
appointments with holds, accounts for two kinds of user, and a service request
that exists before a job does.

## 6.4 What Was Removed

Everything that assumed goods rather than time: outside product search, the
store comparison, product adoption, the in-app retailer browser, orders and
order lines, and the whole shop interface.

## 6.5 Configuration Mapping

| Product setting | Plumbing equivalent |
|---|---|
| `SHOPPING_PROVIDER`, `SERPAPI_KEY` | none. Services are the client's own. |
| `STORE_COMPARISON_TTL_DAYS` | none |
| `ADOPTED_ITEM_ID_BASE` | none |
| `BROWSE_*` | none |
| none | `BOOKING_*`, seven settings |
| none | `PROVIDER_RANKING` |
| none | `CALENDAR_PROVIDER`, `CALENDLY_*` |
| `TAX_RATE`, `SHOP_NAME`, `GEMINI_*`, `SMTP_*` | unchanged |

---

# 7. Deployment & Rebuild Procedure

Backend, code only. The `.env` and the environment on the server are left alone:

```
rsync -az --delete backend/app/ ubuntu@HOST:/home/ubuntu/plumber/backend/app/
ssh ubuntu@HOST 'sudo systemctl restart plumber'
```

Frontend, staged then moved with sudo because the web root is owned by root:

```
cd frontend && npm run build:serviceagent
rsync -az --delete out/ ubuntu@HOST:/tmp/fe-stage/
ssh ubuntu@HOST 'sudo rsync -a --delete /tmp/fe-stage/ /var/www/serviceagent/ \
  && sudo chown -R www-data:www-data /var/www/serviceagent/'
```

Documents are served from `/var/www/serviceagent-docs/`, deliberately outside the
website root, because the frontend deploy above uses `--delete` and would
otherwise remove them.

---

# 8. Verification / Smoke Tests

```
systemctl is-active plumber
curl -s -o /dev/null -w "%{http_code}\n" https://serviceagent.fordev.fun/health
curl -s https://serviceagent.fordev.fun/api/v1/services | head -c 120
```

Then by hand, because these are the paths that break quietly:

1. Describe a problem in the chat and check services come back with prices.
2. Pick one and check real times appear.
3. Book it and check the confirmation email arrives.
4. Sign in as a provider and check the appointment is on the diary.
5. Speak a request and check the reply is spoken back.

---

# 9. Everyday Operations

| Task | Command |
|---|---|
| Is the API running | `systemctl status plumber` |
| Restart it | `sudo systemctl restart plumber` |
| Watch it | `sudo journalctl -u plumber -f` |
| Errors in the last hour | `sudo journalctl -u plumber --since "1 hour ago" -p err` |
| Reload the web server | `sudo nginx -t && sudo systemctl reload nginx` |
| Check the certificate | `sudo certbot certificates` |
| Test renewal | `sudo certbot renew --dry-run` |
| Back up the database | `mysqldump -u aiorder -p plumber_assistant > backup.sql` |
| Free space | `df -h /` |
| Memory | `free -m` |

| Symptom | Where to look |
|---|---|
| 502 on every page | The API has stopped. `systemctl status plumber`, then the log. |
| 404 on every page | The website root is empty, or nginx points elsewhere. |
| Website loads, nothing works | API not answering. `curl localhost:8100/health` on the machine. |
| Certificate warning | The name in nginx and on the certificate do not match. |
| Voice bookings cut off | `proxy_read_timeout` missing from the nginx file. |
| API restarting repeatedly | Out of memory. See 10.2. |
| Emails not arriving | The `SMTP_` settings. Check the log for the send attempt. |

---

# 10. Known Issues & Security Notes

## 10.1 MySQL Exposure

MySQL on the Plumbing machine listens on every network interface, port 3306 is
reachable from the internet, and the `aiorder` user is permitted to sign in from
any address. Anyone who guesses the password reaches the customer and booking
records. This was confirmed by connecting from outside the machine.

```
sudo nano /etc/mysql/mysql.conf.d/mysqld.cnf     # bind-address = 127.0.0.1
sudo mysql -e "DROP USER 'aiorder'@'%';"
sudo systemctl restart mysql
```

Then remove the 3306 rule in Lightsail Networking. The application connects over
`localhost`, so nothing breaks. Section 3.3 sets a new machine up correctly.

## 10.2 Memory Limit

The API is using 699.8 MB against the 700 MB it is allowed, on a machine with
1 GB in total. It will be killed mid request sooner or later. Either raise
`MemoryMax` and move to a 2 GB machine, or keep the limit and accept the
restarts.

## Also outstanding

- Stripe and PayPal webhook addresses are not registered in those dashboards, so
  a real payment cannot confirm itself yet.
- Backups are manual. The `mysqldump` command above is the whole of it.

---

# 11. Rollback / Recovery

**A bad backend deploy.** The code is in git and the server holds no state of its
own, so put the previous commit back and restart:

```
git checkout <previous-commit> -- backend/app
rsync -az --delete backend/app/ ubuntu@HOST:/home/ubuntu/plumber/backend/app/
ssh ubuntu@HOST 'sudo systemctl restart plumber'
```

**A bad frontend deploy.** Rebuild from the previous commit and deploy again. The
website is plain files, so there is nothing else to undo.

**A bad database change.** Restore the dump:

```
mysql -h 127.0.0.1 -u aiorder -p plumber_assistant < backup.sql
```

Take one first. There is no automatic backup, so the only copy is the one made
by hand before the change.

**The machine is lost.** Section 3 is the recovery procedure. What cannot be
rebuilt from the repository is the database and the `.env`, so those two are what
a backup has to cover.

---

# 12. Appendix

## Database schema

**Plumbing, 18 tables.** Bookings: `service_requests`, `jobs`, `appointments`,
`job_lines`, `payments`. Providers: `providers`, `provider_services`,
`provider_availability`, `provider_time_off`. Catalogue: `services`,
`service_phrases`, `categories`, `stores`. People: `accounts`, `customers`,
`sessions`, `chat_sessions`, `cart_items`. Total size 2.2 MB.

**Product, 26 working tables.** Catalogue and outside search: `items`,
`external_offers`, `external_items`. Trade: `orders`, `order_details`, `carts`,
`cart_items`, `payments`. Reference: `customers`, `stores`, `categories`. The
rest are load and sync logs.

`services` still carries `veg`, `organic` and `stock` from the shop it was built
from. They are unused. The live columns are `price`, `duration_minutes` and
`emergency`.

## Environment variables

70 settings, in `/home/ubuntu/plumber/backend/.env`, permissions 600.

| Group | Settings |
|---|---|
| Application | `APP_NAME` |
| Database | `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASSWORD` |
| Assistant | `LLM_PROVIDER`, `SPEECH_PROVIDER`, `GEMINI_API_KEY`, `GEMINI_MODEL` |
| Audio | `FFMPEG_PATH`, `FFPROBE_PATH` |
| Email | `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_FROM`, `AI_ORDER_EMAIL` |
| Access | `ADMIN_TOKEN`, `SESSION_DAYS` |
| Payments | `PAYMENTS_ENABLED`, `COD_ENABLED`, four `STRIPE_`, four `PAYPAL_` |
| Booking | seven `BOOKING_`, `PROVIDER_RANKING` |
| Diary | `CALENDAR_PROVIDER`, four `CALENDLY_` |

## File change inventory

| | Backend | Frontend |
|---|---|---|
| In the Product Application | 64 | 41 |
| In the Plumbing Application | 68 | 53 |
| Carried over unchanged | 17 | 20 shared |
| Modified | 24 | |
| Added | 27 | 33 |
| Removed | 23 | 21 |

## Git commits

Thirteen commits, oldest last. All on `master` in the Plumbing repository.

| Commit | Date | Subject |
|---|---|---|
| `69240eb` | 14 Aug | The runbook: where the database is and how to build the machine again |
| `ce32243` | 14 Aug | Keep the two build profiles in the repo |
| `13696d8` | 14 Aug | Its own subdomain, so the base path has to be a setting |
| `7b62905` | 12 Aug | Paying for a booking: cash, card and PayPal |
| `ed5661d` | 12 Aug | Booking emails, which had never been sent |
| `c9bcae8` | 12 Aug | Phase E walkthrough, in the format the client reads |
| `ef61b45` | 12 Aug | Phase E: the shop becomes a booking application |
| `2a380ab` | 12 Aug | Phase D: a backend the interface can be written against |
| `2f5b617` | 12 Aug | Phase C: a diary per provider, and the terms of the business |
| `aa8261a` | 12 Aug | Phase B: one authentication system for both sides |
| `0b45198` | 12 Aug | Providers, accounts and sessions: the domain a booking platform needs |
| `751f040` | 12 Aug | Track the backend properly, not as an embedded repository |
| `25cc36b` | 12 Aug | Book a real time against a real diary, in one step |
