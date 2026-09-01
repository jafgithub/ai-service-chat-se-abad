# Deploying SmartService

Live at **servicez.smartzees.com**, on **35.91.251.211**. This machine also
serves the landing page and the written documents.

Full detail, including what every file is for:
<https://servicez.smartzees.com/docs/deployment/>

    ssh -i ~/Downloads/sailagentecsdevkey.pem ubuntu@35.91.251.211

## Backend

FastAPI at `/home/ubuntu/plumber/backend`, unit `plumber`, port 8100.

    rsync -az --exclude "__pycache__" --exclude ".venv" --exclude ".env" \
      backend/app/ ubuntu@35.91.251.211:/home/ubuntu/plumber/backend/app/
    ssh ubuntu@35.91.251.211 "sudo systemctl restart plumber"

## Frontend

    export PATH="$HOME/.local/node/bin:$PATH"
    cd frontend && npm run build:serviceagent
    rsync -az --delete out/ ubuntu@35.91.251.211:/home/ubuntu/deploy-serviceagent/
    ssh ubuntu@35.91.251.211 \
      "sudo rsync -a --delete /home/ubuntu/deploy-serviceagent/ /var/www/serviceagent/"

`build:serviceagent`, not `build`: it sets an empty base path and an empty API
url, because the app sits at the root of its own subdomain and the API is same
origin.

## Documents

Served from `/var/www/serviceagent-docs`, outside the site root on purpose. The
frontend deploy above uses `--delete` and would otherwise remove them.

    python3 docs/_house/hub.py
    rsync -az docs/<name>/ ubuntu@35.91.251.211:/home/ubuntu/deploy-docs/<name>/
    ssh ubuntu@35.91.251.211 \
      "sudo rsync -a /home/ubuntu/deploy-docs/ /var/www/serviceagent-docs/"

## This machine is special

It owns the **engine switch for the whole platform**. The other two products
read it from here and never write it, and only this admin panel can start and
stop the model machine. That needs `boto3` in the venv and AWS keys in `.env`.

`plumber-sync` runs here and **must not run anywhere else**: it pushes rows into
the client's live database.

Never build on the server. Under 2GB of memory, a Next.js build takes it down.
