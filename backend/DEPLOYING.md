# Deploying, now that the index changes at runtime

`app/data/` is **state, not code**. The document index, the community registry
and the document library are all written by the running application when the
client uploads or removes a document.

**Never rsync `app/` wholesale to the server.** Doing so overwrites the live
index with whatever is in the repository, and everything uploaded since the last
build disappears. I did exactly that on 22 August and lost four communities
until the index was rebuilt.

Deploy code, and leave the data alone:

```bash
KEY=~/Downloads/sailagentecsdevkey.pem
rsync -az --exclude 'data/' -e "ssh -i $KEY" \
  app/ ubuntu@35.91.251.211:/home/ubuntu/plumber/backend/app/
```

To move the index deliberately, in either direction, name the file:

```bash
# the repository's index becomes the server's, replacing anything uploaded
rsync -az -e "ssh -i $KEY" app/data/serenity_docs.json \
  ubuntu@35.91.251.211:/home/ubuntu/plumber/backend/app/data/

# the server's index comes back to the repository, keeping uploads
rsync -az -e "ssh -i $KEY" \
  ubuntu@35.91.251.211:/home/ubuntu/plumber/backend/app/data/serenity_docs.json app/data/
```

After either, restart: the index is read once, at first use.

## Rebuilding from source documents

`scripts/build_doc_index.py` rebuilds from `knowledge/` alone. **It does not know
about uploads**, which live in `uploads/` and are recorded in
`app/data/documents.json`. Rebuilding therefore drops every uploaded document
from the index while leaving it in the library, and the two have to be brought
back into step by re-uploading. Prefer leaving the index alone unless a chunker
has changed.
