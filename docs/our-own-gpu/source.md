# 1. The short version

The assistant answers residents from your association's own documents. Almost
all of that work already happens on our own server. One step does not: turning
the passage it found into a readable sentence is done by a language model, and
today that model belongs to Google.

We can now do that step on our own hardware instead. A graphics machine, running
an open model, that an administrator switches on before a meeting and which
switches itself off afterwards.

**Nothing about the answers changes.** The same documents, the same rules, the
same refusals. What changes is whose computer writes the sentence.

# 2. Why anyone would want this

Three reasons, in the order they usually matter.

**You can say it.** "The AI runs on our own hardware" is a different sentence
from "we use Google", and for some audiences it is the one that matters.

**Nothing leaves the building.** When the machine is on, a resident's question
and the passage that answers it are handled entirely by computers we control.

**It costs almost nothing when nobody is using it.** Which is the whole trick,
and section 4 is about it.

# 3. What it looks like to use

![What an administrator actually does](p01_using.png)

Press a button, wait a couple of minutes, flip a switch. That is the entire
operation.

The waiting is not a wait anybody sits through. **Questions asked while the
machine is starting are answered normally**, by Google, and the screen tells you
that is what happened. Residents never see anything different.

# 4. What it costs, and the one number that matters

The machine costs about **eighty cents an hour while it is switched on**, and
nothing at all while it is switched off. Its disk costs about eight dollars a
month either way.

So:

| How it is used | Roughly |
|---|---|
| A few meetings a week | $10 to $15 a month |
| Left running by accident, one month | **$580** |

That gap is the only real risk in the whole idea, and it is entirely a question
of whether somebody remembers to switch it off.

**So nothing depends on anybody remembering.** The machine stops itself after
twenty minutes with no questions. And because a machine that has locked up
cannot switch itself off, a second check runs outside it, on a different
computer entirely, and stops anything that has been left on.

![The machine stops itself, and something else stops it if it cannot](p02_offswitch.png)

# 5. What happens when it is off

This is the part worth understanding, because it is what makes the rest safe to
put in front of people.

If the switch says "our own GPU" but the machine is off, still starting, or has
stopped responding, **the assistant answers anyway**, using Google, exactly as it
does today. A resident notices nothing.

The administration screen does not hide this. It says, in as many words, that
the engine is set to our GPU and that Google is currently answering, and why.

> The reason for that honesty is narrow and practical. A demonstration where
> somebody says "this is running on our own hardware" while it quietly is not is
> a worse outcome than the machine being off, and it is the sort of thing that
> gets found out.

# 6. Try it yourself

There is a working model of all of this on a page you can open on any device.
It runs on a sped up clock, so a twenty minute idle timeout takes twenty seconds
to watch.

Switch engines. Start and stop the machine. Turn the questions up. Then switch to
"our own GPU" while the machine is off and watch the answers keep coming, and the
panel say plainly where they came from.

Nothing on that page touches the real system, and nothing on it is charged for.

# 7. What it does not change

- **It does not change the answers.** Which passage answers a question was
  already decided before any model is involved, by searching your documents. The
  model only writes the sentence.
- **It does not change what happens when we do not know.** If nothing in your
  documents covers the question, no answer is written at all, by either engine.
  That was true before and is true now.
- **It does not affect the grocery system**, which is a separate product on a
  separate server and keeps working exactly as it does today.
- **It does not need to be on.** Everything works with the machine switched off,
  forever, if that is what you want. The switch is an option, not a dependency.
