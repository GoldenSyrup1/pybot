"""The answer in the first sentence, for every answer module at once.

Two rules live here, both about the same thing: STYLE.md's "the answer in the first sentence",
read from `memory["understood"]["wants"]`. The first turns a method round when a card written for
"how long" is asked "how"; the second puts a row's own declared opening (`entry(..., lead=...)`)
in front of a card that is written for the harder question and has the plain one to answer too
(`entry(..., lead=("yesno", "Usually, yes"))`: the shape of line, then the sentence owed to it).
Both are read by the one place every knowledge row is rendered (`bot/modules/answers.py`), so a
row in any domain gets them without a module changing.

STYLE.md asks for the answer in the first sentence. A row that holds a dish holds one answer for
every way the dish is asked about, so it is written the way the clock asks for it: "About 40
minutes start to finish. Fry 500g mince hard ...". That is the answer to "how long does chilli
take" and it is not the answer to "how do i make chilli", which is the method the person came
for: read out, the first thing they get is a duration they did not ask for, and the paragraph
that tells them what to do starts in the second sentence.

So when the line asks for the method (`memory["understood"]["wants"]` is `steps`), a reply whose
opening sentence is only the total time of the job is turned round: the method leads and the
total time closes the answer, where it is still useful and no longer in the way of it. Nothing is
added, cut or reworded - the same sentence moves to the end - and every other ask is left exactly
as it is, because "how long" wants the clock first and a limit or a fault is not this file's.

The move is safe because the sentence it moves says only how long the whole thing takes: it
carries "start to finish", "from start to finish", "in total", "altogether" or "all in", so it is
a summary of the job and not one step's own time ("simmer 30 minutes" stays where it is, inside
the method it belongs to).
"""
import re

from . import fit

# The whole answer's duration said as a sentence of its own: "About 40 minutes start to finish.",
# "About 2 hours start to finish for a 2kg chicken.", "About 5 minutes start to finish, then 30
# minutes resting." A figure, a time unit, and the words that make it the total rather than a
# step's own time.
_TOTAL = re.compile(
    r"^(?:about|around|roughly|just|only|under|over|about an?|an?|a)\s*"
    r"[^.]{0,60}"
    r"\b(?:minutes?|mins?|hours?|hrs?|days?)\b"
    r"[^.]{0,60}?"
    r"\b(?:start to finish|from start to finish|in total|altogether|all in|end to end)\b",
    re.I)

# One sentence: everything up to a full stop that ends a sentence (not the dot of "1.5kg" or
# "190C." inside a number), and the rest of the reply.
_OPENING = re.compile(r"^\s*(\S.*?[.!?])\s+(\S.*)$", re.S)

# The shapes that ask for the method itself. A soft `advice` is a reply to the person's situation
# rather than a set of steps, so it is not turned round here.
_METHOD = frozenset(("steps",))

# A sentence that only says what follows. It carries a count and a noun, or points forward, and
# names no fact of its own: "Three tests, in this order.", "Two things to know.", "Here's the
# short version." A count with a verb ("Two things are true") is not this, because it says
# something; a count with no noun ("Two hours.") is an answer, not a signpost.
_SIGNPOST = re.compile(
    r"^(?:"
    r"(?:a few|a couple of|two|three|four|five|six|\d+)\s+"
    r"(?:things?|tests?|steps?|options?|ideas?|ways?|rules?|checks?|questions?|tips?|notes?|"
    r"points?|parts?)"
    r"(?:\s*,?\s*(?:in this order|to know|to try|to check|to keep in mind|first|for you|"
    r"to start with|before you start))?"
    r"|here(?:'?s| is| are)\s+(?:the|a|an|what|how|my|our|it|this)\b[^:]{0,60}"
    r"|the following\b[^:]{0,40}"
    r"|these are\b[^:]{0,40}"
    # A sentence that talks about the question or the answer instead of giving it. It carries no
    # fact, so it is not the answer whatever shape was asked for.
    r"|(?:great|good|fair|interesting|nice|lovely) question"
    r"|(?:that'?s|it'?s) (?:a )?(?:great|good|fair|interesting|nice) question"
    r"|you (?:asked|want(?:ed)? to know|were asking|are asking)\b[^:]{0,80}"
    r"|so (?:you'?re|you are) asking\b[^:]{0,80}"
    r"|the question (?:is|was)\b[^:]{0,80}"
    r"|let me (?:start|explain|answer|walk you through|take you through|think)"
    r"|i'?ll (?:start|explain|answer|walk you through|take you through)"
    r"|i can (?:help|answer|explain|tell you)"
    r")$", re.I)


def _sentences(reply):
    """The reply's sentences, in order, with their own punctuation kept."""
    text = " ".join(str(reply or "").split())
    if not text:
        return []
    out, start = [], 0
    for end in _SENTENCE_END.finditer(text):
        before = text[start:end.start()]
        if _ABBREVIATION_END.search(before):
            continue
        out.append(text[start:end.start()].strip())
        start = end.end()
    if text[start:].strip():
        out.append(text[start:].strip())
    return [sentence for sentence in out if sentence]


# A dot after one of these ends a word, not the sentence, as in `bot/compose/fit.py`.
_SENTENCE_END = re.compile(r"(?<=[.!?])\s+")
_ABBREVIATION_END = re.compile(
    r"\b(?:e\.g|i\.e|approx|incl|etc|vs|cf|fig|dept|est|ref|tel|mr|mrs|ms|dr|prof)\.$", re.I)


def _wants_the_method(understood):
    if not isinstance(understood, dict):
        return False
    want = understood.get("wants")
    if isinstance(want, str):
        want = want.strip().lower()
    return want in _METHOD


def answer_first(reply, understood, line=None):
    """The answer leads: a sentence that only announces the answer is not the answer.

    A row, a card or a composer line is often written to be read on a screen, where a signpost
    helps: "Three tests, in this order.", "Two things to know.", "Here's the short version.",
    "Good question.", "You asked how long rice takes." Read out as the first thing the person
    gets, it answers nothing. STYLE.md puts the answer in the first sentence, so that sentence is
    dropped and the sentence it was announcing leads.

    The same reading is used for every shape of answer: a signpost is not a time, a figure, a
    list, a comparison, a verdict or a method, so no table of labels is kept here. The sentence is
    dropped only when there is another sentence to lead, and nothing else is reordered, added or
    reworded. A count in a signpost ("three tests") is still carried by the tests that follow.
    """
    if not isinstance(reply, str) or not reply.strip():
        return reply
    parts = _sentences(reply)
    if len(parts) > 1:
        first = parts[0].rstrip(".!? ").strip()
        if first and _SIGNPOST.match(first):
            reply = " ".join(parts[1:])
    # A method ask is already turned round by `method_first`, which moves the one sentence that
    # is only the whole job's clock and leaves every step's own time inside the method.
    if _wants_the_method(understood):
        return method_first(reply, understood)
    return reply


def method_first(reply, understood):
    """The reply with its total time moved to the end when the line asked for the method.

    Returns the reply unchanged for every other line, for a reply that is one sentence (there is
    nothing to lead with), and for a reply whose opening sentence is about more than its total
    time.
    """
    if not isinstance(reply, str) or not reply.strip():
        return reply
    if not _wants_the_method(understood):
        return reply
    found = _OPENING.match(reply)
    if not found:
        return reply
    opening, rest = found.group(1).strip(), found.group(2).strip()
    if not _TOTAL.match(opening):
        return reply
    if not rest:
        return reply
    return "%s %s" % (rest, opening)


# The shapes a single sentence can carry, and so the shapes a row can owe a sentence for. The
# soft ones (`opinion`, `advice`, `comfort`, `answer`) are the whole reply rather than a figure, a
# place or a verdict, so no one sentence gives one and no row can declare one for them.
_HARD = frozenset((fit.TIME, fit.AMOUNT, fit.PLACE, fit.PERSON, fit.MEANING,
                   fit.YESNO, fit.PICK, fit.STEPS, fit.OPTIONS, fit.REASON))

# The words a sentence is about: the short ones ("a", "in", "of") say nothing on their own.
_SAID_WORD = re.compile(r"[a-z0-9]+")


def _the_want(understood):
    if not isinstance(understood, dict):
        return ""
    want = understood.get("wants")
    if not isinstance(want, str):
        return ""
    return want.strip().lower()


def _the_opening(reply):
    return fit.first_sentence(reply)


def _already_said(lead_said, opening):
    """True when the opening sentence already says the declared one, in its own words."""
    mine = [w for w in _SAID_WORD.findall(lead_said.lower()) if len(w) > 2]
    if not mine:
        return lead_said.lower().strip(" .,!?") == " ".join(_SAID_WORD.findall(opening.lower()))
    there = set(_SAID_WORD.findall(opening.lower()))
    return all(word in there for word in mine)


def the_sentence_owed(reply, understood, declared=None):
    """The sentence the line asked for, put in front, when the row declares one for its shape.

    A row holds one answer for every way its subject is asked about, and it is written for the
    harder question: the side-effects card was written for "my medication is making me feel odd"
    and answers "are these side effects normal" with a paragraph about the leaflet that reaches
    the verdict only in its third clause. STYLE.md asks for the answer in the first sentence, so
    a row declares the sentence it owes and the shape of line it owes it to -
    `entry(..., lead=("yesno", "Usually, yes"))`, or a callable in place of the sentence for a row
    whose key is asked from both sides ("No" for "is a cold the same as the flu", "" for "can i
    get flu twice") - and this puts it in front.

    What decides is the line, not a reading of the card: the line's `wants` has to be the shape
    the row declared, and only then does the sentence go in front. So a line that wants a time is
    left alone by a row whose sentence is a verdict, a card that already opens on the same words
    is left exactly as it was, and a sentence the shape check can read as another shape is never
    used. Nothing is reworded: the sentence is the row's own words.
    """
    if not isinstance(reply, str) or not reply.strip():
        return reply
    if not isinstance(declared, (tuple, list)) or len(declared) != 2:
        return reply
    shape, said = declared
    shape = shape.strip().lower() if isinstance(shape, str) else ""
    if shape not in _HARD or _the_want(understood) != shape:
        return reply
    if callable(said):
        # a row whose key is asked from both sides of one question reads the line and says which
        # sentence it owes, exactly as a row's `guard=` reads the line. Anything it cannot answer
        # with is no sentence at all.
        try:
            said = said(understood)
        except Exception:  # noqa: BLE001 - a sentence is never worth a turn
            return reply
    if not isinstance(said, str) or not said.strip():
        return reply
    bare = " ".join(said.split()).rstrip(" .!?")
    if not bare:
        return reply
    opening = _the_opening(reply)
    if reply.lstrip().lower().startswith(bare.lower()):
        return reply
    if _already_said(bare, opening):
        # the card opens on the same answer in its own words: "Yes. Yes, but only ..." is not a
        # reply, and "In the cupboard. It keeps a fortnight in the cupboard." is not one either.
        return reply
    line = understood.get("text") if isinstance(understood, dict) else None
    if not isinstance(line, str):
        line = (understood.get("clean") if isinstance(understood, dict) else "") or ""
    try:
        if fit.gives(bare, shape, line) is False:
            # the sentence is unmistakably another shape for this line, so the row is mis-declared
            return reply
    except Exception:  # noqa: BLE001 - a shape check must never cost a turn its reply
        return reply
    return "%s. %s" % (bare, reply.lstrip())
