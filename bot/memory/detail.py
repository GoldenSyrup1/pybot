"""A line that adds a detail to the thing the last answer was about.

"how do i stop condensation on my windows" gets the paragraph, and the next line is "its on the
bedroom ones mainly". That line is not an ask and not small talk: it says which of the things the
advice was about is the one they mean. The store already keeps it - the word "bedroom" goes into
`memory["topic"]` and `memory["entry_answer"]` holds the paragraph - but nothing answered it, so
the composer echoed the person's own words back ("Got it - it's on the bedroom ones mainly"),
which adds nothing and reads like a form being filled in. A search hedge is the other answer it
got ("what about the bathroom" after advice about the bathroom's own window).

So this finds that turn and answers it with the one thing to do out of the answer just given,
with the detail named in front: "On the bedroom ones mainly - use the extractor fan, and open a
window for ten minutes a day." That is the step they were already given, so it is honest without
any new knowledge, and it is about the thing they just narrowed to.

The rule is narrow on purpose:
* the line has to open on a back-reference - a copula or a preposition in front of the thing
  ("its on the ...", "they are in the ...", "with two kids", "what about the bathroom") - so a
  new subject ("its my birthday") is not a detail of anything;
* it has to have no verb of its own: "we already open a window" and "they ate my lettuce" are
  reports about the thing, and a report is the composer's to answer;
* the reply just given has to be a knowledge answer with a step in it, so there is something to
  hand back;
* a detail the same shape has already been handed back in the last few turns is not repeated.
"""
import re

from ..understanding import kinds
from . import again, condition, repeat

# The copula, a pronoun and the prepositions a detail can open on. The pronoun and the copula are
# scaffolding ("its", "it's", "theyre") and are not part of the detail itself.
COPULA_OPEN = re.compile(
    r"^\W*(?:(?:and|but|so|oh|also|well|yeah|yep|ok|okay|right|alright)\W+)*"
    r"(?:it'?s|it\s+is|its|they'?re|they\s+are|there'?s|there\s+is|there\s+are|"
    r"that'?s|this\s+is)\b\s*",
    re.I)
# "what about the bathroom" / "how about the kitchen" is the same detail asked rather than said:
# the thing named is the detail and the answer is the same one.
ABOUT_OPEN = re.compile(
    r"^\W*(?:(?:and|but|so|oh|also|well|yeah|yep|ok|okay|right|alright)\W+)*"
    r"(?:what|how)\s+about\b\s*", re.I)
# A pronoun in front of a preposition is the same back-reference: "im in manchester" after a
# question about the weekend, "we're near the coast" after one about a walk.
PRONOUN_OPEN = re.compile(
    r"^\W*(?:(?:and|but|so|oh|also|well|yeah|yep|ok|okay|right|alright)\W+)*"
    r"(?:i\s*m|im|i\s+am|we\s*re|were|we\s+are)\b\s*", re.I)
# A detail said without the copula at all: "with two kids", "for commuting", "on the top floor".
# "like" is how people introduce the example of the thing the answer was about - "like damp",
# "like keys and names", "like a Sunday" - and nothing read it, so the line was echoed back
# ("Got it - like keys and names.") while the answer's own step was about exactly that.
PREPOSITION_OPEN = re.compile(
    r"^\W*(?:(?:and|but|so|oh|also|well|yeah|yep|ok|okay|right|alright)\W+)*"
    r"(?:with|for|on|in|at|by|near|from|like)\b\s*", re.I)
# "like" introduces the example of the thing the answer was about - "like keys and names", "like
# damp", "like a banging when it spins" - and nothing read it, so those lines were echoed back
# ("Got it - like keys and names.") while the answer above already held the step about them. The
# thing named comes straight after it, so this body needs no preposition of its own, and the word
# "like" is cut off the phrase wherever it is read.
LIKE_OPEN = re.compile(
    r"^\W*(?:(?:and|but|so|oh|also|well|yeah|yep|ok|okay|right|alright)\W+)*like\b\s*", re.I)
# A body that is only a time or a frequency is not the thing the answer was about. "i keep getting
# mouth ulcers" / "like every couple of months" came back "Same for every couple of months: Use a
# soft brush", and a duration reads the same way: the person is telling you how often or how long,
# so the line stays the report it already is.
TIME_WORDS = frozenset("""every each once twice thrice all most couple few several
    time times day days daily night nights nightly morning mornings afternoon afternoon
    evening evenings week weeks weekly month months monthly year years yearly hour hours
    minute minutes second seconds yesterday today tomorrow tonight lunch lunchtime teatime
    bedtime weekend weekends sometimes often always usually rarely never again ago since
    hourly sort of kind""".split())
# A person named after "like" is a different subject, not a narrowing of the answer's thing: "i
# keep getting mouth ulcers" / "like my sister" came back "Same for my sister: Use a soft brush".
A_PERSON_BODY = re.compile(
    r"^(?:my|our|his|her|their|your|the)\s+(?:mum|mom|dad|mother|father|sister|brother|son|"
    r"daughter|wife|husband|partner|boyfriend|girlfriend|friend|mate|colleague|boss|neighbour|"
    r"neighbor|nan|gran|grandma|grandad|grandpa|aunt|uncle|cousin|kid|kids|child|children|"
    r"baby|boy|girl|dog|cat|puppy|kitten|parents|family)\b", re.I)
# A detail is a phrase, not two clauses: "like every couple of months and they hurt" is a report
# whose verb the report test does not know, and "keys and names" is a list of one thing.
AND_A_CLAUSE = re.compile(r"\band\s+(?:i|we|he|she|they|it|you|there)\s+\w", re.I)
# What the detail hangs on after the back-reference: a preposition or an article. "its my
# birthday" and "im 34" are new subjects, not a narrowing of the one on the table.
DETAIL_BODY = re.compile(
    r"^(?:on|in|at|near|by|from|for|with|about|the|a|an|this|that|these|those|both|just)\b",
    re.I)
# A count is a narrowing too: "there's 4 of us and a baby", "we only have 3 days". The unit is
# what makes it a count of the thing rather than a bare number, which is an age or a time on its
# own ("im 34", "its 3").
COUNT = (r"(?:\d+|one|two|three|four|five|six|seven|eight|nine|ten|a\s+few|couple\s+of|"
         r"several)")
QUANTITY_BODY = re.compile(
    r"^(?:" + COUNT + r")\s+(?:of\s+(?:us|them|you)|days?|weeks?|months?|nights?|hours?|"
    r"minutes?|people|adults|kids?|children|guests)\b", re.I)
# A measure is a narrowing too, and it is how people answer a question about size or time: "how
# long do i roast a chicken" -> "20 minutes per 500g plus 20" -> "its 2kg". The unit is what
# makes it a measure; a bare number after the copula is an age or a count ("im 34", "its 3"),
# which is a different kind of line and stays out. The space is optional because "2kg" is how it
# gets written half the time.
MEASURE_BODY = re.compile(
    r"^(?:" + COUNT + r")\s*"
    r"(?:kg|kgs|kilo|kilos|kilogram|kilograms|g|gram|grams|lb|lbs|pound|pounds|oz|ounce|ounces|"
    r"stone|stones|litre|litres|liter|liters|ml|cl|cm|mm|metre|metres|meter|meters|inch|inches|"
    r"feet|foot|ft|miles?|km|degrees?|hours?|hrs?|minutes?|mins?|seconds?|days?|weeks?|months?)\b",
    re.I)
# The count said as the person has it: "we only have 3 days", "weve got 4 of us". This is the
# constraint on the plan the answer just gave, not a new subject, so it takes the same step.
HAVE_COUNT = re.compile(
    r"^\W*(?:(?:and|but|so|oh|also|well|yeah|yep|ok|okay|right|alright)\W+)*"
    r"(?:we|i|weve|ive)\s+(?:(?:only|just)\s+)*(?:have|got|ve\s+got)\s+(?P<count>.+)$",
    re.I)
# The words that say nothing on their own, so a detail made only of them is no narrowing at all.
VAGUE = frozenset("""it its that this these those one ones thing things stuff
    the a an and but so oh also well yeah yep ok okay right alright
    really very quite just mainly mostly only also too as well now today later soon again""".split())
# A detail says which part of the thing, never how the thing is going. "its a bit better today"
# after the sore-knee answer is a report on the knee, and reading it as a detail framed the answer
# as "Same answer for a bit better today: Keep going as far as is comfortable" - talking about the
# day rather than the knee. These words plus the vague ones make a phrase that says only how it is.
STATE = frozenset("""better worse ok okay fine sore stiff swollen tender aching painful easier
    harder bigger smaller good bad rubbish awful great healing improving recovered the same
    bit lot little much slightly more less worse off""".split())
MOST_WORDS = 9
# A step is one instruction, not the paragraph it came out of: trimmed at a clause boundary to
# about this many words, so the detail of the answer is not answered with the whole answer.
STEP_WORDS = 14
# A clause shorter than this is not a step on its own ("use the extractor fan"), so a following
# clause joins it; a longer one stands alone.
SHORT_STEP = 8
# A clause cut out of the middle of a sentence opens on the word that joined it - "..., so a 2kg
# bird takes roughly 1 hour 40 minutes" - and handed back after a colon with a capital on it, "So
# a 2kg bird" reads wrong. The joining word goes with the comma it came from.
JOIN_LEAD = re.compile(r"^(?:so|and|but|then|also|or|plus|because)\b[\s,]+", re.I)
# The answer comes first (STYLE.md, "Answer in the first sentence"): the step, with the thing they
# narrowed to named in the lead, never the other way round - a reply that opens on their own words
# said back is the echo this replaces.
LEADS_LEAD = (
    "{detail_cap} - same answer: {step}",
    "{detail_cap}, then. {step}",
    "{detail_cap}: {step}",
)
LEADS_FOR = (
    "Same answer for {thing}: {step}",
    "Same for {thing}: {step}",
    "For {thing}, the same: {step}",
)
# A detail said with its own preposition ("on the bedroom ones", "with two kids") reads best in
# front of the step; one without ("the bathroom", "a fan oven") reads best after "for".
# "along", "across", "round" and "under" are the same kind of place as "on" and "in", and
# they are how a thing is said to catch or rub: without them the reply lead read "For along
# the bottom, the same:" instead of "The bottom - same answer:".
PREPOSITION = re.compile(r"^(?:on|in|at|near|by|from|for|with|about|along|across|round|"
                         r"around|under|down)\b\s*", re.I)

# The verb of showing is how the trouble is put, not a report about it: "its coming from the front
# corner" after a leak answer names the same thing as "its from the front corner", and the place
# it names is the detail. Read as a report the line went to the composer and got a nod, and the
# sentence of the answer about the front - the one thing that answers it - never came back. The
# place vocabulary is what keeps it to a place: "its coming from manchester" is a person's travel
# and not a detail of anything.
A_PLACE = (r"(?:front|back|rear|bottom|top|inside|outside|underneath|under|side|corner|edge|"
           r"middle|floor|door|seal|hose|filter|drum|pump|tank|pipe|valve|tap|wheel|tyre|tire|"
           r"chimney|gutter|roof|celling|wall|window|sill|radiator|boiler|toilet|basin|shower|"
           r"socket|switch|handle|lid|drawer|join|connection)")
SHOWS_OUT = re.compile(
    r"\b(?:com(?:e|es|ing)|comin|leak(?:s|ing|ed)?|drip(?:s|ping|ped)?|seep(?:s|ing|ed)?|"
    r"run(?:s|ning)?|pour(?:s|ing|ed)?|spray(?:s|ing|ed)?|blow(?:s|ing)?)\s+out(?:\s+of)?\s+"
    r"(?=(?:the\s+)?" + A_PLACE + r"\b)", re.I)
SHOWS_FROM = re.compile(
    r"\b(?:com(?:e|es|ing)|comin|leak(?:s|ing|ed)?|drip(?:s|ping|ped)?|seep(?:s|ing|ed)?|"
    r"run(?:s|ning)?|pour(?:s|ing|ed)?|spray(?:s|ing|ed)?|blow(?:s|ing)?)\s+"
    r"(?=from\s+(?:the\s+)?" + A_PLACE + r"\b)", re.I)


# How the thing is going wrong, and then where: "it catches at the top", "it rubs along the
# bottom", "they skip across the glass". The verb is what the thing does, and the place after it
# is the part of it the answer is about - so the line is a narrowing of the answer even though it
# carries a verb, and the part it names is the place. A report about the thing as a whole names no
# place ("we already open a window", "they ate my lettuce") and is still the composer's.
FALTER = re.compile(
    r"^\W*(?:(?:and|but|so|oh|also|well|yeah|yep|ok|okay|right|alright)\W+)*"
    r"(?:it|its|it'?s|they|they'?re|he|she|that|this|the\s+\w+|my\s+\w+|our\s+\w+)\s+"
    r"[a-z']+\s+(?=(?P<place>(?:at|on|in|along|across|round|around|near|by|under|down)\s+"
    r"(?:(?:the|my|its|their|your)\s+)?" + A_PLACE + r"\b))", re.I)

# After one of these a verb form is the adjective of the thing ("a rented flat", "the raised
# beds"), which is a narrowing of the answer rather than a report about it.
DETERMINER = frozenset("""a an the my our your their his her its some this that these those
    two three few both""".split())


def _a_verb(word, before=""):
    """True for a word that makes the line a report rather than a detail.

    The verb forms the reading already keeps are reused, so "ate", "open" and "tried" are caught
    the same way they are in a question. A verb form behind a determiner is the thing's adjective
    and not a verb, which is how "a rented flat" stays a detail and "they ate my lettuce" does
    not.
    """
    if before in DETERMINER:
        return False
    return word in kinds.VERBISH or word in kinds.VERB_FORMS


def _flat(text):
    return " ".join(str(text or "").split())


def _the_same_answer_as_the_one_it_narrows(step, said):
    """True when the whole reply found for the detail is the answer it narrows, word for word.

    The first 60 characters are enough: an entry is one paragraph, and two entries that open with
    the same sixty characters are the same paragraph to the person reading it.
    """
    here, there = _flat(step).lower()[:60], _flat(said).lower()[:60]
    return bool(here) and here == there


def _words(text):
    return re.findall(r"[a-z']+", _flat(text).lower())


# A line that is only a span: "its been about three weeks now", "its been a month". The copula
# hangs on nothing, so what it hangs on is the answer just given, and the span narrows it.
SPAN_ONLY = re.compile(
    r"^\W*(?:(?:and|but|so|oh|also|well|yeah|yep|ok|okay|right|alright)\W+)*"
    r"(?:it'?s|it\s+is|its|it\s+has|thats|that'?s|that\s+is|ive|i\s+have)\s+"
    r"(?:been\s+)?(?P<span>(?:(?:about|around|nearly|almost|over|just\s+over)\s+)?"
    r"(?:\d+|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|"
    r"a\s+few|couple\s+of|a|several)\s+"
    r"(?:day|week|month|year|fortnight|hour|minute)s?"
    r"(?:\s+(?:now|or\s+so|or\s+more|already))?)\s*$", re.I)


def the_detail(text):
    """The detail as a phrase to put in front of the step ("on the bedroom ones mainly"), or None.

    None means the line is not a detail of the thing the answer was about: a question with a
    thing of its own, a new subject, or a report with a verb in it.
    """
    said = _flat(text)
    if not said or "?" in said:
        return None
    # How the trouble shows is part of the asking: with the verb of showing taken away, "its
    # coming from the front corner" is "its from the front corner", and the place is the detail.
    said = " ".join(SHOWS_OUT.sub("from ", SHOWS_FROM.sub("", said)).split())
    words = said.split()
    if len(words) > MOST_WORDS:
        return None
    # A span said on its own: "its been about three weeks now", "its been a month". The line says
    # how long the thing has been going on and not what the thing is, so the span is a detail of
    # the answer just given, the same shape as "for about three weeks now", which is read below.
    # Without it the span reached no entry, and the next line of a chat about sleep was answered
    # with the sore-back card, from a "back" that was only the particle of "get back to sleep".
    span = SPAN_ONLY.match(said)
    if span:
        return "for " + " ".join(span.group("span").split())
    # The count said as the person has it is read before the verb test: "we only have 3 days"
    # carries "have", but it is the constraint on the answer and not a report about it.
    counted = HAVE_COUNT.match(said)
    counted_rest = None
    if counted and QUANTITY_BODY.match(counted.group("count")):
        counted_rest = counted.group("count").strip()
    # A report has a verb of its own ("we already open a window", "they ate my lettuce"), so it is
    # a statement about the thing rather than a narrowing of it, and the composer answers those.
    falter = FALTER.match(said)
    if falter:
        # The place is the part of the thing, and the verb is how it is going wrong.
        return falter.group("place").strip()
    body_words = [w for w in _words(said) if w not in ("is", "are", "was", "were", "be", "been")]
    # The opening word is not a verb, and "like" is both ("like my sister" is an imperative and
    # "like keys and names" is a detail), so the words of that opening are set aside once, before
    # the verb test rather than after it.
    like_head = LIKE_OPEN.match(said)
    if like_head:
        body_words = [w for w in _words(said[like_head.end():])
                      if w not in ("is", "are", "was", "were", "be", "been")]
    if counted_rest is None and any(
            _a_verb(w, before) for before, w in zip([""] + body_words, body_words)):
        return None
    opener = None
    rest = None
    for opener in (ABOUT_OPEN, LIKE_OPEN, COPULA_OPEN, PRONOUN_OPEN):
        stripped = opener.sub("", said).strip()
        if not stripped or stripped == said:
            continue
        # A detail introduced with "like" names the thing straight away ("keys and names"), so it
        # needs no preposition of its own where a copula does ("its on the bedroom ones").
        if opener is not PRONOUN_OPEN and opener is not LIKE_OPEN and not (
                DETAIL_BODY.match(stripped)
                or (opener is COPULA_OPEN and (QUANTITY_BODY.match(stripped)
                                               or MEASURE_BODY.match(stripped)))):
            return None
        rest = stripped
        break
    if rest is None:
        # A detail said without the copula keeps its own preposition: "with two kids", "in a
        # flat". Those read best in front of the step, so the phrase is the whole line. A count
        # said as the person has it ("we only have 3 days") is the same kind of narrowing.
        if counted_rest is not None:
            opener = HAVE_COUNT
            rest = counted_rest
        elif not PREPOSITION_OPEN.match(said):
            return None
        else:
            rest = said
            # "Like" introduces the thing rather than being part of it, and "Same for keys and
            # names: ..." reads better than "Like keys and names - same answer: ...", so it is
            # cut here and the words after it are the thing the answer is about.
            if LIKE_OPEN.match(rest):
                rest = LIKE_OPEN.sub("", rest).strip(" .,;:")
                if not rest:
                    return None
    # A pronoun with no preposition is the person's own state ("im thirsty"), not a narrowing of
    # anything; one with a preposition keeps it ("im in manchester" -> "in manchester").
    if opener is PRONOUN_OPEN and not PREPOSITION.match(rest):
        return None
    # The phrase goes in front of the step, so a full stop at the end of it would be read in the
    # middle of the reply ("Keys and names. - same answer: ..."): a phrase has no full stop.
    rest = rest.strip(" .,!;:")
    if not rest or AND_A_CLAUSE.search(rest):
        return None
    content = [w for w in _words(PREPOSITION.sub("", rest)) if w not in VAGUE]
    if not content:
        return None
    if all(word in TIME_WORDS for word in content):
        # How often or how long, not which thing: the answer's step is about the thing itself.
        return None
    if A_PERSON_BODY.match(rest):
        # A person is a different subject from the thing the answer was about.
        return None
    if all(word in STATE for word in content):
        # Only how it is, not which part it is: this is a report about the thing the answer was
        # already about, and the answer to it is not "Same answer for a bit better today".
        return None
    return rest


# A figure with a unit, said the way people say what they can already do: "i can do 5k now", "i
# can swim 400m", "i cycle 10 miles a day". The unit is what makes it a measure of a thing rather
# than a bare number, which is an age or a time on its own ("im 34").
A_FIGURE = re.compile(
    r"\b\d+(?:[.,]\d+)?\s*(?:k|km|kms|kilometres?|kilometers?|miles?|mi|metres?|meters?|m|"
    r"mins?|minutes?|hours?|hrs?|h|kg|kilos?|lb|lbs|stone|st|litres?|liters?|degrees?|"
    r"secs?|seconds?|days?|weeks?)\b", re.I)
# The line has to be about the person for their own figure to be a fact about them.
THE_PERSON = re.compile(r"\b(?:i|im|i'm|ive|i've|we|we're|we've|my|our)\b", re.I)
# A question asked without its question mark ("can i do 5k now") is still a question, and the
# answer's own sentence is not a reply to it: the person is asking, not telling.
ASKING_ME = re.compile(
    r"^\W*(?:(?:and|but|so|oh|also|well|yeah|yep|ok|okay|right|alright)\W+)*"
    r"(?:can|should|could|would|do|does|did|is|are|will|shall)\s+(?:i|we)\b", re.I)
# A sentence of an answer shorter than this is not a step on its own.
FACT_SENTENCE_WORDS = 5


def _a_figure(word):
    """The figure as it can be compared: the number and the unit without the space ("5k")."""
    return re.sub(r"\s+", "", word.lower()).rstrip(".,")


def the_fact_the_answer_has(text, memory):
    """The sentence of the answer just given that speaks of a figure the person names, or None.

    "im 34 and i want to run a 10k" then "i can do 5k now" was answered "I'm listening — say more
    if it helps", although the answer on the screen already says what to do about exactly that:
    "If you can run 5k comfortably now, eight to ten weeks is a realistic build." Nothing new is
    known here - the sentence is the answer's own - so it can be handed over honestly, and the
    whole paragraph is not given again.

    The reading is narrow on purpose: the line has to be the person's own ("i can", "we've got"),
    has to name a figure with a unit, and the answer has to have more than one sentence with that
    same figure in one of them. A bare number ("im 34") is an age or a time and nothing here.
    """
    if not memory:
        return None
    said = _flat(text)
    if not said or "?" in said or len(said.split()) > MOST_WORDS:
        return None
    if not THE_PERSON.search(said) or ASKING_ME.match(said):
        return None
    wanted = {_a_figure(found.group(0)) for found in A_FIGURE.finditer(said)}
    if not wanted:
        return None
    reply = ""
    for back, _asked, answer in repeat._recent_answers(memory):  # noqa: SLF001 - same package
        if back > 1:
            break
        if answer:
            reply = str(answer)
            break
    if not reply:
        return None
    sentences = [part.strip() for part in re.split(r"(?<=[.!?])\s+", reply) if part.strip()]
    # One sentence is the whole answer: handing it back is repeating, not answering.
    if len(sentences) < 2:
        return None
    for sentence in sentences:
        if len(sentence.split()) < FACT_SENTENCE_WORDS:
            continue
        there = {_a_figure(found.group(0)) for found in A_FIGURE.finditer(sentence)}
        if there & wanted:
            said_back = sentence if sentence.endswith((".", "!", "?")) else sentence + "."
            return said_back[:1].upper() + said_back[1:]
    return None


def the_step_for(text, memory):
    """The detail, the answer it narrows and the step to hand back, or None.

    The whole of the reading `answer_for` answers from, kept on its own so that another part of
    the bot can ask whether this line belongs to the answer just given before it answers it
    itself: a follow-up that the last answer already has a step for is that answer's, and a
    reading written twice would let the two disagree. Nothing is picked and nothing is written
    here, so asking costs the conversation nothing.

    The fourth item is true when what came back is a whole reply rather than a step: a thing
    named beside the chat's subject has an answer of its own in the knowledge base, and that
    answer beats the answer's step handed over under its name. It is already worded, so it is
    handed back as it stands.
    """
    if not memory:
        return None
    detail = the_detail(text)
    if not detail:
        return None
    # A line about the person's own body or a broken thing is not a detail of an answer, whatever
    # it opens on: "im in pain" after advice wants the composer's care, not the step it already
    # gave. The reading is the same one the composer uses, so the two cannot disagree.
    from ..compose import trouble
    if trouble.reads_as_trouble(_flat(text)):
        return None
    own = None
    own_read = False
    for back, asked, said in repeat._recent_answers(memory):  # noqa: SLF001 - same package
        # The answer one turn back is the one they are narrowing. Two turns back still counts when
        # the turn between is this module's own answer about the same thing ("what about the
        # bathroom" after the bedroom ones were handed the same step).
        if back > 2:
            continue
        # The answer one turn back needs no subject test: a detail moves the subject on purpose
        # ("in a rented flat" makes the flat the thing), and the reply it narrows is the one it
        # followed. Two turns back, the turn between them has to be about the same thing.
        if back > 1 and not repeat._about_the_same_thing(asked, said, memory):  # noqa: SLF001
            continue
        # The thing the detail names is where the answer is, when the answer speaks of it: the
        # move that comes last in the paragraph is about whatever the paragraph ends with.
        # A branch of the answer is not a step of it (see `_a_branch`): the sentences that say
        # what to do in a particular case are left out, and an answer made only of branches has
        # no step to hand back.
        plain = _without_branches(said)
        if not plain:
            # An answer made only of cases has no move of its own to hand over, but a thing the
            # line names of its own may still have a card of its own: "my back hurts" is a
            # paragraph of cases now, and "what about a dehumidifier" after it is the
            # dehumidifier's question, not a narrowing of the back's. Nothing else is handed
            # back here: the last sentence of an answer that is all cases answers the case, not
            # the person's line.
            if not own_read:
                own = _the_thing_itself(detail, memory)
                own_read = True
            if own:
                return detail, said, own, True
            if _another_thing(detail, said):
                worth = _what_it_is_worth(detail, memory)
                if worth:
                    return detail, said, worth, True
            continue
        step = _step_about(plain, detail)
        if _a_count(detail):
            # A count is a detail about size, and what a number of people changes is the figure:
            # "theres 6 of us" after the roast timings is answered with the 20 minutes per 500g,
            # not with "Check the thigh juices run clear", which is the same whatever the number.
            # The sentence carrying the figure is where the answer to a count is, so it is the
            # step; an answer with no figure in it is read as it was before.
            step = _the_figure(plain) or step
        if not step:
            if not own_read:
                own = _the_thing_itself(detail, memory)
                own_read = True
            if own:
                return detail, said, own, True
            # A thing the answer never speaks of is a question of its own, not a narrowing of
            # this answer: "my back hurts" / "what about a dehumidifier" was replied "For a
            # dehumidifier, the same: Keep walking and carry on with your usual jobs", which is
            # advice about a back under the name of a dehumidifier. Where the base keeps a card
            # for the thing itself, that card is the answer.
            if _another_thing(detail, said):
                worth = _what_it_is_worth(detail, memory)
                if worth:
                    return detail, said, worth, True
            # A thing of its own that the answer never spoke of is not a narrowing of it, so the
            # answer's last step is not its answer either: see `_asks_about_a_new_thing`.
            if _asks_about_a_new_thing(text, detail, said):
                continue
            # A span narrows the answer by how long, so the sentence of the answer about a
            # length of time is the one for them. Failing that, only an answer that opens on
            # something to do hands a step back: for an answer that explains, the opening
            # sentence said again is a better reply than a clause picked out of the middle of it
            # ("Open the letter" out of the middle of an answer about putting things off).
            # A span narrows the answer by how long, so the sentence about a length of time is
            # the one for them; failing that the answer's opening move, and failing that the
            # answer's opening sentence said briefly - never a clause picked out of the middle
            # of it, which reads as advice about nothing ("Open the letter").
            if _is_a_span(detail):
                step = (_a_span_step(plain, detail) or _first_instruction(plain)
                        or _opening_said(plain))
            else:
                step = _a_step(plain)
        if not step:
            continue
        if repeat._already_repeated(step, memory):  # noqa: SLF001 - said once already
            # A second detail in the same answer gets the first clause only: the step has been
            # said once, so the shorter form of it is the repeat and not the whole step again.
            step = _first_clause(step)
            if not step or repeat._already_repeated(step, memory):  # noqa: SLF001
                return None
        return detail, said, step, False
    return None


# A word in the detail that counts people or portions: "6 of us", "4 people", "3 days".
COUNTED_DETAIL = re.compile(
    r"^(?:" + COUNT + r")" + r"\s+(?:of\s+(?:us|them|you)|people|adults|kids?|children|"
    r"guests|portions|slices|days|weeks?|months?|nights?|hours?|minutes?)\b", re.I)
# The mark of a figure is a written number, not a number said as a word: "give each place at least
# three of them" counts the nights a plan wants, not how many days the person has, and handing it
# back as the answer to "we only have 4 days" answered the wrong thing.
FIGURED = re.compile(r"\d")


def _a_count(detail):
    """Whether the detail is a number of people or portions, not a part of the thing."""
    return bool(COUNTED_DETAIL.match(_flat(detail)))


def _the_figure(said):
    """The sentence of the answer that carries the figure, or None."""
    for sentence in re.split(r"(?<=[.!?])\s+", _flat(said)):
        sentence = sentence.strip()
        if sentence and FIGURED.search(sentence):
            return sentence
    return None


def answers_the_line(text, memory):
    """True when `answer_for` will answer this line: the answer just given has its step."""
    return the_step_for(text, memory) is not None


def answer_for(text, memory):
    """The reply for a detail added to the answer just given, or None.

    Only the answer one turn back counts: an older answer is a different thing they may have
    moved on from, which is `repeat`'s call, not this one's.
    """
    found = the_step_for(text, memory)
    if found is None:
        return None
    detail, said, step, whole = found
    if whole and _the_same_answer_as_the_one_it_narrows(step, said):
        # The thing the detail names has an entry of its own, and that entry is the one the last
        # answer came from: "the bathroom tap has been dripping for a week" / "its a mixer tap"
        # was handed the dripping-tap paragraph word for word, so the person got the same answer
        # twice and their line went unanswered. Nothing here is new, so this is not a detail of
        # the answer and the composer is left to answer it: it hands back the part of that
        # answer the person has not had ("It's a 20-minute job and saves a lot of water.").
        return None
    if whole:
        # A whole reply rather than a step of the answer: the thing the line names has a card of
        # its own, and the card can be the one the chat has already read word for word. "my
        # wheelie bin smells even after i wash it" / "the food one is the worst" / "its a
        # wheelie bin" found the bin's card again and printed the same paragraph a second time,
        # because this route hands the card back without going through the repeat's own framing
        # (`again.a_thing_of_the_answer`). The paragraph is still the right one, so it is framed
        # as the repeat it is and not replaced. What the chat remembers of the turn is the card
        # itself, though, and not the lead-in in front of it: the readers that ask whether a step
        # was already handed back look for the answer's own words (`repeat._handed_back_already`),
        # and a lead-in on top of them hides it.
        framed = again.a_thing_of_the_answer(step, text, memory)
        repeat._handed_back(memory, step)  # noqa: SLF001 - the next ask counts it
        return framed or step
    thing = PREPOSITION.sub("", detail).strip() or detail
    leads = LEADS_LEAD if thing != detail else LEADS_FOR
    reply = repeat.pick(leads, memory, text).format(
        detail_cap=_capital(detail), thing=thing, step=_capital(step))
    return repeat._handed_back(memory, reply)  # noqa: SLF001 - the next ask counts it said


# Split a move into its clauses. A comma inside brackets ("coat the inside (not the elements)")
# is not a clause boundary, so the split is done by hand rather than by a lookbehind, which
# cannot say "unless an unclosed bracket comes first".
CLAUSE = re.compile(r"[,;:]\s+|\s+-\s+")


def _clauses(move):
    """The move cut where a clause ends, ignoring a comma inside brackets."""
    out, piece, depth = [], [], 0
    for chunk in CLAUSE.split(move):
        depth += chunk.count("(") - chunk.count(")")
        if piece and depth:
            piece.append(chunk)
            continue
        if piece:
            out.append(", ".join(piece))
            piece = []
        piece = [chunk]
    if piece:
        out.append(", ".join(piece))
    return out


def _first_clause(step):
    """The shortest form of a step: its first clause, with a full stop."""
    pieces = [p.strip(" ,;:-.") for p in _clauses(step.rstrip(".")) if p.strip(" ,;:-.")]
    if not pieces:
        return ""
    return pieces[0] + "."


# The words of a naming clause that say nothing about the thing: "a sleeping bag and a mat" is
# the name of the item, and the clause after it says what to look for.
NAME_ONLY = frozenset("""a an the my our your their his her its some this that these those and
    or with without for of in on at to it them they both two three few""".split())

# A word that is the asking and not a thing: "what should we think about" names no thing of its
# own, so the word after it is not looked up beside the chat's subject.
NOT_A_THING = frozenset("""
think thinks thinking thought know knows knowing say says saying tell tells telling ask asks
asking wonder wonders wondering guess guesses guessing consider considers considering decide
              decides deciding choose chooses choosing help helps helping do does doing work works
want wants wanting need needs needing like likes liking get gets getting make makes making
""".split())


def _one_of_a_list(clauses, groups, at):
    """Whether a clause is one item of a list of things, or a thing a dash-group qualifies.

    The tent answer lists the kit ("Tent with its pegs and a mallet, a sleeping bag and a mat -
    a foam or inflatable one"), so the clause that names the sleeping bag is one item of a list
    and the qualifier after the dash is what to look for. The condensation answer names the
    bedroom in a sentence of its own ("A dehumidifier helps in a bedroom that gets it badly"),
    which says what helps, not what to do first - and a detail gets the move, not a description.
    """
    return len(clauses) > 1 or at + 1 < len(groups)


def _head_word(detail):
    """The word the detail names its thing with: "a helmet" -> "helmet", "in a rented flat" ->
    "flat" (the last word that says something, since English puts the thing last)."""
    words = [w for w in _words(PREPOSITION.sub("", detail)) if w not in VAGUE]
    return words[-1] if words else ""


def _subject_words(memory):
    """The words the chat's thing can be named by, best first.

    The subject the store keeps is the best of them ("used bike" -> bike), but it is not always a
    thing: "what should i look for in a used bike" files the subject as "look", so the words of
    the last ask and of the answer it got are read too, and a word in both of those is the thing
    the chat is about before any other.
    """
    from . import topics  # noqa: PLC0415 - same package, kept local for the import order
    turns = [t for t in (memory.get("turns") or []) if isinstance(t, dict)]
    asked = str(turns[-1].get("user") or "") if turns else ""
    said = str(turns[-1].get("bot") or "") if turns else ""
    out = []
    for source in (topics.subject(memory) or "", asked):
        for word in source.split():
            word = re.sub(r"[^a-z]", "", word.lower())
            if len(word) > 2 and word not in VAGUE and word not in topics.STOPWORDS:
                out.append(word)
    seen, both, rest = set(), [], []
    for word in out:
        if word in seen:
            continue
        seen.add(word)
        (both if re.search(r"\b" + re.escape(word) + r"\b", said.lower()) else rest).append(word)
    return (both + rest)[:6]


def _the_entry_reply(found):
    """The text of an entry, or "" when there is none to say (a callable is not read here)."""
    reply = getattr(found, "reply", "") if found is not None else ""
    return reply if isinstance(reply, str) else ""


def _another_thing(detail, said):
    """True when the detail names something the answer in hand never speaks of.

    The answer given is asked as well as the thing named, because a detail about a part of the
    answer can be said in another way ("the bedroom ones" after a paragraph about a cold bedroom)
    and that is still the same answer's detail. What is left is a thing of its own.
    """
    if not _head_word(detail) or _head_word(detail) in NOT_A_THING:
        return False
    want = {word.rstrip("s") or word for word in _words(detail) if word not in VAGUE}
    have = {word.rstrip("s") or word for word in _words(said)}
    if not want or want & have:
        return False
    return True


def _what_it_is_worth(detail, memory):
    """"What about a dehumidifier" is the question "is one worth it", when the base keeps a card so.

    A thing named on its own is asked about the way people ask about a thing they might buy or
    take up, and the base keeps those cards under that ask ("should i get a dehumidifier" reaches
    the appliance card, "a dehumidifier" on its own reaches nothing). Only an answer that opens by
    naming the thing is taken, so a card about something else cannot be handed over this way.
    """
    head = _head_word(detail)
    if not head:
        return None
    try:
        from ..understanding import understand  # noqa: PLC0415 - only when a thing is named
        from ..knowledge import lookup as lookup_mod  # noqa: PLC0415
        from ..modules import answers  # noqa: PLC0415 - a card can be built from the reading
        understood = understand("should i get " + detail, {}) or {}
        found = lookup_mod.find(understood)
        reply = answers._payload(found, memory, understood)  # noqa: SLF001 - its own reader
    except Exception:  # noqa: BLE001 - an entry that cannot be read is no answer
        return None
    if not _says_about(reply, head):
        return None
    if repeat._already_repeated(reply, memory):  # noqa: SLF001 - said once already
        return None
    return reply


def _says_about(reply, head):
    """True when an entry's answer is about the thing itself, and says so as it opens."""
    if not isinstance(reply, str) or len(reply) < 40:
        return False
    first = re.split(r"(?<=[.!?])\s+", reply.strip())[0]
    return head in first.lower()


def _the_thing_itself(detail, memory):
    """The knowledge base's answer for the thing the detail names, asked beside the subject.

    A follow-up can name a thing of its own rather than a part of the answer, and the answer's
    step is then not its answer: "ive got about 400 pounds for a used bike" / "what should i look
    for" / "and what about a helmet" was replied "Same answer for a helmet: Check the frame for
    cracks and dents around the welds", which is the answer to a different purchase under the
    helmet's name. A friend answers about the helmet. The knowledge base keeps an entry for the
    two things together ("bike helmet"), so the thing is asked about with a word of the subject
    joined to it, and only an answer that names the thing itself is taken: "puppy biting" reaches
    the chewing entry, which never says "biting", and that is the answer already on the screen.
    """
    head = _head_word(detail)
    if not head or head in NOT_A_THING:
        return None
    try:
        from ..understanding import understand  # noqa: PLC0415 - only when a thing is named
        from ..knowledge import lookup as lookup_mod  # noqa: PLC0415
    except Exception:  # noqa: BLE001 - a reading that is not there costs the frame nothing
        return None
    for word in _subject_words(memory):
        if word == head:
            continue
        try:
            understood = understand(word + " " + head, {}) or {}
            reply = _the_entry_reply(lookup_mod.find(understood))
        except Exception:  # noqa: BLE001 - an entry that cannot be read is no answer
            continue
        # The entry has to answer about the thing itself, and say so as it opens. An entry for
        # the whole subject answers a narrowing of it too - "condensation bedroom" and "fan oven"
        # both reach the answer already on the screen or the lecture the person did not ask for -
        # and the step out of the answer they have is the better reply there.
        first = re.split(r"(?<=[.!?])\s+", reply.strip())[0]
        if len(reply) < 40 or head not in first.lower():
            continue
        if repeat._already_repeated(reply, memory):  # noqa: SLF001 - said once already
            continue
        return reply
    return None


def _asks_about_a_new_thing(text, detail, said):
    """True for "what about a case" whose thing the answer never speaks of.

    "im buying a new laptop" is answered with what to look for in the laptop, and the next line,
    "what about a case", was handed that same answer back - "Same answer for a case: Get 16GB of
    RAM..." - which is not about a case at all. A thing named after "what about" is only a
    narrowing of the answer when the answer speaks of it; when it does not, the line is a
    question about that thing and the honest answer is no answer here, not the last one again.
    """
    opened = ABOUT_OPEN.match(_flat(text))
    if not opened:
        return False
    # Only a thing said with an indefinite article is a thing of its own: "what about a case",
    # "what about a sleeping bag". "What about the bathroom" is where the windows are, and the
    # answer's step is about exactly that. A definite thing the answer speaks of (the biting,
    # the dehumidifier) is found by `_step_about` before this is asked.
    if not re.match(r"(?:a|an|some)\b", _flat(text)[opened.end():], re.I):
        return False
    from .topics import stem

    want = {stem(word) for word in _words(detail) if word not in VAGUE and word not in NAME_ONLY}
    if not want:
        return True
    have = {stem(word) for word in _words(said)}
    return not (want & have)


def _step_about(said, detail):
    """The part of the answer that is about the thing the detail names, or None.

    "i need to buy a tent" / "what about a sleeping bag" was answered from the last instruction
    in the answer - "Book the pitch ahead and check the site's rules on fires" - which is advice
    about the pitch, not about a sleeping bag. When the answer names the thing the detail names,
    that is where the answer is, however far down the paragraph it sits: the clause that names it,
    and the qualifier the sentence puts after it ("a foam or inflatable one, not just the tent
    floor").
    """
    want = {w for w in _words(detail) if w not in VAGUE and w not in NAME_ONLY}
    if not want:
        return None
    if _is_a_span(detail):
        # "for about three weeks now" narrows the answer by how long, not by name: a sentence of
        # the answer that happens to say "weeks" is not the answer about this thing ("in about
        # eight weeks you will run 20 minutes" for somebody two weeks in). See `_a_span_step`.
        return None
    sentences = [one.strip() for one in
                 re.split(r"(?<=[.!?])\s+", _flat(said)) if one.strip()]
    for sentence in sentences:
        # A list of things with one thing qualified ("a sleeping bag and a mat - a foam or
        # inflatable one") puts the qualifier in the next dash-group, so the groups are kept.
        groups = [one.strip() for one in re.split(r"\s+-\s+|\s+\u2014\s+", sentence)]
        for at, group in enumerate(groups):
            clauses = [one.strip() for one in group.split(",") if one.strip()]
            for pos, clause in enumerate(clauses):
                have = set(_words(clause))
                met = have & want
                if not (want <= have or len(met) * 2 > len(want)):
                    continue
                if not _one_of_a_list(clauses, groups, at):
                    # A sentence can name the thing without saying what to do about it: "A
                    # dehumidifier helps in a bedroom that gets it badly" is a description of
                    # the problem, and the move for a bedroom is "use the extractor fan, open a
                    # window for 10 minutes a day" in the sentence before. Only a clause that is
                    # one item of a list, or one that a dash-group follows, is the answer about
                    # the thing; anything else falls through to the step reader below.
                    continue
                if pos == len(clauses) - 1 and at + 1 < len(groups):
                    qualifier = groups[at + 1].strip(" .,;:-")
                    if 2 <= len(qualifier.split()) <= STEP_WORDS:
                        return qualifier + "."
                if have <= want | NAME_ONLY and pos + 1 < len(clauses):
                    # The clause is only the name ("a sleeping bag and a mat"), so the clause
                    # after it, which says what to look for, is the step.
                    clause = clauses[pos] + ", " + clauses[pos + 1]
                clause = JOIN_LEAD.sub("", clause.strip(" .,;:-"))
                if not clause or len(clause.split()) > STEP_WORDS:
                    return None
                return clause + "."
    return None


def _a_branch(sentence):
    """Whether the sentence is a case and what happens in it, rather than a move.

    "A cat is the kinder choice if you're out all day" is a branch of the answer: it says what
    to do in a particular case. Handed over as a step it answers the person's detail with a
    condition, and to whoever just said the other case it is not even theirs: "im at home all
    day" came back as "At home all day: A cat is the kinder choice if you're out all day".
    """
    return bool(condition.conditions(sentence))


def _without_branches(said):
    """The answer with the sentences that are cases of it taken out."""
    sentences = [one.strip() for one in
                 re.split(r"(?<=[.!?])\s+", _flat(said)) if one.strip()]
    return " ".join(one for one in sentences if not _a_branch(one))


def _the_move_itself(move):
    """The move without the half a colon puts after it.

    A colon says the clause in front of it is complete: what follows is a list or a second
    sentence, not the rest of the same one. Cut at a comma like any other clause boundary and the
    two halves were joined straight back together, so "ask early and in writing: unused holiday
    can usually be taken inside the notice" came back as "Ask early and in writing, unused
    holiday can usually be taken inside the notice" - a run-on that is not a sentence, handed to
    somebody who asked about the holiday they are owed. The half after the colon is never part of
    the step: they have had the answer once.
    """
    head = move.split(":", 1)[0].strip(" ,;.-")
    return head if len(head.split()) >= 2 else move

# The words a span is made of. A span narrows the answer's thing by how long, never by name, so it
# is not the word that picks the sentence of the answer (see `_a_span_step`).
SPAN_WORDS = frozenset("""day days week weeks month months year years fortnight fortnights
                          hour hours minute minutes""".split())
# A clause that opens on a joining word is the rest of the sentence before it, not a step of its
# own: handed over alone it reads "And in about eight weeks you will run 20 minutes".
# The small words a span is said with: "for about three weeks now", "since yesterday".
SPAN_WORDS_ABOUT = frozenset("""for in after since over within about now already past last next
                               been it its thats that and but so oh well yeah yep ok okay right
                               like that""".split())
NUMBER_WORDS = frozenset("""one two three four five six seven eight nine ten eleven twelve
                            couple few several half""".split()) | frozenset(
                                str(digit) for digit in range(0, 100))
LEAD_AND = re.compile(r"^(?:and|then|but|or|also|so|plus)\s+", re.I)


# A span said of a length: "in about eight weeks", "after two days", "3 months". This is the
# sentence that speaks to somebody who has already been at it for a while.
A_DURATION = re.compile(
    r"\b(?:\d+|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|a\s+few|couple\s+of|"
    r"several|a)\s+(?:day|week|month|year|fortnight)s?\b", re.I)


def _first_instruction(said):
    """The answer's first sentence that opens on something to do, cut to its first clause, or "".

    The instruction is often not the opening sentence ("Waking in the night is normal" comes
    first, "Keep the wake-up time the same" comes later), and the person who has just said how
    long it has been going wants the instruction.
    """
    from ..compose.verdict import IMPERATIVES  # the verbs an instruction can open on
    for sentence in re.split(r"(?<=[.!?])\s+", _flat(said)):
        clauses = [one.strip(" ,;:.-") for one in _clauses(sentence)]
        first = next((one for one in clauses if one), "")
        if not first or first.split()[0].lower() not in IMPERATIVES:
            continue
        if len(first.split()) > STEP_WORDS:
            # The method in brackets is not the step, and the instruction is short without it.
            bare = " ".join(re.sub(r"\s*\([^)]*\)", "", first).split())
            first = bare or first
        if 2 <= len(first.split()) <= STEP_WORDS:
            return first + "."
    return ""


def _opening_said(said):
    """The answer's first sentence, or its first clause when that is long."""
    first = re.split(r"(?<=[.!?])\s+", _flat(said))[0].strip()
    if not first:
        return ""
    if len(first.split()) <= STEP_WORDS:
        return first if first.endswith((".", "!", "?")) else first + "."
    return _first_clause(first)


def _is_a_span(detail):
    """True when the detail is only how long a thing has been going on, with no name in it."""
    want = {w for w in _words(detail) if w not in VAGUE and w not in NAME_ONLY}
    return bool(want) and not (want - SPAN_WORDS - NUMBER_WORDS - SPAN_WORDS_ABOUT)


def _a_span_step(said, detail):
    """The move in the answer that speaks of a span, when the detail is a span, or "".

    "i want to start running" / "its been about two weeks now" is somebody two weeks into it, so
    the sentence of the answer that speaks of a length of time is the one for them ("Each week add
    a minute to the jog") rather than the opening sentence they have already read. The last such
    sentence wins, because an answer gives the first step and then how it goes from there.
    """
    if not set(_words(detail)) & SPAN_WORDS:
        return ""
    for sentence in reversed(re.split(r"(?<=[.!?])\s+", _flat(said))):
        if not A_DURATION.search(sentence):
            continue
        for piece in _clauses(sentence):
            piece = LEAD_AND.sub("", piece.strip(" ,;:.-")).strip(" ,;:.-")
            if 2 <= len(piece.split()) <= STEP_WORDS:
                return piece + "."
    return ""


def _opening_of(said):
    """The first clause of the answer's opening sentence, when that sentence says what to do."""
    parts = [p.strip() for p in repeat.SENTENCE.split(str(said).strip()) if p.strip()]  # noqa: SLF001
    if len(parts) < 2:
        return ""
    clauses = [one.strip(" ,;:.-") for one in _clauses(parts[0])]
    first = next((one for one in clauses if one), "")
    if first and len(first.split()) > STEP_WORDS:
        # The method in brackets ("(a bent wire or tweezers does it)") is not the step, and the
        # instruction is short without it.
        bare = " ".join(re.sub(r"\s*\([^)]*\)", "", first).split())
        if bare:
            first = bare
    if not first or len(first.split()) < 2 or len(first.split()) > STEP_WORDS:
        return ""
    from ..compose.verdict import IMPERATIVES  # the verbs an instruction can open on
    if first.split()[0].lower() not in IMPERATIVES:
        return ""
    return first + "." if not first.endswith((".", "!", "?")) else first


def _a_step(said, questions_are_steps=False):
    """The one move out of the answer, cut at a clause boundary so it is not the answer again.

    A knowledge answer's move is often three instructions in one sentence ("use the extractor
    fan, open a window for ten minutes a day, dry clothes outside"): the detail of the thing is
    answered with the first of them, not with all three, because they have already had the
    paragraph once.
    """
    move = (repeat._a_move(said, questions_are_steps=questions_are_steps)
            or "").strip(" ,;:.-")  # noqa: SLF001
    if not move:
        return ""
    # The first thing to do is the opening sentence's first clause when the answer opens on an
    # instruction. An opening sentence too long to be a move on its own was skipped, and the last
    # instruction of the paragraph was handed back instead: for a blocked sink the step was "Skip
    # the chemical cleaner until last", which is the opposite of what to try first.
    opening = _opening_of(said)
    if opening:
        move = opening
    pieces = [p.strip() for p in _clauses(_the_move_itself(move)) if p.strip()]
    kept = pieces[0] if pieces else move
    for piece in pieces[1:]:
        # Only a short opening clause needs a second one to be a step at all. Joining onto one
        # that is already long enough is what cut a sentence in half: "for a week or two, most
        # running knee" is a fragment of the next clause, and a fragment reads as broken.
        if len(kept.split()) >= SHORT_STEP:
            break
        trial = kept + ", " + piece
        if len(trial.split()) > STEP_WORDS:
            break
        kept = trial
    kept = kept.strip(" ,;:-.")
    return kept + "." if kept else ""


def _capital(said):
    said = said.strip()
    if not said:
        return said
    return said[:1].upper() + said[1:]


# A REPORT ABOUT THE THING, RATHER THAN A NARROWING OF IT
#
# ```
# my boiler keeps losing pressure
#   Top the pressure up to between 1 and 1.5 bar using the filling loop ... If it keeps dropping,
#   there's a leak somewhere: stop topping it up and get a heating engineer out.
# it drops to zero every few days
#   -> Thanks for telling me — I'm here if you want to dig into any of that.
# is that dangerous
#   -> That's beyond what I know well, sorry. Searching for it will turn up better sources ...
# ```
#
# The second line is not small talk: the person is telling the bot more about the thing it has just
# answered, and that answer already has a sentence for it ("If it keeps dropping, there's a leak
# somewhere ..."). The nod that fits any message took the turn instead, and because it says nothing
# about the boiler the next line lost the subject and reached the search hedge - the same chat
# without that line answers "is that dangerous" properly.
#
# `the_detail` above does not take these lines on purpose: a report has a verb of its own, and it
# is not a phrase to put in front of the step. What it is is a report about the thing, so the reply
# is the sentence of the last answer that speaks to it, in the answer's own words. Nothing is
# composed here and nothing is invented: the sentence is the one that shares the report's own word
# ("drops" with "keeps dropping") and that is written about behaviour ("if", "when", "keeps",
# "usually"), so a sentence that merely follows it in the answer is never handed back.
#
# A line that asks something ("is that dangerous", "what should i do"), a line about a different
# thing, and a report about a thing whose answer says nothing about it are all passed back
# untouched: the caller's own pool answers those, which is where they were answered before.
REPORT_SENTENCE = re.compile(r"(?<=[.!?])\s+")

# The line has to be about the thing itself: "it drops to zero", "they make a noise", "there is
# water under it". A question about the thing ("is that dangerous") does not open this way, which
# is what keeps those lines with the modules that answer them.
REPORT_OPENS_ON_THE_THING = re.compile(
    r"^\W*(?:(?:and|but|so|then|also|now|well|ok|okay|right)\b[\s,]*)*"
    r"(?:it'?s|its|it|they'?re|they|there'?s|there|that'?s|that|this)\b", re.I)

# A line that asks something of its own is not a report, however it opens.
REPORT_ASKS = re.compile(
    r"\?|^\W*(?:(?:and|but|so|then|also|now|well|ok|okay|right)\b[\s,]*)*"
    r"(?:what|why|how|when|where|who|which|is|are|was|were|do|does|did|can|could|should|would|"
    r"will|shall|may|might)\b", re.I)

# The sentence that speaks to a report is written about how the thing behaves: a condition, a
# habit, a tendency. One with none of these is describing something else.
REPORT_BEHAVIOUR = re.compile(
    r"\b(?:if|when|whenever|unless|until|keeps?|kept|usually|often|always|every|tends?|starts?|"
    r"stops?)\b", re.I)

# A report that negates the thing ("it is not painful though", "it doesnt smell") is never answered
# by quoting the answer's sentence for that thing: the words match and the meaning is the opposite,
# so the sentence that says "go to A&E if the eye is red and painful" was handed to a person saying
# it is not painful. Those lines keep the reply they had.
REPORT_NEGATES = re.compile(
    r"\b(?:not|never|nothing|none|without|hardly|isn'?t|isnt|aren'?t|arent|doesn'?t|doesnt|"
    r"didn'?t|didnt|don'?t|dont|won'?t|wont|can'?t|cant|couldn'?t|couldnt)\b", re.I)

# A report is short. A paragraph about the thing is a new subject with its own answer.
# A sentence that sends the person to somebody: read out once as the answer, it is never the
# sentence that a detail of their own picks, because it says nothing about the detail.
A_REFERRAL = re.compile(
    r"\b(?:ring|call|phone|contact|see|visit|go\s+to|get\s+to|get\s+seen)\b[^.!?]*"
    r"\b(?:111|999|911|112|999|nhs|gp|doctor|nurse|a\s*&\s*e|casualty|hospital|pharmacy|"
    r"midwife|health\s+visitor|emergency)\b|"
    r"\b(?:should|needs?|ought)\s+(?:to\s+)?be\s+(?:looked\s+at|seen|checked|assessed)\b",
    re.I)
REPORT_WORDS = 14

# Words that carry no meaning of their own, so a shared one of these is not a shared subject.
REPORT_FILLER = frozenset("""
a an the and or but if then so to of in on at by for with from about as is are was were be been
being am do does did doing have has had having it its they them their this that these those there
here i me my we us our you your he she his her him one ones very really quite just now still
again too also only even not no yes yeah yep ok okay well right then than
""".split())

# The answer's own hedge is not an answer to anything: quoting a punt says less than the nod did.
NOT_AN_ANSWER = ("i don't know enough", "i dont know enough", "beyond what i know", "no live ",
                 "i'm not sure what you mean", "can't help with that", "searching for it",
                 "a search should", "better sources")


def _report_stem(word):
    """The word without the ending a verb or a plural wears, so "drops" meets "dropping"."""
    for ending in ("ing", "ed", "es", "s"):
        if word.endswith(ending) and len(word) > len(ending) + 2:
            word = word[:-len(ending)]
            break
    if len(word) > 3 and word[-1] == word[-2] and word[-1] not in "aeiou":
        word = word[:-1]
    return word


def _report_content(text):
    return [_report_stem(w) for w in _words(text)
            if w not in REPORT_FILLER and len(w) > 2]


def a_report_about_the_thing(text, memory):
    """The sentence of the last answer that speaks to this report about its thing, or ""."""
    said = _flat(text).lower()
    if not said or len(said.split()) > REPORT_WORDS:
        return ""
    if REPORT_ASKS.search(said) or not REPORT_OPENS_ON_THE_THING.match(said):
        return ""
    if REPORT_NEGATES.search(said):
        return ""
    turns = [t for t in (memory.get("turns") or []) if isinstance(t, dict)]
    if not turns:
        return ""
    answer = str(turns[-1].get("bot") or "")
    if len(answer) < 60:
        return ""
    lowered = answer.lower()
    if any(hedge in lowered for hedge in NOT_AN_ANSWER):
        return ""
    # The words of the report worth matching on: behaviour words the person used, long enough to be
    # a word of their own rather than a "get" or a "day".
    about = {w for w in _report_content(said) if len(w) > 3}
    if not about:
        return ""
    best = ""
    best_shared = 0
    for sentence in REPORT_SENTENCE.split(answer):
        sentence = sentence.strip()
        if len(sentence.split()) < 5:
            continue  # a fragment is not an answer on its own
        if sentence.endswith("?") or not REPORT_BEHAVIOUR.search(sentence):
            continue
        # A sentence that tells them to ring somebody, or to be seen, is advice to act and says
        # nothing about the detail they just added: "my chest hurts when i climb the stairs" /
        # "it stops when i rest" had the 111 line read out a second time instead of the
        # composer's care. The two answers that earn this reading are about the thing, not about
        # who to ring - the boiler's "if it keeps dropping, there's a leak" is the substance the
        # report was asking for.
        if A_REFERRAL.search(sentence):
            continue
        shared = len(about & set(_report_content(sentence)))
        if shared > best_shared:
            best, best_shared = sentence, shared
    if not best or best_shared < 1:
        return ""
    # A sentence the person has already had on its own is not handed back a second time.
    if _flat(best).lower() in {_flat(t.get("bot")).lower() for t in turns[-2:]}:
        return ""
    return _capital(best)
