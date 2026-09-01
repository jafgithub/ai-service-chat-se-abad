# The lab

Two views of the same design, and the difference between them is the whole
point of keeping both.

**Live** reads the three agents' `/api/v1/ai/trace` endpoints and draws real
requests: the stages each one went through, the milliseconds each stage took,
and which engine wrote the answer. Every number is measured. When nothing has
been asked recently a lane says so rather than filling the space.

**Modelled** is the original load simulator, unchanged. Every number in it is
calculated and none of it touches the running service. It is behind its own
tab and labelled on the page, because a modelled figure mistaken for a measured
one is worse than no figure.

## The bit that is not in this repository

The page is served from servicez, and the other two agents are on other names.
A browser fetching them directly fails the cross origin check silently, which
is the worst way for a dashboard to be wrong. So nginx on the service box
proxies them under the same origin:

    location /docs/lab-api/market/api/v1/ai/     -> marketz.smartzees.com
    location /docs/lab-api/community/api/v1/ai/  -> livz.smartzees.com

Those two blocks live in `/etc/nginx/snippets/serviceagent-locations.conf` on
35.91.251.211, with a backup alongside at `.bak-lab`. They are deliberately
narrow: only the `ai` endpoints are reachable through them, which is a listing
of timings and nothing else. If the lanes for Market and Community ever go
silent after a server rebuild, this is the first thing to check.

## Deploying

    rsync -az lab/ ubuntu@35.91.251.211:/home/ubuntu/deploy-docs/lab/
    ssh ... 'sudo rsync -a /home/ubuntu/deploy-docs/lab/ /var/www/serviceagent-docs/lab/'
