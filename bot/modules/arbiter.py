"""Chooses each turn's reply among the modules' candidates. The routing lane owns this file.

The seed rule stays the floor: candidates arrive highest PRIORITY first, and a fallback
(PRIORITY below 0) answers only when nothing else does. Two general rules on top of it
(README.md, "Routing"; STYLE.md):

* the specialist beats the generalist: a module that declares `ANSWERS` (the topics it is
  good at, e.g. `ANSWERS = ("cooking", "food")`) is preferred when this line was read as
  being about one of them, and the candidate in front of it is not about them. A reply about
  the topic asked beats a fluent one about something else. Two specialists go to the one that
  matches the line better (more of its topics, a topic id before a single word), and only
  then to PRIORITY. The understanding engine's topic ids (memory["understood"]["topics"] and
  ["topic"]) are the strong signal; the line's own words are the weaker one, so a module still
  works while a topic reader is missing. A follow-up ("and how long?") has no topic of its
  own, so the line the conversation is on (memory["topic"]) is read with the same reader and
  stands in for it.
* a line about the conversation is the recall band's: a line that names no topic of its own
  ("what am i doing this week" after "im writing up my thesis") was read as a topic only by
  inheritance, and the memory store's answer to it ("You're writing up your thesis.") is the
  answer to what was asked, while a topic entry that fits only by inheritance answers a question
  nobody asked. So the specialist rule does not lift a module over a PRIORITY 7000 candidate on
  a line whose own reading names no topic; the line's own phrase or word can still lift it (see
  `_fit`).
* never say the same thing twice in a row: a candidate whose reply only repeats the bot's
  last turn is passed over while another candidate says something different. Nor a whole answer
  said to this person earlier in the conversation: a reply that is word for word something the
  bot already said, several turns back, is passed over while another real candidate has something
  new. The same question asked twice in a row is the case for the repeat, and there every real
  candidate is that answer again, so nothing is dropped.
* an emergency stays an emergency: for a line that is still inside a safety thread, the
  composer's careful continuation beats a light module that would answer it as ordinary talk.
* a sudden loss is answered as a loss: a pregnancy that has ended or someone who took their own
  life gets the composer's own line for it, even when a module below has a general "sorry to
  hear it" for bad news ("we lost the baby" was answered "give it a day, then look at what you
  can control", which is advice for a setback).
* a bare "where do i start" gets the step out of the answer in hand: a line that names nothing and
  asks for the next move is answered by the shortest candidate built from the answer's own words,
  even when a topic entry answers the same line by reading the whole answer out again in its other
  wording (see `_the_move_in_hand`).
* a module can say that one of its proposals is to be answered as it comes, without raising its
  PRIORITY: it declares `TAKES_AS_IT_COMES(text, memory)` and the arbiter asks it on the line
  the proposal is for (see `_as_it_comes`). A band says "everything this module proposes"; a
  hook says "this line, because I read it whole", which is what a module needs when only part
  of what it proposes deserves the turn.
* a reply does not offer the food the line refused: "im trying to eat better but i hate veg" was
  answered by the balanced-meal card ("Half the plate vegetables..."), the one thing the person
  had just ruled out. The kitchen already reads the refusal, so a candidate whose first sentence
  offers that food is passed over while one that respects it is on the table. The safety band is
  never passed over, and neither is a reply that names the food to leave it out ("No onion then:
  ...", "nut-free"), which is still the answer to the refusal.

* a rule-out keeps the turn when the answer beside it offers back what was ruled out: "what
  should i cook tonight" / "not curry, something else" was answered "Quick: chickpea curry in 25,
  or a sweet potato curry" - the thing refused, twice - while the rule-out's own line ("That one
  never mentions curry at all, so nothing changes. ...") was in the list under the floor. A reply
  that hands back what the person has just ruled out has not read the line, so it is not an answer
  a claim gives way to, by PRIORITY or to a declaring specialist (see `_every_real_answer_offers`).

A candidate at PRIORITY >= 9000 (the safety band) is never passed over this way: a real
emergency is answered by the module that recognised it. Anything unexpected falls back to the
seed rule, so a turn is never lost and the arbiter never crashes a reply.
"""
import importlib
import re

from ..compose import badnews, facts, fallback, fit, leaving, onscreen
from ..compose import limit as _limit
from ..memory import narrow as _narrow
try:  # the reading of "the next line of a hard story" and the lines it is answered with
    from ..memory import ack as _ack
except Exception:  # noqa: BLE001 - a reading that cannot be imported just adds no rule
    _ack = None
try:  # the reading of a death, for the rule that lifts a listening line after one
    from ..compose import loss as _loss
except Exception:  # noqa: BLE001 - a reading that cannot be imported just adds no rule
    _loss = None
try:  # the reading of a report that a step was already taken, and of the step it reports
    from ..memory import already as _already
except Exception:  # noqa: BLE001 - a reading that cannot be imported just adds no rule
    _already = None
try:  # the reading of a wish to hurt somebody, and the lines it is answered with
    from ..compose import harm as _harm
except Exception:  # noqa: BLE001 - a reading that cannot be imported just adds no rule
    _harm = None
try:  # whether anything was said before this line, one reading for every chat reader
    from ..memory import there_is_a_chat as _there_is_a_chat
except Exception:  # noqa: BLE001 - a reading that cannot be imported makes no claim
    _there_is_a_chat = lambda _memory: False  # noqa: E731
try:  # the shared reading of a follow-up that names nothing, and of the ask for the next move
    from ..memory import repeat as _repeat
except Exception:  # noqa: BLE001 - a reading that cannot be imported just adds no rule
    _repeat = None
try:  # the reading of a recall ask ("what was my target again") and the fact it names
    from ..memory import recall as _recall
except Exception:  # noqa: BLE001 - a reading that cannot be imported just adds no rule
    _recall = None
try:  # the reading of the line that answers the bot's own "what's its name?"
    from ..memory import named as _naming
except Exception:  # noqa: BLE001 - a reading that cannot be imported just adds no rule
    _naming = None
try:  # the composer's own name for the kind of line it answers itself: one source of truth
    from ..compose.fallback import CARE_THREAD, PAUSE, THREAD
except Exception:  # noqa: BLE001 - a composer that cannot be imported has no kinds either
    THREAD, CARE_THREAD, PAUSE = "thread", "care-thread", "pause"
try:  # the composer's generic step lines, for the turn an entry already answers with a step
    from ..compose import STEP_WHEN_LOW as _STEP_WHEN_LOW
except Exception:  # noqa: BLE001 - a composer without them has no such lines to yield
    _STEP_WHEN_LOW = ()
try:  # the kitchen's own reading of a food somebody in the line will not eat
    from ..knowledge import cooking as _cooking
except Exception:  # noqa: BLE001 - a kitchen that cannot be imported just adds no rule
    _cooking = None
try:  # the composer's own reading of a thing the line rules out of the answer above
    from ..compose import ruledout as _ruledout
except Exception:  # noqa: BLE001 - a reading that cannot be imported just adds no rule
    _ruledout = None

try:  # whether the chat has a turn behind this one, and which replies lean on one
    from ..memory import history as _history
except Exception:  # noqa: BLE001 - a reading that cannot be imported just adds no rule
    _history = None

# The name of the module attribute the other lanes declare, and that the arbiter itself does not:
# a module says which topics it answers with `ANSWERS = ("cooking", "food")`. The constant used to
# be called ANSWERS too, so `getattr(arbiter, "ANSWERS")` handed back the string "ANSWERS" and the
# arbiter read itself as declaring the seven letters A, E, N, R, S, S and W as topics.
DECLARED_TOPICS = "ANSWERS"
# The understanding engine's label for a line that asks to choose between named options
# ("is it worth fixing or shall i just get a new one"): see `_a_choice_the_answer_did_not_make`.
CHOICE = "choice"
# A module that answers in place of the topic entries declares `ANSWERS_INSTEAD = ("loss",
# "grief")`: it read the whole line itself and it is sure, where a topic entry only matched a
# word or a topic id of it. See `_instead`.
DECLARED_INSTEAD = "ANSWERS_INSTEAD"
DECLARED_DEFERS = "DEFERS_TO"
# A module that answers a line as it comes, whatever else proposed: it declares
# `TAKES_AS_IT_COMES = callable(text, memory) -> bool` and says yes only on the lines it read
# whole itself. See `_as_it_comes`.
DECLARED_AS_IT_COMES = "TAKES_AS_IT_COMES"
# A module that answers a line another module claims as it comes declares
# `CLAIMS_INSTEAD = callable(text, memory) -> bool`: a claim says "this line is mine, whatever
# else proposed", which is right for the lines the claimant read whole and wrong where a
# specialist has the answer the person asked for. See `_claims_instead`.
DECLARED_CLAIMS_INSTEAD = "CLAIMS_INSTEAD"
# A module that can say a line is about the conversation rather than about the world declares
# `ASKS_ABOUT_THE_CHAT(text, memory) -> bool`. The memory store has that reading already, so the
# arbiter asks it instead of keeping a second word list (see `_fit`). A module that keeps the
# same reading under a name of its own is asked through that name, so the store's gate counts
# while its file sits at the repository's size cap and cannot take the published line.
DECLARED_ABOUT_THE_CHAT = "ASKS_ABOUT_THE_CHAT"
OWN_ABOUT_THE_CHAT = "_about_this_chat"
SAFETY = 9000  # PRIORITY band that is never outvoted (see the routing lane's PRIORITY scheme)
# The top of the small-talk band: a take from underneath it is chatter giving way, a take from
# the general band and above is a module that read the line. See `_as_it_comes`.
CHATTER = 1000
RECALL = 7000  # the memory store's recall of what was said leads the turn (README, "Routing")
# A step out of the answer in hand is one clause, and built out of the answer's own words: how many
# words it may run to, and how much of it has to be the answer's words. See `_the_move_in_hand`.
MOVE_WORDS = 26
MOVE_SHARE = 0.5
# How much of the answer a reply has to run to before it is the answer read out again rather than a
# part of it: three quarters of the answer's words. A step is a fraction of an answer (a fifth of
# one, in every case this rule was written for), so the two are never close.
MOVE_WHOLE = 0.75
# ...and how long the answer in hand has to be before that test says anything. A short line has a
# short re-tell: after a twenty-word "why" answer every candidate runs to three quarters of it, so
# `MOVE_WHOLE` called all three of them the answer read out again and the shortest one won - which
# was the hedge, "There is nothing to do about it until we have looked at it". Thirty words is the
# first length where three quarters of an answer is a paragraph rather than a clause.
MOVE_ANSWER_WORDS = 30
# The kinds the composer claims for "ask how the bot itself works" are published by the composer
# (`bot/compose/fallback.py: MY_WORKINGS`). The arbiter keeps no vocabulary of its own: it asks the
# composer which kinds are its workings and reads the reading. See `_about_the_bot`.
# The band of modules that read a whole line and answer it themselves (loss, grief). A turn they
# claim is theirs: the composer's own readings only fill in below them. See `_pause_reply`.
WHOLE_LINE_BAND = 2000
WORD = re.compile(r"[a-z0-9]+(?:'[a-z]+)?")
# The key a topic record carries its label in: the understanding engine writes "id", the
# memory store writes "label" (agreed in #general) and the first store wrote "text".
LABEL_KEYS = ("id", "label", "topic", "name", "text")
# Readings already made of the conversation's stored lines, so a turn costs one at most.
READ = {}


def choose(text, memory, candidates):
    """Return the index of the chosen candidate.

    candidates: [{"module": name, "priority": PRIORITY, "reply": text}], highest PRIORITY
    first. memory["turns"] holds the earlier turns of the conversation.
    """
    try:
        index = _choose(text, memory, candidates)
    except Exception:  # noqa: BLE001 - the arbiter must never lose a turn
        index = _seed(candidates)
    return _a_past_that_is_not_there(index, candidates, text, memory)


def _a_past_that_is_not_there(index, candidates, text, memory):
    """The chosen candidate, unless it answers a chat that has not started.

    A reply that speaks about the conversation - "welcome back, where were we", "you mentioned",
    "same as before", "good to hear, what was the best bit?", "nice one, how did the rest of it
    go?" - is about turns behind this one, and on the opening line there are none. Every pool in
    the bot is written for a chat in progress, so the same fault turns up in a dozen places; the
    fault is not in the pools but in giving a reply about a life the person has not described,
    which is one question about the conversation and not one question per module. It is asked
    here, once, after every rule has had its say, and the question itself lives in one place:
    `bot/memory/history.py::an_earlier_turn`, read by
    `bot/memory/history.py::a_past_that_is_not_there`, which the composer, the store's warmth and
    this guard all call.

    The reading takes the person's line as well as the reply. A frame like "nice one" or "good to
    hear" is right on a first line that brings something of its own ("weve booked a week in
    cornwall" is well met by "Nice one. Is it soon?"), and only wrong when the line brings
    nothing - "carry on", "as i was saying", "sorry, i got cut off". So the frame counts when the
    line points back too, which is the same reading in `bot/memory/history.py`.

    The replacement is the best of what the modules offered after the leak is taken out: a take
    from a real module, never the greeting band underneath them (a greeting is not an answer to
    anything), and never out of the safety band, which does not talk about earlier turns and whose
    candidate is the turn whatever else is on the table. Where every candidate answers something
    unsaid the turn is left as it came: the composer's own answer to that is its first-line pool
    (`bot/compose/fallback_data.py::NOTHING_SAID_YET`), offered on a first line for the same
    reason, and no reply is invented here. The guard cannot raise - a guard that raises is worse
    than no guard, because the exception would take the turn with it - so everything in it is
    inside one `try`.
    """
    if _history is None or not candidates:
        return index
    try:
        def speaks_of_a_past(reply):
            return _history.a_past_that_is_not_there(reply, memory, text)

        reply = candidates[index].get("reply") if 0 <= index < len(candidates) else ""
        if not speaks_of_a_past(reply):
            return index
        if _priority(candidates[index]) >= SAFETY:
            return index
        for other, candidate in enumerate(candidates):
            if _priority(candidate) < 0:
                continue
            if not speaks_of_a_past(candidate.get("reply")):
                return other
    except Exception:  # noqa: BLE001 - the arbiter must never lose a turn
        return index
    return index


# A reply that comes from what was said before this line, rather than from the world. On a line
# that asks for something said earlier, the store's answer is the answer, whatever topic the
# line's words happen to name: "what was my goal again" after "i'm trying to save 8000 for a van"
# was read as a goal-and-habits line, and a habit card lifted over the store's "You said 8000."
# The ask is read once here, so a new wording of it is answered by the store without a specialist
# rule in each module learning it.
MEMORY_MODULES = frozenset(("memory_store", "chat", "greeting"))


def _a_recall_from_an_earlier_turn(text, memory):
    """Whether this line asks for something said earlier, and there is an earlier turn to hold it.

    `recall.ask` reads the fact-shaped asks ("what is my name", "do you remember my budget"), and
    `repeat.asked_back` reads the asks for a figure the person gave ("what was my target again").
    Both are the memory lane's readings; this only asks whether either of them has an answer.
    """
    if not _there_is_a_chat(memory):
        return False
    try:
        if _recall is not None and _recall.ask(text):
            return True
    except Exception:  # noqa: BLE001 - a reading that fails is not an ask
        pass
    try:
        return bool(_repeat is not None and _repeat.asked_back(text, memory))
    except Exception:  # noqa: BLE001 - a reading that fails is not an ask
        return False


def _seed(candidates):
    """The seed rule: the first real candidate, or the first fallback."""
    for index, candidate in enumerate(candidates):
        if _priority(candidate) >= 0:
            return index
    return 0


def _priority(candidate):
    priority = candidate.get("priority", 0)
    if isinstance(priority, bool) or not isinstance(priority, (int, float)):
        return 0
    return priority


# The words that can sit beside a food in a reply without offering it: "no onion then", "nut-free",
# "leave the mushrooms out", "swap the lamb for chicken". A mention with one of these near it is
# the refusal being answered, not the refused food being recommended.
_REFUSAL_UNDONE = frozenset((
    "no", "not", "without", "free", "avoid", "leave", "leaves", "leaving", "left", "out",
    "instead", "swap", "swaps", "swapped", "rather", "cant", "dont", "doesnt", "didnt",
    "refuse", "refused", "refuses", "allergic", "allergy", "intolerant", "allergen", "isnt",
    "arent", "wasnt", "wont", "cannot", "never", "none", "nothing", "off", "replace"))


# A line that says the cupboard is empty is not a person refusing to eat the food: "i dont have
# any eggs" was read as a refusal, and the answer's first move ("Eggs are the whole dish there")
# was passed over for a cooking step that had nothing to do with it. A refusal this line takes
# back ("im not allergic to nuts actually, just peanuts") is not one either.
_ALLERGY_LIFTED = re.compile(
    r"\b(?:not|isnt|arent|wasnt|werent|never)\s+(?:actually\s+)?(?:allergic|intolerant)\b"
    r"|\bno\s+(?:allerg(?:y|ies)|intolerance)\b")


def _the_food_the_line_refused(text, memory):
    """The foods the line says somebody at the table will not eat, read by the kitchen.

    The kitchen's list also names what the cupboard has run out of, and reads "not allergic" as
    an allergy, so those two shapes are left out here: neither is a reason to pass over an answer.
    """
    if _cooking is None:
        return frozenset()
    understood = memory.get("understood") if isinstance(memory, dict) else None
    if not isinstance(understood, dict) or not understood:
        understood = {"clean": text}
    said = str(understood.get("clean") or understood.get("text") or text or "").lower()
    if _ALLERGY_LIFTED.search(said):
        return frozenset()
    if any(phrase in said for phrase in getattr(_cooking, "SHORTAGE_WORDS", ())):
        return frozenset()
    try:
        return frozenset(_cooking.refused_foods(understood))
    except Exception:  # noqa: BLE001 - a reading that fails refuses nothing
        return frozenset()


def _offers_the_food(reply, refused):
    """True when the first sentence of the reply offers a food the line refused.

    Only the first mention of each food is read, and only the words just around it: a reply that
    opens on the refusal ("No mushrooms then: leave them out", "Egg free: ...", "nut-free") has
    answered it, while "Half the plate vegetables..." has not. The first sentence is what the
    person reads before deciding whether the answer heard them.
    """
    first = re.split(r"(?<=[.!?])\s+", str(reply or "").strip(), maxsplit=1)[0].lower()
    words = [word.replace("'", "") for word in re.findall(r"[a-z']+", first)]
    for food in refused:
        names = {food, food + "s"}
        if food.endswith("y"):
            names.add(food[:-1] + "ies")
        if food.endswith("f"):
            names.add(food[:-1] + "ves")
        for place, word in enumerate(words):
            if word not in names:
                continue
            near = words[max(0, place - 5):place + 5]
            if not any(undone in _REFUSAL_UNDONE for undone in near):
                return True
            break  # the first mention is the one the answer opens on
    return False


def _offers_what_the_line_ruled_out(candidate, text, memory):
    """True when a candidate hands back the very thing the person has just ruled out.

    "what should i cook tonight" / "not curry, something else" was answered "Quick: chickpea curry
    in 25, or a sweet potato curry if you have 30 minutes" - the thing the line refused, twice -
    because the kitchen's answer outranks the composer's claim on PRIORITY, and the rule that
    passes over a reply offering a refused *food* only runs after the claims. The rule-out reading
    already knows the thing, so it is read here once and the claim is not given up to a candidate
    that offers it. A reply that names the thing in order to leave it out ("none of that was a
    curry") is answering the refusal, and keeps the turn.
    """
    if _ruledout is None:
        return False
    try:
        thing, _kept, _opening = _ruledout._rules_out_what_i_never_said(text, memory)
    except Exception:  # noqa: BLE001 - a reading that fails offers nothing
        return False
    if not thing:
        return False
    return _offers_the_food(candidate.get("reply") or "", frozenset((thing,)))


def _the_thing_the_line_ruled_out(text, memory):
    """The thing the line rules out of the answer above it, in the person's own words, or ""."""
    if _ruledout is None:
        return ""
    try:
        thing, _kept, _opening = _ruledout._rules_out_what_i_never_said(text, memory)
    except Exception:  # noqa: BLE001 - a reading that fails rules out nothing
        return ""
    return thing or ""


def _every_real_answer_offers(thing, candidates, index):
    """True when every answer above the floor hands back the thing the line just ruled out."""
    others = [candidate for candidate in candidates
              if candidate is not candidates[index] and _priority(candidate) >= 0
              and _priority(candidate) < SAFETY
              and str(candidate.get("reply") or "").strip()]
    if not others:
        return False
    return all(_offers_the_food(candidate.get("reply") or "", frozenset((thing,)))
               for candidate in others)
# A ceiling ask ("how much is too much", "how much is safe") can be answered without a figure at
# all ("no amount is safe"), so the figure test below is not used on it.
A_CEILING = re.compile(
    r"\b(?:too much|too many|max(?:imum)?|limit|safe|how much can i (?:take|have|drink|eat)"
    r"|how many can i (?:take|have|drink|eat))\b", re.I)
# Words that name no subject: a figure candidate that shares only one of these is not about the
# thing the line asks about.
GENERIC = frozenset("""
    about after again along another anything around before being better between could doing
    during enough every first found going great happy least leave might money month months never
    other people place point right should since something still take taken their there these
    thing things think those three through times today together under until usual wanted
    where which while without would wrong year years
""".split())


def _the_candidates_with_a_figure(text, memory, candidates, pool):
    """The candidates whose reply carries the figure a how-much line asks for, or the pool.

    "my car needs a service" / "how much" was answered "12 months." by the memory store, which
    had the same card's duration and not its £150 to £250, while the answers candidate had the
    price. A how-much line that asks for an amount wants a figure in a unit or a currency, so a
    candidate without one stands down when another has it. A ceiling ask is left alone, because
    "no amount is safe" is the answer and has no figure. Nothing changes when every candidate
    lacks a figure, or every one has it: the first candidate still takes the turn.
    """
    understood = memory.get("understood") if isinstance(memory, dict) else None
    if not isinstance(understood, dict) or understood.get("wants") != "amount":
        return pool
    line = str(text or "")
    if not re.search(r"\bhow much\b", line, re.I):
        return pool
    if A_CEILING.search(line):
        # A ceiling line is answered by a card, and a candidate that only hands the last answer
        # back under a repeat frame says nothing new: "how much is too much" after the paracetamol
        # card got "Same as before: <the card>" over the card itself. When every candidate is
        # framed, the pool is left as it was.
        plain = [index for index in pool
                 if not _limit.FRAME.match(str(candidates[index].get("reply") or "").strip())]
        return plain or pool
    figure = (_narrow.SIGNALS.get("money"), _narrow.SIGNALS.get("amount"))
    # The candidate has to be about the thing asked about as well as carry a figure: an
    # emergency-fund question was handed a business-funding card only because "£500 to
    # £25,000" is a figure. The subject words come from the line and the one it follows, and a
    # generic "should" or "about" is no subject at all.
    subject = {word for word in (set(WORD.findall(line.lower()))
                                 | _carried_words(memory))
               if len(word) >= 5 and word not in GENERIC}
    with_figure = []
    for index in pool:
        reply = str(candidates[index].get("reply") or "")
        if not any(signal and signal.search(reply) for signal in figure):
            continue
        if subject:
            said = {word for word in WORD.findall(reply.lower()) if len(word) >= 5}
            if not any(_the_same_word(word, one) for word in subject for one in said):
                continue
        with_figure.append(index)
    return with_figure if with_figure and len(with_figure) < len(pool) else pool


# The shapes a check can read out of the reply's own words and hold a candidate to. `fit` says
# None for the rest (an opinion, a condolence), and those are left exactly as they are.
def _the_candidates_that_give_the_shape(text, memory, candidates, pool):
    """The candidates whose reply gives the shape of answer the line asked for, or the pool.

    The figure rule below was the first of these and the only one: a how-much line was owed a
    figure, and a candidate without one stood down when another had it. The same is true of every
    shape the understanding lane's reading can name - a time, a place, a person, a pick, a yes or
    a no, the steps, the reason, the meaning - and the shape is not the composer's business, so it
    is read once, in `bot/compose/fit.py`, and honoured here for all of them. "my boiler keeps
    losing pressure" / "is that normal" was answered by the memory store reading the last answer
    back under a repeat frame while the composer's verdict line was in the candidates.

    Only a candidate that *definitely* misses the shape stands down, and only for one that
    definitely gives it: where the words cannot tell, the order is left alone. `amount` keeps its
    own reading, because a figure has to be in a unit or a currency and has to be about the thing
    the line named, and that care is worth keeping.
    """
    understood = memory.get("understood") if isinstance(memory, dict) else None
    if not isinstance(understood, dict):
        return pool
    want = understood.get("wants")
    if not want:
        return pool
    if want == "amount":
        return _the_candidates_with_a_figure(text, memory, candidates, pool)
    if want in fit.SOFT:
        return pool
    if not pool or fit.gives(str(candidates[pool[0]].get("reply") or ""), want, text) is not False:
        return pool
    giving = [index for index in pool[1:]
              if fit.gives(str(candidates[index].get("reply") or ""), want, text) is True]
    if not giving:
        return pool
    return giving + [index for index in pool if index not in giving]


def _the_same_word(one, other):
    """True for the same word, or a plural or a short ending of it ("service"/"services")."""
    if one == other:
        return True
    short, long = sorted((one, other), key=len)
    return len(short) >= 5 and long.startswith(short) and len(long) - len(short) <= 2



def _choose(text, memory, candidates):
    real = [index for index, candidate in enumerate(candidates) if _priority(candidate) >= 0]
    if not real:
        return 0
    best = real[0]
    last = _last_reply(memory)
    if _priority(candidates[best]) >= SAFETY:
        return best  # the safety band is answered as it comes, before the never-repeat rule
    # One check, for every module: a reply that talks about the conversation needs one to have
    # happened, and this is the place every candidate passes through. It is made here as well as
    # in the pools (`bot/modules/chat.py`) because the reading is what has to be shared, not the
    # guard: another module's reply can refer to an earlier turn too, and on the first line of a
    # chat there is none. Where every candidate refers to a chat, the top one stands - a reply
    # still has to be given.
    if not onscreen.earlier_turn(memory):
        fresh = [index for index in real
                 if not onscreen.talks_about_the_conversation(candidates[index].get("reply"))]
        if fresh:
            real = fresh
            best = fresh[0]
    # A condolence is not the answer to a question about why a living thing is failing: the entry
    # that names the thing answers the cause that was asked for, and it is read before the claims
    # because the condolence's own module is the one that claims the line. See
    # `_the_cause_asked_for`.
    cause = _the_cause_asked_for(candidates, real, text, best)
    if cause is not None:
        return cause
    # A verdict on the news has no subject of its own, so nothing may answer it with the topic of
    # the conversation: not the same-advice path, and not an entry that owns the verdict's noun
    # ("Nightmares usually follow stress"). The composer has the line for it, so the turn is the
    # composer's, taken before the claims - except in a thread that is not a light one, where the
    # safety continuation or the grief answer stands.
    verdict = _verdict_reply(candidates, text, memory, last, clean=text, best=best)
    if verdict is not None:
        return verdict
    held = _as_it_comes(text, memory, candidates, last)
    if held is not None:
        # A how-much line is owed a figure even when the claim is a recall of the card: "my car
        # needs a service" / "how much" was claimed as "12 months." while the answer's £150 to
        # £250 was in another candidate. See `_the_candidates_with_a_figure`.
        with_figure = _the_candidates_that_give_the_shape(
            text, memory, candidates, [held] + [index for index in real if index != held])
        if held not in with_figure:
            held = with_figure[0]
        # A claim is the whole of the reason to take the turn, so it is only given up to a module
        # that says the line is its own answer at a higher PRIORITY: a claim from the fallback
        # band never beats a specialist that read the line, and a claim from a module above it
        # still does.
        instead = _claims_instead(text, memory, candidates, last, _priority(candidates[held]))
        if instead is not None and _offers_what_the_line_ruled_out(candidates[instead], text, memory):
            instead = None
        return held if instead is None else instead
    pool = _the_candidates_that_give_the_shape(text, memory, candidates, real)
    real = pool
    # The fact the person has just stated in the very line they are asking about is not something
    # to recall: "my sister is veggie and shes coming to dinner, what can i cook" was answered
    # "Your sister is veggie." The store claims a line for the fact in it, at the recall band,
    # while the cooking answer sits beside it at 0 - the fact was never in doubt and the ask after
    # it was. A reply made of nothing but the words the person has just used has told them nothing
    # at all, so it stands down for one that answers the ask.
    answering = _the_candidates_that_answer_the_ask(text, candidates, pool)
    if answering is not None:
        pool = answering
        real = answering
    # The candidate in front offers the very food the line refused, and another real candidate
    # does not: "im trying to eat better but i hate veg" got the balanced-meal card ("Half the
    # plate vegetables or salad"), which is the one thing the line had ruled out, while the store
    # had already answered the refusal. The refusal is read once by the kitchen, and only the
    # reply's opening sentence is checked (`_offers_the_food`), so a substitute that names the
    # food to leave it out keeps its turn. The safety band and a pool where every candidate
    # offers it are left exactly as they were.
    refused = _the_food_the_line_refused(text, memory)
    if refused:
        respecting = [index for index in pool
                      if not _offers_the_food(candidates[index].get("reply") or "", refused)]
        if respecting and len(respecting) < len(pool):
            pool = respecting
            real = respecting
    if last:
        # A reply that says the last answer again with a nod in front ("Same as before: ...",
        # "You've got it: ...") is not a second answer, so it is passed over whenever a real
        # candidate has something new to say. Fallbacks are not counted here: a stock line is not
        # a reason to drop an answer, and STYLE.md would rather have the answer twice than a shrug.
        # A search hedge is not something new to say. "I don't know enough to answer that
        # honestly. A search should sort you out quickly" was given the turn over the answer the
        # bot had just read out, so a bare "what helps" was met with a shrug on a subject it had
        # answered a turn before. The answer said again is better than that, so a hedge never
        # counts as the fresh candidate the repeat is passed over for.
        #
        # The same goes for a whole answer the bot already gave this person two or more turns
        # back: "when should i do that", nine turns into a chat about a boy starting secondary
        # school, was handed the walk-the-route paragraph from the first turn word for word, while
        # the composer had a line about what to ask him. Only an answer the conversation has
        # already moved past is dropped, and only when the candidate in front of it is not one:
        # a line that asks to hear it again ("what did you say") keeps it, and so does the same
        # question asked twice in a row.
        #
        # A reply that only points back at the answer above is the same shrug in better words:
        # "Everything I know on that one is in the answer above" is new wording that says where
        # the answer is. See `_points_back`.
        heard = _said_before(memory, text)
        fresh = [index for index in pool
                 if _content(candidates[index].get("reply")) != last
                 and not _echoes(candidates[index].get("reply"), last)
                 and not fallback.is_a_hedge(candidates[index].get("reply"))
                 and not _points_back(candidates[index].get("reply"))]
        if fresh and _content(candidates[pool[0]].get("reply")) not in heard:
            fresh = [index for index in fresh
                     if _content(candidates[index].get("reply")) not in heard] or fresh
        if fresh:
            pool = fresh
        else:
            if len(pool) > 1:
                # Every candidate says the last answer again, so this turn is a repeat whichever
                # one wins, and the one that repeats least is the best of them: "The thing to do
                # first: put a tall scratching post by the corner she uses" is a nod plus the one
                # step, while the knowledge entry behind it is the whole paragraph read out a
                # second time. It has to be an echo of the answer itself (so a short new answer is
                # never taken for one) and clearly shorter than the longest repeat beside it.
                shortest = min(pool, key=lambda i: len(_content(candidates[i].get("reply"))))
                longest = max(len(_content(candidates[i].get("reply"))) for i in pool)
                if (_echoes(candidates[shortest].get("reply"), last)
                        and len(_content(candidates[shortest].get("reply"))) * 3 <= longest * 2):
                    return shortest
            # Every module with a real claim on the line only says the last answer again: the
            # knowledge entry reads the follow-up as the same question and hands back the opening
            # of the answer just given, word for word. Nothing else is in the race, so the same
            # sentence twice is what the person gets - unless the composer has read the line as a
            # repeat and said so. That line is the only new thing on the table, and it is a
            # question about the answer rather than a shrug, so it takes the turn. It is the
            # composer's own reply, never a raised PRIORITY (see bot/compose/fallback.py,
            # `says_it_already`).
            # The composer's own short form of that answer is a cut of it, not a second telling,
            # so it is the one line here with something the person has not read. Read before the
            # said-it-already line, which asks whether what the cut lost is what they asked
            # about, because a bare "what?" asks for nothing the cut has to keep.
            shorter = _a_shorter_said_again(candidates, last)
            if shorter is not None:
                return shorter
            said = _said_it_already(candidates, text, memory, last)
            if said is not None:
                pool = [said]
            else:
                choice = _a_choice_the_answer_did_not_make(candidates, text, memory, last)
                if choice is not None:
                    pool = [choice]
                elif not [index for index in pool
                          if _content(candidates[index].get("reply")) == last]:
                    # Every real candidate is a slice of the last answer rather than the whole of
                    # it, and the composer has no line of its own about the repeat. A slice read
                    # back can still answer a narrower question ("and what does a major mean" is
                    # in the fail-sheet sentence word for word), so it is only given up to a
                    # fallback line that says what to do about the thing - see
                    # `_answers_this_line`. The composer's own shrug ("Got it - it goes off in two
                    # days") answers nothing, so it never takes the turn off the slice, and the
                    # whole answer said again is left alone either way.
                    unheard = [index for index, candidate in enumerate(candidates)
                               if not _echoes(candidate.get("reply"), last)
                               and _answers_this_line(candidate.get("reply"))]
                    if unheard:
                        pool = unheard
                    # Every real candidate only points back at the answer above, and a line
                    # that carries a piece of that answer is on the table. A reply that only says
                    # where the answer is has answered nothing, so the line that says something
                    # takes the turn: "how much does a boiler cost" / "how long does it take to
                    # fit" / "what about a new one" was told "Everything about a new is in what I
                    # said above - there is no more than that", while the composer had "For a new
                    # one: Fitting a new one is the long job." The reading of "a piece of the
                    # answer" is the composer's, which the arbiter already asks for elsewhere
                    # (`_carries_the_answer`), so a stock line, a hedge or a passing mention
                    # never takes a turn this way.
                    if all(_points_back(candidates[index].get("reply")) for index in pool):
                        says = [index for index in range(len(candidates))
                                if not _points_back(candidates[index].get("reply"))
                                and not fallback.is_a_hedge(candidates[index].get("reply"))
                                and _carries_the_answer(candidates[index].get("reply"), memory)]
                        if says:
                            pool = says

    # A take from the chatter band is picked on what the line was read as - a feeling, a kind of
    # day - and it says nothing of the line itself, because a stock line never can. That is right
    # where the reading was the whole of the line, and wrong where a card beside it answers the
    # thing the person actually named: the pool for a lonely week answered "my bins were left out
    # and not emptied" over the council card that says what to do about the missed collection. So
    # a chatter take that shares no word with the line stands down for a card that shares one, and
    # every line whose words the take does say is left exactly as it was.
    named = _a_card_that_names_the_line(candidates, pool, text, memory)
    if named is not None:
        return named
    best = pool[0]
    own, carried, words, clean = _about(text, memory)
    # The same ask one turn later, in the thread of a condolence: "how do i tell a 4 year old".
    # A card that matches "a 4 year old" answers how much screen time is right, which is not the
    # question, and no knowledge entry is in the candidates to lose to.
    child_words = _the_words_for_the_child(candidates, clean, memory, last)
    if child_words is not None and not _a_whole_line_module_spoke(candidates):
        return child_words
    # A thank-you is not a question about the world. "cheers" after "what can i do with a bag
    # of frozen spinach" was answered with the spinach entry a second time: the reading hands a
    # follow-up the topic the conversation is on, so the knowledge base had "cooking" to match
    # and the small-talk candidate had nothing but its own priority. On a line the understanding
    # engine reads as politeness alone there is no topic of the line's own to match, so the topic
    # rule is skipped and the turn goes to the highest PRIORITY: the seed rule the bands are for.
    polite = _only_acknowledges(memory)
    here = _a_presence_check(memory)
    ask = _the_ask_about_a_child(candidates, clean, last)
    if ask is not None:
        return ask
    gave = _the_name_they_gave(candidates, text, memory)
    if gave is not None:
        return gave
    drafted = _draft_index(candidates, last, clean)
    if drafted is not None:
        return drafted
    # The card for the speaker's own life does not answer a how-to about somebody else.
    about_them = _about_the_person_the_line_names(candidates, pool, clean, last)
    if about_them is not None:
        return about_them
    instead = _instead(text, candidates, last, own, clean)
    if instead is not None:
        return instead
    # A line that says the person is going is not a question about its reason clause: "ill let
    # you go, dinner is burning" was answered "take it off the heat". The composer owns the
    # reading and the wording (bot/compose/leaving.py); this is only the routing decision.
    bye = _leaving_reply(candidates, own, carried, words, clean, text, memory, last)
    if bye is not None:
        return bye
    left = _a_leaving_said_plain(candidates, pool, clean, memory)
    if left is not None:
        return left
    sudden = _sudden_loss_reply(candidates, pool, clean)
    if sudden is not None:
        return sudden
    bot_answer = _about_the_bot(candidates, clean, last)
    if bot_answer is not None:
        return bot_answer
    # When a named place opens is not a fact any entry can hold, so the composer's honest line
    # answers it rather than an entry that took the line on one other word. See
    # `_the_venue_hours_turn`.
    hours = _the_venue_hours_turn(candidates, clean, last, text)
    if hours is not None:
        return hours
    # A question about the bot's own taste has no entry in the knowledge base: "do you have a
    # favourite food" was answered with a list of dishes to cook and "whats your favourite thing
    # to talk about" with advice on starting conversations. Both are good answers to the
    # questions they were written for and neither is an answer to what this person asked, so the
    # composer's taste takes the turn from a card that only matched the noun.
    own_taste = _the_bots_own_taste(candidates, clean, memory, last)
    if own_taste is not None:
        return own_taste
    corrected = _store_correcting(candidates, pool, memory, text, last)
    if corrected is not None:
        return corrected
    # The store taking its own suggestion apart when the line says what is out of it. It is the
    # only module that read the dislike, and its reply is the answer in hand with that one thing
    # gone, so no entry can answer in its place.
    revised = _the_store_revises_the_answer(candidates, pool, memory, text, last)
    if revised is not None:
        return revised
    # A bare "where do i start" asks for the one step out of the answer in hand, and the entry
    # that wrote that answer writes it again - in its other wording, at full length - when the same
    # line reaches it. That second paragraph is not a better answer than the composer's short form
    # of the answer, so the step takes the turn. See `_the_move_in_hand`.
    step = _the_move_in_hand(candidates, real, text, last)
    if step is not None and not _points_back(candidates[step].get("reply")):
        return step
    # The same ask, where no candidate re-tells the answer: two modules hand the step back and the
    # one in front stops at the answer's own comma, so half of the instruction is handed over. The
    # composer keeps the answer's sentence, and on this ask that is the reply to give.
    whole = _the_whole_move(candidates, real, text, last, _the_answer_written_out(memory))
    if whole is not None and not _points_back(candidates[whole].get("reply")):
        return whole
    # "what else" after a step asks for the next part of the same answer, and the entry that wrote
    # it answers with the whole paragraph again. The memory lane has the next part, so it takes the
    # turn. See `_the_next_part`.
    more = _the_next_part(candidates, text, last)
    if more is not None and not _points_back(candidates[more].get("reply")):
        return more
    # "when do we fly", "when is my dentist appointment": the person has already told the bot the
    # date, and a knowledge card about the subject answers a different question than the one asked.
    dated = _the_date_fact(candidates, real, text)
    if dated is not None:
        return dated
    # The next line of a hard story is not a request about its words: after "my wife left me",
    # "she packed her things last night" matched the moving entry and got a removals checklist.
    # The composer's listening line keeps the floor with them instead. Only the composer's own
    # pool can take the turn here, and only for a line that is not a question.
    hurt = _hurting_reply(candidates, pool, clean)
    if hurt is not None:
        return hurt
    story = _story_goes_on_reply(text, memory, candidates, last)
    if story is not None:
        return story
    paused = _pause_reply(candidates, pool, text, memory, last)
    if paused is not None:
        return paused
    if not own and not carried and not words:
        return best
    # The line as typed, not the normalised one: the composer picks its continuation from the
    # words in front of it, and "you there?" inside a live emergency thread must get that thread's
    # line back, not whatever "you there" alone reads as. Stripping the mark cost the thread.
    kind, target = _composer_reading(text, memory)
    if kind in (THREAD, CARE_THREAD):
        keeping = _thread_index(candidates, real, _named_topics(memory), target, last,
                                care_about=clean if kind == CARE_THREAD else "", memory=memory)
        if keeping is not None:
            return keeping
    if polite or here:
        return pool[0]
    fit_own, fit_carried = _fit(own, carried, memory, _priority(candidates[best]),
                                 candidates[best].get("reply") or "",
                                 candidates[best].get("module") or "", text)
    best_score = _match(candidates[best].get("module"), fit_own, fit_carried, words, clean)
    # A follow-up that asks what to do next is answered from the answer the person was given a
    # turn ago, and that answer is what the composer's line carries. An entry that answers the
    # conversation's topic but none of the answer's words is a different fact, and taking the turn
    # with it reads as a change of subject: after "my son wont eat vegetables" / "what do i do",
    # "what should i do" got "Five a day is 400g, and a portion is a handful" instead of the step.
    # Only a claim on a topic the line does not name is held to this, so "and how long?" after a
    # cooking answer still belongs to the cooking entry.
    kept = _carries_the_answer(candidates[best].get("reply"), memory)
    named = _named_topics(memory)
    # A generic step from the composer is what the person gets when nothing behind it can be
    # handed on. An entry that already tells them what to do answers the same question with the
    # thing itself, so the step stands down: after "im lonely" / "what can i do" the loneliness
    # entry says "Do the inviting yourself, and make it the same thing each week", and the
    # composer's first-step line took the turn off it. Wording only, so no entry is read as a
    # repeat it is not, and a step the person asked for by name is still the composer's (the
    # rule above, before this one).
    if _is_a_generic_step(candidates[best].get("reply")):
        for index in pool[1:]:
            entry = candidates[index].get("reply")
            if entry and not _is_a_generic_step(entry) and _opens_on_a_job(entry):
                return index
    recall_from_earlier = _a_recall_from_an_earlier_turn(text, memory)
    for index in pool[1:]:
        if (recall_from_earlier
                and candidates[best].get("module") in MEMORY_MODULES):
            # The store has answered a line that asks what was said earlier. A topic entry that
            # scores on one of the line's words is answering a different question, so it does not
            # take the turn on that score alone.
            continue
        if (not _names_the_subject(candidates[index], memory, words)
                and _reads_the_doubt(candidates[pool[0]])):
            continue
        score = _match(candidates[index].get("module"), fit_own, fit_carried, words, clean)
        if score <= best_score:  # ties keep the higher PRIORITY, which comes first
            continue
        # About the line's subject, and not only about one of its words: the candidate in front
        # is about what the person said and the entry lifting past it is about something else
        # that shares a topic label with it. See `_about_the_line`.
        if (_about_the_line(candidates[best].get("reply"), words, clean)
                and not _about_the_line(candidates[index].get("reply"), words, clean)):
            continue
        # A report of a step the person has just taken is not a request for that step again. After
        # "i had a row with my sister" / "i already told her sorry" the relationships entry scored
        # on the topic and answered "Name what you did, say why it was wrong ... I'm sorry": the
        # advice the person had just told the bot they had taken. The store read the line ("Good.
        # What happened when you did?"), and it is the store's reply that belongs here, so an
        # entry that still hands over that step does not take the turn on its topic alone. The
        # reading is the store's (`already.tells_them_the_step_again`), and it is only consulted
        # when the candidate in front does not repeat it as well.
        if (_already is not None
                and _already.tells_them_the_step_again(candidates[index].get("reply"), text, memory)
                and not _already.tells_them_the_step_again(candidates[best].get("reply"),
                                                           text, memory)):
            continue
        if kept and _match(candidates[index].get("module"), named, carried, words, clean) <= 0:
            entry = candidates[index].get("reply")
            if not (_carries_the_answer(entry, memory) or _opens_on_a_job(entry)):
                continue
        best, best_score = index, score
    # The person asked the bot to rule on their plan and the front of the list rules on nothing:
    # "im thinking of quitting my job" / "is that a good idea" was answered "I cannot call that one
    # for you. Tell me what matters most about quitting my job and I will help you think it
    # through", while the card under the floor had the answer the bot can give ("Yes - quitting
    # your job is worth doing. The one thing to have ready is an answer for what if it goes
    # wrong."). A hand-back is not an answer to a judgement - it is the answer to not knowing what
    # to say - so a card that names the subject of the thread takes the turn off it. Only the ask
    # itself is read here, and only a card that names the subject: an ack ("Alright then") is the
    # same shrug in shorter words, and a card about something else is not an answer either.
    # See STYLE.md, "say what you think" against "I cannot call that one for you".
    #
    # The card can be above the floor too: the judgement asked for is often one the answer in hand
    # already made, and then the module that made it hands its own sentence back - "is that fair"
    # after the answer about a dog alone all day got chat's "Sounds good." while the card beside it
    # said "What is not fair is a puppy, or ten hours with no break at all." That is the same shrug
    # in shorter words against the same answer, so the rule reads every candidate that is not the
    # front one; the safety band is left alone, because it answered already (`_choose` returns it
    # first) and a card must not pull a crisis line out from under the person.
    front = candidates[best].get("reply")
    if (_hands_the_decision_back(front)
            or (candidates[best].get("module") == "chat"
                and _content(front) in _ack_lines())) \
            and (_asks_a_question(memory) or _asks_for_a_judgement(text, memory)):
        already_read = _said_before(memory, text)
        for index in range(len(candidates)):
            if index == best or _priority(candidates[index]) >= SAFETY:
                continue
            reply = candidates[index].get("reply")
            # ...and a card that hands back an answer the person has already read is not an answer
            # to a hand-back either: "im thinking of getting a cat" then "will that work" was
            # given the whole cat card again - the card was pulled in here, past the never-repeat
            # rule, because the front line handed the decision back and the card names the cat.
            # The person had read every word of it a turn ago, so the repeat is no better than the
            # hand-back and it reads as the bot not listening. A card they have not read is
            # untouched, which is what this rule is for.
            if (_content(reply) in already_read
                    or (last and _echoes(reply, last))):
                continue
            if _names_what_they_said(reply, text, memory):
                return index
    return best


LONG_ENOUGH = 4


def _about_the_line(reply, words, clean=""):
    """Whether a reply names something of the subject the line is on.

    A topic label is not the subject: "i told the school and nothing happened" is read as a
    family-and-parenting line and a school-and-study line, and the entry that answered it was
    the sleep card ("Get up after 20 minutes of lying there awake ..."), which names nothing the
    person said. The candidate in front named the school and the meeting.

    So a lift by topic alone is checked against the words: a reply that shares one of the line's
    own subject words is about it, and a shared word is not enough on the other side of the test
    either - the candidate in front has to name what was said before a lift is held back at all.
    """
    said = [word for word in WORD.findall(str(reply or "").lower()) if len(word) >= LONG_ENOUGH]
    if not said:
        return False
    for word in words or ():
        if len(word) < LONG_ENOUGH:
            continue
        for one in said:
            if one.startswith(word) or word.startswith(one):
                return True
    return False


def _names_the_subject(candidate, memory, words):
    """Whether an entry may take a bare yes-or-no doubt that names no subject of its own.

    "is that bad" after "blood in my pee", "is that normal" after "my cat sleeps a lot": the
    question carries nothing but the doubt, so the subject is the line before it, and an entry
    that fits by inheriting the conversation's topic can be about something else entirely. The
    sleep entry answered a cat with "Most adults do best on seven to nine hours", the
    carbohydrate entry answered "can i freeze rice" with "Carbohydrate is not fattening in
    itself", and the repeat line answered a humming fridge with "Everything about normal is in
    what I said above". The composer's line for the doubt itself ("Yes, that is the usual thing
    - what to keep an eye on is change rather than the thing itself") was in front of every one
    of those and lost.

    So on a bare doubt the entry has to name the subject too: a word of the line the conversation
    is on, in the reply. A card that shares it (the kettling entry answering "my boiler is making
    a kettling noise", the chicken entry answering "can i freeze the leftovers") keeps its turn.
    A card that shares nothing is answering a different question and stands down.

    Only a bare doubt is held to this: a line with words of its own ("is that bad for the
    freezer", "is that normal for a 14 year old cat") names its subject itself and is read by
    the ordinary specialist rule.
    """
    if not _a_bare_yes_no(memory):
        return True
    if _carries_the_answer(candidate.get("reply"), memory):
        # The entry comes back to the answer the bot gave a turn ago, so the subject is its own
        # by construction, whatever words the two happen to share. "my calf hurts" / "is that
        # bad" is answered by the calf entry again, and its wording ("For a joint or muscle that
        # aches ... ibuprofen gel") names neither "calf" nor "hurts": a test on the topic's
        # words alone stood it down for the composer's "Nothing in that answer needs anyone yet",
        # which says less than the entry it displaced. Found in review by @smooth-lark.
        return True
    subject = _carried_words(memory) - set(words) - DOUBT_WORDS
    if not subject:
        return True
    reply = _content(candidate.get("reply")).split()
    for word in subject:
        if len(word) < 4:
            continue
        for said in reply:
            if len(said) >= 4 and (said.startswith(word) or word.startswith(said)):
                return True
    return False


# The words a bare doubt is made of: they sit in the reply ("that is the usual thing") and in
# the line the doubt inherits, and they name no subject, so they are not what the entry has to
# share.
DOUBT_WORDS = frozenset("bad normal okay fine good safe right wrong better worse serious worry "
                        "worried thing things that this it is be to a an the for of".split())


def _reads_the_doubt(candidate):
    """True when the reply in front of the entry is the composer's own ruling on the doubt.

    A bare doubt ("is that bad", "is that normal") is answered by the composer's line for it, so
    an entry that only inherits the conversation's topic stands down (`_names_the_subject`). That
    trade is only worth making when the line in front actually rules on the doubt: "is that
    normal" after "my cat sleeps a lot" gets "Yes, that is the usual thing - what to keep an eye
    on is change rather than the thing itself", which reads the doubt, where the entry it
    displaced was the human sleep card.

    Three reviewers measured what happens when the front is something else, and every one of them
    named the same fix:

    - a nod or a farewell. "Alright then - good luck with it." after "im allergic to shellfish /
      is that bad" (@grand-gopher), and "Sounds good." after "i owe about 4000 on my credit card /
      im paying 60 a month / is that enough".
    - a hand-back or a search hedge. "I cannot call that one for you" after "im thinking of
      getting a rescue dog / is that a good idea" displaced the entry that answered (@smooth-lark).
    - a note about the answer. "Nothing in that answer needs anyone yet" after "my calf hurts / is
      that bad" took the turn off the aching-joint card (@smooth-lark).
    - a floor, which asks how long and rules on nothing. "How long has it been going on?" after "i
      take ibuprofen most days / is that ok" took the turn off the dose card (@grand-gopher,
      @neat-moth).
    - a card about something else. "why does my cat scratch its ears / should i clean her ears"
      stood the earwax card down for a cat-scratch-wound card, which is a vocabulary gap rather
      than a reading (@smooth-lark's warning).

    So the test is positive rather than a list of shapes to exclude: the pools in
    bot/compose/verdict.py that rule on a doubt are named there (`RULED_BY_THE_COMPOSER`,
    `rules_on_the_doubt`), and anything else leaves the entry its turn. One rule here instead of
    five negative ones, and a pool that gains a ruling line needs no change in the arbiter.
    """
    try:
        from ..compose import fallback as composer, verdict as opinions
        said = candidate.get("reply")
        return opinions.rules_on_the_doubt(said) or composer.is_said_it_already(said)
    except Exception:  # noqa: BLE001 - a composer that cannot answer leaves the entry its turn
        return False


def _a_bare_yes_no(memory):
    """True when the line asks yes or no and names no topic of its own ("is that normal")."""
    understood = memory.get("understood")
    if not isinstance(understood, dict):
        return False
    if _line_topics(memory):
        return False
    return "yesno" in _labels(understood.get("asks"))


def _carried_words(memory):
    """The words of the line the conversation is on, which a bare follow-up inherits."""
    topic = memory.get("topic")
    if isinstance(topic, dict):
        labels = _labels(topic.get("words"))
        if labels:
            return labels
        text = topic.get("text")
        if isinstance(text, str) and text.strip():
            return set(WORD.findall(text.lower().strip()))
    return set()


def _fit(own, carried, memory, best_priority, reply="", claimant="", text=""):
    """The topics the specialist rule may count, and the ones it may only count weakly.

    The reading gives a turn two topic sets: the line's own (`understood["topics"]`) and the one
    the conversation is on (`understood["topic"]`, which on a follow-up is put back in). Both
    count 2 in `_match`, because on a follow-up the second is the only topic there is.

    A line that names no topic of its own is not about the topic of the conversation, though: it
    is about the conversation. "what am i doing this week" after "im writing up my thesis" was
    read as a language-and-writing line by inheritance alone, and the essay-thesis entry took
    the turn from the memory store's own answer ("You're writing up your thesis."), which is the
    answer to what was asked. So when the candidate in front sits in the recall band (README,
    "Routing": the memory store reads a line about what was said), only a specialist the line
    itself supports - its own topics, a phrase or a word it contains - may take the turn from
    it. The recall band is the only band this applies to: the safety band is answered before
    this function is reached, and the loss and grief bands already answer in place of the
    entries (`_instead`).

    The same holds for a line that asks for the answer again. Its measure word is read as a topic
    of its own - "how long did you say" is a maths-and-numbers line - but it is not a subject the
    line is about, so the conversation's topic is not counted for it either: the entry that wrote
    the answer reads the pointer as the same question and hands the whole answer back, while the
    memory store has the part the person asked for. See `_asks_for_the_answer_again`.

    And it holds for a line that asks about the conversation in some other way: a recap of the chat
    is not the topic its words name, so the module in front publishes that reading
    (the store's `_about_this_chat`) and nothing is counted against the recall band on it. See
    `_asks_about_the_chat`.
    """
    if best_priority >= RECALL:
        # Only when the recall band has the part they asked for. When its own line is the last
        # answer said again ("Again - About 20 minutes per 500g ..."), the entry's card is the
        # better of the two and keeps the turn it had.
        repeat = _asks_for_the_answer_again(memory)
        if repeat and not _echoes(reply, _last_reply(memory)):
            return set(), set()
        # A line that asks about the conversation is the recall band's, whatever topic its words
        # point at. "my boiler keeps losing pressure" then "what have i been saying about the
        # boiler" is read as a home line from the word "boiler", and the specialist rule let the
        # boiler entry answer it with its how-to instead of the store's line about what the
        # person said. "im saving for a car" then "what am i saving for" did the same with money.
        # The store's own gate reads these shapes (`_about_this_chat`), so the arbiter keeps
        # no word list: a recap is not the topic it names, and the conversation's topic does not
        # stand in for it either. A repeat ask is decided by the rule above: it is a reading of
        # the answer in hand, and on "when did you say" the card that gave the timing keeps the
        # turn rather than the store saying its own last line again.
        if not repeat and claimant and _asks_about_the_chat(claimant, text, memory):
            return set(), set()
        if not _line_topics(memory):
            return set(), carried
    return own, carried


def _line_topics(memory):
    """The topic labels the understanding engine read from this line by itself, never inherited."""
    understood = memory.get("understood")
    if not isinstance(understood, dict):
        return set()
    return _labels(understood.get("topics"))


# A line that asks for the answer again points at what the bot said and names nothing else.
POINTS_BACK = re.compile(
    r"\b(?:did|do|does|were|was|have|had)\s+(?:you|u)\s+(?:say|said|tell|told|mention)\b"
    r"|\b(?:you|u)\s+(?:said|say|told|mentioned)\b|\bagain\b")
# Every other word a repeat ask can be made of. The words left over are the line's own subject,
# and a line with one of those is a new ask that happens to point back: "when can i play football
# again" is about the football, and "how old is she again" is about the age.
REPEAT_FRAME = frozenset("""
    a again already an and earlier before but did do does exactly for had has have how is it
    just long many me mention mentioned much now of okay one please say said sayd so sorry tell
    that the them then this to told u us was were what when which you
""".split())


def _asks_for_the_answer_again(memory):
    """Whether the whole line is a pointer back at what the bot said, with no subject of its own.

    The measure words are read as a topic of their own: "how long did you say" and "when did you
    say" after a sprained ankle came back as maths-and-numbers lines, so the specialist rule let
    the ankle card repeat its whole answer while the memory store's length line - the answer to
    what was actually asked - sat behind it. A line made only of the pointer and the measure names
    no topic of its own: it is about the conversation, and the recall band answers it.
    """
    understood = memory.get("understood")
    if not isinstance(understood, dict):
        return False
    text = str(understood.get("clean") or understood.get("text") or "").lower()
    if not POINTS_BACK.search(text):
        return False
    return not [word for word in re.findall(r"[a-z']+", text) if word not in REPEAT_FRAME]


def _a_choice_the_answer_did_not_make(candidates, text, memory, last=""):
    """The fallback to take the turn when a choice was answered with the rest of the last reply.

    Asked only when every real candidate says the last answer again (see `_choose`). A stock line
    is no reason to drop an answer, but the rest of an answer is not an answer to a choice: "is it
    worth fixing or shall i just get a new one" after the bang on the spin got the sentence about
    the transport bolts (a slice of the answer the person had already read past), while the
    composer's own repair-or-replace pool had the line they needed. So on a line whose reading
    asks to choose between options (`understood["asks"]` holds `choice`), a fallback with words
    of its own takes the turn from a repeat.

    Only a choice ask, and only words the last reply does not already hold: the same question
    asked twice is answered by the same answer, and there the repeat is the reply.

    A shrug is not the choice made, so the two shapes of it are passed over: the hedge that says
    the bot cannot call it, and the line that only points back at the answer above. "my fridge is
    on its last legs" then "should i get it repaired or a new one" had the repair-or-replace card
    ("Repair it while a fix is well under half the price of a new one") in the candidates and was
    handed the composer's "Can't call that one for you, sorry. Say what you'd lose either way and
    I'll lay it out with you" instead, because it was the only reply in the fallback band whose
    words the answer above did not already hold. The card answers the choice; the shrug asks for
    the information again. `_choose`'s own filter drops hedges for the same reason.
    """
    understood = memory.get("understood")
    if not last or not isinstance(understood, dict):
        return None
    if CHOICE not in _labels(understood.get("asks")):
        return None
    for index, candidate in enumerate(candidates):
        if _priority(candidate) >= 0:
            continue
        reply = _content(candidate.get("reply"))
        if not reply or reply == last or _echoes(reply, last):
            continue
        if fallback.is_a_hedge(candidate.get("reply")) or _points_back(candidate.get("reply")):
            continue
        return index
    return None


def _a_shorter_said_again(candidates, last):
    """The index of the composer's own shorter form of the last answer, else None.

    Asked only when every real candidate only says the last answer again (see `_choose`), and
    only for a line the composer wrote as a cut of that answer: the frame is the module's and the
    words behind it are the answer's own, in its own order. That is what makes it new - a person
    who typed "what did you say" has read the paragraph once already - and it is why a stock line
    in the fallback band is never taken for one.
    """
    if not last:
        return None
    for index, candidate in enumerate(candidates):
        if _priority(candidate) >= 0:
            continue
        if fallback.is_the_answer_shorter(candidate.get("reply"), last):
            return index
    return None


def _said_it_already(candidates, text, memory, last=""):
    """The index of the composer's said-it-already reply, when it is the only new thing here.

    Asked only when no real candidate has anything new to say (see `_choose`). The composer owns
    both halves of this - the reading of the line as a repeat and the wording - so the arbiter
    only recognises the line and lets it through; it keeps no vocabulary of its own.

    Only a repeat that has lost something counts. The whole answer said again still answers a
    narrower question ("what about tea" is in the answer about water, word for word) and STYLE.md
    would rather have it twice than a shrug; the opening of it, with the rest gone, does not.
    """
    if not last or not fallback.says_it_already(text, memory):
        return None
    real = [candidate for candidate in candidates if _priority(candidate) >= 0]
    if not real:
        return None
    first = _content(real[0].get("reply"))
    if not _echoes(first, last) or len(first.split()) >= len(last.split()) - 3:
        return None
    # ... and only when what is gone is what they asked about. "What about tea" is answered by
    # the shortened line about water, which names tea, so it still answers the question; "how do
    # i free up space" is not answered by the opening, which names the space and drops every way
    # of freeing it.
    # The words of a figure ask are the asking, not the thing asked about. "how many times a
    # week" is answered by "Three runs a week", and "times" is nothing the answer had to keep, so
    # the repeat was read as one that had lost what was asked and the person got "That is all of
    # what I know on it" instead of "Three runs a week gets most people to 5k in about eight
    # weeks". The ask is stripped with the store's own patterns (`repeat.FIGURE_ASKS`), which is
    # the reading `repeat.the_figure_asked` makes of the same line, so a figure ask added there
    # is read here too.
    subject = str(text or "")
    for figure in getattr(_repeat, "FIGURE_ASKS", ()) or ():
        try:
            _name, ask, _says = figure
        except (TypeError, ValueError):
            continue
        # Every ask that the line matches, each read against the whole line, and the shortest
        # result wins: "how many times a week" is one ask for a count ("how many") and one for a
        # rate ("how many times"), and stripping them one after the other leaves "times" behind
        # because the second no longer matches what the first left. The thing asked about is
        # what is left when as much of the asking as possible has been taken out.
        try:
            if ask.search(str(text or "")):
                shorter = ask.sub(" ", str(text or ""))
                if len(shorter) < len(subject):
                    subject = shorter
        except AttributeError:
            continue
    # A bare figure ask names no subject: "how much should i take", "how long should i leave
    # it". The words left after the ask phrase is taken out ("should", "i", "take") are the
    # asking, not the thing asked about, so a shorter answer that gives the figure has not lost
    # what they asked for. Without this the amount sentence "1 to 2 mg about an hour before bed"
    # was read as a repeat that dropped the verb "take", and the shrug took the turn.
    if _repeat is not None:
        left = [word for word in re.findall(r"[a-z']+", subject)
                if word not in getattr(_repeat, "FIGURE_WORDS", ())
                and word not in getattr(_repeat, "FIGURE_SAYING", ())]
        if not left:
            return None
    last_words = set(last.split())
    asked = [word for word in fallback.content_words(subject)
             if word in last_words or word.rstrip("s") in last_words or word + "s" in last_words]
    if not asked:
        return None
    said = set(first.split())
    missing = [word for word in asked
               if word not in said and word.rstrip("s") not in said and word + "s" not in said]
    if len(missing) * 2 < len(asked):
        return None
    for index, candidate in enumerate(candidates):
        if _priority(candidate) < 0 and fallback.is_said_it_already(candidate.get("reply")):
            return index
    return None


ACK_POOL = None


def _ack_lines():
    """The lines `chat` closes a conversation with, reduced the way a reply is compared."""
    global ACK_POOL
    if ACK_POOL is None:
        try:
            module = importlib.import_module(".chat", __package__)
            pools = getattr(module, "REPLIES", None) or {}
            ACK_POOL = frozenset(_content(line) for line in pools.get("ack", ()))
        except Exception:  # noqa: BLE001 - no pool means nothing is read as a stock close
            ACK_POOL = frozenset()
    return ACK_POOL


def _asks_a_question(memory):
    """True when the understanding engine read the line as a question, else False.

    "is that fair" after the answer about a dog on its own all day is a question, and chat's ack
    pool answered it "Sounds good." while the card beside it said the sentence with the verdict in
    it. The reading is the understanding engine's (`understood["kind"]`), so the arbiter keeps no
    words of its own for what a question is.
    """
    understood = (memory or {}).get("understood")
    if not isinstance(understood, dict):
        return False
    return understood.get("kind") == "question" or understood.get("intent") == "question"


def _asks_for_a_judgement(text, memory=None):
    """True when the line asks the bot to rule on the plan on the table, else False.

    The reading is the composer's (`bot/compose/judgement.py`), so nothing here is a second word
    list for "is that a good idea": the module that owns the pools decides what the ask is.
    """
    try:
        from ..compose import judgement
        return bool(judgement.asks_for_a_judgement(text, memory))
    except Exception:  # noqa: BLE001 - a reading that fails claims nothing
        return False


def _hands_the_decision_back(reply):
    """True when the reply hands the choice back rather than answering the line.

    `chat`'s pool for "is that a good idea" says the decision is the person's to weigh and asks
    what matters to them ("I cannot call that one for you. Tell me what matters most about getting
    a cat..."). It is a better reply than the one it replaced, which signed the person off - and it
    is still not an answer to the line: it asks the question back. A take from under the floor that
    says the one thing the bot can say about the thing ("Yes, that is a reasonable way to do it -
    getting a cat is worth doing. The one thing...") is the answer, so a hand-back does not outrank
    it. Measured on twenty chats of a judgement asked after news: seven turns went from that answer
    to a hand-back (#6689), and every one of them read worse.

    The reading is the module's own: `chat` publishes `hands_it_back`, cut from its pools, so the
    arbiter keeps no wording of anybody's.
    """
    try:
        module = importlib.import_module(".chat", __package__)
        return bool(module.hands_it_back(reply))
    except Exception:  # noqa: BLE001 - a module that cannot answer counts as having answered
        return False


def _the_reply_is_the_report(candidate, text, memory):
    """Is this candidate the composer's own reply to a report on the advice just given?

    The reading is the composer's (`fallback.the_report_reply`), and it is the same call the
    module proposing the reply makes, so the arbiter compares two replies rather than keeping a
    second copy of the reading. It exists because a report on the advice is the composer's
    subject, and the module that proposes its reply sits under the floor: "i wiped it and now its
    worse" after the oven answer was answered by `chat`'s tired pool - the word "wiped" read as
    tiredness - over the composer's "Stop and leave it alone. Worse is the answer ...", and
    `_a_real_answer_besides` counted that pool line as an answer to the line.
    """
    reply = _content(candidate.get("reply"))
    if not reply:
        return False
    try:
        own = _content(fallback.the_report_reply(text, memory))
    except Exception:  # noqa: BLE001 - a reading that fails is not a claim
        return False
    return bool(own) and own == reply


def _real_answers_besides(candidates, last=""):
    """The candidates of modules above the floor that said something to the line.

    Being above the floor is not the same as answering: `chat` sits at 300 on every line and its
    acknowledgement pool signs the conversation off ("Alright then - good luck with it."). A hook
    that gives way to that hands the person a goodbye, which is what the whole of this rule is
    meant to stop. The pool is read from the module that owns it, so nothing here is a second copy
    of somebody's wording, and a reply that only repeats the last answer is not an answer either.
    """
    said = []
    for candidate in candidates:
        if _priority(candidate) <= 0:
            continue
        reply = _content(candidate.get("reply"))
        if not reply or (last and reply == _content(last)):
            continue
        if candidate.get("module") == "chat" and reply in _ack_lines():
            continue
        said.append(candidate)
    return said


# The modules whose replies are pools of stock lines read off the line rather than answers held
# in a card: `chat` reads a mood or a kind of line and picks a line for it, and `greeting` is the
# floor itself. Everything else proposes from a table of its own about a subject.
POOL_MODULES = frozenset(("chat", "greeting"))


# A line that says something and then asks about it has two halves, and only the second one is a
# question: "my sister is veggie and shes coming to dinner, what can i cook" states a fact the
# person already knows and then asks something they do not. The clause that carries the ask is
# set off by a comma or a full stop and opens on the word it asks with.
THE_ASK_OPENS = re.compile(
    r"^(?:and |so |but |also |then |please )*"
    r"(?:what|how|which|where|when|who|why|any|ideas|thoughts|suggestions|advice|tips|"
    r"recommend\w*|should|could|shall|can|do|is|are|help)\b")

# The words that carry no content when a reply is held up against the line it came from.
ECHO_STOP = frozenset(("the", "and", "for", "you", "your", "with", "that", "this", "have", "has",
                       "was", "were", "are", "but", "not", "his", "her", "she", "him", "they",
                       "them", "its", "out", "about", "some", "from", "been", "what", "how",
                       "would", "will", "just", "one", "now", "day", "like"))

# The store says a line back in the second person, so the line's own words are read that way too:
# "my sister" comes back as "your sister", "i" as "you".
THEIR_VOICE = {"my": "your", "mine": "yours", "i": "you", "im": "youre", "me": "you",
               "myself": "yourself", "we": "you", "our": "your", "ours": "yours"}


def _the_ask_after_the_facts(text):
    """The ask at the end of a line that states something first, or "" when the line has none.

    Only a clause set off by a comma or a full stop counts, and only when it opens on a question
    word, so "my sister is veggie and shes coming to dinner" on its own is left entirely alone.
    """
    low = (text or "").lower().rstrip(" .?!")
    cut = max(low.rfind(","), low.rfind(";"), low.rfind("."))
    if cut <= 0:
        return ""
    if len(WORD.findall(low[:cut])) < 3:
        return ""
    ask = low[cut + 1:].strip(" .?!")
    return ask if THE_ASK_OPENS.match(ask) else ""


def _only_says_the_line_back(reply, text):
    """True when a reply is made of nothing but the words the person has just used.

    The store claims a line for the fact in it and says that fact back ("Your sister is veggie."),
    which is the answer to a line that only states it and no answer at all to the question after
    it. A reply that adds no word of its own has read nothing new, so it cannot be what the person
    asked for.
    """
    words = WORD.findall(_content(reply))
    if not words or len(words) > 14:
        return False
    said = set(WORD.findall((text or "").lower()))
    said |= {THEIR_VOICE.get(word, word) for word in said}
    body = [word for word in words if word not in ECHO_STOP and len(word) > 2]
    if not body:
        return False
    return all(word in said for word in body)


def _the_candidates_that_answer_the_ask(text, candidates, pool):
    """The pool without the reply that only says the person's own line back, or None to keep it.

    None when the line asks nothing after its facts, when every candidate in the pool says
    something of its own, or when the only reply left is a floor line - a line whose one answer is
    the fact said back keeps it, because telling the person less is worse than telling them what
    they already knew.
    """
    if not _the_ask_after_the_facts(text):
        return None
    answering = [index for index in pool
                 if not _only_says_the_line_back(_content(candidates[index].get("reply")), text)]
    if not answering or len(answering) == len(pool):
        return None
    if not any(_priority(candidates[index]) >= 0 for index in answering):
        return None
    return answering


def _a_card_besides(candidates, index):
    """True when a module with a subject of its own proposed something beside this candidate.

    A report on the advice can be the only reading of a line - "i wiped it and now its worse" is
    not a question and names no subject to look up - and then the composer's reply is the answer,
    not a pool line's. Where a card is beside it ("done that" after the emails answer still has
    the next part of that answer to give), the card keeps the turn and this reading is not
    consulted.
    """
    for other, candidate in enumerate(candidates):
        if other == index:
            continue
        if candidate.get("module") in POOL_MODULES:
            continue
        if _content(candidate.get("reply")):
            return True
    return False


def _a_real_answer_besides(candidates, last=""):
    """True when some module above the floor said something to the line rather than closing it.

    Being above the floor is not the same as answering: `chat` sits at 300 on every line and its
    acknowledgement pool signs the conversation off ("Alright then - good luck with it."). A hook
    that gives way to that hands the person a goodbye, which is what the whole of this rule is
    meant to stop. The pool is read from the module that owns it, so nothing here is a second copy
    of somebody's wording, and a reply that only repeats the last answer is not an answer either.
    """
    return bool(_real_answers_besides(candidates, last))


def _only_a_hand_back_besides(candidates, last=""):
    """True when the only answer above the floor hands the decision back, else False.

    `_a_real_answer_besides` counts a hand-back as an answer, so that a hook from below the floor
    cannot take the turn off it - the same reason a stock close is not counted: a hook that gives
    way to a goodbye hands the person nothing. But a hand-back is not the answer to a judgement
    either (see `_hands_the_decision_back`), and a take from under the floor that says the one
    thing about the thing is a better reply than asking the question back. This is the test that
    tells the two cases apart: everything above the floor here is a hand-back.
    """
    found = False
    for candidate in candidates:
        if _priority(candidate) < 0:
            continue
        reply = _content(candidate.get("reply"))
        if not reply or (last and reply == _content(last)):
            continue
        if candidate.get("module") == "chat" and reply in _ack_lines():
            continue
        if not _hands_the_decision_back(candidate.get("reply") or ""):
            return False
        found = True
    return found


# The words that say nothing about a subject: a take that shares one of these with the person's
# own words is not about the line. Kept short and general - a determiner, a pronoun, a copula and
# the words every English sentence needs.
NOT_A_SUBJECT_WORD = frozenset("""
the and but for you your yours they them their there here this that these those what which who
with from have has had was were are is it its it's i me my mine we us our ours he she his her him
about into over under than then just only also very really quite some any all not none no yes
going want wants wanted wanting think thinking thing things matter matters most about if when
what would could should will shall can cant can't dont don't doesnt doesn't did isnt isn't
know tell say said like made make get got getting do does did done one two three bit lot
""".split())
# A word in a reply that could be the subject of the line: three letters or more.
A_SUBJECT_WORD = re.compile(r"[a-z']{3,}")

# The determiners that introduce the thing a line is about: "my bins", "the washing machine",
# "your landlord". Used to read the subject off the line itself, not off a list of subjects.
A_SUBJECT_PHRASE = re.compile(
    r"\b(?:my|our|your|his|her|their|the|this|that|these|those|a|an)\s+((?:[a-z']+\s+){0,2}[a-z']+)")


def _names_what_they_said(reply, text, memory):
    """True when the reply says a word from what the person has told the bot, else False.

    A take from under the floor may beat a hand-back, but only where it is about the same thing:
    the composer's pool for "is that a good idea" after "im thinking of getting a cat" says the cat
    back ("getting a cat is worth doing"), and the pool it reaches on another line said "Honestly
    I can't tell you what it's like there. What matters most to you about the trip?" after "im
    thinking of going vegetarian" - a sentence about a trip nobody mentioned, which only surfaced
    once the hand-back stopped outranking it. What separates them is the subject, so the reply has
    to share a word with the thread that is not one every sentence holds.
    """
    said = set(A_SUBJECT_WORD.findall(_content(text)))
    for turn in reversed((memory or {}).get("turns") or []):
        if isinstance(turn, dict):
            said.update(A_SUBJECT_WORD.findall(_content(turn.get("user"))))
        if len(said) > 80:
            break
    words = set(A_SUBJECT_WORD.findall(_content(reply)))
    return bool((said & words) - NOT_A_SUBJECT_WORD)


def _as_it_comes(text, memory, candidates, last=""):
    """The index of a candidate its module asks to be answered as it comes, else None.

    Some answers are right whatever else proposed, but only on some of the lines their module
    proposes on. A band cannot say that: it says "everything this module proposes" and the
    module's other lines then take turns they should not. The memory store is the case that
    found it: "my partner is vegetarian" then "places to eat near the old town" must be answered
    from what the person said, and the same module's diet fact must not answer "where can i take
    my dog" just because it was that high up the scale. So the module says which of its own
    proposals this is, on the line in front of it, and the arbiter takes its word.

    Read after the safety band, and before the never-repeat rule, the `ANSWERS_INSTEAD`
    declaration and the specialist fit, because "answer this as it comes" is the whole of the
    claim. A flagged reply that only repeats the bot's last turn is passed over - a module that
    says "this line is mine" still has to say something new - and so is a hook that raises, so a
    module cannot lose the turn by declaring badly.

    A hook from below the floor does not take the turn off a module above it, though. A claim is
    settled by PRIORITY everywhere else in this file (`_claims_instead`), and a module under the
    floor has no higher claim on the line than anything that actually answered it: "im worn out
    and flat this week" / "and" is answered from the store with the one thing that helps ("That
    kind of tired needs an early night, not more coffee"), and a fallback-band hook that took the
    turn said "that's as far as I can take it" over an answer nobody had been given yet. The same
    held for every other band and it was not enforced: "i keep putting off my emails" /
    "done that" gave the greeting's "How is it going with it so far?" over the next part of the
    entry. Hooks above the floor are untouched: those exist to beat the store on the lines it
    proposes on, which is the whole of the reason `answers` has one.
    """
    for index, candidate in enumerate(candidates):
        name = candidate.get("module")
        if not _declares_as_it_comes(name, text, memory):
            continue
        # ...unless the answers beside it hand back the very thing the line ruled out: "not curry,
        # something else" got the kitchen's "Quick: chickpea curry in 25, or a sweet potato curry",
        # which is the thing refused, twice, while the rule-out's own line ("That one never
        # mentions curry at all, so nothing changes. Quick: tuna pasta...") was the only answer to
        # the line in the list. A reply that offers back what the person has just ruled out has
        # not read the line, so it is not an answer the claim gives way to - not to PRIORITY, and
        # not to a declaring specialist either, which is the same card under another name.
        thing = _the_thing_the_line_ruled_out(text, memory)
        vetoed = bool(thing) and _every_real_answer_offers(thing, candidates, index)
        if _priority(candidate) < 0 and _a_real_answer_besides(candidates, last) and not vetoed:
            # A hand-back above the floor is the one case where a take from under it still has
            # the better reply - but only when the take is about what the person said
            # (`_names_what_they_said`), not when it is a pool line about something else.
            hand_back = (_only_a_hand_back_besides(candidates, last)
                         and _names_what_they_said(candidate.get("reply"), text, memory))
            # ...and the composer's answer to a report on the advice it just gave is the
            # other one: that reading is the composer's subject and not a pool line's, so a
            # module that read the line as a feeling or a mood is not an answer beside it -
            # the same reason `_a_declaring_specialist_besides` decides the rest of the
            # layer. A specialist that declares the line's topic still takes the turn.
            # ...and the status question is the one report reply that gives way: "ive tried
            # that" after the running answer is answered "Has it made any difference yet?" only
            # while there is no card beside it, because the answer's own next step is worth more
            # to a person who has just done the last one. Where nothing is beside it - the oven
            # report, the nails - the question is the whole of the answer and takes the turn.
            report = (_the_reply_is_the_report(candidate, text, memory)
                      and (fallback.a_report_that_says_something(text, memory)
                           or not _a_card_besides(candidates, index))
                      and not _a_declaring_specialist_besides(candidates, index, memory, text))
            if not (hand_back or report):
                continue
        reply = _content(candidate.get("reply"))
        if not reply or (last and reply == last):
            continue
        # A take says "this line is worth answering now"; a declaration says "this line is my
        # subject". A module that declares the topic the line was read as outranks a take, and
        # the bands cannot express that: "i shouted at my kids and i feel awful" had the family
        # card in the list at 0 and chat taking the turn as it comes, and raising the card's
        # band to 400 changed nothing because this layer runs above the bands.
        # The recall band is the exception, and it is a real one: "what should i cook for my
        # son" is answered from what the person said about their son's diet, not from a cooking
        # card, so a store taking that line still beats the specialist. Only a generalist's take
        # gives way. (tests.test_arbiter, the declared turn beats a higher priority specialist.)
        # ...but a card that has not read the line does not outrank it either: the conjunct
        # above is about a specialist that read the line and has the answer, and one that hands
        # back the step the person has just reported doing has read nothing. See
        # `_a_declaring_specialist_besides`, which takes the store's reading of the report.
        if (not vetoed and _priority(candidate) < CHATTER
                and _a_declaring_specialist_besides(candidates, index, memory, text)):
            continue
        # A claim says "this line is my subject", and a stock line says nothing of the subject
        # it claims: the pool for a lonely week answered "my bins were left out and not emptied"
        # ("Loneliness is rough. A weekly club or class is the quickest way to see the same faces
        # again") over the council card that answers the missed collection by name. "Left out"
        # was read as the feeling, and the take that answers that reading shares no word with the
        # line at all - the bins, the emptying, the council are all in the card beside it. A reply
        # that says nothing of the line cannot be about it, so the claim stands down where a card
        # beside it names the line's own words. Only a take from the chatter band is read this
        # way: a specialist that claims a line has read it, and the bands already settle those.
        if _priority(candidate) < CHATTER and _a_card_names_the_line(candidates, index, text,
                                                                    memory):
            continue
        # A claim on a line whose answer is the last answer under a lead ("It's what I said a
        # moment ago: <the paragraph>") is not a second answer: the same rule `_choose` applies
        # to the candidates below applies here, or a module that takes a follow-up as it comes
        # reads the paragraph back to the person while a specialist beside it has the answer to
        # the question actually asked. "my baby is not sleeping" / "what should i look out for"
        # got chat handing back the line it had just given, with the baby's own guidance in the
        # list behind it at 0. Fallbacks are not counted: a stock line is not a reason to drop an
        # answer they have not read.
        if (last and (_echoes(reply, last, announced=True)
                      or _the_answer_again_with_a_tail(reply, last))
                and _a_fresh_answer_besides(candidates, index, last)):
            continue
        # A claim that only says the person's own line back is not an answer to the rest of it:
        # "my sister is veggie and shes coming to dinner, what can i cook" was answered "Your
        # sister is veggie." The store claims a line for the fact in it, at the recall band, while
        # the cooking answer sits beside it at 0. The fact was never in doubt and the ask after it
        # was, so a reply made of nothing but the line's own words gives the claim up - but only
        # where a card beside it does answer the ask, never on a line where it is the whole of
        # what the bot has to say.
        if (_the_ask_after_the_facts(text) and _only_says_the_line_back(reply, text)
                and _a_card_besides(candidates, index)):
            continue
        return index
    return None


# The label the chat module declares is the kind of line, not a subject of the world. `ANSWERS =
# ("small-talk",)` in bot/modules/chat.py says which lines it answers, and every manners question
# is read as exactly that topic, so a declaration of it says nothing about who knows the line: the
# composer's own reading is the narrower one there. Left in, it settled a take the wrong way - after
# an answer, "hows your day been" gave way to the chat module's reply about the thing above (the egg
# answer, then the sentence about keeping boiled eggs in the fridge).
NOT_A_SUBJECT = frozenset(("small talk",))


def _a_question_about_the_bot(text, memory):
    """True when the line asks about the bot itself, else False.

    The reading is the composer's (`fallback.reads_as_about_itself`), the same one that makes the
    claim: a question about the bot's own make, limits or handling of what it is told. It is read
    here for the one thing the arbiter needs from it - that no entry about the world is a
    specialist on such a line - and a reading that fails is not one.
    """
    if not isinstance(text, str):
        return False
    try:
        return bool(fallback.reads_as_about_itself(text, memory))
    except Exception:  # noqa: BLE001 - a reading that fails holds nothing back
        return False


def _a_declaring_specialist_besides(candidates, index, memory, text=""):
    """True when another candidate's module declares a topic this line was read as.

    A card that repeats the answer the person already has is not a specialist that read the line.
    After "my boiler is making a noise" / "i already bled the radiators" the radiators entry
    declared heating and read the bleeding instructions out a second time, over the store's own
    line ("Then that part is out of the way: check the pressure is 1 to 1.5 bar"), and the person
    was told to do what they had just said they did. The reading of "still telling them the step
    they just took" is the store's (`already.tells_them_the_step_again`), so this file keeps no
    vocabulary of its own.
    """
    topics = _line_topics(memory) - NOT_A_SUBJECT
    if not topics:
        return False
    # A question about the bot itself is not a subject, whatever topic the reading hung on it.
    # "is what i say saved" was read as money because the person said "saved", and the savings
    # card then outranked the composer's answer to the question actually asked; "do you share what
    # i say" reached the company-shares card ("A share is a piece of a company") the same way, and
    # "can other people read my messages" the phone-trust card. No entry about the world can
    # answer what the bot does with what it is told, so there is no specialist beside this claim.
    if text and _a_question_about_the_bot(text, memory):
        return False
    for other, candidate in enumerate(candidates):
        if other == index:
            continue
        if not (set(_declared(candidate.get("module"))) & topics):
            continue
        reply = _content(candidate.get("reply"))
        if not reply:
            continue
        if _already is not None and _already.tells_them_the_step_again(reply, text, memory):
            continue
        return True
    return False


def _a_fresh_answer_besides(candidates, index, last):
    """True when a real candidate has an answer that is not the last one said again."""
    for other, candidate in enumerate(candidates):
        if other == index or _priority(candidate) < 0:
            continue
        reply = _content(candidate.get("reply"))
        if reply and reply != last and not _echoes(reply, last, announced=True):
            return True
    return False


def _claims_instead(text, memory, candidates, last="", above=None):
    """The index of a real candidate whose module says it answers a line another module claims.

    "how do i unblock my sink" is answered with the plunger and the trap, and the line after it -
    "i tried that and it didn't work" - is read by the composer as a report on that advice, so it
    claims the turn as it comes. What the composer then says is about the attempt ("say what you
    did and that it hasn't shifted"); the module that knows who does the job once a home fix has
    run out ("a plumber, with the plunger and the trap already ruled out") has the answer, and the
    claim takes the turn from it. That is a routing fault, and it cannot be fixed by looking for
    the advice's words in the candidates' replies: word overlap let a wrong answer line through on
    a phone-battery thread and turned "my knee is sore when i run / its not helping" into the
    fallback's shrug.

    So the claim is given up only to a module that says so itself: it declares
    `CLAIMS_INSTEAD(text, memory) -> bool` and says yes only on the lines where its own proposal
    is the answer to the claimed line, never to win turns. PRIORITY still settles the rest - a
    claim from a module above the declaring one keeps the turn, so the memory store's reading of
    "places to eat near the old town" is not displaced by a general answer - and the safety band
    was read before this. A reply that only says the bot's last line again is not an answer, so
    it does not displace anything.
    """
    for index, candidate in enumerate(candidates):
        if _priority(candidate) < 0:
            continue
        if above is not None and _priority(candidate) <= above:
            continue
        name = candidate.get("module")
        if not _declares_claims_instead(name, text, memory):
            continue
        reply = _content(candidate.get("reply"))
        if not reply or (last and reply == last):
            continue
        return index
    return None


def _declares_claims_instead(module_name, text, memory):
    """True when the module says the claimed line is its own answer (README.md, "Interface")."""
    try:
        module = importlib.import_module("." + str(module_name), __package__)
        hook = getattr(module, DECLARED_CLAIMS_INSTEAD, None)
        return bool(callable(hook) and hook(text, memory))
    except Exception:  # noqa: BLE001 - a module that cannot answer claims nothing
        return False


def _declares_as_it_comes(module_name, text, memory):
    """True when the module says this line is one to answer as it comes (README.md, "Interface")."""
    try:
        module = importlib.import_module("." + str(module_name), __package__)
        hook = getattr(module, DECLARED_AS_IT_COMES, None)
        return bool(callable(hook) and hook(text, memory))
    except Exception:  # noqa: BLE001 - a module that cannot answer declares nothing
        return False


def _asks_about_the_chat(module_name, text, memory):
    """True when the module says this line is about the conversation, not about the world.

    The reading belongs to the module that has it (README.md, "Interface"): the memory store's
    gate already knows every recap shape, so `_fit` asks it rather than growing a second word
    list here. A module that cannot answer, or that raises, says nothing.
    """
    try:
        module = importlib.import_module("." + str(module_name), __package__)
        hook = getattr(module, DECLARED_ABOUT_THE_CHAT, None)
        if not callable(hook):
            hook = getattr(module, OWN_ABOUT_THE_CHAT, None)
        return bool(callable(hook) and hook(text, memory))
    except Exception:  # noqa: BLE001 - a module that cannot answer keeps the ordinary rules
        return False


def _the_move_in_hand(candidates, real, text, last):
    """The index of the step out of the answer just given, on a line that asks for it, else None.

    "where do i start" after an answer names nothing to look up: it asks which part of the answer
    in hand to do first. The composer reads that and hands the step back ("The thing to do first:
    Keep them short and filed."), and the entry that wrote the answer is asked by the same line and
    writes the same answer again at full length, in its second wording - so the never-repeat rule
    does not see a repeat either, and the specialist rule then gives the turn to the paragraph the
    person has just read ("i want to stop biting my nails" / "where do i start" came back as the
    nail-biting paragraph a second time).

    What makes a reply a form of the answer is its words: nearly every one of them is a word the
    answer used, or it runs to the answer's own length and is the answer again in other words. A
    step is the shortest of them and one clause long; a paragraph is not. And the
    paragraph has to be the answer again, not a part of it: a reply that runs to three quarters of
    the answer's own length re-tells it, while an entry that has already taken a step out of the
    answer ("The first thing I would change: Ease off running ...") says a third of it, and that
    is answering the same way the composer does, so this rule leaves it alone. Nothing here reads
    the topic, so a step that is genuinely about something else cannot be taken for the answer's
    own (`names_nothing` and `MOVE_ASK` are the memory lane's readings, not a word list here).
    """
    if not last or _repeat is None:
        return None
    try:
        if not _repeat.names_nothing(text) or not _repeat.MOVE_ASK.search(str(text or "")):
            return None
    except Exception:  # noqa: BLE001 - a reading that fails claims no turn
        return None
    if len(real) < 2:
        return None
    said = last.split()
    seen = set(said)
    forms = []
    whole = False
    for index in real:
        words = _content(candidates[index].get("reply")).split()
        if not words:
            continue
        share = sum(1 for word in words if word in seen) / len(words)
        of_the_answer = share >= MOVE_SHARE
        re_tells = len(said) >= MOVE_ANSWER_WORDS and len(words) >= len(said) * MOVE_WHOLE
        if re_tells:
            # A reply as long as the answer is the answer again, whatever words it picks: main's
            # entries are rewritten between commits, and the paragraph that came back for "i want
            # to stop biting my nails" / "where do i start" was another entry's wording of it,
            # sharing too few words to be caught by the share alone.
            whole = True
        if of_the_answer or re_tells:
            forms.append((len(words), index, of_the_answer))
    if not whole:
        return None
    # The step has to be made of the answer's own words, whatever else is on offer: a re-tell may
    # share almost none of them (it is the entry's second wording) but a *step* that shares none
    # is not a part of this answer at all - it is a hedge ("Nothing to do on my side, honestly")
    # or a line pointing at a list from another turn ("the rest in the order I gave them"), and
    # both of those are shorter than the step that should have won.
    sharing = [form for form in forms if form[2]]
    if len(forms) < 2 or not sharing:
        return None
    shortest, index, _ = min(sharing)
    longest = max(length for length, _, _ in forms)
    if shortest > MOVE_WORDS or shortest * 3 > longest * 2:
        return None  # nothing here is a step, or the step is not clearly shorter than the re-tell
    return index


# A step handed back in the answer's own words is one instruction, and the instruction is the
# sentence the answer wrote it in: "Give them sun, a big pot or grow bag, and water at the base
# regularly" is one move, and a module that stops it at the answer's first comma hands over half of
# it ("The first thing to do: Give them sun, a big pot or grow bag."). How long the whole sentence
# may run, and how much of a reply has to be the answer's words to count as its step, are the two
# numbers the rule already uses for a step. See `_the_whole_move`.
WHOLE_MOVE_WORDS = 60
CUT_MARKS = ",;:"
TOKEN = re.compile(r"[a-z0-9']+")


def _the_whole_move(candidates, real, text, last, written=""):
    """The index of the step that keeps the answer's sentence, where another hands over a piece.

    "where do i start" after a how-to is answered by two modules at once: the composer, which
    hands back the sentence the answer wrote its step in, and the entry that wrote the answer,
    which builds "The first thing to do: <the step>" and stops the step at the answer's first
    comma. Both are made of the answer's own words, so the never-repeat rule sees nothing, and
    the specialist rule then gives the turn to the entry - half of an instruction, over the whole
    of it. And the two are the same move: the short one's words are a run of the long one's.

    So this decides one thing: where one candidate hands over a run of the answer that stops at
    the answer's own comma, and another candidate carries that same run on past the comma, the
    one that carries on takes the turn. Nothing else is read - no module name, no topic - and
    where the answer's words run out the seed rule stands, as it does everywhere else.

    A reply counts as a step only when it is made of the answer's own words (`MOVE_SHARE`, the
    same test `_the_move_in_hand` makes) and is short enough to be one (`WHOLE_MOVE_WORDS`), so a
    paragraph of the answer cannot be lifted over a step by this rule.

    A reply that says the answer over again is not a step at all, however well its opening matches
    (`_echoes`). "Same as before: <the answer>" is the entry's card for a bare follow-up, and the
    longest of those reads as a whole sentence with the writer's own comma in it, so without this
    guard the rule handed the turn to a repeat - the one thing STYLE.md forbids outright - because
    it carried the answer past its comma. Handing a sentence back is only better than handing its
    first clause over when the sentence is new.
    """
    if not last or _repeat is None or len(real) < 2:
        return None
    try:
        if not _repeat.names_nothing(text) or not _repeat.MOVE_ASK.search(str(text or "")):
            return None
    except Exception:  # noqa: BLE001 - a reading that fails claims no turn
        return None
    # The answer as it was written: `last` is the answer with its punctuation taken out, and the
    # comma a step was cut at is a comma of the answer as the person read it.
    answer = " ".join(str(written or last).split())
    tokens = [(match.group(0), match.end()) for match in TOKEN.finditer(answer.lower())]
    if len(tokens) < 4:
        return None
    seen = {word for word, _ in tokens}

    def _halves(skip_repeats):
        """The candidates that stop at the answer's comma, and those that carry the run on."""
        cut, whole = [], []
        for index in real:
            words = _content(candidates[index].get("reply")).split()
            if not words or len(words) > WHOLE_MOVE_WORDS:
                continue
            if skip_repeats and _echoes(str(candidates[index].get("reply") or ""), last):
                continue
            if sum(1 for word in words if word in seen) / len(words) < MOVE_SHARE:
                continue
            run = _run_in_the_answer(words, tokens, answer)
            if run and answer[run[1]:run[1] + 1] in CUT_MARKS and len(tokens) - run[2] >= 2:
                cut.append((words, run[0]))
            else:
                whole.append(words)
        return cut, whole

    cut, whole = _halves(True)
    if not cut and whole:
        # Nothing here stops at the answer's comma, so there is no half-step to prefer. There is
        # still the other fault this line has: a card about a different subject. "where do i
        # really start" after the rice answer was answered by the row that builds a fence ("Set
        # the posts first: a string line between the two end posts...") - it opens on a job, so
        # the specialist rule let it take a follow-up, and it shares none of the answer's words.
        # On a line that asks for a move out of the answer in hand, the reply made of that answer
        # is the one to give: the other is about something the person was not talking about.
        absent = [index for index in real
                  if not _made_of_the_answer(candidates[index].get("reply"), seen)]
        if absent:
            for index in real:
                if _made_of_the_answer(candidates[index].get("reply"), seen):
                    return index
    if not cut or not whole:
        # Every candidate here says the answer over again, so there is no step to prefer - but
        # there is still a worse one. The entry's card for a bare follow-up announces the repeat
        # ("Same as before: <the answer>"), and the composer hands the same sentence back as the
        # one thing to do ("Just the one, then: <the answer's first sentence>"). Both quote the
        # answer; only one of them reads as a friend carrying on, and it is the one the pool put
        # first. Left to the specialist rule the entry takes the turn and the person is told the
        # answer again. This is the one case where the repeat is all there is, so the pool's own
        # order settles it rather than a guess at the words.
        repeats = [index for index in real
                   if _echoes(str(candidates[index].get("reply") or ""), last)
                   and _made_of_the_answer(candidates[index].get("reply"), seen)]
        quiet = [index for index in repeats
                 if not _announces_a_repeat(candidates[index].get("reply"))]
        # Only one shape comes here: one lane hands the answer over announcing the repeat ("Same
        # as before: <the answer>") and another hands the same sentence over as the one thing to
        # do ("Just the one, then: <the answer's first sentence>"). Both quote the answer and only
        # one of them reads as a friend carrying on, so the quiet one takes the turn - in the
        # pool's own order, so nothing else is read. Where every lane announces the repeat, or
        # where a lane has a reply that is not the answer again, the rules above stand.
        if quiet and len(quiet) < len(repeats):
            return quiet[0]
        return None
    for index in real:
        words = _content(candidates[index].get("reply")).split()
        if not words or words not in whole:
            continue
        if any(_carries_on(words, run) for _, run in cut):
            return index
    return None


def _made_of_the_answer(reply, seen):
    """True when the reply is the answer's own words and next to nothing else, else False."""
    words = _content(reply).split()
    return bool(words) and sum(1 for word in words if word in seen) / len(words) >= MOVE_SHARE


def _announces_a_repeat(reply):
    """True when a reply opens on one of the lead-ins the other lanes give an answer again in.

    Those lead-ins are the other lanes\' vocabulary, read here the way this rule reads the memory
    lane\'s leads elsewhere (`_a_lead_line`): "Same as before: {reply}" is `bot/memory/topics.py`\'s
    `REPEAT`, and "As I said: {reply}" is `bot/modules/answers.py`\'s `AGAIN`. A reply under one of
    them says it is giving the answer again rather than answering, and STYLE.md forbids saying the
    same thing twice in a row - so where every candidate left is the answer read out again, the
    one that does not announce itself as a repeat is the one to give.
    """
    said = str(reply or "").strip().lower()
    if not said:
        return False
    return any(said.startswith(lead) for lead in _repeat_leads())


def _repeat_leads():
    """The lead-ins the other lanes put in front of an answer they are handing over again."""
    leads = []
    try:
        from ..memory import topics as _topics
        for lead in getattr(_topics, "REPEAT_LEADS", ()):
            leads.append(" ".join(str(part) for part in lead))
    except Exception:  # noqa: BLE001 - a lane that cannot be read adds no lead-in
        pass
    try:
        from . import answers as _answers
        for frame in getattr(_answers, "AGAIN", ()):
            head = str(frame).split("{")[0].strip().lower()
            if head:
                leads.append(head)
    except Exception:  # noqa: BLE001 - a lane that cannot be read adds no lead-in
        pass
    return tuple(leads)


def _carries_on(words, run):
    """True when `run` is a stretch of `words` with more of the answer's step after it."""
    length = len(run)
    for start in range(len(words) - length):
        if words[start:start + length] == run:
            return True
    return False


def _run_in_the_answer(words, tokens, answer):
    """The longest tail of these words that the answer says in one go: (words, end, index)."""
    for length in range(min(8, len(words)), 2, -1):
        tail = words[-length:]
        for start in range(len(tokens) - length + 1):
            if all(tokens[start + offset][0] == tail[offset] for offset in range(length)):
                return tail, tokens[start + length - 1][1], start + length
    return None


# The questions that ask for the cause of a thing failing rather than for comfort: a living thing
# going under ("why are my fish dying", "why are my plants wilting"), and the open ask that comes
# with it ("what am i doing wrong", "what is killing them"). A person is never diagnosed here, so
# the rule stands down on a line about one (see `_the_cause_asked_for`).
THE_CAUSE = re.compile(r"\bwhy\b[^,.;?!]{0,60}\b(?:dying|wilting|drooping)\b"
                       r"|\bwhat (?:am i|are we) doing wrong\b"
                       r"|\bwhat(?:'s| is| are) (?:killing|causing)\b")
# The words that make a line about somebody, so a condolence is the right answer to it and no card
# is asked for the cause of what is happening to them.
_PEOPLE = frozenset("""mum mom mother mum's dad father gran granny nan nana grandad grandpa
son daughter child baby wife husband partner boyfriend girlfriend brother sister friend mate
fiance fiancee aunt uncle cousin niece nephew he she him her his hers they them their people
person someone somebody anyone everyone""".split())
# The openers of a condolence, as every pool of them in the composer begins: "I'm so sorry to hear
# that", "I'm really sorry", "That's a real loss". A reply that opens this way is comfort, whatever
# else it says.
_CONDOLENCE = re.compile(r"^(?:oh\s+)?(?:(?:i'?m|i am|so|that'?s|that is)\s+)?"
                         r"(?:so\s+|really\s+|very\s+|truly\s+)?sorry\b"
                         r"|^that'?s (?:a real|such a|awful|terrible|heartbreaking)\b")
# The words of a line that name nothing, so a reply "naming" one of them is not about the subject.
_THE_NAMELESS = frozenset("""about after again also been before being both could does doing down
even every from have here into just like made make many more most much must need never only other
ought over same should since some such than that their them then there these they thing things
this those through under until very were what when where which while will with would your yours
really actually still might shall upon got gets going gone want wants wanted know knows saying
said tells told feel feels felt look looks looked take takes took today yesterday tomorrow week
month year time days just""".split())


def _a_condolence(reply):
    """Whether *reply* opens as comfort for a loss rather than as an answer about a thing."""
    said = _content(reply).lower()
    return bool(said) and bool(_CONDOLENCE.match(said))


def _says_the_subject(reply, line):
    """Whether *reply* says a word of *line* that names something (four letters or more)."""
    said = {word for word in WORD.findall(_content(reply).lower()) if len(word) >= 4}
    if not said:
        return False
    for word in WORD.findall(line):
        if len(word) < 4 or word in _THE_NAMELESS:
            continue
        for other in said:
            if other.startswith(word) or word.startswith(other):
                return True
    return False


def _the_cause_asked_for(candidates, real, text, best):
    """The entry's answer to "why is this thing failing" beats the composer's condolence.

    "why are my fish dying" was answered "I'm so sorry to hear that. It's a hard thing to carry -
    I'm here if you want to talk about it, or if anything practical would help": the loss composer
    read a pet going under as a bereavement, and the water entry's answer ("A fish sitting on the
    bottom, or hanging at the surface gulping, is reacting to the water rather than to you, and
    ammonia is the usual cause ...") was in the turn and lost, because it is an ordinary entry
    under a module that reads the whole line. A condolence answers a loss somebody has had; a
    question about why a living thing is failing asks for the cause, and the entry that names the
    thing is the one that has it.
    """
    if not _a_condolence(candidates[best].get("reply")):
        return None
    line = _content(text).lower()
    if not THE_CAUSE.search(line):
        return None
    if _says_the_subject(candidates[best].get("reply"), line):
        # A condolence that names the thing ("I'm so sorry about your fish") is about it, so the
        # person is being answered about what they asked about, and it keeps the turn.
        return None
    if set(WORD.findall(line)) & _PEOPLE:
        return None
    for index in real:
        if index == best:
            continue
        if _says_the_subject(candidates[index].get("reply"), line):
            return index
    return None


def _the_date_fact(candidates, real, text):
    """The store's date is the answer to a "when is it" ask, and a card about the subject is not.

    "when do we fly" after "no in july" was answered with the airport check-in card, and "when is
    my dentist appointment" after "im at the dentist on tuesday" with "ring practices near you and
    ask whether they take new NHS patients" - the subject matched and the date did not, so the
    specialist rule handed the turn to the card. A line that asks when something is wants the fact
    back, and the store is the only module that has it (see bot/compose/facts.py).
    """
    if not facts.asks_for_a_when(_content(text)):
        return None
    store = None
    for index in real:
        candidate = candidates[index]
        if candidate.get("module") != "memory_store":
            continue
        if _priority(candidate) < RECALL:
            continue
        if facts.the_fact_asked_for(_content(text), _content(candidate.get("reply"))):
            store = index
            break
    if store is None:
        return None
    # A reply that names the same date needs no help: the store's bare fact is not better than a
    # card that carries it and goes on to say something useful. "what time is my flight" after "my
    # flight is at 6am" / "no, 8" is answered "You told me your flight is at 8am, so be at the
    # airport by 6am ...", and "At 8am." alone would trade that away.
    said = _content(candidates[store].get("reply"))
    for index in real:
        if index == store:
            continue
        if facts.the_same_date(_content(candidates[index].get("reply")), said):
            return None
    return store


def _the_next_part(candidates, text, last):
    """The index of the next part of the answer in hand, on a line that asks for more, else None.

    "what else" after "The thing to do first: Keep them short and filed" asks for the part after
    the step, and the entry that wrote the answer reads the line as the same question and hands
    back the whole paragraph - the answer a third time, at the length it was the first time. The
    memory lane walks the answer in order and hands back the part that comes next
    (`bot/memory/repeat.py`: `NEXT_ASK`, `_another_part`), and this rule keeps the turn for it.

    The line is picked out the way the step is: by the memory lane's own readings
    (`asks_for_more`, `NEXT_LEADS`, `ALSO_LEADS` in bot/memory/repeat.py), so this rule keeps no
    vocabulary of its own. Only the ask the memory lane reads as this one comes here, so nothing
    else moves.
    """
    if not last or _repeat is None:
        return None
    try:
        if not _repeat.asks_for_more(text):
            return None
        leads = tuple(getattr(_repeat, "NEXT_LEADS", ())) + tuple(getattr(_repeat, "ALSO_LEADS", ()))
    except Exception:  # noqa: BLE001 - a reading that fails claims no turn
        return None
    return _a_lead_line(candidates, leads, last)


def _a_lead_line(candidates, leads, last):
    """The index of the memory lane's own short form of the answer in hand, else None.

    Every line the memory lane hands back out of an answer opens with one of its leads ("The
    thing to do first:", "After that:"), and the leads are that lane's constants, so recognising
    the line costs the arbiter no vocabulary of its own. The lead alone does not pick between two
    of them: an entry that takes a step out of its own answer says the same thing as the
    composer's cut of it, and the one that says more is the better reply, so the longest wins.
    The reply just given is no answer, and never answers itself.
    """
    openers = tuple(str(lead).split("{")[0].strip().lower() for lead in leads if str(lead))
    if not openers:
        return None
    found = []
    for index, candidate in enumerate(candidates):
        reply = str(candidate.get("reply") or "").strip()
        if not reply or not reply.lower().startswith(openers):
            continue
        if last and _content(reply) == last:
            continue
        found.append((len(_content(reply).split()), index))
    if not found:
        return None
    found.sort()
    return found[-1][1]
def _only_acknowledges(memory):
    """True when the understanding engine reads the line as politeness and nothing else.

    "cheers", "thanks", "ta", "ok", "nice one", "makes sense": the person has finished with
    the last answer, not started a new question, so nothing it says can be about the thing the
    conversation was on. A line that names a topic of its own is not this: "thank you for the
    spinach tip" is read as thanks and about cooking, and keeps its routing unchanged.
    """
    understood = memory.get("understood") if isinstance(memory, dict) else None
    if not isinstance(understood, dict):
        return False
    if _labels(understood.get("topics")):
        return False  # "thank you for the spinach tip" is thanks and about cooking: not this
    if understood.get("kind") == "thanks":
        return True
    # An acknowledgement is the understanding engine's reading of a line that answers the bot
    # rather than saying anything of its own ("ok", "nice one", "got it"), and what it is made
    # of is what tells a thank-you from a reply with an ask in it: "you pick" and "got any
    # advice" are read as acks too, and both want the conversation's topic to be answered.
    return (understood.get("intent") == "ack" and not understood.get("asks")
            and understood.get("kind") != "question")


def _a_presence_check(memory):
    """True when the understanding engine reads the line as a check that the bot is here.

    "u up?", "you there?", "still about?": the line asks whether the bot is listening, and it
    names nothing of its own, so it inherits the topic of the conversation and a module that
    answers that topic takes the turn. After "how do i unblock my sink" / "it worked", "u up?"
    got "Same as before: Start with a plunger..." - the drain card read out a second time, where
    the reply is "Still here. What's up?". A line that names a subject of its own is not this
    ("you there in that photo with the dog?" is read as a question about a photo, not a check),
    and neither is a thread the composer keeps (an emergency thread answers a "you there?" with
    its own line - that is read before this). The reading is left alone, as it is for politeness
    alone: only the topic rule is skipped, so the highest PRIORITY takes the turn.
    """
    understood = memory.get("understood") if isinstance(memory, dict) else None
    if not isinstance(understood, dict):
        return False
    if _labels(understood.get("topics")):
        return False  # names a subject of its own, so it is about that subject
    if not understood.get("presence"):
        return False
    # A condolence or a crisis is a thread the line belongs to, not a topic it inherited: after
    # "my dog died yesterday" the presence check keeps the loss card that the thread has, and it
    # does not become "Still here. What's up?" in the middle of somebody's grief.
    turns = memory.get("turns")
    if isinstance(turns, list) and turns and isinstance(turns[-1], dict):
        if str(turns[-1].get("module") or "") in ("loss", "safety"):
            return False
    return True


def _about_the_bot(candidates, clean, last=""):
    """The index of the bot's own answer for a line that asks how it works, else None.

    "how do you learn" is a question about the bot, and the study-tips entry answered it with how
    to revise for an exam because the line has "learn" in it; "how do you know things" got the
    same paragraph. A topic entry answers the topic a line is about, and on a line about the bot
    itself the only thing it can match is the verb, so the composer's own answer is the one that
    answers the question asked (STYLE.md).

    Only the kinds the composer publishes claim this (`MY_WORKINGS`), and only from the fallback
    band: the bot's own answers for the rest ("do you have feelings") are already beaten by a
    module that has a better one, and displacing a module that read the line whole is not this
    rule's business. "wrong" is one of them because nothing has a better answer there: a chat that
    was on tomatoes answered "ok random question, do you ever make mistakes" with a tomato sauce
    recipe.
    The reading is the composer's (bot/compose/fallback.py `about_the_bot`), not a word list of
    the arbiter's.
    """
    try:
        kind = fallback.about_the_bot(clean)
    except Exception:  # noqa: BLE001 - a reading that fails claims nothing
        return None
    if kind not in _my_workings():
        return None
    if not candidates or not _declares_topics(candidates[0].get("module")):
        return None
    for index, candidate in enumerate(candidates):
        if _priority(candidate) >= 0 or _declares_topics(candidate.get("module")):
            continue
        reply = _content(candidate.get("reply"))
        if not reply or (last and reply == last):
            continue
        return index
    return None


def _the_venue_hours_turn(candidates, clean, last="", text=""):
    """The index of the composer's honest line for a venue's opening hours, else None.

    "what time does the post office on hill road close today" was answered with the
    weekend-plans card: that entry keys on "today" and a bare "what", and on a question about a
    branch's hours both are noise. "when does the post office close" was answered with the
    postage-times card, and "when do the banks open today" with how to open a bank account.
    Nobody here can know a named venue's hours, so the composer's honest line - where to find
    today's figure - is the one that answers the question asked (STYLE.md), and it takes the
    turn off an entry that matched one other word of the line.

    The reading is the composer's (bot/compose/fallback.py `venue_hours`): a place has to be
    named AND opening or closing has to be the ask, so "what time do hospitals let visitors in",
    "what time does boarding start" and "what time is my appointment today" are untouched. The
    candidate has to BE one of the composer's hours lines, from the fallback band, and it never
    repeats the last reply.
    """
    try:
        if not fallback.venue_hours(clean, None):
            return None
    except Exception:  # noqa: BLE001 - a reading that fails claims nothing
        return None
    if not candidates or not _declares_topics(candidates[0].get("module")):
        return None
    try:
        lines = frozenset(_content(line) for line in fallback.venue_hours_lines())
    except Exception:  # noqa: BLE001 - a pool that cannot be read claims nothing
        return frozenset()
    if not lines:
        return None
    for index, candidate in enumerate(candidates):
        if _priority(candidate) >= 0 or _declares_topics(candidate.get("module")):
            continue
        reply = _content(candidate.get("reply"))
        if reply and reply in lines and not (last and reply == last):
            return index
    return None


def _the_bots_own_taste(candidates, clean, memory, last=""):
    """The index of the composer's taste for a line that asks what the bot likes, else None.

    The same shape as `_about_the_bot`: only a line the composer reads as a question about its
    own taste, and only where a card that declares topics is in front of it. The composer's line
    is one of its taste pools by construction (`reads_as_a_taste` checks the pool), so this rule
    never hands the turn to a shrug or a nod, and a line whose taste the composer has no reply
    for keeps whatever answered it.
    """
    if not candidates or not _declares_topics(candidates[0].get("module")):
        return None
    try:
        asked = fallback.reads_as_a_taste(clean, memory)
    except Exception:  # noqa: BLE001 - a reading that fails claims nothing
        return None
    if not asked:
        return None
    try:
        lines = frozenset(_content(line) for line in (getattr(fallback, "TASTE_LINES", ()) or ()))
    except Exception:  # noqa: BLE001 - a pool that cannot be read claims nothing
        return None
    if not lines:
        return None
    for index, candidate in enumerate(candidates):
        if _priority(candidate) >= 0 or _declares_topics(candidate.get("module")):
            continue
        reply = _content(candidate.get("reply"))
        if not reply or (last and reply == last):
            continue
        if reply in lines:
            return index
    return None


def _my_workings():
    """The kinds the composer claims as questions about how it works, from the composer."""
    try:
        return frozenset(getattr(fallback, "MY_WORKINGS", ()) or ())
    except Exception:  # noqa: BLE001 - a set that cannot be read claims nothing
        return frozenset()


def _declares_topics(module_name):
    """True when a module declares the topics it answers (README.md, "Interface")."""
    try:
        module = importlib.import_module("." + str(module_name), __package__)
    except Exception:  # noqa: BLE001 - a module that cannot be read declares nothing
        return False
    return bool(_labels(getattr(module, DECLARED_TOPICS, ())))


def _reads_as_a_verdict(text, memory=None):
    """The composer's reading of a line that is only a verdict on the news, or False."""
    reader = getattr(fallback, "reads_as_a_verdict", None)
    if reader is None:
        return False
    try:
        return bool(reader(text, memory))
    except Exception:  # noqa: BLE001 - a reading that cannot run claims nothing
        return False


def _verdict_lines():
    """The composer's own lines for a verdict on the news (bot/compose/fallback.py)."""
    lines = set()
    for name in ("VERDICT_ANNOY", "VERDICT_LUCK", "VERDICT_SHAME", "VERDICT_ROUGH",
                 "VERDICT_HEAVY", "VERDICT_NUMB"):
        try:
            lines.update(getattr(fallback, name, ()))
        except Exception:  # noqa: BLE001 - a pool that cannot be read claims nothing
            continue
    # The same reduction the other matchers in this file use (`CALLED_BACK`, `leaving.lines()`):
    # a pool line carries its own punctuation and capital letters, and a reply that came back
    # through `_choose` is the same words, so comparing the raw text against the reduced one
    # never matched and the rule below never fired.
    return frozenset(_content(line) for line in lines)


def _the_verdict_turn(candidates, lines):
    """The index of the candidate whose reply IS the composer's verdict line, else None.

    Matching the line rather than skipping the ones that are wrong is what makes the rule hold:
    "im being evicted next week" then "thats a nightmare" was answered by the sleep entry
    ("Nightmares usually follow stress, late food, alcohol or a heavy film before bed"), and
    "my landlord wont fix the boiler" then "what a headache" by the headache entry, because any
    card that happens to own the noun won the topic rule. A verdict has no subject of its own, so
    the composer's line for it takes the turn and the cards that own the word stand down.
    """
    for index, candidate in enumerate(candidates):
        if _content(candidate.get("reply")) in lines:
            return index
    return None


def _in_a_careful_thread(clean, memory):
    """True while the conversation is inside a live emergency or its next line.

    A verdict after "my husband hit me" is not a light turn: the person is still in the thread
    the bot answered, and the composer's continuation ("You did the right thing telling someone.
    Stay with a person you trust tonight...") is the turn. `_verdict_pool` is a light pool, so it
    must stand down for the whole thread - the same judgment `_thread_index` makes, read here so
    the verdict rule cannot take the turn before that block is reached. The composer's own reader
    for the thread is asked first (it knows the wording), and the arbiter's own question after it
    (was the last word a safety answer) so a thread the reading misses is still not answered with
    a light line.
    """
    kind, _target = _composer_reading(clean, memory)
    if kind in (THREAD, CARE_THREAD):
        return True
    try:
        return bool(getattr(fallback, "in_a_safety_thread", lambda _memory: False)(memory))
    except Exception:  # noqa: BLE001 - a thread that cannot be read is not claimed
        return False


# The modules whose own answer to a verdict stands: both keep the conversation and read the line
# and the thread before they speak, so their answer is about the thing the verdict is about rather
# than about the verdict's word. A pool line is the right reply for the floor, the echo of the last
# answer and the search hedge, which is what this rule is for - not for an answer that already
# answered: "my dog died" then "what a shame" is a pet-loss card, and "im so tired" then "thats
# annoying" is the store's line about that tiredness. Standing the pool up over those traded the
# answer the person had just been given for a general line (gray-cypress, crisp-jackal on #5479).
# The fact store first: it answers with the thing the person said about themselves ("That kind of
# tired needs an early night, not more coffee") where chat answers for anyone.
KEEPS_ITS_OWN_ANSWER = ("memory_store", "chat")
# A card that answers the news keeps the turn too, but only by the news test - never by the
# opener. "my cat was put down yesterday" / "what a shame" got the pool line, and the card it
# stood down opens "I'm sorry, that's one of the hardest days. Nothing has to be decided today:
# the vet can arrange cremation" - the one thing the person can actually do (cowbird-note on
# #5479). The noun's own card cannot come in this way: the headache card is about a word of the
# verdict, not about the news, so `_about_the_news` is false for it.
ANSWERS_THE_NEWS = ("answers",)
# The line a module writes for the verdict itself opens by taking the verdict up ("It is.",
# "That would ... too", "You're right", "That kind of tired ..."), so that opener is one way an
# answer shows it is about this turn.
A_VERDICT_BACK = re.compile(
    r"^\W*(?:it\s+is|it'?s|it\s+does|it\s+doesn'?t|that\s+is|that'?s|that\s+would|that'?d|"
    r"that\s+kind|that\s+sounds|you'?re\s+right|you\s+are\s+right|yeah|yes|true|fair\s+enough|"
    r"of\s+course|same\s+here|i\s+know|i\s+don'?t\s+blame|anyone\s+would)\b")
# The words that only hold a sentence together, so they never make a reply "about" anything.
NOT_A_SUBJECT_WORD = frozenset((
    "the", "and", "but", "for", "with", "you", "your", "yours", "they", "them", "their", "his",
    "her", "hers", "she", "him", "our", "ours", "us", "its", "it", "that", "this", "these",
    "those", "was", "were", "been", "are", "am", "is", "be", "does", "did", "done", "have",
    "has", "had", "can", "cant", "cannot", "will", "would", "should", "could", "may", "might",
    "must", "not", "nor", "off", "out", "down", "too", "very", "really", "much", "many", "some",
    "any", "all", "more", "most", "just", "only", "then", "there", "here", "now", "how", "what",
    "when", "where", "why", "who", "which", "about", "than", "into", "onto", "over", "under",
    "again", "still", "even", "ever", "never", "get", "got", "gets", "one", "two", "put", "say",
    "says", "said", "think", "know", "like", "want", "need", "make", "made", "take", "took",
    "going", "went", "gone", "come", "came", "keep", "keeps", "kept", "let", "lets"))


def _subject_words(text):
    """The words of a line that could be what it is about, roughly singular.

    A crude stem on purpose: "landlords" and "landlord" have to match for the test below to hold,
    and the words a plural adds ("-es") are the same word to a reader.
    """
    words = set()
    for word in WORD.findall(str(text or "").lower()):
        if len(word) < 3 or word in NOT_A_SUBJECT_WORD:
            continue
        for ending in ("ies", "es", "s"):
            if word.endswith(ending) and len(word) > len(ending) + 2:
                word = word[:-len(ending)] + ("y" if ending == "ies" else "")
                break
        words.add(word)
    return words


def _about_the_news(reply, memory):
    """True when a module's answer names something in the news the verdict is about.

    The answer the pool must not take over is the one about the thing the person just told the
    bot about, and it says so with the news's own words: chat's "Landlords have to do most
    repairs in a reasonable time" is about the boiler, and the store's "That kind of tired needs
    an early night" is about the tiredness. The answers the pool must take the turn from are about
    the verdict's word instead: "Nightmares usually follow stress" for "what a nightmare" after a
    question about washing, and a scarecrow joke for "thats a joke" after a broken laptop. Both of
    those name nothing in the news, which is the reading here.
    """
    news = set()
    turns = (memory or {}).get("turns") if isinstance(memory, dict) else None
    if isinstance(turns, list) and turns and isinstance(turns[-1], dict):
        news |= _subject_words(turns[-1].get("user"))
        news |= _subject_words(turns[-1].get("bot"))
    return bool(news & _subject_words(reply))


def _says_the_same_thing_again(reply, last):
    """True when a candidate only re-tells the answer the bot has just given.

    A verdict on the news asks to be heard, not answered again. After "my washing machine is
    broken" the card's own second sentence came back as the answer to "what a pain" ("Check the
    cheap things before you pay anyone..."), and after the landlord letter "what a headache" got
    a second landlord paragraph. Both are the topic the last answer already covered, so the words
    say it: when most of what the candidate says is already in the last answer, it is a re-telling
    and not a second answer to the verdict (tidy-panther on #5479).
    """
    if not last:
        return False
    words = _subject_words(reply)
    said = _subject_words(last)
    if not words or not said:
        return False
    shared = words & said
    return len(shared) >= 2 and len(shared) * 2 >= len(words)


def _the_subject_was_answered(candidate, memory):
    """True when the module that answered last is now saying about this subject again.

    A verdict asks to be heard, not answered again. After the landlord letter, "what a headache"
    came back with a second landlord paragraph ("Landlords have to do most repairs in a reasonable
    time, and anything that came with the flat counts"), and that is the subject the last answer
    had already covered - so the pool is the turn, not another sentence on the same topic.

    Whose words they are is what separates the two (tidy-panther, cowbird-note, blue-hedgehog on
    #5479). The rest of the letter answer is the same module saying the letter again - `answers`
    both times, ten content words of the one before it. The card for a pet that died that opens
    "I'm sorry, that's one of the hardest days" comes from the card the person has not been given
    yet, after `loss` said its condolence, and the two paragraphs share the words every condolence
    in English shares: "sorry", "today", "gentle", "heavy". So it is not a re-telling at all, and
    a second answer to the same question is: the module that answered last, saying it again.
    """
    turns = (memory or {}).get("turns") if isinstance(memory, dict) else None
    if not (isinstance(turns, list) and turns and isinstance(turns[-1], dict)):
        return False
    last = turns[-1]
    if str(last.get("module") or "") != str(candidate.get("module") or ""):
        return False
    said = {word for word in _subject_words(last.get("bot")) if len(word) >= 5}
    return len(said & {word for word in _subject_words(candidate.get("reply")) if len(word) >= 5}) >= 2


def _the_verdict_back(candidates, last="", memory=None):
    """The index of the module's own answer to the verdict, or None.

    Not the candidate that happens to be ranked first: the answer to the news can be ranked
    below a card that only owns a word of it, so the whole list is asked.

    The opener test (`A_VERDICT_BACK`) alone kept out a card that owns a word of the verdict - but
    it also threw away the answers that are about the news: the card for a pet that died opens
    "I'm sorry, that's one of the hardest days", which is not a verdict taken up, and gray-cypress
    found it standing down. So the answer is kept either way round: a line written for the verdict
    (the opener) or a line about the news (`_about_the_news`). An answer that says the last one
    again is neither - it is not a second answer - so the pool is free to take that turn.
    """
    for module_name in KEEPS_ITS_OWN_ANSWER + ANSWERS_THE_NEWS:
        is_a_card = module_name in ANSWERS_THE_NEWS
        for index, candidate in enumerate(candidates):
            if str(candidate.get("module") or "") != module_name:
                continue
            if _priority(candidate) < 0:
                continue
            reply = _content(candidate.get("reply"))
            if not reply:
                continue
            if last and (reply == last or _echoes(candidate.get("reply"), last)):
                continue
            if _says_the_same_thing_again(candidate.get("reply"), last):
                continue
            if not is_a_card and A_VERDICT_BACK.match(reply):
                return index
            if _about_the_news(candidate.get("reply"), memory):
                if not _the_subject_was_answered(candidate, memory):
                    return index
                continue
    return None


def _verdict_reply(candidates, text, memory, last="", clean="", best=0):
    """The index of the candidate a bare verdict on the news is answered with, else None.

    "what a hassle" after an answer about cooking is the person saying how the news sits with
    them. It has no subject of its own, so nothing may answer it with the topic the conversation
    is on: the same-advice path matched "cooking" and answered "Nothing separate for a hassle - it
    is the same advice: <the cooking answer>", which is the bot talking to itself, and any entry
    that owns the verdict's noun answered the noun ("Nightmares usually follow stress").

    Two turns keep the floor: a live emergency thread, where "thats annoying" is still that
    thread, and a line a whole-line module read for itself (grief, loss) - after "my mum died last
    week", "thats a shame" is not a light verdict, and the grief module's answer stands.
    """
    if not _reads_as_a_verdict(text, memory):
        return None
    if _priority(candidates[best]) >= WHOLE_LINE_BAND:
        return None
    if _in_a_careful_thread(clean or text, memory):
        return None
    # A module that read the line and said the verdict back in its own words keeps the turn: "i
    # cant sleep" then "thats annoying" was chat's "It is. Being cross about it for a bit is fair
    # enough.", and a tired thread's own line ("That kind of tired needs an early night") is
    # specific where the pool is general. The pool is better than a floor, a hedge or an echo -
    # not better than an answer that already answered.
    back = _the_verdict_back(candidates, last, memory)
    if back is not None:
        return back
    return _the_verdict_turn(candidates, _verdict_lines())


def _instead(text, candidates, last="", own=(), clean=""):
    """The index of a candidate whose module answers in place of the topic entries, else None.

    A topic entry matches a word or a topic id of the line, so on a line another module read as
    a whole it can answer a different question: "some days i can't get out of bed since my mum
    died" matched the gift-for-mum entry on "mum" and "get", "we had to put our cat down" matched
    litter trays on "cat", and "what do i write in a condolence card" matched a card shop. A
    module that declares `ANSWERS_INSTEAD` read the whole line and says so, so it wins the turn;
    it proposes only on the lines it is sure of, so it is not a priority to raise.

    Every candidate is looked at, not only the ones above priority 0: a module that read the
    whole line may sit in the fallback band on purpose - it proposes nowhere else, so a low
    priority is the honest place for it - and a declaration that only worked from the real band
    would make "I answer in place of the entries" a promise the arbiter then broke. Measured on
    main with no fallback-band declarer: no reply changes, so this only widens the door.

    Checked after the safety band, so a real emergency is still the safety module's turn, and
    before the specialist rule, so a topic entry cannot take the line back on a word. It also
    carries what the composer's death rule used to do on the turns after a death: the loss
    module answers "the anniversary is next week" and "i cant sleep" while the thread is still
    a bereavement, and passes a practical ask inside it ("how do i cancel her phone contract")
    to the topic entry that can answer it.

    A declaring module can also carry `DEFERS_TO`, a test on another candidate's reply, for the
    turns where an entry answers the line better than it can: the test passing lets that entry
    keep the turn (`_defers`). It is opt-in, so a module that declares nothing here is unchanged.
    """
    for index, candidate in enumerate(candidates):
        module = candidate.get("module")
        if not _declares_instead(module):
            continue
        if last and _content(candidate.get("reply")) == last:
            continue  # the never-repeat rule holds in every band
        keeps = _defers(module, candidates, skip=index, last=last, own=own, clean=clean,
                        text=text)
        if keeps is not None:
            return keeps  # the entry that already answers this line better keeps the turn
        return index
    return None


def _defers(module_name, candidates, skip, last="", own=(), clean="", text=""):
    """The index of a candidate whose reply already does what the declaring module would say.

    A module can read the whole line and still meet an entry that answers it better, because
    the entry knows the topic and the module only recognises the situation: "we had to put our
    cat down yesterday" is the pets entry's line (cremation, home burial, a paw print), and the
    module's sympathy is the poorer answer. The module declares `DEFERS_TO`, a test on a reply,
    so the arbiter still reads no wording of its own: a reply that passes it keeps the turn.

    The test is called with the reply and the line (`test(reply, text)`), because the same reply
    can be right for one line and wrong for the next: the pets entry answers "we had to put our
    cat down yesterday" and is the wrong answer to "my cat died and i keep crying". A test
    written for the reply alone (`test(reply)`) is called with the reply only.
    """
    test = _defers_to(module_name)
    if test is None:
        return None
    for index, candidate in enumerate(candidates):
        if index == skip or _declares_instead(candidate.get("module")):
            continue
        if int(candidate.get("priority") or 0) < 0:
            continue  # the fallback band apologises for everything: it cannot keep a real turn
        if own and _match(candidate.get("module"), own, (), (), clean) <= 0:
            continue  # only an entry that answers the topic this line names can keep the turn
        if last and _content(candidate.get("reply")) == last:
            continue  # the entry cannot keep the turn with the reply just given
        reply = candidate.get("reply") or ""
        try:
            if test(reply, text):
                return index
        except TypeError:  # a test written for the reply alone is still a test
            try:
                if test(reply):
                    return index
            except Exception:  # noqa: BLE001 - a test that raises defers to nobody
                continue
        except Exception:  # noqa: BLE001 - a test that raises defers to nobody
            continue
    return None


def _defers_to(module_name):
    """The declaring module's `DEFERS_TO` test on a reply, or None when it declares none."""
    try:
        module = importlib.import_module("." + str(module_name), __package__)
    except Exception:  # noqa: BLE001 - a module that cannot be read defers to nobody
        return None
    test = getattr(module, DECLARED_DEFERS, None)
    return test if callable(test) else None


def _declares_instead(module_name):
    """True when a module says it answers in place of the topic entries (README.md, "Interface")."""
    try:
        module = importlib.import_module("." + str(module_name), __package__)
    except Exception:  # noqa: BLE001 - a module that cannot be read declares nothing
        return False
    return bool(_labels(getattr(module, DECLARED_INSTEAD, ())))


def _pause_reply(candidates, pool, text, memory, last=""):
    """The index of the composer's line for an apology about the chat pausing, or None.

    "sorry for not replying" is an apology for the gap and nothing else, and a topic entry can
    still take it on a word of it: the answers module read "reply" and "message" as a request
    to draft an email, so a person who had just said sorry for being away was told to "say the
    ask in the first line". The reading and the wording are the composer's
    (`fallback.reads_as_pause`, `fallback.CAME_BACK`); the arbiter only keeps the turn where it
    belongs, the way it does for a goodbye.

    Not at the expense of a module that read the whole line itself: the loss and grief bands sit
    above `WHOLE_LINE_BAND` and their turn stands, and a safety thread was answered before this
    (`_composer_reading` returns THREAD for it, so there is no pause to keep).
    """
    try:
        # The composer's own reading decides, including where it does not apply: a condolence
        # thread or a live crisis has its own voice, so it returns no pause there.
        if _composer_reading(text, memory)[0] != PAUSE:
            return None
        said = {_content(line) for line in fallback.CAME_BACK}
        # A line that only points back at the conversation is the same kind for the arbiter's
        # purpose - no topic entry may take it back on a word of it - so its pool is read here
        # too. The version that asks about the thing named after the phrase ("as i was saying
        # about the car") is that pool with the thing filled in, so the thing is what the reply
        # has to be built from.
        said |= {_content(line) for line in fallback.RETURNED_TO_IT}
        named = fallback.reads_as_a_return(text)
        if named:
            said |= {_content(line.format(thing=named))
                    for line in fallback.RETURNED_TO_A_THING}
    except Exception:  # noqa: BLE001 - a reading that fails just adds no rule
        return None
    kept = None
    for index in pool:
        if _priority(candidates[index]) >= WHOLE_LINE_BAND:
            return None  # a module that read the whole line has the better claim
    for index, candidate in enumerate(candidates):
        said_back = _content(candidate.get("reply"))
        if said_back not in said:
            continue
        if not last or said_back != last:
            return index
        kept = index if kept is None else kept
    return kept


def _leaving_reply(candidates, own, carried, words, clean, text, memory, last=""):
    """The index of the sign-off for a line that says the person is going, or None.

    A goodbye is the one line no topic entry owns, and every topic entry can win it on a word of
    the reason behind it: "ill let you go, dinner is burning" matched cooking, "better go and
    get the washing in" got the search shrug, "got to go, the kids are up" got a nod. The
    reading and the wording are the composer's (bot/compose/leaving.py); the arbiter only keeps
    the turn where it belongs. A leave inside a safety thread is still that thread, so the
    careful continuation keeps it.
    """
    # The line as typed: the composer's reading needs the punctuation that separates the leave
    # from the reason ("ill let you go, dinner is burning"), and `clean` has already lost it.
    typed = " ".join(str(text or "").lower().split())
    try:
        if not leaving.reads_as_leaving(typed):
            return None
        said = {_content(line) for line in leaving.lines()}
    except Exception:  # noqa: BLE001 - a reading that fails just adds no rule
        return None
    try:
        if _composer_reading(text, memory)[0] == THREAD:
            return None
    except Exception:  # noqa: BLE001 - no thread reading, no thread to keep
        return None
    # The small-talk module first: a goodbye is its line, and it has its own wording for one.
    # Chat wins this on its own reply rather than on the composer's, so a chat that read the line
    # keeps it and this rule only fills in where nothing did.
    small_talk = _labels(("small-talk",))
    try:
        # Only the leave with a reason in front of it can be answered by the reason: a bare leave
        # ("im off to work now") is a plan as much as a goodbye, and small talk's next-thing line
        # is the better reply to it.
        reasoned = leaving.pool(typed) is leaving.REASON_POOL
    except Exception:  # noqa: BLE001 - no reading of the reason, no reason to be stricter
        reasoned = False
    for index, candidate in enumerate(candidates):
        # ... but only a sign-off. A sign-off asks nothing, and small talk also answers the
        # reason behind the leave with a question ("thanks, i need to go, the kids are up" got
        # "Go, the kids are up - fair enough. What's stopped it happening so far?"); it also
        # answers the reason without one ("talk later, the baby is crying" got "That's a lot for
        # them to carry."). Neither is a goodbye, so where the leave has a reason the composer's
        # vocabulary decides whether the reply in front of it is one.
        if _declared(candidate.get("module")) & small_talk and not _asks(candidate.get("reply")) \
                and (not reasoned or _a_sign_off(candidate.get("reply"))):
            return index
    spare = None
    for index, candidate in enumerate(candidates):
        said_back = _content(candidate.get("reply"))
        if said_back in said:
            if not last or said_back != last:
                return index
            spare = index if spare is None else spare
    if spare is not None:
        return spare
    # No sign-off among the candidates: the first reply that is not about a topic still beats
    # one that matched a word of the reason clause.
    for index, candidate in enumerate(candidates):
        if _priority(candidate) < 0:
            continue
        if _match(candidate.get("module"), own, carried, words, clean) <= 0:
            return index
    return None


def _asks(reply):
    """True when a reply is a question, so it is not a sign-off for a line that says goodbye."""
    return "?" in str(reply or "")


def _a_sign_off(reply):
    """True when a reply lets the person go (bot/compose/leaving.py owns the vocabulary)."""
    try:
        return leaving.reads_as_a_sign_off(reply)
    except Exception:  # noqa: BLE001 - a reading that fails adds no rule
        return False


def _declared(module_name):
    """The topics a module declares (README.md, "Interface"), or () when it declares none."""
    try:
        module = importlib.import_module("." + str(module_name), __package__)
    except Exception:  # noqa: BLE001 - a module that cannot be read declares nothing
        return ()
    return _labels(getattr(module, DECLARED_TOPICS, ()))


def _the_store_revises_the_answer(candidates, pool, memory, text, last=""):
    """The store's reply on the turn the person says one thing in it is out, else None.

    A suggestion is often a list, and the line after it takes one thing off the list: after "what
    can i add to chicken salad" the reply names celery, red onion, apple and walnuts, and "and i
    hate celery" is answered by giving the list back without the celery. Only the store can do
    that. It read the dislike, and its reply is the answer the person already has with the food
    they will not eat taken out.

    The knowledge base cannot know it: the line has the word "celery" in it, so the five-a-day
    entry answers "a portion is a handful - about 80g" and the person who said what they do not
    eat is told about fruit and vegetables instead. The store's reply scores nothing on the
    conversation's topic and the entry scores on it, so the last rule in `_choose` has to pick
    the entry unless this one takes the turn first.

    Narrow on purpose, and each gate is a test:

    - the line has to say the thing the store holds as their dislike (the store's own reading, not
      a second reader here), so a line about something else never qualifies;
    - the store has to have proposed on this line, which it only does when it read the line as the
      revision;
    - its reply has to carry five words in a row of the last answer, which is what makes it the
      answer in hand rather than a new one, and keeps a store reply that shares nothing with the
      answer (`"Celery - got it, that is out of anything I suggest"`) under the ordinary rules.
    """
    if not last or not isinstance(memory, dict):
        return None
    # Their own dislikes and their guests': "she doesnt eat meat" then "and she hates mushrooms" is
    # the same turn as "and i hate celery", and the store holds the suggestion both times.
    held = [memory.get("user")]
    others = memory.get("others")
    if isinstance(others, list):
        held.extend(others)
    dislikes = [str(thing).lower()
                for person in held if isinstance(person, dict)
                for thing in (person.get("dislikes") or []) if thing]
    if not dislikes:
        return None
    said = set(_content(text).split())
    if not said & set(dislikes):
        return None  # the line did not name the thing they do not eat
    previous = last.split()
    for index in pool:
        if candidates[index].get("module") != "memory_store":
            continue
        reply = candidates[index].get("reply") or ""
        if _a_clause_was_cut_in_half(reply):
            continue
        words = _content(reply).split()
        for start in range(0, max(0, len(words) - 4)):
            run = words[start:start + 5]
            if len(run) == 5 and _a_run_of(previous, run):
                return index
    return None


def _a_clause_was_cut_in_half(reply):
    """True when a reply splices a describing clause onto a list, so it reads as two halves.

    The store builds a revision by keeping the list of things from the answer and dropping the
    one that is out. Where the answer put a clause beside the list ("a chickpea and vegetable
    traybake, made in the largest dish you own, which feeds eight from one oven") the same
    keeping word by word gives "a chickpea and vegetable traybake, made in the largest dish you
    own or which feeds eight from one oven all still work" - the list and the clause stitched at
    the wrong place. That is a fault in the store's own wording, and until it builds the list
    without the clause the ordinary answer is the one to give, so the relative pronoun says the
    revision was cut in half.
    """
    words = _content(reply).split()
    return any(word in ("which", "whose") for word in words)


def _store_correcting(candidates, pool, memory, text, last=""):
    """The store's reply on the turn the person corrects what they just said, else None.

    A correction is a line that only replaces something said a moment ago ("my budget is 500"
    then "make it 900"). The understanding engine finds no topic in it, but a knowledge entry
    keyed on its words can: "make it 900" reached the budget-split entry, so the person got a
    lecture about splitting their income instead of "900 - got it". Only the store knows the line
    is a correction of the turn before (the shared `memory["correction"]` says which line it
    was), and no entry can, so on that turn the store's reply is the one they are owed.

    Nothing here reads a reply's wording: the store has to have proposed on this line (its own
    reader decides that) and the never-repeat rule still holds.
    """
    fixed = memory.get("correction") if isinstance(memory, dict) else None
    if not isinstance(fixed, dict) or not fixed.get("value"):
        return None
    if str(fixed.get("said") or "") != " ".join(str(text or "").lower().split()):
        return None  # this is not the line that made the correction
    for index in pool:
        if candidates[index].get("module") != "memory_store":
            continue
        if last and _content(candidates[index].get("reply")) == last:
            return None  # the reply just given is no answer to a correction
        return index
def _draft_index(candidates, last, clean=""):
    """The composer's promised draft, or its offer to write it, or None.

    A line asking for help with a message is answered, honestly, by asking for the two things a
    message needs: who it is for and what it should say. The next line is that detail ("saying im
    off sick tomorrow"), and on main it was echoed back or met with a topic entry that took it on
    a word ("my car broke down" got the hard-shoulder advice instead of the note the person was
    told to hand over). An offer the bot then drops is worse than never offering.

    This is the one place a composer reply is chosen ahead of every other candidate, before
    `_instead`: it is safe only because the composer drafts on its own gates (the offer in the
    bot's last turn, and a line that is not news, a symptom, a mood or a fragment). Any widening
    of the draft has to keep those gates, or this turns routing into a priority raise.

    The composer already writes the draft, so the routing decision is only to give the turn to
    the module the composer answers through - `fallback.FALLBACK_MODULE`, the one module whose
    whole reply is the composer's - when that reply is the drafted message. The module is matched
    rather than the text, because the composer draws its pool twice (see `_thread_index`), and the
    draft is recognised by its own lead-in, so a composer reply that is a statement or a
    continuation never claims the turn this way.

    The offer half is read the same way and only on a line that asks for the words: "can you help
    me write a text to my landlord" got the tenancy entry, which answers about housing and not
    about the message, and its example text was about a rota for a different person entirely. A
    card can be right about the topic and still be the wrong answer to "write me the words", so
    the offer takes the turn and the next line is the message. Both readings live in
    bot/compose/draft.py, and the composer only offers when it has nothing to draft from.

    What the offer may not displace is another answer that hands the words over: the writing card
    answers the same line with the shape to aim at and "tell me who it is for and what you need
    and I will write yours", and a card can answer it with the note itself in quotation marks.
    Both are the offer plus something, so the turn is only taken when no other candidate promises
    to write the message or already hands one over, and the cards keep the lines they were
    written for.
    """
    for index, candidate in enumerate(candidates):
        if candidate.get("module") != fallback.FALLBACK_MODULE:
            continue
        reply = candidate.get("reply")
        if not _content(reply) or _content(reply) == last:
            return None
        if fallback.draft.names_a_draft(reply):
            return index
        if (clean and fallback.draft.offers_a_draft(reply)
                and fallback.draft.reads_as_a_writing_ask(clean)
                and not any(fallback.draft.offers_a_draft(other.get("reply"))
                            or fallback.draft.hands_over_words(other.get("reply"))
                            or fallback.draft.hands_over_the_shape(other.get("reply"))
                            for other in candidates if other is not candidate)):
            return index
        return None
    return None


def _a_leaving_said_plain(candidates, pool, clean, memory):
    """The index of the composer's reply to a leaving said as the news it is, or None.

    "my husband has left me" is the news, not a question about money, and the entry for a
    divorce answered it with the first job of a settlement: "Get the money apart quietly and
    early: open a current account in your own name". A plan for the day is not an answer to
    having just said your life has come apart - STYLE.md's worst reply is the one that reads as
    not having heard - so when the reply in front of this line hands over a job, the composer's
    line that hears it takes the turn.

    Only the line that says nothing else. An ask is answered by the entry ("my husband has left
    me, where do i stand on the house"), and so is a reply that already hears it (the entry for
    the same news says "Nothing you do this week makes it hurt less, so do not make decisions in
    it", which is not a job). The reading is bot/compose/badnews.py's and the wording is
    `fallback.LEFT_POOL`'s, so this is only the routing decision.
    """
    if not clean:
        return None
    try:
        if not (badnews.reads_as_the_leaving(clean)
                or badnews.reads_as_a_leaving_already_gone(clean)):
            return None
    except Exception:  # noqa: BLE001 - a reading that fails just adds no rule
        return None
    understood = memory.get("understood") or {}
    if (understood.get("kind") == "question"
            or understood.get("intent") in ("question", "request")
            or understood.get("help_ask") or understood.get("asks_a_verdict")):
        return None
    index = _is_loss_reply_in(candidates, pool,
                              pools=(fallback.LEFT_POOL, fallback.LEFT_POOL_GONE))
    if index is None:
        return None
    best = pool[0] if pool else None
    if best is None or not _opens_on_a_job(candidates[best].get("reply")):
        return None
    return index


def _sudden_loss_reply(candidates, pool, clean):
    """The index of the composer's reply to a sudden loss, or None.

    A pregnancy that has ended and a suicide among the people a person knows are read here
    rather than only in the gentle pool, because the pool's words ("that's frustrating, want a
    hand working out the next step") are for a setback, and because a module with a general
    bad-news line must not answer a bereavement as one. Bleeding in pregnancy comes with them:
    it is a midwife today, not a chat.

    The reading lives in bot/compose/badnews.py and the wording in bot/compose/fallback.py, so
    this is only the routing decision: when the composer has a line for this, it gets the turn.

    One ask is not a condolence: "my husband died in march and i dont know how to tell our
    daughter" wants the words to say to the child, and the knowledge base has them
    (`explaining-death-to-a-child`). The composer's own reading says when the ask is that
    (`fallback.asks_what_to_tell_a_child`), and on the day itself it says no, so a fresh death
    keeps the condolence whoever else proposed.
    """
    try:
        if not clean:
            return None
        if not (badnews.reads_as_sudden_loss(clean)
                or badnews.reads_as_pregnancy_bleeding(clean)):
            return None
        if fallback.asks_what_to_tell_a_child(clean) and _a_knowledge_entry_has_it(candidates):
            return None
        pools = (fallback.SUDDEN_LOSS, fallback.PREGNANCY_BLEEDING,
                 fallback.THE_FIRST_HOUR_AND_A_CHILD)
    except Exception:  # noqa: BLE001 - a reading that fails just adds no rule
        return None
    return _is_loss_reply_in(candidates, pool, pools)


def _the_words_for_the_child(candidates, clean, memory, last=""):
    """The index of the composer's words for a child, after a condolence.

    `_the_ask_about_a_child` above is the same ask in one line with the death, and it hands the
    turn to the entry. A turn later there is no death in the line at all - just "how do i tell a
    4 year old" - so the entry reads it as a general how-to and the card on screen time takes it,
    or the condolence's own drafter answers with a message for the bereaved. The composer reads
    the thread (`childwords.asks_the_words_for_a_child`) and has the words; this is only the
    routing decision, and it stands aside the moment that reading says no.
    """
    from ..compose import childwords
    try:
        if not clean or not childwords.asks_the_words_for_a_child(clean, memory):
            return None
    except Exception:  # noqa: BLE001 - a reading that fails just adds no rule
        return None
    for index, candidate in enumerate(candidates):
        if candidate.get("module") != fallback.FALLBACK_MODULE:
            continue
        reply = _content(candidate.get("reply"))
        if not reply or (last and reply == last):
            continue
        if reply in _the_words_for_a_child_pool():
            return index
    return None


def _a_whole_line_module_spoke(candidates):
    """True when a module that reads a whole line (grief, loss) has an answer of its own.

    Those modules answer the same follow-up better than a pool can: grief's `TELLING_REPLIES`
    has the name and the day ("\"your wife died on Tuesday\" is kinder than a soft way round
    it") where the child's words are three lines about how to say it at all. The reading is
    there for the turn those modules leave alone - the ask with no name in it, "how do i tell a
    4 year old", which grief reads as no question it knows and passes. So it stands aside the
    moment one of them speaks, the same way `_the_subject_was_answered` does for a card.
    """
    for candidate in candidates:
        if _priority(candidate) >= WHOLE_LINE_BAND and candidate.get("module") != fallback.FALLBACK_MODULE:
            return True
    return False


def _the_words_for_a_child_pool():
    """The composer's pool for a child's words, reduced the way the candidates are.

    `_content` drops punctuation and case, so a pool line has to be reduced the same way before
    the two can be compared (the em dash alone makes them unequal).
    """
    from ..compose import childwords
    return tuple(_content(line) for line in childwords.THE_WORDS_FOR_A_CHILD)


def _the_ask_about_a_child(candidates, clean, last=""):
    """The index of the knowledge entry that answers "how do I tell the child", else None.

    The person is not asking what to say to themselves about a death; they are asking for the
    words for a child, and the entry that has them (`explaining-death-to-a-child`) is the only
    reply that answers the question. `loss` answers bad news well and declares `ANSWERS_INSTEAD`,
    so without this the ask got advice for talking to a grown-up ("use the person's name, don't
    rush to fill the silence") on the lines the entry now reads: a niece, a grandson, "my girls".
    Read before that declaration, because the question is not the loss.

    Strict, and only on the lines the composer read whole: the reading says no to a death named
    as today and to the child who is the one who died, so a bereaved parent keeps the condolence.
    """
    try:
        if not fallback.asks_what_to_tell_a_child(clean):
            return None
    except Exception:  # noqa: BLE001 - a reading that fails just adds no rule
        return None
    for index, candidate in enumerate(candidates):
        if candidate.get("module") != "answers" or _priority(candidate) < 0:
            continue
        reply = _content(candidate.get("reply"))
        if not reply or (last and reply == last):
            continue
        return index
    return None


# A how-to about someone else is not about the speaker. "how do i stop my teenager staying up all
# night" was answered by the small-talk card written for the speaker's own night ("That's a hard
# one to carry into a day. Go easy on yourself today and aim for bed an hour earlier tonight"),
# with the entry that has the answer ("in the teen years the body clock shifts later by up to two
# hours") underneath it at a lower PRIORITY. The card never mentions the person the line is about.
# So on a how-to line that names someone else, a card that says nothing about them is passed over
# for a reply that does - the answer to "how do I stop my teenager" cannot be about my night.
# Only cards below the recall band are passed over (7000 and the safety band are answered as they
# come), and only for a knowledge entry that does say something about the person.
_A_HOW_TO = re.compile(
    r"^(?:how\s+(?:do|can|should|could|would)\s+(?:i|we|you)|how\s+to\b|"
    r"what(?:'?s|\s+is)\s+the\s+best\s+way\s+to|whats\s+the\s+best\s+way\s+to|"
    r"any\s+tips\s+(?:for|on)|what\s+should\s+i\s+do\s+(?:about|with))\b", re.I)
# The person the line is about, said as a relation rather than a name ("my teenager", "our son").
_THE_ONE_NAMED = re.compile(
    r"\b(?:my|our|his|her|their)\s+(?:teenager|teen|son|daughter|child|kid|boy|girl|mum|mom|"
    r"mother|dad|father|partner|husband|wife|boyfriend|girlfriend|flatmate|housemate|roommate|"
    r"friend|boss|manager|colleague|brother|sister|gran|granny|grandma|grandad|grandpa|baby|"
    r"toddler|nephew|niece|aunt|uncle|cousin)\b", re.I)
# Any person a line names, in either form: the relation a how-to is about ("my teenager") or
# somebody it meets by article ("a friend"). Only the first one in the line decides, because the
# how-to's subject is the person it starts with: "how do i console a friend whos just lost their
# dad" is a how-to about the friend and their grief, and the "their dad" further along is the
# person they lost, not the person to answer about.
_A_PERSON_NAMED = re.compile(
    r"\b(?:(?:my|our|his|her|their)\s+(?:teenager|teen|son|daughter|child|kid|boy|girl|mum|mom|"
    r"mother|dad|father|partner|husband|wife|boyfriend|girlfriend|flatmate|housemate|roommate|"
    r"friend|boss|manager|colleague|brother|sister|gran|granny|grandma|grandad|grandpa|baby|"
    r"toddler|nephew|niece|aunt|uncle|cousin)|"
    r"(?:a|an|the|this|that|one)\s+(?:friend|mate|neighbour|neighbor|colleague|coworker|"
    r"co-worker|classmate|loved\s+one|relative|family\s+member))\b", re.I)
# Whether a reply is about somebody other than the person being spoken to.
_ABOUT_SOMEONE_ELSE = re.compile(
    r"\b(?:they|them|their|theirs|themselves|he|she|him|his|hers)\b", re.I)


def _the_name_they_gave(candidates, text, memory):
    """The reply that takes up the name the bot has just asked for, or None.

    "we got a puppy on saturday" is answered "What's its name?", and the next line - "hes called
    biscuit", or just "biscuit" - is the answer to that question. The knowledge base reads the
    name as a subject instead: biscuit is a food, so the puppy got the biscuit recipe, which is
    the one reply nobody asked for. A line that only gives the name goes to the highest reply
    that says the name back, because that reply is the one that has taken the answer up.
    """
    if _naming is None:
        return None
    name = _naming.the_name_given(text, memory)
    if not name:
        return None
    said = name.lower()
    for index, candidate in enumerate(candidates):
        if _priority(candidate) < 0:
            continue
        if said in str(candidate.get("reply") or "").lower():
            return index
    return None


def _about_the_person_the_line_names(candidates, pool, clean, last=""):
    """The index of a reply about the person a how-to line names, when the front one is not.

    The card in front answers the speaker's own life; the entry below it answers the question
    about the other person. Read only on a how-to line that names someone ("how do i stop my
    teenager staying up all night"), so a line about the speaker is untouched. The person the
    how-to is about is the first person the line names, so "how do i console a friend whos just
    lost their dad" is about the friend and their grief, not a cue to answer about a dad. And a
    reply that says it cannot answer is never taken over the card in front, which can.
    """
    if not clean or not _A_HOW_TO.match(clean):
        return None
    named = _THE_ONE_NAMED.search(clean)
    if named is None:
        return None
    first = _A_PERSON_NAMED.search(clean)
    if first is None or first.start() != named.start():
        # the line names somebody else first ("how do i console a friend who lost their dad")
        return None
    word = named.group(0).split()[-1].lower()
    if _priority(candidates[pool[0]]) >= RECALL:
        return None  # the recall band and the safety band are answered as they come
    front = _content(candidates[pool[0]].get("reply"))
    if not front:
        return None
    if re.search(r"\b%ss?\b" % re.escape(word.rstrip("s")), front, re.I) or \
            _ABOUT_SOMEONE_ELSE.search(front):
        return None  # the reply in front already says something about them
    for index in pool[1:]:
        candidate = candidates[index]
        if _priority(candidate) >= RECALL or candidate.get("module") != "answers":
            continue
        reply = _content(candidate.get("reply"))
        if not reply or (last and reply == last):
            continue
        if fallback.is_a_hedge(reply):
            continue  # "I don't know enough to answer that" is not an improvement on the card
        if re.search(r"\b%ss?\b" % re.escape(word.rstrip("s")), reply, re.I) or \
                _ABOUT_SOMEONE_ELSE.search(reply):
            return index
    return None


def _a_knowledge_entry_has_it(candidates):
    """Whether the knowledge base proposed an answer to this line.

    The composer stands down for "how do I tell a child" only when something does have the
    words. The reading is a rough match on words, and a line it reads which no entry answers
    would otherwise lose its condolence to a nod: "my son died and i have to tell my daughter"
    is a bereaved parent, and the child who has to be told is the next turn, not this one.
    """
    for candidate in candidates:
        if int(candidate.get("priority") or 0) >= 0 and candidate.get("module") == "answers":
            return True
    return False


def _hurting_reply(candidates, pool, clean):
    """The index of the composer's reply to a wish to hurt somebody, or None.

    "i want to smack my son" reached the answer written for a child who is being hit, and came
    back "Being hit needs dealing with every time ... say the rule in one sentence" - a parent
    being told how to handle somebody else's violence while saying they want to smack their own
    child. The reading and the wording both live in bot/compose/harm.py, so this is only the
    routing decision: when the composer has a line for this, it gets the turn.
    """
    if _harm is None or not clean:
        return None
    try:
        if not _harm.reads_as_hurting_someone(clean):
            return None
    except Exception:  # noqa: BLE001 - a reading that fails just adds no rule
        return None
    for index in list(pool) + list(range(len(candidates))):
        try:
            if _harm.reads_as_our_reply(candidates[index].get("reply")):
                return index
        except Exception:  # noqa: BLE001 - a reply we cannot read answers nothing
            continue
    return None


def _story_goes_on_reply(text, memory, candidates, last=""):
    """The index of the composer's listening line for the next line of a hard story, or None.

    The reading lives in bot/memory/ack.py (`carries_the_story_on`: bad news in the last two
    turns, and this line about someone else doing something) and the wording next to it, so this
    is only the routing decision - the same shape as `_sudden_loss_reply` above, for the turn
    after bad news rather than the bad news itself.

    The one thread the listening reply does not keep is a thread that began with news that has a
    name in it: a condition on somebody they love, a court letter, an award stopped, the roof going
    (`badnews.NEWS_WITH_A_NAME`). Those lines are answered gently and then the person asks about
    the thing itself - "my dad has parkinsons" then "he keeps falling" is the falls card's turn,
    and "she keeps asking for her mum" after a diagnosis is the question the dementia answer is
    for. The listening line is for the thread a death, a break-up or a refusal began, where the
    next line is more of the same story - `_a_story_opened` reads the two, and `_a_refusal` keeps
    "she wont eat" after a diagnosis with the listening line rather than the feeding card.
    """
    if _ack is None:
        return None
    try:
        if not _ack.carries_the_story_on(text, memory):
            return None
        if (not _a_story_opened(memory) and not _a_refusal(text)
                and any(_priority(candidate) >= 0 for candidate in candidates)):
            # Named news - a condition on somebody, a stay in hospital - is news the next line
            # asks a question about ("my mum has cancer" / "she keeps falling" is the falls card),
            # so the module that answered it keeps the turn. After a death there is nothing to
            # answer and the listening line holds: "my nan died last week" / "he took the car" is
            # the story going on, and the motorway advice under it read as a shrug.
            return None
        pools = (_ack.THE_STORY_GOES_ON,)
        for index, candidate in enumerate(candidates):
            if int(candidate.get("priority") or 0) >= SAFETY:
                continue  # a real emergency is never passed over for a listening line
            reply = str(candidate.get("reply") or "").strip()
            if not reply or (last and _content(reply) == last):
                continue
            if any(reply in wanted for wanted in pools):
                return index
    except Exception:  # noqa: BLE001 - a reading that fails just adds no rule
        return None
    return None


def _a_story_opened(memory):
    """Whether the last turn or two said a death or a leaving, rather than news about somebody living.

    The listening line is for the line after a story has begun - "my nan died last week" / "he
    took the car", "my wife left me" / "she packed her things last night" - because there is
    nothing to answer and the person is telling it. After news about somebody who is still here
    ("my mum has cancer", "my son is in hospital") the next line asks about that: "she keeps
    falling" wants the falls card, and a listening line takes it away.
    """
    if _loss is None:
        return True  # no reading, no narrowing: the rule stays as it was
    for turn in (memory.get("turns") or [])[-2:]:
        if not isinstance(turn, dict):
            continue
        said = str(turn.get("user") or "").strip().lower()
        if not said:
            continue
        if _loss.reads_as_loss(said):
            return True
        try:
            if badnews.reads_as_the_leaving(said) or badnews.reads_as_a_leaving_already_gone(said):
                return True
        except Exception:  # noqa: BLE001 - a reading that fails just adds no widening
            continue
    return False


# A line that says somebody will not do something: "she wont eat", "she wont talk about it".
# After news about somebody living this is their state of mind rather than an event to act on, so
# it keeps the listening line - the feeding card ("one new food next to one they already eat") is
# advice for a fussy toddler, and a wife with cancer who will not eat is not that.
REFUSAL = re.compile(r"\b(?:won'?t|wont|wouldn'?t|refus\w*|isn'?t eating|not eating|"
                     r"doesn'?t want|does not want|gives? up|gave up|stops? eating)\b")


def _a_refusal(text):
    """Whether the line is somebody refusing something, rather than something happening to them."""
    return bool(REFUSAL.search(str(text or "").lower().replace("\u2019", "'")))


def _is_loss_reply_in(candidates, pool, pools):
    """The index of the candidate whose reply is one of these pools' lines, else None."""
    for index in list(pool) + list(range(len(candidates))):
        text = str(candidates[index].get("reply") or "").strip()
        if text and any(text in wanted for wanted in pools):
            return index
    return None


def _composer_reading(clean, memory):
    """What the composer says this line is: (kind, target), or ("", ()) for an ordinary line.

    The routing lane's one door to bot/compose/: a line still inside a safety thread is the one
    kind of line the rest of the app must not answer as small talk, and the composer owns both
    the judgement and the wording. The arbiter only decides when a module keeps the turn
    instead. Adding a second kind is one branch in the composer and one here, never a second
    scanning loop.
    """
    try:
        from ..compose import fallback as composer
        kind, target = composer.reading(clean, memory)
    except Exception:  # noqa: BLE001 - a composer that cannot answer changes no reply
        return "", ()
    return (kind, target) if kind else ("", ())


def _carries_the_answer(reply, memory):
    """True when a reply comes back to the answer the bot gave a turn ago, else False.

    The reading is the composer's (bot/compose/verdict.py): the step a follow-up asks for is in
    that answer, so a line that carries a run of its words is answering the same question, and
    one that shares nothing with it is a different fact about the same topic.
    """
    if not reply:
        return False
    try:
        from ..compose import verdict as composer
        return bool(composer.carries_the_answer(reply, memory))
    except Exception:  # noqa: BLE001 - a composer that cannot answer holds nothing back
        return False


def _opens_on_a_job(reply):
    """True when a reply opens on an instruction, so it is already the next step, else False."""
    if not reply:
        return False
    try:
        from ..compose import verdict as composer
        return bool(composer.opens_on_a_job(reply))
    except Exception:  # noqa: BLE001 - a composer that cannot answer holds nothing back
        return False


def _is_a_generic_step(reply):
    """True when a reply is one of the composer's own generic first-step lines, else False.

    The pool is the composer's (bot/compose/__init__.py, `STEP_WHEN_LOW`), read here rather than
    restated: the step lines say the same few things to everybody, which is what makes them a
    fallback, and an entry that answers the subject with something concrete is not a fallback.
    A composer without the pool declares nothing, and then nothing is read as one.
    """
    if not reply or not _STEP_WHEN_LOW:
        return False
    return reply.strip() in _STEP_WHEN_LOW


def _named_topics(memory):
    """The topics the line itself names, not the one the reading infers from the kind of line.

    `understood["topics"]` is what the words in front of the bot point at ("my hand is still
    sore" -> health); `understood["topic"]` also carries the fallback the reader uses for a kind
    of line ("hiya" -> small-talk). A module keeps its turn inside an emergency because the
    person asked about its subject, so only the first counts: a bare greeting is not asking
    chat about small talk, and on a live crisis thread it was getting "Morning! How's your day
    going?" while the composer was still answering it.
    """
    understood = memory.get("understood")
    if not isinstance(understood, dict):
        return set()
    return _labels(understood.get("topics")) - CHITCHAT


# The label the reader gives a line that carries no subject of its own ("how are you" is
# "small-talk", not a topic). A module that declares it is not answering a question asked, so
# it is not a reason to take a live emergency thread away from the composer: what the person
# is doing mid-emergency is checking the bot is still there, and chat's "Doing well, thanks"
# was the answer. Content labels (health, cooking) still keep their turn, as before.
CHITCHAT = frozenset(("small talk",))


def _thread_index(candidates, real, own, target, last, care_about="", memory=None):
    """The composer's continuation for a safety thread, or None.

    After the bot has answered an emergency, the next line ("im scared") is not small talk: it
    is the same thread, and a light module proposing a reframe would win it on PRIORITY. The
    composer already has a continuation for exactly that line, so the routing decision is to
    give the turn to the module the composer answers through - `fallback.FALLBACK_MODULE`,
    the one module whose whole reply is the composer's - and to nothing else. The wording
    stays in bot/compose/ for the composer lane to own.

    Matching the *module* rather than the text is what makes the thread hold: the composer
    draws its continuation from a pool, and the draw the arbiter makes and the draw the
    module makes are two calls, so a text match only holds while both pick the same line. On
    the ones where they differed ("you there?" after "my dad is having chest pain"), chat's
    "Yep, I'm here" took a live emergency thread - the flaky red in `test_chat`.

    A module that declares the line's own topic is answering the question asked, so it keeps
    its turn even inside the thread (a health entry quoted back mid-emergency).

    The one exception is a follow-up about the very thing the bot has just answered, in a
    first-aid thread: "can i pop the blister" after the scald answer names a word the clothing
    entry claims, and that entry's answer ("break new shoes in slowly") is for a different
    person with a different blister. The composer's continuation is the burn's own line, so it
    keeps the thread. It takes both halves to say so: the thread must be a care thread (a
    crisis answer's next question is often about something else), and the line must name
    something the last answer named - a new question in the thread still goes to its entry.
    """
    text = target[0] if target else ""
    if not _content(text):
        return None
    # The line asks about the thing the thread has answered. The thread's answer is read as well
    # as the last reply, because inside a care thread the last reply is a pool line: "Don't put
    # anything on a burn - not butter, not cream, not ice. Twenty minutes under cool running
    # water, then a loose clean dressing" never says "blister", and "can i pop the blister" was
    # answered by the blister-plaster entry (shoes) instead of the burn's own line.
    asks = fallback.asks_about_a_care_answer(care_about, last, memory, own)
    if any(own and _labels(_answered(candidates[index].get("module"))) & own
           for index in real) and not asks:
        return None
    for index, candidate in enumerate(candidates):
        if _priority(candidate) < 0 and candidate.get("module") == fallback.FALLBACK_MODULE:
            reply = _content(candidate.get("reply"))
            if not reply or reply == last:
                return None  # nothing to say, or the same line again
            if asks:
                # Both candidates can be on topic, and priority does not say which one continues
                # the conversation. The reply that says more of the answer in hand does: the
                # burn's own line shares ten of its words, the shoe answer ("a padded blister
                # plaster and wear the shoes for short stretches") shares three, while for
                # "should i cover the blister" it is the entry's "cover it with a clean
                # non-fluffy dressing" that carries the answer and the pool line that carries
                # none of it. So the entry keeps the turn where it is the answer, and the
                # composer keeps it where the entry is about another thing. See
                # `fallback.how_much_of_the_answer_kept`.
                mine = fallback.how_much_of_the_answer_kept(candidate.get("reply"), memory)
                for other in real:
                    closer = fallback.how_much_of_the_answer_kept(
                        candidates[other].get("reply"), memory)
                    if closer > mine:
                        return other
            return index  # the composer's continuation for this thread
    return None


def _answers_this_line(reply):
    """True when a line from below the floor tells the person something to do, else False.

    Asked only where every real candidate is a slice of the last answer, so the choice is between
    the paragraph again and a line the composer wrote. A line that opens on a job ("Fix it if it is
    a part and a few pounds; bin it if the repair is half the price of new") answers the turn - it
    says what to do about the thing the person asked about - and it takes the turn. A nod is not:
    "Got it - it goes off in two days" and "I'm not sure about that one, sorry" would fit any
    message, and the answer's slice again is better than either. The reading is the composer's
    (`bot/compose/verdict.py: opens_on_a_job`), so the arbiter keeps no vocabulary of its own.
    """
    if not reply or fallback.is_said_it_already(reply):
        return False
    return _opens_on_a_job(reply)


def _content(reply):
    """A reply reduced to what it says, for the never-repeat rule."""
    return " ".join(WORD.findall(str(reply or "").lower()))


def _echoes(reply, last, announced=False):
    """True when a reply is only words the bot said in its last answer.

    Two shapes. The first is the last answer said again with a nod in front: a bare follow-up
    ("why is that", "what should i do") is answered "Same as before: <the opening of the last
    answer>", which is not a second answer, because the person read those words a turn ago and is
    asking about them. The never-repeat rule compared whole replies, so a reply with three words
    in front of the last one read as a fresh candidate.

    The second is a slice of the answer with nothing in front of it: after "my washing machines
    making a bang on the spin", "is it worth fixing or shall i just get a new one" got the
    sentence about the transport bolts, which is the branch of that answer the person had not read
    - words already on the screen, dressed as a reply to a question they never answered.

    The shape stays narrow on purpose, so nothing that adds anything can be taken for a repeat: at
    most six words of lead-in, then twelve words or more of the last answer word for word, in one
    run to the end of the reply. Anything the candidate says of its own after the run is new, and
    a reply shorter than twelve words is a sentence a friend might choose to say again.
    """
    words = _content(reply).split()
    previous = _content(last).split()
    if len(previous) < 12 or len(words) < 12:
        return False
    for lead in range(0, min(6, len(words) - 12) + 1):
        run = words[lead:]
        if len(run) >= 12 and _a_run_of(previous, run):
            return True
    # A lead that names itself as a repeat is longer than the six words allowed above, so it is
    # read only where the never-repeat rule must decide a claim, and only when asked for: "Same as
    # before: <the whole answer>" would otherwise count as a repeat in `_choose`, where the answer
    # said again is the only thing on the table and the fallback's question ("tell me what it is
    # for") would take the turn off it - "what do i bring" after the meeting-the-parents answer
    # lost "Take something small for the house" that way in a blind sample.
    if announced:
        handed = _the_quoted_repeat(reply)
        if handed:
            run = handed.split()
            if len(run) >= 8 and _a_run_of(previous, run):
                return True
    return False


# A claim that reads the answer back is not a claim: how much of the last answer has to come
# first, and how much the reply may add after it, to say the reply is the answer again with a
# comment on the end rather than a second answer.
AGAIN_FIRST_WORDS = 16
AGAIN_TAIL_WORDS = 12


def _the_answer_again_with_a_tail(reply, last):
    """True when the reply opens on the last answer and then adds a short remark of its own.

    `_echoes` reads two shapes of repeat, and both of them end in the answer: a lead and then the
    answer, or a slice of it with nothing after. This is the third shape, and the one a claim uses
    to keep a line it should have given up: the whole answer, word for word from its first word,
    and then a sentence of its own on the end.

    "im knackered all the time" / "i only get about five hours sleep" is the case. The memory
    store answers as it comes, and what it handed back was the tiredness answer from the top -
    every word of it - with "Five hours is more than enough for all of that" added. The
    knowledge entry beside it had the answer the line asked for ("Five hours is on the short side:
    most adults need seven to nine"), and the store's tail was not only a repeat, it was the
    opposite of what the card says. The tail is new, so `_echoes` leaves the whole reply alone;
    this reading says the reply is the answer again, and settling a claim on it hands the person
    the paragraph they read a turn ago.

    Narrow on purpose: the answer has to be sixteen words or more, the reply has to open on it
    from the first word, and what comes after may be no more than twelve. A store that quotes a
    line and adds the one thing that matters most is doing its job, so that is not this shape.
    """
    words = _content(reply).split()
    previous = _content(last).split()
    if len(previous) < AGAIN_FIRST_WORDS:
        return False
    same = 0
    while same < len(words) and same < len(previous) and words[same] == previous[same]:
        same += 1
    return same >= AGAIN_FIRST_WORDS and len(words) - same <= AGAIN_TAIL_WORDS


def _the_quoted_repeat(reply):
    """The part of the last answer a lead says it is handing back, or None.

    A lead that names itself as a repeat ("It's what I said a moment ago: ...", "Same answer:
    ...") is longer than the six words `_echoes` allows in front of a quote, so a reply wearing
    one was read as a new answer when it was the paragraph again. The lead has to be one the
    other lanes write themselves (`_repeat_leads`, the same list `_announces_a_repeat` reads),
    and the words after it have to be the answer's, because a lead that says it is handing on the
    *next* part of the answer ("There was a second bit to that answer: ...") is the answer the
    person has not read yet and must not be taken for a repeat.

    Not called `_announces_a_repeat`: that is the rule that settles a turn where every candidate
    is the answer over again, and it answers yes or no. A second function of that name read every
    reply as the quiet one and turned "what do i bring" from the answer in hand into a question.
    """
    text = _content(reply)
    if not text:
        return None
    heads = [_content(lead) for lead in _repeat_leads()]
    # The memory lane's own leads are the long ones ("It's what I said a moment ago: {said}",
    # "From just now: {said}"), which is why this reading exists at all.
    try:
        heads.extend(_content(str(frame).split("{")[0]) for frame in getattr(_repeat, "LEADS", ()))
    except Exception:  # noqa: BLE001 - a lane that cannot be read adds no lead
        pass
    for head in heads:
        if head and text.startswith(head):
            return text[len(head):].strip()
    return None


# A reply that answers by pointing at the answer already on the screen, rather than saying
# anything: the knowledge entry found the follow-up again and came back with a short form of the
# answer it just gave, so the turn says where the answer is instead of reading it out a second
# time (bot/modules/answers.py, SAID_ABOVE and NOTHING_SEPARATE). The words are new, and that is
# the whole trouble: the never-repeat rule compares wording, so a line that adds nothing at all
# read as the one fresh candidate on the table and took the turn off a real answer.
A_POINTS_BACK = re.compile(
    r"\bis in what I said above\b|\bis in the answer above\b|\bis covered by the answer above\b"
    r"|\bwhat I said above is the whole of it\b|\bthan what I said above\b"
    r"|\bis the whole of what I have on it\b"
    r"|\bnothing separate on\b|\bnothing more on\b|\bno separate answer for\b",
    re.IGNORECASE)


def _points_back(reply):
    """True when the reply only says the answer above covers the thing, adding nothing."""
    return bool(A_POINTS_BACK.search(str(reply or "")))


def _a_run_of(previous, run):
    """True when `run` is a continuous run of words inside `previous`, the last reply."""
    size = len(run)
    return any(previous[start:start + size] == run
               for start in range(0, len(previous) - size + 1))


def _the_answer_written_out(memory):
    """The last answer as the person read it: punctuation and case kept."""
    turns = memory.get("turns")
    if isinstance(turns, list) and turns and isinstance(turns[-1], dict):
        return str(turns[-1].get("bot") or "")
    return ""


def _last_reply(memory):
    turns = memory.get("turns")
    if isinstance(turns, list) and turns and isinstance(turns[-1], dict):
        return _content(turns[-1].get("bot"))
    return ""


def _said_before(memory, text):
    """Whole answers the bot has already given this person, as `_content` strings.

    Only answers of two or three sentences count (`at least eight words`): a short "Got it." is
    a thing a friend says twice and no repeat, and it is never the whole of a real answer. The
    turn being answered is not in `memory["turns"]` yet, so this is the conversation so far.

    A turn whose question is this line word for word is left out: the same question asked again
    is answered again, in the wording the repeat frame gives it (`bot/memory/again.py`), and
    that rule is what tells the person where the answer went. So this is only the answers to
    other questions, which have no business coming back here.
    """
    said = set()
    turns = memory.get("turns")
    if not isinstance(turns, list):
        return said
    asked = _content(text)
    for turn in turns:
        if not isinstance(turn, dict):
            continue
        if asked and _content(turn.get("user")) == asked:
            continue
        reply = _content(turn.get("bot"))
        if len(reply.split()) >= 8:
            said.add(reply)
    return said


def _about(text, memory):
    """What this turn is about: (the topic the reading gives it, the topic only a stored record
    names, the line's words, the whole line), all lower case.

    The first set is the understanding engine's reading of this turn, `understood["topics"]`
    (the line by itself) and `["topic"]` (the line plus what a follow-up inherits from the
    conversation), and both count 2: they are one reading, and the engine has already decided
    how much a follow-up leans on the line before. So on a follow-up the conversation's topic
    ties with the line's own, and PRIORITY settles it - whether that is the right rule is
    written down in the routing lane plan, not decided here. Only a record that names a topic
    outright (`memory["topic"] = {"label": "cooking"}`, the shape the memory lane agreed) is
    the weaker signal, at 1.
    """
    understood = memory.get("understood")
    own = set()
    words = set()
    if isinstance(understood, dict):
        own |= _labels(understood.get("topics"))
        own |= _labels(understood.get("topic"))
        for word in _strings(understood.get("words")):
            words.update(WORD.findall(word.lower()))
    carried = _labels(memory.get("topic")) - own
    clean = " ".join(WORD.findall(str(text).lower()))
    words.update(clean.split())
    return own, carried, words, clean


def _strings(value):
    """The strings in value, one level deep (a list, a tuple, a set, or one string)."""
    if isinstance(value, str):
        return [value]
    if isinstance(value, (list, tuple, set, frozenset)):
        return [item for item in value if isinstance(item, str)]
    return []


def _label(value):
    """One topic label, canonical: lower case words joined by spaces, so "small-talk",
    "Small talk" and "small_talk" are the same topic."""
    return " ".join(WORD.findall(str(value).lower()))


def _labels(value):
    """The topic labels in a value the understanding engine or the conversation wrote: a label,
    a list of labels, one of the records a lane writes (`{"id": ...}` from the understanding
    engine, `{"label": ...}` or `{"text": ...}` from the memory store), or a mapping of topic
    -> score. Anything else, including a whole memory dict, adds nothing.

    A record is read from its label key only. The other keys of a record describe it ("turn",
    "kind", "words") and are not labels, so reading them would make every specialist miss
    the topic and the specialist rule silent."""
    found = set()
    if isinstance(value, str):
        found.add(_label(value))
    elif isinstance(value, dict):
        found |= _stored(value)
        for key in LABEL_KEYS:
            if isinstance(value.get(key), str):
                found.add(_label(value[key]))
                break
        else:
            if "topics" in value:
                found |= _labels(value.get("topics"))
            elif value and all(not isinstance(item, (dict, list, tuple))
                               for item in value.values()):
                for key in value:  # a mapping of topic -> score
                    if isinstance(key, str) and key not in LABEL_KEYS:
                        found.add(_label(key))
    elif isinstance(value, (list, tuple, set, frozenset)):
        for item in value:
            found |= _labels(item)
    found.discard("")
    return found


def _stored(record):
    """The topic of the line the conversation is on, when a record only keeps the line itself
    (`{"turn", "text", "words"}`, the shape the memory store writes). The stored line is read
    with the understanding engine, the same reader the current line gets, so a follow-up ("and
    how long?") is about what the earlier line was about and the specialist rule still fires.
    """
    text = record.get("text") if isinstance(record.get("text"), str) else ""
    if not text.strip():
        text = " ".join(_strings(record.get("words")))
    return _read_topic(text)


def _read_topic(text):
    """The topic id the understanding engine gives for a line, or nothing when it gives none."""
    key = " ".join(WORD.findall(str(text or "").lower()))
    if not key:
        return set()
    found = READ.get(key)
    if found is None:
        try:
            from ..understanding import topics as understood
            from ..understanding.normalize import normalise
            read = normalise(key)
            topic, score = understood.detect_topic(read, None, understood.detect_entities(read))
            found = {_label(topic)} if topic and score >= 2 else set()
        except Exception:  # noqa: BLE001 - a reader that fails adds no topic
            found = set()
        READ[key] = found
    return set(found)


def _answered(module_name):
    """The topic labels a module declares it answers. Declared per module, so it is read from
    the module itself (README.md, "Interface")."""
    try:
        module = importlib.import_module("." + str(module_name), __package__)
    except Exception:  # noqa: BLE001 - a module that cannot be read declares nothing
        return set()
    return _labels(getattr(module, DECLARED_TOPICS, ()))


def _match(module_name, own, carried, words, clean):
    """How well a module's declared topics fit this turn: 2 for a topic id the reading gives
    this turn (the line, or on a follow-up the conversation it is still on), 1 for one only a
    stored record names, 1 for a declared phrase or word the line contains. 0 when it declares
    nothing that fits, so a generalist keeps its PRIORITY over a specialist of some other
    topic."""
    score = 0
    padded = " " + clean + " "
    for label in _answered(module_name):
        if label in own:
            score += 2
        elif label in carried:
            score += 1
        elif " " in label:
            if " " + label + " " in padded:
                score += 1
        elif label in words:
            score += 1
    return score


# The subject the line names: the thing after "my", "the", "your" - the bins in "my bins were
# left out and not emptied", the washing in "my washing was left out in the rain". A line about a
# feeling names no such thing ("i feel lonely at work"), which is the difference between a stock
# take answering a reading of the line and a card answering the thing in it.
def _the_subject_words(text):
    """The words the line says its subject with - what follows a determiner, else an empty set."""
    words = set()
    for phrase in A_SUBJECT_PHRASE.findall(str(text or "").lower()):
        words.update(word for word in A_SUBJECT_WORD.findall(phrase)
                     if word not in NOT_A_SUBJECT_WORD)
    return words


def _the_lines_own_words(text, memory):
    """The words of the line that say what it is about, else an empty set."""
    understood = memory.get("understood") if isinstance(memory, dict) else None
    words = _the_subject_words(text)
    if isinstance(understood, dict) and understood:
        subject = understood.get("subject")
        if isinstance(subject, str) and subject:
            words.update(A_SUBJECT_WORD.findall(subject.lower()))
        words.update(word for word in _the_subject_words(subject or "")
                     if word not in NOT_A_SUBJECT_WORD)
    return {word for word in words if word not in NOT_A_SUBJECT_WORD}


def _the_forms_of(word):
    """The word and the endings English puts on it - "bins", "bin", "emptied", "emptying"."""
    forms = {word}
    if word.endswith("s") and len(word) > 3:
        forms.add(word[:-1])
        if word.endswith("es") and len(word) > 4:
            forms.add(word[:-2])
    if word.endswith("ed") and len(word) > 4:
        forms.update((word[:-2], word[:-1]))
    if word.endswith("ing") and len(word) > 5:
        forms.update((word[:-3], word[:-3] + "e"))
    return {form for form in forms if len(form) >= 3}


def _the_same_word(said, word):
    """True when `said` is a form of `word` - "bin" for "bins", "empty" for "emptied"."""
    return said in _the_forms_of(word)


def _names_a_word_of(a_reply, words):
    """True when the reply says one of `words` as a word of its own, not merely a sound of it."""
    said = A_SUBJECT_WORD.findall(_content(a_reply))
    return any(_the_same_word(one, word) for one in said for word in words)


def _a_card_names_the_line(candidates, index, text, memory):
    """True when another real candidate names the line's own words and this one names none.

    A stock line can never name the thing the person said - it does not know it - so a take that
    shares no word with the line is the one case where a card beside it answers more of the line
    than the take does. Every line whose words the take does say is left alone, as is every line
    with no card beside it: this passes over a candidate, it never chooses one, and no PRIORITY is
    read or changed anywhere.
    """
    words = _the_lines_own_words(text, memory)
    if not words:
        return False
    if _names_a_word_of(candidates[index].get("reply"), words):
        return False
    for other, other_candidate in enumerate(candidates):
        if other == index or _priority(other_candidate) < 0:
            continue
        if _names_a_word_of(other_candidate.get("reply"), words):
            return True
    return False


def _a_card_that_names_the_line(candidates, pool, text, memory):
    """The index of a card that names the line where the chosen take names nothing of it.

    Read off the reading's own keywords, so a reply that shares one of them is about the line by
    the same reading that says what the line is about. Only a take below the chatter band is
    passed over, and only for a real candidate beside it: this never picks a fallback, and no
    PRIORITY is read or changed.
    """
    if len(pool) < 2 or _priority(candidates[pool[0]]) >= CHATTER:
        return None
    words = _the_lines_own_words(text, memory)
    if not words or _names_a_word_of(candidates[pool[0]].get("reply"), words):
        return None
    for index in pool[1:]:
        if _priority(candidates[index]) < 0:
            continue
        if _names_a_word_of(candidates[index].get("reply"), words):
            return index
    return None
