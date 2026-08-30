# SOP: adding a community document

Nine short sections for the association and the management office: what to send,
the five second test that decides whether a PDF can be used, what we do at our
end, what is loaded today, and the four contradictions between the documents
that need a decision from the client.

**Live:** https://servicez.smartzees.com/docs/adding-documents/

## Rebuilding

```bash
python3 render_diagrams.py
python3 render_pages.py
python3 render_html.py
```

## Deploying

```bash
KEY=~/Downloads/sailagentecsdevkey.pem
rsync -az --delete -e "ssh -i $KEY" build/web/ ubuntu@35.91.251.211:/tmp/sop-stage/
ssh -i $KEY ubuntu@35.91.251.211 \
  'sudo rsync -a --delete /tmp/sop-stage/ /var/www/serviceagent-docs/adding-documents/ \
   && sudo chown -R www-data:www-data /var/www/serviceagent-docs'
```

**No em or en dashes.** The client reads them as machine written.
