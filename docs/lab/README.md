# Break the assistant

The pitch page. Our AI infrastructure under load, as something a person can
drag rather than a claim they have to accept.

Live at `servicez.smartzees.com/docs/lab/`, deployed 29 August 2026.

Single self-contained `index.html`. No build step, no network calls, nothing
that needs the live service to be up.

## What it is arguing

One sentence, generated live under the meters:

> Holding 1.35M a day on 2 cards, because 69% of it never reaches one.

That is the whole pitch, and it is arithmetic rather than a boast. A million
requests a day is about twelve a second. Roughly 60% of those are repeat
questions the cache answers, and 18% of the rest are refused by the gate with no
model called at all, so only about a third reaches a card. Two cards absorb that
several times over.

Turn the cache off and watch the same traffic need six.

## The design, and why it looks like this

Copied deliberately from the reference Abad sent (`asimali.me/lab`), because the
lesson there is right: **the boxes carry no text**. Nodes are 24 by 14 pixels
with the name above them, the columns are labelled along the bottom, and every
word of explanation sits either in the legend under the picture or beside the
control it belongs to. Nothing inside the diagram competes with the numbers,
which are the only things that move.

If you add a node, do not put a caption in it. Add a line to the legend.

## The numbers, and where they come from

| | |
|---|---|
| Pass cost | 900ms fixed plus 115ms per item in the batch |
| Cache hit | 60% by default, adjustable |
| Gate refusal | 18%, the rate measured on real questions |
| Card price | $0.8048 an hour, g6.xlarge in us-west-2 |

The pass model is what makes batching a trade rather than a free win: a bigger
batch buys throughput and spends latency, and the sliders let somebody feel
that. Autoscale is on by default because the page is about how the design
sustains load, and a fixed card count demonstrates nothing.

## The bug that was here, and will come back if you are not careful

Arrivals are Poisson, generated in a loop each tick:

```js
while (S.nextArrival <= S.t) {
  arrive();
  S.nextArrival += -Math.log(1 - Math.random()) / lambda;
}
```

The `+=` is load bearing. Written as `S.nextArrival = S.t + gap` the clock
restarts at each tick, so the loop can only fire once per tick however high the
rate is set. Arrivals were silently capped at ten a second, which is the tick
rate and has nothing to do with traffic, and the page cheerfully reported 600k a
day while claiming to be running at 90 requests a second.

The same mistake was in `../srs/` and `../gpu-simulation/` and was fixed in all
three at once.

## Deploying

```bash
KEY=~/Downloads/sailagentecsdevkey.pem
ssh -i $KEY ubuntu@35.91.251.211 'mkdir -p /tmp/stage-lab'
rsync -az -e "ssh -i $KEY" index.html ubuntu@35.91.251.211:/tmp/stage-lab/
ssh -i $KEY ubuntu@35.91.251.211 \
  'sudo rsync -a --delete /tmp/stage-lab/ /var/www/serviceagent-docs/lab/ \
   && sudo chown -R www-data:www-data /var/www/serviceagent-docs'
```

## Rules

**No em or en dashes.** The client reads them as machine written.

It is a model, and the footer says so. Retrieval, the gate and the fallback
behave as the running system does; the card figures are modelled on an L4. Do
not let it start implying it is a measurement of production, which is one
process on a 1GB box today.
