"""A question about a fact of the person's own life, where the bot has not been told it.

"how many brothers do i have" got the search hedge ("I don't know enough to answer that honestly.
A search should sort you out quickly") - which is nonsense: no search engine knows how many
brothers the person typing has. "whats my middle name" got the same. The store answers these fine
when it was told (`memory_store`: "You told me you're 34", "Your sister is called Emma"), so what
is left is the case where nobody ever said it, and the honest answer there is not a search engine.
It is STYLE.md's "Not knowing, honestly" in its plainest form: only they know, say so in a few
words, and ask - which is also the one move that turns the gap into the fact the store can keep.

The question is read here, not composed from a list of facts: "how many X do i have" becomes "how
many X you have", "whats my X" becomes "what your X is", "when is my X" becomes "when your X is".
So the reply says the thing back in the person's own words and then says the true part.

Narrow on purpose. It takes a question about themselves - "my", "i have", "am i" - whose subject
is a thing of their own life: family, a name, an age, a birthday, a home, work, a pet, an
appointment. A how-to ("how do i lose weight"), a fact about the world ("how many people live in
wales"), a question about the bot ("whats your name"), an ask with no subject of theirs in it, and
anything the store or a card already answers keep the reply they had.
"""
import re

from . import pick

# A thing of their own life, the kind only the person can tell you. Kept as families of words
# rather than whole phrases, because the question is the person's own and there are as many of
# them as there are people: "my sister", "my kids", "my nan", "my landlord", "my shift".
OWN_WORDS = frozenset((
    # family and the people around them
    "mum", "mom", "mother", "dad", "father", "parent", "parents", "brother", "brothers",
    "sister", "sisters", "sibling", "siblings", "son", "sons", "daughter", "daughters", "kid",
    "kids", "child", "children", "baby", "wife", "husband", "partner", "nan", "nana", "gran",
    "granny", "grandma", "grandad", "grandpa", "grandparents", "aunt", "auntie", "uncle",
    "cousin", "cousins", "niece", "nephew", "inlaws", "family", "flatmate", "housemate",
    "landlord", "neighbour", "neighbours", "boss", "manager", "colleague", "carer",
    # a name, an age, a date of their own
    "name", "surname", "middlename", "nickname", "age", "birthday", "birthdate", "dob",
    # home, work, money, records
    "address", "postcode", "house", "flat", "home", "rent", "mortgage", "job", "work", "shift",
    "shifts", "rota", "wage", "wages", "salary", "pay", "holiday", "holidays", "leave",
    "appointment", "appointments", "referral", "prescription", "meds", "medication", "tablets",
    "results", "record", "records", "account", "bill", "bills", "order", "budget", "savings",
    # pets and possessions they keep track of
    "dog", "dogs", "cat", "cats", "pet", "pets", "puppy", "kitten", "car", "van", "bike",
))

# "how many brothers do i have", "how much holiday have i got left"
HOW_MANY = re.compile(r"^how (many|much)\s+(.+?)\s+(?:do|did) i have(?: left)?$")
HOW_MANY_GOT = re.compile(r"^how (many|much)\s+(.+?)\s+have i got(?: left)?$")
HOW_OLD = re.compile(r"^how old am i$")
# "whats my middle name", "what is my dogs name called", "whats my rent again"
WHAT_MY = re.compile(r"^what(?:s| is| was)?\s+my\s+(.+?)$")
# "when is my appointment", "what time is my shift"
WHEN_MY = re.compile(r"^(?:when|what time)(?:s| is| was)?\s+my\s+(.+?)$")
# "wheres my car", "where is my appointment"
WHERE_MY = re.compile(r"^where(?:s| is| was)?\s+my\s+(.+?)$")

# The pools. Every line says the same three true things - it is not known here, only they know it,
# and saying it lets the bot keep it - because that is all the bot can honestly say, and the
# wording is what stops it sounding like a form.
HAVEN_T_SAID = (
    "You haven't told me {q}, so I've no way to know - tell me and I'll remember it.",
    "I don't know {q}: that's yours, not something I can look up. Tell me and I'll keep it.",
    "I only know what you tell me, and you've not said {q}. What's the answer?",
)
# The same thing said when the clause reads better as the question it came from: "how many
# brothers do you have? You've not said, so only you know - tell me and I'll keep it."
AS_THE_QUESTION = (
    "{Q}? You've not said, so only you know - tell me and I'll remember it.",
    "{Q}? I can't look that up: it's about you. Say it once and I'll keep it.",
)

# A how-to is a different line and has an answer of its own; "how do i" is not a fact question.
HOW_TO = re.compile(r"\bhow (?:do|can|could|should|would|might) i\b")
# A question about the bot, not about them: "whats your name", "how old are you".
ABOUT_BOT = re.compile(r"\b(?:you|your|yours|yourself)\b")
# The store's own tells: if the line asks to be reminded of something already said, the store
# answers it and this never runs. It is here only so a line that lost its memory keeps the
# composer's reply rather than getting a second "you haven't told me".
SAID_BEFORE = re.compile(r"\b(?:again|remind me|did i say|did i tell you)\b")


def _has_a_shape(text):
    """True when the line is one of the question shapes below, whatever its tail is."""
    if HOW_MANY.match(text) or HOW_MANY_GOT.match(text) or HOW_OLD.match(text):
        return True
    return any(pattern.match(text) for pattern in (WHAT_MY, WHEN_MY, WHERE_MY))


def _as_clause(text):
    """The question as the thing they have not said: "how many brothers you have"."""
    found = HOW_MANY.match(text) or HOW_MANY_GOT.match(text)
    if found:
        many, thing = found.groups()
        return f"how {many} {thing} you have"
    if HOW_OLD.match(text):
        return "how old you are"
    for pattern in (WHAT_MY, WHEN_MY, WHERE_MY):
        found = pattern.match(text)
        if found:
            tail = found.group(1).strip()
            if re.search(r"\bcalled$", tail):
                return f"what your {tail}"
            if pattern is WHEN_MY:
                return f"when your {tail} is"
            if pattern is WHERE_MY:
                return f"where your {tail} is"
            return f"what your {tail} is"
    return None


def _as_question(clause):
    """The same clause turned back into the question a person would ask: "how many brothers you
    have" -> "how many brothers do you have"."""
    if clause.startswith(("how many", "how much")):
        return clause.replace(" you have", " do you have")
    if clause.startswith("how old you are"):
        return "how old are you"
    for head, ask in (("what your ", "what is "), ("when your ", "when is "),
                      ("where your ", "where is ")):
        if clause.startswith(head):
            tail = clause[len(head):]
            if tail.endswith(" is"):
                tail = tail[:-3]
            return ask + "your " + tail
    return clause


# A tail that is a noun phrase takes "what your X is" and reads right. A tail with a verb or a
# preposition in it does not: "what is my mum allergic to" is not "what your mum allergic to is",
# and "when is my mum coming" is not "when your mum coming is". Those are said back as the
# question they are instead, which keeps every word where the person put it.
NOT_A_NOUN_PHRASE = re.compile(r"\b(?:to|for|with|about|at|in|on|from|by|due|like|doing|going|"
                               r"coming|getting|allowed|before|after|now|then|anymore|"
                               r"originally|anyway)\b|\w+ing\b")


def _the_thing(text):
    """The word the question turns on, when it is a thing of their own life."""
    words = re.findall(r"[a-z]+", text)
    for word in words:
        if word in OWN_WORDS:
            return word
    # A plural the list does not carry ("brothers") is caught by its singular.
    for word in words:
        if word.endswith("s") and word[:-1] in OWN_WORDS:
            return word[:-1]
    return None


def _second_person(text):
    """The person's own question with themselves in the second person, every word in its place:
    "what was my budget" -> "what was your budget"."""
    out = re.sub(r"\b(whats|wheres|whens|hows)\b",
                 lambda m: {"whats": "what's", "wheres": "where's", "whens": "when's",
                            "hows": "how's"}[m.group(1)], text)
    out = re.sub(r"\bmy\b", "your", out)
    out = re.sub(r"\bdo i have\b", "do you have", out)
    out = re.sub(r"\bhave i got\b", "have you got", out)
    out = re.sub(r"\bam i\b", "are you", out)
    return out


def _capital(clause):
    return clause[:1].upper() + clause[1:]


def answer_for(text, memory):
    """A reply for a fact question about the person that nobody ever told the bot, or None."""
    if not text:
        return None
    clean = " ".join(text.lower().replace("\u2019", "'").split()).strip(" ?.!,")
    if not clean or len(clean.split()) > 10:
        return None
    if ABOUT_BOT.search(clean) or HOW_TO.search(clean) or SAID_BEFORE.search(clean):
        return None
    # A question that names no thing of theirs is not this reader's line, however it is shaped:
    # "how many do i need" and "whats my best option" are about the answer's own subject.
    if not _the_thing(clean) and not HOW_OLD.match(clean):
        return None
    if not _has_a_shape(clean):
        return None
    clause = _as_clause(clean)
    if clause and NOT_A_NOUN_PHRASE.search(clause.split("your", 1)[-1]):
        # A tail with a verb or a preposition in it is said back as the question instead.
        clause = None
    # One pool for the clause said out loud, one for the question said back; which one answers is
    # the composer's own chooser, so the same gap is not answered in the same words every time.
    if clause is None:
        return pick(AS_THE_QUESTION, memory, text).format(
            Q=_capital(_second_person(clean)), q=clean)
    pool = HAVEN_T_SAID if len(clause.split()) > 4 else AS_THE_QUESTION
    line = pick(pool, memory, text)
    # The question is the one they asked, with their own words in the second person, so the
    # tense and the word order are theirs: "what was my cat called" comes back as "what was your
    # cat called", not "what is your cat called".
    question = _capital(_second_person(clean))
    return line.format(q=clause, Q=question)
