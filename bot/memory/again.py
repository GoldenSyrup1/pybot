"""The same paragraph is about to be said twice: say the short of it, framed as the repeat it is.

STYLE.md rules out the same answer twice in a row. `bot/memory/topics.said_again` frames a repeat
with a lead-in, but it stands aside when the line names something of its own: "he keeps coming
into our bed at 2am" is a new detail, so the turn is not "the same ask again" and the lead-in is
withheld - and the entry the line reaches has nothing new to say, so the paragraph goes out byte
for byte as before. The person has just told the bot something and gets back what they already
read:

    my son is 6 and he wont sleep
      Walk them back every time with the same short line - "it's sleep time, I love you" - and ...
    he keeps coming into our bed at 2am
      (the same paragraph, word for word)

The answer is still right, so it is not replaced: it is cut to the sentence with the move in it
and the lead-in says the answer has not changed, which also leaves the door open for the person
to say what did not work.
"""
import re
import string

from ..understanding import lexicon
from . import topics
from . import quotes as quoted

# A reply shorter than this many words is already the short of itself, so it is framed whole.
SHORT = 14

# A sentence break, for cutting an answer to its first sentence.
SENTENCE = re.compile(r"(?<=[.!?])\s+")

# The lead-in says the answer has not changed, and it moves on with each repeat: a person who
# says the same thing three times does not read "same answer" three times.
AGAIN = (
    "Same answer, and it covers this: {reply}",
    "That is still the thing to do: {reply}",
    "Nothing new to add on it: {reply}",
)
# The same for an answer that is already the short of itself: "On Tuesday." framed as "Same
# answer, and it covers this: On Tuesday." is a sentence about nothing, and the lead-in is the
# only part that has to be there, because the arbiter passes over a reply that repeats the last
# answer word for word.
SHORT_AGAIN = (
    "Same as before: {reply}",
    "As I said: {reply}",
    "Still: {reply}",
)


# Asked a third time the answer is not landing, so the bot says so and asks what went wrong rather
# than handing over the same paragraph again.
AGAIN_HELP = "Same answer I'm afraid: {reply} If that hasn't worked for you, tell me what went wrong and I'll take it from there."

# A follow-up that names a *detail* of the thing the answer was about ("what about the biting"
# after the chewing answer) reaches the same entry again, and the entry has one paragraph for the
# whole subject: on its own words it is not the same line, so the repeat is not counted by the
# line and the paragraph came back word for word. The detail is named in the lead-in instead, so
# the person hears that the answer covers it, and the short form is given rather than the lot.
DETAIL_AGAIN = (
    "Same for {detail}: {reply}",
    "Same answer for {detail}: {reply}",
    "It is the same for {detail}: {reply}",
    "Same again for {detail}: {reply}",
)
# When no sentence of the answer says the detail by name, the lead-in must not claim that it does:
# "Same for the biting: Chewing is normal while teeth change..." is one word doing another's job,
# and a friend asked about biting does not answer about chewing under the word "biting". What is
# true is that the entry has nothing separate for it, so that is what the lead says, and the short
# form of the answer follows - the turn is neither a claim that is wrong nor the paragraph word
# for word on the screen a second time (STYLE.md, "Never answer the same way twice in a row").
SAME_ADVICE = (
    "Nothing separate for {detail} - it is the same advice: {reply}",
    "Nothing different for {detail} I'm afraid: the same answer covers it - {reply}",
    "No separate fix for {detail} - the same advice as before: {reply}",
    "Nothing more for {detail}: the same answer covers it - {reply}",
)
# The answer is one the chat has already had, but it is not the turn just before: the person
# went off to something else and has come back. Said as "Same as before", a return reads like a
# glitch - they know they asked before, they asked again for a reason. The lead names the thing
# they came back to and the short of the answer follows, so the return is acknowledged and the
# answer is on the screen for a second time in different words.
RETURN = (
    "Back to {detail}: {reply}",
    "Back to {detail} then: {reply}",
    "Back on {detail} again: {reply}",
    "As we said about {detail}: {reply}",
)

# Said a third time, the bot may not talk about its own stock again. The second lead-in already
# said the answer had not changed; a third "nothing further to add" or "nothing different for
# empty I'm afraid" is the bot reporting on itself, which STYLE.md gives it only when a person
# asks about the bot, and the "empty" in it is an adjective lifted out of the line as if it were a
# thing the answer could have a part for. What a friend does on the third saying is put the
# person's own words next to the answer: the word they chose is the new thing on the screen, and
# it says the answer has not changed without a claim about what the bot holds.
#
#     i feel low / everything feels flat / i feel empty / nothing interests me
#     -> "Feeling empty is the same thing underneath, and the step is the same: Do one small thing"
#     -> "Nothing interests you - that is the same thing underneath, and the step is the same: ..."
UNDERNEATH_SAID = (
    "{said} is the same thing underneath, and the step is the same: {reply}",
    "{said} is the same thing again, so the step has not changed: {reply}",
)
# A line that is a whole clause ("nothing interests me", "everything feels flat") is not a subject,
# so it cannot take "is" after it: it stands on its own and the frame follows.
UNDERNEATH_CLAUSE = (
    "{said} - that is the same thing underneath, and the step is the same: {reply}",
    "{said}, and it comes to the same thing: {reply}",
)

# Every frame in the codebase that carries an answer behind a lead-in, in one place: this module
# and `topics.REPEAT` say the answer has not changed, the two above name the detail the line
# asked about, and the knowledge module has a wording of its own for a line asked a third time.
# A reply under any of them is the answer already on the screen, so a caller deciding whether its
# own reading found anything new has to look at the body, not at the lead-in - and a frame added
# anywhere else has to be added here, or its answers read as new words.
FRAMES = (AGAIN + (AGAIN_HELP,) + DETAIL_AGAIN + SAME_ADVICE + RETURN
          + UNDERNEATH_SAID + UNDERNEATH_CLAUSE + topics.REPEAT)
# The words that turn round when the bot says the person's own line back to them.
FOR_THE_PERSON = {
    "i": "you", "me": "you", "my": "your", "mine": "yours", "myself": "yourself", "am": "are",
    "i'm": "you're", "im": "you're", "i've": "you've", "i'll": "you'll", "i'd": "you'd",
    "we": "you", "our": "your", "us": "you", "was": "were",
}

# A slot other than the answer's own, `{detail}`, which the lead-in fills with whatever the line
# named: the lead it puts in front of the answer is not one string but a family of them.
SLOT = re.compile(r"\{[a-z_]+\}")


# The shapes of line the frame above can be built from, and nothing else: a phrase built from a
# line it does not know reads as one word doing another's job ("Sorry how do I cook rice is the
# same thing underneath"). These are the shapes people use to say how they are, which is where
# the same answer comes back a third time.
FEELING = re.compile(r"^(?:i\s+feel|i\s+felt|i'?m\s+feeling|i\s+am\s+feeling|feeling)\s+(.+)$", re.I)
CANNOT = re.compile(r"^(?:i\s+can'?t|i\s+cannot|i\s+can\s+not|i'?m\s+not\s+able\s+to)\s+(.+)$", re.I)
BEING = re.compile(r"^(?:i'?m|i\s+am)\s+(?:so\s+|really\s+|very\s+|still\s+|just\s+|quite\s+)?(.+)$", re.I)
NOTHING = re.compile(r"^nothing\s+(\w+)\s+me$", re.I)
# A line that is a sentence about how things are, with no "I" in it: "everything feels flat".
CLAUSE_ONLY = re.compile(r"^(?:everything|nobody|nothing|life|things|it|this)\s+\S", re.I)
# A word at the front of a line that says nothing about what the person feels.
OPENING_FILLER = re.compile(r"^(?:so|and|but|yeah|yeah|well|honestly|tbh|idk|dunno|just|ok|okay|"
                            r"hi|hey)\b[ ,]*", re.I)
# A phrase longer than this is a sentence about something rather than a word for how somebody is.
A_PHRASE = 8


def as_a_phrase(text):
    """The person's own words for it as a phrase, and whether it can stand as a subject.

    Returns `(kind, phrase)` where kind is "said" for a phrase that takes "is" ("Feeling empty"),
    "clause" for a whole clause that does not ("Nothing interests you"), or None when the line is
    not one of the shapes this frame can be built from. The pronouns are turned round, because the
    phrase is the bot saying their own words back to them: "i feel empty" is "Feeling empty",
    "nothing interests me" is "Nothing interests you".

    The store hands the reader the chat's last lines joined ("i feel low, i feel empty"), so the
    line is read clause by clause and the newest one that is a shape is the phrase: what the person
    has just said is the word for it now.
    """
    if not isinstance(text, str):
        return None
    whole = _a_phrase_of(text)
    if whole:
        return whole
    clauses = [part for part in re.split(r"[,;]|\band\b|\bbut\b|\bso\b", text) if part.strip()]
    for clause in reversed(clauses[1:] if len(clauses) > 1 else []):
        made = _a_phrase_of(clause)
        if made:
            return made
    return None


def _a_phrase_of(text):
    """`as_a_phrase` for one clause of the line."""
    if not isinstance(text, str):
        return None
    line = OPENING_FILLER.sub("", text.strip().rstrip(".!,")).strip()
    if not line or len(line.split()) > A_PHRASE or "?" in line:
        return None
    found = NOTHING.match(line)
    if found:
        verb = found.group(1).lower()
        if verb.endswith("s") and verb not in ("is", "was", "has"):
            return ("clause", "Nothing " + verb + " you")
        return None
    for pattern in (FEELING, CANNOT):
        found = pattern.match(line)
        if found:
            rest = _for_the_person(found.group(1))
            if not rest or len(rest.split()) > A_PHRASE - 1:
                return None
            if "," in rest or ";" in rest or _says_i(found.group(1)):
                return None  # two clauses said in one line ("i feel low, i feel empty")
            if rest.split()[0].lower() in ("to", "that", "like", "as", "so"):
                return None  # "Feeling to stop" is not a thing a friend says
            if pattern is CANNOT:
                return ("said", "Not being able to " + rest)
            return ("said", "Feeling " + rest)
    found = CLAUSE_ONLY.match(line)
    if found:
        # A whole sentence about how things are: "everything feels flat", "life feels pointless".
        # It stands as its own clause, so it is said back as one rather than turned into a subject.
        turned = _for_the_person(line)
        return ("clause", turned[:1].upper() + turned[1:])
    found = BEING.match(line)
    if found:
        rest = _for_the_person(found.group(1))
        if "," in rest:
            return None
        words = rest.split()
        if not words or len(words) > 3:
            return None
        if words[-1].lower().endswith("ing") or words[0].lower() in ("going", "gonna", "about", "not"):
            return None  # "Being not sleeping" is not a thing a friend says
        if any(word.lower() in ("to", "the", "a", "an", "my", "your") for word in words):
            return None
        return ("said", "Being " + rest)
    return None


def _says_i(text):
    """True when the words hold a first person still to turn, so they are more than one clause."""
    return any(word.strip(string.punctuation).lower() in FOR_THE_PERSON
               for word in str(text or "").split())


def _for_the_person(text):
    """`text` with the first person turned round: "my head is banging" -> "your head is banging"."""
    words = []
    for word in str(text or "").split():
        bare = word.strip(string.punctuation).lower()
        ending = word[len(word.rstrip(string.punctuation)):]
        head = word[:len(word) - len(ending)] if ending else word
        if bare in FOR_THE_PERSON:
            turned = FOR_THE_PERSON[bare]
            if word[:1].isupper():
                turned = turned.capitalize()
            words.append(turned + ending)
        else:
            words.append(word)
    return " ".join(words)


def the_same_thing_underneath(text, reply, times, memory=None):
    """The answer behind the person's own word for it, once the frame has been said twice, or "".

    `times` is how many times in a row the chat has had this answer, counted before this turn. One
    lead-in saying the answer has not changed is right; the second one is about the bot, so from
    then on the person's word takes its place. "" when the line is not a shape this frame can be
    built from, which leaves the caller's own wording.
    """
    if not isinstance(reply, str) or not reply.strip() or not times or times < 2:
        return ""
    if _carries_a_lead_in(_flat(reply)) or unframed(reply):
        return ""  # another path framed it already: a lead-in is never stacked on another
    made = as_a_phrase(text)
    if not made:
        return ""
    kind, said = made
    pool = UNDERNEATH_SAID if kind == "said" else UNDERNEATH_CLAUSE
    # Which wording, by the turn it is said on, not by the count: two of these frames come one
    # after the other in a chat that keeps saying the same thing, and both cannot carry the same
    # tail ("and the step is the same") - that is the same way twice in a row, which STYLE.md
    # rules out. `RETURN` picks its wording the same way.
    turns = len(memory.get("turns") or []) if isinstance(memory, dict) else times
    return pool[turns % len(pool)].format(said=said, reply=reply.strip())


def _lead(frame):
    """A pattern for the lead-in `frame` puts in front of its answer.

    Anything in front of the answer is matched word for word, except the filled slots, which
    stand for whatever was put in them."""
    head = str(frame).split("{reply}")[0]
    return re.compile("^" + ".+?".join(re.escape(part) for part in SLOT.split(head)))


LEADS = tuple(str(frame).split("{reply}")[0] for frame in FRAMES) + ("Like I said: ",)
PATTERNS = tuple(_lead(frame) for frame in FRAMES) + (re.compile(r"^Like I said: "),)


def unframed(reply):
    """The answer under a repeat's lead-in, or None when the reply carries none."""
    mine = str(reply or "")
    for pattern in PATTERNS:
        match = pattern.match(mine)
        if match and mine[match.end():].strip():
            return mine[match.end():].strip()
    return None


def _flat(text):
    """A reply reduced to its words, so a repeat is a repeat whatever the punctuation."""
    return " ".join(topics.words(text or ""))


def _short(reply):
    """The first sentence of an answer, or the first two when the first is only a lead-in.

    Never stops inside a quotation: the words an answer hands over to say have full stops of
    their own, and half a quotation is a broken answer rather than a short one (`quotes.closed`).
    """
    parts = quoted.sentences(reply, SENTENCE)
    if not parts:
        return str(reply or "")
    if len(parts[0].split()) >= SHORT or len(parts) == 1:
        kept = parts[:1]
    else:
        kept = parts[:2]
    return quoted.closed(" ".join(part.strip() for part in kept), parts[len(kept):], reply)


def _the_first_sentence(reply):
    """The sentence that carries the answer, so a return gives the move rather than the lot."""
    parts = quoted.sentences(reply, SENTENCE)
    if not parts:
        return str(reply or "")
    kept = parts[:1]
    if len(parts[0].split()) < 5 and len(parts) > 1:
        kept = parts[:2]
    return quoted.closed(" ".join(part.strip() for part in kept), parts[len(kept):], reply)


def _carries_a_lead_in(mine):
    """True when the reply opens with a repeat's lead-in ("as i said: ...", "same as before: ...")."""
    for lead in topics.REPEAT_LEADS:
        if mine.startswith(" ".join(lead)):
            return True
    return False


def _times_on_the_screen(mine, memory):
    """How many turns in a row already said this reply, word for word."""
    turns = memory.get("turns")
    if not isinstance(turns, list):
        return 0
    times = 0
    for turn in reversed(turns):
        if not isinstance(turn, dict):
            break
        if _flat(turn.get("bot")) != mine:
            break
        times += 1
    return times


def _said_earlier(mine, memory):
    """True when this answer was already given somewhere earlier in the conversation.

    Only a paragraph is counted, because a paragraph is what reads as a machine when it comes
    back word for word: a short fact ("On Tuesday.", "You're Sam.") said again on a later turn
    is the answer, not a repeat - people ask about the same fact twice and want the fact. The
    turn just before is left to `_times_on_the_screen` above, which numbers its lead-ins; this is
    for the answer the chat has moved on from and come back to.
    """
    return _said_earlier_text(mine, memory) != ""


def _said_earlier_text(mine, memory):
    """The bot turn that already says this answer, or "" when the conversation has not had it."""
    if len(mine.split()) <= SHORT:
        return ""
    turns = memory.get("turns")
    if not isinstance(turns, list) or not turns:
        return ""
    for turn in turns:
        if not isinstance(turn, dict):
            continue
        said = _flat(turn.get("bot"))
        if said == mine:
            return said
        # The same answer, cut: a later line reaches the entry again and gets its opening
        # sentence, which is the earlier answer with its second half missing. That is still the
        # paragraph coming back, so it is framed the same way.
        if said.startswith(mine + " "):
            return said
    return ""


def _names_something_the_answer_says(text, mine):
    """True when the line names a thing this answer is about.

    A word of the answer's own, in the line, and not a word every line has: "its a wheelie
    bin" shares "bin" with the answer that says what to do with one. A line about something
    else shares none of them, so the paragraph coming back on it stays the misreading it is and
    gets no lead-in claiming it still applies.

    A word that names nothing is not a thing the line is about, which is what `ASK_ONLY` is
    for: "what should i do first" shares "first" with the boiler answer ("you want the pump to
    run on for a minute first") and nothing else, and framing the answer on that word alone took
    the turn off the composer's own short of it ("Start with this: Turn the boiler off at the
    wall switch").
    """
    said = {word for word in topics.words(str(text or ""))
            if len(word) > 2 and word not in topics.STOPWORDS
            and word not in topics.ASK_ONLY}
    if not said:
        return False
    return bool(said & set(mine.split()))


def _returned_thing(memory, text):
    """The thing the person went back to on this turn, when the line names it: "the tap".

    Read only for the lead-in of a reply already given: the store marks the return itself, so
    this asks it rather than reading the line for opener words. The thing has to be said in the
    line ("back to the tap, what tools do i need") so "back to it" - which names nothing - is
    not given the lead, and a short thing only, because a lead carrying a whole clause is longer
    than the answer it frames.
    """
    record = topics.resumed(memory)
    if not isinstance(record, dict):
        return ""
    thing = " ".join(str(record.get("asked") or "").lower().split())
    if not thing or len(thing.split()) > 4:
        return ""
    if thing not in _flat(text):
        return ""
    return thing


def _the_line_asks(memory, text):
    """Whether the line asks something, read the way the store read the return.

    "back to lisbon" names a place and asks nothing: the person has said where they want to be and
    not yet what they want, and the answer to that is a question back, not the paragraph from the
    top of the chat. The store reads the return itself and says whether the line asks, so this asks
    it rather than reading the words for question marks - the line the answer sees may have been
    rewritten with a lead of its own ("what about back to lisbon"), and that is the rewrite's ask.
    """
    record = topics.resumed(memory)
    if isinstance(record, dict) and record.get("asks") is not None:
        return bool(record.get("asks"))
    said = memory.get("understood") if isinstance(memory, dict) else None
    if isinstance(said, dict):
        return said.get("kind") == "question" or bool(said.get("asks"))
    return bool(AN_ASK.search(_flat(text)))


def _adds_nothing_the_answer_did_not_say(thing, text, said, memory):
    """Whether the return asks again for the answer, rather than asking something it covers.

    The answer to a return may already have a part that answers what the line adds. "back to the
    guitar, should i get lessons or an app" comes back to a paragraph that ends "an app is fine for
    a month; six lessons after that fix your hands" - the words the line adds are in the answer, so
    the part of it that answers them is the reply, and a lead saying the whole paragraph again is
    the wrong answer under a claim that it is the same one. The words that decide this are the
    ones the line adds over the return itself: the thing it named and the grammar of the line come
    out, and every word left that the answer does not say is what makes this a new ask.
    """
    if not _the_line_asks(memory, text):
        return False
    said_as_typed = memory.get("understood") if isinstance(memory, dict) else None
    typed = said_as_typed.get("text") if isinstance(said_as_typed, dict) else None
    asked = _flat(typed if isinstance(typed, str) and typed.strip() else text)
    thing = set(str(thing or "").lower().split())
    added = {word for word in asked.split()
             if word.isalpha() and len(word) > 2 and word not in FRAME_WORDS
             and word not in thing and word not in lexicon.CORE_WORDS}
    return not (added & set(_flat(said).split()))


# A line that names the thing it goes back to and asks nothing after it ("back to lisbon") is not a
# return to an answer: the person has said where they want to be and not yet what they want. The
# bot asks rather than handing over the paragraph it gave before.
AN_ASK = re.compile(
    r"\b(?:what|whats|which|why|how|when|where|who|whose|should|shall|could|would|can|do|does|"
    r"did|is|are|was|were|any|anything)\b|\?")

# The words of a line that are not the return itself, so what is left is what the line adds: the
# thing it named, the words of the frame, and the grammar every line is made of come out.
FRAME_WORDS = frozenset("""back again then about as said return returning goes going go to a an the
    of in on at for and or but so also just still now it its this that these those i me my we our
    you your they them their he she him her please thanks thank""".split())


def _places():
    """The place names the vocabulary knows, so a lead can write one the way a name is written."""
    try:
        from ..understanding.topics import PLACES
    except ImportError:  # pragma: no cover - the module is always there in the bot
        return frozenset()
    return PLACES


def _as_a_name(thing):
    """The thing with a place in it written as a name: "lisbon" -> "Lisbon", "new york" -> "New York".

    The line the lead is built from has been flattened to lowercase, so "Back to lisbon" would put
    the place in lower case next to an answer that writes "Alfama" and "Belem". Only words in the
    vocabulary of places are touched, so "my knee" and "the tap" stay as they are, and the words
    an ordinary thing is made of are left alone.
    """
    places = _places()
    return " ".join(word[:1].upper() + word[1:] if word in places else word
                    for word in str(thing or "").split())


def _without_the_thing_in_front(short, thing):
    """The short of the answer with a phrase naming the thing taken off the front.

    "In Rome: the Colosseum with a timed ticket, ..." under a lead that already says "Back to
    rome" says the place twice before the answer starts. The phrase comes off, and only when it
    names the same thing the lead does, so "For a deposit, aim for 10%" keeps its own words.
    """
    said = str(short or "").strip()
    for pattern in (r"^(?:in|at|on|for|about|with|around)\s+%s\s*[:,]?\s+",
                    r"^%s\s*[:,]\s+"):
        found = re.match(pattern % re.escape(str(thing or "").lower()), said, re.I)
        if found and said[found.end():]:
            rest = said[found.end():]
            return rest[0].upper() + rest[1:]
    return said


def _said_recently(mine, memory, look=3):
    """1 when this reply is among the last few bot turns word for word, turns between or not.

    Only a run of the same reply was counted, so one answer in between made this one new again:
    "i have an exam next week" / "how do i use a slow cooker" / "i havent revised" set the whole
    study plan out again word for word, a turn after the person read it, with no lead-in at all.
    The answer is still on their screen; what came between was an answer to something else.
    """
    turns = memory.get("turns")
    if not isinstance(turns, list):
        return 0
    said = [one for one in (_flat(turn.get("bot")) for turn in turns if isinstance(turn, dict))
            if one]
    return 1 if mine in said[-look:] else 0


# A detail ask is a narrower question about the same answer: "how do i cook rice" and then, with a
# turn about something else between, "how long do i cook rice for". The frame keeps the opening of
# the answer, and the opening is not where the number is: "Same answer, and it covers this: Rinse
# it until the water runs clear, then one mug of rice to one and a half mugs of water." answers
# "how long" with everything but the time. A shortened answer to a detail ask is a wrong answer, so
# the whole of the answer goes under the lead.
A_DETAIL = re.compile(r"\bhow\s+(?:long|much|many|often|far|hot|old|quickly)\b", re.I)


def _asks_for_a_detail(text):
    """True when the line asks for a time, an amount or a count."""
    return bool(A_DETAIL.search(str(text or "")))


# A line that says something new about the person is not the answer coming round again. "i quit my
# job and its great" then "im doing the same work from home now" reached the quitting card a second
# time on the word "same", and the frame put "Same answer, and it covers this: That is a real
# decision, and most people feel two ways at once about it" in front of it - a paragraph about
# quitting, handed to somebody who is telling the bot how their week is going, which also took the
# turn off the line that was about working from home. A repeat ask names nothing of its own ("what
# should we see", "so which one then"); a report has a subject and something said about it.
#
# The line reaches this as the rewritten ask, not as it was typed ("quit im doing the same work
# from home now"), so the person can sit behind the theme the rewrite put in front: the clause is
# found anywhere in the line, and any line that asks something is not a report.
A_REPORT = re.compile(r"\b(?:i|im|i'm|i've|ive|we|we're|we've|my|our|he|he's|hes|she|she's|"
                      r"shes|they|they're|they've)\s+\w", re.I)
AN_ASK = re.compile(r"\b(?:what|which|how|why|when|where|who|can|could|should|would|shall|is|"
                    r"are|do|does|did|any|anything|anyone|remind|tell|told|worth)\b|\?", re.I)


def _a_report(text):
    """True when the line tells the bot something about the person rather than asking for a part."""
    line = str(text or "")
    return bool(line) and bool(A_REPORT.search(line)) and not AN_ASK.search(line)


# A sentence in the answer that the person could say out loud, in quotes: "Say it as a
# preference...: 'I love that you think of me - could we do a coffee instead?'" The wording asks
# above have to know whether the card in hand already holds the words, because when it does, the
# frame handing it back is the answer to the line.
A_SCRIPT = re.compile(r"(?:\"[^\"]{8,}\"|\u201c[^\u201d]{8,}\u201d"
                      r"|(?<![\w])'[^']{8,}'(?![\w]))")


def _has_a_script(reply):
    """Whether the answer holds a sentence in quotes, which is the thing a wording ask wants."""
    return bool(A_SCRIPT.search(str(reply or "")))


def _the_line_that_got_it(mine, memory, look=3):
    """The line the answer `mine` was given to, among the last few turns, or ""."""
    turns = memory.get("turns")
    if not isinstance(turns, list):
        return ""
    for turn in reversed(turns[-look:]):
        if isinstance(turn, dict) and _flat(turn.get("bot")) == mine:
            return " ".join(str(turn.get("user") or "").split())
    return ""


def _said_and_more(mine, memory):
    """True when the bot's last line was this reply and then a question of its own.

    A reply the bot went on from is still on the screen: "You have an exam on friday. How are
    you feeling about it?" is the fact plus a question the bot put there itself, and the fact
    said back on its own is the same answer, not a new one. Only the whole reply counts here -
    the short form is left to the exact match above, so a longer line is not mistaken for the
    short of itself already given.

    A line that starts with the answer is not the answer: "You don't eat meat, good to know -
    I'll plan around it." opens with the sentence the store would say and then talks about the
    greeting, so the question is what separates the two. The bot's own follow-up question means
    it went on from the answer; anything else means it only said the answer was news. The line
    ends in that question, so it is the end of the line that says which of the two it was.
    """
    turns = memory.get("turns")
    if not mine or not isinstance(turns, list) or not turns:
        return False
    last = turns[-1] if isinstance(turns[-1], dict) else {}
    raw = str(last.get("bot") or "").strip()
    said = _flat(raw)
    if not said or not said.startswith(mine + " ") or not raw.endswith("?"):
        return False
    return True
# A reply that only says one of their own facts back to them: "You've got a cat.", "You live in
# Leeds.", "Your name is Sam.", "You're allergic to nuts.", "You told me you're coeliac.",
# "I have you as Sam.". This is the sentence a recall of their fact gets, and it is short by
# nature: a second ask about the same fact ("what pets do i have", then "how many cats do i
# have") reaching the same words is not a paragraph printed twice. "Same answer, and it covers
# this: You've got a cat." is longer than the fact and says the bot is repeating itself, when
# what the person hears is the answer. So the floor stands aside for it, and the fact comes back
# as the fact - a friend asked twice about their cats says the cats again.
FACT_RECALL = re.compile(
    r"^(?:you(?:'ve| have) (?:got|had)|you (?:live|'re|are)|your \w[\w' -]{0,20}? (?:is|was)|"
    r"i have you as|you told me (?:you|your|it))\b", re.I)


def already_had(reply, memory):
    """The reply behind a lead-in that says the chat has had this answer, or None.

    `instead` frames an answer for a line that *returns* to the thing it is about, and it needs
    the thing the person came back to, because that lead reads "Back to the tap: ...". A line that
    asks the same thing again without naming a return is not that: `is that dangerous` about a
    boiler the chat answered two turns before is the question again, and the paragraph that
    answers it is already on the screen. Standing down there hands the turn to a vaguer line
    (`Worth doing rather than worrying about`), so the answer goes back whole behind the plain
    lead for a repeat - and only a paragraph, because a short fact said again is the answer.
    """
    mine = _flat(reply)
    if not mine or not isinstance(memory, dict):
        return None
    if _carries_a_lead_in(mine) or len(mine.split()) <= SHORT:
        return None
    if not _said_earlier(mine, memory):
        return None
    return AGAIN[0].format(reply=str(reply or "").strip())


def _content_words_in_order(text):
    """The content words of a line, in the order they were said."""
    seen = []
    for word in topics.words(str(text or "")):
        word = word.rstrip("s") or word
        if len(word) > 2 and word not in topics.STOPWORDS and word not in topics.ASK_ONLY:
            if word not in seen:
                seen.append(word)
    return seen


def _the_same_question_asked_again(mine, text, memory):
    """The thing the line asks about again, when an earlier turn asked the same question.

    Only a near-verbatim second ask counts ("is heat or ice better" / "so is heat or ice better
    then"): a line that adds a detail the old answer never mentioned is a new question, and its
    old answer coming back is a misreading rather than a return.
    """
    asked = set(_content_words_in_order(text))
    if len(asked) < 2:
        return ""
    turns = memory.get("turns") if isinstance(memory, dict) else None
    if not isinstance(turns, list):
        return ""
    for turn in turns:
        if not isinstance(turn, dict):
            continue
        said = _flat(turn.get("bot"))
        if said != mine and not said.startswith(mine + " "):
            continue
        earlier = set(_content_words_in_order(turn.get("user")))
        if len(earlier) < 2:
            continue
        if len(asked & earlier) * 4 < len(asked | earlier) * 3:
            continue  # less than three quarters shared: a different question on the same subject
        return " ".join([word for word in _content_words_in_order(text)
                         if word in earlier])
    return ""


def _the_subject_on_the_screen(memory):
    """The subject the conversation is on, in the person's words ("my back"), or "".

    A return on the turn before ("right, back to my back") puts the topic back, but the line
    after it ("so is heat or ice better then") is a follow-up and can make its own record
    current again. The return is what the person is on, so it is read first.
    """
    if not isinstance(memory, dict):
        return ""
    returned = memory.get("returned")
    if isinstance(returned, dict):
        turn = returned.get("turn")
        if isinstance(turn, int) and turn >= len(memory.get("turns") or []) - 2:
            subject = " ".join(str(returned.get("asked") or "").split())
            if subject:
                return _as_your(subject)
    record = memory.get("topic")
    subject = str(record.get("subject") or "").strip() if isinstance(record, dict) else ""
    return _as_your(subject)


def _as_your(subject):
    """The person's own words for a thing, said back to them: "my back" is "your back"."""
    if subject.lower().startswith("my "):
        return "your " + subject[3:]
    return subject


def instead(reply, text, memory):
    """The reply framed as the repeat it is, or None when it is new to this conversation.

    Read by the module that would otherwise serve the paragraph a second time, as the last thing
    it does: everything above has already said whether this turn is a repeat in the bot's own
    terms, and this is the floor under it - whatever route the answer came by, it is not printed
    twice in the same words.
    """
    mine = _flat(reply)
    if not mine or not isinstance(memory, dict):
        return None
    if _carries_a_lead_in(mine):
        return None  # another path already framed it: a lead-in is never stacked on another
    if FACT_RECALL.match(str(reply or "").strip()) and len(mine.split()) <= SHORT:
        return None  # a fact said back is the answer, not a paragraph on the screen twice
    times = _times_on_the_screen(mine, memory)
    if not times:
        times = _said_recently(mine, memory)
    if not times and _said_and_more(mine, memory):
        times = 1
    if not times and _said_earlier(mine, memory):
        # The chat has had this answer before and the line goes back to the thing it answers: the
        # return is the reason it is here again. They know they asked before, so "same as before"
        # reads like a glitch; the lead names the thing they came back to and the short of the
        # answer follows. Only a return gets this: an answer that comes back on a line about
        # something else is a misreading, and a lead saying "it is still the thing to do" would
        # put a wrong claim on the screen instead of the wrong answer alone.
        thing = _returned_thing(memory, text)
        if not thing:
            # The same question asked again later in the chat, after the person went off to
            # something else: "is heat or ice better" and, five turns on, "so is heat or ice
            # better then". The answer is still the answer, but it is the paragraph from before
            # word for word, so it is framed as the return it is and cut to its first sentence.
            asked = _the_same_question_asked_again(mine, text, memory)
            if asked:
                detail = _the_subject_on_the_screen(memory) or asked
                frame = RETURN[len(memory.get("turns") or []) % len(RETURN)]
                return frame.format(detail=_as_a_name(detail), reply=_the_first_sentence(reply))
            return None
        said = _said_earlier_text(mine, memory)
        if said and not _adds_nothing_the_answer_did_not_say(thing, text, said, memory):
            return None  # a part of this answer answers what the line adds: not the same ask
        thing = _as_a_name(thing)
        frame = RETURN[len(memory.get("turns") or []) % len(RETURN)]
        # The whole of the answer, not the short of it: they asked for it again, so the part that
        # says what to do comes with it ("book the tower ahead", "two meat-free dinners"). Cut
        # to one sentence under a lead, the return loses the half the person came back for.
        body = _without_the_thing_in_front(str(reply or "").strip(), thing)
        return frame.format(detail=thing, reply=body)
    if not times:
        return None
    return _framed_as_a_repeat(reply, mine, memory, times, text)


def a_thing_of_the_answer(reply, text, memory):
    """The reply framed as the repeat it is, when the line names a thing the reply is about.

    Read by the module that has already found the card for the thing the line names
    (`bot/memory/detail.py`): "my wheelie bin smells even after i wash it" / "the food one is the
    worst" / "its a wheelie bin" found the bin's own card, which is the paragraph already on the
    screen, and that route hands the card back without asking `instead` - the thing named has no
    lead of its own, so the paragraph went out word for word a second time.

    The paragraph is still the right one, so it is framed rather than replaced: the answer is the
    same and the line is about it. What keeps this honest is `_names_something_the_answer_says` -
    a line about something else shares none of the answer's words, and the paragraph coming back
    on it stays the misreading it is, with no lead claiming it still applies. An answer that
    holds the step for the fault coming back is left to `bot/memory/returned.py`, which owns
    "its dropped again".
    """
    mine = _flat(reply)
    if not mine or not isinstance(memory, dict):
        return None
    if _carries_a_lead_in(mine):
        return None  # another path already framed it: a lead-in is never stacked on another
    if not _said_earlier(mine, memory):
        return None  # new to the chat: there is no repeat to frame
    if not _names_something_the_answer_says(text, mine):
        return None
    from . import returned  # lazy: the return's readers are not needed before this
    if returned.the_next_step(str(reply or "")):
        # An answer that holds the step for the fault coming back is one the return rules answer:
        # "my boiler keeps losing pressure" / "i topped it up yesterday" / "its dropped again" is
        # owed the answer's own sentence ("there's a leak somewhere: stop topping it up and get a
        # heating engineer out"), and a framed repeat took the turn off it - the arbiter passes a
        # bare repeat over for something new, and a repeat with a lead-in in front no longer
        # reads as one.
        return None
    return _framed_as_a_repeat(reply, mine, memory, 1, text)


def _framed_as_a_repeat(reply, mine, memory, times, text=""):
    """The reply under a lead-in saying it is the same answer, cut to the short of it.

    `times` is how many times the chat has had it, which picks the lead-in. A few words is
    already the short of itself, so it gets the short of the lead-ins instead.

    `text` is the line that asked, which both callers have and this reader needs: it decides
    whether the line asks for a part of the answer (see below). It was read here without being
    passed in, so every framed repeat of a paragraph raised NameError, the runtime swallowed it
    as it is meant to, and the whole knowledge base went silent behind a greeting: "how do i cook
    rice" / "sorry how do i cook rice" was told "I'm not sure about that one, sorry".
    """
    if len(mine.split()) <= SHORT:
        # A few words is already the short of itself, so the paragraph frame is wrong: "how old is
        # she again" wants the fact, not a sentence about the fact being repeated. The answer still
        # has to say it is the same one, though, and for a second reason: the arbiter passes over a
        # candidate that is the last answer word for word, so "On Tuesday." twice handed the turn
        # to whichever module had something new (the cold card, for a tooth out on Tuesday). Two
        # words of lead-in keep the answer and say it has not changed.
        return SHORT_AGAIN[min(times, len(SHORT_AGAIN)) - 1].format(reply=reply.strip())
    if _a_report(text):
        return None  # new information about the person: the paragraph came back on a shared word
    from ..compose import fallback  # lazy: the wording asks live with the lines that answer them
    if ((fallback.WORDING_ASKS.search(text) or fallback.WORDING_SOMEONE.search(text)
         or fallback.WORDING_SAYS.search(text)) and not _has_a_script(reply)):
        # "what do i say" after the council-bin card asks how to word the call, not for the card
        # again: the answer is the shape to say it in, and the frame handed back the first half of
        # the card with "Same answer, and it covers this" in front of it.
        #
        # An answer that already has the words in it is the one exception, and it is not a small
        # one: "my mum keeps buying me clothes i hate" is answered with the sentence to say to her
        # ("'I love that you think of me - could we do a coffee and a walk instead of a top?'"),
        # and handing that back as the answer that covers this is what the person asked for. Only
        # a card with no words in it is worth standing aside for.
        return None
    from . import repeat  # lazy: `repeat` reads the composition side, which reads this module
    if repeat.asks_for_the_move(text):
        # The line asks which part of the answer in hand to do ("what should i do first", "where
        # do i start", "how do i clean it off"), so the reply is that step, not the paragraph
        # again with a lead in front of it: "Same answer, and it covers this: Radiators that are
        # hot at the bottom and cold at the top have air in them: open the bleed valve..." is
        # every sentence they had already read to answer a question about the first one. The
        # reader that hands the step back is the module this one would stand aside for.
        return None
    underneath = the_same_thing_underneath(text, _short(reply), times, memory)
    if underneath:
        return underneath
    short = _short(reply)
    if _flat(short) != mine and _times_on_the_screen(_flat(short), memory):
        short = reply  # the short form was served last turn too: say the whole of it, framed
    if _asks_for_a_detail(text) and not _asks_for_a_detail(_the_line_that_got_it(mine, memory)):
        # This line asks for a part of the answer the earlier line did not ("how long do i cook
        # rice for" after "how do i cook rice"), so the part it asks for is further down than the
        # opening, and the frame must not throw it away.
        short = reply
    return AGAIN[min(times, len(AGAIN)) - 1].format(reply=short)
