# The names, and what serves them

Changed 2026-08-30. The `fordev.fun` names are retired but not deleted.

| Product | Name | Box | Certificate |
|---|---|---|---|
| SmartMarket | `marketz.smartzees.com` | 54.254.25.0 | own, Let's Encrypt |
| SmartService | `servicez.smartzees.com` | 35.91.251.211 | own, Let's Encrypt |
| SmartCommunity | `livz.smartzees.com` | 35.91.251.211 fronting 54.188.207.85 | own, Let's Encrypt |
| The front door | `smartzees.com` | 35.91.251.211 | **waiting on DNS** |

## The old names

Both 301 to the new one with the path preserved, so a deep link into the
documents still lands on the same page:

    serviceagent.fordev.fun/docs/srs/  ->  servicez.smartzees.com/docs/srs/
    dev.agent.fordev.fun/docs/...      ->  marketz.smartzees.com/docs/...

They are kept rather than deleted because they are in emails already sent, in
QR codes on windscreens, and in every design document written so far.

`/.well-known/acme-challenge/` is excluded from both redirects. Without that
exclusion Let's Encrypt's challenge would be sent to the other host and these
certificates would stop renewing, silently, about two months later.

## What the applications were told

Not only nginx. An application that writes a URL into an email or a QR code has
to write the new one:

    SmartService   FRONTEND_URL, SITE_BASE_URL   -> https://servicez.smartzees.com
    SmartMarket    FRONTEND_URL, PUBLIC_BASE_URL -> https://marketz.smartzees.com
    SmartCommunity FRONTEND_URL                  -> https://livz.smartzees.com

`IMAGE_BASE_URL` on SmartMarket is deliberately untouched: it is the client's
own image host on a different domain.

## The trap this rename walked into

`sites-enabled/aiorder-dev` on the grocery box was a **regular file, not a
symlink** to `sites-available`. The two had drifted apart, so the first edit
changed a file nginx does not read and the redirect appeared to do nothing.
It is a symlink again now. Check this before editing nginx on any of these
boxes:

    ls -la /etc/nginx/sites-enabled/

## What is left

The apex. `smartzees.com` still resolves to GoDaddy's parking service
(3.33.130.190, 15.197.148.33, which are AWS Global Accelerator addresses that
GoDaddy parks on). The server block, the page and the directory are all in
place and dormant. One record:

    A   @   35.91.251.211   TTL 600

`www` is already a CNAME to the apex and will follow. The certificate is then
one certbot run.
