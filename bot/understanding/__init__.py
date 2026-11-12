"""The understanding engine: what the user said and meant. The understanding lane owns it.

bot/modules/understand.py stores understand(text, memory) in memory["understood"] before any
module proposes a reply, so every module reads one reading of the line instead of matching its
own keywords.

The reading is built in four steps, each in its own module:

- `normalize.py`: messy typing becomes ordinary words (chat-speak, missing apostrophes,
  obvious typos, stretched letters), and run-on lines are split into clauses.
- `kinds.py`: what kind of line it is, the finer intent, and what it asks for.
- `topics.py`: the topic, the things it names, and the numbers with their units.
- `references.py`: what "it", "that", "they" and "there" point at, and whether the line
  follows the last one.

`understand()` returns a plain dict of plain data (README.md lists every key). Nothing here
answers; it only reads. `kind` keeps its four original values and `clean`/`words` keep their
meaning, so a module written against the seed's reading keeps working.
"""
import re

from . import body
from . import breeds
from . import kinds, lexicon, normalize, references, senses, topics
from .normalize import (background_positions, normalise, respell_urgent,
                        _the_part_that_hurts, _the_sugar_that_is_blood,
                        without_the_figure_of_speech)

# Words that carry no topic on their own, dropped from `keywords`.
STOPWORDS = frozenset("""
a an the and or but if then than that this these those there here it its i me my myself
we our us you your yours he him his she her hers they them their theirs am is are was were be
been being do does did doing done have has had having will would shall should can could may
might must not no nor so too very just really quite only also as at by for from in into of
off on onto out over under up with within without about above after again against all any
both each few more most other some such own same what which who whom whose when where why how
please thanks thank hi hello hey ok okay yeah yes sure sorry oh um uh like get got to want
need help tell give show find know think guess
""".split())
MAX_KEYWORDS = 14
LOOKBACK = 4          # how many earlier lines count as "the conversation so far"
# The bar a line's own topic must clear before it can be the conversation's subject. It is the
# same bar that makes a topic count at all, so a line that named something always leaves the
# conversation on that subject: "is that enough" two lines later is still about the fitness plan.
CARRY_TOPIC = 2
CARRY_WORDS = 8       # how much of the earlier line is carried for a follow-up
# Intents that answer the bot instead of leaning on what was already said: those never carry.
CARRY_PASS = frozenset("empty greeting farewell thanks ack smalltalk laugh about_bot".split())
# What a line that asks the bot about itself is about. The topic id is the deck's own area name,
# so a module that declares this area can be preferred on the line.
# What a thank-you can be said for, rather than go on with: "thanks for the recipe" and
# "thanks about the boiler" are sign-offs, and what follows names what was thanked for.
THANKED_FOR = frozenset("for about of so again".split())
# A thank-you that reports the thing went well closes the loop: "thanks, the oven temperature
# was perfect" is the sign-off itself, and the answer it would earn is a shrug.
# What a person did with the answer, which is the sign-off itself: "thanks, i set my oven to
# a lower temperature", "thanks, i tried it and it worked".
DID_IT = frozenset("""set put turned used tried made did got added took left changed lowered
    raised cleaned fixed swapped bought watched read told asked moved ran went came filled
    drained switched adjusted threw cleaned""".split())
PRAISED = frozenset("""perfect perfectly great brilliant sorted solved fixed works working
    lovely gorgeous spot marvellous marvelous amazing""".split())
ABOUT_THE_BOT = "about-the-bot"
# The words a line uses to talk to the bot rather than about the world. A question that names no
# subject of its own and puts one of these first is about the bot: "do you have a name" and
# "what model are u" read as naming nothing at all, and the deck's own about-the-bot rows were
# half unread because of it. They are only ever consulted when the line names no topic, so
# "where is your nearest shop" keeps the shop.
SECOND_PERSON = frozenset("you your yours yourself u ur youre ya ye yous".split())
# The words a question can open on and still be about the bot, when the bot is named within the
# next few: "where are you", "who created you", "what model are u". "How" is left out on purpose:
# it is the how-to family ("how do you spell necessary", "how do you bleed a radiator"), which
# asks about the thing, and a question about the bot's own day is named by its shape below.
ASKING_WORDS = frozenset("what which who whom whose where when why".split())
# A question that names the bot second is about the bot when it opens on a copula ("do you have a
# name", "are your answers always right"), and only when it opens on a modal if what follows is
# about the bot's own doing with nothing named: "can you hear me" and "can you cook" are the bot,
# while "can you freeze lettuce" and "can you cook a chicken with the lid on" are requests about
# the thing in them, which is why the modal question has to be a short one.
COPULA_AUX = frozenset("do does did are is was were have has will would".split())
MODAL_WORDS = frozenset("can cant cannot could".split())
MODAL_STATE = frozenset("see hear listen think feel remember understand know learn sleep dream "
                        "sing draw read write talk speak taste smell count help cook make".split())
# "who made you" asks about the bot; "who made you do that" asks about whoever made it say a
# thing, so a "who" question has to end on the bot or on one of its own words.
WHO_ENDS = frozenset("from here there".split())
# What a question can say about the bot once it has named it and still be about the bot. The
# words between the bot and its own state are fillers: "do you EVER get bored". Anything else
# after the bot is what the line is really about - "do you rate air fryers" is air fryers, and
# "do you reckon i should just ask her straight" is her - so it is not one of these.
AFTER_BOT_FILLER = frozenset("ever always still actually really even also just then now never "
                             "a an the".split())
BOT_STATE = MODAL_STATE | frozenset("""have has had got get make makes think thinks know knows
    remember remembers understand see hear listen feel feel help helps do does done
    bot bots robot robots llm ai chatgpt gpt claude human person people real alive awake
    busy smart clever intelligent right wrong sure ok okay there here about up online around
    ready name named personality hobbies hobby fun weekend weekends day days week evening
    morning night thing things lot bit much many answers answer mean means meant""".split())
# The nouns that are only ever the bot's: a line that says "model" or "hobbies" is about the bot
# whatever else it says around it ("which model are you using"), and one that says "air fryers"
# is not, however it opens.
BOT_NOUNS = frozenset("model models llm llms ai bot bots robot robots chatgpt gpt claude "
                      "name names personality hobby hobbies".split())
# "what would you do" and "what would you skip" put the user's own situation to the bot: the
# answer is about the last turn, not about the bot, and "would" is what says so. "what can you
# do" is the capability question and keeps its reading.
HYPOTHETICAL = frozenset("would wouldnt wouldve".split())
# The question about the bot's own time: "how was your day", "how did your week go", "how is your
# weekend been". It opens on "how" like a how-to question does, so the day word is what says which
# of the two it is.
DAY_VERBS = frozenset("was is are did has have were s".split())
# "what do you mean", "what do u mean by that": the line is asking what the bot's own words
# meant, and the tail after the verb adds nothing to it.
MEANING_WORDS = frozenset("mean means meant".split())
MEANING_TAIL = frozenset("by that this it there here then exactly you i".split())
DAY_WORDS = frozenset("day week weekend morning night evening afternoon".split())

# A line that only names a second thing - "and my shoulder too", "and the van as well" - stands on
# the line before it: the person is saying the same thing of another thing, and the words for what
# is wrong are elided because they were just said. "my back hurts" / "and my shoulder too" is a
# shoulder that hurts, and on its own the line names a thing with nothing said of it, so the health
# answer for a shoulder never got its chance and a greeting answered instead.
#
# What is lent is only what the earlier line said was wrong (the fault), never the thing itself:
# the second line keeps its own subject. Both halves are kept narrow, because a line that has
# anything of its own to say is not standing on the one before it:
#   * the join is how a person hangs a second thing on (and / also / plus / but at the front,
#     too / as well / also at the back), and it is what makes the line a second thing at all;
#   * the words left once the join is taken off are a name and nothing else - a verb of its own
#     ("and i do too", "and we went as well") means the line says its own thing and is left alone;
#   * the earlier line has to hold a fault to lend ("hurts", "aches", "is blocked", "wont start"),
#     taken with the words that make it a phrase, and the second line must not already say it.
SECOND_JOIN_HEAD = re.compile(
    r"^(?:(?:and|also|plus|but|so|then|yeah|yes|and\s+then|oh|and\s+yeah)\s+)+", re.I)
SECOND_JOIN_TAIL = re.compile(
    r"[\s,]*(?:\btoo\b|\bas\s+well\b|\balso\b|\ban\s+all\b|\band\s+all\b|"
    r"\band\s+that\b|\baswell\b)[\s.!?]*$", re.I)
# A correction names the thing it means instead of the one just said, and the fault the earlier
# line gave is still the thing's fault: "my knee hurts" / "no i mean my hip" is a hip that
# hurts, and read on its own it is a thing with nothing said of it - the bot answered it with the
# person's own words back ("Got it - no you mean your hip"). Only the words that say "I am naming
# it again, differently": a bare "no thanks" says nothing of the kind and is left alone.
CORRECTION_HEAD = re.compile(
    r"^(?:(?:no|nah|sorry|actually|wait|no\s+sorry|sorry\s+no)[\s,]+)?"
    r"(?:(?:i\s+mean|i\s+meant|i\s+did\s+mean|mean)"
    r"|(?:it'?s|it\s+is))\s+", re.I)
# The words that say a line is putting something right. Without one, the "it's" shape is also how
# a person opens the next thing they say - "its monday", "its under the door", "its not working" -
# and read as a correction each of them hands the earlier line's fault to a phrase that named no
# thing ("its under the door" became "under the door is leaking", "its not working" became "not
# working is leaking"). Where it does put something right it names both values ("its Preeya not
# Priya"), so the markerless shape has to hold a value in front of the "not" as well.
CORRECTION_MARKER = re.compile(
    r"^(?:(?:no|nah|sorry|actually|wait|no\s+sorry|sorry\s+no)[\s,]+)"
    r"|^(?:i\s+mean|i\s+meant|i\s+did\s+mean|mean)\b", re.I)
A_VALUE_IN_FRONT_OF_NOT = re.compile(r"\S.*\bnot\b", re.I)
# A name with a verb of its own in it is not elided: "and i do too", "and we went as well".
OWN_VERB = frozenset("""is are was were am be been being do does did done have has had having
    will would can could should shall may might must went go goes gone going came come comes
    coming get gets got getting make makes made making want wants wanted like likes liked need
    needs needed think thinks thought know knows knew say says said tell tells told try tries
    tried use uses used eat eats ate eating drink drinks drank cook cooks cooked buy buys bought
    sell sells sold work works worked play plays played watch watches watched read reads run
    runs ran walk walks walked live lives lived feel feels felt hurt hurts ache aches""".split())
# What the earlier line can say is wrong with its thing, longest phrase first so "is killing me"
# is lent whole and not as "is".
A_FAULT_TO_LEND = re.compile(
    r"\b(is\s+killing\s+me|kills\s+me|is\s+playing\s+up|is\s+on\s+the\s+blink|"
    r"(?:is|are)\s+not\s+working|(?:isnt|aren't|aint|isn't)\s+working|has\s+stopped|"
    r"have\s+stopped|keeps\s+stopping|wont\s+start|won't\s+start|doesnt\s+start|"
    r"doesn't\s+start|wont\s+turn\s+on|won't\s+turn\s+on|doesnt\s+turn\s+on|"
    r"doesn't\s+turn\s+on|wont\s+come\s+on|isnt\s+working|isn't\s+working|"
    r"is\s+blocked|is\s+blocked\s+up|is\s+leaking|is\s+flat|is\s+dead|"
    r"is\s+sore|is\s+stiff|is\s+swollen|is\s+broken|has\s+gone|is\s+bad|itches|itch|"
    r"hurts|hurting|hurt|aches|aching|ache)\b", re.I)


def _the_second_thing(text):
    """The name a second-thing line keeps once the join is taken off, or ""."""
    line = str(text or "").strip()
    if not line:
        return ""
    correction = CORRECTION_HEAD.match(line)
    if correction and not _says_which_value_is_meant(line):
        correction = None
    head = correction or SECOND_JOIN_HEAD.match(line)
    rest = line[head.end():] if head else line
    tail = SECOND_JOIN_TAIL.search(rest)
    core = (rest[:tail.start()] if tail else rest).strip()
    if not core:
        return ""
    if correction:
        # A correction holds nothing back: it is the join and the name and nothing else.
        words = [word.lower() for word in re.findall(r"[A-Za-z']+", core)]
        if not words or len(words) > 5 or any(word in OWN_VERB for word in words):
            return ""
        return core
    # A join at one end or the other is what makes it a second thing: "and my shoulder too" and
    # "my shoulder too" both hang on the line before, where "my shoulder" alone starts a subject.
    if not head and not tail:
        return ""
    words = [word.lower() for word in re.findall(r"[A-Za-z']+", core)]
    if not words or len(words) > 5:
        return ""
    if any(word in OWN_VERB for word in words):
        return ""
    return core


def _says_which_value_is_meant(line):
    """Whether a correction line names the value it means, or marks itself as a correction.

    "no i mean my hip", "sorry, it's the 3rd" and "i meant the back one" mark it themselves.
    The bare "its X" does not: it is the commonest way to start the next thing said, and the
    "not" with a value in front of it ("its Preeya not Priya") is the one markerless shape that
    can only be a correction.
    """
    if CORRECTION_MARKER.match(line):
        return True
    rest = CORRECTION_HEAD.match(line)
    if not rest:
        return False
    return bool(A_VALUE_IN_FRONT_OF_NOT.search(line[rest.end():]))


def _the_fault_to_lend(previous):
    """What the earlier line says is wrong with its thing, or ""."""
    found = A_FAULT_TO_LEND.search(str(previous or ""))
    return found.group(1) if found else ""


def _with_the_fault_lent(text, memory):
    """The line with the earlier line's fault on the end of its own name, or "".

    Only the line right after the one that said the fault, only the person's own earlier line,
    and only when this line would otherwise name a thing with nothing said of it.
    """
    core = _the_second_thing(text)
    if not core:
        return ""
    # The line the fault stands on is the nearest one that named one, which is not always the line
    # right before: "my back hurts" / "and my shoulder too" / "and my hip too" is three things
    # that hurt, and the third line has only the second to stand on. A line that says something
    # of its own ends the search - the chat has moved on and the fault is not this line's.
    fault = ""
    for earlier in reversed(_user_lines(memory, 3)):
        found = _the_fault_to_lend(earlier)
        if found:
            fault = found
            break
        if not _the_second_thing(earlier):
            break
    if not fault:
        return ""
    if A_FAULT_TO_LEND.search(core):
        return ""
    # The earlier line's fault is about its own thing: "and my shoulder too" after "the cake rose
    # nicely" has nothing to stand on, and "i dont know" is not a fault of the thing.
    return core + " " + fault


def _turns(memory):
    turns = memory.get("turns") if isinstance(memory, dict) else None
    return turns if isinstance(turns, list) else []


# How far back a line with no home in it can find the home somebody lives in: the line that says
# it is often several turns before the question it answers ("my mum moved into a home last month"
# ... "what should i bring her"). This only ever adds a reading to a line that names nobody.
HOME_LOOKBACK = 8


def _user_lines(memory, limit):
    """The user's last `limit` lines, oldest first."""
    lines = []
    for turn in reversed(_turns(memory)):
        text = turn.get("user") if isinstance(turn, dict) else None
        if isinstance(text, str) and text.strip():
            lines.append(text)
            if len(lines) >= limit:
                break
    return list(reversed(lines))


def _pointable(entities):
    """The entities a pronoun can point at.

    A thing, a place, a person or a title always counts. A cap from the start of a line counts
    only when it reads as a name: "Two weeks in September" starts with a cap that is not a
    name, and "We've got 12,000 so far" must not become the thing a later "it" points at.
    """
    kept = []
    for entity in entities:
        kind, word = entity.get("type"), str(entity.get("text", "")).lower()
        if kind in ("thing", "place", "person", "title"):
            kept.append(entity)
        elif kind == "name" and "'" not in word and word not in topics.COMMON_WORDS:
            kept.append(entity)
    return kept


def _pointed_at(history):
    """The earlier line a pronoun in the next turn points at: the nearest one that names
    something. A line that only leans on the line before it ("its worse when i lie down",
    "what should i do?") does not take the thing being talked about away, so the search
    carries on past it: "should i see someone about it" still means the heartburn."""
    for text in reversed(history):
        read = normalise(text)
        entities = _pointable(topics.detect_entities(read))
        if entities:
            return read, entities
    return None, []


# Every word a line can use to point at something already said (references.PRONOUNS).
ANY_PRONOUN = frozenset(word for aliases in references.PRONOUNS.values() for word in aliases)


def _the_recorded_subject(memory):
    """The line the conversation's stored topic came from, when the last few name nothing.

    A follow-up that points at something ("will they survive that") looks past the last line
    when that line names nothing. The search only reads the last few lines, so in a long chat
    the subject itself can have aged out of it: after five turns on tomatoes, "im away for 2
    weeks in august" named nothing and "will they survive that" pointed at the August line
    instead of the tomatoes. The store keeps the line the topic came from (`of`), which is
    what a person means when nothing nearer names a thing.
    """
    record = memory.get("topic") if isinstance(memory, dict) else None
    if not isinstance(record, dict):
        return None, []
    for key in ("of", "text"):
        line = record.get(key)
        if not isinstance(line, str) or not line.strip():
            continue
        read = normalise(line)
        entities = _pointable(topics.detect_entities(read))
        if entities:
            return read, entities
    return None, []


def _recent_topic(lines):
    """The topic the conversation has been on: the topic of the most recent line that names
    one. "is that enough" names nothing, so it is still about the fitness plan two lines up;
    a line that merely mentions something at the edge does not take the conversation over."""
    best = None
    for index, text in enumerate(lines):
        read = normalise(text)
        topic, score = topics.detect_topic(read, None, topics.detect_entities(read))
        if topic and score >= CARRY_TOPIC:
            key = (score, -index)          # best evidence first, then the earliest line
            if best is None or key > best[0]:
                best = (key, topic)
    return best[1] if best else None


# Ways of saying "this is a different question now". The conversation's topic stops carrying.
SHIFTS = ("never mind", "nevermind", "forget that", "forget it", "different question",
          "new question", "new topic", "changing the subject", "change of subject",
          "on another note", "moving on", "back to", "anyway", "anyways", "instead",
          "another thing", "unrelated", "off topic")
# "actually" is a shift at the front of a clause ("actually, make it Tuesday", "no, actually the
# spare room") and filler in the middle of one ("what do I actually say?", "do I actually need
# it?"). Read as a shift everywhere it stopped a follow-up from leaning on the line before it,
# and "what do I actually say?" after a friend line got the shrug instead of the sentence.
SHIFT_ACTUALLY = re.compile(r"(?:^|\|)\s*actually\b|\b(?:no|oh|well|sorry|and|but),? actually\b")


def _changes_subject(line):
    padded = " " + line["norm_text"] + " "
    if any(cue in padded for cue in SHIFTS):
        return True
    return bool(SHIFT_ACTUALLY.search(line["norm_text"]))


def _names_a_bot_noun(words):
    """Whether the line says one of the words only the bot has: "model", "hobbies", "bot"."""
    return any(word in BOT_NOUNS for word in words)


def _about_the_bot(line, read, entities=()):
    """Whether a line that named no topic of its own is asking the bot about itself.

    Two shapes ask it. The kinds already read one of them (`about_bot`: "do you remember what I
    said", "can you see me"), and the plainest ones - a question whose first words are about the
    bot - read as naming nothing at all: "do you have a name", "are you smart", "where are you",
    "hows u", "what model are u".

    Only a question counts, and only one that opens on the bot ("do you ...", "are your ...",
    "where are you") rather than naming a thing first: "is that your coat" is a coat, and a line
    that names a place or a person is about what it named ("what do you know about lisbon").
    It is also only ever asked once the line has named no topic of its own, so "are you happy"
    keeps its feelings and "can you help me with my tax" keeps the tax.
    """
    if read.get("intent") == "about_bot":
        return True
    if read.get("kind") != "question" or entities:
        return False
    words = [word for word in (line.get("words") or []) if word != "|"]
    if len(words) < 2:
        return False
    if (words[0] == "how" and len(words) > 3 and words[2] in SECOND_PERSON
            and words[1] in DAY_VERBS):
        return any(word in DAY_WORDS for word in words[3:])
    if words[1] in SECOND_PERSON:
        if words[0] in COPULA_AUX:
            # "do you have a name", "are your answers always right", "are you smart": the
            # copula says nothing on its own, so what comes after the bot has to be about it.
            rest = [word for word in words[2:] if word not in AFTER_BOT_FILLER]
            return not rest or rest[0] in BOT_STATE or _names_a_bot_noun(words)
        return (words[0] in MODAL_WORDS and 2 < len(words) <= 4
                and words[2] in BOT_STATE)
    if not (words[0] in ASKING_WORDS
            and any(word in SECOND_PERSON for word in words[:4])):
        return False
    if words[0] == "who":
        return words[-1] in SECOND_PERSON or words[-1] in WHO_ENDS
    bot_at = next(index for index, word in enumerate(words) if word in SECOND_PERSON)
    if any(word in HYPOTHETICAL for word in words[1:bot_at]):
        return False
    rest = [word for word in words[bot_at + 1:] if word not in AFTER_BOT_FILLER]
    # What the bot's own words meant is about the bot however long the line is: the length cap
    # below is for the lines that name something, and "by that" names nothing.
    if (rest and rest[0] in MEANING_WORDS
            and all(word in MEANING_TAIL for word in rest[1:])):
        return True
    # A short line that names nothing else is the question; a long one is about what it names.
    if len(words) > 5:
        return False
    return not rest or rest[0] in BOT_STATE or _names_a_bot_noun(words)


# A presence check: "u up?", "you there?", "anyone around?" asks whether the bot is here at
# all. It is not a question about the world, so it must not be answered with "I don't know".
PRESENCE_SUBJECT = frozenset("you u ya your yourself me".split())
PRESENCE_WORD = frozenset("""up there around about here online awake alive ready with
    free""".split())
# "heya" and "evenin" are greetings people type that the greeting list does not carry, so a
# presence check behind them would otherwise be read as a question about the world.
# "u free later?", "you around later?": a word of the near future is not a subject, so the ask
# is still about whether the bot is here. A day is different and stays out - "are you free on
# saturday" and "you free this weekend" are someone proposing something, not checking the bot is
# reading, and tests/test_understanding.PresenceTest holds that line.
PRESENCE_FILLER = frozenset("""still ok okay good right fine then now anyone anybody someone
    hello hey hi hiya heya howdy yo morning evenin again mate pal buddy all are is r else
    later soon l8r""".split())
PRESENCE_ASKER = frozenset("anyone anybody someone".split())
PRESENCE_NOT = frozenset("""greeting thanks farewell empty""".split())
PRESENCE_MAX = 5
# A greeting in front of the question does not change it: "hiya, u about?" asks what "u
# about?" asks. Only the single-word greetings, and only as the first word.
PRESENCE_GREETING = frozenset(word for word in kinds.GREETINGS if " " not in word)
# "good morning", "good evening": the greetings that are two words, so a short ask still reads
# as the ask when one of these is in front of it.
GREETING_PHRASE = frozenset(word for word in kinds.GREETINGS if " " in word)
OWN_QUESTION_TOPIC = "nature-and-weather"


# Asking the bot for its view rather than about the world: "what do you think", "what's your
# advice", "anything you'd suggest". The words that may be in such a line and still leave it
# naming nothing are the ask itself, the bot and the filler around them - anything else is a
# thing, and a line with a thing in it keeps its own reading.
NOTHING_NAMED_ASK_WORDS = frozenset("""what which who how why when where do does did would should
    will can could is are any anything something else more that this it for me i we to about of
    in on with""".split())
NOTHING_NAMED_VIEW_WORDS = frozenset("""think say suggest recommend advise reckon opinion advice
    thoughts thought view take recommendation suggestion ideas idea""".split())
NOTHING_NAMED_FILLER = frozenset("""so and ok okay right well but then now here first next
    actually please pls""".split())
BOT_ASK_WORDS = frozenset("you u ya your yours yourself".split())

# "knackered" and "buggered" are two words with two senses, and the owner in the line says
# which is meant: a machine that is knackered is broken, a person who is knackered is worn out.
# The fault answers are matched on the word "broken", so with the word left as typed the line
# reached nothing at all - "my washing machine is knackered" was answered "I'm listening - say
# more if it helps." where "my washing machine is broken" reaches the plug-fuse and door-check
# card, and the same for "the boiler is knackered", which is the pressure-gauge card.
BROKEN_OF_A_THING = ("knackered", "buggered")
EDGE_PUNCTUATION = ".,!?;:'\"()"
# The words that may stand between the thing and the word and leave the thing its owner: the
# verb that carries the state, and the measures someone puts in front of it.
# A verb between the thing and the word that is not the verb carrying the state means the thing
# is not the subject any more ("the kids have knackered me" is a person worn out, not a broken
# child), and a comma ends the clause the same way.
A_CLAUSE_VERB = frozenset("""have has had having do does did done get gets got getting
    go goes went gone make makes made making take takes took taken come comes came bet bet
    felt feel feels leave leaves left keep keeps kept put puts""".split())


def _a_word_that_depends_on_the_owner(plain, entities, state_owner=None):
    """The sense of "knackered" that means broken, where a thing in the line owns the word.

    The owner is the thing the state is said *about*: "my washing machine is knackered" is a
    machine that is broken, and "im knackered" names nothing and is a person who is worn out.
    A person named first ("the kids have knackered me") keeps the word: nothing is broken.

    It is not enough for a thing to be named somewhere earlier in the line. "just got back from
    a night shift, knackered" is the person worn out, and the shift is not being called broken;
    so the thing has to be the subject of the clause the word sits in - between the thing and
    the word there may be nothing but the verb that carries the state and a measure or two, and
    a comma in between ends the clause and the claim with it.
    """
    if not plain or not entities or state_owner == "self":
        return plain
    owners = set()
    for entity in entities:
        if entity.get("type") == "thing":
            owners.update(word.lower() for word in entity["text"].split())
    if not owners:
        return plain
    words = plain.split()
    out = []
    for at, word in enumerate(words):
        bare = word.strip(EDGE_PUNCTUATION).lower()
        if bare not in BROKEN_OF_A_THING:
            out.append(word)
            continue
        between = []
        owner = None
        for back in range(at - 1, -1, -1):
            earlier = words[back]
            if any(mark in earlier for mark in ",;:?!."):
                break
            low = earlier.strip(EDGE_PUNCTUATION).lower()
            if low in owners:
                owner = low
                break
            between.append(low)
        if owner is None or any(word_ in A_CLAUSE_VERB for word_ in between):
            out.append(word)
        else:
            out.append(word.replace(word.strip(EDGE_PUNCTUATION), "broken"))
    return " ".join(out)


def _opens_the_conversation(previous):
    """True when there is nothing before the line to have a view about.

    The first line of a conversation is one thing; a line that follows "hi" or "thanks" is the
    same. A line that follows anything with something in it is a follow-up whatever it looks
    like - "im looking at two bikes" / "what would you suggest" is a question about the bikes -
    so only a person's opening line is read as an opening.
    """
    if previous is None:
        return True
    return len([word for word in previous.get("norm") or [] if word and word != "|"]) <= 3


def asks_with_nothing_named(norm):
    """True when the line asks the bot's view of something it has not named yet.

    "what's your advice" and "anything you'd suggest" were search hedges: there is nothing named
    to advise on, and the reply that helps is to ask what it is about. "what's your advice on my
    cv" names the cv and keeps its own reading.
    """
    words = [word for word in norm if word and word != "|"]
    if not any(word in BOT_ASK_WORDS for word in words):
        return False
    if not any(word in NOTHING_NAMED_VIEW_WORDS for word in words):
        return False
    rest = set(words) - NOTHING_NAMED_ASK_WORDS - BOT_ASK_WORDS - NOTHING_NAMED_VIEW_WORDS \
        - NOTHING_NAMED_FILLER
    if rest:
        return False
    # "can you think" and "could you say that again" put the bot itself in the subject seat: they
    # ask what it can do, not what it makes of something, and they have their own answer.
    return not (words[0] in ("can", "could") and len(words) > 1
                and words[1] in BOT_ASK_WORDS)


def _presence(line):
    """True when the whole line asks whether the bot is there, e.g. "u up?" or "you around?".

    A greeting ("hey there") is a greeting, not a presence check, so the line also has to
    address the bot (you/u) or ask after anyone at all, or leave the person out entirely the
    way people do when they are not sure anyone is reading: "still there?", "still up?".
    """
    # The clause break normalise() puts after a greeting is not a word, so it cannot count
    # against the short line this reads.
    words = [word for word in line["norm"] if word and word != "|"]
    if words and words[0] in PRESENCE_GREETING:
        words = words[1:]
    if not words or len(words) > PRESENCE_MAX:
        return False
    if not any(word in PRESENCE_WORD for word in words):
        return False
    asked = any(word in PRESENCE_SUBJECT or word in PRESENCE_ASKER for word in words)
    # "still there?" drops the "you". Only a short line made of nothing but the question and
    # its fillers can do that; anything else ("is it up", "are you ok") is about something.
    dropped_subject = len(words) <= 2
    if not asked and not dropped_subject:
        return False
    return all(word in PRESENCE_WORD or word in PRESENCE_SUBJECT or word in PRESENCE_ASKER
               or word in PRESENCE_FILLER for word in words)


# Asking for a moment, or asking whether they may ask at all: "got a sec?", "can I ask you
# something", "are you free to chat". These want "yes, go on", so they are presence checks too -
# the answer is not about the world, and a search hedge is the wrong reply to "have you got a
# minute". Kept to the words that carry the ask, so a real request keeps its own reading:
# "have you got a minute to look at my boiler" names the boiler, and that is a request.
MOMENT_WORDS = frozenset("""sec secs second seconds min mins minute minutes mo moment
    time""".split())
MOMENT_VERBS = frozenset("got have get spare".split())
MOMENT_FILLER = frozenset("""a an the to for chat talk and i you u me ask something question
    quick please ta thanks can could would may might will just wanted like us we mind if
    wondering favour favor do does did hey hi hello so well um er there""".split())
ASK_PERMISSION = ("ask you something", "ask you a question", "ask you one", "ask a question",
                  "ask something", "ask you quick question", "ask a quick question",
                  "bend your ear", "pick your brains", "ask your advice",
                  "talk to you", "talk with you", "chat to you", "chat with you",
                  "can we talk", "could we talk", "can we chat", "have a word", "quick word",
                  "quick question", "quick one", "ask a favour", "ask you a favour")
# Words that may sit round the ask without making the line about anything: "i wanted to talk to
# you", "can i ask you a quick question", "you got a minute to chat", "hey, quick word".
# A word that says *when* the talk happens is the line's own news, not filler: "talk to you
# later" and "chat to you soon" are how a person leaves a conversation, and the answer to them
# is "take care", not "go on". So only "now"/"then" are here, where the ask is still happening.
PERMISSION_FILLER = frozenset("""you u ya your yourself need needed want wanted mind about
    something then now bit wee little one just really actually
    ok okay hey hi hello so well oh ah and but or yeah yes please ta thanks love mate""".split())
ASK_FREE_WORDS = frozenset("free around available busy".split())
ASK_FREE_FILLER = frozenset("""are is you u ya to for a chat talk then now still or and quick
    moment min minute sec second right mate please""".split())


# A word that says *how* the talk should go does not say anything about the world: "can we talk
# properly" asks for the talk as plainly as "can we talk" does. An adverb of manner is the shape
# it takes, but the -ly ending is not the test on its own: "can we talk about sicily" named a
# place, and sicily, assembly and anomaly were all read as the way the talk goes, which turned a
# real question into "What's on your mind?".
NOT_MANNER = frozenset("""silly friendly lovely lonely ugly early daily weekly monthly yearly
    likely only family reply supply apply july italy belly jelly rally fly""".split())
# The talk verbs: a word of manner follows one of these directly ("can we talk properly"), or
# follows the "more/much/really/very" that shapes it ("can we talk more privately").
TALK_VERBS = frozenset("talk talking speak speaking chat chatting discuss discussing".split())
MORE_WORDS = frozenset("more much really very".split())
# The adverbs people use about a talk. A closed list, because plenty of -ly words name a thing.
MANNER_TALK = frozenset("""properly privately seriously openly honestly frankly quietly calmly
    briefly quickly plainly directly bluntly gently carefully sensibly reasonably""".split())
# "is this a good time", "is now ok": the line asks whether now suits and names nothing else, so
# it is the same ask as "you got a minute" and wants the same "yes, go on" - it was a search hedge.
GOOD_TIME_WORDS = frozenset("""a an the it this that is s good bad ok okay fine right wrong
    better best time moment now for to then or""".split())
# The words that may sit round "can we talk <manner>" and say nothing themselves.
# A word that says *when* is not here: it makes the line a plan rather than a question about
# this moment ("can we talk tonight", "talk to you soon", "chat to you later"). Only "now" and
# "then" stay, where the ask is still happening, the same rule PERMISSION_FILLER keeps.
TALK_FILLER = frozenset("""can could would will may might shall should we i you u ya us to for a
    about with now just please then""".split())


def _a_manner(norm, at):
    """True when the word here says how the talk should go rather than naming anything."""
    word = norm[at]
    if len(word) <= 4 or not word.endswith("ly") or word in NOT_MANNER:
        return False
    if word in MANNER_TALK:
        return True
    back = at - 1
    if back >= 0 and norm[back] in MORE_WORDS:
        back -= 1
    return back >= 0 and norm[back] in TALK_VERBS


def _not_manner(norm):
    """The words of a line that say something, with the words of manner taken out.

    An intensifier goes with the manner word after it: "can we talk more privately" says nothing
    about the world either.
    """
    left = set()
    for at, word in enumerate(norm):
        if _a_manner(norm, at):
            continue
        if word in MORE_WORDS and at + 1 < len(norm) and _a_manner(norm, at + 1):
            continue
        left.add(word)
    return left


# The load a person carries for everybody else is said as the job they do, never as a word for
# how they feel: "im always the one who organises everything", "everyone leans on me", "i never
# get a minute to myself". Nothing in a line like that is a feeling word, so no pool of feelings
# fired and the line was answered with a shrug - "I'm listening - say more if it helps" - to a
# person who had just said what the trouble is. It is not loneliness either (they may be
# surrounded), and it is not a named mood: it is a job nobody shares.
#
# The shapes are the ones people use for it, and each carries a word that says *all* of it
# (`everything`, `everyone`, `never`), because the same words without it are an ordinary chore:
# "im the one who does the bins" is not this, and "im always the one who organises everything" is.
LEANS_ON_THEM = re.compile(
    r"\b(?:everyone|everybody|they all|all of them)\s+"
    r"(?:leans?|rel(?:y|ies)|depends?|counts?|comes?|come)\s+(?:on|to)\s+(?:me|us)\b")
DOES_IT_ALL = re.compile(
    r"\bi\s+(?:do|handle|manage|carry|hold|sort|run|organise|organize|deal\s+with)\s+"
    r"(?:it\s+all|everything|the\s+lot|all\s+of\s+it|the\s+whole\s+lot)\b"
    r"|\bi\s+(?:carry|hold)\s+(?:the\s+)?(?:whole\s+)?(?:house|family)\b"
    r"|\bi\s+do\s+everything\s+for\s+(?:everyone|everybody|them|the\s+kids)\b")
NO_TIME_OFF = re.compile(
    r"\bi\s+(?:never|hardly\s+ever|rarely)\s+get\s+(?:a\s+break|five\s+minutes)\b"
    r"|\bi\s+(?:never|hardly\s+ever|rarely)\s+get\s+a\s+(?:minute|moment|second)\s+"
    r"(?:to\s+myself|for\s+myself|off)\b"
    r"|\bi\s+(?:never|dont|do\s+not)\s+get\s+any\s+time\s+(?:to\s+myself|off|for\s+myself)\b")
ALL_ON_THEM = re.compile(
    r"\b(?:it'?s|its|it\s+is|everything\s+is|everything'?s)\s+(?:all\s+)?on\s+me\b"
    r"|\bit'?s\s+all\s+(?:down\s+)?to\s+me\b"
    r"|\ball\s+on\s+my\s+(?:own\s+)?(?:plate|shoulders|back)\b")
THE_ONE_WHO = re.compile(
    r"\bi'?m\s+(?:always\s+|usually\s+|often\s+)?(?:the\s+|the\s+only\s+)?one\s+(?:who|that)\b"
    r"|\bi\s+am\s+(?:always\s+)?(?:the\s+|the\s+only\s+)?one\s+(?:who|that)\b")
NO_ONE_HELPS = re.compile(
    r"\b(?:no ?one|nobody)\s+(?:else\s+)?"
    r"(?:helps?|helped|helps\s+out|does\s+anything|lifts\s+a\s+finger)\b")
EVERYTHING_AT_ONCE = re.compile(
    r"\b(?:everything|everyone|everybody|all\s+of\s+it|it\s+all|nothing|nobody|no ?one"
    r"|the\s+lot|the\s+whole)\b")
# "why do i have to do everything" is a question about the cause, and the answer to it is an
# explanation, not a warm line about a load: the pools stand down on a why.
# "i do everything i can" is effort, not a load: the all-word is how hard they try.
DOES_ALL_THEY_CAN = re.compile(r"\beverything\s+(?:i|we)\s+(?:can|could)\b")
# "her mother says no one helps her" is somebody else's house.
THIRD_PERSON = re.compile(
    r"\b(?:she|he|they|her|his|their|them|him|mum|mom|mother|dad|father|parents"
    r"|sister|brother|son|daughter|partner|husband|wife|friend|colleague|boss)\b")
# "no one helps" is the load only when it is the person's own: "my mother in law says no one
# helps her" is hers, and the reading belongs to whoever said it.
FIRST_PERSON_ANYWHERE = re.compile(r"\b(?:i|me|my|mine|myself|we|us|our)\b")
ASKS_WHY_IT_IS = re.compile(r"^\s*(?:why|how\s+come|what\s+makes|whats\s+making|what'?s\s+making)\b")
# "i do everything at work" and "i never get a break from work" are the job they are paid for, not
# the house nobody helps with, so a clause that puts the load at work is not this reading - unless
# the same clause names home as well ("i do everything at work and at home").
WORK_SCOPE = re.compile(r"\b(?:at|from|in|to)\s+work\b|\bwork(?:ing)?\s+(?:all|every)\s+(?:day|night)\b")
HOME_SCOPE = re.compile(r"\b(?:at|in)\s+(?:home|the\s+house|our\s+house|this\s+house)\b|\bhome\b")
# "i do everything right" is the good version of the load - the same words say it went well, and
# the good-news reading has that line.
DOES_IT_RIGHT = re.compile(r"\b(?:it|everything|things)\s+(?:all\s+)?(?:right|perfectly|correctly)\b")
# The house itself, said as the job: "im the one who runs the house" names no all-word, so the
# one-who arm misses it.
RUNS_THE_HOUSE = re.compile(
    r"\bi\s+(?:run|runs|running|manage|managing)\s+"
    r"(?:the|this|our)\s+(?:house|home|family)\b"
    r"|\bi'?m\s+(?:the\s+)?only\s+one\s+(?:who\s+)?(?:holds?|holding|keeps?|keeping|runs|running)"
    r"\b[^.]*\btogether\b"
    r"|\b(?:i'?m|i\s+am)\s+(?:always\s+|usually\s+)?(?:the\s+)?one\s+who\s+"
    r"(?:runs?|keeps?|holds?)\s+(?:the|this|our)\s+(?:house|home|family)\b")
# "i run myself ragged for everyone" is the load said as what it costs them.
RUNS_MYSELF_RAGGED = re.compile(
    r"\bi\s+(?:run|runs|running|work|working|push|pushing|drive|driving)\s+myself\s+"
    r"(?:ragged|into\s+the\s+ground|to\s+the\s+bone)\b")
# "nobody helps me with anything" carries its own person in the match, so the head in front of it
# is empty and the first-person test cannot see them.
HELPS_ME_NOT = re.compile(
    r"\b(?:no ?one|nobody)\s+(?:else\s+)?(?:helps?|helped)\s+me\s+(?:with|at|around)\b")


def a_load_carried(text):
    """True when the line says the person is the one holding it all up for everybody else.

    A reading, not a reply: `memory["understood"]["a_load_carried"]` carries it, so one module
    decides what a line like this is and every reader of the reading agrees.
    """
    said = " ".join(str(text or "").lower().replace("\u2019", "'").split())
    if not said:
        return False
    said = said.strip("'\" ")
    for piece in re.split(r"[.!?,;:]+|\bbut\b|\bthough\b", said):
        piece = piece.strip()
        if not piece or ASKS_WHY_IT_IS.match(piece) or DOES_ALL_THEY_CAN.search(piece):
            continue
        if WORK_SCOPE.search(piece) and not HOME_SCOPE.search(piece):
            continue
        if DOES_IT_RIGHT.search(piece):
            continue
        if RUNS_MYSELF_RAGGED.search(piece) or RUNS_THE_HOUSE.search(piece):
            return True
        if HELPS_ME_NOT.search(piece):
            return True
        if LEANS_ON_THEM.search(piece) or DOES_IT_ALL.search(piece):
            return True
        if NO_TIME_OFF.search(piece) or ALL_ON_THEM.search(piece):
            return True
        unhelped = NO_ONE_HELPS.search(piece)
        if unhelped:
            head = piece[:unhelped.start()]
            if FIRST_PERSON_ANYWHERE.search(head) and not THIRD_PERSON.search(head):
                return True
        if THE_ONE_WHO.search(piece) and EVERYTHING_AT_ONCE.search(piece):
            return True
    return False


def _asks_for_a_moment(line):
    """True when the line only asks whether the bot has a moment or whether they may ask."""
    norm = [word for word in line["norm"] if word and word != "|"]
    if not norm or len(norm) > 9:
        return False
    bare = " ".join(norm)
    for phrase in ASK_PERMISSION:
        if phrase in bare:
            # The idiom already says what the ask is, so only fillers may be left round it:
            # "pick your brains" is the whole line, "pick your brains about my boiler" is not.
            # The phrase's own last word comes along, so a word of manner right after the
            # talk verb it used up is still read as one: "can we talk properly" is the ask.
            rest = bare.replace(phrase, " ").split()
            last = phrase.split()[-1]
            if last in TALK_VERBS:
                rest = [last] + rest
            if not (_not_manner(rest) - MOMENT_FILLER - MOMENT_WORDS - MOMENT_VERBS
                    - PERMISSION_FILLER):
                return True
            # The idiom is here, but something beside it says what the line is about
            # ("can we have a word about my boiler"), so the checks below get their say:
            # "hiya can we talk" is the idiom with a greeting in front, and it used to stop
            # here on the greeting word alone.
            continue
    # A greeting in front of an ask for a moment does not change it, the same rule _presence
    # keeps for "hiya, u about?": "hiya, got a sec?" asks what "got a sec?" asks, and it was a
    # search hedge. Only at the front, so "morning, got a minute" is a request for one too while
    # "got a sec to look at my boiler" still names its boiler and keeps its own reading. The
    # ask-permission idiom above is left alone: "hiya, quick question" already has a warmer
    # answer than "go on" and the greeting does not take it away.
    while norm and norm[0] in PRESENCE_GREETING:
        norm.pop(0)
    if len(norm) > 2 and " ".join(norm[:2]) in GREETING_PHRASE:
        norm = norm[2:]
    words = set(norm)
    if not words:
        return False
    if words & ASK_FREE_WORDS and (words & PRESENCE_SUBJECT or len(norm) <= 2):
        return not _not_manner(norm) - ASK_FREE_FILLER - ASK_FREE_WORDS
    # "have you got the time" asks what the clock says and "have you got a minute" asks whether
    # the bot is free: the determiner is the whole difference. The clock row answers the first
    # (bot/knowledge/travel.py, `time-here`), so the moment reading has to leave it alone. Only
    # when "time" is the sole moment word - "got the time for a quick chat" is still the moment.
    if "the time" in " ".join(norm) and not ((words - {"time"}) & MOMENT_WORDS
                                             or words & TALK_VERBS):
        return False
    if words & MOMENT_WORDS and words & MOMENT_VERBS:
        return not (_not_manner(norm) - MOMENT_FILLER - MOMENT_WORDS - MOMENT_VERBS
                    - {"you", "u", "ya"})
    if words & {"time", "moment"} and (words - TALK_VERBS) <= GOOD_TIME_WORDS:
        return True
    # "can we talk properly", "hiya can we speak": the talk verb with a word of manner round it
    # is the whole ask, and MOMENT_WORDS does not carry the talk.
    if len(norm) <= 6 and words & TALK_VERBS:
        return not _not_manner(norm) - TALK_FILLER - TALK_VERBS
    return False


def _keywords(norm):
    return [word for word in norm
            if word not in STOPWORDS and (len(word) > 1 or word.isdigit())][:MAX_KEYWORDS]


# The words people ask a property with. They are the measure, never the thing measured, so an
# earlier line that names one says nothing a follow-up can lean on as its subject.
PROPERTY_SUBJECTS = frozenset("""
temperature temp temps degrees centigrade fahrenheit heat time times price cost size
setting weight length height age speed amount number
""".split())

SUBJECT_TYPES = ("title", "name", "person", "place", "thing")


# A line that asks a property of the thing in hand: "what temperature", "and how hot". What
# such a line carries is how the property is asked, not what it is asked about.
PROPERTY_ASK = re.compile(r"^\s*(?:and|so|ok|okay|also|but)?\s*[,:]?\s*(?:what|which|how)\b")


def _asks_a_property_and_nothing_else(text):
    """"what temperature" and "and how hot", and nothing else: a property asked of the thing.

    A line that states one is not this ("he has a temperature" is a thing about him, and the line
    after it is still about that), so the shape of the ask is what decides it, not the words.
    `bot/memory/topics.py` asks the same question of its own topic with its own word list, so
    that neither package has to import the other.
    """
    low = str(text or "").strip().lower()
    if not PROPERTY_ASK.match(low):
        return False
    found = _keywords(low.split())
    return bool(found) and all(word in PROPERTY_SUBJECTS for word in found)


def _leans_on(line, read, ref, carried_text, carried, previous, own_topic, previous_topic,
              previous_entities, carried_is_older=False):
    """The earlier line this one leans on, or None.

    "How long in the oven?" and "And if I stuff it?" are about the last thing the person
    said; on its own the line names no subject, so a knowledge lookup or a reply has nothing
    to hold on to. The same is true of a line that says more about the thing already on the
    table without naming anything new ("He's scared of men and hides under the table" after a
    rescue dog). Both are read against that earlier line. A line that points at something of
    its own (`topic_own`) is left alone: it has started something new.

    The words of the earlier line are handed on as plain data, so any module can read the line
    in context without keeping its own history (README.md, `leans_on`).
    """
    if not carried_text or read["intent"] in CARRY_PASS:
        return None
    if not ref["followup"] and own_topic:
        return None
    if _changes_subject(line):
        return None
    # A breed in the line being carried is the animal it is, here as anywhere: "we got a rescue
    # greyhound last week" then "she wont eat in the morning" is a dog that will not eat, and
    # the follow-up names no animal of its own, so the fill is where the animal's word goes.
    words = breeds.the_animal_a_breed_is(_keywords(carried["norm"]))
    if carried is not previous and not carried_is_older:
        # The last line only leaned on this one ("and how long?"), so its own words go in
        # beside the carried line's: they are how the person said what they wanted to know.
        # A line the store remembered from earlier is not that: it is a different line, and
        # its words are not how the person asked this one (a "feed" three turns back is not
        # part of "how much exercise does it need").
        for word in _keywords(previous["norm"]):
            if word not in words:
                words.append(word)
    words = words[:CARRY_WORDS]
    if not words:
        return None
    # A property asked of the thing in hand says how to measure it, not what it is: "i want to
    # cook a roast chicken" / "what temperature" / "how long for" leaned on the temperature, and
    # the words handed on reached the entry keyed on a temperature - the timing of a roast chicken
    # came back as the fever card ("most fevers from a virus settle within two or three days").
    # The measure word is dropped from what a later line leans on, and the thing the chat is on
    # answers instead. Only a line that asked a property is read this way: a temperature somebody
    # has ("he has a temperature") is a thing about them, and the line after it is still about it.
    asked_only = _asks_a_property_and_nothing_else(carried_text)
    words = [word for word in words if word not in PROPERTY_SUBJECTS] if asked_only else words
    named = [entity for entity in previous_entities if entity["type"] in SUBJECT_TYPES
             and not (asked_only and entity["text"].lower() in PROPERTY_SUBJECTS)]
    plain = [entity for entity in named if entity["type"] not in ("name", "title")]
    chosen = next((entity for entity in reversed(plain or named)), None)
    subject = chosen["text"].lower() if chosen else None
    return {"text": carried_text, "words": words, "subject": subject,
            "subject_type": chosen["type"] if chosen else None,
            "topic": previous_topic}


# A line after a courtesy that is about a person, or that says something is wrong, still wants
# an answer. A thing that came out right is how the thanks ends: "the paint covered the stain"
# and "the cake rose this time" are the person saying it worked.
PERSON_HEADS = frozenset("""i im ive ill id youre you he hes she shes they theyre we were weve
    weve us""".split())
POSSESSIVE = frozenset("my his her their our your".split())
AT_IT_STILL = frozenset("still again now".split())


def _about_a_person_or_a_trouble(after):
    """True when the words after a courtesy are about a person or name a trouble."""
    if set(after) & (kinds.NEEDS_ANSWER | AT_IT_STILL):
        return True
    if kinds.STILL_WRONG.search(" ".join(after)):
        return True
    if after[0] in PERSON_HEADS:
        return True
    if (after[0] in POSSESSIVE and len(after) > 1
            and after[1] in kinds.OTHER_PEOPLE | kinds.PERSON_NOUNS | kinds.MOOD_NOUNS):
        return True
    return False


def _about_something_of_its_own(after):
    """True when the words after a thank-you are a line about something, not a sign-off.

    "my boss is a nightmare" and "the tap is still dripping" name a thing and say something
    about it, so the thank-you is a wrapper and the line inside needs the answer. "that
    worked", "that helps a lot" and "love" say nothing of their own, and "that explains the
    boiler" comments on the answer just given rather than asking again, so the bar is the one
    a line's own topic has to clear.
    """
    if len(after) < 2 or after[0] in kinds.ADDRESS_WORDS:
        return False       # "thanks pet", "thanks love": the word left is who it is said to
    if after[0] == "i" and after[1] in DID_IT:
        # "thanks, i set my oven to a lower temperature" tells the bot what was done with the
        # answer, which is the sign-off itself. A fault named in the same breath is still
        # news: "thanks, i set the oven too high and burnt the cake" wants an answer.
        if not set(after) & kinds.NEEDS_ANSWER and not kinds.STILL_WRONG.search(" ".join(after)):
            return False
    words = set(after)
    if words & PRAISED:
        return False       # "thanks, the oven temperature was perfect" is the sign-off itself
    # A step of the advice done and reported back is the sign-off itself, the same way DID_IT
    # lines are, and says nothing the bot has to answer: "thanks, i cleared the cache",
    # "cheers, i restarted the router", "thanks, i gave it a go". A step that failed is news.
    if kinds._a_step_done(after) and not kinds._the_step_went_wrong(after):
        return False
    # Praise said with a verb is the sign-off too: "thanks, my son loved it", "cheers, the stew
    # went down well". So is a fall that is not one ("thanks, i fell asleep at nine"), the
    # oven's temperature ("thanks, i need a higher temperature"), and nothing left to do.
    if words & kinds.PRAISING_VERB or kinds.PRAISE_SAID.search(" ".join(after)):
        return False
    if kinds._a_fall_that_is_not_one(after):
        return False
    if "temperature" in after or kinds.SIGNING_OFF.search(" ".join(after)):
        return False
    if not _about_a_person_or_a_trouble(after):
        return False
    rest = normalise(" ".join(after))
    entities = topics.detect_entities(rest)
    topic, score = topics.detect_topic(rest, None, entities, False)
    return topic is not None and score >= CARRY_TOPIC + 1


# A bare follow-up, and the words it can open on. "what about a duck", "and the metro", "or a
# used one": the opener is not the question, and what follows it is the whole of what the line
# says. "what if" and "and if" are left out on purpose - a counterfactual is a new question of
# its own ("and if i use a bundt tin"), not the last one with a different thing in it.
FOLLOW_OPENER = (("and", "what", "about"), ("what", "about"), ("how", "about"), ("and",),
                 ("or",), ("also",), ("what",), ("how",))
# A word that makes what follows the opener a clause rather than a thing: "and the board i chop
# it on", "what if i start in march instead". A thing is named without a verb and without the
# person in it, so a phrase holding one of these is not the thing to put in the earlier ask.
NOT_A_THING = frozenset("""i im ive me we us you your youre u he she they theyre it its is are
    was were am be been being do does did can could should would will shall may might have has
    had if when while because since until though although than that this then there here and or
    but not no""".split())
# What can sit in front of a thing in a follow-up ("what about MY neck") and in front of the
# thing it goes in place of ("MY back hurts"): one of these is enough, two is one too many.
DETERMINER_TAIL = frozenset("the a an my your our their his her each every".split())


def _the_new_thing(words):
    """The thing a bare follow-up names, as its words, or None.

    "what about my neck" -> ["my", "neck"], "and jo" -> ["jo"], and None for "what about the
    board i chop it on", which says a whole clause rather than a thing.
    """
    phrase = list(words or ())
    dropped = True
    while dropped and phrase:
        dropped = False
        for opener in FOLLOW_OPENER:
            if tuple(phrase[:len(opener)]) == opener:
                phrase = phrase[len(opener):]
                dropped = True
                break
    if not phrase or len(phrase) > 5:
        return None
    for word in phrase:
        if word in NOT_A_THING:
            return None
    if not any(len(word) > 2 or word in lexicon.COMMON_NAMES for word in phrase):
        return None
    return phrase


# The words a thing can be swapped for another of, kept as the vocabularies the bot already
# knows: a person of the family, a name, a part of the body, a stretch of time. Two words of
# the same one of these are the same kind of thing, so one can stand where the other stood.
# Two words of different kinds cannot, which is why "and my job?" after "i work in a bakery"
# is read as its own line and not as "i work in a job".
SAME_KIND_WORDS = (("person", topics.RELATIONS), ("name", lexicon.COMMON_NAMES),
                   ("part", lexicon.BODY_PARTS), ("time", normalize.COUNT_UNITS))


def _the_same_kind(a, b):
    """The kind of thing these two words are, when they are one, or None."""
    for kind, words in SAME_KIND_WORDS:
        if a in words and b in words:
            return kind
    if any(ch.isdigit() for ch in a) and any(ch.isdigit() for ch in b):
        return "number"
    return None


def _where_the_swap_goes(before, phrase):
    """Where in the earlier line this line's own thing goes, as a slice of its words, or None.

    The place is chosen by what the thing is, not by position: a number goes where the earlier
    number is ("180c" -> "200c" in "what is 180c in fahrenheit"), a person where the earlier
    person is ("my son" -> "my mum" in "my son has a cough"), a part of the body where the
    earlier part is ("my back hurts" -> "my neck hurts"), a stretch of time where the earlier
    one is ("each week" -> "each month"). Nothing else is put in place of anything: a line
    that brings a thing of another kind is read as the line it is, which is how "what about
    the weather" stays a question about the weather.
    """
    places = list(before or ())
    if not places or not phrase:
        return None
    for word in phrase:
        for at, earlier in enumerate(places):
            kind = _the_same_kind(word, earlier)
            if not kind:
                continue
            end = at + 1
            if any(ch.isdigit() for ch in earlier):
                # "250 a month" is one amount: "300 a week" takes the unit with it, or the
                # line says "300 a week a month".
                while end < len(places) and (places[end] in normalize.COUNT_UNITS
                                             or places[end] in ("a", "an", "each", "per", "every")):
                    end += 1
            return at, end, kind
    return None


def _the_swap_is_said(before, phrase, place):
    """The earlier line with this line's own thing in it, or None when that is the same line.

    The "my" in front of the place stays: "what about my neck" after "my back hurts" is "my
    neck hurts", not "my my neck hurts".
    """
    places = list(before or ())
    said = list(phrase or ())
    if not places or not said or place is None:
        return None
    start, end, _kind = place
    if start > 0 and places[start - 1] in DETERMINER_TAIL and said[0] in DETERMINER_TAIL:
        said = said[1:]
    if not said:
        return None
    return " ".join(places[:start] + said + places[end:])


def _the_line_before(read, memory):
    """The last line the person sent, which is the ask a bare follow-up is asking again.

    It is the last turn of the memory rather than `leans_on`, because a follow-up can lean on a
    line further back: "im saving for a deposit" / "i can put by 400 a month" / "what about 500
    a month" leans on the deposit line, and the thing to swap is in the one before it.
    """
    turns = (memory or {}).get("turns") if isinstance(memory, dict) else None
    for turn in reversed(turns or ()):
        if isinstance(turn, dict) and isinstance(turn.get("user"), str) and turn["user"].strip():
            return turn["user"]
    leans = (read or {}).get("leans_on") if isinstance(read, dict) else None
    if isinstance(leans, dict) and isinstance(leans.get("text"), str):
        return leans["text"]
    return None


def _asked_again(read, memory=None):
    """The last ask with this line's own thing in it, or None.

    Only a bare follow-up is read this way: one that leans on an earlier line and names no
    subject of its own. The earlier line comes from the memory as plain data, so nothing here
    keeps a history of its own.
    """
    if not isinstance(read, dict):
        return None
    if not isinstance(read.get("leans_on"), dict):
        return None
    before = _the_line_before(read, memory)
    if not isinstance(before, str) or not before.strip():
        return None
    phrase = _the_new_thing(read.get("norm"))
    if not phrase:
        return None
    earlier = normalise(before)
    at = _where_the_swap_goes(earlier["norm"], phrase)
    if at is None:
        return None
    said = _the_swap_is_said(earlier["norm"], phrase, at)
    if not said or said == " ".join(earlier["norm"]):
        return None
    return said, at[2]


def understand(text, memory=None):
    """One reading of the user's line, as documented in README.md (memory["understood"])."""
    read = _read_line(text, memory)
    # A line that introduces the person with a word for how they are ("call me quiet", "my name
    # is lazy") is a statement about them, not a name: read it as the state it names.
    stated = _an_introduction_that_says_how_they_are(text)
    if stated:
        alt = _read_line(stated, memory)
        alt["text"] = read["text"]
        return alt
    # A line that only names a second thing is read with the fault the line before it named:
    # "my back hurts" / "and my shoulder too" is a shoulder that hurts, and read on its own it is
    # a thing with nothing said of it, so nothing answers it but a greeting.
    lent = _with_the_fault_lent(text, memory)
    if lent:
        alt = _read_line(lent, memory)
        if _reaches(alt):
            alt["text"] = read["text"]
            return alt
    # A bare follow-up asks the last question again with one thing changed: "what about 200c"
    # after "what is 180c in fahrenheit", "what about my neck" after "my back hurts", "and
    # each month" after "how much do i need to put by each week". Read on its own, the follow-up
    # says nothing a module can answer, which is why it used to get a shrug. So the line is read
    # as the earlier ask with this line's own thing standing where the earlier one stood.
    #
    # The swap is by what the words are, never by position: a number for a number, a part of the
    # body for a part of the body, a person for a person, a stretch of time for a stretch of
    # time. A thing of another kind is not put in place of anything, so "and my job?" after "i
    # work in a bakery" and "what about the weather" stay the lines they are.
    asked = _asked_again(read, memory)
    if asked:
        said, kind = asked
        # A person, a name, a part of the body or a stretch of time stands in for one of its own
        # kind in an ask or in a bare fragment ("and jo", "and each month"). A number only where
        # the line asks something: "so 440 a month" is a new figure, not the earlier question
        # with a bigger one in it.
        asked = said if (read.get("kind") == "question" or kind != "number") else None
    if asked:
        alt = _read_line(asked, memory)
        if alt.get("clean"):
            alt["text"] = read["text"] if isinstance(read.get("text"), str) else ""
            alt["fixes"] = read.get("fixes")
            alt["ref"] = read.get("ref")
            alt["leans_on"] = read.get("leans_on")
            # The words the line was read as, so a module or a test can see why it answered.
            alt["asked_again"] = asked
            return alt
    if _reaches(read):
        return read
    # A real word typed for the word that sounds the same is invisible to the reader: every
    # step reads "loose" as the word it is, so "whats the best way to loose weight" named no
    # topic at all and the bot shrugged at a fitness question. The table of those confusions is
    # a second chance, tried only on a line that read as nothing, and kept only when the line
    # then reads as something. The line as typed stays the line: facts and quotes are kept from
    # it, exactly as the spelling repairs already work (see bot/modules/understand.py).
    swapped, pairs = _confused_text(text)
    if not swapped:
        return read
    alt = _read_line(swapped, memory)
    if not _reaches(alt):
        return read
    alt["text"] = read["text"]
    alt["fixes"] = list(alt.get("fixes") or []) + pairs
    return alt


def line_as_read(understood):
    """The line with the repairs the engine made, for a reader that matches the line itself.

    `clean` keeps the line as it was typed, and that is right for a reply that quotes the
    person: "you said: i need a recipie". A reader that matches the line rather than its words
    has the other need. "a recipe for <dish>" is a shape, and the shape read as typed missed
    every line with a slip in the word "recipe" itself: "i need a recipie for shortbread" was
    not read as naming a dish at all, so the dish table answered with a list of ten-minute
    dinners while the shortbread card was there for the asking. `plain` is the same line with
    the repairs this pass settled, so the dish is still the dish after a slip. A reading with
    no plain line hands back the line as typed, so a reader never gets "".
    """
    if not isinstance(understood, dict):
        return ""
    plain = understood.get("plain")
    if isinstance(plain, str) and plain.strip():
        return plain
    return str(understood.get("clean") or understood.get("text") or "")


# What a reading has to have before a line counts as read: something it is about, something it
# asks, or something said about the person. A line with none of these is the only one worth a
# second chance at the words in it.
REACHING_KEYS = ("topic", "emotion", "body", "numbers", "summons", "presence")


def _reaches(reading):
    """True when a reading has anything to go on at all."""
    if not isinstance(reading, dict):
        return False
    for key in REACHING_KEYS:
        value = reading.get(key)
        if value:
            return True
    return False


def _an_introduction_that_says_how_they_are(text):
    """The state a line introduces with, or "".

    "call me quiet", "my name is lazy", "im called messy": the frame says a name is coming, and
    the word is how the person is. The store is right to refuse that word as a name (a session
    calling somebody Quiet is worse than holding no name at all), but the line then read as an
    introduction with nothing in it, and a phone's volume was explained to somebody choosing what
    to be called. Read as what it says about the person instead: "call me quiet" is "im quiet".
    Only a word from the reading's own table of how people are is taken, and only when it is the
    whole line, so "call me dave" stays an introduction and "call me when you land" stays a ask.
    """
    match = INTRODUCING_A_STATE.match(str(text or "").strip())
    if not match:
        return ""
    word = match.group(1).lower()
    if word in lexicon.A_DESCRIBING or word in lexicon.TRAITS or word in lexicon.A_STATE:
        return "im " + word
    return ""


# The frames that introduce a name, the softening words people put in front of the word, and the
# tail of the line: "call me quiet", "please just call me really quiet", "call me quiet please",
# "my name's lazy lol". A line that says more than that ("call me quiet and tall") is left alone.
INTRODUCING_A_STATE = re.compile(
    r"^\W*(?:(?:you can|please|just|ok|okay)\s+)*"
    r"(?:call me|my names?|my name['\u2019]s|my name is|im called|i am called|"
    r"i['\u2019]m called|known as)\s+"
    r"(?:(?:actually|honestly|properly|officially|tbh|really|very|so|quite|a bit|a little)\s+)*"
    r"([a-z][a-z'-]{1,19})"
    r"(?:\s*[,.!]*\s*(?:please|lol|lols|thanks|ta|cheers|then|btw|tbh|lmao|ha))?\s*[.!]*$", re.I)


def _said_of_themselves(words, place):
    """True when the word at `place` is how the person says they are.

    "im board", "im so board", "i feel really board": a first-person frame, at most a filler or
    two between it and the word. "my board has split down the middle" and "the chairman of the
    board" are a board, and this is what tells the one from the other.
    """
    back = place - 1
    while back >= 0 and words[back][0] in lexicon.FEELING_FILLER:
        back -= 1
    if back < 0:
        return False
    lead = words[back][0]
    if lead in lexicon.FEELING_LEAD:
        return True
    # "i was board", "i am board": the subject is the word before the frame.
    return (lead in ("was", "wasnt", "wasn't", "is", "isnt", "isn't", "get", "got")
            and back > 0 and words[back - 1][0] in ("i", "im", "i'm", "iam"))


def _confused_text(text):
    """The line with every sound-alike word put right, and the pairs that were changed.

    "" and [] when the line holds none of them, which is nearly every line, so the second
    chance costs one pass over a word list. Every word is looked at once, in the place it
    stands: a word is never bent twice ("quiet" to "quite" and back again), and a word that is
    only sometimes the other word is bent only where it is.
    """
    if not isinstance(text, str) or not text.strip():
        return "", []
    words = [(match.group(0).lower(), match.start(), match.end())
             for match in re.finditer(r"[A-Za-z']+", text)]
    if not words:
        return "", []
    pieces, pairs, cut = [], [], 0
    for place, (word, start, end) in enumerate(words):
        before = words[place - 1][0] if place else ""
        after = words[place + 1][0] if place + 1 < len(words) else ""
        meant = lexicon.CONFUSIONS.get(word)
        if not meant:
            pair = lexicon.CONFUSIONS_AFTER.get(word)
            if pair and before in pair[1]:
                meant = pair[0]
            else:
                pair = lexicon.CONFUSIONS_BEFORE.get(word)
                if pair and after in pair[1]:
                    meant = pair[0]
                elif not after:
                    meant = None
        if not meant:
            pair = lexicon.CONFUSIONS_IN_A_FEELING.get(word)
            if pair and (not after or after in pair[1]) and _said_of_themselves(words, place):
                meant = pair[0]
        if not meant and after in lexicon.QUESTION_WORDS:
            meant = lexicon.CONFUSIONS_BEFORE_A_QUESTION.get(word)
        if not meant or meant == word:
            continue
        pieces.append(text[cut:start])
        pieces.append(meant)
        cut = end
        pairs.append((word, meant))
    if not pairs:
        return "", []
    pieces.append(text[cut:])
    return "".join(pieces), pairs


# A line that puts a fact on a constraint of the thing in hand: "my budget is 5k" after "im
# buying a used car", "my age is 45" after "im thinking of retraining". It names a word of its
# own, so it looked like a subject and the ask after it leaned on it - "what should i check" was
# read with the budget's words in front of it and answered with the household budget card, when
# the person is still buying a car. A constraint is about the thing, so the line it leans on is
# the one the constraint was said about.
CONSTRAINT_FACT = re.compile(
    r"^\s*(?:my|our|the)\s+(?:budget|price|cost|age|salary|wage|wages|income|savings|time|"
    r"spending|tariff|allowance)\s+(?:is|was|'s)\b")


def _a_constraint_on_the_thing(line):
    """True for a constraint said as a fact about the thing in hand ("my budget is 5k")."""
    if not isinstance(line, dict):
        return False
    return CONSTRAINT_FACT.match(" ".join(line.get("norm") or ())) is not None


def _read_line(text, memory=None):
    """One reading of the user's line, before the second chance at the words in it."""
    memory = memory if isinstance(memory, dict) else {}
    # A figure of speech about being sick ("sick with worry") is read as the feeling it stands
    # for before anything reads the line, so the illness it is not does not reach the words, the
    # topic or the entries: "my son is sick with worry about school" was the unwell child's card.
    line = normalise(_the_sugar_that_is_blood(
        _the_part_that_hurts(without_the_figure_of_speech(text))))
    read = kinds.classify(line)
    # A thank-you with a line after it is that line. "thanks, my boss is a nightmare" was
    # answered "You're welcome - glad that helped" about a boss nobody had helped with, and
    # "thanks! the tap is still dripping" got the sign-off instead of the tap. What stays a
    # thank-you is a sign-off: "thanks, that worked", "thanks for the advice", "thanks love",
    # and a comment on the last answer ("thanks, that explains the boiler"). The line inside
    # has to be a line about something of its own, so the bar is the one a line's own topic
    # has to clear, and a thing thanked for ("thanks for the recipe") is not that line.
    if read["kind"] == "thanks":
        after = kinds.the_line_after_a_courtesy(line["norm"])
        if after and after[0] not in THANKED_FOR and _about_something_of_its_own(after):
            line = normalise(" ".join(after))
            read = kinds.classify(line)

    history = _user_lines(memory, LOOKBACK)
    previous_text = history[-1] if history else None
    previous = normalise(previous_text) if previous_text else None
    previous_entities = topics.detect_entities(previous) if previous else []
    previous_topic = None
    if previous:
        previous_topic, _ = topics.detect_topic(previous, None, previous_entities)
    # The line a follow-up leans on. The last line is the one it means, unless that line named
    # nothing itself ("and how long?", "she's 7"): then the subject is the nearest earlier line
    # that named one, exactly as a pronoun looks past a line that only leaned on the one before.
    carried_text, carried = previous_text, previous
    carried_is_older = False
    constraint_before = _a_constraint_on_the_thing(previous)
    if previous and (not previous_entities or constraint_before):
        # ...and unless that line is a subject of its own. A line can name no thing and still be
        # what the chat is now on: "i want to lose a stone" names nothing a sentence can be a
        # noun of, but it is a diet, and "how long will it take" after it is about the diet.
        # Walked back past it to the last line with a thing in it, that ask was answered from
        # the puppy two turns earlier ("we are getting a puppy" / "i want to lose a stone" /
        # "how long will it take" -> five minutes of walking for each month of age). Only a line
        # that leans on the one before it - "and how long", "and the vets" - is walked past, so
        # the carry stands when the two lines are on the same subject ("we are getting a puppy" /
        # "i love dogs" / "how long will it take").
        own_subject = None if constraint_before else topics.subject_topic(previous,
                                                                       previous_entities)
        earlier, earlier_entities = _pointed_at(history[:-1])
        if not earlier_entities and set(line["norm"]) & ANY_PRONOUN:
            earlier, earlier_entities = _the_recorded_subject(memory)
            carried_is_older = bool(earlier_entities)
        if earlier_entities and own_subject is not None and not constraint_before:
            earlier_subject = topics.subject_topic(earlier, earlier_entities)
            if earlier_subject is not None and earlier_subject != own_subject:
                earlier, earlier_entities = None, []
                carried_is_older = False
        if earlier_entities:
            previous_entities = earlier_entities
            carried_text, carried = earlier["text"], earlier
            if previous_topic is None:
                previous_topic = topics.detect_topic(earlier, None, earlier_entities)[0]

    ref = references.resolve(line, read, previous, previous_entities, previous_topic)
    entities = topics.detect_entities(line)
    # A line that names no subject of its own ("is that enough", "we have a 3 year old", "any
    # tricks") is talking about what the conversation is already about, so the topic carries
    # even when the line is not shaped like a follow-up.
    continues = ref["followup"] or topics.subject_topic(line, entities) is None
    inherited = None
    if continues and not _changes_subject(line):
        claimed = memory.get("topic")
        if isinstance(claimed, str) and claimed:
            inherited = claimed
        else:
            inherited = _recent_topic(history) or previous_topic

    # A line that names no subject of its own keeps the conversation's topic, so the topic the
    # line itself names is read separately (own_topic) before the place in it is weighed.
    # A verbless line that names a thing and a place asks what to pick there: "restaurants in
    # edinburgh". Read as a request, so a module answers it instead of acknowledging news.
    if (read["kind"] == "statement" and not read["asks"]
            and any(entity["type"] == "place" for entity in entities)
            and kinds.noun_phrase_request(line)):
        read["intent"] = "request"
        read["asks"] = ["recommend"]
        read["replies_to_bot"] = False
    # A line asks when it is a question, a request, or advice wanted; a place in a line that
    # asks what to do there is what the line is about ("museums in Rome").
    asks_something = read["kind"] == "question" or read["intent"] in ("request", "advice")
    own_topic, own_score = topics.detect_topic(line, None, entities, asks_something)

    topic, score = topics.detect_topic(line, inherited, entities, asks_something)
    # the topics of this line alone, best first: what a module that declares ANSWERS matches
    ranked = [name for name, points in topics.rank_topics(line, None, entities, asks_something)]
    # A question put to the bot itself names no subject of its own, so it read as naming nothing:
    # "do you have a name", "what model are u", "where are you", "can you make mistakes",
    # "should i call you anything".
    # (a line that says a question is coming names nothing yet, and its reading is that ask:
    # "can you help me with something" stays an opening, so it keeps its own intent and reply)
    # The bot's own day is read before the small-talk fallback: "how was your day" and "hbu" are
    # small talk, but what they are about is the bot, and reading them as "small-talk" first left
    # the two readings disagreeing ("how did your day go" was about-the-bot and "how was your
    # day" was not).
    if (topic is None and not kinds.opening_line(line["norm"])
            and _about_the_bot(line, read, entities)):
        topic = ABOUT_THE_BOT
        ranked = [ABOUT_THE_BOT] + [name for name in ranked if name != ABOUT_THE_BOT]
    elif topic is None and read["intent"] in ("greeting", "smalltalk"):
        topic = "small-talk"
    elif (topic is None and read.get("state_owner") == "self" and read.get("emotion")
          and not entities and read["intent"] not in ("question", "request")):
        # A line that is how they are and names nothing else is about how they are, the way
        # "im sad" is. A state read in other words - "my heart is broken", "im broken hearted",
        # "could be better" - read no topic at all, so a module that declares an area had
        # nothing to match on and the deck's feelings rows counted as unread. Only when the
        # state is the speaker's own, nothing is named (a heart is not a thing here, a bill or
        # a battery is) and the line asks for nothing.
        topic = "feelings"
        ranked = ["feelings"] + [name for name in ranked if name != "feelings"]
    # Rain and sunshine are small talk when they are said, and weather when they are asked
    # about: "it's freezing here" is chat, "will it rain tomorrow" wants an answer.
    if read["kind"] == "question" and topic == "small-talk" and OWN_QUESTION_TOPIC in ranked:
        topic = OWN_QUESTION_TOPIC
        ranked = [OWN_QUESTION_TOPIC] + [name for name in ranked if name != OWN_QUESTION_TOPIC]
    subject = next((entity["text"].lower() for entity in entities
                    if entity["type"] in ("title", "name", "person", "place", "thing")), None)
    # What in the line gave `topic` its score, strongest first: a phrase when a phrase is what
    # says which sense is meant (`hot dog`, `the date on the milk`), else the words it used.
    topic_from = topics.the_words_that_said(line, topic, entities)
    leans_on = _leans_on(line, read, ref, carried_text, carried, previous, own_topic,
                         previous_topic, previous_entities, carried_is_older)

    intent = read["intent"]
    # "can i ask you something", "i need some advice": the line says a question is coming and
    # names nothing yet, so there is nothing to answer - the reply is to invite them to go on.
    # A line that names a topic ("a question about my boiler", "advice about my mortgage") is
    # about that thing and keeps its own reading.
    if not ranked and intent in ("question", "request", "news", "statement", "ack") \
            and kinds.opening_line(line["norm"]):
        intent = "opening"
    # "what do you think", "what's your advice", "anything you'd suggest": the person is asking
    # the bot's view of something they have not said yet. With nothing named and nothing carried
    # from the last turn there is nothing to have a view about, and the search hedge ("I'd rather
    # not guess", "a search should sort you out") is the one reply that shuts the door - so this
    # is read as the opening it is, and the reply is to invite them to say.
    elif not entities and not leans_on and intent in ("question", "request") \
            and _opens_the_conversation(previous) \
            and not (previous_topic or previous_entities) \
            and asks_with_nothing_named(line["norm"]):
        intent = "opening"
    elif intent in ("question", "request", "news", "statement", "ack") \
            and kinds.talk_frame(line["norm"]):
        # The frame is the whole line, so nothing in it is a subject and any answer that matched
        # a word inside it ("run", "brain", "share") is about something the person never said.
        intent = "opening"
    presence = _presence(line) or _asks_for_a_moment(line)
    if presence and read["intent"] in PRESENCE_NOT:
        # A greeting on its own ("hey there") is a greeting, not a presence check; but a
        # greeting in front of one ("hiya, u about?") leaves the question being asked, so the
        # greeting only wins while the line has no word that addresses the bot.
        presence = (bool(set(line["norm"]) & (PRESENCE_SUBJECT | PRESENCE_ASKER))
                    or _asks_for_a_moment(line))
    if presence:
        intent = "presence"

    plain = _a_word_that_depends_on_the_owner(line["plain"], entities, read["state_owner"])

    # A breed is the animal it is: "my greyhound is not eating" names no dog, so the reading
    # carries the animal's own word beside the breed's and the dog entry that answers "my dog is
    # not eating" answers this too. See breeds.py.
    words = breeds.the_animal_a_breed_is(line["words"])
    # An animal the line only points at is read the same way: after "my cat milly is 12", "she's
    # been drinking a lot more water" names no animal, and the entry for a person's own drinking
    # water answered it. `clean` and `words` keep the line as typed - the word is the pronoun's,
    # not the line's - and a reader that needs the animal takes it from here. See references.py.
    animal_in_hand = references.the_animal_in_hand(ref, words)

    # Whether the line asks about something that changes, and what changes. Read once, here, and
    # again at the end for a short follow-up that only carries on the last question, which needs
    # the reading of this line to be complete (`followup`) and the last turn's reading beside it.
    over_time, over_time_what = kinds.over_time(line, read)
    last_read = memory.get("understood") if isinstance(memory, dict) else None

    out = {
        "text": text if isinstance(text, str) else "",
        "clean": line["clean"],
        "words": words,
        "plain": plain,
        # The animal this line only points at ("she's been drinking a lot more water" after a
        # cat): a word the line did not say, so anything counting the line's own words leaves it
        # out, and the knowledge lookup reads it into the words it matches on. See references.py.
        "animal_in_hand": animal_in_hand,
        # True when the line opened by saying it is changing the subject ("changing subject,
        # how do i stop my bin smelling") and that clause came off. The line is then about what
        # follows, not about what came before: a module that treats its bare words as a
        # follow-up on the last topic is reading the announcement as the subject.
        "change_of_subject": bool(line.get("change_of_subject")),
        "dropped_subject": line["dropped_subject"],
        # {"place", "time"} when the line says the thing has already been kept somewhere for a
        # length of time ("rice thats been in the fridge 3 days", "leftover rice after 3 days"),
        # else None. A keeping row reads it; a recipe, a date-on-the-pack or a warm-pot row
        # stands down on it.
        # A word that names two everyday things, and the sense the whole line supports
        # ("i have no room in my kitchen" is the space, "the hotel has no room for us" is the
        # bed). Only the words the line settles are here: "my bat is broken" says nothing either
        # way, so it reads nothing and a row that owns one sense stands aside rather than guess.
        # See bot/understanding/senses.py.
        "sense": senses.senses(line),
        # Whether the line asks about something that holds only for the day, and what: a price, a
        # surgery's opening hours, the weather, the news, what is in stock, a timetable, a
        # rate, or what is on. False for a fact that stands still - a count, a record, a definition, a
        # working, a history, a method, a conversion - and None where the line says neither.
        # Freshness words are not evidence either way: "latest" and "in the world" do not make
        # a question live, and the noun the question is about decides. See
        # bot/understanding/kinds.py (`changes`). A module that would state a figure as though it were
        # settled reads this first, and so does one that would hedge a settled fact.
        "over_time": over_time,
        "over_time_what": over_time_what,
        "kept": line.get("kept"),
        "kind": "question" if presence else read["kind"],
        "intent": intent,
        "presence": presence,
        "asks": read["asks"],
        # True when the line ends in a tag asking for agreement ("..., right", "..., innit").
        "tag": bool(read.get("tag")),
        # the activity the person is into, when they say it as an interest rather than a
        # question: "im into running" -> running, "ive got into yoga" -> yoga; see
        # kinds.taking_up. None for everything else, including "shes into running".
        "taking_up": kinds.taking_up(line, read),
        # The shift pattern the line names: "im on lates this week" is a week of hours, not a
        # period that is late. None on every other line, so "im late for work" keeps its reading.
        "shift": kinds.shift_worked(line["clean"]),
        # The person living in a care home a line is about ("my mum moved into a home last
        # month", "i feel guilty about not visiting my dad in the home"), with the shape the
        # line says it in: "guilt", "visiting", "moved" or "in". None on every other line, so
        # "im going home" and "i work from home" keep the readings they had. A present of a
        # guest in the speaker's flat, and a move into a new one, are different turns and both
        # of those rows stand down on it.
        # The line says it itself, or else the person is the one the conversation has already
        # placed in a home: "what should i bring her" is about that visit and nothing in the line
        # names it. The lookback is wider than the follow-up one above, because the line that
        # placed somebody in a home is often a few turns back.
        "care_home": (kinds.a_care_home(line["clean"])
                      or kinds.a_home_carried_forward(line["clean"],
                                                      _user_lines(memory, HOME_LOOKBACK))),
        "help_ask": read["help_ask"],
        "asks_a_verdict": read["asks_a_verdict"],
        "emotion": read["emotion"],
        "state_owner": read["state_owner"],
        # The thing the line says has run out, when it says one: "im low on milk" is a shortage
        # of milk and "ive run out of tea bags" of tea. A shortage is a fact about the cupboard,
        # not a low mood and not a state of the speaker, which is why it is its own reading.
        "shortage": read.get("shortage"),
        "polarity": read["polarity"],
        # The word the line used for how warm somebody is ("cold"), when that is what the word
        # is saying: "my mum is cold" is a mum who needs a jumper, and the same word is also the
        # illness. None when the line has the illness ("my mum has a cold", "full of cold"), the
        # weather or a thing ("the radiator is cold"), or a part of the body, which is
        # circulation ("my hands are cold"). A row that answers being cold reads it; the rows
        # that answer the illness stand aside on it. See topics.the_warmth_said.
        "warmth": topics.the_warmth_said(line["norm"]),
        # The part of the body the line says is unwell, when it is the speaker's own: "i have a
        # migraine" is a head, "my throat hurts" a throat, "i have a fever" a temperature. None
        # on every line that names no part, so a cold keeps the plain illness pool.
        "body": body.read(line["norm_text"]),
        # The word for what comes out of the person ("my poo", "i have not pooed"), when the
        # line makes it the person's own, or None. A row that shares the word with a thing - a
        # stool is a chair, green leaves keep a week - stands aside for it.
        "own_output": topics.own_output_word(line["norm"]),
        "short": read["short"],
        "first_person": read["first_person"],
        "about_bot": read["about_bot"],
        "about_bot_kind": read["about_bot_kind"],
        # A "how many" asked about the bot's own doings ("how many people have you talked to"):
        # there is no number to give, and it is a different reply from "what do you remember".
        "counts_the_bots_own_day": bool(read.get("counts_the_bots_own_day")),
        "replies_to_bot": read["replies_to_bot"],
        # True only for the agreement itself ("will give it a go"), not for every short reply
        # read as an ack ("ok", "will do"): a module can tell the two apart.
        "agrees_to_try": bool(read.get("agrees_to_try")) and intent == "ack",
        # True when the line asks for a question to answer ("quiz me", "give me a quiz
        # question"): the hand-over verb opens the line, or stands behind nothing but a modal or
        # a courtesy, so the person is the one asking. False for a question somebody else handed
        # over ("she gave me a question to answer"), which names the same words the other way
        # round. See kinds._hands_a_question_to_the_speaker.
        "wants_a_quiz": bool(read.get("wants_a_quiz")),
        # The idiom of agreement the whole line is ("tell me about it", "you and me both"), or
        # None: the person has just agreed with something, so the reply agrees back.
        "agreement": read.get("agreement"),
        # True when the line says the money has run out ("im skint till friday", "a bit short
        # this month"): a tight week, which wants a different reply from a question about money.
        "tight_on_money": topics.tight_on_money(line["norm"], read["kind"],
                                                line.get("text") or ""),
        # True when the line itself says what is left and when the money comes ("ive got 60 quid
        # till friday"). The tight-week reply must not ask "what's left" of a person who has just
        # said it, so the composer reads this to choose a line that does not.
        "amount_left": topics.purse_till_at(line["norm"], line.get("text") or "") is not None,
        # True when the line reports a routine the person keeps ("i walk the dog every day",
        # "we eat out twice a month"): the person is the one doing it, nothing is asked, and
        # nothing in the line is a fault or a feeling. A card is about the thing a line names,
        # and on a routine the thing is what they do it to, so a domain whose subject is that
        # thing stands aside for it (bot/knowledge/pets.py::STANDS_ASIDE) and the habit tail
        # says the routine back. See kinds.is_a_routine.
        "routine": kinds.is_a_routine(line, read),
        # True when the line says the person is the one holding it all up for everybody else
        # ("im always the one who organises everything", "everyone leans on me", "i never get a
        # minute to myself"). Not a mood and not loneliness: a job nobody shares. See
        # `a_load_carried` above.
        "a_load_carried": a_load_carried(line["clean"]),
        # Someone who can call them in wanting a word with them ("the council have written to
        # me", "my sons teacher wants a word"): {"who", "shape"} or None. See kinds.SUMMONS_WHO.
        "summons": read["summons"],
        # True when the line ends by asking the bot the same question it answers ("not bad, and
        # you?", "im fine thanks, yourself"): the reply has to say how the bot is and then get
        # back to the person. See kinds._asks_back.
        "asks_back": read["asks_back"],
        # The thing a line that only rules something out takes away, and the flag that says the
        # whole line is that limit ("no horror", "no treats", "without the garlic"). The composer
        # answers it inside the last answer instead of finding a new subject in the word.
        "excludes": read.get("excludes") or [],
        "constraint": bool(read.get("constraint")),
        # Advice somebody else gave the person ("my mate said i should try it", "i was told to
        # rest") as {"who": "Your mate", "source": "my mate"}, or None when the line is the
        # person's own plan or no plan at all. Nothing in the line has happened yet, so a reply
        # that asks how it went is about a day that has not been had: the composer answers the
        # plan, and names the person where the line named one. See kinds.A_REPORTED_VERB.
        "suggestion": read.get("suggestion"),
        # The words of a thing the line says it does not mean ("for a holiday not a house"). A
        # reader that answers the line skips them; every other module still sees the line whole.
        "ruled_out": read.get("ruled_out") or [],
        "norm": line["norm"],
        "norm_text": line["norm_text"],
        "fixes": line["fixes"],
        "clauses": line["clauses"],
        "focus": line["focus"],
        "signals": line["signals"],
        "topic": topic,
        "topic_score": score,
        "topics": ranked,
        "topic_own": own_topic,
        "topic_own_score": own_score,
        # What in the line gave `topic` its score, strongest first. A reader that wants to know
        # whether the line named an area or only brushed against one reads this, instead of
        # guessing from the topic name.
        "topic_from": topic_from,
        # True when that evidence is only ordinary words (weight 1 each), so the topic is the
        # shape of the sentence rather than its subject: `i need a new iron` reads shopping on
        # "need" and "new". A reader that needs the line to have named an area reads this before
        # answering from the topic; the reading itself is unchanged either way.
        "topic_is_a_brush": all(weight < 2 for _word, weight in topic_from),
        "entities": entities,
        "person_names": topics.person_names(line),
        # The words that only say WHEN or WHERE it happened ("it started at work in the garden
        # centre", "it started this morning when i was in the garden"): they are not what the
        # line is about, so a knowledge entry keyed on one of them must not answer it.
        "background": [line["norm"][index] for index in
                       sorted(background_positions(line["norm"]))],
        # "on earth" / "the hell" is never what the line is about, so it gets a key of its own
        # rather than sitting in `background`: a word there is only dropped when the line names
        # no subject of its own, and "what on earth is wrong with my boiler" names the boiler,
        # so "earth" survived and the layers of the planet answered it.
        "intensifier": list(line.get("intensifier") or []),
        # The half of the surprise the line still holds, which is what a knowledge lookup may
        # drop from its words: "the hell" is still in the line, "on earth" is not.
        "intensifier_left": list(line.get("intensifier_left") or []),
        "subject": subject,
        "numbers": topics.detect_numbers(line),
        "keywords": _keywords(line["norm"]),
        "ref": ref,
        "followup": ref["followup"],
        # True when the line is about a person the chat has not met yet ("should i text him
        # back" on the first turn, or after a line about a knee): somebody new, so a module
        # must not answer it by carrying on with the last line's subject. See
        # references.person_is_new.
        "someone_new": references.person_is_new(line, previous_entities),
        "leans_on": leans_on,
    }
    carrying_on = kinds.over_time(line, out, last_read, carrying_on=True)
    if carrying_on is not None:
        out["over_time"], out["over_time_what"] = carrying_on
    return out
