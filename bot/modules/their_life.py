"""A fact about the person's own life, said on its own, gets its own turn.

People drop the shape of their life into a conversation while it is about something else:
"we live near the park", "i live in a flat", "we rent", "we have a dog", "i've got two cats".
Said mid-thread, none of them is a detail of the answer before it, and today two things can
happen instead of an answer to it:

- after a knowledge answer, the rest of that answer is handed over again: "my laptop broke"
  then "we live near the park" is answered "If there is no light on the charger at all, try
  another socket and cable" (bot/modules/greeting.py, `the_step_they_have_not_had`, whose
  `A_DETAIL_OF_IT` matches any "in/near/on the X" - the intended line there, "its fine in the
  kitchen", has no subject of its own, and "we live" does);
- the thread decides the entry: "my back hurts" then "we have a dog" is answered about a dog
  in pain, which the person never said;

and a fact with nothing else in the line is only nodded back ("Noted: you have a sister and a
brother.", "Noted: you're 34." - the `FRAMES` receipt in bot/memory/ack.py, which knows the fact
and has nothing to say about it).

What a friend does with any of these is take the fact in and ask the one thing about it. That is
all this module does, for the four shapes of ordinary life that turn up this way - where they
live, the animals in the house, the brothers and sisters they have, and how old they are - so a
person who mentions their dog is not answered about their back, and a person who mentions their
sister is not handed their own sentence back.

What a friend does with "we live near the park" is take the fact in and ask the one thing about
it. That is all this module does, for the two shapes of ordinary life that turn up this way -
where they live, and the animals in the house - so a person who mentions their dog is not left
with the answer to their back.

Only a whole line is one of these facts: a line that goes on to say something else ("we have a
dog that keeps barking at the postman", "we live near the park and the gate is broken") keeps
the reading it has. A line in a heavy thread, or one carrying a symptom or a loss, is not a
fact about the shape of their life, and stands this down.
"""
import re

# Above the knowledge module (0) and below the chat module (300): the chat module has the place
# with a town name in it and the pets it knows, and it keeps those turns. This answers the lines
# it does not take, and the ones the thread would otherwise answer with the wrong entry.
PRIORITY = 100

# The two shapes, each with the lines it can be answered by: three, so a conversation that
# comes back to the same fact twice does not hear the same sentence.
_PLACES = (
    "{Where} - what's it like there?",
    "How long have you been there?",
    "{Where}, then. Is it handy for what you need?",
)

# One animal has a name and a history; more than one has the pair of them to ask about, which is
# the better question when there are two ("Two cats - do they get on?" is what a friend asks).
# The animal is named in the line, so a person who says "we have a dog" is answered about their
# dog rather than in the abstract.
_ONE_PET = (
    "{Pet} - what's their name?",
    "How long have they been with you?",
    "{Pet} - who spoils them most?",
)

_PETS = (
    "{Pets} - do they get on?",
    "{Pets} - what are their names?",
    "{Pets} - who spoils them most?",
)

# The words for a number in front of the animal, as the person said them.
_NUMBER_WORDS = {"two": "Two", "three": "Three", "four": "Four", "five": "Five", "six": "Six"}

# The words a line cannot carry and still be a fact about the shape of their life: a symptom, a
# loss, a problem. The same reader in the composer treats these as news (bot/compose/fallback.py,
# `_reads_as_heavy_news`), and a fact wrapped round one of them is a story with the fact inside.
_NOT_A_SHAPE = re.compile(
    r"\b(?:pain|pains|painful|hurt|hurts|hurting|ill|sick|poorly|dying|died|dead|death|"
    r"cancer|chemo|radiotherapy|tumour|tumor|dementia|alzheimers|alzheimer's|stroke|"
    r"hospital|hospice|funeral|buried|passed away|lost|loss|bereave\w*|griev\w*|"
    r"depress\w*|anxious|anxiety|panic|suicid\w*|self harm|crisis|emergency|"
    r"broken|leaking|damp|mould|flood\w*|evicted|eviction|arrears|debt|bailiff\w*|"
    r"divorce|separated|affair|abusive|violent|police|social services)\b", re.I)

# A verb out of these puts the line into the middle of something - a story, a plan, a complaint -
# rather than naming the shape of their life: "we have a dog that keeps barking", "we live near
# the park and the gate is broken".
_STORY = re.compile(
    r"\b(?:that|which|who|and|but|because|so|when|while|if|keeps?|kept|started|stopped|"
    r"barking|bites|bit|chewed|escaped|ran|went|got|needs?|needed|wants?|made|makes|"
    r"cost|costs|comes?|came|goes?|going|has|have|had|is|are|was|were|will|would|can|could)\b",
    re.I)

# The tone that ends a line without adding anything to it: "we have a dog tbh".
_TONE = re.compile(
    r"(?:\s+(?:tbh|tho|though|now|anyway|actually|really|literally|honestly|i\s+suppose|"
    r"i\s+guess|still|also|too|by\s+the\s+way|btw|atm|at\s+the\s+moment|lol|ha|haha|lmao|"
    r"so\s+yeah|yeah|innit|mate|dude|as\s+well))+$", re.I)

# Where they live: a place named without a town ("near the park", "in a flat", "by the river").
# A town has its own reader in the chat module ("Leeds - nice. How long have you been there?"),
# which is at a higher PRIORITY and keeps the turn; this is for the lines it does not take.
_LIVE = re.compile(
    r"^(?P<who>i|we)\s+(?:live|stay)\s+"
    r"(?P<where>(?:in|near|on|by|above|below|behind|next\s+to|opposite|at)\s+"
    r"(?:a|an|the|my|our|their|his|her)?\s*[a-z][a-z' -]{0,24})$")

# The place itself, without the direction: "we live in a flat".
_PLACE_KINDS = re.compile(
    r"^(?:in|near|on|by|above|below|behind|next\s+to|opposite|at)\s+"
    r"(?:a|an|the|my|our)?\s*(?:flat|house|home|place|bungalow|cottage|farm|boat|caravan|"
    r"car park|park|river|canal|sea|coast|beach|woods|wood|common|high\s+street|"
    r"village|town|city|estate|council\s+estate|block|tower\s+block|camper|motorhome|"
    r"shop|pub|office|station|hospital\s+car\s+park|school|church|allotment)$")

_PET = re.compile(
    r"^(?P<who>i|we)(?:'ve\s+got|\s+(?:have|got|own))\s+"
    r"(?P<num>a|an|one|two|three|four|five|six|\d+|\d+\s+)?\s*"
    r"(?P<pet>dogs?|cats?|puppies|puppy|kittens?|kitten|rabbits?|hamsters?|budgies?|parrots?|"
    r"horses?|pony|guinea\s+pigs?|tortoises?|snakes?|lizards?|geckos?|fish|gerbils?|ferrets?|"
    r"chickens?|hens?|ducks?|goats?|bees)$")


# The brothers and sisters they have: "i have a sister and a brother", "i have two brothers".
# The whole line has to be the family and nothing else, so "i have a brother who is ill" keeps the
# reading it has. Kids are left to the chat module ("Three kids. What are they into at the
# moment?"), which reads them already.
_SIBLINGS = re.compile(
    r"^(?P<who>i|we)(?:'ve\s+got|\s+(?:have|got))\s+(?P<what>"
    r"(?:(?:a|an|one|two|three|four|five|six|seven|eight|\d+|older|younger|little|big|twin|"
    r"step|half)[\s-]+)*(?:brother|sister|brothers|sisters)"
    r"(?:\s*(?:,|and)\s*)?"
    r"(?:(?:a|an|one|two|three|four|five|six|seven|eight|\d+|older|younger|little|big|twin|"
    r"step|half)[\s-]+)*(?:brothers?|sisters?)?)$")

_SIBLING_LINES = (
    "{What} - older or younger than you?",
    "{What} - do you see much of them?",
    "{What}, and do you get on?",
)

# Their age, said on its own: "im 34", "im 34 years old". A number with a measure after it is
# something else ("im 34 weeks pregnant", "im 34 kilos"), which is not a fact to ask a question
# about here.
_AGE = re.compile(
    r"^(?:im|i'm|i\s+am)\s+(?P<age>\d{1,2})(?:\s*(?:years?\s+old|yrs?\s+old|y/?o|yo|now|"
    r"today))?$")

_NOT_AN_AGE = re.compile(
    r"\b(?:weeks?|days?|months?|pregnan\w*|kilos?|kg|stone|pounds?|lbs?|miles?|minutes?|"
    r"hours?|degrees?|percent|%|cm|feet|foot|ft)\b", re.I)

_AGE_LINES = (
    "{Age} - how's this year treating you?",
    "{Age}, then. Anything you'd like to be different by {Next}?",
    "{Age} - a good age to be, or not?",
)

_MORE_THAN_ONE = frozenset(("two", "three", "four", "five", "six"))


def _more_than_one(num):
    """True for "two", "4", "10" - the count in front of the animal, when there is one."""
    said = str(num or "").strip()
    if said in _MORE_THAN_ONE:
        return True
    return said[:1].isdigit() and said not in ("0", "1")


def _line(text):
    """The line as this reader wants it: lower case, no edge punctuation, no tone on the end."""
    said = str(text or "").replace("\u2019", "'").strip().lower()
    said = said.strip(" .,!;:-\"'")
    said = re.sub(r"\s+", " ", said)
    while True:
        trimmed = _TONE.sub("", said)
        if trimmed == said:
            return said
        said = trimmed


def _a_fact_about_their_life(said):
    """The kind of fact this is, or None: "place", "pet", "siblings" or "age"."""
    if not said or "?" in said or _NOT_A_SHAPE.search(said):
        return None
    lived = _LIVE.match(said)
    if (lived and _PLACE_KINDS.match(lived.group("where"))
            and not _STORY.search(lived.group("where"))):
        return "place"
    siblings = _SIBLINGS.match(said)
    if siblings and not _STORY.search(said[siblings.end():]):
        what = _TONE.sub("", siblings.group("what")).strip(" ,")
        if what:
            return "siblings:" + what
    age = _AGE.match(said)
    if age and not _NOT_AN_AGE.search(said) and 13 <= int(age.group("age")) <= 99:
        return "age:" + age.group("age")
    pet = _PET.match(said)
    if pet and not _STORY.search(said[pet.end():]):
        num = (pet.group("num") or "").strip()
        kind = "two_pets" if _more_than_one(num) else "pet"
        return kind + ":" + num + ":" + pet.group("pet")
    return None


def _where_words(said):
    """The place said back in their own words: "near the park" -> "Near the park"."""
    lived = _LIVE.match(said)
    where = lived.group("where") if lived else said
    return where[:1].upper() + where[1:]


def respond(text, memory):
    said = _line(text)
    found = _a_fact_about_their_life(said)
    if not found:
        return None
    kind, _, rest = found.partition(":")
    if kind in ("siblings", "age"):
        num, animal = rest, ""
    elif kind in ("pet", "two_pets"):
        num, animal = rest.split(":", 1)
    else:
        num, animal = "", ""
    # A heavy thread is not the place for a cheery question about the dog: after a death or a
    # diagnosis the fact is something the person said while telling the thing that matters, and
    # that thing keeps the turn.
    from ..compose import fallback
    if (fallback._the_thread_is_heavy(memory) or fallback._reads_as_heavy_news(said)
            or _THE_LINE_BEFORE_IS_HEAVY.search(_the_line_before(memory))):
        return None
    return _the_fact(kind, num, animal, said, memory)


# fallback's own read of heavy news is about the words a person says when they are telling you
# the news; the line before can carry it in a plainer word ("my friend is very ill", "my son is
# being bullied") that it does not read, and a cheery question about the dog after that is worse
# than the composer's own answer.
_THE_LINE_BEFORE_IS_HEAVY = re.compile(
    r"\b(?:ill|unwell|poorly|sick|dying|died|death|passed away|funeral|bereave\w*|griev\w*|"
    r"cancer|chemo\w*|radiotherap\w*|tumou?r|dementia|alzheim\w*|stroke|sepsis|surgery|"
    r"operation|transplant|hospice|palliative|terminal|hospital|icu|ambulance|diagnos\w*|"
    r"bully\w*|bullied|depress\w*|suicid\w*|self harm|miscarr\w*|stillborn|addict\w*|"
    r"relapse\w*|overdose\w*|sectioned|in pain|suffering)\b", re.I)


def _the_line_before(memory):
    """What the person said on the turn before this one, or "" on the first turn."""
    turns = [turn for turn in ((memory or {}).get("turns") or []) if isinstance(turn, dict)]
    return str(turns[-1].get("user") or "") if turns else ""


def _the_fact(kind, num, animal, said, memory):
    if kind == "siblings":
        what = num[:1].upper() + num[1:]
        return _pick(_SIBLING_LINES, memory).replace("{What}", what)
    if kind == "age":
        line = _pick(_AGE_LINES, memory)
        return line.replace("{Age}", num).replace("{Next}", str(int(num) + 1))
    if kind == "place":
        return _pick(_PLACES, memory).replace("{Where}", _where_words(said))
    if kind == "two_pets":
        line = _pick(_PETS, memory)
        count = _NUMBER_WORDS.get(num, "The")
        return line.replace("{Pets}", count + " " + _plural(animal))
    line = _pick(_ONE_PET, memory)
    return line.replace("{Pet}", ("An " if animal[:1] in "aeiou" else "A ") + animal)


def _plural(word):
    """The animal as more than one, whatever the person typed: "cat" -> "cats"."""
    said = str(word or "")
    if said.endswith("s") or said in ("fish", "sheep", "deer"):
        return said
    if said.endswith("y"):
        return said[:-1] + "ies"
    return said + "s"


def _pick(pool, memory):
    """The first line of the pool this conversation has not said yet."""
    said = set()
    for turn in (memory.get("turns") or []):
        if isinstance(turn, dict) and isinstance(turn.get("bot"), str):
            said.add(turn["bot"].strip())
    for line in pool:
        if line not in said:
            return line
    return pool[0]
