"""The things the bot cannot see, and the one place that does see them.

The floor of this bot is one reply for everything nobody knows, and on main that reply is the
honest shrug: "I'm not sure about that one, sorry - a quick search online will get you a solid
answer". It is honest, and it is useless to somebody who asked a question with a *place* behind
it. STYLE.md draws the line this module sits on:

    What time does the post office on Hill Road close today?
    I can't check live opening hours, sorry. Search for the branch online: its listing on a map
    app usually shows today's hours, holidays included.

Three things make that reply good, and none of them is in the shrug: it says what the bot cannot
do (check live hours), it names the one place that can (the branch's listing on a map app), and it
does not guess. The pool cannot do that for every line - it does not know what the line is about -
so this module reads the line for the *kind* of thing being asked about and gives the limit, the
place to look and, where it helps, one short question.

    is it on iplayer                      "I can't see what's on iPlayer from here, sorry..."
    what time is the last train to leeds  "...no live train times from me - a journey planner..."
    whats the best beach in cornwall      "...I don't know the beaches round there well enough..."
    how about moving to spain             "...it depends on your passport - gov.uk's living
                                           abroad pages and the country's own official site..."
    will it frost tonight                 "...no live weather from me - a forecast app has
                                           today's, hour by hour..."

Five kinds are here and no more, because each one has a *named* place that knows and that is what
makes the reply worth more than a search: a service's own catalogue, a journey planner, the place's
own listing, the government that writes the rules, and the sky over the person's own postcode.
Anything else stands down (returns None) and the floor answers as it did before.

Two more were added after the operator's note that a pointer on its own is not an answer: a choice
between two named things, and an ask for a shortlist. Neither names a subject - that is exactly
what the line does not have - so each one says the part that is true of every question of its
shape, what to look for and the usual first step, and then asks the one thing only the person
knows. That is STYLE.md's "what to look for" half of "Not knowing, honestly", and it comes before
any mention of where the rest lives.

This is a last resort and it is written to be one: `bot/modules/greeting.py` asks it alongside the
detail of an answer and the composer, and the composer is asked first, so a line any entry, any
module or the composer can answer never reaches this file. What it can lose is a line the shrug
would have got; what it cannot do is take a turn away from a better answer, or invent a fact to
fill the gap. Nothing here is a fact about the world: every reply says only what the bot cannot
check, what decides a thing of that kind, and where a person can find the rest.
"""
import re

from ..memory.facts import COUNTRIES

# Moving to one of these is a move at home: the paperwork for living abroad is not the answer.
HOME_NATIONS = frozenset("""england scotland wales britain uk ireland northern ireland""".split())
from . import pick

# The countries that are not the one whose council answers a bin or a pothole question. A named
# country is the cheapest way to know a thread has left the UK: "we live in spain now" carries no
# word `ABROAD` can see, and "what about the bins" after it is not a question for a council.
HOME_COUNTRIES = frozenset((
    "united kingdom", "england", "scotland", "wales", "northern ireland", "great britain",
    "britain", "uk", "ireland",
))
NOT_HOME_COUNTRIES = tuple(sorted(
    (name for name in COUNTRIES if name not in HOME_COUNTRIES), key=len, reverse=True))

# The services whose catalogue the bot cannot see. Named the way people type them, with the form
# the reply uses - "iplayer" is "iPlayer" on screen and "bbc" alone is not a service.
SERVICES = (
    ("iplayer", "iPlayer"), ("bbc iplayer", "iPlayer"), ("itv hub", "ITV Hub"),
    ("itvx", "ITVX"), ("itv", "ITV"), ("channel 4", "Channel 4"), ("all 4", "All 4"),
    ("4od", "All 4"), ("my5", "My5"), ("netflix", "Netflix"), ("prime video", "Prime Video"),
    ("amazon prime", "Prime Video"), ("disney plus", "Disney+"),
    ("disney+", "Disney+"), ("now tv", "Now TV"), ("nowtv", "Now TV"), ("apple tv", "Apple TV"),
    ("paramount", "Paramount+"), ("britbox", "BritBox"), ("hayu", "Hayu"), ("sky go", "Sky Go"),
    ("sky q", "Sky Q"), ("sky tv", "Sky"), ("sky cinema", "Sky Cinema"),
    ("sky sports", "Sky Sports"), ("spotify", "Spotify"), ("audible", "Audible"),
    ("youtube", "YouTube"),
)
# The ask that makes a service a lookup: whether the thing is on it. A fault ("netflix keeps
# stopping"), a password, a price or a subscription is another question, and 4 of the 10 lines in
# this file's test that name a service are one of those, so the availability shape is required.
# What is not this reading however it is asked: a fault, the money, the account, the choice.
NOT_AVAILABILITY = re.compile(
    r"\b(?:stopping|stops|stopped|buffer\w*|glitch\w*|not working|keeps? (?:cutting|freezing|"
    r"loading)|wont play|won't play|password|log ?in|sign ?up|account|cancel\w*|subscri\w*|"
    r"price|prices|cost|costs|cheaper|worth it|share|sharing|binge|download\w*|aeroplane|"
    r"plane|offline|recommend|any good|what to watch|something to watch|worth watch\w*|"
    r"turn (?:off|on)|settings|autoplay|auto play|notification\w*|episodes? (?:left|to go)|"
    # "anything funny on netflix" is asking to be told about a film, which is a recommendation
    # and not a lookup.
    r"(?:anything|something|whats|what's)\s+(?:\w+\s+){0,2}(?:funny|good|scary|sad|new|"
    r"decent|chilled|violent|easy)\b|"
    r"what (?:can|could|should) (?:i|we) (?:watch|see|stream)|"
    r"(?:anything|something) (?:good )?(?:on|to watch))\b", re.I)

# A journey the bot cannot time: the mode, and the ask that wants a time or a yes/no about one.
TRAVEL = {
    "train": ("train", "trains"), "trains": ("train", "trains"), "bus": ("bus", "buses"),
    "buses": ("bus", "buses"), "coach": ("coach", "coaches"), "tube": ("tube", ""),
    "underground": ("tube", ""), "metro": ("metro", ""), "tram": ("tram", "trams"),
    "ferry": ("ferry", "ferries"), "ferries": ("ferry", "ferries"),
}

# "how do i get to bristol from cardiff" names no train and is still a journey: the route is the
# question. Both ends are required, so "how do i get to sleep" and "how do i get to work" (which
# are about a thing and a habit) are not this reading.
# Both ends are required, so "how do i get to sleep", "get to work" and "get to the gym" - a
# thing and two habits - are not this reading. The "from" is what makes it a journey.
GET_FROM_TO = re.compile(
    r"\bhow (?:do|can|would|could) (?:i|we|you) (?:get|travel)\s+(?:to|from)\b[^?.]{0,30}\bfrom\b|"
    r"\bbest way (?:to|of) (?:get|getting|travel|travelling)\s+(?:to|from)\b[^?.]{0,30}\bfrom\b|"
    r"\bhow long (?:does it|will it|would it) take to (?:get|drive|travel|cycle|walk)\s+to\b"
    r"[^?.]{0,30}\bfrom\b|"
    r"\bhow (?:do|can|would|could) (?:i|we|you) (?:get|travel)\s+from\b[^?.]{0,30}\bto\b", re.I)
WANTS_A_TIME = re.compile(
    r"\b(?:what time|whatt?ime|how long|last|first|next|earliest|latest|timetable|doable|"
    r"won'?t make|is there a|are there any|how often)\b", re.I)
# "the last train to leeds" is this reading. A train that is late, a ticket price, a seat and a
# season ticket are all questions with an answer of their own, and the bot has them.
NOT_A_JOURNEY = re.compile(
    r"\b(?:delayed|delay|cancelled|cancel|refund|ticket price|how much is .{0,20}ticket|"
    r"season ticket|railcard|strike|replacement bus|sleeper|i'?m on (?:the|a) "
    r"(?:train|bus)|on the (?:train|bus)|lost property|left (?:my|her|his) \w+ on)\b", re.I)

# A pick in a place: the thing to pick, and the noun the reply uses for it.
PICKS = (
    (("beach", "beaches"), "beaches"),
    (("pub", "pubs"), "pubs"),
    (("restaurant", "restaurants", "place to eat", "places to eat", "eatery"), "restaurants"),
    (("cafe", "cafes", "coffee shop", "coffee shops"), "cafes"),
    (("walk", "walks", "hike", "hikes"), "walks"),
    (("park", "parks"), "parks"),
    (("market", "markets"), "markets"),
    (("museum", "museums", "gallery", "galleries"), "museums and galleries"),
    (("chippy", "chippies"), "chip shops"),
    (("thing to do", "things to do", "day out", "day trip"), "things to do"),
)
# A shop's own facts - what it has, what it charges, when it delivers - are the shop's to know,
# and the bot has no window on any of them. The name is what makes the reply worth more than a
# search: "how long does aldi delivery take" gets the shop and the place on its site, not a shrug.
SHOPS = (
    ("aldi", "Aldi"), ("lidl", "Lidl"), ("tesco", "Tesco"), ("asda", "Asda"),
    ("sainsbury's", "Sainsbury's"), ("sainsburys", "Sainsbury's"), ("morrisons", "Morrisons"),
    ("waitrose", "Waitrose"), ("iceland", "Iceland"), ("co-op", "the Co-op"), ("coop", "the Co-op"),
    ("boots", "Boots"), ("superdrug", "Superdrug"), ("argos", "Argos"), ("amazon", "Amazon"),
    ("ebay", "eBay"), ("ikea", "IKEA"), ("currys", "Currys"), ("screwfix", "Screwfix"),
    ("b&q", "B&Q"), ("b and q", "B&Q"), ("homebase", "Homebase"), ("wickes", "Wickes"),
    ("halfords", "Halfords"), ("decathlon", "Decathlon"), ("sports direct", "Sports Direct"),
    ("john lewis", "John Lewis"), ("marks and spencer", "Marks and Spencer"), ("m&s", "M&S"),
    ("poundland", "Poundland"), ("home bargains", "Home Bargains"), ("the range", "The Range"),
    ("dunelm", "Dunelm"), ("asos", "ASOS"), ("wickes", "Wickes"),
)
SHOP_ASK = re.compile(
    r"\b(?:how long|how much|do they|do you|does it|can i|when|delivery|deliver|in stock|"
    r"stock|return|returns|refund|click and collect|collect|charge|postage|warranty|"
    r"guarantee|trade ?in|price|prices|cost)\b", re.I)
# The word that makes a pick word a place is the company it keeps: "a good beach read", "where
# should i park the car" and "the best way to walk the dog" are a book, a car and a dog, and a
# list of beaches, car parks and walks is the wrong answer to all three.
PICK_NOT = {
    "beach": re.compile(r"\b(?:read|reads|book|books|novel|towel|body|volleyball|ball|hut|"
                        r"huts|wedding|holiday\s+read)\b", re.I),
    "park": re.compile(r"\b(?:the car|my car|your car|the van|the bike|it there|carefully|"
                       r"properly|legally)\b", re.I),
    "walk": re.compile(r"\b(?:the dog|my dog|to work|to school|home|back|the kids to|"
                       r"take|taking|wear|wearing|bring|bringing|pack|packing|carry|boots|"
                       r"shoes|rain|wet|long|short|slow|fast|bit of a)\b", re.I),
    "market": re.compile(r"\b(?:the car|to buy|flog|sell)\b", re.I),
    "thing to do": re.compile(r"\b(?:with it|with them|with the|today|tonight|now|this evening|"
                              r"picnic|take|bring|pack)\b", re.I),
    "restaurant": re.compile(r"\b(?:wear|wearing|wore|dress|order|book a table|booking)\b", re.I),
    "chippy": re.compile(r"\b(?:order|nice from|to have|whats nice|what is nice)\b", re.I),
}
# A pick is a pick *in a place*: without one the question is "what should i do with half an hour",
# which is not a list of places to go. The place can be on the turn before this one ("we're going
# to cornwall in august" then "any good beaches for the kids").
A_PLACE = re.compile(
    r"\b(?:in|near|around|round|at|by|beside|from|to|outside|inside)\s+"
    r"(?!eat\b|go\b|walk\b|do\b|take\b|get\b|see\b|find\b|pick\b|order\b|book\b|be\b|"
    r"have\b)[a-z]", re.I)
WANTS_A_PICK = re.compile(
    r"\b(?:best|good|nice|decent|any good|recommend|worth|where should|what should|"
    r"suggest|anywhere|favourite|favorite|top)\b", re.I)

# A day out is not a pick the bot can be wrong about: it cannot name a beach or a museum, but the
# shape of a day and the question that decides it are honest and useful, and it is the follow-up
# its own invitation asks for ("where to stay or what to do while you are there?").
THINGS_TO_DO_POOL = (
    "I don't know the place well enough to name things, so here is the shape instead: one thing "
    "worth the journey out, one long lunch, and the rest of the day left loose. What do you "
    "usually enjoy doing?",
    "Nothing specific from me, sorry - naming places I have not been to would be guessing. A day "
    "that works most places is one big thing in the morning and nothing booked after it. Are "
    "you after coast and walking, or food and towns?",
    "I can't recommend places I have not been to. What I would do is pick the one thing you "
    "would be sorry to miss and plan the day round that. What sort of thing do you like doing?",
)
# A day out asked about the place the conversation is already in: "what should i do there",
# "anything good to do while we are there", "what should we see in rome". The line names the
# thing wanted (a day) and not the place, because the place was named a turn or two ago - the
# same follow-up the pick reading above is written for, one step wider (a day, not a beach).
# The two shapes of the ask: the thing wanted ("anything to do there", "things to do with the
# kids") and the open question ("what should we do there", "what should i see in rome").
WANTS_A_THING_DONE = re.compile(
    r"\b(?:what|anything|something|where)\b[^?.!]{0,18}\b(?:to do|to see|to visit)\b|"
    r"\b(?:things|stuff) to do\b", re.I)
ASKS_WHAT_TO_DO = re.compile(
    r"\bwhat (?:should|shall|can|could|do) (?:i|we|you) do\b|"
    r"\bwhat (?:should|shall|can|could) (?:i|we|you) (?:see|visit)\b|"
    r"\bwhats there to do\b|\bwhat is there to do\b", re.I)
WANTS_A_DAY_OUT = re.compile(
    WANTS_A_THING_DONE.pattern + "|" + ASKS_WHAT_TO_DO.pattern, re.I)
# "what should i do about my knee", "what can i do with an old laptop" and "what should i do
# tonight" are not a day out: an ask about a thing, and a line with no place in it at all, both
# stay with whatever answers them. The "with" half only stands a *do*-ask down: "anything to do
# with the kids" is the day out, and "what should i do with the kids" is the question about the
# thing in hand that another card answers.
DAY_OUT_NOT = re.compile(
    r"\b(?:about|to (?:sleep|stop|help|get|fix|make|keep)|for (?:my|the) )|"
    # a day at home is the house's business, not a place to visit
    r"\b(?:in|at|round|around) the (?:morning|afternoon|evening|night|weekend|meantime|garden|"
    r"kitchen|office|house|home|shed|garage|bedroom|bathroom|flat|car|shower|bath)\b", re.I)
A_THING_IN_HAND = re.compile(
    r"\bwith (?:it|them|him|her|this|that|an?|a)\b|"
    # a group of people is not a thing in hand: "what should i do with the kids" away for a week
    # is the day out, and "what should i do with my knee" is not
    r"\bwith (?:the|my) (?!kids|children|family|parents|boys|girls|toddler|baby|dog|"
    r"grandparents|grandchildren|niece|nephew|in-laws)\w+", re.I)
# "there" and "here" are the place: the line has no name in it, and the thread does.
A_PLACE_THERE = re.compile(r"\b(?:there|here|nearby|round here|around here)\b", re.I)
# The ask on its own, with no place word at all: "im going to spain in july" then "what should we
# see". It is the same follow-up as "what should we see there", and the trip in the thread is what
# makes it one.
A_BARE_DAY_OUT = re.compile(
    r"^\W*(?:(?:so|and|ok|okay|right|then|also|but)[\s,]+)*"
    r"(?:what|anything|something)\b[^?.!]{0,18}\b(?:to do|to see|to visit)\b|"
    r"^\W*(?:(?:so|and|ok|okay|right|then|also|but)[\s,]+)*"
    r"(?:things|stuff) to do\b|"
    r"^\W*(?:(?:so|and|ok|okay|right|then|also|but)[\s,]+)*"
    r"(?:what|where) (?:should|shall|can|could|do) (?:i|we|you) (?:do|see|visit)\b", re.I)
# The line that put a trip on the table: a place the person is going to, which is what "there"
# means for the turns after it.
A_TRIP_BEFORE = re.compile(
    r"\b(?:going to|going away|off to|flying to|driving to|heading to|travelling to|traveling to|"
    r"holiday|holidays|trip to|weekend in|week in|fortnight in|visiting|booked|days in)\b", re.I)
# A visit to see somebody, or somewhere nobody goes for a day out: "visiting my mum in hospital"
# then "what should i do there" is the ward's question, not a list of things to see.
NOT_A_DAY_OUT_PLACE = re.compile(
    r"\b(?:hospital|doctors?|dentist|gp|clinic|ward|surgery|a&e|court|work|school|nursery|"
    r"college|uni|university|interview|funeral|wedding|christening|prison|jail|care home|"
    r"vets?|physio|therapist|my mum|my dad|my sister|my brother|my son|my daughter|my kids|"
    r"my gran|my nan|my grandma|my grandad|my husband|my wife)\b", re.I)

# The rules that depend on who you are, split by who writes them: an official site about being
# somewhere else, and the council that decides a local rule.
# Moving is only a country when there is somewhere to move *to*: "move the money", "moving my
# photos to a new phone" and "change my address after moving" are not visa questions.
# A time after "to" or "in" is not a country: "my landlord says we have to move out in two
# months" put "move ... in two months" into the branch below, and three turns later "who do i
# write to" was answered with the gov.uk living-abroad pages. A move *out* is a tenancy, and a
# date, a month or "next year" names no destination at all.
A_TIME_AFTER = (
    r"(?!\s*(?:\d+|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|"
    r"a\s+few|few|a\s+couple|next|this|last|the\s+(?:next|new|coming|end)|"
    r"january|february|march|april|may|june|july|august|september|october|november|"
    r"december|spring|summer|autumn|winter)\b)")
ABROAD = re.compile(
    r"\b(?:abroad|overseas|emigrat\w*|expat\w*|visa|residency|passport for|work permit|"
    r"right to (?:live|work)|liv(?:e|ing) abroad|work(?:ing)? abroad)\b"
    r"|\b(?:relocat|retir|buy(?:ing)? (?:a|an) (?:house|flat|place))\w*\b[^?.]{0,25}"
    r"\b(?:to|in|abroad)\b" + A_TIME_AFTER +
    r"|\bmov\w*\b(?!\s*out\b)[^?.]{0,25}\b(?:to|in|abroad)\b" + A_TIME_AFTER, re.I)
# The words that make "move ... to" be about a thing rather than a country.
A_THING_NOT_A_PLACE = re.compile(
    r"\b(?:phone|mobile|laptop|computer|pc|tablet|account|money|funds|savings|isa|pension|bin|"
    r"box|boxes|photos?|files?|data|number|direct debit|standing order|everything|furniture|"
    r"house|flat|home|office|job|team|city|town|area|school|bedroom|kitchen)\b", re.I)
# "how do i ask about working abroad" asks how to raise it, not what the paperwork needs.
NOT_THE_PAPERWORK = re.compile(
    r"\b(?:how do i (?:ask|raise|bring (?:it )?up|mention|broach)|who do i ask|"
    r"ask (?:my|your|the) (?:boss|manager|employer)|talk to (?:my|your) (?:boss|manager)|"
    r"send(?:ing)? (?:money|cash)|transfer(?:ring)? (?:money|cash)|ripped off|scam\w*|"
    r"how much (?:money|cash) (?:to|can)|"
    # "moving in with my boyfriend" is a person, not a country, and roaming charges are the
    # phone's business rather than a passport's.
    r"mov(?:e|ing|ed) (?:in|on)\b|"
    r"(?:phone|mobile).{0,25}(?:charges?|roaming|data|contract|plan))\b", re.I)
# What "move" is about when it is not a country: the house, the job and the town the person
# already lives in, which is not a visa question.
MOVING_HOUSE = re.compile(
    r"\b(?:house|flat|home|office|job|team|city|town|area|neighbourhood|school)\b", re.I)
# The council is named, or the ask is the one thing everybody means by "the council" without
# saying it: whether they may park where they are thinking of parking. "How do i clean my bin" and
# "how do i write a letter to my landlord" are not council questions, and the bot has answers.
COUNCIL_WORD = re.compile(
    r"\b(?:council|councils|council tax|local authority|permit|planning permission|byelaw\w*|"
    r"blue badge|housing benefit|bulky waste|licensing|premises licence|taxi licence)\b", re.I)
PARKING_RULE = re.compile(
    r"\b(?:park|parking)\b[^?.]{0,30}\b(?:allowed|legal|illegal|ok|okay|fine|ticket|permit|"
    r"charge|charges|charged|free|sunday|sundays|resident\w*|restriction\w*|badge|disabled)\b|"
    # The words in the other order: "is it legal to park on the pavement", "am i allowed to park
    # here on sundays". The rule is the same local one, and reading only the first order sent
    # both to the shrug.
    r"\b(?:allowed|legal|illegal|ok|okay|fine|against the rules)\b[^?.]{0,25}\bpark\b|"
    r"\b(?:can|could|am i allowed to|are we allowed to|where can i|where should i|is it ok to|"
    r"is it okay to)\b[^?.]{0,20}\bpark\b", re.I)
WANTS_THE_RULES = re.compile(
    r"\b(?:can i|could i|do i|does it|how do i|how can i|what do i|what are the|whats the|"
    r"what's the|am i allowed|is it (?:allowed|legal|ok|okay|possible)|are we allowed|"
    r"will i|do we|who do i|where do i|how much is the|"
    # "how about moving to spain" asks the same question as "can i move to spain": the subject
    # is the move, so the shape that opens with the subject instead of the verb counts too.
    r"how about|what about|thoughts on|what do you think (?:of|about)|is it easy to|"
    r"whats it like to|what's it like to|should we)\b", re.I)

# One short question at the end of a reply is a friend's move, not a form: it gives the person
# somewhere to put the part of the question the bot did not get. Only one reading uses it, and only
# where the answer genuinely depends on a detail (which service, which journey, what they want).
SERVICES_POOL = (
    "I can't see what's on {service} from here, sorry. Its own search settles it in seconds, and "
    "says whether the thing is included or to pay for.",
    "I can't check {service}'s catalogue, sorry. Typing the title into its search is the quickest "
    "way to know whether it is there today.",
    "No access to {service} from here. Its own search will say whether it has it, and whether that "
    "is a rental or part of the subscription.",
)
JOURNEY_POOL = (
    "I can't see live {mode} times from here, sorry. A journey planner will have today's, "
    "cancellations included - where are you starting from, and when do you need to be there?",
    "No live {mode} times from me, sorry. The operator's app or a journey planner has the real "
    "ones - tell me the two ends and the time you have to be there and I'll help you plan around "
    "it.",
)
ROUTE_POOL = (
    "I can't see live times or routes from here, sorry. A journey planner has today's options door "
    "to door - where are you going from, and when do you need to be there?",
    "No timetables from me, sorry. A journey planner is the one that knows the real times between "
    "two places - tell me the two ends and the day and I'll help you pick.",
)
PICK_POOL = (
    "I can't vouch for {thing} somewhere I have never been, so a pick from me would be a guess. A "
    "map app's reviews are the honest way to do it - say what matters and I'll help you narrow it "
    "down.",
    "Nothing reliable from me on {thing} I have not been to, sorry. Sorting a map app's reviews "
    "by what you need, or asking in a local group, beats a guess.",
)
SHOP_POOL = (
    "I can't see {shop}'s stock, prices or delivery times from here, sorry. Its own site has them, "
    "worked out for your postcode.",
    "That is {shop}'s own to know - I have no window on its stock or charges. Its site has the "
    "answer, and the checkout tells you before you pay.",
)
ABROAD_POOL = (
    "I can't tell you what the paperwork needs - it depends on your passport and what you would be "
    "doing there. The gov.uk pages on living abroad and the country's own official site are the "
    "two that count.",
    "That is one for the official pages rather than me: it turns on your nationality and your "
    "plans. gov.uk's living abroad guidance, then the destination's own government site, are the "
    "ones to read.",
)
# The sky is the one reading here that is not a place at all: the forecast is live information
# about where the person is standing, and the bot has no window on it. A forecast app or a
# national weather site does, and it is worked out for their own postcode, which is the part a
# general answer cannot give. The pool says only that: no invented weather, no guess at the week.
WEATHER_POOL = (
    "I can't check the forecast from here, sorry - no live weather in me. A weather app has "
    "today's for your postcode, hour by hour, and the week ahead when you are planning.",
    "No live weather from me, sorry. A forecast app or the national weather site has what is "
    "actually coming where you are - that is the part I cannot see.",
)
# The sky as the subject of an ask: "will it rain", "is it going to be icy", "is it foggy",
# "will it be frosty on monday", "is there a frost tonight". The article is refused after "it"
# so "is it a cold or hayfever" stays the illness it is, and the "is there" branch names only
# the weather itself, so "is there a cold going round" is not read as the sky either. A day word
# is not required: "will it rain" and "will it rain on saturday" are one question.
A_SKY_ASK = re.compile(
    r"\b(?:will|would|is|are|does|do|should|might|shall|can|could)\s+(?:it|we|they)\s+"
    r"(?:(?:going\s+to|gonna|meant\s+to|likely\s+to|supposed\s+to)\s+)?"
    r"(?:be\s+|get\s+|stay\s+|turn\s+)?"
    r"(?:raining|rainy|rain|snowing|snowy|snow|frost|frosty|freezing|freeze|thaw\w*|icy|ice|"
    r"hail|hailing|sleet|foggy|fog|misty|mist|windy|gusty|gusts|thunder|stormy|storm|sunny|"
    r"sunshine|cloudy|drizzle|drizzling|showers?|humid|muggy|warm|cold|hot|chilly|mild)\b"
    r"|\b(?:is|will|are)\s+there\s+(?:a\s+|an\s+|any\s+|much\s+)?"
    r"(?:frost|ice|snow|rain|hail|sleet|fog|mist|wind|showers?|sun|thunder|storm)\b"
    # The same ask with the forecast said in it: "is there going to be a storm", "will there be
    # frost tonight". The shape above reads "is there a storm" and not these, so both reached the
    # floor and got the search hedge, which is the one reply that helps nobody on a phone.
    r"|\b(?:is|are|will)\s+there\s+(?:going\s+to\s+be|gonna\s+be|likely\s+to\s+be|be)\s+"
    r"(?:a\s+|an\s+|any\s+|much\s+)?"
    r"(?:frost|ice|snow|rain|hail|sleet|fog|mist|wind|showers?|sun|thunder|storms?|"
    r"heat|heatwaves?)\b"
    r"|\b(?:any|much)\s+(?:chance|risk|sign)\s+of\s+(?:a\s+|any\s+)?"
    r"(?:frost|ice|snow|rain|sleet|hail|fog|wind|thunder|showers?)\b"
    r"|\b(?:are|is|will)\s+we\s+(?:due|in\s+for)\s+(?:a\s+|any\s+|some\s+)?"
    r"(?:frost|ice|snow|rain|sleet|hail|fog|wind|thunder|showers?|storm|sun)\b", re.I)
# A reading of a thing, not of the sky: the oven's heat, the fridge, the car's engine. "Will it
# be hot in the oven" is a roast, and the entries for those have the answer.
A_SETTING = re.compile(
    r"\b(?:oven|grill|hob|fridge|freezer|microwave|kettle|boiler|radiator|cooker|washing "
    r"machine|tumble dryer|dishwasher|iron|shower|bath|sauna|engine|car|van|room|bedroom|"
    r"house|flat|dough|batter|sourdough)\b", re.I)
COUNCIL_POOL = (
    "I can't check your council's rules from here, sorry - they differ from one to the next. Its "
    "own site has the rule and the form, and the phone line will tell you which applies to you.",
    "That depends on where you live, so I would not guess. Your council's own site is the one that "
    "decides it, and it has the form.",
)

# The other half of STYLE.md's "Not knowing, honestly": a limit is worth nothing on its own.
# "A quick search online will get you a solid answer" is all the shape-only questions got on main,
# and it names nothing about the question - not what to check, not the first step. Two shapes have
# nothing else: a choice between two named things, and an ask for a shortlist. Neither names a
# subject the bot can look up, which is exactly why the reply has to carry the part that is true of
# every question of that shape - what decides it and the usual first step - and then ask for the
# one thing only the person knows.
CHOICE_POOL = (
    "Decide it on the one thing it must do well for you and compare only on that; the rest of "
    "the difference rarely matters. What must it do well?",
    "What settles these is fit rather than quality, so name the job it has to do and the limit you "
    "cannot go past - money, space or time. Which of those is tighter?",
    "When two are close, what separates them is how they are in use rather than on paper. What "
    "will you use it for most?",
)
SHORTLIST_POOL = (
    "A shortlist needs the thing you are starting from: what you are choosing between, and the one "
    "limit you cannot go past. Give me those two and I will put three or four in order.",
    "I can narrow it once I know what is on the table and what would make one of them useless to "
    "you. What is on the table?",
    "The useful part is what rules one out - money, timing, effort, or a line you will not cross. "
    "Tell me that and what you are choosing from.",
)

# A form is not a thing a shop near you sells: it comes from the organisation that wants it, and
# that is the part the bot does know about paperwork even when it cannot see which office it is.
# Getting one and sending one back have different answers, so they are read apart.
FORM_FROM_POOL = (
    "The form comes from the organisation that wants it, and their own site has it under the name "
    "of the thing you are applying for. Their contact page will post one if it is not there. "
    "Which organisation is it?",
    "Start from the letter or page that asked you: it names the office, and that office's site has "
    "the form to download or to fill in online. Their number can post one out. Do you still have "
    "it?",
)
FORM_TO_POOL = (
    "It goes to the address printed on the form itself - not to a general office - and a photo of "
    "it before it goes is what settles a dispute later. Which one is it?",
    "The letter that came with it names the office and the address to return it to; if it is "
    "missing, their contact page has one and a ring will confirm which. Do you have the letter?",
)

def _said(text):
    return str(text or "").lower()


def _the_line_before(memory):
    """What the person said in the last few turns, or "" on the first turn.

    A follow-up names what is being asked about and not where: "we're thinking of moving to spain"
    then "what paperwork do i need", and "we're going to cornwall in august" ... then "any good
    beaches for the kids" are one question in two turns, and the second turn alone has no country
    and no place in it. Only the kind is read from the earlier lines, never the answer, and the
    last three are enough for a person to have changed the subject.
    """
    if not isinstance(memory, dict):
        return ""
    turns = [turn for turn in (memory.get("turns") or []) if isinstance(turn, dict)]
    said = [str(turn.get("user") or "").lower() for turn in turns[-3:]]
    return " ".join(said)


def _named_service(said):
    """The service a line names, as (the word in the line, the name on screen), or ("", "").

    The longest name wins, because "bbc iplayer" and "iplayer" are the same service and "sky go"
    is a narrower thing than "sky".
    """
    best = ""
    for word, shown in SERVICES:
        if len(word) > len(best) and re.search(r"\b" + re.escape(word) + r"\b", said):
            best, chosen = word, shown
    return (best, chosen) if best else ("", "")


def _about_a_service(said, understood):
    word, service = _named_service(said)
    if not word or NOT_AVAILABILITY.search(said):
        return None
    # The service has to be named in a frame that makes it a platform - "on iplayer", "does netflix
    # have it", "netflix's search" - and the line has to ask something. "who is the prime minister
    # of australia" and "why is the sky blue" name a prime and a sky, and the old entries for
    # "prime" and "sky" answered both with a catalogue.
    platform = re.compile(
        r"\b(?:on|from|at|via|in)\s+(?:the\s+)?" + re.escape(word) + r"\b|"
        r"\b" + re.escape(word) + r"(?:'s|s')\b|"
        r"\b" + re.escape(word) + r"\s+(?:has|have|got|shows|show|streams|stream|adds)\b|"
        r"\b(?:does|do|did|is|are|has|have)\s+(?:the\s+)?" + re.escape(word) + r"\b", re.I)
    if not platform.search(said):
        return None
    if not re.search(r"\b(?:is|are|was|were|isnt|arent|any|anything|do|does|did|can|could|where|"
                     r"how)\b", said, re.I):
        return None
    return pick(SERVICES_POOL, understood or {}, said).replace("{service}", service)


def _about_a_shop(said):
    """The shop a line asks about, in the form the reply uses, or "".

    The name alone is not the shop: "my boots creak when i walk" is about footwear and "boots"
    there is a pair of them, so the name has to be in a frame that makes it a shop - at, in, from,
    to, "does", or its own possessive.
    """
    best = ""
    for word, shown in SHOPS:
        frame = re.search(
            r"(?:\b(?:at|in|from|to|does|do|did|is|are|asda's|with)\s+(?:the\s+)?"
            + re.escape(word) + r"\b)|(?:\b" + re.escape(word) + r"(?:'s|s')\b)", said)
        if frame and len(word) > len(best):
            best, chosen = word, shown
    if not best or not SHOP_ASK.search(said):
        return ""
    return chosen


def _about_a_journey(said):
    if GET_FROM_TO.search(said) and not any(
            re.search(r"\b" + re.escape(word) + r"\b", said) for word in TRAVEL):
        return "route"
    for word, (single, plural) in TRAVEL.items():
        # The mode is a noun only when something in front of it makes it one: "i train next to
        # the window", "bus it over" and "i tube to work" are the verb.
        noun = re.search(
            r"\b(?:the|a|an|my|your|our|his|her|their|this|that|these|those|last|next|first|any|"
            r"every|no|by|take the|catch the|get the)\s+" + re.escape(word) + r"\b", said)
        if not noun:
            continue
        if NOT_A_JOURNEY.search(said) or not WANTS_A_TIME.search(said):
            return None
        # The same word is a train set, a bus pass and a flight of stairs: only a line that asks
        # for a time or a journey is this reading.
        if word in ("tube", "metro"):
            mode = "Tube"
        elif plural and re.search(r"\b" + re.escape(plural) + r"\b", said):
            mode = plural
        else:
            mode = single
        return mode
    return None


# A follow-up that names only a subject and asks nothing: "what about the schools", "and the
# worktop", "what about the food there". There is no verb in it, so the floor has nothing to work
# with and the person gets the search shrug for a question they can already see is about one
# thing - but the noun still says which kind it is, and the honest answer is the same limit and
# the same place that knows that the full question would have got.
ONLY_A_SUBJECT = re.compile(
    r"^(?:and|but|ok|okay|so|also)\s+what\s+about\b|^what\s+about\b|"
    r"^(?:and|but|also)\s+(?:the|my|your|a|an|those|these|that)\b", re.I)
# A bare "and the food" is a subject; "and the food was cold" is a report and "also my back hurts
# from the drive" is a complaint. Only a line with no verb in it is the follow-up.
HAS_A_VERB = re.compile(
    r"\b(?:is|are|was|were|has|have|had|does|do|did|can|could|will|would|should|hurts?|feels?|"
    r"seems?|goes|went|keeps?|works?|tastes?|smells?)\b", re.I)
# A line that names a subject and then asks its own question - "what about white wine, does that
# come out easier", "what about the drive down, is it awful in august" - is not this shape: it
# says what it wants and is read as that.
A_QUESTION_OF_ITS_OWN = re.compile(
    r"[?,]\s*(?:is|are|was|were|does|do|did|can|could|will|would|should|how|why|when|where|what|"
    r"who|which)\b|\b(?:is|are|does|do|did|can|could|will|would|should)\s+"
    r"(?:it|that|they|this|i|we|you|he|she)\b", re.I)
# Five words is a subject; longer is a sentence with a subject in it.
A_FEW_WORDS = 5
# The words that only point at the subject: "the food there", "a pub near here", "the beaches
# like there". Everything else in the line has to be the noun itself, or the subject is not the
# whole of what the person said - "what about burnt bbq food" is a complaint about a barbecue.
POINTING_WORDS = frozenset((
    "the", "a", "an", "any", "some", "my", "your", "our", "their", "its", "his", "her", "these",
    "those", "that", "this", "near", "nearby", "here", "there", "around", "round", "about", "in",
    "on", "at", "to", "for", "like", "instead", "then", "too", "and", "or", "please", "though",
))
# The nouns that settle the kind on their own, because one place keeps the answer for that noun
# whichever question is being asked about it: a bin, a library and a patch of fly-tipping are all
# the council's, and a beach, a pub and a market are all somewhere a map app has reviews of.
SUBJECT_KINDS = (
    ("council", re.compile(
        r"\b(?:bins?|rubbish|recycling|refuse|potholes?|librar(?:y|ies)|leisure cent(?:re|er)|"
        r"bulky waste|council tax|parking permits?|green waste|fly ?tipping|grass cutting|"
        r"school places|school catchments?|catchment areas?|catchments?|admissions|schools?)\b",
        re.I)),
    ("map", re.compile(
        r"\b(?:food|restaurants?|pubs?|cafes?|coffee shops?|takeaways?|take-aways?|beaches|walks|"
        r"things to do|days? out|markets?|parks?|chippy|chip shops?)\b", re.I)),
    ("journey", re.compile(
        r"\b(?:trains?|buses|coach|trams?|ferr(?:y|ies)|the drive|traffic)\b", re.I)),
)
# The word the pick line needs: a question about "the food there" is a question about
# restaurants, and one about "the chippy" is about chip shops.
_SUBJECT_LABEL = {
    "food": "restaurants", "restaurant": "restaurants", "restaurants": "restaurants",
    "pub": "pubs", "pubs": "pubs", "cafe": "cafes", "cafes": "cafes", "coffee shop": "cafes",
    "coffee shops": "cafes", "takeaway": "takeaways", "takeaways": "takeaways",
    "take-away": "takeaways", "take-aways": "takeaways", "beach": "beaches",
    "beaches": "beaches", "walk": "walks", "walks": "walks", "thing to do": "things to do",
    "things to do": "things to do", "day out": "days out", "days out": "days out",
    "market": "markets", "markets": "markets", "park": "parks", "parks": "parks",
    "chippy": "chip shops",
    "chip shop": "chip shops", "chip shops": "chip shops",
}
# A subject about a drive is a question about travel, so the journey line reads "travel times"
# rather than "drive times".
_SUBJECT_MODE = {"trains": "train", "buses": "bus", "trams": "tram", "ferries": "ferry",
                 "coach": "coach", "the drive": "travel", "traffic": "travel"}


def _a_country_not_home(text):
    """The first country in the line that is not this one, or "".

    Read from the knowledge base's own country list rather than a short list of holiday names,
    because the thread can leave the UK in any direction and a council is then the wrong body.
    """
    for name in NOT_HOME_COUNTRIES:
        if re.search(r"\b" + re.escape(name) + r"\b", text):
            return name
    return ""


def _about_the_subject_named(said, understood, before=""):
    """The limit and the place that knows, for a follow-up that names only a subject.

    "what about the schools" after a house move is a question about admissions, and it went to
    the search shrug because there is no verb to read. The noun is the whole of it, and it names
    a kind with a place behind it, so the answer here is the same one the long version of the
    line would have got. Anything else - a subject nobody keeps ("what about the parsnips",
    "what about a stainless steel one") - is left to the floor, which is where it was.
    """
    lead = ONLY_A_SUBJECT.match(said)
    if not lead:
        return None
    rest = said[lead.end():].strip(" ?.!,")
    if not rest or len(rest.split()) > A_FEW_WORDS or A_QUESTION_OF_ITS_OWN.search(said):
        return None
    if said[lead.start():lead.end()].strip().startswith(("and", "but", "also")) and \
            not re.search(r"what about", said[:lead.end()], re.I):
        # "and the food" is this shape; "and the food was cold" is a report about dinner.
        if HAS_A_VERB.search(said):
            return None
    words_in_line = [word.strip("?,.!'") for word in rest.split()]
    for kind, words in SUBJECT_KINDS:
        named = words.search(rest)
        if not named:
            continue
        left = list(words_in_line)
        for word in named.group(0).lower().split():
            if word in left:
                left.remove(word)
        if [word for word in left if word and word not in POINTING_WORDS]:
            # Something else is in the line, so the subject is not the whole of it.
            continue
        if kind == "council":
            # A council is the wrong body in another country. After "we're thinking of moving to
            # spain", "what about the bins" is a question about Spanish paperwork and the bin
            # day there, and naming a council would be worse than the floor's own answer. The
            # long form of the ask makes the same stand-down in `_about_the_rules`.
            if (ABROAD.search(before) or _a_country_not_home(before)
                    or _a_country_not_home(said)):
                return None
            return pick(COUNCIL_POOL, understood or {}, said)
        if kind == "journey":
            word = named.group(0).lower()
            return pick(JOURNEY_POOL, understood or {}, said).replace(
                "{mode}", _SUBJECT_MODE.get(word, word))
        thing = _SUBJECT_LABEL.get(named.group(0).lower())
        if not thing:
            return None
        # A pick is a pick somewhere: "what about the food there" is a question about a place,
        # "what about the food" on its own is not, so it is left to the floor.
        if not (A_PLACE.search(rest) or re.search(r"\b(?:there|here|nearby|local)\b", rest)
                or A_PLACE.search(before) or re.search(r"\b(?:there|here|nearby|local)\b", before)):
            return None
        return pick(PICK_POOL, understood or {}, said).replace("{thing}", thing)
    return None


def _about_a_pick(said, before=""):
    """The kind of place a line asks to be told about, or None.

    Two things have to hold, and both of them are about the word being the thing asked *for*
    rather than a place named on the way: an ask word ("best", "any good", "recommend") has to come
    just before it, and it must not be the object of a preposition of place, so "anywhere nice to
    eat near the beach" is a question about eating and not about beaches.
    """
    if not A_PLACE.search(said) and not A_PLACE.search(before):
        return None
    for words, thing in PICKS:
        for word in words:
            for match in re.finditer(r"\b" + re.escape(word) + r"\b", said):
                blocked = PICK_NOT.get(words[0])
                if blocked is not None and blocked.search(said):
                    break
                before = said[max(0, match.start() - 26):match.start()]
                if re.search(r"\b(?:in|near|around|round|at|by|beside|on|from|to)\s+(?:the\s+)?$",
                             before):
                    continue
                if not WANTS_A_PICK.search(before):
                    continue
                return thing
    return None


def _the_home_town(memory):
    """The town the person's own words already put them in, lowercased, or ().

    The understanding engine files a move already made as a home ("i just moved to bristol" is
    `home: true`, `city: Bristol`), and a move being planned as a place or a plan instead
    ("we're thinking of moving to spain" is a place with no home), so this reads the one and
    not the other.

    A country is not a town, and the engine files "i moved to france last year" the same way it
    files the move to Bristol - `home: true`, `city: France` - so the guard read that home as the
    town they are in and stood the paperwork down for the person who needs it most: "what
    paperwork do i need to stay" after moving to France was answered with the search hedge. The
    guard is about a town the move brought them to, so a country named as the home is left out -
    except the four nations of the UK, where a move is a move at home and "what classes are on"
    after "i moved to scotland" is the class question, not the paperwork.
    """
    if not isinstance(memory, dict):
        return ()
    user = memory.get("user")
    if not isinstance(user, dict) or not user.get("home"):
        return ()
    # A move the engine has filed as a plan has not happened yet, whatever the home flag says:
    # "we are moving to spain" is `home: true, city: Spain` *and* `plans: ["Moving to spain"]`,
    # and the paperwork for going is exactly what that person is asking for.
    plans = user.get("plans")
    if isinstance(plans, str):
        plans = (plans,)
    if isinstance(plans, (list, tuple)):
        if any(GOING_AWAY.search(str(plan)) or MOVING.search(str(plan)) for plan in plans):
            return ()
    found = []
    for key in ("city", "town", "village", "hometown", "home_city"):
        value = user.get(key)
        if isinstance(value, str):
            found.append(value.strip().lower())
    return tuple(word for word in found if word and (word in HOME_NATIONS or word not in COUNTRIES))


def _the_lines_of_this_question(said, memory):
    """The last few turns and this one, oldest first, as the person said them.

    `_the_line_before` glues the earlier lines into one string, which is enough to say that
    something was said about moving and not enough to say which came last. A move already made
    and a move still to come are told apart by which of them is the newer.
    """
    if not isinstance(memory, dict):
        return [said]
    turns = [turn for turn in (memory.get("turns") or []) if isinstance(turn, dict)]
    earlier = [str(turn.get("user") or "").lower() for turn in turns[-3:]]
    return earlier + [said]


def _the_move_was_to_their_own_town(said, memory):
    """True when the newest thing said about moving is the move that brought them where they are.

    "i just moved to bristol" is a statement about the town the person lives in now, and it was
    still being read three turns later: after "whats a good way to meet people here" and "i dont
    really drink", the line "ok what about classes or clubs" was answered with the paperwork for
    living abroad, because "moved to" is a move and nothing checked the destination. A place
    already in their own words as where they are is not a somewhere-else they are planning.

    Only the newest line that talks about moving counts. "i just moved to bristol" and then
    "we are planning to emigrate" is a person in Bristol who is still going, and the paperwork
    answer is theirs; the home move is only the last word on the subject when nothing after it
    says the move is still to come.
    """
    places = _the_home_town(memory)
    if not places:
        return False
    for line in reversed(_the_lines_of_this_question(said, memory)):
        move = MOVING.search(line)
        if move:
            destination = line[move.end():move.end() + 30]
            for place in places:
                if re.search(r"(?:^|[^a-z])" + re.escape(place) + r"(?:[^a-z]|$)", destination):
                    return True
            return False
        if GOING_AWAY.search(line):
            return False
    return False


def _a_day_out(said, before=""):
    """True when the line asks what to do or see in the place the thread is already about.

    The place has to be somewhere real: named on this line ("what should we see in rome"), or
    only pointed at ("what should i do there", "anything good to do while we are there") with a
    trip in the last few lines, which is how a follow-up is asked. A line with an object of its
    own ("what should i do about my knee", "what should i do with it") is not this reading,
    neither is a day at home ("what should i do in the garden" is the garden's), and neither is
    a visit to a ward or to see somebody.
    """
    if not said or not WANTS_A_DAY_OUT.search(said) or DAY_OUT_NOT.search(said):
        return False
    if ASKS_WHAT_TO_DO.search(said) and A_THING_IN_HAND.search(said):
        return False
    if A_PLACE.search(said) and not NOT_A_DAY_OUT_PLACE.search(said):
        return True
    if not (A_PLACE_THERE.search(said) or A_BARE_DAY_OUT.search(said)):
        return False
    # no name on this line: "there" and a bare "what should we see" need the trip behind them
    return bool(A_TRIP_BEFORE.search(before) and not NOT_A_DAY_OUT_PLACE.search(before))


def _about_the_rules(said, understood, before="", memory=None):
    if not WANTS_THE_RULES.search(said):
        return None
    # The country is allowed to be on the turn before this one; the ask is not, because an ask
    # with nothing of its own to ask about is the shrug's business, not this reading's.
    both = said + " " + before
    strong = re.search(r"\b(?:abroad|overseas|emigrat\w*|visa|residency|passport for)\b", said)
    if (ABROAD.search(both) and not _the_move_was_to_their_own_town(said, memory)
            and not NOT_THE_PAPERWORK.search(said)):
        # A country is named on this line or the one before it, and the thing being moved is not
        # a phone, an account or a house: "should we move house" is not a visa question.
        if (strong or not A_THING_NOT_A_PLACE.search(said)) and not (
                MOVING_HOUSE.search(both) and not re.search(
                    r"\b(?:abroad|overseas|country)\b", both)):
            return pick(ABROAD_POOL, understood or {}, said)
    # The council has to be named on this line: a follow-up like "what do i even write" after a
    # parking ticket is asking for the wording, and "your council's site has the form" is not that.
    if COUNCIL_WORD.search(said) or PARKING_RULE.search(said):
        return pick(COUNCIL_POOL, understood or {}, said)
    return None


# The three shapes that had no reading at all. Each one is read for its *shape* rather than for a
# subject, because the subject is exactly what the bot does not have: a choice between two named
# things, an ask for a list, and an ask for a list.
WANTS_A_CHOICE = re.compile(
    r"\b(?:which|what)\s+(?:is|s|'s|would be|will be)\s+(?:the\s+)?(?:better|best|cheaper|"
    r"stronger|safer|easier|quicker|healthier|nicer)\b"
    r"|\bwhich (?:one )?(?:should|would|do) i (?:get|buy|use|go for|pick|choose|have)\b"
    r"|\b(?:is|are)\s+[a-z][a-z' -]{0,24}?\s+or\s+[a-z][a-z' -]{0,24}?\s+"
    r"(?:better|best|worth it|the one)\b"
    r"|\bwhat would you (?:go for|pick|choose|get)\b"
    r"|\bis it better to\b", re.I)
# "what is better for a burn" is a fact about the world, not a choice between two things the
# person has already picked, and the health cards own that shape.
NOT_A_CHOICE = re.compile(
    r"\b(?:for a|for my|for the)\s+(?:burn|cut|rash|cough|cold|headache|baby|child|dog|cat)\b",
    re.I)
WANTS_A_SHORTLIST = re.compile(
    r"\b(?:short ?list|a list of|(?:a few|some|a couple of|three|two) (?:options|ideas|"
    r"suggestions|choices|picks)|options (?:for|on)|what are my options|what are the options|"
    r"(?:give|gimme|send) me (?:a few|some|three|two|a couple)|(?:suggest|recommend) "
    r"(?:a few|some|three|two))\b", re.I)
# A list of something the person is going to write themselves (a shopping list, a checklist) or a
# list they are already on is not a list the bot can be asked to draw up.
NOT_A_SHORTLIST = re.compile(
    r"\b(?:shopping list|ingredients list|list of ingredients|to do list|todo list|checklist|"
    r"waiting list|price list|job list|shortlisted|list of names)\b", re.I)
# Paperwork has a shape of its own: the verb is get, send or return and the object is a form. It is
# not a product, so no shop near them has one and no map app will find it.
GET_A_FORM = re.compile(
    r"\b(?:get|getting|find|download|print|print off|obtain|ask for|request)\b[^?.]{0,25}"
    r"\bforms?\b", re.I)
# The place and the office are what this half answers, so it needs one of them: "do i need to
# return the form" is a yes-or-no question about the paperwork itself, not about where it goes.
SEND_A_FORM = re.compile(
    r"\b(?:where|who|what address|which office|which address|how do i (?:send|return|post))\b"
    r"[^?.]{0,40}\b(?:send|sending|post|return|returning|hand|hand in|submit|give)"
    r"[^?.]{0,25}\bforms?\b"
    r"|\b(?:where|who)\b[^?.]{0,40}\bforms?\b[^?.]{0,25}\b(?:go|goes|going|back)\b", re.I)
# "A form of words", "in good form" and "form a queue" are not paperwork.
NOT_A_FORM = re.compile(
    r"\bform of (?:words|government|address|money|id|identification)\b|\b(?:in|on) (?:good |top )?"
    r"form\b|\bform an?\b|\bform (?:a|an)\b", re.I)


def _a_form(said, understood):
    """Where a form comes from, or where it goes back to, or None."""
    if NOT_A_FORM.search(said):
        return None
    if SEND_A_FORM.search(said):
        return pick(FORM_TO_POOL, understood or {}, said)
    if GET_A_FORM.search(said):
        return pick(FORM_FROM_POOL, understood or {}, said)
    return None


def _a_choice(said, understood):
    """The deciding factor for a choice between two things, or None.

    "Which is better, water or oil based" names no subject the bot can look up, and a search is
    a poor second to saying the one thing that is true of every choice of that shape: what it is
    used for and how hard it is worked decides it. The question at the end is the way in.
    """
    if not WANTS_A_CHOICE.search(said) or NOT_A_CHOICE.search(said):
        return None
    return pick(CHOICE_POOL, understood or {}, said)


def _a_shortlist(said, understood):
    """What a shortlist has to come from, or None: the bot cannot draw one out of nothing."""
    if not WANTS_A_SHORTLIST.search(said) or NOT_A_SHORTLIST.search(said):
        return None
    return pick(SHORTLIST_POOL, understood or {}, said)


def _about_the_sky(said, understood):
    """The weather a line asks about, as a reply naming where it is read, or None.

    The composer has its own weather line for the asks it recognises ("whats the weather like",
    "is it going to rain on saturday"), and this reading only ever runs on a line the composer
    left at the shrug: a sky word in an asking frame that it did not have words for, which is
    every frost, ice, hail, sleet, fog, mist, gust, thunder, drizzle, muggy or freeze question.
    A reading of a thing rather than the sky - the oven, the fridge, the car - stands down, so
    "will it be hot in the oven" keeps the roast answer it has.
    """
    if not A_SKY_ASK.search(said):
        return None
    if A_SETTING.search(said):
        return None
    return pick(WEATHER_POOL, understood or {}, said)


def answer_for(text, memory=None):
    """The honest limit and the place that knows, or None when the line is not one of these.

    Only five kinds are read, and each one names a place the person can go to today. A line that
    fits none of them is left to the floor, which is where it was before this module existed.
    """
    said = _said(text)
    if not said.strip():
        return None
    read = {}
    if isinstance(memory, dict):
        candidate = memory.get("understood")
        if isinstance(candidate, dict):
            read = candidate
    service = _about_a_service(said, read)
    if service:
        return service
    sky = _about_the_sky(said, read)
    if sky:
        return sky
    mode = _about_a_journey(said)
    if mode == "route":
        return pick(ROUTE_POOL, read, said)
    if mode:
        return pick(JOURNEY_POOL, read, said).replace("{mode}", mode)
    shop = _about_a_shop(said)
    if shop:
        return pick(SHOP_POOL, read, said).replace("{shop}", shop)
    before = _the_line_before(memory)
    if _a_day_out(said, before):
        return pick(THINGS_TO_DO_POOL, read, said)
    thing = _about_a_pick(said, before)
    if thing:
        return pick(PICK_POOL, read, said).replace("{thing}", thing)
    subject = _about_the_subject_named(said, read, before)
    if subject:
        return subject
    rules = _about_the_rules(said, read, before, memory)
    if rules:
        return rules
    # Lowest of all, because each of these is read for the shape of the question and knows
    # nothing about the subject: anything above that names a place, a service or a rule keeps
    # its turn, and so does every card the composer can answer.
    return _a_choice(said, read) or _a_shortlist(said, read) or _a_form(said, read)
