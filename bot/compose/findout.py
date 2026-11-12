"""Where the answer lives, when it is not in this bot.

The last thing the bot says to a question nothing else answered is an honest hedge: "I'd
rather not guess, a quick search online will get you a solid answer". It is true, and it fits
nothing in particular - a person asking what time the tip shuts gets no more out of it than a
person asking who won the darts, and STYLE.md's "Not knowing, honestly" asks for the place
the answer lives instead:

    **User:** What time does the post office on Hill Road close today?
    **Bot:** I can't check live opening hours, sorry. Search for the branch online: its
    listing on a map app usually shows today's hours, holidays included.

Nearly every such line has the same shape underneath: the answer exists, and it lives in one
named place - the venue's own page, the operator's app, a map app, the office that
issues the thing. This module reads which of those the ask needs and says it,
with what the person will find there. Nothing here is a fact about the world, so nothing can
be invented and nothing goes stale.

Kinds are read from the ask rather than from a list of subjects, so a line nobody has written
down ("when does the bottle bank shut", "are there delays on the a38") lands in the same place
as the ones in the deck. A line that is not one of these gets None and keeps whatever the
composer had.
"""
import re

# The reply for a question about opening hours, and a line with nothing of its own.
HOURS = (
    "Opening hours are set by each branch rather than by the chain, and they shift at bank "
    "holidays and at short notice. The branch's own page or its map listing has today's - that's "
    "the bit that catches people out.",
    "A branch keeps its own hours and they move for holidays, a delivery day or a refit, so "
    "nothing said from here would be right today. A map app's listing for that branch is the "
    "quickest check, and a phone call settles it.",
    "Hours like that are local and they change: bank holidays, stock takes, a summer timetable. "
    "Ring the place or look at its map listing - both are updated when the hours move.",
)
# A place whose hours can be asked about. Long enough to cover the everyday ones, and a
# place named some other way simply misses the kind and keeps the composer's reply.
A_PLACE = frozenset("""
    shop shops store stores supermarket tesco asda sainsburys sainsbury aldi lidl morrisons
    coop co-op iceland waitrose branch bank banks building society library libraries tip dump
    recycling pool lido leisure gym market stall cafe caff cafe restaurant chippy chippies
    takeaway takeaway kebab chip pizza pub pubs bar pharmacy chemist chemists surgery gp
    doctors dentist dental hospital garage showroom museum gallery gallery bowling cinema
    theatre softplay church chapel club hairdresser hairdressers barber salon vets vet
    merchants warehouse centre center office reception
""".split())
# "Open" is a verb about a window, a jar and a letter as well as a shop's hours, and a person's
# own day opens too ("what time do i start"), so those lines are not this kind.
NOT_A_VENUE = frozenset("""
    window windows jar tin box boxes door doors envelope packet bottle can letter parcel
    present gift browser app file folder email shift work school run day week
""".split())
THE_PEOPLE = frozenset("""
    son daughter kid kids child children baby wife husband partner mum mom mother dad father
    boyfriend girlfriend nan grandma grandad grandson granddaughter friend boss manager
""".split())
# The ask for hours in the shapes people type it: "when does the market open", "what time does
# the tip shut", "is the pool open on sunday", "how late is the chippy open", "is there a
# pharmacy open late near me".
HOURS_ASK = re.compile(
    r"\b(?:when|what\s+time[s]?)\s+(?:does|do|is|are|will|would|can|should)\b[^?]{0,44}?"
    r"\b(?:open|opens|opening|close|closes|closing|shut|shuts|shutting)\b"
    r"|\b(?:is|are)\b[^?]{0,32}?\bopen\b")
# "How late" and "opening hours" are the same question without the verb, and they are also how a
# person asks the time of day ("how late is it") or the length of a job ("how late is it open"),
# so this shape needs a place named in the line. "How late is the chippy open" has one; "how
# late is it" does not and keeps whatever the composer had.
LATE_ASK = re.compile(r"\bhow\s+late\b|\bopen\s+late\b|\bopen\s+early\b"
                      r"|\bopening\s+(?:hours|times?)\b|\bclosing\s+time\b"
                      r"|\btill\s+(?:when|what\s+time)\b")
# A how-to about opening a thing is not a question about hours.
HOW_TO_OPEN = re.compile(r"\bhow\s+(?:do|to|can|should)\s+(?:i\s+)?open\b")

# Live travel and live plans: the operator, the club and the venue know today's, and none of
# them is a fact the bot holds.
TRAVEL = frozenset("""
    bus buses coach coaches train trains tram trams tube underground flight flights plane
    planes ferry ferries motorway motorways a-road by-pass bypass line lines route routes
    service services replacement bus traffic junction
""".split())
STATUS = frozenset("""
    running delayed delay delays cancelled canceled cancellation cancel strike strikes closed
    shut diverted diversion disruption disruptions roadworks traffic
""".split())
# A claim is about what is owed afterwards, not about where the train is now, and the operator's
# app has nothing to say about it.
TRAVEL_CLAIM = frozenset("""
    claim claims claimed refund refunds compensation compensate money owed reimburse reclaim
    pays insurance insurer hotel rebook rebooking
""".split())
# "My train was cancelled so I drove" is a story; "is my train cancelled tomorrow" is a question.
# The ask is the verb in most lines, and in some it is only the noun: "delays on the a38",
# "roadworks on the m6", "traffic on the northern line" is a person asking about today with the
# question left out, and a status word at the head of the line is as good a sign as "is".
ASKED = re.compile(r"\b(?:is|are|will|any|does|do)\b|"
                   r"^\s*(?:any\s+)?(?:delays?|disruptions?|traffic|roadworks?|road\s+works|"
                   r"cancellations?|strikes?|engineering\s+works)\b")
# A question that opens with the verb is a question whatever follows it: "is my bus running, the
# drivers were meant to be striking" is about today, not a story.
OPENS_ASKING = re.compile(r"^\s*(?:is|are|will|any|does|do|what|when|how)\b")
STORY = re.compile(r"\b(?:was|were|got|had|did|have|has|theyve|weve|ive|again|yesterday|"
                   r"this\s+morning|last\s+night)\b")
STATUS_PHRASES = ("engineering works", "called off", "on time", "bus replacement",
                  "replacement bus", "road works")
# A road named by its number - "the m6", "the a38" - is live information as much as a bus is.
ROAD = re.compile(r"(?<![a-z0-9])[am]\s?\d{1,3}(?![a-z0-9])")
TRAVEL_LINES = (
    "Disruption can clear or spread within the hour, so only today's version is worth acting "
    "on: the operator's app or a journey planner has the next service, and for a road the "
    "traffic service names the stretch.",
    "Whether it is running today is on the operator's own system, and delays move. Their app or "
    "a journey planner shows the next one and any disruption - check it just before you set off.",
)
# What's on, and when it starts: listings change weekly and a kick-off moves for television.
ON_WORDS = frozenset("""
    cinema theatre theater pictures gig gigs match game show concert festival listings listing
    play screening movie movies film films odeon vue cineworld multiplex venue
""".split())
# A thing that happens on a day: a market, a fete, a gig. "Is it on" is the same question as
# "what's on", asked about one event, and the answer lives on the event's own page too.
ON_EVENT = frozenset("""
    market markets festival fete fair gig gigs match game show concert cinema theatre play
    screening event events boot sale
""".split())
ON_ASK = re.compile(r"\b(?:whats?|what\s+is)\s+on\b|\blistings?\b|\bwhats\s+on\s+at\b"
                    r"|\bis\s+(?:it|that|the\s+[a-z]+)\s+on\b|\bstill\s+on\b")
KICK_OFF = re.compile(
    r"\bwhat\s+time\s+(?:is|does|do|will)\b[^?]{0,24}?\bkick\s*-?\s*off\b"
    r"|\bwhen\s+(?:is|does)\b[^?]{0,24}?\bkick\s*-?\s*off\b"
    r"|\bwhat\s+time\s+(?:is|does)\s+the\s+(?:match|game|final)\b"
    r"|\bis\s+the\s+(?:match|game)\s+on\b")
# The same question in the shape people use when they want a recommendation rather than a
# timetable: "what's good at the theatre this month", "what's worth seeing at the cinema",
# "what's the new film at the pictures". The venue word is what makes it a listing and not a
# taste question - "what's good to watch" on its own is a person asking what to watch, and the
# answer to that is a different kind of help.
WHAT_IS_GOOD = re.compile(
    r"\b(?:whats?|what\s+is|anything)\s+(?:good|worth\s+(?:seeing|watching|a\s+look))\b"
    r"|\bwhats?\s+(?:the\s+)?(?:new|latest)\s+(?:film|movie|play|show)\b"
    r"|\bwhat\s+(?:film|films|movie|movies|play|plays)\s+(?:is|are)\s+(?:on|showing|worth)\b"
    r"|\bwhats?\s+worth\s+(?:seeing|watching)\b")
WHATS_ON_LINES = (
    "Listings turn over every week and seats sell out quietly, so the venue's own page or a "
    "listings app is the only schedule that is right today: times, prices and what is left.",
    "That is this week's timetable, and it changes more often than a general answer could keep "
    "up with. The venue's own page or a listings app has the times, plus the number if you want "
    "to check seats.",
)
KICK_OFF_LINES = (
    "Kick-off moves for television and it can move twice, so the club's own page or a sports app "
    "is the one to trust - anything said from here could be a week out of date.",
    "The fixture list is the club's own, and televised games get moved late. Their page or a "
    "sports app has the time and says if it has been moved.",
)

# How busy it is: the queue at the tip, the wait at the surgery. Live in the same way, and only
# the place itself knows, so a call beats anything said from here.
BUSY = re.compile(r"\bhow\s+busy\b|\bis\s+(?:it|the\s+[a-z]+)\s+busy\b"
                  r"|\bhow\s+long\s+(?:is|are)\s+(?:the\s+)?(?:wait|queue|line)\b"
                  r"|\bwhats\s+the\s+(?:wait|queue|line)\b|\bwaiting\s+times?\b")
BUSY_LINES = (
    "A queue changes hour to hour, and nobody publishes it everywhere at once: one call settles "
    "it faster than anything I could guess, and their own page has a live wait if they keep one.",
    "It will be worse at the weekend and around school pick-up, but today's wait is only on "
    "their system. Ring them before you set off - the place itself is the only one that knows.",
)

# Prices of the things an operator sets - parking, a bus, admission - are live in the same way.
PRICE_ASK = re.compile(r"\bhow\s+much\s+(?:is|are|does|do|will)\b"
                       r"|\bwhats?\s+the\s+(?:price|charge|cost|fee|rate)\b")
# Free entry is a price too, and no operator is named: "is the museum free on sunday".
FREE_ASK = re.compile(
    r"\bis\s+(?:the\s+|a\s+)?[a-z' -]{2,24}\s+free\b"
    r"|\bis\s+(?:entry|admission|parking)\s+free\b"
    r"|\bis\s+there\s+a\s+charge\b"
    r"|\bpay\s+to\s+(?:park|get\s+in|go\s+in|enter|visit)\b"
    r"|\bdo\s+(?:i|we)\s+have\s+to\s+pay\s+(?:to|for\s+(?:a|an|the|any|my|our))\b")
# "Free" joins the word before it into one adjective: gluten free, dairy free, duty free, tax
# free. None of those is a price at a gate, so they keep whatever the composer had.
FREE_COMPOUND = frozenset("""
    gluten dairy sugar fat nut nuts wheat lactose caffeine msg toll duty tax hands care cruelty
    smoke contact peanut egg soya soya soy
""".split())
PRICE_THING = frozenset("""
    parking park bus buses train trains tube taxi cab admission entry entrance ticket tickets
    delivery postage post fee fees fare fares hire rental charge
""".split())
PRICE_LINES = (
    "Rates like that are set by whoever runs the place and they change with the season: their "
    "own site or one quick call has the figure they actually charge, and a map listing carries "
    "the number if there is no site.",
    "Admission and parking prices are set locally and move with the season, so the current one "
    "is on their website or through one call, and a map listing has the number.",
)

# Whether there is anything left: a sell-out, a table, a pitch, a place at the last minute. It is
# known to the place's own booking page and to nobody else, and it changes by the hour.
AVAIL = re.compile(
    r"\b(?:tickets?|seats?|tables?|rooms?|spaces?|places?|slots?|pitches?|appointments?)\s+left\b"
    r"|\b(?:are|is)\s+there\s+(?:any\s+|a\s+)?(?:tickets?|seats?|tables?|rooms?|spaces?|"
    r"pitches?)\b"
    r"|\b(?:is\s+it|are\s+they)\s+(?:fully\s+)?(?:booked\s+up|full|sold\s+out)\b"
    r"|\b(?:is|are|has|have|did|does|will)\b[^?]{0,20}?\bsold\s+out\b"
    r"|\bcan\s+(?:i|we)\s+(?:still\s+)?(?:get|book)\s+(?:a|any)\s+(?:table|seat|ticket|room"
    r"|space|pitch|slot)\b")
AVAIL_LINES = (
    "What is left is on their booking system rather than anywhere I can see, and it changes by "
    "the hour. Their booking page shows what is still free, and the box office settles a "
    "sell-out in a second.",
    "Anything still free is in their own system, sorry - it moves too fast for a general answer. "
    "Their booking page shows it, and ringing is quicker if you are on your way.",
)

# A figure or a date about the person's own area: the council holds it, and a map app does not.
LOCAL_AREA = re.compile(
    r"\b(?:my|our)\s+(?:town|village|area|county|streets?|roads?|ward|district|neighbourhood|"
    r"postcode|council|city)\b")
LOCAL_ASK = re.compile(r"\bhow\s+many\b|\bpopulation\b|\bwho\s+is\b|\bwhich\s+band\b|"
                       r"\bhow\s+do\s+i\s+find\b|\bwhat\s+is\s+the\s+population\b")
LOCAL_LINES = (
    "Figures about your own patch come from your council, and they publish them: their site has "
    "it - the box at the top takes your postcode - and one call to the main number works if the "
    "site buries it.",
    "Your council holds that and keeps it up to date. Their site has it, or one call to the main "
    "number answers it - the postcode does most of the work.",
)
# School term dates are the school's calendar rather than a fact about the world: the school's own
# site has the inset days, which are the part a general answer always gets wrong.
TERM_DATES = re.compile(r"\bterm\s+dates?\b|\binset\s+days?\b|\bacademic\s+year\b|\bwhen\s+do\s+"
                        r"(?:the\s+)?schools?\s+(?:break|finish|start)\b")
TERM_LINES = (
    "Term dates are the school's own calendar, and the inset days are the bit a general answer "
    "always gets wrong. The school's site has both, and the council lists every school's in one "
    "place if you need to compare.",
    "The school sets its own term dates and its own inset days. Their page has both, and the "
    "council's site collects them all if you are looking at more than one school.",
)

# Something near the person rather than in the world: only a map knows what is on their street.
NEARBY_AREA = re.compile(
    r"\bnear\s?(?:me|us|here)\b|\bround\s+here\b|\bnear\sby\b|\bnearby\b"
    r"|\bin\s+my\s+(?:area|town|village|city|street|road|postcode|neighbourhood)\b"
    r"|\bmy\s+(?:postcode|area|town|village)\b")
# "The shop near me shut early" is a remark, not a search: only a question or a request for one
# gets the map-app line, so the person telling the bot their news keeps its answer.
ASKS_LOCAL = re.compile(
    r"\bis\s+there\b|\bare\s+there\b|\bwhere\b|\bwheres\b|\bwhich\b|\bany\b"
    r"|\banywhere\b|\bcan\s+(?:i|we|you)\b|\bcould\s+(?:i|we|you)\b|\bdo\s+you\s+know\b"
    r"|\b(?:i|we)\s+(?:need|want|are\s+looking|am\s+looking)\b|\blooking\s+for\b"
    r"|\brecommend\b|\bfind\b|\bwhats\s+good\b|\bgood\s+(?:place|places|spot|spots)\b")
# "The nearest pharmacy" names a thing on their own street without saying "near me" at all; a
# nearest airport to Lisbon is a fact about the world, so "closest to" is left out.
NEAREST = re.compile(r"\b(?:nearest|closest)\s+(?!to\b)[a-z]+")
NEARBY_SERVICE = frozenset("""
    pharmacy chemist cashpoint atm supermarket shop store garage launderette laundrette dentist
    doctors surgery hospital petrol gym pool park school nursery vet takeaway chippy pub cafe
    restaurant bank tip
""".split())
DELIVER = re.compile(r"\bdeliver(?:y|s|ed)?\s+(?:to|in)\b|\bdeliver\s+to\s+my\b|"
                     r"\bdo\s+(?:they|you)\s+deliver\b")
DELIVER_LINES = (
    "Delivery depends on the postcode and the day, and only the shop's own checker knows it: put "
    "your postcode in on their site and it says yes or no in a second, with the earliest slot.",
    "That depends on the postcode, which their own delivery checker holds - it takes ten seconds "
    "with your postcode in, and it shows the earliest date too.",
)
NEARBY_LINES = (
    "What is near you depends on your postcode, so a map app is the one that knows: it lists the "
    "closest in order of distance, with today's hours and a phone number for each one.",
    "A map app puts them in order of distance and carries the phone number, which is faster than "
    "any list I could give you from here.",
)

# A method question ("how do i get a refund from a cancelled flight") is about the world and
# has an answer of its own; it is not a live status and not a form to fetch.
HOW_TO = re.compile(r"\bhow\s+(?:do|can|should|would)\s+(?:i|we)\b|\bhow\s+to\b|"
                    r"\bwhat\s+do\s+i\s+need\s+to\b|\bwhats\s+the\s+best\s+way\b")

# The office that issues a thing: a licence, a card, a copy of a record, the rules on a fire.
OFFICIAL_ASK = re.compile(
    r"\b(?:whats|what\s+is|what\s+are)\s+the\s+(?:law|rules?|legal\s+position|regulations?)\b"
    r"|\bis\s+it\s+(?:legal|allowed|illegal)\b|\bam\s+i\s+(?:allowed|legally)\b"
    r"|\bdo\s+i\s+need\s+(?:a|an|any|to)\b"
    r"|\bhow\s+do\s+i\s+(?:get|apply|renew|replace|register|order|book)\b"
    r"|\bhow\s+do\s+i\s+(?:check|find\s+out)\s+(?:if|whether|who|what)\b")
OFFICIAL_THING = frozenset("""
    licence license permit permission registration certificate copy record records badge card
    cscs dbs crb passport visa form application skip planning consent exemption grant benefit
    number registered register renewal certificate blue disabled
""".split())
# A question about the rules needs no thing of its own: the rules are what is being asked about.
RULES_ASK = re.compile(r"\b(?:law|legal|allowed|rules?|regulations?|illegal)\b")
# A board game has rules and no council: "what are the rules of uno" is not a question about the
# law. Nor is a bare "what are the rules", which names nothing to have rules about.
GAME = frozenset("""
    uno chess poker monopoly scrabble darts snooker dominoes cluedo risk rummy bingo
""".split())
ASK_STOP = frozenset("""
    what whats is are the a an it i we you do does to of on for in my our and if can could
    there be this that rule rules law legal allowed illegal regulations regulation about
""".split())
OFFICIAL_LINES = (
    "Anything with a form behind it is set by the office that issues it, and the fee and the "
    "paperwork change with the year. Their official page - GOV.UK for the national ones, your "
    "council for anything local - names what to send, what it costs and how long it takes.",
    "The form, the fee and the waiting time all come from the office that issues it, and they "
    "change. Their own page is the one to act on, and it says who to ring if your case does not "
    "fit the standard one.",
    "The rules differ by council and by country, so the version that counts is on the issuing "
    "office's own page: GOV.UK has the national forms, and the page names who to ring about the "
    "rest.",
)
# The rules themselves, rather than a form to fill in: the local version is the one that counts.
RULES_LINES = (
    "Rules like that are set locally and the byelaws differ from one council to the next: your "
    "council's site has them, plus the permit if one is needed, and their phone line answers the "
    "odd case.",
    "The rules differ by council and by country, so the local version is the only one worth "
    "acting on: the council's site has it, and GOV.UK has the national half.",
)


# Registering a death is a form for a person and nothing at all for a pet: a cat that died has
# no official page, so the honest hedge is better than a form and fee that does not exist.
PET = frozenset("""
    cat cats dog dogs kitten puppy pet pets hamster rabbit budgie parrot
""".split())
DIED = frozenset("""
    died dead death passing euthanised put down cremated
""".split())


# A report is not an ask. "roadworks on the m6 ruined my morning", "delays on the a38 every single
# day", "roadworks on the m6, absolute chaos" - the person is telling the bot how their week went,
# and the receipt ("I'm listening - say more if it helps") is what a friend says back. The status
# word and the road are both there, so without this the readings below turn a complaint into a
# live-travel note nobody asked for. A duration says how long it has been going on, which is what
# makes it a report; the same words with a question mark are still the ask.
A_REPORT = re.compile(
    r"\b(?:every\s+(?:single\s+)?(?:day|week|morning|evening|night|time)"
    r"|all\s+(?:week|weeks|month|months|year|day|days|morning|night|the\s+time)"
    r"|for\s+(?:weeks|months|days|ages|hours)"
    r"|since\s+(?:january|february|march|april|may|june|july|august|september|october|november"
    r"|december|last|monday|tuesday|wednesday|thursday|friday|saturday|sunday|easter|christmas|then)"
    r"|each\s+(?:day|week|morning)"
    r"|the\s+whole\s+(?:week|month|day)"
    r"|ruined|ruins|wrecked|wrecks|chaos|nightmare|fed\s+up|sick\s+of|so\s+tired|held\s+me\s+up"
    r"|made\s+me\s+late|cost\s+me|missed\s+my)\b")


def reads_as_a_report(text):
    """True when the line is telling the bot about something rather than asking about it."""
    said = " ".join(str(text or "").lower().split())
    return bool(said) and not said.endswith("?") and bool(A_REPORT.search(said))


def _words(clean):
    """The line as whole words, for the tests that only need to know one is present."""
    return re.findall(r"[a-z0-9'-]+", clean)


def pool(clean):
    """The lines for a question whose answer lives somewhere else, or None."""
    text = " ".join(str(clean or "").lower().split())
    if not text:
        return None
    said = set(_words(text))
    if reads_as_a_report(text):
        return None
    # Hours: a place named in the line, and an ask about when it opens or shuts.
    if ((HOURS_ASK.search(text) and (said & A_PLACE or "it" in said))
            or (LATE_ASK.search(text) and said & A_PLACE)):
        if not HOW_TO_OPEN.search(text) and not said & NOT_A_VENUE and not said & THE_PEOPLE:
            return HOURS
    # A kick-off, then what's on: both are timetables that change weekly.
    if KICK_OFF.search(text):
        return KICK_OFF_LINES
    if said & (ON_WORDS | ON_EVENT) and ON_ASK.search(text):
        return WHATS_ON_LINES
    # A recommendation asked about a venue's programme is the same timetable, so it wants the
    # same place: "what's good at the theatre this month" is not a question about taste.
    if said & ON_WORDS and WHAT_IS_GOOD.search(text):
        return WHATS_ON_LINES
    # Live travel: a way of travelling or a numbered road, and something wrong or due. A how-to
    # about travel ("how do i get a refund from a cancelled flight") is a method, not a status.
    if ((said & TRAVEL or ROAD.search(text)) and not HOW_TO.search(text)
            and not said & TRAVEL_CLAIM and ASKED.search(text)
            and not (STORY.search(text) and not OPENS_ASKING.search(text))
            and (said & STATUS or any(phrase in text for phrase in STATUS_PHRASES))):
        return TRAVEL_LINES
    # What an operator charges for something they run.
    if (PRICE_ASK.search(text) and said & PRICE_THING) or (
            FREE_ASK.search(text) and not said & FREE_COMPOUND):
        return PRICE_LINES
    if AVAIL.search(text):
        return AVAIL_LINES
    if BUSY.search(text) and said & A_PLACE:
        return BUSY_LINES
    # A figure about their own town: the council holds it, which is not a map app's job. The
    # town has to be theirs - "how many hours a day" on a road trip is not a council question.
    if LOCAL_AREA.search(text) and LOCAL_ASK.search(text):
        return LOCAL_LINES
    # Their street, or whether a shop will come to their postcode. A figure about their own area
    # is not about what is near it ("how many people live in my town" got the map-app line).
    if DELIVER.search(text):
        return DELIVER_LINES
    if TERM_DATES.search(text):
        return TERM_LINES
    if (NEARBY_AREA.search(text) and ASKS_LOCAL.search(text)) or (
            NEAREST.search(text) and said & NEARBY_SERVICE):
        return NEARBY_LINES
    # The office that issues it: only when a thing to be issued or a rule is named, so
    # "how do i get to sleep" and "how do i get better at chess" keep their own answer. A
    # question about the law or the rules needs no thing of its own: the rules are the thing.
    if OFFICIAL_ASK.search(text) and not (said & PET and said & DIED):
        if said & OFFICIAL_THING:
            return OFFICIAL_LINES
        if RULES_ASK.search(text) and not said & GAME and said - ASK_STOP:
            return RULES_LINES
    return None


# The loosest ask of all: no ask word and no verb, only a status word spent on the thing it is
# about - "delays on the a38", "roadworks on the m6", "disruptions on the northern line". In
# somebody's typing that is a question about today; in the composer's reading it is a remark, so
# the neutral pool files it and says "Got it." - a placeholder to the person who asked. The
# preposition is what keeps it honest: "traffic was awful", "roadworks made me late" and
# "strikes are a nightmare" are the story of a day and stay with the pool that reads stories.
A_STATUS_SPENT_ON = re.compile(
    r"^\s*(?:any\s+|the\s+)?(?:delays?|disruptions?|traffic|roadworks?|road\s+works|"
    r"cancellations?|strikes?|engineering\s+works)\s+"
    r"(?:on|at|near|around|by|into|outside|through)\b")


# A status word spent on something of their own is about that thing, not about today's
# travelling: "delays on my order" belongs to the shop, not to a journey planner.
NOT_THEIR_STATUS = re.compile(r"\b(?:my|our|order|parcel|delivery|claim|refund)\b")


def pool_over_a_receipt(clean):
    """The lines for a line the composer would otherwise meet with only the flat receipt.

    Kept apart from `pool` because the reading is deliberately looser: the only evidence of a
    question is a status word spent on a named road or line. It is consulted only where the reply
    is already the neutral receipt, so every pool above keeps its turn.
    """
    text = " ".join(str(clean or "").lower().split())
    if not text or not A_STATUS_SPENT_ON.search(text):
        return None
    if reads_as_a_report(text):
        return None
    # The reader below is anchored to a status word at the head of the line, so the article that
    # sometimes opens it ("the delays on the a38") comes off here rather than in the reader,
    # where it would widen every other kind too.
    bare = text[4:].strip() if text.startswith("the ") else text
    found = pool(bare)
    if found:
        return found
    # The reader above wants to recognise the thing after "on" as a service or a road, and some
    # of them it cannot: "cancellations on the 7am" names a train by its time. A status word
    # spent on a thing is the ask either way, so the operator's answer stands - unless the thing
    # is one of theirs, where the operator is not who holds it ("delays on my order").
    if NOT_THEIR_STATUS.search(bare):
        return None
    return TRAVEL_LINES


# The line after a gap: "roadworks on the m6" then "is it going to add an hour". The follow-up
# names nothing the reader above can hold - no road, no operator - and it reached the search
# hedge one turn after the bot had named the place that knows. A short question that carries a
# back-reference is about the same gap, and the same app still has it.
A_FOLLOW_UP = re.compile(
    r"^\s*(?:is|are|will|would|how\s+(?:long|much|bad|far)|what\s+about|and\b|"
    r"does|do)\b")
A_BACK_REFERENCE = re.compile(r"\b(?:it|that|they|them|those|this|the\s+same|still)\b")


def more_about_the_journey(clean, memory):
    """The travel answer again, for a follow-up to a turn findout just answered.

    Only the journey: hours, prices and the rest of the kinds have a follow-up that is a new
    question about the same place, and the pool for the previous kind would answer the wrong
    one. The bot's own last line is the test - if it came from somewhere else, this stands down.
    """
    text = " ".join(str(clean or "").lower().split())
    if not text or not A_FOLLOW_UP.search(text) or not A_BACK_REFERENCE.search(text):
        return None
    turns = [t for t in (memory.get("turns") or []) if t.get("bot")]
    if not turns or (turns[-1].get("bot") or "") not in TRAVEL_LINES:
        return None
    return TRAVEL_LINES


# A hedge is not always a gap. Some of the bot's own lines already say what the bot cannot see and
# send the person somewhere that can answer - "I can't look at a map from here, sorry. A map app
# puts them in order of distance" is the whole of what this file would say, said shorter. The
# reading here keeps those turns, so the pools above only ever replace a line that names nothing:
# it is the test for "already done", not a fact about the world.
#
# "Search" and "look it up" are deliberately not here. They are what the pools above exist to
# replace: a search engine is not a place that holds the hours of one shop, today's queue at one
# tip, or the form for one licence.
A_PLACE_NAMED = re.compile(
    r"\b(?:map app|maps|google maps|the council|council'?s?|gov\.uk|\.gov\b|government"
    r"|operator'?s?|journey planner|traffic service|road agency|roads agency|national rail"
    r"|pharmac(?:y|ist)|chemist|\bgp\b|doctor'?s|surgery|the ward|nurse|vet'?s?|veterinary"
    r"|their (?:own )?(?:site|website|web page|page|app|account|office|desk|number)"
    r"|the (?:official )?(?:site|website) of|official (?:page|site)"
    r"|box office|ticket office|the office that|issuing office|passport office|dvla"
    r"|registry office|landlord|letting agent|estate agent|employer|\bhr\b|payroll"
    r"|your bank|the bank|insurer|insurance company|the airline|the hotel|the venue"
    r"|the airline'?s?|one call|give them a ring|ring them|call them|their line)\b")
# The same, said as a route to a figure rather than as a place: "the number is on a map listing",
# "their page has the form", "the app has today's". One noun and one thing it holds.
HOLDS_IT = re.compile(
    r"\b(?:has|have|shows|lists|carries|publishes|updates)\b[^.]{0,30}"
    r"\b(?:number|form|fee|price|prices|hours|wait|times|schedule|status|page|listing)\b")


def says_where_to_look(reply):
    """True when a reply already names a place that holds what the person asked for."""
    said = " ".join(str(reply or "").lower().split())
    if not said:
        return False
    return bool(A_PLACE_NAMED.search(said) or HOLDS_IT.search(said))
