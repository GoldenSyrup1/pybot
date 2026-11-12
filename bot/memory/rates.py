"""How often a thing they do happens, said of themselves.

    i go to the gym twice a week
    how often was that again
      "You go to the gym twice a week."

The store kept the hours a person's day runs on (`bot/modules/memory_store.py`, `_the_times`)
but nothing about how often they do a thing, so a late "how often was that again" reached the
detail ask-back and asked them the question they were asking the bot ("You haven't said - how
often was that?"), and "how often do i go to the gym" was answered from the exercise entry's
guideline rather than from the twice they had told it. This is the same shape of fact as a time
of day with a different unit, so it is filed the same way: against the doing they named, newest
winning, and read back in their own words.

Only a first-person line is filed, so "my husband goes to the gym twice a week" is not put on
them; a pronoun in the ask never names a doing ("how often should i feed them" after "i water
them every day" is about feeding, which nothing here holds); and a rate asked for as advice
("how often should i water them") is the knowledge base's, not this reader's.
"""
import re

from ..compose import pick


# How often a thing they do happens, when they say it of themselves: "i go to the gym twice a
# week", "we swim three times a week", "i walk the dog every morning". Kept the way the hours
# of their day are kept, because the ask on the other end is the same shape - "how often was
# that again" is asking this store what they told it, and answering it back ("You haven't said
# - how often was that?") says the chat was not listening. The rate is filed against the doing
# they named, so "and how often" with nothing of its own names the newest one.
# The rate itself, in the words people type it: "twice a week", "3 times a week", "every morning",
# "most days". One pattern for both ends, so the ask can quote back exactly what was filed.
RATES_TEXT = (r"(?:once|twice)(?:\s+(?:a|per|each)\s+(?:day|week|fortnight|month|year))?"
             r"|(?:(?:\d+|two|three|four|five|six|seven|eight)\s+times?)"
             r"\s+(?:a|per|each)\s+(?:day|week|fortnight|month|year)"
             r"|every\s+(?:\d+|a|an|one|two|three|four|five|six|few)\s+(?:days?|weeks?|months?)"
             r"|every\s+(?:day|week|morning|evening|night|weekend|other\s+day|monday|tuesday"
             r"|wednesday|thursday|friday|saturday|sunday)"
             r"|most\s+(?:days|weeks|mornings|evenings)")
RATES_SAID = re.compile(r"\b(?P<how>" + RATES_TEXT + r")", re.I)
# The first-person clause the rate sits in, which is where the doing is: "i go to the gym twice a
# week" is about the gym. A rate in somebody else's line ("and the cat gets fed twice a day") is
# not this person's own doing, and is left to whatever already reads that line.
RATES_SUBJECT = re.compile(
    r"^(?P<lead>and\s+|so\s+|also\s+|oh\s+|well\s+|but\s+|"
    r"actually\s+|no\s+|sorry\s+|make it\s+|i mean\s+|i meant\s+|rather\s+|instead\s+)*"
    r"(?P<subj>i|we|i'm|im|i've|ive|we're|were)\b(?P<rest>.*)$", re.I)
# A rate put right on a later line: "actually we go three times a week now". The doing is the one
# already on file, so the new rate replaces it rather than sitting beside it as a different thing.
RATES_FIX_LEAD = frozenset(("actually", "no", "sorry", "make", "i mean", "i meant", "rather",
                           "instead"))
# The words that make a line the doing rather than the rate alone: "twice a week" on its own is
# an answer to a question the bot asked, not something to file against a subject.
RATES_IGNORE = frozenset("""i we my our me the a an at on in to for of it that this and but so
just now only really still usually normally about around im ive were don't dont""".split())

# A rate put right on a line with no doing in it: "actually 5 times", "no wait, twice a week",
# "sorry, every other day". The doing is the one the store filed a turn or two before, because a
# bare rate typed straight after their own line is that line put right, not a second thing they
# do. Without this the chat kept the figure it was about to be corrected on, and the ask back read
# out the old rate over the correction:
#
#     i walk 3 times a week / actually 5 times / how often do i walk
#       "You walk 3 times a week."
#
# Two turns back is the limit: past that a bare "actually twice a week" is as likely to be about
# something the chat moved on from, and a correction the person did not make is worse than the
# figure they gave first.
RATES_CORRECTION_LEAD = (r"(?:actually|no\s+wait|no|sorry|wait|hang\s+on|make\s+it|i\s+mean"
                         r"|i\s+meant|rather|instead)")
RATES_CORRECTION_TAIL = r"(?:\s+(?:now|instead|actually|these\s+days|not))?\s*[.!]*\s*$"
# The count alone, which is how a rate is most often put right: "actually 5 times". The period is
# the one on file when the line does not name one, because the person is changing how many, not
# how often the period runs.
A_BARE_COUNT = re.compile(
    r"^\s*" + RATES_CORRECTION_LEAD + r"\b[,\s:]*"
    r"(?P<num>\d+|two|three|four|five|six|seven|eight|nine|ten)\s+times?"
    r"(?:\s+(?:a|per|each)\s+(?P<period>day|week|fortnight|month|year))?"
    + RATES_CORRECTION_TAIL, re.I)
# The whole rate again with the doing left off: "no wait, twice a week".
A_BARE_RATE = re.compile(r"^\s*" + RATES_CORRECTION_LEAD + r"\b[,\s:]*"
                         r"(?P<how>" + RATES_TEXT + r")" + RATES_CORRECTION_TAIL, re.I)
# The count in a rate on file, so a corrected count keeps the period it was said with.
A_COUNT_AND_PERIOD = re.compile(
    r"^(?P<num>\d+|two|three|four|five|six|seven|eight|nine|ten)\s+times?"
    r"\s+(?:a|per|each)\s+(?P<period>day|week|fortnight|month|year)$", re.I)


def _the_rates(memory):
    held = memory.get("rates")
    return held if isinstance(held, list) else []


def _keep_a_rate(memory, what, how, said):
    """File one rate they said of a thing they do, newest winning for that doing."""
    what = " ".join(str(what or "").split()).strip(" .,!;:-")
    how = " ".join(str(how or "").split()).strip(" .,!;:-")
    if not what or not how:
        return
    held = _the_rates(memory)
    turn = len(memory.get("turns") or [])
    for item in held:
        if isinstance(item, dict) and item.get("what") == what:
            item["how"] = how
            item["said"] = said
            item["turn"] = turn
            break
    else:
        held.append({"what": what, "how": how, "said": said, "turn": turn})
    memory["rates"] = held[-8:]


def _the_newest_recent_rate(memory, within=2):
    """The newest rate on file said a turn or two ago, which a bare correction can be about."""
    turn = len(memory.get("turns") or [])
    for item in reversed(_the_rates(memory)):
        if not isinstance(item, dict) or not item.get("how"):
            continue
        if turn - int(item.get("turn") or 0) <= within:
            return item
    return None


def _the_rate_put_right(text, memory):
    """File a correction of a rate that names no doing of its own, when there is one to correct.

    "actually 5 times" and "no wait, twice a week" are the line before, put right. The count alone
    keeps the period the rate was said with, because the person is changing how many and not how
    often the period runs: "i walk 3 times a week" then "actually 5 times" is five times a week,
    not five times ever.
    """
    said = " ".join(str(text or "").split())
    if not said:
        return False
    count = A_BARE_COUNT.match(said)
    whole = None if count else A_BARE_RATE.match(said)
    if not count and not whole:
        return False
    item = _the_newest_recent_rate(memory)
    if item is None:
        # Nothing on file to put right: a bare "actually 5 times" after a line about the weather
        # is not a rate of their own doing, and the store files nothing from it.
        return False
    if count:
        period = count.group("period")
        if not period:
            held = A_COUNT_AND_PERIOD.match(str(item.get("how") or "").strip())
            if held is None:
                # The rate on file is not a count ("every morning"), so a bare count cannot be
                # that rate put right, and guessing a period would invent one.
                return False
            period = held.group("period")
        item["how"] = count.group("num").lower() + " times a " + period.lower()
    else:
        item["how"] = " ".join(whole.group("how").lower().split())
    item["said"] = said.lower()
    item["turn"] = len(memory.get("turns") or [])
    memory["rates"] = _the_rates(memory)
    return True


def keep(text, memory):
    """Keep a rate said of their own doing: "i go to the gym twice a week"."""
    if not isinstance(text, str) or not isinstance(memory, dict):
        return
    if _the_rate_put_right(text, memory):
        # The line was a rate on file put right and named no doing of its own, so there is no
        # second thing to file: reading on would file the corrected figure as a new doing.
        return
    for clause in re.split(r"[.;!?,]|\band\b|\bbut\b", text.lower()):
        said = " ".join(clause.split())
        if not said:
            continue
        rate = RATES_SAID.search(said)
        if not rate:
            continue
        subject = RATES_SUBJECT.match(said)
        if not subject or subject.group("subj").lower() not in ("i", "we", "i'm", "im", "i've",
                                                               "ive", "we're", "were"):
            continue
        rest = " ".join(subject.group("rest").split())
        # The doing is the rest of the clause with the rate taken out of it: "go to the gym".
        inner = RATES_SAID.search(rest)
        what = (rest[:inner.start()] if inner else "").strip(" .,!;:-!")
        what = " ".join(word for word in what.split())
        words = [word for word in re.findall(r"[a-z']+", what) if word not in RATES_IGNORE]
        if not words:
            continue
        lead = (subject.group("lead") or "").strip().split()
        if lead and lead[0] in RATES_FIX_LEAD:
            # "actually we go three times a week now" is the rate already on file, put right, and
            # only a rate said in the last turn or two can be the one this line moves.
            held = _the_rates(memory)
            turn = len(memory.get("turns") or [])
            for item in reversed(held):
                if not isinstance(item, dict) or not item.get("how"):
                    continue
                mine = set(re.findall(r"[a-z']+", str(item.get("what") or "").lower()))
                theirs = set(re.findall(r"[a-z']+", what.lower()))
                if (mine & theirs) or turn - int(item.get("turn") or 0) <= 2:
                    item["what"] = item.get("what") or what
                    item["how"] = rate.group("how")
                    item["said"] = said
                    item["turn"] = turn
                    memory["rates"] = held
                    break
            else:
                _keep_a_rate(memory, what, rate.group("how"), said)
            continue
        _keep_a_rate(memory, what, rate.group("how"), said)


# The ask for one of those rates. It has to lean back on what this store holds, or name the doing
# without a rate of its own: "how often was that again", "how often do i go to the gym", "was that
# twice a week", "remind me how often". A rate asked of the world ("how often should i water the
# plants") names a doing this store has no rate for and is left to the knowledge base.
# A rate asked as advice ("how often should i water them") is the knowledge base's, not this store's.
RATES_ADVICE = re.compile(r"\b(?:should|shall|ought|need(?:s)?|best|recommend\w*|advice)\b", re.I)
RATES_ASK = re.compile(
    r"^\s*(?:and |so |ok |okay |oh |also |then )*(?:remind me\s+)?"
    r"(?:(?P<a>how often|how many times)\b(?P<rest>.*)"
    r"|(?P<b>was|is|were|are)\s+(?:that|it|this)\s+(?P<how>" + RATES_TEXT + r")"
    r"|what(?:'s|s| is| was)\s+the\s+(?:pattern|rate|schedule)\b(?P<rest2>.*))\s*[?.!]*\s*$", re.I)
# A pronoun in the ask points at what the store holds ("i water them every evening" / "how often
# should i feed them") but does not name it, so it never makes one doing the one asked about:
# "them" is in both lines and the question is about feeding, which this store has no rate for.
RATES_PRONOUN = frozenset("""them they it its it's that this these those him her his hers me us
one ones thing stuff""".split())
RATES_ASK_FILLER = frozenset("""do does did was is were i we my our me the a an you go going
again then was that it this now still say said tell once twice a week day month year times
usually normally i'm im've""".split())


def is_a_rate_ask(text, memory):
    """Is this line only the ask for one of the rates kept here?"""
    return bool(answer(text, memory))


def answer(text, memory):
    """The rate of their own doing a late ask names, said back in their own words."""
    if not isinstance(text, str) or not isinstance(memory, dict):
        return None
    held = [item for item in _the_rates(memory) if isinstance(item, dict) and item.get("how")]
    if not held:
        return None
    asked = RATES_ASK.match(" ".join(text.split()))
    if not asked:
        return None
    # "how often should i water them" is asking for advice about the thing, not for the rate this
    # store holds: the knowledge base's own figure ("twice a week in dry weather") is the answer,
    # and saying their habit back tells them nothing they did not say.
    if RATES_ADVICE.search(asked.group(0)):
        return None
    rest = (asked.group("rest") or asked.group("rest2") or "").lower()
    named = {word for word in re.findall(r"[a-z']+", rest) if word not in RATES_ASK_FILLER
             and word not in RATES_PRONOUN and len(word) > 2}
    item = None
    if named:
        for held_item in reversed(held):
            words = {word for word in re.findall(r"[a-z']+",
                                                 str(held_item.get("what") or "").lower())
                     if word not in RATES_PRONOUN}
            if named & words:
                item = held_item
                break
        if item is None:
            # A doing this store holds no rate for: not its to answer.
            return None
    else:
        lean_back = re.search(r"\b(?:that|it|this|again|remind)\b", asked.group(0).lower())
        if not lean_back and not asked.group("b"):
            return None
        item = held[-1]
    what = " ".join(str(item.get("what") or "").split())
    how = " ".join(str(item.get("how") or "").split())
    if not what or not how:
        return None
    # Said back to the person, so their own possessive is ours: "i get my hair cut" is "You get
    # your hair cut", not "You get my hair cut".
    what = re.sub(r"\bmy\b", "your", what)
    what = re.sub(r"\bour\b", "your", what)
    if pick([0, 1], memory) == 0:
        said = "You " + what + " " + how + "."
    else:
        said = how[:1].upper() + how[1:] + \
            " \u2014 you " + what + "."
    return said


