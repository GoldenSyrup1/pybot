"""A line that asks to be reminded of the thing they told us about, and not about the world.

"my boiler keeps losing pressure" then "what was wrong with my boiler again" is the person
going back over what they said: the past tense and the "again" are the reminder, and the answer
they want is their own line. Read as a question about the world it is a fault to diagnose, so
the answers lane took it and handed back the flow-temperature card, and the store - which had
the boiler on file - was never asked.

The reading is a shape, not a phrase. What makes a line this ask is all three of:

  * a past-tense ask ("what was", "what did", "remind me what was"),
  * an ask about a thing's state rather than its price or its recipe ("wrong", "up", "the
    problem", "happening", "keep doing"), and
  * a thing named after "with" - "with my boiler", "with the car", "with it" - where the thing
    is one they really did say something about earlier. A boiler they only heard the bot
    mention is not theirs to be reminded of, and a present-tense "what's wrong with my boiler"
    is a fault to diagnose, not a reminder: only the past tense and the reminding frames below
    (with "again", with "remind me") make it about the chat.

A pronoun is the thing the understanding engine resolved it to (`memory["understood"]["ref"]`),
which is how "what was wrong with it again" reaches the boiler and not the last line said.
"""
import re

from . import recent
from .topics import content, forms, stem

# The thing, named after "with": "my boiler", "the car", "our kitchen". Three words at most, so
# a whole clause after "with" is not the thing ("what was wrong with the way they spoke to me").
WITH_THE_THING = re.compile(
    r"\bwith\s+(?:((?:my|our|the)\s+[a-z][a-z'\-]*(?:\s+[a-z][a-z'\-]*){0,2})|"
    r"(it|that|this|them|those))\b", re.I)
# The words the thing carries that say nothing about which thing it is, or that point at the
# remembering rather than the thing: "with the boiler again" names the boiler.
TRAILING = frozenset("""again before earlier already then yesterday today please so far
until up now one ones thing things stuff lot""".split())
EMPTY = frozenset("one ones thing things stuff lot".split())
# The ask is about the state of the thing. "what was wrong with", "what was up with", "what was
# the problem with", "what was happening with", "what the boiler kept doing". A price, a colour
# or a recipe is a question about the world and is left to the entries.
STATE_ASKS = re.compile(
    r"\b(?:wrong|up|the\s+(?:problem|matter|issue|fault|trouble|deal)|happen\w*|going\s+on|"
    r"doing|keep\s+doing|kept\s+doing|said\s+about)\b", re.I)
# The ask in the tense of the telling. "was"/"were"/"did"/"has" and not "is"/"does": a fault
# asked about in the present ("what's wrong with my boiler") is a diagnosis, which the answers
# lane answers better than a quote of the line does.
IN_THE_PAST = re.compile(
    r"^(?:and |so |but |also |ok |okay )?(?:what|whats|which)\s+(?:was|were|did|has|have|had)\b"
    r"|\b(?:what|whats)\s+(?:was|were)\b", re.I)
# The words that make it a reminder rather than a first question. "again" is how people ask for
# a thing a second time, and the reminder is what they want when they cannot place it.
AGAIN = re.compile(r"\b(?:again|before|earlier|remind me|remind me again|"
                   r"(?:cant|can not|cannot|dont|do not) remember|"
                   r"what did i say|what did i tell you)\b", re.I)
REMINDING = re.compile(r"\b(?:remind me|(?:cant|can not|cannot|dont|do not) remember)\b", re.I)
# The thing done, rather than its state: "what did the boiler keep doing again". The thing is
# named straight after "did", so this shape has no "with" in it.
WHAT_IT_DID = re.compile(
    r"\b(?:what|whats)\s+(?:did|does|has|have)\s+((?:my|our|the)\s+[a-z][a-z'\-]*"
    r"(?:\s+[a-z][a-z'\-]*){0,2}?)\s+(?:keep\s+|kept\s+)?(?:doing|do|say|saying)\b", re.I)


def _trim(words):
    """The named thing without the words that point at the remembering rather than the thing."""
    kept = [word for word in str(words or "").split() if word.lower() not in TRAILING]
    return " ".join(kept).strip(" .,!?")


def _said_before(thing, memory):
    """True when one of their own earlier lines names this thing.

    The guard is what keeps the reading to the chat: a boiler the bot mentioned, or one named
    for the first time in the ask itself ("my boiler is making a noise again" / "what was wrong
    with my boiler again" in the same breath), has no line of theirs to be reminded of.
    """
    words = [word for word in content(thing) if word not in EMPTY]
    if not words:
        return False
    for turn in recent(memory, 12):
        line = turn.get("user") if isinstance(turn, dict) else None
        if not line:
            continue
        said = set(content(line))
        if all(any(word == seen or forms(word) & forms(seen) or stem(word) == stem(seen)
                   for seen in said) for word in words):
            return True
    return False


def the_thing(text, memory=None):
    """The thing a reminder is about ("my boiler", "the car", "it"), or None when the line is
    not a reminder about a thing they named.

    The reading is shared by the gate that says the line is about the chat (the store's
    `_about_this_chat`) and the reply that quotes the line (`_recall_reply`), so the two cannot
    disagree about which lines are reminders.
    """
    line = " ".join(str(text or "").lower().split())
    if not line:
        return None
    if not STATE_ASKS.search(line):
        return None
    if not (IN_THE_PAST.search(line) or REMINDING.search(line)):
        return None
    # "again", "remind me", "i can't remember": the words that ask for a thing a second time.
    # Without one of them the line is the first question about the thing, and a first question
    # about a fault is the answers lane's turn.
    if not AGAIN.search(line):
        return None
    thing = ""
    named = WITH_THE_THING.search(line)
    if named:
        if named.group(1):
            # "again" and the other pointing words are the ask's, not part of the thing, and
            # they would be searched for in the person's lines as if they were.
            thing = _trim(named.group(1))
        else:
            # A pronoun is the thing the understanding engine resolved: "what was wrong with it
            # again" after the boiler is about the boiler.
            thing = _resolved(named.group(2), memory)
    else:
        did = WHAT_IT_DID.search(line)
        if did:
            thing = _trim(did.group(1))
    # The thing named in the ask is not the thing told: "what was wrong with my boiler again"
    # said in the same breath as the news has nothing to be reminded of.
    if not thing or not content(thing):
        return None
    return thing


def _resolved(pronoun, memory):
    """The thing a pronoun points at, as the understanding engine read it."""
    if not isinstance(memory, dict):
        return ""
    read = memory.get("understood")
    if not isinstance(read, dict):
        return ""
    ref = read.get("ref")
    if not isinstance(ref, dict):
        return ""
    value = ref.get(str(pronoun or "").lower())
    if isinstance(value, str) and value.strip():
        return _trim(value)
    return ""


def about_a_thing_they_said(text, memory=None):
    """True when the line is a reminder about a thing of theirs, so the chat is what it asks
    about rather than the world."""
    try:
        thing = the_thing(text, memory)
        return bool(thing) and _said_before(thing, memory)
    except Exception:  # noqa: BLE001 - a reading that fails claims nothing
        return False
