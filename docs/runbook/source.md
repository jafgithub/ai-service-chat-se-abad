# What this document is

The Service Assistant runs on one Amazon Lightsail machine. This is the record
of what is on it, where the database lives, and how to build the same thing
again on a new machine with its own subdomain and its own certificate.

Every command here was run against the live server. Nothing is written from
memory. Where a value is a secret it is shown as a placeholder and the document
says which file on the server holds the real one.

**Live now:** https://serviceagent.fordev.fun

---

# The machine

| | |
|---|---|
| Address | 52.25.174.57 |
| Subdomain | serviceagent.fordev.fun |
| Operating system | Ubuntu 22.04.5 LTS, 64 bit |
| Size | 2 processors, 1 GB memory, 58 GB disk, 53 percent used |
| Region | Oregon, US West |
| Sign in | `ssh -i sailagentecsdevkey.pem ubuntu@52.25.174.57` |

Three things run on it. The API, the web server in front of it, and the
database. A fourth service, the render service on port 8800, belongs to the
grocery shop and is not part of this system.

| Program | Version | Listening on |
|---|---|---|
| nginx | 1.18.0 | 80 and 443, open to the internet |
| Service Assistant API | uvicorn, Python 3.12.13 | 127.0.0.1:8100, local only |
| MySQL | 8.0.46 | 3306 |
| Python on the machine | 3.10.12 | the API uses its own 3.12 |
| uv, the installer | 0.12.1 | |

---

# Where everything lives

| Path | What it is |
|---|---|
| `/home/ubuntu/plumber/backend` | The API. Code, settings and its own Python. |
| `/home/ubuntu/plumber/backend/.env` | Every setting and secret. The one file to guard. |
| `/home/ubuntu/plumber/backend/.venv` | The API's own Python 3.12 and its libraries. |
| `/home/ubuntu/plumber/backend/migrations` | Four database change scripts, safe to re-run. |
| `/var/www/serviceagent` | The website. Plain files, no program. |
| `/etc/nginx/sites-available/serviceagent` | The web server settings for this subdomain. |
| `/etc/systemd/system/plumber.service` | What starts the API and restarts it if it stops. |
| `/etc/letsencrypt/live/serviceagent.fordev.fun` | The certificate. |

The API is under `/home/ubuntu`, not under `/var/www`. That is worth knowing
before going looking for it.

---

# The database

| Setting | Value |
|---|---|
| Server | the same machine, 52.25.174.57 |
| Port | 3306 |
| Database name | `plumber_assistant` |
| User | `aiorder` |
| Password | in `/home/ubuntu/plumber/backend/.env`, on the `DB_PASSWORD` line |
| Size | 2.2 MB across 18 tables |

To read the password:

```
ssh -i sailagentecsdevkey.pem ubuntu@52.25.174.57
grep DB_ /home/ubuntu/plumber/backend/.env
```

To connect from the machine itself:

```
mysql -h 127.0.0.1 -u aiorder -p plumber_assistant
```

To connect from your own computer, over an encrypted tunnel rather than across
the open internet:

```
ssh -i sailagentecsdevkey.pem -L 3307:127.0.0.1:3306 ubuntu@52.25.174.57
mysql -h 127.0.0.1 -P 3307 -u aiorder -p plumber_assistant
```

![The 18 tables, listed from the live database](t01_tables.png)

## What the tables hold

| Group | Tables |
|---|---|
| Bookings | `service_requests`, `jobs`, `appointments`, `job_lines`, `payments` |
| Providers | `providers`, `provider_services`, `provider_availability`, `provider_time_off` |
| Catalogue | `services`, `service_phrases`, `categories`, `stores` |
| People and sessions | `accounts`, `customers`, `sessions`, `chat_sessions`, `cart_items` |

`services` still carries a few columns from the grocery system it was built
from, such as `veg` and `organic`. They are unused here. The columns that matter
are `price`, `duration_minutes` and `emergency`.

---

# Building a new machine

Fifteen steps. Read the whole list before starting: steps 2 and 3 are the ones
people forget, and both have to be done before the certificate will issue.

## 1. Create the instance

In the Lightsail console: **Create instance**, Linux, **Ubuntu 22.04 LTS**,
then the 2 GB plan or larger. Attach a static IP afterwards, otherwise the
address changes when the machine restarts and the subdomain stops working.

Download the key file and protect it, or SSH refuses to use it:

```
chmod 600 ~/Downloads/your-key.pem
ssh -i ~/Downloads/your-key.pem ubuntu@NEW.IP.ADDRESS
```

## 2. Open the ports

Lightsail blocks everything except SSH until told otherwise. In **Networking**
on the instance, add:

| Application | Protocol | Port |
|---|---|---|
| HTTP | TCP | 80 |
| HTTPS | TCP | 443 |

Leave 3306 closed. The API talks to the database on the same machine, so the
database never needs to be reachable from outside.

## 3. Point the subdomain at it

In the DNS for `fordev.fun`, add an **A record**: the name is the subdomain, for
example `serviceagent`, and the value is the new static IP.

Wait until this answers with the new address before going further, because the
certificate in step 12 is issued by a service that checks the name really points
at the machine:

```
dig +short yoursubdomain.fordev.fun
```

## 4. Install what is needed

```
sudo apt update
sudo apt install -y nginx mysql-server ffmpeg git curl
curl -LsSf https://astral.sh/uv/install.sh | sh
```

`ffmpeg` is required: it converts the audio from voice bookings.

## 5. Create the database

```
sudo mysql -e "CREATE DATABASE plumber_assistant CHARACTER SET utf8mb4;"
sudo mysql -e "CREATE USER 'aiorder'@'localhost' IDENTIFIED BY 'CHOOSE_A_STRONG_PASSWORD';"
sudo mysql -e "GRANT ALL ON plumber_assistant.* TO 'aiorder'@'localhost';"
sudo mysql -e "FLUSH PRIVILEGES;"
```

Use `'aiorder'@'localhost'`, not `'aiorder'@'%'`. The second form lets the user
sign in from anywhere on the internet, which is how the current machine is set
up and is the one thing about it that should not be copied.

## 6. Copy the data across

On the old machine:

```
mysqldump -h 127.0.0.1 -u aiorder -p plumber_assistant > plumber.sql
```

Bring it to the new one and load it:

```
scp -i key.pem ubuntu@OLD.IP:plumber.sql .
scp -i key.pem plumber.sql ubuntu@NEW.IP:~
ssh -i key.pem ubuntu@NEW.IP
mysql -h 127.0.0.1 -u aiorder -p plumber_assistant < plumber.sql
```

## 7. Copy the application

```
mkdir -p ~/plumber
scp -i key.pem -r ubuntu@OLD.IP:~/plumber/backend ~/plumber/
```

Or from the repository, which is cleaner:

```
git clone git@github.com:jafgithub/ai-service-chat-se-abad.git ~/plumber
```

## 8. Install the API's own Python

```
cd ~/plumber/backend
uv venv .venv --python 3.12
uv pip install --python .venv/bin/python -r requirements.txt
```

The virtual environment is made by `uv` and has no `pip` inside it. Use
`uv pip install --python .venv/bin/python`, not `.venv/bin/pip`, which does not
exist.

## 9. Write the settings file

```
nano ~/plumber/backend/.env
chmod 600 ~/plumber/backend/.env
```

These are the settings. Copy the old file and change the marked lines:

| Setting | Change it? | What it is |
|---|---|---|
| `APP_NAME` | if renaming | Shown in emails |
| `DB_HOST` `DB_PORT` `DB_NAME` `DB_USER` | usually not | `127.0.0.1`, `3306`, `plumber_assistant`, `aiorder` |
| `DB_PASSWORD` | **yes** | The one chosen in step 5 |
| `GEMINI_API_KEY` `GEMINI_MODEL` | carry over | The assistant's language model |
| `LLM_PROVIDER` `SPEECH_PROVIDER` | no | Both `gemini` |
| `FFMPEG_PATH` `FFPROBE_PATH` | no | `/usr/bin/ffmpeg`, `/usr/bin/ffprobe` |
| `SMTP_HOST` `SMTP_PORT` `SMTP_USER` `SMTP_PASSWORD` | carry over | Sends booking emails |
| `SMTP_FROM` `AI_ORDER_EMAIL` | **yes** | Sender and the address that gets copies |
| `ADMIN_TOKEN` | **yes, new one** | Opens the admin screens |
| `STRIPE_SECRET_KEY` `STRIPE_PUBLISHABLE_KEY` `STRIPE_WEBHOOK_SECRET` | **yes** | Card payments |
| `PAYPAL_CLIENT_ID` `PAYPAL_SECRET` `PAYPAL_BASE_URL` `PAYPAL_WEBHOOK_ID` | **yes** | PayPal |
| `PAYMENTS_ENABLED` `COD_ENABLED` | as wanted | Turn payment methods on or off |
| `CALENDAR_PROVIDER` | no | |

The Stripe and PayPal webhook settings are tied to the address that the payment
company calls back. Changing the subdomain means updating them in the Stripe and
PayPal dashboards too, or payments will be taken and never confirmed.

## 10. Apply the database changes

```
cd ~/plumber/backend
for m in migrations/00*.py; do .venv/bin/python "$m"; done
```

Each one checks before it changes anything, so running them twice is safe.

## 11. Make the API start on boot

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

On a machine with 1 GB of memory raise `MemoryMax`, or drop it entirely on a
larger machine. On the current server the API sits at 699.8 MB against a 700 MB
ceiling, which is too close to the line.

## 12. Set up the web server

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

`proxy_read_timeout 180s` matters. Voice bookings can take longer than the
minute nginx allows by default, and without it they fail halfway through.

## 13. Get the certificate

```
sudo apt install -y certbot python3-certbot-nginx
sudo certbot --nginx -d yoursubdomain.fordev.fun --agree-tos -m you@example.com --redirect
```

Certbot edits the nginx file itself, adding the certificate lines and a rule
sending plain HTTP to HTTPS. Renewal is automatic; the timer is already
installed.

![The certificates held on the machine](t03_certs.png)

## A wildcard certificate instead

One certificate covering every subdomain at once saves repeating step 13. It
cannot be issued the same way: proving ownership of `*.fordev.fun` needs a DNS
record rather than a web page, so the domain has to be verified by hand.

```
sudo certbot certonly --manual --preferred-challenges dns \
  -d "*.fordev.fun" -d fordev.fun --agree-tos -m you@example.com
```

Certbot prints a `_acme-challenge.fordev.fun` TXT record. Add it in the DNS,
wait for it to answer, then press enter:

```
dig +short TXT _acme-challenge.fordev.fun
```

Point nginx at the wildcard certificate instead of the per-subdomain one:

```
ssl_certificate     /etc/letsencrypt/live/fordev.fun/fullchain.pem;
ssl_certificate_key /etc/letsencrypt/live/fordev.fun/privkey.pem;
```

The trade: a wildcard covers every subdomain, but a manual certificate does not
renew on its own. It has to be reissued by hand every 90 days unless the DNS
provider offers an automatic plugin. For one or two subdomains, step 13 is less
work and less risk.

## 14. Put the website on

Built on your own computer, because the server has no Node installed:

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

## 15. Check it

```
curl -s -o /dev/null -w "home    %{http_code}\n" https://yoursubdomain.fordev.fun/
curl -s -o /dev/null -w "health  %{http_code}\n" https://yoursubdomain.fordev.fun/health
curl -s https://yoursubdomain.fordev.fun/api/v1/services | head -c 200
```

Three 200s and a list of services means the website, the API and the database
are all working together.

![The checks passing on the live server](t04_verify.png)

![The Service Assistant, running](s01_home.png)

---

# Changing the subdomain later

```
sudo nano /etc/nginx/sites-available/serviceagent    # change server_name, both blocks
sudo certbot --nginx -d thenewname.fordev.fun --agree-tos --redirect
sudo nginx -t && sudo systemctl reload nginx
```

Add the DNS record for the new name first. Nothing in the API or the website
holds the address: the website calls `/api/` on whatever host it was opened
from, so it follows the subdomain without being rebuilt.

The exception is payments. Stripe and PayPal call back to a fixed address, so
their webhook settings have to be changed in those dashboards to match.

---

# Everyday commands

| Task | Command |
|---|---|
| Is the API running | `systemctl status plumber` |
| Restart it | `sudo systemctl restart plumber` |
| Watch what it is doing | `sudo journalctl -u plumber -f` |
| Errors in the last hour | `sudo journalctl -u plumber --since "1 hour ago" -p err` |
| Reload the web server | `sudo nginx -t && sudo systemctl reload nginx` |
| Check the certificate | `sudo certbot certificates` |
| Test renewal without doing it | `sudo certbot renew --dry-run` |
| Back up the database | `mysqldump -u aiorder -p plumber_assistant > backup.sql` |
| Free space | `df -h /` |
| Memory in use | `free -m` |

---

# When something is wrong

| What you see | Where to look |
|---|---|
| 502 on every page | The API has stopped. `systemctl status plumber`, then the log. |
| 404 on every page | `/var/www/serviceagent` is empty, or nginx is pointed elsewhere. |
| Website loads, nothing works | The API is not answering on 8100. Check `curl localhost:8100/health` on the machine. |
| Certificate warning | The name in nginx and the name on the certificate do not match. |
| Voice bookings cut off | `proxy_read_timeout` missing from the nginx file. |
| API restarting over and over | Out of memory. Raise `MemoryMax` or use a larger machine. |
| Emails not arriving | The `SMTP_` settings. Check the log for the send attempt. |

---

# Two things to fix on the current machine

Both are true of the server as it stands today and should not be repeated on a
new one.

**The database is open to the internet.** MySQL is listening on every network
interface, port 3306 is reachable from anywhere, and the `aiorder` user is
allowed to sign in from any address. Anyone who guesses the password reaches the
customer and booking records. Step 5 above sets up a new machine correctly. To
close it on the current one:

```
sudo nano /etc/mysql/mysql.conf.d/mysqld.cnf     # bind-address = 127.0.0.1
sudo mysql -e "DROP USER 'aiorder'@'%';"
sudo systemctl restart mysql
```

Then remove the port 3306 rule in Lightsail Networking. The application connects
over `localhost`, so nothing breaks.

**The API is at its memory ceiling.** It is using 699.8 MB of the 700 MB it is
allowed, on a machine with 1 GB in total. It will be restarted mid request
sooner or later. Either raise the limit and move to a 2 GB machine, or keep the
limit and accept the restarts.

---

# What is not finished

- The Stripe and PayPal webhook addresses are not registered in those
  dashboards, so a real payment cannot confirm itself yet.
- Backups are not automatic. The `mysqldump` command above is the whole of it
  today, and it has to be run by hand.
