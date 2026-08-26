# 1. What this covers

The Service Assistant answers two different kinds of question through one chat
box. "My sink is leaking" is a request for a tradesperson and goes to the
service catalogue. "What are the quiet hours" is a question about the rules and
is answered from the association's own documents. This is a reference for the
second one: how a question reaches the documents, which community's documents
it may be answered from, and what to do when a new association sends its
paperwork.

Two rules run through everything below, and both are enforced by code rather
than by asking a model nicely.

- **An answer is either supported by a passage we retrieved, or it is a
  refusal.** If nothing clears the retrieval floor, the refusal is returned
  without a model being called at all, so the usual failure of a document
  assistant, answering plausibly from its own training, has nowhere to happen.
- **One community is never answered from another's documents.** Not when the
  names are similar, not when the other document is the better match, not when
  we hold nothing for the community that was asked about.

The second rule is why this document exists in the shape it does. On 20 August
a resident question about Three Lakes was answered out of the Serenity Point
rules, because "Lake" sits close to "lakes" in the embedding space and nothing
downstream knew the difference mattered. Rules about somebody's home, delivered
confidently, from a document that does not govern them.

![One process, three engines, two places state lives](d04_architecture.png)

Everything below is a detail of that picture. Four surfaces, one API, and three
engines that decide, answer and issue. The only work done off this machine is
phrasing an answer, hearing a spoken question and sending an email: the
embedding model, the index, the documents and the passes are all here.

# 2. The two ways in

**One door, not two.** Every question about the community documents arrives
through the floating assistant, bottom right of every page. It posts to
`POST /api/v1/docs/ask` and has no service catalogue in front of it, so every
question it receives is already known to be about the rules. There is nothing
to guess.

![The two front doors and the one core](d01_doors.png)

The booking chat books jobs and nothing else: search the catalogue, add to the
basket, pick a time, pay. It does not consult the documents.

**It did, for a day.** The same answers were available inside the booking chat,
and the machinery worked: shape and vocabulary decided whether a message was
about the rules, a community name scoped it, and the answer arrived with its
sources. What it could not fix was the shape of the thing. One box answering
both "what are the quiet hours" and "my sink is blocked" has to guess which is
being asked on every message, and every guess it got wrong was visible to a
resident. Two boxes, each certain what it is for, need no guess at all.

That is why the routing rules that used to be documented here are gone. They
were a good answer to a question that should not have been asked.

**And then it did again, on 26 August, at the client's request.** "I thought all
are going to be chat ai based interactive." The main chat now answers community
questions itself, and the guessing problem that closed it the first time is
answered differently: the conversation remembers what it is about, so it does
not have to decide afresh on every message. Section 15.

# 3. Which community, and how it is chosen

A resident is asked once, on their first question, which association they are
in. Two taps at most, and it is remembered from then on, shown in the panel
header where it can be changed.

Asked once rather than on every question, because the common case is a resident
of one community asking about their own home, and a dropdown in front of every
question taxes exactly that case. Naming a community in the question still wins
over the setting: somebody who types "Lauderdale Lakes tall grass" is asking on
purpose, and the credit under the answer says which community answered.

Only communities the index holds documents for are offered. One that is
declared but empty is recognised in a typed question and refused by name, which
is right there and wrong in a menu: a choice that cannot be answered should not
be on the list.

# 4. Retrieval, and what grounds it

`app/services/docs_index.py` holds the index in memory: 189 chunks at 384
dimensions is about 124 KB of floats, and the whole search is one matrix
multiply. It follows what `catalog_index.py` already does for the service
catalogue, so there is one pattern in this codebase rather than two.

| Step | What happens |
|---|---|
| Load | `app/data/serenity_docs.json` is read once, on first use. Chunks and their vectors are separated, and each community's row numbers are recorded so a scoped search is a slice rather than a scan. |
| Scope | The communities named in the question, or Serenity if none are named. See section 5. |
| Embed | The query only. Through `rag.embed_text`, which is the model the booking search already holds open. |
| Score | Dot product against the rows in scope. Vectors were normalised at build time, so the dot product is the cosine. |
| Floor | `MIN_SCORE = 0.30`. Anything below it is not returned. |
| Answer | The top four passages are the only context the model sees, and it is told to reply `NO_ANSWER` if they do not cover the question. |

**The embedding model is shared on purpose.** The first version of this file
loaded its own `SentenceTransformer`, roughly 90 MB of weights plus torch's
allocator on top. The `plumber` service runs under a `MemoryMax` cgroup limit
and already sits at about 500 MB, so every question failed on the live box with
"embedding model unavailable" while passing in the test suite, because pytest
runs outside the cgroup. The index is built with the same model, so the vectors
are directly comparable.

**Where the floor came from.** Genuine questions score 0.35 to 0.75. Things the
documents say nothing about sit under 0.30. The gap is comfortable and the cost
of being wrong is asymmetric: a refusal is a small annoyance, an invented rule
about someone's home is not.

The floor is not the only guard, and should not be. "What are your opening hours
on Christmas Day" pulls the nuisance rule at about 0.40, because that rule
really does discuss holidays and curfews. It is the nearest thing in the corpus
and retrieval is right to return it. The documents still do not state opening
hours, so refusing that one is the model's job. Raising the floor to swallow it
would cost real answers: "what colour can I paint my house" scores 0.478.

# 5. Community detection and scoping

Every chunk carries a `community` tag. `HOME_COMMUNITY` is `serenity`.

## 5.1 Recognising the name

`COMMUNITIES` in `docs_index.py` is a small registry: a key, a label to say back
to the resident, and the aliases a resident might type. A question's words are
compared against those aliases after both sides are normalised.

Normalisation lowercases, singularises crudely, and drops filler that decorates
a name without identifying it: the, a, of, in, city, town, community,
association, HOA, homeowners, point, village, estates, subdivision,
neighbourhood.

| Typed | Normalised | Resolves to |
|---|---|---|
| Lauderdale Lake community rules | lauderdale lake rule | lauderdale lakes |
| rules at Serenity Point | rule serenity | serenity |
| Three Lake Community quiet hours | three lake quiet hour | three lakes |
| can I fish in the lake | can i fish lake | nobody |

The singular rule is deliberately crude. It only has to make "lakes" and "lake"
the same word, which is the whole of the bug it was written for: the client
typed "Lauderdale Lake", the tag said "lauderdale lakes", and the substring test
that used to live here missed by one letter.

Matching is on **consecutive words**, not substrings, so "Lakeview Drive" cannot
match "lake" and a name only matches where it was actually written.

## 5.2 Scoping before ranking

Naming a community **scopes to** that community. It does not add it to home.

Only the rows belonging to the communities in scope are scored at all, so a
document from anywhere else cannot appear in the results however well it
matches. This is the change that stopped the second failure in the client's
screenshots. The Lauderdale handbook is 93 chunks against Serenity's 96, so
under the old behaviour, which searched both and filtered afterwards, naming
Lauderdale was enough for its ordinances to fill the top four and push the
Serenity answer out.

Naming nothing means Serenity only, which is unchanged. Naming two communities
searches both, which is a fair question: "how do Serenity and Lauderdale Lakes
differ on parking" is a comparison, and mixing is what was asked for.

## 5.3 A community we hold nothing for

If the question names a community that has no chunks in the index, the
assistant says so and stops.

> I do not have the Three Lakes documents, so I cannot answer from them, and I
> will not answer from another community's rules instead.

This is checked before any search runs, and `search()` refuses again if it is
reached directly, so no path through the module can answer a question about one
community out of another's documents. Both front doors return this message
rather than nothing, because in the booking chat "nothing" would send the
resident on to a service search and their question would go unanswered.

![Serenity, Lauderdale Lakes, Three Lakes](d03_scope.png)

Availability is read off the loaded index, never declared. A community becomes
answerable the moment its chunks are in the index, with no code change.

# 6. What is indexed today

208 sections, from twelve documents across six associations.

| Community | Documents | Sections |
|---|---|---|
| Serenity Point | Rules and Regulations, management pack, application package, ARB form, amenities fees, parking pass | 97 |
| Lauderdale Lakes | City of Lauderdale Lakes Code Compliance Handbook | 92 |
| Three Lakes | mailbox guidelines, design review form, direct debit form | 16 |
| Kendall Square | approved colour archive | 1 |
| Valencia | approved colour archive | 1 |
| Enclave At Old Cutler | approved colour archive | 1 |

Lauderdale Lakes is a different city: Serenity Point is in Miami Lakes. Each of
the others is a separate association. All of them are tagged, so a resident
asking about their own bin day is never answered out of another city's
ordinances, and nobody is told to paint their door with another association's
colour.

## 6.1 The colour sheets, and why they have their own chunker

The three colour archives are three columns wide: the surfaces on one line, the
paint codes a few lines below, the colour names below that. Flattened the way
every other document is, they read "Body Trim Accent SW 6106 SW 6076 SW 6119
Kilim Beige Turkish Coffee Antique White", and a resident asking what colour to
paint their body could be told Turkish Coffee.

So the columns are paired by their position on the page before anything else
happens, and the chunk says "Body is SW 6106 Kilim Beige" in as many words. If
the layout ever changes so that no pairs are found, the build stops rather than
guessing, because a wrong pairing here is a wrong instruction about somebody's
home.

## 6.2 What is held but not indexed

| Document | Why |
|---|---|
| Three Lakes Design Standards, 23 pages | a scan, needs OCR and a careful read |
| Serenity occupancy application, 11 pages | a scan |
| Three Lakes site map | a drawing: OCR would not help |
| Three Lakes subsurface drainage | a drawing |

The last two are worth stating plainly: they are pictures. No amount of text
extraction makes a site map answerable, and they belong in the download list
rather than the index.

# 7. Three Lakes, and the OCR dependency

**Three Lakes answers now, but not from everything.** Three of its documents
arrived readable on 21 August and are indexed. Its design standards and covenant
guidelines PDF is still a scan: an image of a page, with no text layer. `pdftotext` returns zero
characters from it. There is nothing to chunk and nothing to embed, so it is not
in the index and questions about it are refused by name.

The same is true of the Serenity occupancy application. Both files sit in
`backend/knowledge/needs-ocr/` rather than in a community folder, which is what
keeps them out of the build.

**What it would take.** The index is built offline, on a laptop, and shipped as
JSON, so this needs no server dependency: only an OCR engine, `tesseract` or
`ocrmypdf`, on whichever machine runs the build script. That is a small install.

**Why it has not been done.** OCR of a scanned covenant document will contain
errors, and those errors would become rules about someone's home. The honest
sequence is to OCR it, read the extracted text against the PDF by eye, correct
it, and only then index it. That is an hour of careful work, not a switch, and
it is worth asking the association for a text PDF first: a document that was
printed and scanned usually still exists as a file somewhere.

Until then the assistant says it does not hold them. That is the correct
behaviour, and it is deliberately not a silent gap.

# 8. Contradictions

The documents disagree with each other in at least five places. The assistant
does not pick a winner. It states both and names the document each came from,
because choosing silently would be inventing a rule.

| Subject | One document says | The other says |
|---|---|---|
| Quiet hours | Rule 18: no loud music from 11:00PM, resuming 9:00AM | Rule 2: nothing after 10pm Sunday to Thursday, midnight Friday and Saturday |
| Lease term | Application requirements: minimum one year | Use restrictions: no lease less than six months |
| Pets | Rules sheet: reads as a blanket ban | Management pack: domestic pets allowed, on a leash, per County ordinance |
| Decision timescales | Stated differently in two places | |
| Site working hours | Stated differently in two places | |

Retrieval has to hand the model both sides or it cannot report the
disagreement, which is why the chunker keeps both documents rather than
deduplicating them, and why a test asserts that both quiet hours rules are
retrieved together for the same question.

These need a decision from the association about which document is
authoritative. Until one is given, showing both is the only honest answer.

# 9. Adding a new community

**The short way is now the admin screen**, section 13: choosing a file registers
the community, indexes the document and has it answering within the minute. What
follows is the offline route, which is still how a large or awkward document
gets in, and which explains what the screen does on your behalf.

Two things, and the second is the one that is easy to forget.

**1. Index the documents.** Put the PDF under `backend/knowledge/<community>/`,
add a line to `MANIFEST` in `scripts/build_doc_index.py` giving its path, title,
short name and community tag, and rerun the builder on a laptop:

```bash
cd backend
python3 scripts/build_doc_index.py
```

The builder extracts text with `pdftotext -layout` into a `.txt` sidecar
committed beside the PDF, chunks by structure, embeds, and writes
`app/data/serenity_docs.json`. It exits with an error if a PDF produces no text,
which is how a scan announces itself.

**2. Declare the community name.** Add a `Community` entry to `COMMUNITIES` in
`app/services/docs_index.py`:

```python
Community("three lakes", "Three Lakes",
          ("three lakes", "three lake", "three lakes community")),
```

**This step is not optional and it is not cosmetic.** A community name that has
never been declared is not recognised as a name at all, so a question about it
is treated as an ordinary question and answered from **Serenity's** documents.
That is the exact failure this whole design exists to prevent, and it comes back
the moment a document is indexed without its name being registered.

The registry is the one hand maintained list in this feature. Everything else,
including whether a community can be answered at all, is read off the index.
Declare the name even when there are no documents yet: that is what turns a
silent wrong answer into "I do not have the Three Lakes documents".

Then run the tests, redeploy the backend, and restart the service. The index is
loaded once at first use, so a restart is required for a new index to be seen.

# 10. Files, and what changed on 20 August

| File | What it does |
|---|---|
| `app/services/docs_index.py` | The index, the community registry, name normalisation, scoping, retrieval |
| `app/api/docs.py` | The prompt, the refusals, small talk, `/docs/ask`, `/docs/suggestions`, and `answer_from_documents()` which both front doors call |
| `app/services/conversation.py` | The routing gate in the booking chat |
| `scripts/build_doc_index.py` | The offline builder: extraction, chunking, embedding |
| `app/data/serenity_docs.json` | The shipped index, 189 chunks, 920 KB |
| `backend/knowledge/` | The source PDFs and their text sidecars |
| `frontend/src/components/chat/HelpWidget.tsx` | The floating panel |
| `frontend/src/components/chat/ChatPage.tsx` | The booking chat, including the results pane |

Changed on 20 August, in response to the client's screenshots:

**`docs_index.py`.** Added the `COMMUNITIES` registry, `named_communities()`,
`unavailable()`, `documents_for()` and word based normalisation, replacing a
substring test that missed "Lauderdale Lake" by one letter. Community rows are
now indexed at load and retrieval scores only the rows in scope, replacing rank
then filter. Naming a community scopes to it instead of adding it to home.

**`api/docs.py`.** A named community with no documents is now refused by name,
in both front doors, before any search runs. An ordinary miss now names the
documents that were actually searched, and lists what is held for that
community, because "I could not find that in the community documents" is
misleading when the question named Lauderdale Lakes and the Lauderdale handbook
is what was searched.

**`conversation.py`.** Added `_DOC_SHAPE` and `_wants_documents()`, so a noun
phrase reaches the documents. A named community's question is answered by the
documents or reported as a miss, never handed to the catalogue. The document
lookup no longer runs twice for a question the documents cannot answer.

**`ChatPage.tsx`.** The results pane no longer describes a documents answer as a
failed search. It said "Nobody on the platform lists anything like that" beside
every correct answer about the rules, which is true of the catalogue and beside
the point of what was asked.

No change to the index format, the chunker, the embedding model, the prompt, or
the grounding rules.

# 11. Testing and verification

**289 automated tests pass.** 55 of them are new, in
`backend/tests/test_community_scope.py`, and they use the real index and the
real embedding model. Nothing in that file calls a language model, so the
retrieval and scoping behaviour is asserted without a network round trip.

```bash
cd backend
.venv/bin/python -m pytest -q --ignore=tests/legacy_shop
```

What the new tests assert:

- Every phrasing of a community name resolves, singular or plural, with or
  without "community" and "point"
- "lake" on its own resolves to nobody, so Serenity's own rules about the lakes
  are not read as a question about Lauderdale Lakes
- A community with no documents is never searched, and the shared core returns
  the refusal itself rather than nothing
- Naming Lauderdale returns only Lauderdale, naming Serenity returns only
  Serenity, naming nobody stays at home, naming both searches both
- Both quiet hours rules are still retrieved together, so the contradiction can
  still be reported
- Eleven community questions reach the documents, ten service requests do not
- The documents named on a miss are the ones actually indexed

The 21 failures in `tests/legacy_shop/` are pre-existing and unrelated. They
fail on `no such table: items`, a schema from the grocery application this
codebase was forked from.

**Checked live, on the deployed server**, through both front doors and through a
real browser:

| Asked | Answered |
|---|---|
| Lauderdale Lake community rules | From the Lauderdale documents, naming the handbook it holds |
| Lauderdale Lakes quiet hours | Lauderdale only, honest miss: the handbook states no hours |
| Serenity parking rules | Serenity only, quotes the parking rule |
| What are the quiet hours? | Both rules, reported as a disagreement |
| What are the rules in Three Lakes? | I do not have the Three Lakes documents |
| Three Lakes community rules | The same |
| I need someone to cut my grass | Garden maintenance, from $55.00 |
| book a plumber | The booking flow |
| I need a boiler repair | Eight services |
| my sink is leaking | Five services |

![The refusal in the booking chat](s01_threelakes.png)

![Service booking, unaffected](s02_booking.png)

# 12. Known limits

Three of these were fixed between 22 and 26 August and are struck through
rather than deleted, because the reasoning that put them here is still worth
reading.

- ~~**Three Lakes needs OCR.**~~ Three of its documents are indexed and
  answering. The two scans are held as downloads instead, section 14.
- ~~**The registry is hand maintained.**~~ It lives in
  `app/data/communities.json` and an upload registers its own community,
  section 13. The trap it warned about is real for anything that writes the
  index directly: a chunk whose community is not in the registry is
  unreachable, and the question falls back to Serenity.
- ~~**A restart is required** after a new index is deployed.~~ A check every ten
  minutes reloads whatever moved, section 16.
- **Lauderdale Lakes has no quiet hours** in its handbook, so that question
  refuses honestly. It reads like a fault and is not one.
- **The contradictions need a decision** from the association about which
  document is authoritative. Section 8.
- **Four associations of six hold almost nothing.** Lauderdale Lakes has its
  code handbook; Kendall Square, Valencia and Enclave At Old Cutler have a
  colour sheet each. A resident of those four can be asked almost nothing, and
  no amount of code fixes it. The admin screen names them, section 13.
- **One code opens every door.** The same admin token that checks a parking pass
  opens orders, payments and document removal, and the gate page keeps it on
  the device that scanned. Before guards use it at a barrier they need a
  credential that only checks passes.

# 13. Uploading a document, without sending it to anybody

The client asked for this on 22 August: "allow Admin to upload the documents".
Before it, every document reached the assistant by being emailed to us and
loaded by hand, which put a day between an association approving a rule and a
resident being able to ask about it.

**Where:** serviceagent.fordev.fun/admin, under Community documents.

![Adding a document, and the associations that hold almost nothing](s03_admin_upload.png)

Choosing a file does all of it in one request: the text comes out, the document
is cut into sections on its own headings, the sections are embedded, and the
index is updated in memory and on disk. The screen reports how many sections it
read. A resident can ask about it a few seconds later. Removing a document is
the same in reverse and takes effect just as quickly.

**A new association is a file and a name.** Choosing "Add a new community" in
the same form registers it, which is what makes the registry data rather than
code. There is no separate screen and no Display Name field: the name typed
here is what residents see in the picker.

**A scan is accepted, not refused.** When no text can be extracted the document
is stored as download only. The assistant will not answer from a picture of a
page, and says so, but the file is on the community's shelf for residents to
open. Four documents are held that way today.

**The warning at the top is not decoration.** Four of the six associations hold
almost nothing, and a resident of those four can be asked almost nothing. It is
shown on the screen that fixes it.

# 14. Taking the document away

Every answer names the documents it came out of, and each one is a row with two
things to do with it: the title opens the PDF in a tab to read, the button saves
it.

![Steps from the document, the form attached, and the association's shelf](s06_steps_and_shelf.png)

Two details in that screenshot are deliberate.

**The steps are steps, not a list of things to book.** When a question is about
a procedure the assistant writes it as a numbered list out of the document, and
the form for that procedure is attached underneath. Numbered lines used to be
drawn as bookable service rows whatever they said, which is what made a resident
ask what "book item 1" was supposed to mean.

**The panel holds the whole shelf.** Every document the association has, for the
length of the conversation, each with its own Download. It used to empty itself
whenever an answer cited a source, which is why the client reported that
downloading had stopped working. It had not; there was simply no button on
screen.

**Asking for a document by name works, and so does pointing at one.** "Send me
the design review form" finds it by title. "Can you download that" resolves
against whatever was last named. Title matching is the only thing that can find
a scan at all, because there is no text inside it to match against.

# 15. Which community, chosen once and remembered

Nothing is asked until it matters. Somebody describing a blocked drain is never
asked which homeowners association they belong to. The first time a question is
about the rules and we do not know where they live, the assistant asks.

![Choosing an association, and what each one holds](s04_community_picker.png)

A search box rather than a row of buttons, because six fit on a screen and fifty
do not. Each row says what that association actually holds, so a resident learns
that Kendall Square has one colour sheet before they spend their question on it
rather than after.

One tap remembers the choice and re-asks the original question against it, so
the answer arrives on the same turn. The choice is shared with the floating
assistant, and it is kept on the session as well as in the browser: the voice
endpoint has no way to send one, so a spoken question used to be answered from
Serenity's rules whoever was asking.

**Naming another association answers from it without changing the default.** A
resident checking a neighbour's rule out of curiosity is told plainly that the
answer came from somewhere other than their own community, and their own
community is still theirs on the next question.

**The conversation stays where it is.** Once it is about the rules, follow-ups
stay with the rules, vague ones included. Only a clear request for a
tradesperson switches, and the switch says so: "Switching to services for this
one." Before this, every message was classified from scratch, so "what about
weekends" could land anywhere.

![The miss, what the association does hold, and somewhere to go next](s05_miss_with_shelf.png)

A question the documents cannot answer is answered honestly, naming what the
association does hold, with the two ways out that stop it being a dead end. It
never falls through to the service catalogue: a tradesperson is not a worse
answer to "what are the quiet hours", it is not an answer to it.

# 16. Keeping itself current

A check runs every ten minutes and rebuilds only what moved. It compares one
count and one timestamp over the services table, and the modification times of
the index and the registry. A pass that finds nothing costs almost nothing, so
it can run all day.

Documents uploaded through the admin screen do not wait for it; they are live
within the same request. The refresher is for every other way the data changes:
a service added straight to the database, an index rebuilt from source, a file
copied onto the server.

`REFRESH_MINUTES=0` switches it off.

# 17. Parking passes

A separate flow, asked for on 22 August, and reachable from the conversation
since 26 August. Saying "visitor parking" or "I need a parking pass" opens the
form without leaving the chat.

![Asking for a pass, in the conversation](s07_parking_in_chat.png)

**A pass belongs to a person.** Signing in is required, and that is the feature
rather than a hurdle: the office has to be able to say whose vehicle is on the
property, so an anonymous pass is not a pass.

The code appears on screen and arrives by email at the same time, so a resident
who closes the tab on the way out of the door can still open a barrier twenty
minutes later, and so it can be forwarded to whoever is driving.

**What the code carries is a token and nothing else.** Scanning it opens a page
that shows nothing at all without the office code, so a photograph of a
windscreen gives away nothing. With the code, whoever is at the gate sees the
vehicle, the resident, the community, who is being visited and the expiry.

**The pass is spent on the way out.** Ending it at the barrier is what stops it
being forwarded on for the rest of the week. Scanning a spent code says
"Already used" and shows when the vehicle left.

Questions *about* parking are not requests for a pass. "What are the parking
rules" and "can I park a boat at my house" go to the documents. Two signals keep
them apart: the documents' own vocabulary always means the rules, and a question
word means the rules only when nothing is being asked for, so "how do I get a
parking pass" still opens the form.

# 18. What changed, 22 to 26 August

| | |
|---|---|
| Registry moved from code into `app/data/communities.json` | 22 Aug |
| Upload, extract, chunk, embed and go live in one request | 22 Aug |
| Scans kept as downloads instead of being refused | 22 Aug |
| Downloads under every answer, and a shelf per community | 23 Aug |
| Parking passes, emailed, with the gate page at `/parking/check` | 23 Aug |
| The ten minute refresher | 24 Aug |
| Parking and documents reachable from the conversation | 26 Aug |
| The community picker, searchable, saying what each holds | 26 Aug |
| The conversation remembers its community and its documents | 26 Aug |

Two faults found by the client's own testing and fixed the same day are worth
recording, because both were invisible in the logs.

**A community that holds nothing offered a mechanic.** A Kendall Square resident
asked for the quiet hours five times in forty six seconds and was answered each
time with "Mobile mechanic call out, from $70.00". The documents found nothing,
the question fell through to the catalogue, and one weak catalogue match was
enough to hide the fact that the association has no rules loaded at all.

**"color" never matched "colour".** He asked to download the colour archive one
message after being told the association holds it, and was asked whether he
meant the rules or a tradesperson. Set intersection does not care that the two
words mean the same thing. Both spellings now normalise onto one form.
