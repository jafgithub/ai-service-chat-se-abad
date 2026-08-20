# 1. Purpose

Two applications share one codebase. The **Product Application** is a grocery
shop. The **Plumbing Application**, Service Agent, is a booking platform. The
second was built from the first.

This document shows how to run either one, and how to build a third the same
way. Every command was run against the live servers.

Wherever a command appears, the line under it says what you should see when it
worked. If you see something else, that is where to stop and look.

**Product:** https://dev.agent.fordev.fun
**Plumbing:** https://serviceagent.fordev.fun

---

# 2. Architecture Overview

![One machine, four parts](d01_architecture.png)

Four parts, one machine.

| Part | Its job |
|---|---|
| **nginx** | The front door. The only part open to the internet. |
| **The website** | Plain files. No program running. |
| **The application** | Answers anything under `/api/`. Talks to the database. |
| **The database** | MySQL, on the same machine. |

| | Product | Plumbing |
|---|---|---|
| Machine | 54.255.130.57 | 52.25.174.57 |
| Address | dev.agent.fordev.fun | serviceagent.fordev.fun |
| Application port | 8000 | 8100 |
| Service name | `aiorder` | `plumber` |
| Website folder | `/var/www/ai-order/frontend-dist` | `/var/www/serviceagent` |
| Application folder | `/var/www/ai-order/backend` | `/home/ubuntu/plumber/backend` |
| Database | `aidata2prd_dev` | `plumber_assistant` |

The two application folders are in different places. Worth knowing before going
looking for one.

**The community documents.** The plumbing application also answers questions
from the association's own PDFs, in the floating panel and in the booking chat.
That index is built offline and shipped as JSON inside the application folder,
so it needs nothing on the machine and no build step here. How it is routed,
scoped and rebuilt, and the one hand maintained list that has to be updated when
a new community is added, are in its own reference:
https://serviceagent.fordev.fun/docs/community-rag/

---

# 3. SOP: Spinning Off a New Application

![Two ways to get a new machine](d05_routes.png)

**Route A** copies the machine we already run. **Route B** builds one from
nothing. Route A is the normal way and the rest of this section assumes it.
Route B is section 3.2, kept for the day there is no machine left to copy.

---

# 3.1 Route A: from a snapshot of Service Assistant

![Route A: the whole journey](d06_snapshot.png)

A snapshot is a photograph of a whole machine, disk and all, taken while it
runs. Launch a new machine from one and it starts up already finished: nginx,
MySQL, Python, ffmpeg, the code, the settings and the data are all there, and
the application is already running.

The work is not building anything. The work is changing the handful of things
that still say **serviceagent.fordev.fun**.

![What the copy brings with it](d07_carried.png)

## Stage 1: Take the snapshot

Lightsail console, the Service Assistant instance, the **Snapshots** tab,
**Create snapshot**. Name it with the date.

Nothing stops and nobody is logged out. It takes a few minutes because the disk
is about 31 GB.

> You should see: the snapshot appear in the list, state **Available**. Until it
> says that, it cannot be launched from.

## Stage 2: Launch the new machine

On the snapshot, **Create new instance**.

Choose a plan with **at least as much disk as the original**. Lightsail will not
let you go smaller, and the same size or larger is the safe answer. The original
is a 2 GB machine, so pick 2 GB or more.

Then attach a **static IP**, or the address changes on restart and the subdomain
stops working.

**Open the two doors.** Networking, add HTTP on TCP **80** and HTTPS on **443**.
Leave **3306 closed**.

> You should see: the new instance go **Running**, and this, straight away:

```
ssh -i ~/Downloads/your-key.pem ubuntu@NEW.IP.ADDRESS
systemctl is-active plumber nginx mysql
```

Three times `active`. The application is already up, on a machine you have done
nothing to. That is the whole point of route A.

## Stage 3: Give it its own address

In the DNS for `fordev.fun`, add an **A record**: name is the new subdomain,
value is the new static IP.

```
dig +short newname.fordev.fun
```

> You should see: the new IP. Nothing, or the old address, means it has not
> spread yet. Wait. Stage 4 will fail without this.

## Stage 4: Change the five things

Everything here is a copy of ours until you change it.

**1. The name in the front door.**

```
sudo nano /etc/nginx/sites-available/serviceagent
```

Change **every** `server_name serviceagent.fordev.fun;` to the new name. There
are two, one in each block.

```
sudo nginx -t && sudo systemctl reload nginx
```

> You should see: `syntax is ok` and `test is successful`.

**2. The certificate.** The one in the picture is ours and has our name on it,
so a browser will warn until you get your own.

```
sudo certbot --nginx -d newname.fordev.fun --agree-tos -m you@example.com --redirect
```

> You should see: "Congratulations". If it fails, the subdomain is not pointing
> here yet: go back to stage 3.

Then remove ours, which will never renew on this machine:

```
sudo certbot delete --cert-name serviceagent.fordev.fun
```

**3 and 4. The two passwords.** The database password and the admin token are
both ours, and both are in a file another team has seen.

```
sudo mysql -e "ALTER USER 'aiorder'@'localhost' IDENTIFIED BY 'A_NEW_PASSWORD';"
nano /home/ubuntu/plumber/backend/.env      # DB_PASSWORD and ADMIN_TOKEN
sudo systemctl restart plumber
```

While that file is open, the same list from route B applies if any of it is
yours rather than ours: `SMTP_FROM`, `AI_ORDER_EMAIL`, the four `STRIPE_` and
the four `PAYPAL_`.

**5. The data.** The database arrived with our bookings, providers and customers
in it. Two choices.

Keep it, if this is a copy of the same business. Or empty the working records and
keep the catalogue:

```
mysql -u aiorder -p plumber_assistant -e "
  SET FOREIGN_KEY_CHECKS=0;
  TRUNCATE appointments; TRUNCATE jobs; TRUNCATE job_lines; TRUNCATE payments;
  TRUNCATE service_requests; TRUNCATE chat_sessions; TRUNCATE cart_items;
  TRUNCATE sessions; TRUNCATE customers;
  SET FOREIGN_KEY_CHECKS=1;"
```

Take a backup first. `mysqldump -u aiorder -p plumber_assistant > before.sql`.
There is no undo.

## Stage 5: Clear out what came along

The snapshot copied the whole disk, so it copied things that were only ever on
our machine. None of it is running on yours. It is about 8 GB of room.

```
sudo rm -f /etc/nginx/sites-enabled/aiorder-dev
sudo systemctl disable --now aiorder-render
sudo rm -rf /var/www/ai-order
sudo mysql -e "DROP DATABASE aidata2prd_dev;"
sudo nginx -t && sudo systemctl reload nginx
```

Also **check who can log in**. Our machine has four keys on it, and they all
came with the copy:

```
nano ~/.ssh/authorized_keys
```

Leave your own line. Delete the rest.

## Stage 6: The same four checks

```
curl -s -o /dev/null -w "home    %{http_code}\n" https://newname.fordev.fun/
curl -s -o /dev/null -w "health  %{http_code}\n" https://newname.fordev.fun/health
curl -s https://newname.fordev.fun/api/v1/services | head -c 200
```

Two 200s and a list of services. Then the four pictures in section 3.2, stage 6,
show what each check looks like when it is right.

## One thing route A does not fix

The copy inherits both problems in section 10: the database open to the
internet, and the 700 MB memory ceiling. Section 10.1 and 10.2 are worth doing
on the new machine on day one, while nobody is using it yet.

---

# 3.2 Route B: from an empty machine

![Route B: building from an empty machine](d02_journey.png)

Only needed when there is no machine to copy. Six stages, in order. Allow about
an hour.

## Stage 1: Prepare

**Create the machine.** Lightsail console, **Create instance**, Linux,
**Ubuntu 22.04 LTS**, the 2 GB plan or larger. Then attach a **static IP**, or
the address changes on restart and the subdomain stops working.

**Let your key be used.** A key file that anyone can read is refused by SSH.

```
chmod 600 ~/Downloads/your-key.pem
ssh -i ~/Downloads/your-key.pem ubuntu@NEW.IP.ADDRESS
```

> You should see: a prompt ending in `ubuntu@ip-...:~$`. You are on the machine.

**Open the two doors.** Lightsail blocks everything except SSH until you say
otherwise. Under **Networking**, add HTTP on TCP **80** and HTTPS on TCP **443**.

Leave **3306 closed**. That is the database, and it only ever talks to the
application sitting beside it on the same machine.

**Point the subdomain.** In the DNS for `fordev.fun`, add an **A record**: name
is the subdomain, value is the new static IP.

```
dig +short yoursubdomain.fordev.fun
```

> You should see: the new IP address. Nothing, or the old address, means it has
> not spread yet. Wait. Stage 5 will fail without this.

## Stage 2: Install

```
sudo apt update
sudo apt install -y nginx mysql-server ffmpeg git curl
curl -LsSf https://astral.sh/uv/install.sh | sh
```

> You should see: a long list of packages, ending without the word `Error`.

`ffmpeg` is not optional. It converts the audio from voice bookings.

## Stage 3: Data

**Make an empty database and a user for it.**

```
sudo mysql -e "CREATE DATABASE plumber_assistant CHARACTER SET utf8mb4;"
sudo mysql -e "CREATE USER 'aiorder'@'localhost' IDENTIFIED BY 'A_STRONG_PASSWORD';"
sudo mysql -e "GRANT ALL ON plumber_assistant.* TO 'aiorder'@'localhost';"
sudo mysql -e "FLUSH PRIVILEGES;"
```

`'aiorder'@'localhost'` means "only from this machine". Writing `'aiorder'@'%'`
instead means "from anywhere on the internet". Section 10.1 is what happens when
you get that wrong.

**Copy the data over.** On the old machine:

```
mysqldump -h 127.0.0.1 -u aiorder -p plumber_assistant > plumber.sql
```

On the new one:

```
mysql -h 127.0.0.1 -u aiorder -p plumber_assistant < plumber.sql
```

![The database has its tables](t01_tables.png)

## Stage 4: Application

**Bring the code.**

```
git clone git@github.com:jafgithub/ai-service-chat-se-abad.git ~/plumber
```

The code is not in that repository yet. Until it is, copy the folder off a
running machine instead: `rsync -az ubuntu@52.25.174.57:/home/ubuntu/plumber/
~/plumber/`. Route A avoids this question entirely.

**Give it its own Python.**

```
cd ~/plumber/backend
uv venv .venv --python 3.12
uv pip install --python .venv/bin/python -r requirements.txt
```

This environment has **no `pip` inside it**. Always
`uv pip install --python .venv/bin/python`. Typing `.venv/bin/pip` gives
"no such file", and that is expected, not a fault.

**Write the settings.**

```
nano ~/plumber/backend/.env
chmod 600 ~/plumber/backend/.env
```

Copy the old file, then change these and only these:

| Setting | Why |
|---|---|
| `DB_PASSWORD` | The password you chose in stage 3 |
| `ADMIN_TOKEN` | Opens the admin screens. Invent a new one. |
| `SMTP_FROM`, `AI_ORDER_EMAIL` | Who emails come from, and who is copied |
| The four `STRIPE_` | Card payments |
| The four `PAYPAL_` | PayPal |

Everything else carries over untouched.

**Apply the database changes.**

```
for m in migrations/00*.py; do .venv/bin/python "$m"; done
```

> You should see: four short reports. Running this twice is safe, each one
> checks before it changes anything.

## Stage 5: Publish

**Teach the machine to start the application.**

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

[Install]
WantedBy=multi-user.target
```

```
sudo systemctl daemon-reload
sudo systemctl enable --now plumber
```

![The application is running](t02_service.png)

**Set up the front door.**

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
sudo nginx -t && sudo systemctl reload nginx
```

> You should see: `syntax is ok` and `test is successful`. nginx refuses to
> reload a file it cannot understand, so this is safe to run any time.

`proxy_read_timeout 180s` is there for a reason: voice bookings run longer than
the minute nginx allows by default, and without it they stop halfway.

**Get the padlock.**

```
sudo apt install -y certbot python3-certbot-nginx
sudo certbot --nginx -d yoursubdomain.fordev.fun --agree-tos -m you@example.com --redirect
```

> You should see: "Congratulations". Certbot edits the nginx file itself and
> sets up automatic renewal. If it fails, the subdomain is not pointing here
> yet: go back to stage 1.

![The certificate is valid](t03_certs.png)

**One certificate for every subdomain instead.** Possible, but it cannot be
checked through a web page, so you must add a DNS record by hand:

```
sudo certbot certonly --manual --preferred-challenges dns \
  -d "*.fordev.fun" -d fordev.fun --agree-tos -m you@example.com
```

Certbot prints a `_acme-challenge` record. Add it in the DNS, confirm it answers
with `dig +short TXT _acme-challenge.fordev.fun`, then press enter.

The catch: a certificate made this way **does not renew on its own**. It has to
be redone every 90 days. For one or two subdomains the simple command above is
less work and less risk.

**Put the website on.** Built on your own computer, because the server has no
Node installed.

```
cd frontend
npm install
npm run build:serviceagent
rsync -az --delete out/ ubuntu@NEW.IP:/tmp/fe-stage/
ssh ubuntu@NEW.IP 'sudo rsync -a --delete /tmp/fe-stage/ /var/www/serviceagent/ \
  && sudo chown -R www-data:www-data /var/www/serviceagent/'
```

Use `build:serviceagent`, not `build`. The plain build is made for the old
address where the app sat inside a folder, and its pages look in the wrong place
on a subdomain.

## Stage 6: Check

```
curl -s -o /dev/null -w "home    %{http_code}\n" https://yoursubdomain.fordev.fun/
curl -s -o /dev/null -w "health  %{http_code}\n" https://yoursubdomain.fordev.fun/health
curl -s https://yoursubdomain.fordev.fun/api/v1/services | head -c 200
```

![All three parts answer](t04_verify.png)

Two 200s and a list of services means the website, the application and the
database are all talking to each other. You are done.

![The Plumbing Application, running](s01_home.png)

---

# 4. Product Application

A conversational grocery shop. A shopper types or speaks, the assistant searches
25,631 products, results fill a basket. When the catalogue has nothing, a paid
search looks at other shops.

Search never touches the database. The whole catalogue sits in memory, which is
why a search answers in about 200 milliseconds.

**Its own settings:** the shopping group (`SERPAPI_KEY`, `SHOPPING_PROVIDER`,
`STORE_COMPARISON_TTL_DAYS` and four more) and six `BROWSE_` settings for an
in-app retailer browser that was built and then switched off.

**Its database:** 26 working tables. `items` for the catalogue, `orders` and
`order_details` for trade, `external_offers` for what outside search found.

---

# 5. Plumbing Application

Same shape, different transaction. A customer describes a problem, the assistant
matches a service, shows who does it and what they charge, offers real times
from each provider's diary, and books one.

**18 tables.** Four migrations built the new ones:

| Migration | Adds |
|---|---|
| `001_providers_and_accounts` | providers, their services, their hours, accounts, sessions |
| `002_provider_time_off` | holidays and closures |
| `003_service_requests` | the request that exists before a job does |
| `004_booking_payments` | payment status on a job |

`items` became `services`, gaining `duration_minutes` and `emergency`. `orders`
became `jobs`. `appointments` is new.

**Its own settings:** seven `BOOKING_` (working day 8 to 17, no weekends, hourly
slots, 3 hours notice, 14 days ahead, 10 minute hold), `PROVIDER_RANKING`,
`SESSION_DAYS`, and the Calendly group.

**How booking works.** A slot is held for ten minutes while the customer
confirms, so two people cannot take the same time. Payment is cash, card or
PayPal, and only a signed webhook marks a booking paid.

---

# 6. Product to Plumbing Conversion

| | Backend | Frontend |
|---|---|---|
| Carried over untouched | 17 files | 20 shared |
| Changed | 24 | |
| Added | 27 | 33 |
| Removed | 23 | 21 |

**Reused:** the assistant, speech in and out, the in-memory search, the design
system, sign-in, the email sender, payments, and the whole deployment shape.

**Changed:** the machinery stayed, the vocabulary moved from products to
services. `catalog_index.py` still holds every row in memory and still ranks the
same way; it just reads a different table.

**Added:** the booking world, which a shop has no equivalent for: providers,
diaries, appointments with holds, accounts for two kinds of user.

**Removed:** everything that assumed goods rather than time. Outside search,
store comparison, the retailer browser, orders, and the whole shop interface.

Routes went from 3 to 15.

---

# 7. Deployment & Rebuild Procedure

![What a deploy moves, and what it never touches](d03_deploy.png)

There are two paths, and they are different because the website folder belongs
to root while the application folder belongs to you.

## The application

```
rsync -az --delete backend/app/ ubuntu@HOST:/home/ubuntu/plumber/backend/app/
ssh ubuntu@HOST 'sudo systemctl restart plumber'
```

> You should see: nothing from the first command, which means it worked. Then
> check with `systemctl status plumber`.

## The website

Three moves, not one: build on your computer, put the files in a waiting room on
the server, then move them in with `sudo`.

```
cd frontend && npm run build:serviceagent
rsync -az --delete out/ ubuntu@HOST:/tmp/fe-stage/
ssh ubuntu@HOST 'sudo rsync -a --delete /tmp/fe-stage/ /var/www/serviceagent/ \
  && sudo chown -R www-data:www-data /var/www/serviceagent/'
```

The waiting room exists because you cannot write into `/var/www` directly. The
`chown` at the end hands the files to the web server, or nginx cannot read what
you just delivered.

## Two things a deploy never touches

The **settings file** and the **database**. That is deliberate, and it is what
makes section 11 possible: because a deploy only ever replaces code, undoing one
is always safe.

## Documents

These pages live in `/var/www/serviceagent-docs/`, deliberately **outside** the
website folder. The website deploy above uses `--delete`, which empties whatever
it is copying into. Documents kept inside it would be erased on the next deploy.

---

# 8. Verification / Smoke Tests

```
systemctl is-active plumber
curl -s -o /dev/null -w "%{http_code}\n" https://serviceagent.fordev.fun/health
```

Then five things by hand, because these are the paths that fail quietly:

1. Describe a problem in the chat. Services come back with prices.
2. Pick one. Real times appear.
3. Book it. The confirmation email arrives.
4. Sign in as a provider. The appointment is on the diary.
5. Speak a request. The reply is spoken back.

---

# 9. Everyday Operations

![Three things go wrong, and what each looks like](d04_wrong.png)

| Task | Command |
|---|---|
| Is it running | `systemctl status plumber` |
| Restart it | `sudo systemctl restart plumber` |
| Watch it live | `sudo journalctl -u plumber -f` |
| Last fifty lines | `sudo journalctl -u plumber -n 50` |
| Reload nginx | `sudo nginx -t && sudo systemctl reload nginx` |
| Check the certificate | `sudo certbot certificates` |
| Back up the database | `mysqldump -u aiorder -p plumber_assistant > backup.sql` |
| Free space | `df -h /` |

Two more symptoms worth knowing: a **certificate warning** means the name in
nginx and the name on the certificate disagree, and **voice bookings cutting
off** means `proxy_read_timeout` is missing from the nginx file.

---

# 10. Known Issues & Security Notes

Both of these travel in a snapshot. A machine launched by route A arrives with
them, so fix them there too.

## 10.1 The database is open to the internet

MySQL is listening on every network connection, port 3306 is reachable from
anywhere, and the `aiorder` user is allowed in from any address. Confirmed by
connecting from outside the machine. Anyone who guesses the password reaches the
customer and booking records.

```
sudo nano /etc/mysql/mysql.conf.d/mysqld.cnf     # bind-address = 127.0.0.1
sudo mysql -e "DROP USER 'aiorder'@'%';"
sudo systemctl restart mysql
```

Then remove the 3306 rule in Lightsail. Nothing breaks: the application connects
over `localhost`. Stage 3 sets a new machine up correctly.

## 10.2 The application is at its memory ceiling

It is using 699.8 MB of the 700 MB it is allowed, on a machine with 1 GB in
total. It will be stopped mid request sooner or later. Either raise `MemoryMax`
and move to a 2 GB machine, or keep the limit and accept the restarts.

## Also outstanding

- Stripe and PayPal webhook addresses are not registered, so a real payment
  cannot confirm itself yet.
- There is no automatic backup. The `mysqldump` command is the whole of it.

---

# 11. Rollback / Recovery

**A bad deploy.** The code is in git and the server keeps no state of its own,
so put the old code back and restart:

```
git checkout <previous-commit> -- backend/app
rsync -az --delete backend/app/ ubuntu@HOST:/home/ubuntu/plumber/backend/app/
ssh ubuntu@HOST 'sudo systemctl restart plumber'
```

For the website, rebuild from the previous commit and deploy again. It is only
files, so there is nothing else to undo.

**A bad database change.**

```
mysql -h 127.0.0.1 -u aiorder -p plumber_assistant < backup.sql
```

Take the backup **first**. There is no automatic one, so the only copy is the
one you made by hand before the change.

**The machine is lost.** Launch a new one from the most recent snapshot, section
3.1. It comes back with the database and the settings file as they were on the
day the snapshot was taken, which is the strongest reason to take one on a
schedule. Everything after that day has to come from a `mysqldump`.

Section 3.2 is the recovery procedure only if there is no snapshot either.

---

# 12. Appendix

**Database, plumbing, 18 tables.** Bookings: `service_requests`, `jobs`,
`appointments`, `job_lines`, `payments`. Providers: `providers`,
`provider_services`, `provider_availability`, `provider_time_off`. Catalogue:
`services`, `service_phrases`, `categories`, `stores`. People: `accounts`,
`customers`, `sessions`, `chat_sessions`, `cart_items`. Total 2.2 MB.

`services` still carries `veg`, `organic` and `stock` from the shop it was built
from. Unused. The live ones are `price`, `duration_minutes`, `emergency`.

**Settings, 70 in all,** in `/home/ubuntu/plumber/backend/.env`, permissions
600: application, database, assistant, audio, email, access, payments, booking,
diary.

**Connecting to the database from your own computer.** Over a tunnel, not across
the open internet:

```
ssh -i your-key.pem -L 3307:127.0.0.1:3306 ubuntu@52.25.174.57
mysql -h 127.0.0.1 -P 3307 -u aiorder -p plumber_assistant
```

The password is on the `DB_PASSWORD` line of the settings file.

**Git.** Thirteen commits on `master`, from `25cc36b` (booking against a real
diary) through the five build phases to `69240eb` (this document).
