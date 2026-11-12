"""A "when ..." follow-up, answered from what the person already told us.

People ask about their own dates with the thing itself and no time in the ask: "when am I
moving?", "when's my exam?", "when is it?". The line that stated it is in the conversation, and
it carries the date, so the answer is the date alone rather than the whole plan again.

    i'm moving house in march            / when am i moving    -> In March.
    my exam is in june                   / when's my exam      -> In June.
    i have a dentist appointment on tuesday / when is it       -> On Tuesday.

The helper answers only when the ask and an earlier line are about the same thing: a word in the
ask has to be in that line (in any of its forms, so "moving" finds "move"), and the line has to
carry a date. When a line carries two dates - "i'm going to japan in march and i've got a
dentist appointment on tuesday" - the date that belongs to the thing asked is the one just after
it. Everything else is left to the modules that know about it.
"""
import datetime
import re

from .facts import (DAYS, DETERMINERS, FUTURE, MONTHS, a_date_put_right, a_moved_time,
                    the_date_put_right)
from .topics import content, forms

# A line that asks for the date of something. "when do I start?" is the plan's own verb and is
# answered before this; the shapes here are the ones that ask about a thing by name.
WHEN_ASK = re.compile(
    r"^\s*(?:and |so |but |oh |right |also |ok(?:ay)?[ ,]+)*"
    r"(?:when(?:'s|s| is| are| was| am| do| does| did| will| would)\b"
    r"|what (?:day|date)\b|which day\b)", re.I)

# "What day is it?" is the calendar, and the "it" in it is the day itself: the date on the last
# line is not the answer to it. A driving test "on the 14th" answered the bare ask with "On the
# 14th.", which is their own date read back at them as if it were today. The pointing word is
# what makes the ask about their own thing ("what day is it on", "what date is that"), and that
# ask is answered where the plan is kept (memory_store's DAY_IT branch).
BARE_CALENDAR_ASK = re.compile(
    r"^\W*(?:(?:and|so|but|oh|right|also|ok|okay)\b[\s,]*)?"
    r"what(?:'s|s| is| was)?\s+(?:the\s+)?(?:day|date)"
    r"(?:\s+(?:is\s+it|it\s+is|is\s+that|it|today|now|please|then|already|again))*\W*$", re.I)

# An ask about when the person *said* it ("when did i tell you about the exam?") is about the turn
# and not about the date in it: the date would read as the day they said it, which the chat never
# says. It is left to whoever can answer questions about the conversation.
WHEN_SAID = re.compile(r"\bwhen did (?:i|we|you)\b[^.?!]*\b(?:say|said|tell|told|mention|mentioned|"
                       r"ask|asked|bring|brought|talk|talks|talked|discuss|discussed|"
                       r"cover|covered)\b|\bwhen (?:was|were) it (?:i|we) (?:said|told)\b",
                       re.I)

WORD = re.compile(r"[a-z0-9']+")

# A question about the day now, not about a thing they told us: "what day is it", "what's the
# date today", "what date is it". The "it" is the weather's it - it names nothing they said -
# so there is no line here to answer from, and the calendar is answered where the calendar is
# read. Without this the plan was handed back as the day: "im going to rome in may" then "what
# day is it" said "In May.", which is a trip's date in place of today's. An ask that names
# something ("what day is my exam"), or points at the turn before ("what day is that"), is not
# this one and keeps its reading.
CALENDAR_NOW = re.compile(
    r"^\W*(?:(?:and|so|but|ok|okay|right|oh|also|hi|hey|quick|sorry|excuse me)\W+)*"
    r"what(?:'s|s| is| are| was)?\s+(?:the\s+)?(?:day|date)"
    r"(?:[\s,]*(?:is it|it is|today|now|tonight|tomorrow|this (?:week|morning|evening)|"
    r"right now))*\s*$", re.I)

# Words an ask picks up that say nothing about which line it means, or that ask where in the
# line the answer is and not which line: "when is my sister *due*" is about the sister.
ASK_THROWS = frozenset("""exactly again then just roughly about long before after tonight due
start starts starting end ends ending say said tell told know""".split())

# A date said the short way: "i booked a trip to rome for april", "the wedding is september". The
# store's own future-date reader wants a preposition it knows ("in april", "next month"), and a
# "for" or a bare month is the same date. Read here, where the date is only ever used to answer a
# when ask about a line they already said, so nothing else in the bot changes.
# A number is a date on its own only when no month follows it: "on 3 may" is the third of May,
# and a reader that stops at the number answers "On 3.", which is not a date anybody says. The
# month after it is read with "of" too, because a day kept in the store is written that way:
# "on the 12th of July" answered "On the 12th." and left the month out.
MONTH_NAMES = "|".join(sorted(MONTHS, key=len, reverse=True))
SHORT_DATE = re.compile(
    r"\b(?:for|in|on|by|until|till|around|from)\s+(?:the\s+)?"
    r"(?:(?:early|mid|late)\s+)?"
    r"(?:" + MONTH_NAMES + r"|"
    + "|".join(sorted(DAYS, key=len, reverse=True)) + r"|"
    # A bare number after one of those words is a day of the month, and no month has a 32nd, so
    # the number has to be a day for the word before it to be a date. "im putting by 60 a month"
    # was a deadline ("by 60"): the saving line became a dated plan, and the follow-up "how many
    # months until i have 1000" counted down to it - "That's about 7 weeks away - Thursday 31
    # December", a confident date for a question about a sum of money. A rate is not a deadline.
    r"(?:0?[1-9]|[12]\d|3[01])(?:st|nd|rd|th)?(?:\s+(?:of\s+)?(?:" + MONTH_NAMES + r"))?)\b"
    r"|\b(?:is|was|it's|its)\s+(?:in\s+|on\s+)?"
    r"(?:" + "|".join(sorted(MONTHS, key=len, reverse=True)) + r")", re.I)

# A date already behind the person: "last september", "back in april", "last winter", "last year".
# The reader knew "in april" and "next april" but nothing said with "last", so "i moved house last
# september" filed no date at all and "when did i move" answered "No date from you on that one.
# When is it?" - one turn after the person had said when. A season and "last year" are the same
# kind of date, said the same way.
PAST_WHEN = re.compile(
    r"\b(?:last|back in|this past)\s+(?:(?:early|mid|late)\s+)?"
    r"(?:" + MONTH_NAMES + r"|spring|summer|autumn|winter|year)\b", re.I)

# A trip is asked about by the word for the trip, not by the place it goes to: "when is my
# holiday" after "i'm going to spain in july" is the line that carries a place and a travel verb.
# The words name nothing the line has to match, so they are dropped before matching, and the
# answer is only given when that line really is a trip.
TRIP_WORDS = frozenset("""holiday holidays trip break vacation getaway going go flying fly travel
travelling traveling leaving leave away""".split())
# A line about a journey is not always said with a travel verb: "i booked the tickets for june",
# "we've got the ferry booked for august", "i got the train tickets for june" are the same trip
# said through what was booked, and "when am i going" is answered by them. Without the booking
# words those lines had no travel word in them, so the ask found no trip to answer from and fell
# through to the search hedge while "when do we go" (whose ask names nothing at all) answered from
# the same line.
TRIP_LINE = re.compile(r"\b(?:go|going|goes|went|fly|flying|flies|flew|travel\w*|leave|leaving|"
                       r"left|trip|holiday|break|vacation|getaway|visiting|visit|abroad)\b", re.I)
# What a journey is booked as. Tickets, a flight and a ferry are part of a journey and nothing
# else, so the word alone is the trip. A train, a coach, a seat and a room are every day too - a
# coach at work, a train of thought, a seat in the window - and a book is only an object, so
# these count as a journey only where the line also says something was booked. Without the
# booking verb "i ordered a book on monday" became a trip and "when am i going" answered "On
# Monday." out of a parcel.
TRIP_BOOKED = re.compile(r"\b(?:tickets?|flights?|ferry|plane|abroad|"
                         r"check(?:ed)?\s*-?\s?in|boarding)\b", re.I)
BOOKING = re.compile(r"\b(?:book(?:ed|ing)|reserv\w*)\b", re.I)
TRIP_BOOKED_ONLY_WITH_A_BOOKING = re.compile(r"\b(?:trains?|coach|coaches|seat|seats|hotel|"
                                             r"room|rooms|table)\b", re.I)


def _is_a_trip_line(said):
    """True when this line is about a journey, whether said by its verb or by what was booked."""
    if TRIP_LINE.search(said) or TRIP_BOOKED.search(said):
        return True
    return bool(TRIP_BOOKED_ONLY_WITH_A_BOOKING.search(said) and BOOKING.search(said))


# An ask can point back at the line instead of naming it: "when is the best time to prep for
# it", "when is a good time to get there". The back-reference is the last word, and what it
# points at was just said - so the newest dated line answers it, as long as that line is still
# one of the last few turns. A date from long ago is a different thing by then, and the ask is
# left to whoever else can answer it.
POINTS_BACK = frozenset("""it that this them there then him her those these""".split())
BACK_TURNS = 3

# People name an event by its noun and tell you about it with its verb: "my sister is getting
# married in june", then "when is the wedding?". The ask and the line then have no word in
# common, so the date was never given back and the ask went to a hedge. Each name is matched
# only against the words that state that same event, so a party is still not a wedding, and it
# still needs a date in the line: "when is the baby due" after "my wife is pregnant" has nothing
# to answer with, and falls through to whoever knows about babies.
EVENT_NAME = {
    # An engagement is not the wedding, so its date is not given for a wedding ask.
    "wedding": ("married", "marry", "wedding"),
    "birthday": ("birthday", "born", "turns"),
    "operation": ("operation", "surgery"),
}


def _names_that_event(word, other):
    """True when the line states, with `other`, the event the ask named with `word`."""
    for name, says in EVENT_NAME.items():
        if _same(word, name) and any(_same(one, other) for one in says):
            return True
    return False

# A date on a death is not a date to say back. "my dad died in march" then "when was that" is a
# person going over a loss, and answering "In March." hands them a calendar instead of the
# sympathy the line before it got. The words are the ones a bereavement is said with, so a
# birthday, a funeral plan or a date in a story is left alone only when it is one of these.
NOT_A_DATE_TO_GIVE = re.compile(
    r"\b(?:died|dies|dying|dead|death|killed|passed\s+away|passed\s+on|funeral|burial|"
    r"buried|cremation|cremated|put\s+to\s+sleep|euthanis\w*|widow|widowed)\b", re.I)
# The same words, pointed at the person themselves. "im going to kill myself in october" then
# "how long till that" is not a countdown, and answering it with a number is the worst thing
# this bot could do: a date someone sets for their own death is a crisis, not a plan. The other
# reader in this file already knows a death is not a date to say back; it only had the words for
# somebody else's.
THEIR_OWN_DEATH = re.compile(
    r"\b(?:kill\s+myself|killing\s+myself|kill\s+me(?!\s+a)|suicide|suicidal|end\s+my\s+(?:own\s+)?"
    r"life|take\s+my\s+(?:own\s+)?life|hang\s+myself|hang\s+myself|overdose|cut\s+myself|"
    # A wish said in a contraction is still a wish: `dont want to`, `didnt want to`, `do not want to`.
    # And `carry on` is the same wish as `be here`: "i dont want to carry on in december" was read
    # as an ordinary date and counted down to.
    r"done\s+with\s+living|better\s+off\s+dead|"
    r"(?:(?:do(?:es)?|did)\s+not|don'?t|dont|didn'?t)\s+want\s+to\s+"
    r"(?:be\s+here|live|carry\s+on|go\s+on)"
    r"(?=\s*(?:$|[.,!?;:]|and\b|any\s?more|anymore|at\s+all|like\s+this|like\s+that|"
    r"for\s+good|for\s+much\s+longer|much\s+longer|any\s+longer|tonight|today|"
    r"this\s+(?:week|month|year|time)|"
    r"(?:in|by|at|before|until|till|after)\s+(?:\d{4}|jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)))|"
    r"want\s+to\s+die|going\s+to\s+die|"
    # A wish that names no time at all, which the fence above would otherwise let past: "i do not
    # want to live forever" and "i do not want to live in this world" are the same words the arm
    # caught before it was fenced, and `forever` is not a date clause.
    r"(?:do(?:es)?\s+not|did\s+not|don'?t|dont|didn'?t)\s+want\s+to\s+(?:live|be\s+here)\s+"
    r"(?:forever|for\s+ever|in\s+this\s+world|on\s+this\s+earth))\b", re.I)


# A thing the person has told us about and never put a date on: "we are having a baby" then "when
# is it due", "im starting a new job" then "when do i start". There is no date in the conversation
# to give back, so the search hedge answered a parent-to-be with "a quick search online will get
# you a solid answer". What the store does have is the thing itself, so the reply says there is no
# date from them yet and hands the question back, which is what a friend does.
NO_DATE_YET = (
    "You haven't told me when — when is it?",
    "No date from you on that one. When is it?",
    "I don't have a date from you for that. When is it?",
)
# A question about the world, not about their own plan: "when should i start looking for a job"
# names the same words as the job they start on Monday, and it wants advice, not a date.
NOT_A_DATE_ASK = re.compile(r"\b(?:should|ought|best|better|good|safe|easiest|cheapest|likely|"
                            r"worth|advice|tips?|look\w*|search\w*|appl\w*|think\w*|tr(?:y|ying)|"
                            r"plan\w*)\b", re.I)
# The things that go in a diary and take a date. A goal ("i want to lose a stone") is the same
# shape as "im starting a new job" and is not one of them: "when do i start" after a goal asks for
# advice about when to begin, and the answer to that is not "you haven't told me when".
EVENT_WORD = re.compile(
    r"\b(?:baby|babies|pregnan\w*|birth|scan|job|work|wedding|marri\w*|wed|move|moving|moved|"
    r"flat|house|trip|holiday|honeymoon|exam|exams|test|appointment|interview|operation|surgery|"
    r"course|term|flight|ferry|train|placement|retire\w*|start\w*|begin\w*|due|deadline|"
    r"due\s+date|results?|course)\b", re.I)
WANT_LINE = re.compile(r"\b(?:want|wanna|wanted|would\s+like|hope|hoping|trying|try|thinking\s+of|"
                       r"dream\w*|plan\s+to)\b", re.I)
# An ask about the plan's own verb: "when do i start" after "im starting a new job", "when's it
# due" after "we are having a baby". The verb is the thing itself, so the ask names nothing that
# can be matched against a line, and the line it is about is the newest one they said.
PLAN_VERB_ASK = re.compile(
    r"^\W*(?:(?:and|so|but|ok|okay|right)\W+)*when(?:'s|s)?\s+(?:do|does|did|will|would|is|are|"
    r"was|were|am)\s+(?:i|we|it|that|this|they|he|she)\s+"
    r"(?:start|starts|begin|begins|finish|end|ends|go|going|leave|leaving|due|happen\w*|arrive\w*|"
    r"back|home|on)\b", re.I)


def asks_what_today_is(text):
    """"What day is it", "what's the date", "what date is it today": the calendar now.

    A question about today, not about anything the chat is on. The store reads an ask that names
    a fact and leaves the value out as one about the thing being talked about, which is right for
    "and my job?" and wrong here: in a chat about a new job the dress code for a first day
    answered "what day is it", and in a chat about a bad week a sympathy line did. The date is
    the answer, and the calendar is read where the calendar is read.
    """
    line = " ".join(str(text or "").split()).rstrip("?!. ")
    return bool(CALENDAR_NOW.match(line))


def when_answer(text, memory):
    """The date of the thing the line asks about, or None when no earlier line says it."""
    line = str(text or "")
    if CALENDAR_NOW.match(line):
        return None  # "what day is it" asks about today, and today is not one of their lines
    if not WHEN_ASK.search(line) or WHEN_SAID.search(line):
        return None
    if BARE_CALENDAR_ASK.match(" ".join(line.split())):
        return None  # "what day is it" asks the calendar: see BARE_CALENDAR_ASK
    words = [word for word in content(line) if word not in ASK_THROWS]
    if NOT_A_DATE_TO_GIVE.search(line):
        return None  # a date asked for over a death is not the thing they want said back
    if words and _points_back(line):
        # "when is the best time to prep for it" names the asking ("best time", "prep") and
        # nothing of the thing, so no word has to match: the newest dated line is the thing.
        dated = _dated(memory)
        if dated and a_date_put_right(dated[0][0]) and _said_in_the_last_few_turns(memory, dated[0][0]):
            # A day put right under a line that gave the month is both halves of one date:
            # "my holiday is in july" / "actually it's the 12th" / "when do i go" is the 12th
            # of July, and the day alone would drop the month they already told us.
            joined = _a_day_and_a_month(dated[0][1][-1][0], dated[1][1][-1][0]) if len(dated) > 1 else ""
            if joined:
                return _sentence(joined)
        for said, spans in dated[:1]:
            if _said_in_the_last_few_turns(memory, said):
                return _sentence(spans[-1][0])
        return None
    asked = [word for word in words if word not in TRIP_WORDS]
    trip = asked != words
    # A date put right sits directly above the line it corrects, so it is held for that line only:
    # "my test is on the 3rd of may" / "sorry, it's the 4th" / "when is my test" is the 4th, and
    # the correction is dropped again once a line under it turns out not to be the one asked
    # about, because the date it names belongs to the thing above it and nothing else. A day put
    # right under a month is both halves of one date, which is what `_a_day_and_a_month` joins.
    put_right = ""
    for said, spans in _dated(memory):
        if NOT_A_DATE_TO_GIVE.search(said):
            continue  # a date in the line about a death is not an answer to give back
        # The put-right line is read before the trip filter, because it never says the thing it
        # is about: "i'm going to spain in june" / "sorry, it's the 4th" / "when do we fly" is
        # the day of that trip, and a filter that wants a travel word in every line drops the
        # only line that carries the day.
        if a_date_put_right(said):
            # The lines come newest first, so a second day put right in a row is the one they are
            # going with: "sorry saturday i got the day wrong" / "actually its sunday now" is
            # Sunday, and the older correction is only the line the newest one replaced. Only the
            # newest is kept, so a chat with one correction reads exactly as it did.
            put_right = put_right or spans[-1][0]
            continue
        if trip and not _is_a_trip_line(said):
            continue
        when = _time_for(asked, said, spans)
        if when:
            said_date = _a_day_and_a_month(put_right, when) or put_right or when
            # The same words are a diary and a memory, and only the verb says which: "i went to
            # rome in june" then "when am i going" said "In June.", which reads as a trip still
            # to come. A date that has happened is said back as one.
            if _has_happened(said) and not AN_ASK_IN_THE_PAST.search(line):
                return _was_sentence(said_date)
            return _sentence(said_date)
        # A date said with no subject of its own is about the thing named a line or two above:
        # "weve got my in laws coming for dinner" / "its going to be on friday" / "when is the
        # dinner" is Friday, and read line by line this line dates nothing the ask names.
        if asked and not _names_a_thing(said, spans):
            above = _the_thing_before_the_date(memory, said, asked)
            if above:
                return _sentence(_a_day_and_a_month(put_right, spans[-1][0])
                                 or put_right or spans[-1][0])
        put_right = ""
    return _no_date_yet(asked, line, memory)


ASK_OPENER = re.compile(
    r"^\W*(?:do|does|did|can|could|should|would|will|shall|is|are|was|were|have|has|had|am|"
    r"how|what|when|where|who|which|why|any|anyone)\b", re.I)


def _is_an_ask(line):
    """True when the line is a question, not a statement of what they are doing."""
    text = str(line or "").strip()
    if not text:
        return False
    return text.endswith("?") or bool(ASK_OPENER.search(text))


def _backs_off(line):
    """True when the ask ends on a word that points at something already said.

    The same test as `_points_back` with the words that ask where in the line the answer is
    ("due", "exactly", "again") taken off first: "when is it due" points back through the "due".
    """
    tokens = re.findall(r"[a-z']+", str(line or "").lower())
    while tokens and tokens[-1] in ASK_THROWS:
        tokens.pop()
    return bool(tokens) and tokens[-1] in POINTS_BACK


def _no_date_yet(asked, line, memory):
    """The reply for a thing they have told us about but never dated, or None.

    Only when the newest line the ask is about carries no date at all: a line with a date in it is
    the other readers' business, and saying "you haven't told me when" over a date they did give
    would be worse than the hedge.
    """
    if not isinstance(memory, dict) or NOT_A_DATE_ASK.search(line):
        return None
    turns = [" ".join(str(turn.get("user") or "").split())
             for turn in (memory.get("turns") or []) if isinstance(turn, dict)]
    plans = [str(p) for p in ((memory.get("user") or {}).get("plans") or []) if isinstance(p, str)]
    latest = (memory.get("user") or {}).get("plan")
    if isinstance(latest, str):
        plans.append(latest)
    recent = [said for said in turns if said][-BACK_TURNS:]
    for said in recent + list(reversed(plans)):
        if not said or NOT_A_DATE_TO_GIVE.search(said):
            continue
        # A question they asked is not a plan they told us: "do i get bank holidays off" then
        # "when is the next bank holiday" shares the word "holiday", and the store answered a
        # question about the calendar with "no date from you on that one".
        if _is_an_ask(said):
            continue
        if list(FUTURE.finditer(said)) or list(SHORT_DATE.finditer(said)):
            return None  # that line is dated; the date was not read, so leave the turn alone
        if asked:
            theirs = [word for word in content(said) if word not in ASK_THROWS]
            if not any(_same(word, other) for word in asked for other in theirs):
                continue
        else:
            # The verb on its own ("when do i start") names nothing that can be matched, so the
            # line has to be an event they put in their diary: after "i want to lose a stone" the
            # same ask means "when should I begin", which the answers lane already answers well.
            if not (_backs_off(line) or PLAN_VERB_ASK.search(line)):
                return None
            if not EVENT_WORD.search(said) or WANT_LINE.search(said):
                continue
        return NO_DATE_YET[len(turns) % len(NO_DATE_YET)]
    return None


def _a_day_and_a_month(day, month):
    """The two halves of one date joined: "on the 4th" put right under "in june".

    A day put right says the day and nothing else, so the month has to come from the line it
    corrects: "i'm going to spain in june" / "sorry, it's the 4th" / "when do we fly" is
    "On the 4th of june.", not "On the 4th." (no month) or "In June." (the month they took
    back). Returns "" unless one half is a day and the other a month.
    """
    the_day = re.search(r"\b\d{1,2}(?:st|nd|rd|th)\b", str(day or ""))
    a_month = next((word for word in re.findall(r"[A-Za-z]+", str(month or ""))
                    if word.lower() in MONTHS), "")
    if not (the_day and a_month):
        return ""
    return "on the %s of %s" % (the_day.group(0), a_month.lower())


def _points_back(line):
    """True when the ask ends on a word that points at something already said.

    "when is the best time to prep for it" is about the thing "it" names; "when is the best
    time to take a mortgage" ends on a thing of its own and is a question about the world.
    """
    tokens = re.findall(r"[a-z']+", str(line or "").lower())
    return bool(tokens) and tokens[-1] in POINTS_BACK


def the_plan(memory):
    """The newest plan the store keeps, in the person's own words, or None.

    The store rewrites this line when the plan is corrected, so "i'm going to lisbon in may"
    followed by "sorry, june" leaves *this* as "Lisbon in June". Anything that reads a time out
    of the conversation should read it from here before it reads the older turns, or a value the
    person has already taken back goes on being used.
    """
    known = (memory.get("user") or {}) if isinstance(memory, dict) else {}
    if not isinstance(known, dict):
        return None
    plan = known.get("plan")
    if isinstance(plan, str) and plan.strip():
        return " ".join(plan.split())
    plans = [p for p in (known.get("plans") or []) if isinstance(p, str) and p.strip()]
    return " ".join(plans[-1].split()) if plans else None


def _said_in_the_last_few_turns(memory, said):
    """True when that line is still one of the last few things the person typed."""
    turns = [" ".join(str(turn.get("user") or "").split())
             for turn in (memory.get("turns") or []) if isinstance(turn, dict)]
    key = " ".join(str(said or "").split())
    return key in turns[-BACK_TURNS:]


def _names_a_thing(text, spans):
    """True when the line names something other than the date it carries.

    "my test is on the 3rd of may" names a test; "its going to be on friday" names nothing but
    the day, so the date in it belongs to whatever the line before it is about. The date itself
    is taken out before the words are counted, and the little words that only carry a date along
    ("going", "sorry", "wrong") are not things.
    """
    said = str(text or "")
    for when, _start in sorted(spans, key=lambda span: -span[1]):
        said = said.replace(when, " ", 1)
    left = [word for word in content(said) if word not in NOT_A_THING]
    return bool(left)


# The words a line has left over when it was only there to carry a date: "its going to be on
# friday" is about nothing but the Friday, so an ask naming the dinner is not answered from it.
NOT_A_THING = frozenset("""
about actually also because been before day days going coming sorry wrong now still yet again
think thought said say told tell really surely maybe right okay ok well thanks thank got get
have has had was were is are be been being turn turns
""".split())


def _the_thing_before_the_date(memory, said, asked):
    """The earlier line the ask is about, when the date was said with no subject of its own.

    "weve got my in laws coming for dinner" / "its going to be on friday" / "when is the
    dinner" is Friday: the second line says the date with an "it" and names nothing, so read on
    its own the date has nothing to belong to and the ask was answered "you haven't told me
    when". The thing is the nearest line above that the ask's own words match, within the last
    few turns, so a date from long ago is still a different thing.

    A date said with a subject of its own is not bridged: "my test is on the 3rd of may" is the
    test's date, and an ask about the boiler is not answered with it.
    """
    turns = [" ".join(str(turn.get("user") or "").split())
             for turn in (memory.get("turns") or []) if isinstance(turn, dict)]
    key = " ".join(str(said or "").split())
    if key in turns:
        cut = len(turns) - 1 - turns[::-1].index(key)
    else:
        cut = len(turns)
    for line in reversed(turns[max(0, cut - BACK_TURNS * 2):cut]):
        if not line or line == key:
            continue
        spans = [found.group(0) for found in FUTURE.finditer(line)]
        spans += [found.group(0) for found in SHORT_DATE.finditer(line)]
        if a_date_put_right(line):
            continue
        if not _names_a_thing(line, [(span, 0) for span in spans]):
            continue
        if spans:
            # A dated thing of its own in between: "the dentist is on tuesday" / "weve got people
            # coming for dinner" / "its going to be on friday" / "when is the dentist" is not
            # Friday. The bridge only carries a date over the lines that name nothing.
            break
        if any(_same(word, found) for word in asked for found in WORD.findall(line)):
            return line
    return ""


# The line a correction was made to, as the store keeps it for the topic, with the value they
# meant beside it: "my parents are coming for dinner on saturday (mean Sunday)".
THE_MEAN_NOTE = re.compile(r"\s*\(\s*(?:i\s+|sorry,?\s+i\s+)?mean\s+([^)]*)\)\s*$", re.I)
# The words a date is joined to the thing it belongs to, which stay on the line when the date
# itself is what moves: "on saturday" put right is "on sunday", not "dinner sunday".
JOINED_TO_A_DATE = re.compile(
    r"(?i)\s*(?:(?:for|is|was|it's|its|'s|in|on|at|by|next|this|last)\s+)*")


def _the_line_put_right(memory):
    """The topic's line with the value they meant in place of the date they took back.

    The store writes the correction onto the topic as a note after the line ("... on saturday
    (mean Sunday)") and files the corrected plan beside it. The note is what says which date is
    in force once the turn of the correction has gone by: without it the newest line they typed
    still carries the old date, and a later ask about the day is answered with the date they had
    already put right. Returns the line they meant and the date it replaced, or ("", "").
    """
    record = (memory or {}).get("topic") if isinstance(memory, dict) else None
    text = " ".join(str(record.get("text") or "").split()) if isinstance(record, dict) else ""
    note = THE_MEAN_NOTE.search(text)
    if not note:
        return "", ""
    meant = " ".join(note.group(1).split()).strip(" .,")
    line = text[:note.start()].strip(" ,;")
    if not line or not meant:
        return "", ""
    if not a_moved_time(meant):
        # A value put right that is no kind of time ("my budget is 400 (mean 800)") says nothing
        # about a date, and swapping it in would drop the date the line does name.
        return "", ""
    spans = list(FUTURE.finditer(line)) + list(SHORT_DATE.finditer(line))
    if not spans:
        return "", ""
    # The note comes after the whole line and the date they put right is the one nearest it, so
    # the last date on the line is the one the value they meant goes in place of. Two of the
    # readers find the same date with different words in front of it ("is july 12th", "is july"),
    # and the longer one is the date: the short one stops before the day of the month.
    last = max(spans, key=lambda found: (found.start(), len(found.group(0))))
    joined = JOINED_TO_A_DATE.match(last.group(0)).group(0)
    swapped = line[:last.start()] + joined + meant + line[last.end():]
    # The date they took back is the date itself, with no joining word on it, which is how the
    # other lines are checked for it ("on saturday" is the "saturday" they took back).
    old = JOINED_TO_A_DATE.sub("", last.group(0), count=1)
    return " ".join(swapped.split()), _plain(old)


def _dated(memory):
    """Every earlier line that carries a date, with its dates: newest first.

    The plans are the dated lines the store keeps as plans, and the turns are every line the
    person typed, so "the wedding is in september" answers a "when" ask even though the store
    keeps no plan for it."""
    out, seen = [], set()
    known = (memory.get("user") or {}) if isinstance(memory, dict) else {}
    plans = [p for p in (known.get("plans") or []) if isinstance(p, str)]
    latest = known.get("plan")
    if isinstance(latest, str) and latest not in plans:
        plans.append(latest)
    typed = [str(turn.get("user") or "") for turn in reversed(memory.get("turns") or [])
             if isinstance(turn, dict)]
    lines = typed
    # A date the person put right is the date: "i'm going to spain in june" / "sorry july" then
    # a turn or two of something else still answers "when do we fly" with July. The corrected
    # line stands where the newest one does, and the date it replaced is dropped from the lines
    # that still say it, so a line with two dates in it keeps the one that was not corrected. Not
    # from the corrected line itself, which says the new date and would lose it as the old one:
    # "my holiday is in july" / "actually it's the 12th" leaves "holiday on the 12th of July",
    # and dropping "july" from that answers "On the 12th." with the month thrown away.
    fixed_sentence, replaced = _put_right(memory)
    if not fixed_sentence:
        # The correction is the news of one turn, and the turn after it the store keeps the line
        # it was made to with the value they meant beside it in the topic. Reading the turns alone
        # answered "when are they coming" with the day they had already taken back.
        fixed_sentence, replaced = _the_line_put_right(memory)
    if fixed_sentence:
        lines = [fixed_sentence] + lines
    theirs = {" ".join(line.split()).lower() for line in typed}
    for said in lines + list(reversed(plans)):
        said = " ".join(said.split())
        key = said.lower()
        if not said or key in seen:
            continue
        spans, places = [], set()
        for found in FUTURE.finditer(said):
            spans.append((_lead(_with_the_month_after(said, found)), found.start()))
            places.add(found.start())
        for found in SHORT_DATE.finditer(said):
            if found.start() in places:
                continue
            spans.append((_lead(found.group(0)), found.start()))
            places.add(found.start())
        for found in PAST_WHEN.finditer(said):
            if found.start() in places:
                continue
            spans.append((_lead(found.group(0)), found.start()))
            places.add(found.start())
        if not spans and a_date_put_right(said):
            # "sorry, it's the 4th" carries a date and nothing else: it is the date put right,
            # and the space it stands in is where the line it corrects was.
            spans.append((_a_date_said(the_date_put_right(said)), 0))
        spans.sort(key=lambda span: span[1])
        # Only a line they typed loses the date they took back: the store's own plan and the
        # corrected sentence hold the new date, and "July" there is not the "July" replaced.
        if replaced and key in theirs:
            spans = [span for span in spans if replaced not in _plain(span[0]).split()]
        if not spans:
            continue
        seen.add(key)
        out.append((said, spans))
    return out


LEAD = ("for", "is", "was", "it's", "its", "'s")


def _lead(found):
    """A date given with the word that joins it to the thing it belongs to.

    "the wedding *is* september" is September, and "i booked a trip *for* april" is April: the
    joining word says what the date is for, not that it is a deadline. The date is said back with
    the preposition a date takes ("in july", "on tuesday") so that a copula is never the answer:
    "my dentist appointment is tuesday" / "when is it" is "On Tuesday.", not "Is Tuesday."
    """
    text = " ".join(str(found).split()).strip(" ,;.")
    words = text.split()
    if len(words) > 1 and words[0].lower() in LEAD:
        rest = " ".join(words[1:])
        if rest.lower().startswith(("in ", "on ", "at ", "by ", "next ", "this ", "last ")):
            return rest
        first = re.split(r"[\s,]", rest)[0].lower()
        if first in MONTHS or first in ("early", "mid", "late"):
            return "in " + rest
        return "on " + rest
    return text


def _time_for(asked, said, spans):
    """The date in that line that belongs to the thing asked about."""
    if not asked:
        # "when is it?" names nothing of its own, so it means the thing just said: the last date
        # in the newest dated line. "i'm going to japan in march and i've got a dentist
        # appointment on tuesday / when is that again" is the appointment, not Japan.
        return spans[-1][0]
    hits, seen = [], set()
    for found in WORD.finditer(said):
        for word in asked:
            if word not in seen and (_same(word, found.group(0))
                                     or _names_that_event(word, found.group(0))):
                seen.add(word)
                hits.append(found.start())
    # The line has to be about what the ask names, not just share one word with it: "when
    # should I start looking for a job?" is not answered by the job that starts on Monday.
    if len(seen) < len(asked) and (len(asked) < 3 or len(seen) < len(asked) - 1):
        return None
    best = None
    for when, start in spans:
        # The date that follows the thing it belongs to, and the nearest one: "dentist
        # appointment" two words before "on tuesday" is Tuesday, not the March before it.
        after = [start - hit for hit in hits if start >= hit]
        score = (min(after), 0) if after else (min(abs(start - hit) for hit in hits), 1)
        if best is None or score < best[0]:
            best = (score, when)
    return best[1]


# A day number followed by the month it is in: "is the 3rd of june", "on the 21st june". The date
# readers stop at the number, so a countdown to "the 3rd of june" was counted to the third of the
# month in play and said December. The month is said after the day in half the chats that give one,
# so it is read with the day rather than left to whichever month the chat had touched last.
MONTH_AFTER_THE_DAY = re.compile(
    r"^\s+(?:of\s+)?(?:" + "|".join(sorted(MONTHS, key=len, reverse=True)) + r")\b", re.I)
# The words that make what follows them a thing of its own: "my food", "the boiler", "a parcel".
# A countdown that names one is about that thing, whether or not the chat dated it.
A_THING_NAMED = re.compile(r"\b(?:my|our|your|his|her|their|the|this|that|these|those|a|an)\s+"
                           r"([a-z][a-z'-]{1,19})", re.I)


def _with_the_month_after(said, found):
    """The date text, plus the month said right after a bare day number."""
    text = found.group(0)
    if not re.search(r"\d{1,2}(?:st|nd|rd|th)$", text.strip()):
        return text
    after = MONTH_AFTER_THE_DAY.match(said[found.end():] or "")
    if not after:
        return text
    return text + after.group(0)


def _names_a_thing_of_its_own(line, said):
    """Whether a countdown ask names a thing the dated line is not about.

    "i have an exam in june" / "how long until my food arrives" is a question about the food - the
    date in the chat is not what is being counted to, and the answer said "about 7 months away -
    sometime in June" to somebody waiting on a delivery. Same for "how long until the boiler is
    fixed" after a scan date. The thing is a noun behind a determiner ("my food", "the boiler"),
    and it is this line's own subject unless the dated line says that word too, which is what keeps
    "how long have i got to revise" (a bare verb, no thing) and "how long until my exam" (the exam
    is the dated line) answered as before.

    A thing needs no determiner to be its own: "how many weeks till christmas" and "how many days
    till payday" were counted to a holiday in June, 204 days to a payday that was never in the
    chat. "Till" and "until" are followed by the event itself, so a countdown that uses one and
    whose words the dated line does not hold is about that event. The other countdown leads are
    not: "have i got to revise" and "to go" say what the time is for, and they keep the date.
    """
    found = UNTIL_COUNTDOWN.search(line)
    if not found:
        return False
    body = line[found.end():]
    if _POINTS_AT_IT.search(body):
        return False  # "till it goes off", "until that happens": the thing is the one just said
    dated = set(WORD.findall(str(said or "").lower()))
    if (found.group(1) or "").lower() in UNTIL_NAMES_THE_EVENT:
        words = WORD.findall(body.lower())
        for index, word in enumerate(words):
            if word in UNTIL_THROWS or word in ASK_THROWS:
                continue
            if word in dated or any(_same(word, held) for held in dated):
                continue
            behind = words[index - 1] if index else ""
            if behind in DETERMINERS and not _a_doing_word(words[index + 1:]):
                # "how many weeks till the wedding" after "my sister is getting married": a
                # definite thing with no verb of its own is the event the chat already holds.
                continue
            return True  # "till christmas", "till we book", "until the boiler is fixed"
    for match in A_THING_NAMED.finditer(body):
        thing = match.group(1).lower()
        if thing in dated or any(_same(thing, word) for word in dated):
            continue
        if thing in UNTIL_THROWS:
            continue
        return True
    return False


def _a_doing_word(words):
    """Whether any of the words says what is done, rather than naming the thing.

    "until the boiler is fixed" and "until my food arrives" say what will happen to the thing;
    "till the wedding" only names it. Read from the shape of the word, so no list of verbs has to
    be kept: a participle or a third-person form ends the thing named and starts the event.
    """
    return any(word.endswith(("ed", "ing")) or (len(word) > 3 and word.endswith("s"))
               for word in words if word not in ("is", "are", "was", "were", "be", "been"))


def _plain(when):
    """The date with the word that joins it stripped: "in july" -> "july"."""
    words = [word for word in str(when or "").lower().split()]
    while words and words[0] in LEAD:
        words.pop(0)
    return " ".join(words)


def _put_right(memory):
    """The date a correction settled on, and the old one it replaced.

    The store keeps the line the person used to put it right (`say`/`from`/`sentence`), and the
    date they were put right on is the date in it. Returns ("", "") when nothing was corrected
    or the corrected line carries no date, so every other chat is unchanged.
    """
    fixed = (memory or {}).get("correction") if isinstance(memory, dict) else None
    if not isinstance(fixed, dict):
        return "", ""
    sentence = " ".join(str(fixed.get("sentence") or "").split())
    old = _plain(fixed.get("from"))
    if not sentence or not old:
        return "", ""
    found = list(FUTURE.finditer(sentence)) + list(SHORT_DATE.finditer(sentence))
    if not found:
        return "", ""
    return sentence, old


# Two words for the same thing, said one way in the ask and the other in the line: "the wedding
# *is* september" then "when is the wedding" shares no word with "we are getting married in june",
# so the date they had already given was not found and the search hedge answered instead.
SAME_THING = {
    "wedding": frozenset("married marry marrying wed weddings".split()),
    "married": frozenset("wedding weddings marry marrying wed".split()),
    "marry": frozenset("wedding weddings married marrying".split()),
    "baby": frozenset("pregnant pregnancy birth born due babies".split()),
    "babies": frozenset("pregnant pregnancy birth born due baby".split()),
    "pregnant": frozenset("baby babies pregnancy birth due".split()),
    "pregnancy": frozenset("baby babies pregnant birth due".split()),
    "job": frozenset("work working career".split()),
    "work": frozenset("job career".split()),
}
def _a_date_said(value):
    """A bare date said back the way a date is said: "june" -> "in June", "the 4th" -> "on the
    4th", "4th may" -> "on the 4th of may".

    The date is stored the way it was typed, and the answer has to be a date somebody would say,
    so the joining word is put back on it. A month takes "in" and a day takes "on", which is the
    same rule `_lead` follows for a date that already had its joining word.
    """
    phrase = " ".join(str(value or "").split()).strip(" .,!?")
    words = phrase.lower().split()
    if not words:
        return ""
    if len(words) >= 2 and re.fullmatch(r"\d{1,2}(?:st|nd|rd|th)?", words[0]) and (
            words[1] in MONTHS or (len(words) > 2 and words[1] == "of")):
        rest = " ".join(words[1:]) if words[1] in MONTHS else " ".join(words[2:])
        return "on the " + words[0] + " of " + rest
    if words[0] in MONTHS or words[0] in ("early", "mid", "late"):
        return "in " + phrase
    return "on " + phrase


def _same(word, other):
    """True when the two words are the same word, with or without a verb ending on it."""
    word, other = word.lower(), other.lower()
    if word == other or forms(word) & forms(other):
        return True
    if _root(word) == _root(other):
        return True
    return other in SAME_THING.get(word, ()) or word in SAME_THING.get(other, ())


def _root(word):
    for ending in ("ing", "ed"):
        if word.endswith(ending) and len(word) - len(ending) >= 2:
            return word[:-len(ending)]
    return word


# One part of a plan, asked for on its own. "we're off to portugal in august" said back whole
# ("You're off to portugal in august") answers both "where are we going again" and "which month
# are we going", and asking the second of them got the first answer again word for word. What a
# part ask wants is the part: the place for "where", the date for "when".
ASKS_WHERE = re.compile(r"\bwhere(?:abouts)?\b", re.I)
ASKS_WHEN = re.compile(r"\bwhen\b|\b(?:which|what) (?:month|day|week|date|time of year)\b", re.I)
# An ask that names the kind of date it wants gets that kind or nothing: "which month are we
# going" is not answered by the day of the week a plan names.
ASKS_THE_MONTH = re.compile(r"\b(?:which|what) month\b", re.I)
ASKS_THE_DAY = re.compile(r"\b(?:which|what) (?:day|week)\b", re.I)
# What is left of a plan once its date is taken out is a place only when it names one: "i'm going
# away in august" has no place in it, and "Away." is no answer to "where am i going".
NO_PLACE = frozenset("""away out off back home there somewhere anywhere everywhere now soon
later today tomorrow tonight weekend week month year again then bed sleep work""".split())
# A plan kept without its verb ("im moving house in june" is kept as "house in june") has no
# place in it either: what is left is the thing being done, and "House." answers a where ask with
# the object of a move. The sentence the plan came from is what says there is a place in it, so a
# phrase-only reading has to look like a name to be one at all (see `_the_place`).
A_VERB = frozenset("""move moving go going went fly flying drive driving travel travelling
traveling visit visiting start starting begin beginning take taking run running play playing work
working book booking sort sorting pack packing have having get getting see seeing meet meeting
buy buying sell selling pay paying do doing make making""".split())
# Where a place is said: after "to" in the sentence the plan came from. The verb in front of it is
# what makes it a journey - "we're off to portugal in august", "i'm going to the gym tomorrow",
# "i booked a trip to rome in may" - and "i spoke to my sister" is not one.
GOES_TO = re.compile(
    r"\b(?:go|goes|going|went|gone|off|head|headed|heading|fly|flying|flies|flew|flown|move|moves|"
    r"moving|moved|travel|travelling|traveling|drive|driving|drove|back|booked|book|trip|tour|"
    r"visit|visiting|holiday|vacation|head(?:ing|ed)?|away)\b[^.;!?]*?\b(?:to|towards)\s+"
    r"([^,.;!?]+)$", re.I)
PLACE_PREP = re.compile(r"\b(?:to|towards|via)\s+(\S.*)$", re.I)
# The word that joins the date to the thing stays behind when the date is lifted out: "portugal in
# august" is "portugal" and not "portugal in".
TRAILING_JOINER = re.compile(
    r"(?:[\s,]+\b(?:in|on|at|for|by|from|to|and|around|during|early|mid|late|the|of)\b)+$", re.I)


def the_part_asked(plan, low, line=None, is_a_place=None):
    """The part of a plan an ask names on its own, as a whole sentence, or "".

    "where are we going again" after "we're off to portugal in august" is "Portugal.", and
    "which month are we going" is "In August.". The plan read out whole is right and is what the
    bot said the turn before, so a person asking for a part gets the part. "" means the ask names
    a part this plan does not carry (a where ask on a plan with no place, a month ask on a plan
    with only a day), and the caller keeps its own answer.

    `line` is the sentence the plan was said in, when the store can find it. A plan is kept
    without its verb ("house in june"), and only that sentence can say whether anybody is going
    anywhere: it is where the place after "to" comes from. `is_a_place` is the caller's own
    reading of a place (the store has one), used to tell a place named on its own ("Portugal",
    "Bristol") from the object of a verb kept without it ("House").
    """
    text = " ".join(str(plan or "").split())
    ask = str(low or "")
    if not text or not ask:
        return ""
    spans = _the_dates_in(text)
    if ASKS_WHERE.search(ask):
        place = _the_place(text, line, is_a_place)
        if not place:
            return ""
        return _a_name(place) + "."
    if ASKS_WHEN.search(ask):
        when = _the_date_asked(ask, [said for _, _, said in spans])
        return _sentence(when) if when else ""
    return ""


def _the_place(plan, line, is_a_place=None):
    """The place a plan carries, said the way the person said it, or "" when it has none.

    The sentence the plan came from is asked first, because it still has the verb that makes the
    place one ("i'm going to the gym tomorrow" -> "the gym"). The plan on its own is used only
    when what is left of it is a place by the caller's own reading ("Portugal in august" ->
    "Portugal"), which is how the store keeps a place it lifted out of a trip; "house in june"
    is the object of a move, and a where ask about it keeps the plan sentence.
    """
    said = " ".join(str(line or "").split())
    if said:
        found = GOES_TO.search(said)
        if found:
            place = _without_the_date(found.group(1))
            place = TRAILING_JOINER.sub("", place).strip(" .,;:!?-")
            if _names_a_place(place):
                return place
    place = _without_the_date(plan)
    place = TRAILING_JOINER.sub("", place).strip(" .,;:!?-")
    cut = PLACE_PREP.search(place)
    if cut:
        place = cut.group(1).strip(" .,;:!?-")
    if not _names_a_place(place):
        return ""
    if is_a_place is not None and not is_a_place(place):
        return ""
    return place


def _a_name(place):
    """A place said as a name: "new york" -> "New York", "the gym" -> "The gym".

    A name of more than one word with no small word in it is a proper name and is written in
    title case ("New York"); everything else keeps its own capitals and takes one on the first
    letter, so "the gym" is not "The Gym".
    """
    small = frozenset("the a an of and in on at for to".split())
    words = place.split()
    title = len(words) > 1 and not any(word.lower() in small for word in words)
    out = []
    for turn, word in enumerate(words):
        if word[:1].isalpha() and (turn == 0 or title):
            word = word[:1].upper() + word[1:]
        out.append(word)
    return " ".join(out)


def _without_the_date(text):
    """A phrase with every date taken out of it: "portugal in august" -> "portugal"."""
    out = str(text or "")
    for start, end, _ in reversed(_the_dates_in(out)):
        out = out[:start] + " " + out[end:]
    return " ".join(out.split())


def _names_a_place(place):
    """True when a phrase left over from a plan is a place and not the remains of a sentence."""
    if not place or not re.search(r"[a-z]", place, re.I):
        return False
    plain = place.lower().strip(" .,;:!?-")
    if plain in NO_PLACE:
        return False
    words = re.findall(r"[a-z']+", plain)
    if not words or set(words) & A_VERB:
        return False
    return not re.search(r"\b(?:is|are|was|were|am|and|with|for|about)\b", plain)


def _the_dates_in(text):
    """Every date in a piece of a line, in the order it is said, with where it sits."""
    out = []
    for pattern in (FUTURE, SHORT_DATE, PAST_WHEN):
        for found in pattern.finditer(text):
            if any(found.start() < end and start < found.end() for start, end, _ in out):
                continue
            out.append((found.start(), found.end(), found.group(0)))
    out.sort()
    return out


def _the_date_asked(ask, dates):
    """The date the ask names the kind of: the month it asks for, the day it asks for."""
    for when in reversed(dates):
        plain = _plain(when).lower()
        words = set(plain.split())
        if ASKS_THE_MONTH.search(ask) and not words & MONTHS:
            continue
        if ASKS_THE_DAY.search(ask) and not (words & DAYS or re.search(r"\d", plain)):
            continue
        return when
    return ""


# A booking is not a memory however past its verb is: "i booked the tickets for june" and
# "i booked a table for friday" are the trip still to come, and a rule that reads every past tense
# as a thing done turned both into "That was in June.". The countdowns read the same verbs through
# `_said_in_the_past` and are left alone: what changes here is only the plain "when is it" answer.
SAYS_IT_IS_COMING = re.compile(
    r"\b(?:booked|reserved|arranged|scheduled|organi[sz]ed|planned)\b"
    r"|\b(?:got|bought|picked\s+up)\b[^.!?]{0,20}?\b(?:tickets?|flights?)\b", re.I)


# What the person is in the middle of doing or about to do: "im getting married in june",
# "we're flying out on the 12th". `-ed` is not the only past tense and `-ing` is not a past one,
# but the word list reads "married" and "booked" alike, so the shape is read here.
GOING_ON = re.compile(r"\b(?:i|we|they|he|she)(?:'?m|'?re|'?s)?\s+[a-z]+ing\b", re.I)
WAS_GOING_ON = re.compile(r"\b(?:was|were|had|been)\b", re.I)


# An ask that wants the side of today rather than the date: "did i already go", "have i been
# yet", "did that happen". The line that gave the date says which side, and the answer is one
# word and the date - the hedge it met was the same reply for everyone who ever booked anything.
ALREADY_DONE_ASK = re.compile(
    r"\b(?:did|have|has|do)\s+(?:i|we|that|it)\b[^.?!]*?\b(?:already|yet|happen(?:ed)?|"
    r"been|go|gone|going|did)\b|\b(?:already|yet)\s+(?:go|gone|been|happen(?:ed)?)\b", re.I)


def already_answer(text, memory):
    """Whether the thing the person asks about has happened, from the line that dated it."""
    line = str(text or "")
    if not ALREADY_DONE_ASK.search(line) or WHEN_ASK.search(line):
        return None
    if NOT_A_DATE_TO_GIVE.search(line):
        return None
    words = [word for word in content(line) if word not in ASK_THROWS]
    asked = [word for word in words if word not in TRIP_WORDS]
    for said, spans in _dated(memory)[:2]:
        if NOT_A_DATE_TO_GIVE.search(said) or not _said_in_the_last_few_turns(memory, said):
            continue
        when = (_time_for(asked, said, spans) if asked else "") or (spans[-1][0] if spans else "")
        if not when:
            continue
        plain = _plain(when).split()
        # Both sides are answered: "have i been yet" about a trip still to come is as much a
        # question as about one already gone, and "No - that's on the 12th." is the whole answer.
        if _has_happened(said):
            if plain and (plain[0] in MONTHS or plain[0] in DAYS):
                return "Yes - that was in " + _sentence(when)
            said_when = _sentence(when)
            return "Yes - that was " + said_when[:1].lower() + said_when[1:]
        if plain and (plain[0] in MONTHS or plain[0] in DAYS):
            return "No - that's in " + _sentence(when)
        said_when = _sentence(when)
        return "No - that's " + said_when[:1].lower() + said_when[1:]
    return None


# An ask about a date that has gone: "when did i move", "when was my exam". The date is the
# answer and it needs no "that was" in front of it.
AN_ASK_IN_THE_PAST = re.compile(r"\b(?:did|was|were|had|have\s+i|has\s+it)\b", re.I)


def _has_happened(said):
    """Whether the line that gave the date says the thing is behind the person, not ahead."""
    said = str(said or "")
    if SAYS_IT_IS_COMING.search(said):
        return False
    if GOING_ON.search(said) and not WAS_GOING_ON.search(said):
        return False
    return _said_in_the_past(said)


def _was_sentence(when):
    """A date the line says has already happened: "in june" -> "That was in June." """
    plain = _plain(when).split()
    if plain and (plain[0] in MONTHS or plain[0] in DAYS):
        return "That was in " + _sentence(when)
    said = _sentence(when)
    return "That was " + said[:1].lower() + said[1:]


def _sentence(when):
    """A date said on its own: "in march" -> "In March." """
    out = []
    for word in when.split():
        low = word.lower().strip(",;:")
        if low in MONTHS or low in DAYS:
            word = word[:1].upper() + word[1:]
        out.append(word)
    said = " ".join(out).rstrip(" .")
    return said[:1].upper() + said[1:] + "."


# --- how long until it ---------------------------------------------------------
#
# The date of the thing they said is not the only thing a person asks about it. "im running a
# half marathon in october" / "how many weeks till that" was answered with the statutory holiday
# allowance, and "how long have i got" after a moving date with a search hedge: the bot had the
# date in the conversation and could count from it, and counting is the whole answer. Nothing is
# invented - the dates someone gives are already on file (`_dated`), so the reply is arithmetic
# on their own line.
#
#     i have an interview on the 14th        / how many days have i got  -> That's 6 days away
#     we're going to cornwall in august      / how many weeks till that  -> About 38 weeks away
#     im going to rome next month            / how long till that        -> About 4 weeks away
#
# Only a line that asks how long until the thing, and only when the thing was dated in the last
# few turns: a date from ten turns ago is not what "how long till that" means.
# An ask about when they will *know* is not the date on file: "i have a scan on the 14th" then
# "how long till i know" wants the result, and counting the scan is a different answer. The scan
# is still counted when they ask about the scan.
# A length said for a plan, where no line gives a date: "we're moving house in 6 weeks",
# "the wedding is in two months". `until_answer` only ever counted from a date (`_dated`), so a
# chat that said how far off the thing was could not answer "how long have i got until the move"
# and the line fell to the calendar ask ("tell me the date - the day and the month"), which asked
# the person to say again what they had already said. The length is the answer, said back.
AN_INTERVAL_AHEAD = re.compile(
    r"\bin\s+(?P<n>\d+|a|an|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|"
    r"couple\s+of|a\s+couple\s+of|a\s+few|few|several)\s+"
    r"(?P<unit>days?|nights?|weeks?|fortnight|fortnights?|months?|years?)\b", re.I)

# The words a line can put between the thing and its length: "the wedding is in two months".
INTERVAL_JOINERS = frozenset("""is are was were will be gets get got has have had and so but
  only just now then again roughly about around nearly maybe probably ideally hopefully""".split())


def _the_interval_it_means(line, memory):
    """The length said for the thing the ask names, or "" when no recent line gives one.

    Only a line that is still one of the last few things they said counts, and the ask has to name
    that line's thing - or point back at it ("how long have i got", "how many weeks left") - so a
    length said about one thing is not handed to an ask about another. Nothing here counts
    calendar days: the line gave a length, not a date, so the answer is that length said back and
    the honest note that it was measured from when they said it.
    """
    said_lines = [_said_before_now(memory, turn) for turn in (memory.get("turns") or [])[-BACK_TURNS:]]
    said_lines = [said for said in said_lines if said]
    if not said_lines:
        return ""
    asked = [word for word in content(line) if word not in ASK_THROWS and word not in UNTIL_THROWS]
    named = [word for word in asked if word not in TRIP_WORDS]
    points_back = _points_back(line) or not asked
    for said in reversed(said_lines):
        found = AN_INTERVAL_AHEAD.search(said)
        if not found:
            continue
        if found.group("unit").lower().endswith(("day", "days")) and re.search(
                r"\b(?:ago|since)\b", said, re.I):
            continue  # "in 3 days" after a thing that happened is not ahead of anybody
        if not points_back and named:
            line_words = set(content(said))
            if not any(_same(word, other) for word in named for other in line_words):
                continue  # the length is for another thing than the one asked about
        length = " ".join(found.group(0).split()[1:])
        return f"You said {length}, so a little less than that by now."
    return ""


def _said_before_now(memory, turn):
    """The line the person typed on that turn, or "" when it is the bot's own turn."""
    said = turn.get("user") if isinstance(turn, dict) else None
    return " ".join(said.split()) if isinstance(said, str) else ""


UNTIL_A_LEARNING = re.compile(
    r"\b(?:till|until|til)\s+i\s+(?:know|hear|find\s+out|learn|s\s*(?:out|back)|"
    r"get\s+(?:the\s+)?(?:results?|answer|news))", re.I)
UNTIL_ASK = re.compile(
    r"\bhow\s+(?:long|soon|far|many\s+(?:days?|weeks?|months?|nights?))\b"
    r"[^.?!]*?(?:\b(?:till|til|until|to\s+go|left|away|off|have\s+i\s+got|"
    r"do\s+(?:i|we)\s+have|does\s+that\s+leave|ago|since)\b"
    r"|\b(?:is|was|are)\s+(?:that|it|this)\b)", re.I)
# An ask that counts back: "how long ago was that", "how many weeks since". A date said in the
# past is only ever counted the one way.
AGO_ASK = re.compile(r"\b(?:ago|since|back\s+was|has\s+it\s+been)\b", re.I)
# A line that says the thing has already happened. The date reader takes the next time a month
# comes round, which is right for "my birthday is on 21 june" and wrong for "i had an exam in
# june": the same words, and only the verb says which side of today the day is on.
# Every past tense counts, not a list of the ones I thought of: "moved", "booked", "broke" and
# "went" are one verb each, and a list that misses "broke" called a broken arm six months away.
SAID_IN_THE_PAST = re.compile(
    r"\b(?:had|was|were|went|did|been|got|took|made|bought|brought|sold|lost|met|left|saw|"
    r"said|told|felt|broke|broke\s+up|came|died|kept|paid|ran|sat|stood|wrote|spoke|"
    r"\w+ed)\b", re.I)
# A line with one of these in it is about what is to come however past its verbs look: "we're
# booked in for june" and "the exam is in june" are plans, and a plan counts forward.
NOT_IN_THE_PAST = re.compile(
    r"\b(?:will|going\s+to|next|upcoming|tomorrow|have|has|is|are|am)\b|'(?:re|m)\b", re.I)


def _said_in_the_past(line):
    """Whether the line the date came from says the thing has already happened."""
    said = str(line or "")
    if not said:
        return False
    return bool(SAID_IN_THE_PAST.search(said)) and not NOT_IN_THE_PAST.search(said)


# The asks that are a countdown and nothing else: whatever else the line names is what they will
# do with the time, not another thing to count to.
UNTIL_COUNTDOWN = re.compile(r"\b(till|til|until|to\s+go|have\s+i\s+got|do\s+(?:i|we)\s+have)\b",
                             re.I)
# The countdown leads that name the event after them ("till christmas", "until the boiler is
# fixed"), as opposed to the ones that say what the time is for ("have i got to revise").
UNTIL_NAMES_THE_EVENT = frozenset(("till", "til", "until"))
# "how many weeks", "and how many days": the unit asked a turn after the same count still asks the
# same count, but there is no "till" in it, so the ask is recognised by its shape and the date it
# counts to is the one the last count used ("my driving test is on the 14th" / "how many days have
# i got" / "and how many weeks" went to the lessons card).
BARE_UNIT_ASK = re.compile(
    r"^\W*(?:(?:and|but|so|ok|okay|right|then|now|well|yeah)\W+)*"
    r"how\s+many\s+(?:days?|weeks?|months?|nights?)\b"
    r"(?:\W+(?:have\s+i\s+got|is\s+that|to\s+go|left|away|off|now|then|again))*\W*$", re.I)


# A count from a date to a day they have already said how long is, is not the answer: "im going to
# rome for three days in may", "what should i see", "and where should i eat", then "how many days"
# asks about the three days, and the countdown told them the trip was 173 days away. A line that
# gives the length of a thing ("for three days", "for a week") has answered the length already, so
# a bare unit ask is a question about that length. A tail that asks for a count ("days have i got",
# "days to go", "days left") is still a countdown, because it says so.
A_LENGTH_IN_THE_LINE = re.compile(
    r"\bfor\s+(?:\d+|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|a|an|"
    r"a\s+couple|couple|few|several)\s+(?:days?|nights?|weeks?|months?|hours?)\b", re.I)
# What makes a bare unit ask ask for a count rather than for a length: it says so itself.
A_COUNT_TAIL = re.compile(
    r"\b(?:have\s+i\s+got|is\s+that|to\s+go|left|away|off|till|til|until)\b"
    r"|\bhow\s+(?:long|soon|far)\b", re.I)


# A stay has a length, and a bare unit ask in a chat that is on a trip asks for it: "we are going to
# rome in june" / "how many days" is how long to spend in Rome, and the travel card answers it.
# Nothing in that line asks about the distance to June - a countdown says "till", "until", "to go"
# (`A_COUNT_TAIL`) - so the days asked about are the days of the trip. A trip line that names a day
# of its own ("we fly on the 12th") is a date to count to, and stays a countdown.
A_TRIP_SAID = frozenset("""trip vacation honeymoon""".split())
# The words that make "going to" something other than a place: "im going to be 40 in june" and
# "going to the gym" are not trips, and "we are going to rome" is.
A_GOING = frozenset("""going off flying travelling traveling heading driving""".split())
NOT_A_PLACE = frozenset("""be get go do try have see make take start stop need leave work bed school
    bed sleep the a an my our your their""".split())


def _a_trip_is_named(dated):
    """Whether the line says a trip or a journey to a place of its own."""
    words = re.findall(r"[a-z']+", " ".join(str(dated or "").lower().split()))
    if any(word in A_TRIP_SAID for word in words):
        return True
    for place, word in enumerate(words):
        if word in A_GOING and place + 2 < len(words) and words[place + 1] == "to":
            if words[place + 2] not in NOT_A_PLACE:
                return True
    return False


def _a_bare_unit_ask_wants_a_length(line, dated):
    """Whether a bare unit ask is about a length, not a countdown."""
    said = str(line or "")
    if A_COUNT_TAIL.search(said):
        return False
    dated = str(dated or "")
    if A_LENGTH_IN_THE_LINE.search(dated):
        return True
    if not re.search(r"\bdays?\b", said):
        return False  # a stay is counted in days; weeks and months asked bare are a countdown
    if _the_day(dated)[0] is not None:
        return False  # a day of its own is a date to count to, whatever the trip
    return _a_trip_is_named(dated)


def until_ask_matches(line, again=None):
    """Whether the line asks how long until something, a bare unit ask counting as one."""
    if again is None:
        again = BARE_UNIT_ASK.match(str(line or ""))
    return bool(UNTIL_ASK.search(line) or again)


# Words in the ask that say nothing about which line it means: they ask how long, not what.
UNTIL_THROWS = frozenset("""how long soon far many much day days week weeks month months night
nights till til until to go going left away off have got do does did i we you it that this then
them there is was are be time left ago since""".split())

MONTH_NUMBER = {"january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6,
                "july": 7, "august": 8, "september": 9, "october": 10, "november": 11,
                "december": 12}
MONTH_NAME = {number: name.capitalize() for name, number in MONTH_NUMBER.items()}
WEEKDAY_NUMBER = {"monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3, "friday": 4,
                  "saturday": 5, "sunday": 6}
WEEKDAY_NAME = {number: name.capitalize() for name, number in WEEKDAY_NUMBER.items()}


def _today():
    """The day these replies count from. A plain function so a test can stand still."""
    return datetime.date.today()


def until_answer(text, memory):
    """How long until the thing the line asks about, or None when no line dates it.

    Every line is offered this: the ask has to be a how-long-until ask and a dated line has to be
    in the last few turns, and anything else falls through untouched.
    """
    line = str(text or "")
    again = BARE_UNIT_ASK.match(line)
    if not until_ask_matches(line, again) or WHEN_SAID.search(line):
        return None
    if NOT_A_DATE_TO_GIVE.search(line) or THEIR_OWN_DEATH.search(line):
        return None  # counting down to a death is not what the person asked for
    if UNTIL_A_LEARNING.search(line):
        return None  # how long till they know is not how long till the date they gave
    when, dated = _the_date_it_means("how long until that" if again else line, memory)
    if not when:
        # No line gave a date, but one may have said how far off the thing was ("in 6 weeks").
        # The calendar ask below would otherwise ask the person to say again what they just said.
        return _the_interval_it_means(line, memory) or None
    if again and _a_bare_unit_ask_wants_a_length(line, dated):
        # "im going to rome for three days in may" / ... / "how many days": the three days are the
        # answer, and the countdown to the trip is a different question they did not ask.
        return None
    # A date is often given in two goes - "we're going to rome in may", then "we fly on the 12th" -
    # and the day on its own is that date completed. Read alone, "the 12th" is the twelfth of this
    # month, so the count went to the wrong month: the one the line before named is the one it
    # means, and it is used while that line is still in play.
    if AN_INTERVAL_AHEAD.search(when):
        # The line said how far off the thing is, not the day it falls on ("in 6 weeks"), so
        # there is no calendar to count: the length said back is the answer, and `_the_day`
        # below would have made nothing of it.
        return _the_interval_it_means(line, memory) or None
    month = ""
    if _a_day_but_no_month(when):
        month = _the_month_in_play(when, memory)
    day, kind = _the_day((when + " " + month) if month else when)
    if day is None:
        return None
    if _said_in_the_past(dated):
        # "i had an exam in june" is a thing that has happened, so the day it names is the one in
        # the past and no countdown to it is an answer: asked how long ago, the reply counts back
        # ("that was about 5 months ago - in June"), and asked how long till it, the line stands
        # down rather than calling a June already gone seven months away.
        if not AGO_ASK.search(line):
            return None
        return _how_long_ago(day, kind, line)
    if AGO_ASK.search(line):
        # "how long ago was that" about a date that has not come yet ("my sister is getting
        # married in june"): there is nothing to count back, and counting forward to the date
        # answers a different question than the one asked.
        return None
    return _how_long(day, kind, line)


def _the_date_it_means(line, memory):
    """The date words the ask is about, or None. The ask's own body, not a `when` ask."""
    words = [word for word in content(line) if word not in ASK_THROWS and word not in UNTIL_THROWS]
    if not words or _points_back(line):
        # "how long till that", "how many weeks have i got": the thing is the one just said, so no
        # word has to match and the newest dated line is the one, as long as it is recent.
        return _the_newest_date(memory)
    asked = [word for word in words if word not in TRIP_WORDS]
    trip = asked != words
    for said, spans in _dated(memory):
        if NOT_A_DATE_TO_GIVE.search(said) or THEIR_OWN_DEATH.search(said):
            continue  # a death, or a date they set for their own, is not counted down to
        if trip and not _is_a_trip_line(said):
            continue
        when = _time_for(asked, said, spans)
        if when:
            return when, said
    if UNTIL_COUNTDOWN.search(line) and not NOT_A_DATE_ASK.search(line):
        # "i have an exam in june" / "how long have i got to revise" names the work, not the exam,
        # so no word matched - but the ask is a countdown ("have i got", "till", "to go") and the
        # date just given is what it counts to. The word that did not match says what they will do
        # with the time, which is not a different thing to count to. An ask for judgement is not a
        # countdown: "how long till i should leave" wants to know when to set off, and the date of
        # the appointment is not that answer.
        newest, said = _the_newest_date(memory)
        if newest and _names_a_thing_of_its_own(line, said):
            return None, ""
        return newest, said
    return None, ""


def _the_newest_date(memory):
    """The date on the newest line they dated, or None when that line has gone cold.

    A date on a death is not a date to count down to, and a line from ten turns ago is not what
    "how long till that" means. A date they put right counts as the newest line: the store
    rewrites those in their own words, so the rewritten line is not among the turns.
    """
    fixed, _ = _put_right(memory)
    fixed = " ".join(fixed.split()) if fixed else ""
    for said, spans in _dated(memory):
        if NOT_A_DATE_TO_GIVE.search(said) or THEIR_OWN_DEATH.search(said):
            continue  # a death, or a date they set for their own, is not counted down to
        if _said_in_the_last_few_turns(memory, said) or (fixed and said == fixed):
            return spans[-1][0], said
        return None, ""
    return None, ""


def _a_day_but_no_month(when):
    """Whether the date says which day of the month and not which month.

    "on the 12th" is half a date and the month it belongs to is the one in play; "on the 12th of
    may", "in march", "on monday", "tomorrow" are whole enough to read by themselves.
    """
    words = _plain(when).replace(",", " ").split()
    if not words:
        return False
    if any(word in MONTH_NUMBER or word in WEEKDAY_NUMBER for word in words):
        return False
    if any(word in ("today", "tomorrow", "tonight", "weekend", "month", "week", "year")
           for word in words):
        return False
    return any(re.fullmatch(r"\d{1,2}(?:st|nd|rd|th)?", word) for word in words)


def _the_month_in_play(when, memory):
    """The month a recent line named, for a day given on its own ("on the 12th").

    A date is often given in two goes - "we're going to rome in may", then "we fly on the 12th" -
    and the second line is the same date completed. The month is taken from the newest line that
    named one, and only while that line is still in play: a month from ten turns ago is a different
    thing's month, and guessing it would put the count on a day nobody gave.
    """
    month = ""
    for said, spans in _dated(memory):
        if not _said_in_the_last_few_turns(memory, said):
            break
        for span in spans:
            words = _plain(span[0]).replace(",", " ").split()
            if any(word in MONTH_NUMBER for word in words):
                # The span the ask is about is skipped: it is the bare day itself.
                named = [word for word in words if word in MONTH_NUMBER][-1]
                if _plain(span[0]).strip() != _plain(when).strip():
                    return named
                month = month or ""
    return month


def _the_day(when, today=None):
    """The calendar day a date said the short way falls on, and how it was said.

    The kinds are how much of the date the person gave, because the reply says back only that
    much: a month alone is "sometime in October", a day is "Tuesday 14 October". A date already
    gone is the next time it comes round, which is how people say "in march" in November.
    """
    today = today or _today()
    words = [word for word in _plain(when).replace(",", " ").split() if word]
    month = day = weekday = None
    early = has_end = has_next = has_this = has_month = has_week = False
    for word in words:
        if word in MONTH_NUMBER:
            month = MONTH_NUMBER[word]
        elif word in WEEKDAY_NUMBER:
            weekday = WEEKDAY_NUMBER[word]
        elif word in ("early", "mid", "late"):
            early = True
            day = {"early": 1, "mid": 15, "late": 25}[word]
        elif word in ("end", "ends", "ending"):
            has_end = True
        elif word == "next":
            has_next = True
        elif word == "this":
            has_this = True
        elif word == "month":
            has_month = True
        elif word == "week":
            has_week = True
        elif re.fullmatch(r"\d{1,2}(?:st|nd|rd|th)?", word):
            day = int(re.match(r"\d{1,2}", word).group(0))
        elif word in ("the", "of", "in", "on", "at", "by", "start", "beginning", "weekend",
                      "a", "an", "for", "from", "to", "until", "till", "around", "about"):
            continue
        else:
            return None, None
    if has_month and has_next:
        return _add_months(today.replace(day=1), 1), "month"
    if has_month and has_this:
        return today.replace(day=1), "month"
    if has_end:
        if month is not None:
            return _last_day(_a_year_for(today, month, 1)), "end"
        if has_next:
            return _last_day(_add_months(today.replace(day=1), 1)), "end"
        return _last_day(today.replace(day=1)), "end"
    if has_week and has_next:
        return today + datetime.timedelta(days=7), "week"
    if month is not None:
        when_day = _a_year_for(today, month, day)
        return when_day, ("month" if day is None or early else "date")
    if weekday is not None:
        ahead = (weekday - today.weekday()) % 7 or 7
        return today + datetime.timedelta(days=ahead), "date"
    if day is not None:
        upcoming, kind = _this_month_or_next(today, day)
        return upcoming, ("month" if early else kind)
    return None, None


def _this_month_or_next(today, day):
    """That day number in this month, or next month when this month's has gone."""
    try:
        found = today.replace(day=day)
    except ValueError:
        return _a_year_for(today, today.month + 1, day), "date"
    if found >= today:
        return found, "date"
    return _a_year_for(today, today.month + 1, day), "date"


def _a_year_for(today, month, day):
    """That month and day in the year it next comes round, spoken of as a date."""
    while month > 12:
        month -= 12
        today = today.replace(year=today.year + 1)
    day = day or 1
    for year in (today.year, today.year + 1):
        try:
            found = datetime.date(year, month, min(day, _days_in(year, month)))
        except ValueError:  # noqa: PERF203 - a date the month has not got is not this shape
            continue
        if found >= today:
            return found
    return datetime.date(today.year + 1, month, 1)


def _days_in(year, month):
    if month == 12:
        return 31
    return (datetime.date(year, month + 1, 1) - datetime.date(year, month, 1)).days


def _last_day(first_of_month):
    return first_of_month.replace(day=_days_in(first_of_month.year, first_of_month.month))


def _add_months(day, months):
    month = day.month + months
    year = day.year
    while month > 12:
        month -= 12
        year += 1
    return datetime.date(year, month, 1)


def _how_long(day, kind, line):
    """The reply: how many days or weeks off it is, and the day itself when they said one."""
    today = _today()
    days = (day - today).days
    if days < 0:
        return None
    if days == 0:
        return "That's today."
    if days == 1:
        return "That's tomorrow."
    asked = str(line or "").lower()
    named = ""
    if re.search(r"\bweeks?\b", asked):
        named = unit = "week"
    elif re.search(r"\bdays?\b", asked):
        named = unit = "day"
    elif re.search(r"\bmonths?\b", asked):
        named = unit = "month"
    elif days <= 14:
        unit = "day"
    elif days <= 84:
        unit = "week"
    else:
        unit = "month"
    if unit == "day":
        head = "That's %d days away" % days
    elif unit == "week":
        weeks = int(round(days / 7.0))
        if weeks <= 1:
            head = "That's just over a week away"
        elif named == "week" or weeks <= 30:
            # The unit they asked in is the unit they get: "how many weeks till that" about a
            # half marathon in October asked for weeks, and the month count was a different
            # question. Only an ask that named no unit falls back to months past half a year.
            head = "That's about %d weeks away" % weeks
        else:
            # Past half a year nobody counts in weeks: 47 weeks is a month count waiting to happen.
            unit = "month"
    if unit == "month":
        months = int(round(days / 30.44))
        head = "That's about a month away" if months <= 1 else "That's about %d months away" % months
    said = _the_day_said(day, kind)
    return head + " - " + said + "." if said else head + "."


def _how_long_ago(day, kind, line):
    """The reply to a count-back: how long ago the day they gave was, and the day itself.

    The day on file is the next time that date comes round (that is how a date said the short way
    is read), so the same month and day a year or two back is the one they mean: "i had an exam in
    june" asked "how long ago was that" is "That was about 5 months ago - in June."
    """
    today = _today()
    past = _a_day_in_the_past(day, today)
    if past is None:
        return None
    days = (today - past).days
    if days <= 0:
        return None
    asked = str(line or "").lower()
    if re.search(r"\bweeks?\b", asked):
        unit = "week"
    elif re.search(r"\bdays?\b", asked):
        unit = "day"
    elif re.search(r"\bmonths?\b", asked):
        unit = "month"
    elif days <= 14:
        unit = "day"
    elif days <= 84:
        unit = "week"
    else:
        unit = "month"
    if unit == "day":
        head = "That was %d days ago" % days
    elif unit == "week":
        weeks = int(round(days / 7.0))
        head = ("That was just over a week ago" if weeks <= 1
                else "That was about %d weeks ago" % weeks)
    else:
        months = int(round(days / 30.44))
        head = "That was about a month ago" if months <= 1 else "That was about %d months ago" % months
    # "sometime in June" is how a month to come is said; a month that has gone is "in June".
    if kind == "month":
        said = "in " + MONTH_NAME[past.month]
    elif kind == "end":
        said = "at the end of " + MONTH_NAME[past.month]
    else:
        said = _the_day_said(past, kind)
    return head + " - " + said + "." if said else head + "."


def _a_day_in_the_past(day, today):
    """The same month and day as `day`, on the side of today that has already happened."""
    month, number = day.month, day.day
    for year in (day.year - 1, day.year - 2, day.year - 3):
        try:
            found = datetime.date(year, month, min(number, _days_in(year, month)))
        except ValueError:  # noqa: PERF203 - a date the month has not got is not this shape
            continue
        if found <= today:
            return found
    return None


def _the_day_said(day, kind):
    """The day itself, said as much as the person said it: "sometime in October", "Sunday 15
    November", "the end of November"."""
    month = MONTH_NAME[day.month]
    if kind == "month":
        return "sometime in " + month
    if kind == "end":
        return "the end of " + month
    if kind == "week":
        return "around " + WEEKDAY_NAME[day.weekday()]
    return "%s %d %s" % (WEEKDAY_NAME[day.weekday()], day.day, month)

# A day the person names, with the part of the day that goes with it: "friday night", "tomorrow",
# "the weekend". The part of the day is read with the day, because "friday night instead" moves
# the plan to the evening, and a rewrite that takes only "friday" leaves "night" behind.
_DAY_NAMED = re.compile(
    r"\b(?:(?:mon|tues|wednes|thurs|fri|satur|sun)day|tomorrow|tonight|the weekend|next week|"
    r"next month)(?:\s+(?:night|morning|afternoon|evening|lunchtime|midday))?\b", re.I)
# A word that says the plan is not when it was: "instead", "move it", "leave it till".
_MOVED = re.compile(
    r"\b(?:instead|move it|push it|put it off|leave it (?:till|until|to)|another day|a day later)\b",
    re.I)
# What a plan is, said in a line that also names another day: "can i make it friday instead",
# "could we have it saturday", "do it tomorrow instead".
_PLAN_VERB = re.compile(
    r"\b(?:make|cook|do|have|serve|eat|start|finish|go|come|meet|post|send|call|book|clean|"
    r"get|buy|pick|deliver|visit)\b", re.I)
# Words that point back at the plan already on the table. A line that names its own thing ("can i
# make pancakes on friday instead") says what it is about and is left to the entries.
_POINTS_AT_IT = re.compile(r"\b(?:it|that|this)\b", re.I)


def a_plan_moved_to_a_day(text):
    """{"day": "friday night", "line": "can i make it ahead of time"}, or None.

    "im cooking chilli for 6" / "can i make it friday night instead" is a plan moved to another
    day, and the question inside it is whether the dish can be made ahead: the answer that says
    it keeps three days and is better the next day is exactly what was asked, and it was given for
    "can i make it the day before" already. The line is read by putting "ahead of time" where the
    day was, so the same reader answers both, and the day is handed back so the reply can say the
    day out loud.

    None unless the line names a day, says the plan moved, names a plan verb and points back at
    the plan with "it"/"that", so nothing that says what it is about is rewritten here.
    """
    said = " ".join(str(text or "").lower().split()).strip(" .!?")
    if not said or len(said.split()) > 14:
        return None
    day = _DAY_NAMED.search(said)
    if not day:
        return None
    if not _MOVED.search(said) and not re.search(r"\b(?:on|till|until)\s+" + re.escape(day.group(0)),
                                                 said):
        return None
    if not _PLAN_VERB.search(said) or not _POINTS_AT_IT.search(said):
        return None
    line = _DAY_NAMED.sub("ahead of time", said, count=1)
    line = _MOVED.sub("", line)
    line = re.sub(r"\b(?:on|till|until)\s+ahead of time\b", "ahead of time", line)
    line = " ".join(line.split())
    if "ahead of time" not in line:
        return None
    return {"day": " ".join(day.group(0).split()), "line": line}
