"""What kind of answer a line wants, and whether a reply gives it.

The understanding engine says what a line is about and which question words it carries
(`memory["understood"]["asks"]`). It does not say what shape of answer the person is owed: a
`how_long` line wants a time, a `where` line a place, a `which` line a pick, a bare `yesno` a
verdict. This module reads that shape from the whole line, and checks a reply for it.

The reading runs once per turn in `bot/modules/intent.py`, which writes
`memory["understood"]["wants"]` before any other observer runs. The check is for the composer and
for `tools/intent.py`: a reply on the right topic that does not answer the question - the story of
what rice is for, for "how long does rice take" - is a miss even though it reads well.

The labels are the lane's fixed list, and a module may return None rather than guess:

    time      a duration or a clock time ........ "about 12 minutes", "by Friday", "1 to 1.5 bar"
    amount    a quantity, price or sum .......... "about 2 kilos", "£3.50", "21 ÷ 3 = 7"
    place     somewhere to go ................... "the post office", "Antarctica"
    person    who to ask ........................ "the vet", "your GP", "Napoleon"
    meaning   what the thing is ................. "An APR is the yearly cost..."
    yesno     a yes or a no ..................... "Yes", "Straight in is fine", "No need"
    pick      which of two or more .............. "Replace it", "Oat milk for coffee"
    steps     what to do, in order .............. "First..., then..."
    options   a few ideas ....................... "one, or two, or three" (not one idea)
    reason    why it happens .................... "because...", "that's why..."
    opinion   what the bot makes of it .......... not checkable by words
    advice    what the person might do .......... not checkable by words
    comfort   an answer to something hard ....... not checkable by words
    answer    anything else ..................... not checkable by words

`wants` reads the shape. `gives` says True when a reply's opening sentence gives that shape,
False when it can say what the reply gives instead (a shrug, or an unmistakable other shape), and
None where words cannot tell - the soft labels above, and an opening the cue list has nothing
for. It is a finder, not a mark: "eight to ten years" is a time without a digit and "straight in
is fine" is a yes without the word yes, so every check is written to be right more often than it
is wrong and to say nothing where it cannot be sure.
"""
import re

# The answer shapes, in the lane's fixed words. Nothing outside this list is written to `wants`.
TIME = "time"
AMOUNT = "amount"
PLACE = "place"
PERSON = "person"
MEANING = "meaning"
YESNO = "yesno"
PICK = "pick"
COMPARE = "compare"
STEPS = "steps"
OPTIONS = "options"
REASON = "reason"
OPINION = "opinion"
ADVICE = "advice"
COMFORT = "comfort"
ANSWER = "answer"

WANTS = (TIME, AMOUNT, PLACE, PERSON, MEANING, YESNO, PICK, COMPARE, STEPS, OPTIONS, REASON,
         OPINION, ADVICE, COMFORT, ANSWER)

# The shapes a check cannot read out of the reply's own words. A condolence or an opinion is a
# reply to the whole line, not a figure or a place, and a word list that tried to grade one would
# be wrong more often than right, so `gives` says None for them and no miss is counted.
SOFT = frozenset((OPINION, ADVICE, COMFORT, ANSWER))

# The kinds of answer understanding's `asks` labels point at, strongest first. Two things to know:
#
# - A line that names two things and asks which is a `pick` before it is anything else: "should i
#   get it repaired or a new one" is the same question as "repair or replace", so `choice` is read
#   before `yesno` even though understanding labels both.
# - `what should i cook tonight` arrives as `steps` (understanding reads the `what should` as a
#   question of method), and that is the understanding lane's to fix, not a second reading here.
ASKED_FOR = (
    (PICK, frozenset(("choice", "compare", "which"))),
    (MEANING, frozenset(("definition",))),
    (PLACE, frozenset(("where",))),
    (PERSON, frozenset(("who",))),
    (REASON, frozenset(("why",))),
    (TIME, frozenset(("how_long",))),
    (AMOUNT, frozenset(("how_much", "how_often"))),
    # Understanding labels any line holding a number as `maths` ("my mums birthday is on the 3rd
    # of may", "half a roast chicken left over"), so a sum is read off a question and no other
    # line is given a figure to answer.
    (AMOUNT, frozenset(("maths",))),
    (OPTIONS, frozenset(("list",))),
    (STEPS, frozenset(("steps", "how"))),
    (PICK, frozenset(("recommend",))),
    (YESNO, frozenset(("yesno",))),
)


# The whole line as people wrote it, for the readings that need more than the `asks` labels.
def _said(understood):
    parts = []
    for key in ("norm", "norm_text", "clean", "text"):
        value = understood.get(key)
        if isinstance(value, (list, tuple)):
            value = " ".join(str(word) for word in value)
        if isinstance(value, str) and value:
            parts.append(value)
    return " ".join(" ".join(parts).lower().replace("\u2019", "'").split())


# Who the line is about, when the who beside them belongs to them rather than asking for a name.
def _a_who_a_person_owns(understood):
    """True when the who in the line belongs to the person the line is already about.

    "something for my sister who just had a baby", "how do i deal with a boss who shouts":
    understanding has read the sister and the boss as a person of the line, and the who standing
    right after them is the relative pronoun - the ask is a present or for advice, not a name.
    Read as a who-question, 33 of the deck's 349 person wants owed a name no gift or advice reply
    could give, and each of those replies was counted a miss. A who the line opens on, a who that
    asks after a new person ("my daughter wants to know who mozart was") and a who with no
    person before it ("i got whiplash in a crash who pays") still owe the name.
    """
    words = understood.get("words")
    entities = understood.get("entities")
    if not isinstance(words, (list, tuple)) or not isinstance(entities, (list, tuple)):
        return False
    for entity in entities:
        if not isinstance(entity, dict) or entity.get("type") != "person":
            continue
        at = entity.get("at")
        if not isinstance(at, int) or at < 0:
            continue
        after = at + len(str(entity.get("text") or "").split())
        if 0 < after < len(words) and str(words[after]).lower() in ("who", "that"):
            return True
    return False


# Two named sides: understanding labels the choice, the comparison or the "which".
PICK_SIDES = frozenset(("choice", "compare", "which"))
# Two named sides are not always a choice to make. "What is the difference between a sprain and a
# strain" comes in as `compare`, but nobody is asking the bot to prefer one: the answer is what
# each of the two is. The same line answered with a pick would be answering a question the person
# did not ask, so the difference questions are read for the meaning and the contrasts are read
# further down by the ordinary side rule ("which is better, the train or the coach" is a pick).
# A difference that is not the object of the question - "does that make a difference", "how long
# until i notice a difference", "my week is different", "a different charger" - is not this ask.
DIFFERENCE = re.compile(
    r"\bwhat(?:['\u2019]?s| is| are| was| were)?\b(?:\s+[\w'-]+){0,3}\s+differences?\b"
    r"|\bhow (?:is|are|does)\b[^.?!]{0,40}\b(?:different|differ)\b\s*(?:from|to)\b"
    r"|^[\W]*(?:the )?differences? between\b", re.I)
# The asks that are a real question of their own, and so beat the yes/no understanding labels on
# any line that opens on an auxiliary. "how long do i boil an egg" and "how much should i save"
# arrive as `how_long`/`how_much` *and* `yesno` (the "do i" is read as the yes/no), and the figure
# is what the person is waiting for. "recommend" is deliberately not here: "is it worth it" is a
# verdict with a recommendation word in it, not a request to pick one of two things. Neither is
# the bare `how` or `maths` label, which are loose: "is that how it works" is a yes/no about the
# bot's last answer, and "can i freeze double cream" carries `maths` for the word "double".
SPECIFIC_ASKS = frozenset((
    "choice", "compare", "which", "definition", "where", "who", "why", "how_long",
    "how_much", "how_often", "list", "steps"))
# Every kind of a thing asked as a menu: "what kinds of coffee are there" asks for the kinds, not
# for what coffee is, and understanding reads the "what" as a definition. The identifying form is
# a different question - "what kind of dog is that" asks what the one in front of them is - so it
# is named here and stood down, rather than left to the reply to sort out.
KINDS_OF = re.compile(
    # The set of kinds asked for as a set: "what kinds of coffee are there", "what types of
    # insulation can i get", "what sorts of food can i freeze", "what kinds of things can go wrong
    # with a boiler". The tail is what makes it a menu - a there-is or a can - because the same
    # words with an "is best" or an "is good with kids" are asking which one kind suits them.
    r"\b(?:what|which) (?:kinds?|types?|sorts?|varieties|styles|brands|makes|models)"
    r"(?: of (?:[\w'-]+ ){0,4})?"
    r"(?:are there|are available|is there|exist|do you|would you|can|could)\b"
    r"|\bwhat (?:are|were) the (?:kinds?|types?|sorts?|varieties|styles)\b"
    r"|\bwhat (?:are|were) (?:my|the|our) (?:options|choices)\b"
    r"|\bwhat (?:options|choices) (?:do i|do we|have i|are there)\b"
    r"|\b(?:any|other|more) (?:options|choices|alternatives)\b"
    r"|\bwhat else (?:is|are) (?:there|out there)\b"
    r"|\bwhat (?:is|are) available\b", re.I)
NOT_KINDS_OF = re.compile(
    r"\bwhat (?:kind|type|sort) of (?:a )?(?:[\w'-]+ ){0,3}(?:is|was|are|were) "
    r"(?:that|this|it|those|these|he|she)\b"
    # Nor is the kind that would suit them a menu of kinds: "what sort of dog would suit that" is
    # asking which one fits the life they have, which is advice about their situation.
    r"|\bwhat (?:kind|type|sort) of (?:[\w'-]+ ){0,3}(?:would|will|should|could|might|suits?|fits?)\b",
    re.I)

# The method asked for as a set of steps: "what are the steps to reset a boiler", "what is the
# process for getting a visa", "step by step for a bookshelf", "what are the stages of buying a
# house". The words "what are the ..." are the same words as a menu of options, so the method is
# read before the menu: the person asked for the order to do things in, not a few ideas to choose
# between, and a reply that lists the kinds available instead is the wrong answer to it.
STEPS_ASK = re.compile(
    r"\bwhat (?:are|is) the steps\b|\bsteps (?:to|for|in)\b|\bstep[- ]by[- ]step\b"
    r"|\bwalk me through\b|\bwhat(?:'s| is) the process\b|\bthe process (?:for|of|to)\b"
    r"|\bhow do i go about\b|\bwhat order\b|\bin what order\b"
    r"|\b(?:the )?(?:best|right|correct|proper) order (?:to|for|in)\b", re.I)
# A count of steps is a figure, not a method: "how many steps a day should i walk", "how many
# steps in a mile", "steps per mile", "10000 steps in miles". The word is the same and the answer
# wanted is a number, so the counted forms are read before the method.
COUNTED_STEPS = re.compile(
    r"\bhow many steps\b|\bsteps? per\b|\bsteps? in (?:a|one) (?:mile|km|day)\b"
    r"|\bstep count\b|\b\d{3,} steps\b", re.I)
# The members of a set asked for by the set's own word: "what are the early signs of dehydration",
# "what are the symptoms of a chest infection", "what are the stages of labour". Understanding
# reads the bare "what are" as a request for the meaning of a word, so the line came out wanting a
# definition - and the reply that lists four signs was charged for not defining anything. The
# answer wanted is the set, which is a menu of things rather than a definition of one.
MEMBERS_ASK = re.compile(
    r"\bwhat (?:are|were) the (?:early |first |main |usual |common |classic |key |warning |"
    r"typical |initial )?(?:signs?|symptoms?|stages?|phases?)\b"
    r"|\bwhat (?:signs?|symptoms?|stages?)\b[^.?!]{0,30}\b(?:should|would|do|can|might) "
    r"(?:i|you|we) (?:look|watch|expect|see)\b"
    r"|\bwhat are the (?:warning|telltale) signs\b", re.I)

# A comparison asks for both sides and then what sets them apart, so it is a shape of its own and
# not a pick: "compare a dehumidifier and a window vac", "gas vs electric hob", "how does a heat
# pump compare with a gas boiler", "what sets a leasehold apart from a freehold", "is a heat pump
# better than a gas boiler". The verdict form of the same question - "is it worth it", "should i
# take the train or the coach" - is asking for a decision, and is read before this by its own ask.
COMPARISON = re.compile(
    r"\bcompare[ds]?\b|\bcomparing\b|\bvs\.?(?=\s|$)|\bversus\b"
    r"|\bdifferences? between\b"
    r"|\bhow (?:is|are|does|do|did) [^.?!]{0,40}\b(?:different|differ|compare)\b"
    r"|\bwhat sets? [^.?!]{0,30}\bapart\b|\bsets? [^.?!]{0,30} apart\b", re.I)
# One thing said to be a comparative of the other is a comparison too - "is a loan cheaper than a
# credit card", "is a plank better than a sit up" - but only when the line is asking something.
# "Some people say its better than butter" and "better than i expected" are the person's own
# remarks, and neither owes both sides back.
COMPARED = re.compile(
    r"\b(?:better|worse|cheaper|dearer|quieter|louder|faster|slower|easier|harder|healthier|"
    r"safer|simpler|tastier|stronger) than\b", re.I)
# The words that make the same two things a decision rather than a survey of them.
NOT_A_COMPARISON = re.compile(
    r"\b(?:should i|shall i|worth (?:it|doing|the)|for me|which should i|which one should i|"
    r"is it better to|would you)\b"
    # The comparing the person does themselves is news, not a request: "i compare myself to my
    # sister all the time" is telling the bot something and owes no comparison back.
    r"|\b(?:i|we) (?:always |still |keep |often |just )?compare\b"
    # "How do i tell the difference" and "how do i compare two mortgages" ask for the method of
    # comparing, which is steps about their own job, not a comparison handed back.
    r"|\bhow (?:do|can|should|would|could) (?:i|we)\b"
    # And "better than i expected" is how the person judges something, not two things put together.
    r"|\b(?:better|worse) than (?:i|we|you|they|she|he) (?:expected|thought|hoped|feared|looked)\b",
    re.I)

# The two things a comparison puts together, in the words the line uses to put them: "between X and
# Y", "X vs Y", "X compared with Y", "X different from Y", "X cheaper than Y". A side stops at the
# joining word, so "between an ssd and an hdd" gives "ssd" and "hdd" and not "ssd and".
_SIDE = r"([\w'-]+(?: (?!and\b|from\b|than\b|vs\b|versus\b)[\w'-]+)?)"
_THE = r"(?:a |an |the )?"
SIDE_PAIRS = (
    re.compile(r"\bbetween " + _THE + _SIDE + r" and " + _THE + _SIDE, re.I),
    re.compile(r"\bcompare[sd]? " + _THE + _SIDE + r" (?:and|with|to) " + _THE + _SIDE, re.I),
    re.compile(_SIDE + r" apart from " + _THE + _SIDE, re.I),
    re.compile(_SIDE + r" (?:vs\.?|versus) " + _THE + _SIDE, re.I),
    re.compile(_SIDE + r" compar(?:e|ed) (?:with|to) " + _THE + _SIDE, re.I),
    re.compile(_SIDE + r" (?:is |are |was |were )?(?:comparable to) " + _THE + _SIDE, re.I),
    re.compile(_SIDE + r" (?:is |are |was |were )?(?:different|differs?) (?:from|to) "
               + _THE + _SIDE, re.I),
    re.compile(_SIDE + r" (?:better|worse|cheaper|dearer|quieter|louder|faster|slower|easier|"
               r"harder|healthier|safer|simpler|tastier|stronger) than " + _THE + _SIDE, re.I),
)
# The words that ask for the two things to be put side by side whatever the line's shape is:
# "compare a dehumidifier and a window vac" is an instruction with no question mark in it.
EXPLICIT_COMPARE = re.compile(
    r"\bcompare[ds]?\b|\bcomparing\b|\bvs\.?(?=\s|$)|\bversus\b|\bdifferences? between\b",
    re.I)


def _names_a_pair(said):
    """True when the line itself names the two things it is about, as a comparison has to."""
    return any(pattern.search(said or "") for pattern in SIDE_PAIRS)


def _asks_about_them(understood, said):
    """True when the line is asking about the pair rather than telling the bot something about it.

    "Hows that different" carries the words of comparing but no pair, and it is a question about
    the bot's own last answer, so it falls through to the follow-up rule and keeps the shape it
    followed. "I think im being underpaid compared to the new guy" names a pair and is still news.
    """
    if understood.get("intent") == "news":
        return False
    return EXPLICIT_COMPARE.search(said or "") or understood.get("kind") == "question"


# A negative that is a request for help, not a question about the bot.
HELP_ME = re.compile(r"\b(?:can|could|would|will) you help me\b|\bhelp me (?:with|to|out)\b", re.I)
# A how that wants a figure rather than a method. A length of time - how soon, how early, how
# quickly, how long - is a time; any other measure word ("how much", "how many", "how often",
# "how hot", "how hard") is an amount, and the figure is the answer to all of them. The measure
# word is read from the text because understanding carries only some of them as a label: "how hot
# should the oven be" arrives as a bare `how`, which on its own is a method.
# The person's own how is a method: "how do i cancel my disney plus", "how do i know what size".
HOW_I = re.compile(r"\bhow (?:do|can|could|should|would) i\b", re.I)
# The person weighing their own life against someone else's is not a method for two things:
# "how do i compare myself to others", "how do i compare to my sister".
COMPARE_MYSELF = re.compile(
    r"\bcompar(?:e|ing)\b[^.?!]{0,14}\b(?:myself|ourselves)\b"
    r"|\bcompare\s+(?:to|with)\s+(?:me|my|us|our|him|her|them|others)\b", re.I)
HOW_SOON = re.compile(r"\bhow (?:soon|early|quickly|long)\b", re.I)
HOW_MEASURE = re.compile(
    r"\bhow (?:tall|old|big|far|heavy|wide|deep|high|fast|hot|cold|warm|hard|loud|cheap|expensive|"
    r"many|much|often)\b", re.I)
# The same shape at the head of the ask, over a wider list of measure words. A measure word
# anywhere in the line can be a word inside a method, so the reading that says the figure is the
# answer only takes a line that opens on the measure: "how thick should i slice bread" is 1cm,
# "how ripe should a banana be" is the colour, "how tight should a bike helmet be" is a finger's
# width under the strap. Each of those carries no measure label, only `how`, so `should` in the
# rest of the line was reading the first as a verdict and the other two as a method.
HOW_MEASURE_HEAD = re.compile(
    r"^how (?:tall|old|big|far|heavy|wide|deep|high|fast|hot|cold|warm|hard|loud|cheap|expensive|"
    r"thick|thin|ripe|tight|loose|full|low|slow|quick|short|small|large|near|soft|firm|dark|"
    r"bright|sharp|rough|smooth|fine|coarse|steep|cool|fresh|dry|wet|salty|sweet|spicy|sour|mild|"
    r"strong|weak|light|stiff)\b", re.I)
# "what does a boiler service cost", "what does a cup of honey weigh": a verb of price or measure
# after "what does" asks for the figure, and understanding reads the "what does" as a definition,
# so the figure that came back read as a miss. Same shape as the how-words above.
WHAT_DOES_MEASURE = re.compile(
    r"\bwhat (?:does|do)\b(?:(?!\bwhat\b)[^?]){0,30}?"
    r"\b(?:cost|costs|charge|charges|weigh|weighs)\b"
    # "what does the whole lot come to" is the total; "what does it mean when birds come to my
    # feeder" is the "come to" of a bird, so this arm is only read where no meaning is asked.
    r"|\bwhat (?:does|do)\b(?:(?!\bwhat\b)[^?]){0,30}?\bcome(?:s)? (?:to|out at|out as)\b",
    re.I)

# A conversion, not a duration: "how long is 100m in feet", "how long is a 5k in miles". The
# answer is a length, so "how long" here asks for an amount however the word "long" reads.
CONVERSION = re.compile(
    r"\bhow long (?:is|are|was)\b[^?]{0,30}?\b(?:in|to|as|into) "
    r"(?:feet|foot|metres?|meters?|miles?|kilometres?|kilometers?|km|yards?|inches|inch|cm|mm)\b",
    re.I)
# A when that opens the question. "when i ring someone my screen goes black" is advice about a
# thing that happens, and "my mum keeps asking when were having kids" is a report, not a when.
# A day, a date or a month is a time too: "what day is that", "what date does it start", "which
# day is it". A line that asks which of several days is *best* is a pick, so the choices are left
# to the pick below.
# A follow-up opens on the join: "and what date is that", "so when is it", "but when should i go".
# The question is the same one, and the join in front of it is not part of it.
LEADING_JOIN = re.compile(r"^(?:(?:and|so|but|then|also|ok|okay|right|now|well)\b[ ,]*)+", re.I)
WHEN_ASKS = re.compile(
    r"^(?:when'?s|when|what time|what day|what date|what month|what year|which day|what weekday) "
    r"(?:should|shall|is|are|was|were|will|would|does|do|did|can|could|to|am|has|have|of|had)\b",
    re.I)
WHICH_DAY_IS_BEST = re.compile(r"\b(?:best|better|rather|prefer|do you think|recommend)\b", re.I)
# An open choice: "what should i cook tonight" wants one thing picked, not the method for it.
# A judgement word in front of a measure asks for the figure: "what's a good time for a half
# marathon", "a normal price for a boiler". The noun picks the check.
# A recommendation asked for with the word what: "whats a good podcast for the car", "wats a gud
# cake", "wots a good cheap pressie", "whats a good breakfast thats quick". `GOOD_FIGURE` below is
# the same shape when a figure is wanted: "what is a good half marathon time".
GOOD_THING = re.compile(
    r"\bwhat(?:'s|s| is| are)\s+(?:a|an|the|some)?\s*(?:really |actually |bit of a )?"
    r"(?:good|great|nice|decent|cheap|budget|quick|easy|simple|sensible|healthy)\b", re.I)
GOOD_WAY = re.compile(r"\b(?:way|method|approach|routine)\b", re.I)
# "whats a good resting heart rate" asks for the figure, not a few ideas, so a measure word in the
# line keeps the figure reading `GOOD_FIGURE` gives it.
GOOD_FIGURE_WORD = re.compile(
    r"\b(?:time|timeframe|rate|age|price|cost|number|amount|weight|height|length|salary|wage|"
    r"dose|dosage|percentage|temperature|speed|distance|size)\b", re.I)
# The table a place keeps its hours in is a time, not the meaning of a word: the words after
# "what are" are times or hours and the answer is on the clock.
WHAT_ARE_TIMES = re.compile(
    r"^\W*(?:(?:so|and|ok|okay|oh|also|right)\s+)*what(?:'s| is| are|s)\b[^?]{0,60}?"
    r"\b(?:opening|visiting|closing|trading|check ?in|check ?out|business|office|term|school|"
    r"library|swimming|bus|train|ferry|flight|shop|bank|tip|pool|gym|leisure|surgery|pharmacy|"
    r"restaurant|pub|museum) ?(?:times|hours|dates)\b", re.I)

GOOD_FIGURE = re.compile(
    r"\b(?:good|average|normal|typical|usual|best) (?:\w+ ){0,3}(?:time|age|price|number|amount|cost)\b",
    re.I)
# "how does a lock and key work" asks for the mechanism, which is a meaning; understanding reads
# the bare "how" as a method. Only the thing-works form, so nobody doing the working is caught.
HOW_IT_WORKS = re.compile(
    r"\bhow (?:does|do|did) (?:(?!\b(?:i|you|we|im|me)\b)[\w']+ ){1,4}(?:work|works|working)\b",
    re.I)
# A written thing has a length in words or characters, and its "how long" is that length: the noun
# followed by "be" is what tells it from a length of time.
WRITTEN_THING = re.compile(
    r"\bhow long (?:should |would |will |does |do |can )?(?:a|an|my|our|your|the|this|that)\s+"
    r"(?:[a-z]+\s+){0,2}(?:personal statement|statement|essay|dissertation|thesis|coursework|"
    r"assignment|cover(?:ing)? letter|letter|cv|resume|blog post|post|article|abstract|summary|"
    r"report|review|answer|paragraphs?|chapter|book|story|speech|presentation|email|text|message|"
    r"comment|description|bio|application|proposal|synopsis|blurb|poem|script|personal profile|"
    r"profile)\s+be\b", re.I)
# The person has to do the explaining, saying or answering: that is a method, not a meaning.
HOW_TO_DO = re.compile(
    r"\bhow (?:do|can|could|should|would|will) (?:i|we|you) (?:explain|answer|say|tell|word|"
    r"respond|reply|put it|break it|approach|handle)\b|\bhow to (?:explain|answer|say|tell|"
    r"word|respond|reply|approach|handle)\b", re.I)
# Small talk shaped like a how: it asks nothing of the world.
# "hows things" and "hows u" are the same hello as "how are you", and were read as a method and
# scored a steps miss. A noun that a verb follows is not small talk: "how things work" asks for the
# meaning and keeps its shape.
HOW_ARE_YOU = re.compile(
    r"^(?:(?:hey|hi|hiya|heya|hello|yo)(?: there)?[ ,]+)?how(?:'?s| is| are)?[ ,]+"
    r"(?:you|u|ya|things|tricks|life|are you|are things|is it going|s it going|have you been|"
    r"are we|your (?:day|week|evening|morning|night|head|family))\b"
    r"(?!\s+(?:work|works|worked|working|go|goes|went|change|changes|changed|happen|happens|"
    r"happened|fit|fits|seem|seems)\b)",
    re.I)
# A line that opens on a question word or an auxiliary is asking, whatever punctuation it has.
ASKS_OUT_LOUD = re.compile(
    r"^(?:what|which|who|whose|when|where|why|how|is|are|was|were|do|does|did|can|could|should|"
    r"shall|would|will|any|anything|anyone|recommend|suggest|name|give me|tell me|got any)\b",
    re.I)
# A line that asks what a thing costs wants the figure, though understanding reads its "what
# does" as a definition and "price of a pint" as one more thing to define. A standing charge is
# not a cost question, so the price word here is one a thing is measured by, or the verb itself.
COST_ASK = re.compile(
    r"\bwhat (?:does|do|will|would|did|is it going to) .{0,40}\bcosts?\b"
    r"|\bwhat .{0,40}\bcosts?\b"
    r"|\b(?:price|cost|charge|fee)s? (?:of|for)\b", re.I)
# A price asked as a definition: "what is a gym membership a month" and "whats a cleaner an hour"
# are the figure, and a card that explains what a membership is does not answer either.
WHAT_IS_PER = re.compile(
    r"\bwhat(?:'s|s| is)\b[^?]{0,40}\b(?:a|an|per|each|every) "
    r"(?:month|week|year|day|hour|litre|liter|kg|kilo|pint|mile|gb|gigabyte|night|visit|session|"
    r"person|head|class|lesson)\b", re.I)
# The asks a cost line may carry and still be asking the price: a `why` or a `where` in the line
# keeps its own shape, so this is a subset of every other ask, not a list of them.
COST_STANDS_IN = frozenset(("what", "definition", "list", "opinion", "recommend", "question"))
# A sum asked with no question word at all: "subtract 10 percent from 55", "split 120 between 4
# people", "half a cup of rice in grams". Understanding labels the number `maths` and the line is
# a statement, so the figure is the ask even though the line never asks one out loud.
SUM_OUT_LOUD = re.compile(
    r"^(?:subtract|add|multiply|divide|solve|factorise|factorize|work out|convert|split|minus|"
    r"plus|double|halve|times)\b|\bhow much is\b", re.I)
SUM_ASKS = re.compile(
    r"\b(?:\d+|half|quarter|third|two thirds|three quarters|a few)\b.{0,30}\bin "
    r"(?:grams?|gms?|kg|kilos?|kilograms?|ml|millilitres?|litres?|liters?|cups?|ounces?|oz|"
    r"pounds?|lbs?|tablespoons?|tbsp|teaspoons?|tsp|pints?|centimetres?|cm|inches|feet|metres?)\b"
    r"|\b(?:half|a quarter|a third|two thirds|three quarters|three quarters|a fifth) of \d+"
    r"|\bas a percentage\b|\bpercent (?:off|on top)\b|\b\d+\s*(?:%|percent)\b"
    r".{0,25}\b(?:off|tip|on top|between|split)\b"
    r"|\bsplit (?:the )?(?:bill|cost|rent|fare|total|it|\d|\u00a3)", re.I)
# ... unless the figure words are about the bot itself, or the person is really asking whether the
# thing matters. "how much do you know about boilers" and "how much does it matter" want no
# figure. A "do you" alone is not about the bot: "how much do you feed a pig" and "how much do you
# tip a waiter" ask for a figure, so the verb of knowing is what makes the line the bot's own. This
# sits in front of every amount reading below, not only the how-much one, because the label table
# at the bottom maps the same how_much label to a figure.
NOT_A_FIGURE = re.compile(
    r"\bhow (?:much|many) (?:do|did|can|could|would|have) you "
    r"(?:know|remember|understand|recall)\b|"
    r"\bhow (?:much|often) (?:does|do) (?:it|that|this|they) matter\b|"
    r"\bhow much (?:should|do) (?:i|we) (?:worry|care|mind)\b", re.I)
PICK_ONE = re.compile(
    r"\bwhat (?:do|should|shall|can|could) (?:i|we|he|she|they) (?:cook|make|eat|have|drink|watch|"
    r"read|listen to|wear|get|buy|order|play|study|plant|visit|do with|give|bring)\b"
    r"|\bwhat (?:do|should|shall|can|could) (?:my|our|his|her|their) \w+ (?:cook|make|eat|have|"
    r"drink|watch|read|wear|get|buy|order|play|study|plant|visit|give|bring)\b", re.I)
# The same ask with a kind of thing named in front of the verb: "what knife should i buy", "what
# book should i read", "what kind of plant should i get". A want of None means nothing is checked
# at all, so the good picks on these turns passed unseen and the punts did too. The verb still
# decides, and the noun has to be a thing to choose from: a measure ("what time should i get up"),
# an entitlement or a record ("what age do i get my state pension", "what pets do i have") and
# "what else" keep their own reading. A preposition after the "what" opens a different ask - "what
# about flights, should i book early" is a yes/no about the flights - so it is not read here.
PICK_ONE_OF_A_KIND = re.compile(
    r"\bwhat (?!else\b|about\b|of\b|in\b|on\b|at\b|to\b|from\b|for\b|with\b|by\b|between\b|"
    r"age\b|time\b|date\b|month\b|year\b|day\b|size\b|temp\b|temperature\b|price\b|cost\b|"
    r"amount\b|number\b|help\b|support\b|percentage\b|share\b)"
    r"(?:(?:kind|sort|type|brand|make) of )?"
    r"(?:[\w'-]+ ){1,2}should (?:i|we) "
    r"(?:cook|make|eat|have|drink|watch|read|listen to|wear|get|buy|order|play|study|plant|visit|"
    r"do with|give|bring|choose|pick|go for|book|take)\b", re.I)
# A price is also asked as an adjective on the thing: "is paris expensive", "is a plumber costly",
# "will that be expensive to fix" are questions about how much, and the answer a person gets is a
# range. Only the words that mean a lot of money count: "cheap" and "cheaper" compare two things
# and a `than` names them, so those keep their pick.
PRICE_ADJECTIVE = re.compile(
    r"\b(?:is|are|was|were|isn'?t|aren'?t|wasn'?t|weren'?t)\b[^?.!]{0,30}?\b(?:expensive|"
    r"costly|pricey)\b"
    r"|\b(?:will|would|won'?t|wouldn'?t)\b[^?.!]{0,24}?\bbe\b[^?.!]{0,14}?\b(?:expensive|"
    r"costly|pricey)\b", re.I)
# A comparison of two named things is a pick, and a verdict on the value of something is a yes/no:
# "is a cheap mattress worth it" asks whether to buy it, not what it costs.
PRICE_ADJECTIVE_KEEPS = re.compile(
    r"\b(?:than|or|instead|versus|vs|worth|whether|rather)\b", re.I)
# ...and the price word is not the ask when the line asks something else after it: "sky tv is too
# expensive can i cancel" is a remark about their bill and a question about cancelling, and the
# reply people get is the steps for cancelling. A question word with a person after it is another
# question, and the price in front of it is what that question is about.
PRICE_ADJECTIVE_THE_ASK_IS_LATER = re.compile(
    r"\b(?:expensive|costly|pricey)\b[^?.!]{0,30}?\b(?:can|could|should|shall|would|will|do|does|"
    r"did|am|is|are)\s+(?:i|we|you|he|she|they|it)\b", re.I)
# ...and a "why" about the price keeps its reason: "why is everything so expensive", "why is london
# so expensive" want the cause, and the price word in them is what the why is about. Understanding
# labels them `why` plus `yesno` (the line opens on an auxiliary), which is what put them at risk.
PRICE_ADJECTIVE_WHY = frozenset(("why",))
# A line that asks the bot outright what to do about something: "what can i do 4 a sore throat",
# "my baby is constipated, what can i do", "what do i say to my boss", "what do i try first".
# Understanding labels the `what should i do` spelling as steps and leaves the rest of the family
# as a bare `what`, so the whole line is read here and the verb decides: doing, saying, taking or
# trying wants the steps. Something to wear or get is a choice, and `PICK_ONE` above has it, so
# those verbs are not here; `use` is read as `SUBSTITUTE` below instead.
WHAT_TO_DO = re.compile(
    r"\bwhat (?:do|should|shall|can|could|would) (?:i|we) "
    r"(?:do|say|take|try|check|avoid|ask|tell|help|start|stop|keep)\b", re.I)
# The same ask said to the bot rather than about the person: "what do you do about that" is the
# method, and "what would you take to a new baby" is the list of things. The verb tells them apart,
# and the job question ("what do you do for a living") is still about the person, not a method.
WHAT_YOU_DO = re.compile(
    r"\bwhat (?:do|does|would|should|can|could) (?:you|one) (?:do|try)\s+"
    r"(?:about|with|if|when|for|to)\b", re.I)
WHAT_YOU_TAKE = re.compile(
    r"\bwhat (?:do|does|would|should|can|could) (?:you|one) (?:take|bring|give|get|need|buy)\b"
    r"(?! (?:for|to do|to get|to make)\b)", re.I)
# The same ask said from the other side: "what do i need for a camping trip", "what do i need to
# buy for a roast", "what will we need for the baby". It is the list of things the person asked
# for - the shape "what would you take to a new baby" already had - and on its own words it read
# as no ask at all, which was eighty of the deck's lines. The infinitive after the need decides
# which ask it is: what to buy, get, bring, pack or order is the list of things, and what to do,
# know, say or watch out for about the situation is the method, which is read further down.
WHAT_I_NEED = re.compile(
    r"\bwhat (?:do|does|will|would|should|shall|might|can) (?:i|we) (?:need|require)\b"
    r"(?!\s+(?:to\s+)?(?:do|know|say|ask|tell|learn|understand|work|watch|avoid|stop|prevent|"
    r"fix|deal|look|sort|handle|word|phrase)\b)", re.I)
# A figure has a unit named in the question: "what temperature should i cook chicken at", "what
# gas mark for a sponge", "what setting on the oven". Understanding reads the `what` as a
# definition, so the noun is what says a figure is owed.
WHAT_FIGURE = re.compile(
    r"\bwhat (?:temperature|temp|heat|gas mark|setting|speed|depth|size|weight|voltage)\b",
    re.I)
# A remedy asked for with "what helps" is a few things to try, not one method: "what helps a sore
# throat", "what can help with cramps".
WHAT_HELPS = re.compile(
    r"\bwhat (?:helps|can help|might help|will help|would help|works)\b", re.I)
# The infinitive of the same two asks: "what to wear to a wedding", "what to cook tonight", "what
# to do when your boiler leaks". It is how people type the `what should i` family without the
# auxiliary, and on its own the reading found no shape at all, so "what to cook tonight" owed
# nothing while "what should i cook tonight" wanted a pick - one question, two answers. The verb
# decides, as it does above. A line that only reports knowing ("i know what to wear to a wedding")
# asks nothing, so the ask has to open the line or follow a doubt; "i dont know what to cook" is
# that doubt and is still an ask.
WHAT_TO_OPENS = re.compile(
    r"^(?:so |and |ok |okay |now |also |please |but )?what to\b"
    r"|\b(?:i (?:don'?t|do not) know|not sure|no idea|dunno) what to\b", re.I)
WHAT_TO_PICK = re.compile(
    r"\bwhat to (?:cook|make|eat|have|drink|watch|read|listen to|wear|get|buy|order|play|study|"
    r"plant|visit|give|bring|pack|do with)\b", re.I)
WHAT_TO_STEPS = re.compile(
    r"\bwhat to (?:do|say|write|text|reply|feed|serve|take|try|check|avoid|ask|tell|keep)\b",
    re.I)
# Somebody else's question, told to the bot, is a report and not a question of the bot's own:
# "my brother asked me what to do", "she wants to know what she should take".
REPORTED = re.compile(
    r"\b(?:she|he|they|mum|dad|mom|someone|somebody|my \w+)\b.{0,25}"
    r"\b(?:asked|told|wonder\w*|wants to know|keeps asking)\b.{0,30}\bwhat\b", re.I)
# What to use in place of a thing the person has not got wants the substitutes, not a method:
# "what can i use instead of mince", "no yoghurt what can i use". What it is used *on* is
# another matter - "what can i use on a burn" - and is left alone rather than guessed at.
SUBSTITUTE = re.compile(
    r"\bwhat (?:do|should|shall|can|could) (?:i|we) use\b(?! (?:for|on|to)\b)"
    # "what can i use instead" is the substitutes; "what should i do instead" is the other method,
    # so `do` is not one of the verbs here.
    r"|\bwhat (?:else )?(?:do|should|shall|can|could) (?:i|we) (?:use|try|have|make)\b"
    r".{0,25}\binstead\b", re.I)
# "what do i have" asks for the list the person already gave, not for a thing to cook or eat;
# "what do i have for dinner" names the thing and is still a choice.
HAVE_RECALL = re.compile(r"^\W*what (?:do|did) i have\b"
                         r"(?! (?:for|on|in the|tonight|to eat|to wear|to drink))", re.I)
# "what do i do for a living" asks about the person's own job, not for a method of doing one.
NOT_STEPS = re.compile(r"\bwhat (?:do|does|did) (?:i|you|we|he|she|they) do for (?:a )?living\b|"
                       r"\bwhat (?:do|does|did) (?:i|you|he|she|they) do for work\b", re.I)
# A line that opens on another question word is that question first, whatever a later clause asks:
# "where do i register my mums death and what do i take" wants the place.
OTHER_QUESTION = re.compile(r"^\W*(?:where|when|who|whose|which|why|how|is|are|was|were|can|could|"
                            r"should|shall|would|will|does|did)\b", re.I)
# Understanding reads the "should i" or the "do i" of a measure question as a yes/no as well, so
# "how long should i boil an egg" carries both `how_long` and `yesno`. The measure is the question:
# a yes or a no is the wrong answer to every one of them, and the figure is the answer.
MEASURE_LABELS = frozenset(("how_long", "how_much", "how_often"))
# "where do i start" names no place: it is the same ask as "what do i do first", and understanding
# reads its "where" as one. The answer owed is the steps.
WHERE_START = re.compile(
    r"\bwhere (?:do|does|should|shall|can|could|would|will|to) (?:\w+ ){0,3}start\b"
    r"|\bwhere to (?:begin|start)\b", re.I)
# A thing's origin is not a place: "where does honey come from" is answered by the bees and the
# nectar, "where does paper come from" by wood and pulp - an explanation, not a town. Understanding
# reads the "where" as a place, so the good reply that explains the thing read as a miss for naming
# no place. A person's origin is still a place ("where do you come from", "where does she come
# from"), so only a thing's is read this way.
ORIGIN_ASK = re.compile(r"\bwhere (?:does|do|did) (?:\w+ ){0,3}(?:come from|grow)\b", re.I)
# "what is glass made of", "what are sausages made from": the making of the thing, which is the
# same answer an origin question wants and no `definition` label carries.
MADE_OF = re.compile(r"\bwhat (?:is|are) (?:\w+ ){0,3}made (?:of|from|out of)\b", re.I)
ORIGIN_PERSON = re.compile(r"\bwhere (?:does|do|did) (?:you|they|we|i|he|she|u)\b", re.I)
# "where's the point of any of it", "wheres the point in carrying on": despair, not a place.
# Understanding reads the "where" and the safety answer to it read as a miss for naming no place.
WHERE_POINT = re.compile(
    r"\bwhere(?:'s|s| is| was)\b[^?]{0,20}\b(?:the|any) point\b", re.I)
# A person's own whereabouts is a question for memory, not a place the world keeps. "where does she
# live", "where am i", "where was i going", "where's my phone" are answered from what the person
# has said - or honestly, "you haven't mentioned a place yet" - and no place named is not a miss.
WHERE_RECALL = re.compile(
    r"\bwhere (?:am|was) i\b|\bwhere (?:were|are) we\b|\bwhere we (?:left|were|are)\b"
    r"|\bremind me where\b"
    # A knowledge verb and a first person is the person asking the bot to recall their own facts:
    # "do you know where i live", "forgot where i put my keys". A report about somebody else is not
    # this: "my nan had a fall and doesnt know where she is" is a place ask, and the fall card
    # answers it - reading the "knows where she is" as a recall made a right answer a miss. So the
    # other person keeps only the words about where they live.
    r"|\b(?:know|knows|known|tell me|told me|remind|remember|forgot|forget|said)\b[^?]{0,25}\b"
    r"where (?:i|we|you) (?:live|work|are|were|went|put)\b"
    r"|\b(?:know|knows|known|tell me|told me|remind|remember|forgot|forget|said)\b[^?]{0,25}\b"
    r"where (?:he|she|they) (?:live|lives|work|works|stay|stays)\b"
    # One person's street is not a place the world keeps either: "where does john live", "where
    # does she work". The reply "you haven't said" is the answer, and no place named is right.
    # The subject has to be a person, though: a kind of thing with an article is a habitat and a
    # real place question - "where do penguins live" is answered by the penguins card, and reading
    # it as a recall of a fact the bot was never told made that right answer a miss.
    r"|\bwhere (?:does|did) (?!a |an |the )[a-z]{2,}(?: [a-z]{2,})? (?:live|work|stay)\b"
    r"|\bwhere (?:do|does|did) (?:i|you|he|she|we|they) (?:live|work|stay)\b"
    r"|\bwhere (?:do|does|did) (?:my|our|your|his|her|their) \w+(?: \w+)? (?:live|work|stay)\b"
    r"|\bwhere (?:do|does|did) i (?:decide|say|tell|mean|think|go\b[^?]{0,12}\b(?:last|before))"
    # Where the conversation was, not where a thing in the world is: "where did we leave off",
    # "where did we get to". The reply "we're at the beginning" is right and names no place. Only
    # the first person plural: "where do i leave the recycling" is a place ask and stays one.
    r"|\bwhere did we (?:leave off|left off|leave it|left it|get to|got to)\b"
    r"|\bwhere (?:did|do) we (?:get up to|got up to)\b"
    # Where a thing comes from is the fact about the world that `ORIGIN_ASK` reads lower down, not
    # a recall of what the person told the bot: "where does honey come from" wants the bees and the
    # nectar, and this arm answered it with nothing at all. A person's own origin keeps its place
    # reading through the arms above, which name the person.
    r"|\bwhere(?:'s|s| is| are| did i put| have i put| can i find)\b[^?]{0,20}\b"
    r"(?:my|me|our|the)\s+(?:phone|keys|key|wallet|purse|glasses|bag|bags|parcel|nappy|nappies|"
    r"coat|remote|passport|documents|bus pass|ticket|tickets)\b", re.I)
# The same readings for a line that is only that and nothing else: "where i live" alone asks the
# bot to recall it, while "what do i do about a flood warning where i live" is a method. `_said`
# joins every reading the engine kept, so the line sits in it several times and no anchor holds;
# these read the plain line instead.
WHERE_ALONE = re.compile(
    r"^(?:and |so |ok |okay )?where(?:'s|s| is| are) (?:it|that|this)$"
    r"|^(?:and |so |ok |okay )?where (?:i|we|you) (?:live|work)$"
    r"|^where (?:do|does|did) i (?:live|work)$", re.I)


def _whole(understood):
    """The line as the person typed it, for the few readings that need the whole of its shape."""
    for key in ("plain", "text"):
        value = understood.get(key)
        if isinstance(value, str) and value.strip():
            return " ".join(value.lower().replace("\u2019", "'").split())
    return ""

# A where that asks for a suggestion - "where should we eat", "where should we go in october" - is
# still a place ask, and it was tempting to let it go: a few ideas are one way to answer it. They
# are not. Over the 55 such lines in the deck, 47 replies name a place and are right, and the 8 that
# name none are all the same reply, "Decide in this order ... then pick a place whose menu is short"
# - the way to choose instead of anywhere to choose. That is the miss this lane exists to count, so
# the suggestion keeps its place reading and the answers lane has a named target.
# "how do i answer where do you see yourself in five years" is a request for the way to say
# something, and the "where" inside it is the question being quoted.
# ... and the same ask said of somebody else's question: what to say back. Only the first person
# answering ("how do i answer why i left") and the asked-of-you form ("what do you say when they
# ask ..."), because "what would you say to him" and "what do you say about the chewing" are the
# person's own advice to give, not a question to be answered.
HOW_TO_ANSWER = re.compile(
    r"\b(?:how|what) (?:do|should|can|could|would) i (?:answer|reply to|explain|word|phrase)\b"
    r"|\b(?:what|how) (?:do|should|would) you say when they ask\b", re.I)
# A who that shares its line with a measure is not the ask: "who pays what when one earns more"
# wants the rule for the split, and the good reply that gives the rule read as a miss for naming
# no person. A who on its own ("who do i ring about a council tax refund") still owes a name.
WHO_AND_MEASURE = re.compile(r"\bwho\b[^?]{0,40}\b(?:what|how much|how many)\b", re.I)
# A `who` that belongs to a noun is not a who-question: "should i chip in for a present for the
# woman who is leaving" is a yes/no with a relative clause in it, and it was read as a request for
# a person's name, so "Chipping in is a shared cost split between the people it is for..." was a
# miss. The `who` after a noun is the noun's own clause - "the woman who is leaving" is one person,
# not a question about who she is.
# A `who` followed by a pronoun and "am/are/is" is the person talking about themselves, not a
# question about who anyone is: "i dont know who i am now" was read as a request for a name and
# "I'm listening - say more if it helps." was a miss.
WHO_OF_A_PRONOUN = re.compile(r"\bwho (?:i|you|we|they|he|she|it) (?:am|are|is|was|were)\b", re.I)
WHO_OF_A_NOUN = re.compile(
    r"\b(?:the|a|an|this|that|these|those|someone|somebody|anyone|anybody|everyone|everybody|"
    r"no one|nobody|person|people|man|woman|boy|girl|child|kid|friend|colleague|neighbour|"
    r"neighbor|boss|manager|teacher|nurse|doctor|carer|minder|babysitter)\s+who\b", re.I)

# A line that opens on its who asks it, whatever person it names later: "who should i call about
# a neighbour who plays loud music" owes a name, and only the second who is the relative one.
WHO_OPENS = re.compile(r"^\W*(?:(?:and|so|but|then|or|also|now|ok|okay)\s+)?who(?:'s|s|se)?\b", re.I)
# The best way to do a thing is the method for it, not a thing picked: "what's the best way to
# cook rice" was read as a recommendation and answered with a pick. `best` is not the only word
# that judges a way: "what's the easiest way to peel a kiwi" and "the quickest way to chill a
# drink" were read as nothing at all, so the shape was lost and a method read as a miss. The
# judgement word has to be in front of `way`, `method` or `approach`, which is what keeps a
# judgement about a thing ("what is a good price", "a good breakfast") out of it.
BEST_WAY = re.compile(
    r"\b(?:the )?(?:best|good|right|proper|easiest|quickest|simplest|safest|cheapest|fastest) "
    r"(?:way|method|approach) (?:to|of|for)\b", re.I)
# "whats a good present for him", "whats a good tent for two": understanding reads the `what is`
# as a definition and the reply that offers ideas was a miss for not defining the word. Only a
# measure word keeps its own shape, and that is read before this ("what is a good time to go").
# "whats a good salary for a graduate", "whats a good interest rate", "whats a good credit score":
# a measure word asked for with "whats a good" wants the figure. The good-thing reading below turns
# it into a few to choose from, and no card of prices and rates answers a list. A "good tip for a
# first date" is advice and keeps its few ideas, so a tip only counts as money when nothing follows.
GOOD_MEASURE = re.compile(
    r"\bwhat(?:'s|s| is)\s+(?:a |an |the )?(?:really |actually |roughly |sensible |sort of )?"
    r"(?:good|decent|normal|typical|average|usual|realistic|fair)\s+(?:\w+\s+){0,2}"
    r"(?:salary|wage|wages|pay|income|rate|deposit|budget|score|pension|pot|percentage|percent"
    r"|tip(?!\s+(?:for|on|to|about)\b))\b", re.I)


GOOD_ONE = re.compile(r"\bwhat(?:'s|s| is) (?:a |an )?good\b", re.I)
# "how come the milk curdled" asks the cause, and understanding reads its "how" as a method, so
# the reply that says why read as a miss. "how come" is the everyday "why", never a how-to.
HOW_COME = re.compile(r"\bhow come\b|\bhow is it that\b", re.I)
# "what are the best museums in rome", "what are some good films to watch": a plural after the
# best, or "some/a few", asks for a few to choose from. Understanding reads the "what" as a
# definition and the reply that lists three museums read as a miss for not being a meaning.
BEST_OF_MANY = re.compile(
    r"\bwhat (?:are|were) (?:the )?(?:best|main|top|nicest|cheapest|better)\b"
    r"|\bwhat (?:are|were) (?:some|a few|any)\b"
    r"|\bwhat (?:are|were) (?:the )?\w+ (?:to|for)\b", re.I)
# "is that expensive", "is it pricey to run", "are they cheap": the whole predicate is the price,
# so the answer is the figure and the verdict rides with it - "A car MOT costs up to £54.85 ..." is
# the answer to "is that expensive". Understanding reads the "is it" as a yes/no, and a price
# answer then read as a miss for not opening with yes. Only a pronoun for the subject: "is a cheap
# guitar a waste of money" asks about the waste, not the price.
A_PRICE_ASK = re.compile(
    r"\b(?:is|are|was|were)\s+(?:it|that|this|these|those|they|there|one)\s+"
    r"(?:(?:too|so|really|actually|very|quite)\s+)?"
    r"(?:expensive|pricey|dear|cheap|costly)\b", re.I)
# A comparison ("cheaper than dried"), a worth ("worth it") and an affordability ("can i afford
# it") are verdicts with a reason, not a figure, so they keep their yes/no.
NOT_A_PRICE_ASK = re.compile(r"\bworth\b|\bcheaper than\b|\bmore expensive than\b|\bafford", re.I)
# "what are my rights", "what are my entitlements", "what are our obligations": a possessive asks what
# applies to this person, not what a word means. Understanding reads the "what are" as a definition,
# so the advice the bot gives ("Put it in writing, a text or email is fine, and keep a copy") was
# named a miss for answering the question that was asked. Read before the definition block below,
# and left alone by a line that asks what a thing is called or means.
WHAT_ARE_MINE = re.compile(
    r"\bwhat(?:'s| is| are|s)\b[^?]{0,40}?\b(?:my|our) (?:[a-z]+ ){0,2}"
    r"(?:rights?|entitlements?|obligations?)\b", re.I)

# A meaning is asked for by "what is a p60", "what does a p60 show", "what does it mean", "what do
# you call", "the difference between". Understanding writes `definition` off the word "what does"
# alone, so "what does my sister like" and "what does it cost" arrived as definitions of a word.
ASKS_FOR_MEANING = re.compile(
    r"\bwhat (?:is|are|was|were|'s)\b"
    # "what does engine oil do", "what does a full service include", "what does a p60 show": the
    # thing a subject does, holds or covers *is* what it is, so this is still a meaning ask.
    r"|\bwhat (?:does|do)\b(?:(?!\bwhat\b)[^?]){0,30}?"
    r"\b(?:do|does|include|includes|cover|covers|contain|contains|show|shows|sound like)\b"
    r"|\bwhat do you call\b|\b(?:mean|means|meaning|stand for|stands for|short for)\b"
    r"|\bdifference between\b", re.I)
# A number in front of the word `steps` does not make it a method: it is the unit the person
# walked in. Understanding reads the word as the ask for steps on every line that holds it, so
# "i did 12000 steps today" was a steps question and a good answer to "is 10000 steps a day
# enough" was a miss. Where the steps are counted - a figure in front of the word, a step count,
# or a count of them per day or per mile - the word is a measure, and the shape of the answer is
# whatever else the line asks. A line that does ask how to do it keeps the method, because the
# strong readings below return before this one: "how do i get my step count up", "steps to bleed
# a radiator".
STEPS_ARE_COUNTED = re.compile(
    r"\b\d[\d,]*\s*(?:k\s+)?steps?\b"
    r"|\bsteps? count\b"
    r"|\bsteps? (?:a|per|each|every) (?:day|week|month|hour|mile|km|kilometre)\b", re.I)
# "10000 steps in miles" and "steps per mile" are a conversion: the person knows the count and
# wants the distance, which is the figure, not the walk.
STEPS_AS_A_DISTANCE = re.compile(
    r"\bsteps? (?:in|into|to|per|versus|vs)\s+(?:a |one )?(?:mile|miles|km|kilometre|kilometres|"
    r"kilometer|kilometers)\b"
    r"|\b(?:mile|miles|km|kilometre)s? (?:in|to|from|of) (?:a |one )?\d[\d,]*\s*(?:k\s+)?steps?\b",
    re.I)


# A length of time said as a count of its unit: "how many hours between doses", "how many days
# does a cold last", "how many weeks pregnant am i". Understanding reads the "how many" as
# `how_much` and the shape came out an amount, so the reply was free to give any number at all -
# and "how many hours between ibuprofen doses" was answered with the dose, which is an amount.
HOW_MANY_TIME = re.compile(
    r"\bhow (?:many|much) (?:more |longer )?(?:seconds?|secs?|minutes?|mins?|hours?|hrs?|days?|"
    r"weeks?|months?|years?|nights?|time)\b", re.I)


# The phrases that ask for a cause without the word why.
REASON_ASK = re.compile(
    r"\bhow come\b|\bwhat (?:causes|caused|causing|is causing)\b|"
    r"\bwhat(?:'?s| is| was)?\s+(?:causing|making|the cause|the reason)\b|"
    # "what makes thunder", "what makes you sneeze", "what makes my chest hurt" ask for the cause.
    # "what makes soup thick without cream" and "what makes a villain believable" ask how, and a
    # method is the right answer to them, so they are left to the shapes that read how-asks: the
    # question word of a "what makes X <quality>" is "how", not "why".
    r"\bwhat (?:makes|made) (?:you|me|us|people|him|her|them|it|this|that|someone|"
    r"my|your|our|their|his|its)\b|"
    r"\bwhat (?:makes|made) (?:the |a |an )?[a-z']+(?:(?: and| or) (?:the |a |an )?[a-z']+)*\s*$",
    re.I)

# "whats the point of a dehumidifier", "any point in solar panels", "point of a warm up": the
# point of a named thing is the reason it is done, and a description of the thing, a price or a
# method answers a different question. The thing is read after the "of"/"in" so that a line about
# the point of nothing in particular is left to the shapes that comfort it.
POINT_ASK = re.compile(
    r"\bwhat(?:'?s| is| was)?\s+the point (?:of|in)\s+(\w+(?: \w+){0,2})"
    r"|^(?:any )?point (?:of|in)\s+(\w+(?: \w+){0,2})", re.I)
# "whats the point of any of it", "i just dont see the point in anything anymore": no thing, so no
# purpose is owed and the line is not read as a reason at all. A measure of a thing - a boiling
# point, a freezing point - is not the point of it either, and is kept out below.
POINT_NOT_A_THING = frozenset("""
    it this that these those anything everything nothing any all carrying carry continuing going
    living life you me us them anymore honestly really now boiling freezing melting smoke
    """.split())


# A bare follow-up, with no question word of its own: "and for brown rice", "what about once it is
# up", "and which of those two". It asks for the same kind of answer about something else, so it
# wants whatever the line before it wanted. Read on its own it is nothing of the kind: "and for
# brown rice?" after "how long does rice take" is a plain ask for the facts of brown rice, and the
# answer it is owed - a time - cannot be checked at all.
FOLLOWUP = re.compile(
    r"^\s*(?:and|so|then|but|ok(?:ay)?[,\s]+(?:and|so)|what\s+about|how\s+about|what\s+if|"
    r"would\s+that|does\s+that|same\s+(?:for|with))\b", re.I)
# A follow-up that asks its own question about the person's own next move is a new question, not
# the last one again: after "is it going to rain tomorrow", "so what do i take with me" is not a
# yes or a no. The verb is the person's own, so the answer shape is theirs too.
NEW_ASK = re.compile(r"\bwhat (?:do|does|should|shall|can|could|will|would) (?:i|we|you)\b", re.I)


def asks_a_follow_up(understood):
    """True when the line is a bare follow-up: it opens on "and"/"what about" and asks nothing new."""
    if not isinstance(understood, dict) or understood.get("asks_a_verdict"):
        return False      # "and is that safe" asks the bot's own last answer a verdict
    said = _said(understood)
    if not FOLLOWUP.search(said):
        return False
    if set(understood.get("asks") or ()) - {"what", "yesno"}:
        return False      # it has a question word of its own: "and how much", "so which is better"
    if NEW_ASK.search(said):
        return False      # "so what do i take with me" asks something new of its own
    kind = understood.get("kind")
    if kind == "question" or said.rstrip().endswith("?"):
        return True
    # "and for brown rice" has no question mark and reads as a statement, but the reading knows it
    # leans on the line before. A short one of those is the same question again; a longer one is
    # the person adding something of their own ("and i also need a bin bag").
    line = str(understood.get("plain") or understood.get("text") or "")
    return kind == "statement" and bool(understood.get("followup")) and len(line.split()) <= 6


def wants(understood, before=None):
    """The shape of answer the line asks for, or None when the line does not ask for one.

    Read from the whole line's reading, not one keyword. `asks_a_verdict` ("is that bad", "should
    i worry") is a yes/no about the bot's own last answer and comes before every `asks` label;
    `help_ask` ("anything i can do about it") is a bare ask for steps. A question about the bot
    itself ("who are you") wants the bot's own answer and no shape from this list, so it is left
    alone rather than read as a who-question that owes a person's name.
    """
    if not isinstance(understood, dict):
        return None
    own = _wants_alone(understood)
    if own:
        # The line asks for a shape of its own: "and can i freeze it" after "how long does rice
        # take" is a question about whether, and a time would answer a different question.
        return own
    if before and asks_a_follow_up(understood):
        return before     # nothing of its own, so it is the same question again about something else
    return None


def _wants_alone(understood):
    """The shape this line asks for on its own words, ignoring the line before it."""
    if understood.get("about_bot"):
        return None
    if understood.get("asks_a_verdict"):
        return YESNO
    if understood.get("help_ask"):
        return STEPS
    asks = understood.get("asks")
    asks = set(asks) if isinstance(asks, (list, tuple, set)) else set()
    said = _said(understood)
    # A line the engine reads as news is the person telling the bot something, not asking: "my
    # brothers birthday is on the 2nd of june" carries `maths` for the 2nd and "we were thinking
    # italy or spain" carries `choice` for the two countries, and neither owes a figure or a pick.
    # "A birthday to get something for. Any idea what yet?" and "Sounds alright. Anything good in
    # it?" were scored as replies that missed a question nobody asked. Only the two loose labels
    # are dropped: a how-long, a why or a where on a news line is still asked for.
    if understood.get("intent") == "news":
        asks -= frozenset(("maths", "choice"))
    # A statement that only carries the words of a measure is not asking for one: "its amazing how
    # much room there is" and "i didnt know how long it would take" name no figure to go and find.
    # Only a line that asks - a question, or a request like "tell me how long it takes" - owes one.
    asking = (understood.get("kind") == "question"
              or understood.get("intent") in ("question", "request"))
    # "how are you" has the word how and asks for no shape at all.
    if HOW_ARE_YOU.match(said):
        return None
    # A request for help with a thing is the help itself: "can you help me with a budget" is a
    # steps question, not a yes/no about whether the bot can.
    if HELP_ME.search(said):
        return STEPS
    # Neither "where do i start" nor "the best way to ..." asks for a place or a pick, whatever
    # their words look like: both want the method.
    if WHERE_START.search(said) or BEST_WAY.search(said):
        return STEPS
    # A "where" on the point of something asks for a reason to carry on, and no place answers it.
    if WHERE_POINT.search(said):
        return None
    # A "where" about somebody's own whereabouts, or about where a thing comes from, is not a
    # place the world keeps: it is answered from what the person said ("you haven't mentioned a
    # place yet") or by what makes the thing ("bees make it"). No place named is the right answer.
    if WHERE_RECALL.search(said) or WHERE_ALONE.search(_whole(understood)):
        return None
    if HOW_TO_ANSWER.search(said):
        return STEPS
    # "how come the milk curdled" is a why, not a how-to, and wants the cause.
    if HOW_COME.search(said):
        return REASON
    # A first-person how asks for the method, whatever measure word rides along with it:
    # "how do i plan a long drive" carries `how_long`, "how do i stop getting so many emails"
    # carries `how_much` and "how do i memorise a list quickly" carries `list`, so each of those
    # readings owed the person a figure or a menu instead of the steps they asked for. The engine
    # has already labelled these `steps`; this keeps the label rather than letting a word of the
    # line outrank it. Two things still outrank it: a sum with figures in it ("how do i divide 45
    # by 9" wants the number) and weighing the person's own life against somebody else's ("how do
    # i compare myself to others" is a pick, and so is "how do i compare to my sister").
    if ("steps" in asks and HOW_I.search(said) and not COMPARE_MYSELF.search(said)
            and not (("maths" in asks or "how_much" in asks) and re.search(r"[0-9]", said))):
        return STEPS
    # An overview of the kinds of a thing is a menu, not the meaning of a word and not one idea to
    # take: "what kinds of coffee are there", "what types of insulation can i get", "what are my
    # options for a new phone", "what else is there for a sore throat". The identifying form - "what
    # kind of dog is that" - asks what the one in front of the person is, so it is left to the
    # readings below rather than read as a menu.
    # The method asked for as a set of steps comes first: "what are the steps to reset a boiler"
    # holds the same "what are the ..." as the menu below, and only one of them is the answer.
    if STEPS_ASK.search(said) and not (COUNTED_STEPS.search(said)
                                       and not re.search(r"\bhow (?:do|can|should) i\b", said)):
        return STEPS
    # The signs, symptoms and stages of a thing are the members of a set, not the meaning of the
    # word: "what are the early signs of dehydration" is answered by the four signs, and the reply
    # that listed them was scored for not defining anything.
    if MEMBERS_ASK.search(said):
        return OPTIONS
    if KINDS_OF.search(said) and not NOT_KINDS_OF.search(said):
        return OPTIONS
    # A comparison names two things and wants both of them and what sets them apart, which is a
    # different answer from taking a side: "compare a dehumidifier and a window vac", "gas vs
    # electric hob", "how does a heat pump compare with a gas boiler", "what sets a leasehold apart
    # from a freehold", "is a heat pump better than a gas boiler". A line that names two sides and
    # asks which to take is a pick, so a should-i or a worth asking it keeps the pick below.
    if (COMPARISON.search(said) or COMPARED.search(said)) \
            and not NOT_A_COMPARISON.search(said) \
            and _names_a_pair(said) and _asks_about_them(understood, said):
        return COMPARE
    # Where a thing comes from is how it is made: "where does honey come from" wants the bees and
    # the nectar, and it is the same answer a `what is it` would get. See ORIGIN_ASK.
    if (ORIGIN_ASK.search(said) and not ORIGIN_PERSON.search(said)) or MADE_OF.search(said):
        return MEANING
    # A few to choose from, not the meaning of a word: "what are the best museums in rome". Not
    # when the plural is a price word the line is asking about: "what are the fees for a passport"
    # and "what are the charges for a replacement" match this reading - a plural after "what are
    # the" and a "for" - and were answered with a list to choose from instead of the money.
    if BEST_OF_MANY.search(said) and not (COST_ASK.search(said) and asks <= COST_STANDS_IN):
        return OPTIONS
    # "what are my rights" is a question about the person's situation and wants what to do next,
    # not the meaning of a word.
    if ("definition" in asks and WHAT_ARE_MINE.search(said)
            and not re.search(r"\b(?:called|mean|means|meaning|stand for|stands for)\b", said)):
        return STEPS
    # A definition is owed only when the line asks what a thing is or means; understanding writes
    # the label off the words "what does", which also ask what someone likes and what a thing costs.
    if ("definition" in asks and re.search(r"\bwhat does\b", said)
            and not ASKS_FOR_MEANING.search(said)):
        asks.discard("definition")
    # A statement owes nobody a definition, whatever word it carries: "thanks, that explains the
    # boiler", "that explains the noise". Understanding writes `definition` off "explains", which
    # is not an ask; a line that does ask - "what does that mean", "the difference between" - is
    # left alone.
    if "definition" in asks and not asking and not ASKS_FOR_MEANING.search(said):
        asks.discard("definition")
    # "whats a good podcast for the car", "wats a gud cake", "wots a good cheap pressie": a good or
    # cheap or quick thing is asked for as a few to choose from, not the meaning of a word.
    # Understanding labels the "what" a definition, and the pick the bot gives then reads as an
    # answer to a different question. A good way to do something is the method, not a few ideas.
    # A measure word asked for with "whats a good" wants the figure: "whats a good salary for a
    # graduate", "whats a good interest rate", "whats a good credit score". The reading below hands
    # any good thing a few to choose from, and no card of prices and rates answers a list.
    if GOOD_MEASURE.search(said):
        return AMOUNT
    if GOOD_THING.search(said) and "definition" in asks and not GOOD_FIGURE_WORD.search(said):
        return STEPS if GOOD_WAY.search(said) else OPTIONS
    # The mechanism of a thing is a meaning, and understanding reads its bare "how" as a method:
    # "how does a lock and key work", "how do tides work". Only the "how do/does/did <thing>
    # work" form, never "how do i work out a tip" (a method) and never "how is work" (small talk).
    if HOW_IT_WORKS.search(said) and not re.search(r"\bhow do i\b", said, re.I):
        return MEANING
    # A who the person in the line already owns is the relative pronoun, not the ask:
    # "a present for my sister who just had a baby" wants a present, not the name of a person.
    if "who" in asks and not WHO_OPENS.match(said) and _a_who_a_person_owns(understood):
        asks.discard("who")
    # A who that shares its line with a measure asks for the rule, not the name of a person.
    if "who" in asks and (WHO_AND_MEASURE.search(said) or WHO_OF_A_PRONOUN.search(said)
                          or (WHO_OF_A_NOUN.search(said) and not WHO_OPENS.match(said))):
        asks.discard("who")
    # The "where" of "should i stay where i am" is the pronoun of a clause, not the place the
    # line asks for: it asks whether, and the verdict is what it is owed. A line that asks to be
    # told the place - "can you tell me where it is" - keeps its place.
    if "where" in asks and (asks & frozenset(("yesno", "recommend"))) \
            and WHERE_RELATIVE.search(said) and not ASKS_TO_BE_TOLD_WHERE.search(said):
        asks.discard("where")
    # A measure question wants the figure, whatever else its words carry: "how long should i boil
    # an egg" and "how often should i wash the bedding" both read as `how_long`/`how_often` and a
    # yes/no from the "should i", and a yes/no is the wrong answer to either.
    # A conversion of a length asks for a figure in other units: "how long is 100m in feet" is
    # not a question about time, whatever the word "long" says, so it is read before the measure.
    if CONVERSION.search(said):
        return AMOUNT
    # A measure question that is not asking for a measure: "how much do you know about boilers"
    # asks about the bot, and "how much does it matter" asks whether it matters at all. Neither
    # owes a figure, and the how_much label is on both, so the guard stands in front of the
    # reading rather than after it.
    if NOT_A_FIGURE.search(said):
        return None
    if asks & MEASURE_LABELS and asking:
        # A written thing's "how long" is a length in words, pages or characters and not in
        # minutes: "how long should a personal statement be" is the 4,000-character limit,
        # "how long should an essay be" the word count. The noun followed by "be" is what tells
        # it from "how long should i leave it before replying to a text", which is a duration.
        if "how_long" in asks and WRITTEN_THING.search(said):
            return AMOUNT
        # "how many hours between doses" is a time and not an amount: the figure is a number of
        # hours. Main keeps its own "how_long" reading and this adds the counted unit to it.
        return TIME if "how_long" in asks or HOW_MANY_TIME.search(said) else AMOUNT
    # A price or a weight asked for with "what does" is the figure, not the meaning of a word:
    # "what does a boiler service cost", "what does a cup of honey weigh", "what do tyres cost".
    if WHAT_DOES_MEASURE.search(said) and not ASKS_FOR_MEANING.search(said):
        return AMOUNT
    # ... and a price asked as a definition wants the figure too.
    if WHAT_IS_PER.search(said):
        return AMOUNT
    if "how" in asks:
        # A how that measures something wants the figure, and understanding reads the word after
        # "how" as a method: "how tall am i" is an amount, "how soon can i fly" a time.
        if HOW_SOON.search(said):
            return TIME
        if HOW_MEASURE.search(said):
            return AMOUNT
        # A line that opens on a measure word wants the figure, whatever "should" makes of the rest
        # of it: see HOW_MEASURE_HEAD.
        if HOW_MEASURE_HEAD.match(LEADING_JOIN.sub("", said)):
            return AMOUNT
        # "how do i explain moving house to my son" is a method; "explain" had it read as a
        # definition, which owes a meaning rather than the steps. It is only a method when the
        # person does the explaining: "explain how wifi works to me" and "how does darts scoring
        # work" want the meaning itself, and a reply that explains it is not a miss.
        if HOW_TO_DO.search(said):
            asks.discard("definition")
    # A question that opens on "when" wants a time; a "when" inside a clause does not.
    asked = LEADING_JOIN.sub("", said)
    if WHEN_ASKS.match(asked) and not WHICH_DAY_IS_BEST.search(said):
        return TIME
    # "what are hospital visiting times", "what are the opening times of the tip", "what are the
    # school term dates": understanding reads the "what are" as a definition, so the line came out
    # wanting the meaning of a word. What it wants is on the clock. A line that asks what a thing
    # is *called* still wants the meaning ("what are those times called").
    if WHAT_ARE_TIMES.match(said) and not REPORTED.search(said) and not re.search(
            r"\b(?:called|mean|means|meaning|stand for)\b", said):
        return TIME
    # "what is a good half marathon time" is a figure, and understanding reads its "what" as a
    # definition. A good or average time, age, price or number is the figure that follows.
    if GOOD_FIGURE.search(said):
        return AMOUNT if re.search(r"\b(?:age|price|number|amount|cost)\b", said) else TIME
    # A good thing is a thing to pick, not a word to define.
    if GOOD_ONE.search(said):
        return OPTIONS
    # A what-should-i-cook/watch/wear names an open choice and wants one thing picked; the verb
    # is what tells it from "what should i do first", which wants the steps. Understanding already
    # calls a `what should i have` a choice, so the `do` spelling of the same verbs is read here -
    # except a `what do i have`, which is a recall of the list the person already gave.
    # A question that names the unit of the figure it wants owes the figure: "what temperature
    # should i cook chicken at", "what gas mark for a sponge".
    if WHAT_FIGURE.search(said):
        return AMOUNT
    # "what helps a sore throat" wants the few things that might work, and "what would you take
    # to a new baby" the list of things: both are a few ideas, not one method, not a definition.
    if WHAT_HELPS.search(said) or WHAT_YOU_TAKE.search(said) or WHAT_I_NEED.search(said):
        return OPTIONS
    # The same ask said to the bot: "what do you do about that" is the method.
    if WHAT_YOU_DO.search(said):
        return STEPS
    if (PICK_ONE.search(said) or PICK_ONE_OF_A_KIND.search(said)
            or (WHAT_TO_OPENS.search(said) and WHAT_TO_PICK.search(said))):
        return None if HAVE_RECALL.match(said) else PICK
    # "what can i use instead of mince" wants the substitutes, which is a few ideas and not a
    # method, so the instead is read before the steps below.
    if SUBSTITUTE.search(said):
        return OPTIONS
    # Asked what to do, say or try, the person wants the steps, whatever `asks` says: understanding
    # reads the `what should i do` spelling as steps and the rest as a bare `what`. A question
    # somebody else asked, told to the bot, is a report and owes no shape of its own; a job is not
    # a method; and a line that opens on another question word is that question first.
    if ((WHAT_TO_DO.search(said)
         or (WHAT_TO_OPENS.search(said) and WHAT_TO_STEPS.search(said)))
            and not REPORTED.search(said) and not NOT_STEPS.search(said)
            and not OTHER_QUESTION.match(said)):
        return STEPS
    # A cause asked without the word why wants the reason, and understanding carries `why` only
    # for the word itself: "what causes colic", "what makes thunder", "how come my kettle furs up".
    # A statement about a reason ("work is the reason theyre cutting hours") and a cause somebody
    # else was reported to have asked are not questions here.
    if asking and not REPORTED.search(said) and REASON_ASK.search(said):
        return REASON
    # The point of a named thing is the reason it is worth doing, and nothing else answers it:
    # "whats the point of a warm up", "any point in solar panels". A fragment carries no question
    # word of its own, so this is read without the `asking` test above.
    found = POINT_ASK.search(said)
    if found:
        thing = (found.group(1) or found.group(2) or "").split()
        if thing and thing[0] not in POINT_NOT_A_THING:
            return REASON
    # "worth a go i suppose" carries the "worth" of a recommendation but asks nothing: a line
    # that names no question and does not open on one is a remark, and owes no shape. Neither does
    # a remark that only holds the words of a measure ("no idea how much it costs").
    if (asks <= ({"recommend"} | MEASURE_LABELS) and not said.rstrip().endswith("?")
            and not ASKS_OUT_LOUD.match(said)):
        return None
    # What the difference between two things is wants the two of them explained, not a side taken:
    # "what is the difference between leasehold and freehold" is the pair of definitions, and a
    # pick would be answering something else.
    if DIFFERENCE.search(said):
        return MEANING
    # Two named sides are a pick whatever else the line asks; a yes/no with no second side is a
    # verdict even when understanding also reads the "worth it" as a recommendation.
    if asks & PICK_SIDES:
        return PICK
    # A count of steps is a distance or a number of them, not a method: the word is the unit, so
    # the shape is whatever else the line asks (a verdict for "is 10000 steps a day enough", the
    # figure for "10000 steps in miles", nothing at all for "i did 12000 steps today").
    if STEPS_ARE_COUNTED.search(said) or STEPS_AS_A_DISTANCE.search(said):
        asks.discard("steps")
        if STEPS_AS_A_DISTANCE.search(said):
            return AMOUNT
    # A price asked as an adjective on the thing wants the figure, not a verdict: the reply people
    # get for "is paris expensive" is "about 65 to 110 pounds a day", and a yes/no check reads that
    # as an answer in the wrong shape. The comparison and the value questions are read above.
    # The question after the price is read on the line itself, not on `said`: `_said` repeats the
    # line for each of its spellings, so "is it expensive" comes back as "expensive is it" and the
    # repeat looks like a second question.
    if (PRICE_ADJECTIVE.search(said) and not PRICE_ADJECTIVE_KEEPS.search(said)
            and not PRICE_ADJECTIVE_THE_ASK_IS_LATER.search(_line_text(understood.get("text")))
            and not asks & PRICE_ADJECTIVE_WHY):
        return AMOUNT
    # A yes/no is the weakest reading in the list: understanding labels it on every line that
    # opens on an auxiliary, so "how long do i boil an egg" comes in as `how_long` and `yesno` and
    # "how much should i be saving a month" as `how_much` and `yesno`. The question word is the
    # question; the auxiliary is only the grammar. So a how-long, a how-much, a where, a who, a
    # why, a definition, a list, a steps or a how wins, and a bare yes/no is read only when there
    # is no ask of its own beside it. "is it worth it" keeps its verdict, because `recommend`
    # alone is not one of those asks.
    # The price word is what the why is about, so the cause is the answer: "why is it so
    # expensive to fix a boiler" asks why the fix costs, and `A_PRICE_ASK` below reads the
    # adjective as a request for the figure and answers it with a number.
    if PRICE_ADJECTIVE.search(said) and asks & PRICE_ADJECTIVE_WHY:
        return REASON
    # "is that expensive" wants the price, not a yes: see `A_PRICE_ASK`.
    if A_PRICE_ASK.search(said) and not NOT_A_PRICE_ASK.search(said):
        return AMOUNT
    if "yesno" in asks and not (asks & SPECIFIC_ASKS):
        return YESNO
    # "what does a bathroom cost", "whats the price of a pint": the asks say what the thing is,
    # and the line asks what it costs, so the figure is the answer it wants.
    if COST_ASK.search(said) and asks <= COST_STANDS_IN:
        return AMOUNT
    for shape, labels in ASKED_FOR:
        if (asks - (frozenset() if asking else MEASURE_LABELS)) & labels:
            # A figure in a statement is not an ask: "my shift starts at half 5" is when the
            # person works and "my phone is on 2 percent" is news. Only a question owes a sum,
            # unless the line is a sum said out loud ("split 120 between 4 people").
            if shape == AMOUNT and "maths" in asks and "how_much" not in asks and \
                    understood.get("kind") != "question" and \
                    not (SUM_OUT_LOUD.search(said) or SUM_ASKS.search(said)):
                continue
            return shape
    return None


# "or" is the mark of a choice offered: two things, take one. A list joined by commas and "and"
# is one plan ("a film, a walk and a call, then tea"), and a colon then a clause is not a choice.
# An answer to a yes or a no rarely opens with yes or no. It says why ("Tea has enough caffeine to
# keep you awake, so after 2pm is too late"), what the thing is, or the figure the yes depended on,
# and every one of those is the answer the person was waiting for. Read without the line, a cause,
# a definition or a figure is evidence about the reply rather than a verdict on it - "Two years'
# service is the line" carries a figure, "Because the seal has gone" carries a cause - so this
# reading is only ever made where the line is known to have asked whether.
#
# It is not made for a reply that tells the person what to do. A method can carry a time or a
# figure as easily as a verdict can, and then the figure belongs to the how-to: "Sort by colour,
# not by kind of garment: dark cottons together on 40" is no answer to "should i run a hot wash
# with vinegar", and "Sow basil indoors from late April" is no answer to "is that ok for the
# plant". Any verb at the front says the reply is a method, not only the ones this file lists, so
# the word after the first is read: a subject there carries a verb with an -s on it ("It varies",
# "Caffeine lasts", "A scrum restarts") and an object does not ("Sow basil", "Sort by colour").
NOT_A_VERB_HEAD = re.compile(
    r"^(?:a|an|the|it|it's|its|there|this|that|these|those|they|them|we|you|i|he|she|both|all|"
    r"some|most|many|one|two|three|four|five|six|seven|eight|nine|ten|from|in|at|on|for|to|with|"
    r"without|after|before|about|around|once|if|when|until|roughly|up|down|by|as|of|no|not|"
    r"nothing|nobody|never|always|usually|often|your|my|our|his|her|their|every|each|another|"
    r"any|much|little|few|several|such|what|who)\b", re.I)


# A reply that offers to do the thing is an answer to "can you", whatever it opens on.
I_OFFER = re.compile(
    r"\b(?:i'll|i will|i can|i'd|we'll|we can|let me|i've|i would)\b", re.I)

# The offer is an answer to a line that asks the bot to do something, and to almost nothing else:
# "I can work things out - sums, plans" is the bot describing itself, "I'd do a bean stew" is a
# recipe, and "I would start here" is advice. 43 of 297 deck replies carry one of those phrases,
# so an ungated offer arm says yes to a seventh of the deck.
ASKS_THE_BOT = re.compile(r"\b(?:can|could|would|will)\s+(?:you|u)\b|\bdo you\b|\bare you\b", re.I)


# A bare count is not the figure a yes rested on: "Two different claims" opens on a number and
# says nothing about how much of anything. The figure that answers a yes or a no carries its unit:
# "60 to 80mg", "78 calories", "three hours", "6 to 7p a unit".
A_UNIT = re.compile(
    r"\d|\b(?:mg|g|kg|ml|l|litres?|liters?|cm|mm|metres?|meters?|feet|foot|inches?|degrees?|c|f|"
    r"hours?|hrs?|minutes?|mins?|seconds?|days?|weeks?|months?|years?|nights?|p|pence|pounds?|"
    r"quid|grams?|calories|kcal|watts?|kw|kwh|amps?|volts?|per\s+cent|%)\b", re.I)


def _an_amount_with_a_unit(opening):
    return bool(_an_amount(opening)) and bool(A_UNIT.search(opening))


# A reply whose subject is a pronoun is about what was just said, so the thing can be named
# anywhere in it: "is coffee keeping me awake" / "It varies with the drink: a mug of instant
# coffee is 60 to 80mg". Any other opening names its own subject first, and that is what the
# reply is about.
POINTS_BACK = re.compile(r"^(?:it|it's|this|that|these|those|they|them|there|its)\b", re.I)

# Words that name nothing: "the" alone made every reply about the line's thing, because an
# opening sentence nearly always has one. "tea", "vet", "dog" and "cat" name things and stay in.
# The four- and five-letter ones are here for the same reason as "the": "with" and "from" in a line
# match a comparison reply as readily as a name does, and "that" and "this" are in every other
# opening.
NOT_A_THING = frozenset((
    "the", "and", "for", "you", "not", "but", "all", "any", "one", "two", "are", "was", "has",
    "had", "how", "why", "who", "did", "may", "can", "its", "our", "per", "via", "yet", "own",
    "off", "out", "too", "get", "put", "use", "let", "now", "far", "lot", "bit", "way", "she",
    "him", "her", "his", "new", "old", "few", "yes", "them", "they", "their", "there", "then",
    "that", "this", "with", "from", "your", "have", "what", "when", "will", "would", "could",
    "should", "about", "into", "over", "just", "only", "even", "still", "much", "many", "some",
    "very", "also", "been", "being", "does", "done", "more", "most", "less", "like", "need",
    "want", "make", "made", "going", "were", "than", "such", "each", "both", "else", "said",
))


def _about_the_thing_the_line_named(opening, said):
    """True when the reply is about something the line named: provenance, not subject.

    A wide reading of a yes or a no - why, what the thing is, the figure the yes rested on, what
    to do about it - is worth nothing when the reply is about something else, and read without
    the line it says yes to nearly any fact-shaped reply: in a paired test "Two to three hours."
    was credited as the verdict for every yes/no line there is, and "Sort by colour, not by kind
    of garment" answered "should i run a hot wash with vinegar".

    The thing has to be named where the reply states its subject - the first five words - unless
    the reply points back with a pronoun ("It varies with the drink, ... 60 to 80mg") or tells the
    person what to do, where the object comes later ("Slice it first, then bag it: bread keeps
    three months" answers "can i freeze bread"). The figure the line asked about counts as well:
    "is 60mg enough" / "60 to 80mg is a mug of instant coffee".
    """
    words = _words(opening)
    wide = bool(POINTS_BACK.match(opening)) or _an_instruction(opening)
    head = set(words) if wide else set(words[:5])
    for word in set(_words(said)):
        if len(word) < 3 or word in _EMPTY or word in NOT_A_THING:
            continue
        if word in head:
            return True
        # A stem must be a word that names something: "add" cut to two is "ad" and then "a", and
        # "young" cut to three is "you", so the reply's own article or pronoun made it the thing
        # the line named. The plural and the participle keep their stem ("eggs" to "egg", "boiling"
        # to "boil"), which is what the stem is for.
        for stem in (word[:-1], word[:-2]):
            if len(stem) < 3 or stem in _EMPTY or stem in NOT_A_THING:
                continue
            if stem in head:
                return True
    return bool(set(re.findall(r"\d+", opening)) & set(re.findall(r"\d+", said)))


# A method opens on any of these, and a method is not a verdict. The list is kept out of
# `INSTRUCTS` because `_the_job_answers` reads that one as "this is the job the line asked
# about", where a wider list turned "Lower eggs into already boiling water" into the answer to
# "can my son eat grapes".
METHOD_VERBS = re.compile(
    r"^(?:lower|brown|mash|crush|sprinkle|grease|steam|blend|scatter|lay|shake|score|chill|thaw|"
    r"reheat|serve|strain|sieve|portion|layer|arrange|thread|screw|hammer|nail|clamp|level|"
    r"preheat|dust|wring|drape|tuck|loop|knot|peg|hoover|vacuum|mop|air|cure|rest)\b", re.I)


def _an_instruction(opening):
    """True when the reply tells the person to do something, which is not a verdict on its own."""
    if (INSTRUCTS.match(opening) or JOB.match(opening) or METHOD_VERBS.match(opening)
            or MEANS_OF.search(opening)):
        return True
    words = _words(opening)
    if len(words) < 2 or NOT_A_VERB_HEAD.match(opening):
        return False
    second = words[1]
    return not (second.endswith("s") and not second.endswith("ss"))


CHOICE = re.compile(r"\bor\b", re.I)


def gives(reply, want, line=None):
    """True when `reply` gives an answer of kind `want`, False when the check can name what is
    wrong with it, None when words cannot tell.

    Only the opening sentence is read, because STYLE.md asks for the answer in the first sentence
    and a figure buried in the third paragraph of a paragraph about something else is not the
    reply the person got. A method is the one shape read a sentence further, because its opening
    is often the reason: "Sticking is nearly always a wet dough meeting a dry surface. Chill the
    pastry 20 to 30 minutes before rolling." A want this module does not know, or one of the soft
    shapes, is None.

    False is a claim about the reply, so the check only makes it when it can say what the reply
    is instead: a shrug, or an unmistakable other shape - a duration, a figure, a method, a
    named kind of place, a role, what the thing is, a verdict or a named side. A reply in words
    the cue list has nothing for is None, not a miss: "Vinegar does not go off" is the answer to
    "does vinegar go off", and "Granita is fruit juice or coffee" is the answer to "what is
    granita", and neither carries a cue this module knows.
    """
    if want not in WANTS or want in SOFT:
        return None
    # The line comes as the person's own words, and as the reading of them: the tests here hold a
    # reply against what `understand` made of the line, which is how the arms that need the line
    # were written and checked. Reading a dict as text made every one of those arms dead - the
    # pair-up arm never fired on "is a bath better than a shower" - so the two are the same thing
    # here, once, for every arm.
    if isinstance(line, dict):
        line = line.get("text") or line.get("clean") or line.get("plain") or ""
    opening = first_sentence(reply)
    if not opening:
        return None
    # "That's beyond what I know" is not a figure, a place or a method, whatever words follow it.
    if is_a_punt(opening):
        return False
    check = _CHECKS.get(want)
    # A price per hour is not a length: "A dehumidifier is about 7p an hour, and it dries a room by
    # running longer rather than hotter" answered how much, and reading "an hour" out of it credited
    # it as a how-long. The rate phrase is taken off and the time check runs again on what is left,
    # so "£12 an hour, and it takes an hour to warm up" is still a time.
    if want == TIME and _a_money_rate(opening):
        stripped = _without_a_money_rate(opening)
        if stripped != opening:
            return bool(_a_time(stripped))
    if want == STEPS:
        # A method is the one shape the whole reply gives: see `_steps_in`.
        if _steps_in(reply):
            return True
    elif want == REASON:
        # The one check that reads the line as well as the reply: see `_a_reason`.
        if _a_reason(opening, line):
            return True
    elif want == YESNO:
        # The yes/no check reads the line too, for its two quality arms: see `_a_yesno`.
        if _a_yesno(opening, line):
            return True
    elif check and check(opening):
        return True
    # An offer to do it is the yes: "Paste the words you want to send and I'll soften them" answers
    # "can you make it shorter".
    if want == YESNO and line and ASKS_THE_BOT.search(_line_text(line)):
        # An offer answers "can you" only when it is about the thing the line asked for:
        # "can you make it shorter" / "I'll soften them" is an answer, "could you add my shift on
        # friday to my calendar" / "I would start here: get a quote" is not.
        if I_OFFER.search(opening) and _about_the_thing_the_line_named(
                opening, _line_text(line)):
            return True
    # The wide read of a yes or a no - the reply says why, what the thing is, the figure the yes
    # rested on, or what to do about it - is only worth anything when it is about the thing the
    # line named. Read without the line it says yes to nearly any fact-shaped reply: "Two to three
    # hours." was credited as the verdict for every yes/no line in a paired test, and "Sort by
    # colour, not by kind of garment" for "should i run a hot wash with vinegar". Nor when the line
    # is the person's own doing and the outcome is what they asked about: "if i set off at 5 will i
    # miss my flight" is not answered by "Leave for the airport three hours before the flight".
    if (want == YESNO and line and not _an_outcome_of_their_own_doing(_line_text(line))
            and _about_the_thing_the_line_named(opening, _line_text(line))):
        if (_a_meaning(opening) or _a_reason(opening) or _a_time(opening)
                or _an_amount_with_a_unit(opening)):
            return True
    # The job the person asked whether to do is the yes, and only ever the yes: it is checked
    # before the clear shapes so a method that answers the line is not read as a method instead.
    # Anything this cannot read falls through to the clear shapes and then to None, so a reply
    # main called "words cannot tell" is not turned into a miss by knowing the line.
    if want == YESNO and _the_job_answers(opening, line):
        return True
    # A verdict said about the thing rather than as the words yes or no: "is brown bread better
    # than white" / "Wholemeal is the better everyday loaf", "is cycling bad for knees" / "Cycling
    # is one of the kinder things for knees". The words that carry the verdict are not the opening
    # ones, so this reads the whole opening - and only beside the line, because those words credit
    # a reply to a completely different line as readily as the right one: 11 real turns and 11
    # wrong pairings on 755 yes/no turns. The reply naming something the line named is what tells
    # them apart (6 real, 2 wrong), and what it leaves unread stays the "words cannot tell" it was.
    if (want == YESNO and line and VERDICT_ABOUT_IT.search(opening)
            and _names_what_the_line_named(opening, _line_text(line))):
        return True
    # A verdict can be the rule in the sentence after the thing it is about: "can i get a bus pass
    # if im disabled" / "A disabled person's bus pass is a council scheme ... You qualify if ...".
    # Only this reading is followed into the rest of the reply, and only for its own phrase list.
    if want == YESNO and VERDICT_RULE.search(reply):
        return True
    # "is wholemeal better than white" is a yes/no with a pair in it, and it is answered by
    # picking one: "Wholemeal is the better everyday loaf", "Showering wins on time and water",
    # "iPhone if you want the long updates". Only a line that puts two things up reaches this.
    if want == YESNO and line and _the_side_wins(opening, line):
        return True
    # The no said as the line's own verb denied: "does vinegar go off" / "Vinegar does not go off".
    if want == YESNO and _an_echoed_no(opening, line):
        return True
    # A yes/no about a quantity names no thing for a reply to be about, so the reading above cannot
    # reach it: "is that enough", "is that too far", "is 18 hours too much for a cat" are about a
    # figure from earlier in the chat. What answers them is the person's own figure set against the
    # standard: "15 minutes is short of the 20 minutes that answer named", "2 sessions a week is
    # under the three or four sessions a week that answer named - one more would put you there".
    if (want == YESNO and line
            and _the_figure_against_the_standard(opening, _line_text(line))):
        return True
    # A pick may name one of the two sides the line offered: "should i get a cat or a dog" /
    # "A dog needs two walks a day". Only the words either side of the "or" are sides, and the
    # reply has to open on one.
    if want == PICK and line and _names_a_side(opening, _line_text(line)):
        return True
    # A comparison is answered only when both things the line named are in it: "A sprain is a
    # stretched or torn ligament, a strain a torn muscle" compares them, and a reply that names one
    # of the two and never the other has answered half the question.
    both = _names_both_sides(reply, _line_text(line)) if want == COMPARE and line else None
    if both:
        return True
    # And when the missing side is a short name the reply may spell out ("hdd" as "a hard drive"),
    # nothing is claimed against the reply, whatever shape its opening happens to look like.
    if want == COMPARE and both is None:
        return None
    # A why is answered by naming the cause first and what to do about it after a colon: "One
    # channel going funny is the aerial or the box, and every channel is the set: push the aerial
    # lead in". The head of that sentence is the explanation, so the method behind the colon is
    # not a different shape - it is what the person does next. A head that only labels ("Quick:",
    # "Two things:") has no verb in it and is left to the readings below.
    if want == REASON and _head_explains(opening):
        return True
    # A definition names the thing first and then says what it is for: "what is a student loan" /
    # "A student loan pays the tuition fee and the maintenance money while you study". The reply
    # has said what the thing does, which is what the person asked, so it is not a miss for
    # opening on a verb `MEANS` does not list.
    if want == MEANING and line and _defines_the_thing(opening, _line_text(line)):
        return True
    # Where a thing comes from is answered by naming the source and then what is done with it:
    # "Bees make it: a worker drinks nectar out of flowers", "One bush, Camellia sinensis: the
    # leaves are picked, then wilted", "The juice of sugar cane or of sugar beet, boiled down
    # until the sugar crystallises". The source is the head of the sentence, so the thing the
    # person asked about is often not named at all - which is why the shape readings miss it.
    # Only an origin question is read this way, and only for the head of the reply.
    if want == MEANING and line and (ORIGIN_ASK.search(_line_text(line))
                                    or MADE_OF.search(_line_text(line))) and _an_origin(opening):
        return True
    # An ideas ask is answered by the one idea the bot would take: "what's a good podcast about
    # history" - "*The Rest Is History* is the best all-round history podcast". A pick is what an
    # options ask wants when the reply names one, which ample-bag measured over the 258 deck lines
    # of "what's a good X". A pointer that names nothing is still not an idea ("Try the film you
    # have been meaning to watch" is a job for the person), and a colon list is left to `_options`
    # above, which knows a list of one plan ("One evening: a film, a walk and a call, then tea")
    # from a list of ideas.
    # An ideas ask is answered by the one idea the bot would take: "what's a good podcast about
    # history" - "*The Rest Is History* is the best all-round history podcast". A pick is what an
    # options ask wants when the reply names one, which ample-bag measured over the 258 deck lines
    # of "what's a good X". A pointer that names nothing is still not an idea ("Try the film you
    # have been meaning to watch" is a job for the person), and a colon list is left to `_options`
    # above, which knows a list of one plan ("One evening: a film, a walk and a call, then tea")
    # from a list of ideas.
    # An ideas ask is answered by one idea named, or by a menu of them: a list joined by "or",
    # two or more titles ("*Codenames* (2 minutes to learn), *Ticket to Ride* (a bit longer),
    # *Carcassonne* for a fourth"), or a labelled list - the person asked for things to pick from
    # and that is what they were given. An imperative is the person's own job ("Try the film you
    # have been meaning to watch"), and a colon list is left to `_options` above, which knows a
    # list of one plan ("One evening: a film, a walk and a call, then tea") from a list of ideas.
    if want == OPTIONS and not _imperative(opening) and not VERDICT_OPEN.match(opening) \
            and not LIST_AFTER_COLON.search(opening) \
            and (_a_pick(opening) or CHOICE.search(opening) or _marked_things(opening) >= 2):
        return True
    # A rule that names the side for each case is the verdict, whichever way the person's own facts
    # fall: "Fix it if it is a part and a few pounds; bin it if the repair is half the price of new"
    # answers "is it worth fixing" and "is it worth fixing or shall i get a new one" alike.
    if want in (YESNO, PICK) and _the_rule_names_both_sides(reply):
        return True
    # A few things asked for as things - what to buy, what to take, what to bring - are given as a
    # list of them, in the reply's own words: "Litter tray and litter, two bowls, a scratching
    # post, a carrier, a soft bed and food for its age". `_options` above reads the list only when
    # the reply names it (a colon, an "or", a semicolon); a list laid out as commas and "and" was
    # read as no list at all. A figure often comes first ("About 0.5kg of raw joint for 2... Then
    # potatoes, carrots, parsnips or swede"), so the opening two sentences are read, and a
    # sentence that tells the person to do something is still not a list of things.
    if want == OPTIONS and not _an_instruction(opening) \
            and not VERDICT_OPEN.match(opening) and _three_names(_opening_two(reply)):
        return True
    # The reply is not this shape; is it clearly another one? Only then is it a miss we can name.
    for other, strong in _CLEAR:
        if other == want or (want == STEPS and other in _FIGURES):
            continue
        # A definition is evidence against a figure or a method, and says nothing about a choice:
        # "what can i use instead of chilli powder" is answered by "Paprika is the closest thing
        # to chilli powder", and "which is better, paprika or cayenne" by the same sentence.
        if other == MEANING and want in (PICK, OPTIONS):
            continue
        # An age, a price or a figure is how a yes/no is answered as often as "yes" is: "can i
        # vote at 16" / "Eighteen to vote in a general election", "is a refurbished iphone worth
        # it" / "A refurbished phone is a good way to save 30 to 50%". The figure is the verdict
        # in those, so a figure cannot name a yes/no as the wrong shape.
        if other == AMOUNT and want == YESNO:
            continue
        if strong(opening):
            return False
    return None


def missing(reply, wants_, line=None):
    """The wants in `wants_` (one label or a list) that `reply` clearly does not give."""
    if isinstance(wants_, str):
        wants_ = [wants_]
    gone = []
    for want in wants_ or ():
        if gives(reply, want, line) is False:
            gone.append(want)
    return gone


def second_sentence(reply):
    """The sentence after the opening one, tidied, or "" when the reply has only one."""
    text = " ".join(str(reply or "").split())
    parts = re.split(r"(?<=[.!?])\s+", text, maxsplit=2)
    return parts[1].strip() if len(parts) > 1 else ""


# A dot after one of these ends a word, not the sentence: "e.g. stands for exempli gratia, Latin
# for for example" opens on that whole clause, and reading the opening as "e.g" left the shape
# cues unread and the answer to "what does e.g. mean" scored None. A title belongs here for the
# same reason ("Dr. Patel says"), and it is never the last word of a sentence.
ABBREVIATION_END = re.compile(
    r"\b(?:e\.g|i\.e|approx|incl|etc|vs|cf|fig|dept|est|ref|tel|mr|mrs|ms|dr|prof)\.$", re.I)
SENTENCE_END = re.compile(r"(?<=[.!?])\s+")


def first_sentence(reply):
    """The reply's opening sentence, tidied, or "" for an empty reply.

    A full stop inside a figure ("1.5 bar") has no space after it, so it does not end a sentence;
    the split needs the space a real sentence ends with. A full stop after an abbreviation has one,
    so the split skips it and reads on to the sentence the reply really opens with.
    """
    text = " ".join(str(reply or "").split())
    if not text:
        return ""
    for end in SENTENCE_END.finditer(text):
        before = text[:end.start()]
        if ABBREVIATION_END.search(before):
            continue
        return before.strip()
    return text


def _opening_two(reply):
    """The reply's first two sentences, tidied, or "" for an empty reply.

    A short verdict or a figure often opens the reply and the list the person asked for follows in
    the next sentence: "About 0.5kg of raw joint for 2, which is 250g a person. Then potatoes,
    carrots, parsnips or swede". Two sentences and not the whole reply, so a list that has nothing
    to do with the answer cannot make the reply pass.
    """
    text = " ".join(str(reply or "").split())
    if not text:
        return ""
    seen = 0
    for end in SENTENCE_END.finditer(text):
        if ABBREVIATION_END.search(text[:end.start()]):
            continue
        seen += 1
        if seen == 2:
            return text[:end.start()].strip()
    return text


# The words of a sentence that carry on about something rather than name one of the things: "you
# put in 5% and your employer at least 3%" has a comma and an "and" in it and names no item of a
# list, and "a scratching post, a carrier, a soft bed" names three.
NAME_STOP = re.compile(
    r"\b(?:i|you|your|yours|we|our|us|me|my|it|its|they|them|their|he|she|his|her|is|are|was|"
    r"were|be|been|being|do|does|did|have|has|had|can|could|will|would|should|shall|may|might|"
    r"must|if|then|so|but|that|this|these|those|there|here|when|while|because|about|from|with)\b",
    re.I)
# A sequence word between the items of a list splits it into steps: "a film, a walk and a call,
# then tea" is one plan, not three things to bring.
STEPS_INSIDE_A_LIST = re.compile(
    r",\s*(?:then|next|after that|afterwards|finally|lastly)\b", re.I)


def _three_names(text):
    """True when three or more things are named in one run, not prose that has commas in it.

    A list of things is names and joining words and nothing else: "Litter tray and litter, two
    bowls, a scratching post, a carrier". A sentence that carries on about something has a verb or
    a pronoun in it - "you put in 5% and your employer at least 3%, and the tax relief comes on
    top" - and that is prose with commas, not a list. So each run between the verbs and the
    pronouns is read, and three or more short items inside one of those runs is the list. Long
    items are left out: a clause with more than four words in it is a sentence, not a thing.
    """
    plain = " ".join(str(text or "").split())
    if not plain:
        return False
    for clause in re.split(r"(?<=[.!?;:])\s+", plain):
        # A list of things has commas in it. Three words joined by "and" are a sentence about two
        # things: "Small and specific beats big and vague" is not a list of things to bring.
        if clause.count(",") < 2:
            continue
        # A plan is a sequence of jobs, not a list of things: "One evening: a film, a walk and a
        # call, then tea" is one evening and the parts of it. Only a sequence word that sits
        # between the items breaks the list - "then tea" after a comma - because "a soft bed and
        # food for its age, plus a vet visit booked for the first week" is a list with the word
        # "first" inside one of its items. A clause that opens on the sequence word is the rest of
        # a list ("Then potatoes, carrots, parsnips or swede"), so the word is dropped and read on.
        opened = re.sub(r"^[\W]*(?:then|next|after that|afterwards|finally|lastly)\b", "",
                        clause, flags=re.I)
        if STEPS_INSIDE_A_LIST.search(opened):
            continue
        for run in NAME_STOP.split(opened):
            items = [item.strip() for item in re.split(r"\s*,\s*|\s+(?:and|or|plus)\s+", run)]
            items = [re.sub(r"^(?:and|or|plus)\s+", "", item) for item in items if item]
            items = [item for item in items if item]
            # A note after the list does not spoil it: "Litter tray and litter, two bowls, a
            # scratching post, a carrier, a soft bed and kitten food, plus a vet visit booked for
            # the first week" is six things and then a note. A long item in front of the others is
            # the sentence carrying on about something, not a list, so only the last item may run
            # long - "One thing you will actually do at 8pm (a film, a walk, a call), tea, and the
            # phone in another room" is one plan, not four things.
            # An item explained in brackets is a sentence about the thing, not a thing: "One
            # thing you will actually do at 8pm (a film, a walk, a call), tea, and the phone in
            # another room" is one plan for the evening, and the commas inside the brackets are
            # the parts of it.
            if "(" in run:
                continue
            short = [item for item in items if len(item.split()) <= 4]
            trailing = len(items) - len(short) == 1 and len(items[-1].split()) > 4
            if len(short) >= 3 and (len(short) == len(items) or trailing):
                return True
    return False


# ------------------------------------------------------------------------------- the figures

_WORD_NUMBER = (r"(?:\d+(?:[.,]\d+)?|one|two|three|four|five|six|seven|eight|nine|ten|eleven|"
                r"twelve|thirteen|fourteen|fifteen|sixteen|seventeen|eighteen|nineteen|twenty|"
                r"thirty|forty|fifty|sixty|seventy|eighty|ninety|hundred|thousand|million|"
                r"a couple|couple|a few|half|a quarter|a third|a fifth|double|dozen)")
# A duration: a figure and a unit, or one of the phrases that is a time without a figure.
# A length is often qualified: "one to three working days" for a transfer, "two clear days" before
# you can ring them, "a working week". DURATION wanted the unit straight after the number, so three
# everyday answers to a how-long went unread.
_DURATION_QUALIFIER = (r"(?:(?:working|clear|business|banking|bank|calendar|school|full|whole|"
                       r"solid|straight|extra|more|further)\s+)?")
DURATION = re.compile(
    r"(?:" + _WORD_NUMBER + r"|\ba\b|\ban\b)[\s-]*(?:" + _WORD_NUMBER + r"[\s-]*)?"
    + _DURATION_QUALIFIER +
    r"(?:sec|second|min|minute|hr|hour|day|week|fortnight|month|year|night|morning|"
    r"afternoon|evening)s?\b"
    r"|\bovernight\b|\ball day\b|\ball night\b|\bfor a bit\b|\bwithin the hour\b|\bsoon\b|"
    r"\b(?:for|in) (?:days|weeks|months|years)\b|"
    r"\ba (?:full|whole) (?:hour|day|week|month|year)s?\b|"
    # A length said without a figure at all: "give it a couple of days", "several weeks", "a
    # handful of days". "a few days" is already a figure in `_WORD_NUMBER`; the words that need
    # their own place are the ones that take "of" before the unit, and the plural quantifiers.
    r"\b(?:a couple of|a pair of|a number of|a handful of|several|many|numerous)\s+"
    r"(?:sec|second|min|minute|hr|hour|day|week|fortnight|month|year|night|morning|"
    r"afternoon|evening)s?\b|"
    r"\bten minutes\b|\bnext day\b", re.I)
# A time of day or a date is a time too: "by Friday", "before 9am", "on the 3rd".
CLOCK_SURE = re.compile(
    r"\b(?:mon|tues|wednes|thurs|fri|satur|sun)day\b"
    # A month is a month when it is written as one, and the names are spelled out: `sep`, `dec`
    # and `nov` were matched as prefixes, so "Separate the yolks and whisk the whites" and "6
    # separate ones" were a September, "Decide the date between you first" a December and "Novel
    # ways are rarely better" a November - four replies read as dates. `may` and `march` are read
    # with their case, because they are ordinary words too: "You may need to ring them first" was
    # a date, and so a steps answer failed. A day after one of them ("3 may") is still a date.
    r"|\b(?:january|february|april|june|july|august|september|october|november|december"
    r"|jan|feb|mar|apr|jun|jul|aug|sept|sep|oct|nov|dec)\b\.?"
    r"|\b(?-i:May|March)\b\.?"
    r"|\b(?:may|march)\b\.?\s+\d{1,2}\b"
    r"|\b\d{1,2}\s*(?:am|pm)\b|\bo'clock\b|\bmidday\b|\bmidnight\b|\btonight\b|\btomorrow\b"
    # A time in words answers a when-question just as well: "Text the same evening or the next
    # morning". A part of the day on its own does not: "pour it at the base in the morning"
    # says how to do something, not when.
    r"|\b(?:same|next|this|that) (?:morning|afternoon|evening|night)\b"
    # A clock time said as figures with minutes on them after at/by/until: "At 8.15.", "by 9:30
    # at the latest". A bare hour after a preposition ("you start work at 6", "by 9") is not read
    # here, because it is a count or a surface as often as a clock - "at 5 percent", "at 10
    # litres", "at 3-1 to the away side", "put it on 2 shelves". It is still a time on the passing
    # side, in `NAMED_CLOCK` below: a reply that answers "what time is my train" with "At 6."
    # gives what was asked for, and a reply to some other question is not failed for saying it.
    r"|\b(?:at|by|until|till|before|after|from) \d{1,2}[.:]\d{2}(?![.:]?\d)"
    # A year is a date, and "when did ww1 start" is answered in one: "began in 1914", "the
    # legions left in 410", "from 1948 to 1994", "abolished in 1848". The preposition or the range
    # is what tells a year from a figure: "2000 calories a day" is not a date.
    r"|\b(?:in|since|until|till|from|by|during|after|before) "
    # "in the 1800s" is a decade as much as "in 1914" is a year.
    r"(?:\d{3,4}s?\b|the \d{3,4}s?\b)"
    # A three-or-four figure after a preposition is a quantity as often as a year: "Change the
    # filter at 10 litres, or in 2000 uses" and "Sand it in 180 grit" were both read as dates, and
    # so was a 2000-calorie day. A unit or a count right after it keeps it a measurement.
    r"(?!\s*(?:g|kg|ml|l|p|pence|%|bar|cm|mm|km|m|ft|lb|oz|st|deg|grit|uses?|pages?|words?|"
    r"steps?|calories|kcal|people|guests?|servings?|slices?|eggs?|metres?|meters?|miles?|"
    r"yards?|feet|foot|litres?|liters?|grams?|kilos?|acres?|square|long|wide|tall)\b)"
    r"|\b\d{3,4}\s*(?:ad|bc|b\.c\.)\b"
    r"|\b(?:1[0-9]{3}|20[0-9]{2})\s*(?:-|to|or|and)\s*(?:1[0-9]{3}|20[0-9]{2})\b"
    # "on the 28th", "the 3rd of March": a date said as an ordinal.
    r"|\bthe \d{1,2}(?:st|nd|rd|th)\b|\b\d{1,2}(?:st|nd|rd|th) of (?:jan|feb|mar|apr|may|jun|"
    r"jul|aug|sep|oct|nov|dec)",
    re.I)
# A season answers a when-question too, but so faintly that it is only a pass: "Late spring for
# me: long evenings, everything green" is a pick, and the one season word in it does not make the
# reply a time. Only a season with a preposition or an edge on it ("in early autumn") is strong.
SEASON = re.compile(r"\b(?:spring|summer|autumn|winter)\b", re.I)
CLOCK = re.compile(CLOCK_SURE.pattern + r"|" + SEASON.pattern, re.I)
# A year is as good an answer to "when was the battle of waterloo" as a day is: "from 1837 to
# 1901", "In 1605 a group of English Catholics". A figure that is a count or a price is not a
# date, so a year only counts where a date is being given - after a word that introduces one ("in",
# "from", "since", "by"), at the very start of the reply, or as a decade or a century. "Use 1000
# grit paper" and "A 2024 model is better" are neither, and nor is a figure a unit follows ("in
# 2000 calories", "about 1500 steps"): the unit wins over the year. A count sits in the same
# place and looks like no unit at all - "change the filter in 2000 uses", "in 2000 cycles" - so
# a plural word after the figure keeps it out too. A plural that really follows a year is rare
# in a reply ("in 1945 soldiers came home"); a count after a preposition is common.
NOT_A_YEAR = (
    r"(?!\s*(?:cal|kcal|calorie|step|mile|km|kilomet|metre|meter|gram|g\b|kg|ml|litre|liter|"
    r"watt|lumen|gb|mb|megabyte|pound|dollar|euro|per cent|%)\w*)"
    r"(?!\s+[a-z]{2,}s\b)")
DATE = re.compile(
    r"(?:\b(?:in|from|since|until|till|by|of|during|between|after|before|around|about|circa|"
    r"early|late|mid|and|to)\s+(?:the\s+)?|^)(?:1[0-9]{3}|20[0-2][0-9])\b" + NOT_A_YEAR +
    r"|\b(?:in|from|since|during|of|the|by|until|early|late|mid)\s+(?:\d{4}s|\d{1,2}(?:st|nd|"
    r"rd|th) century)\b", re.I)
# A time is often said as a bare hour or a date rather than as a duration: "You start work at 6",
# "Your driving test is on the 12th", "on Tuesday at 6.30", "by the 3rd of may". DURATION and
# CLOCK both want a unit of time or a named day on its own, so the hour a time word introduces is
# read here as well. Only the passing side uses this: a bare figure is not evidence that a reply
# to some other question is about a clock.
# The hour is said in words as often as in figures: "You go to bed at eleven", "at half past
# six". Only the twelve clock hours are read that way - "at half the price" is not a time.
HOUR_WORD = (r"(?:one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve)"
             r"(?:\s*(?:am|pm|a\.m|p\.m))?")
# Only a clock shape is a clock on its own: a colon or a dot between the figures, an am/pm, an
# ordinal date, or a day of a month. A bare figure or a bare hour word is a clock only after a
# time word that cannot introduce anything else, and only inside the 24 hours of a day - "on one
# side", "on 2 shelves", "about one in five" and "at 5 percent" name no time between them.
CLOCK_ANYWHERE = (
    r"(?:\d{1,2}[:.]\d{2}"
    r"|\d{1,2}\s*(?:am|pm|am\.|pm\.|a\.m|p\.m|o'clock)"
    r"|(?:the\s+)?\d{1,2}(?:st|nd|rd|th)\b"
    r"|(?:the\s+)?\d{1,2}\s+of\s+(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)"
    r"|(?:half|quarter|ten|twenty|five|twenty-five)\s+(?:past|to)\s+" + HOUR_WORD + r")"
)
_HOUR_24 = (r"(?:[01]?\d|2[0-4])(?![\d:])(?!\.\d)"
            # A scoreline or a ratio is not a clock: "It finished at 3-1 to the away side",
            # "at 2-1 the draw looks generous".
            r"(?!\s*[-\u2013\u2014]\s*\d)"
            # Nor is a share or a measurement: "at 5 percent", "at 10 litres", "change it in 2000
            # uses", "wash it at 40C".
            r"(?!\s*(?:%|percent|per cent|g|kg|ml|l|p|pence|bar|cm|mm|km|m|ft|lb|oz|st|deg|"
            r"metres?|meters?|miles?|yards?|feet|foot|litres?|liters?|grams?|kilos?|calories|"
            r"kcal|acres?|grit|uses?|square|long|wide|tall)\b)")
NAMED_CLOCK = re.compile(
    r"(?:\b(?:at|by|from|until|till|before|after|around|about|on)\s+" + CLOCK_ANYWHERE +
    r"|\b(?:at|by|from|until|till|before|after)\s+(?:" + HOUR_WORD + r"(?!\s+of\b)|" +
    _HOUR_24 + r")"
    r"|(?:half|quarter|ten|twenty|five|twenty-five)\s+(?:past|to)\s+" + HOUR_WORD + r")", re.I)
# "One of the hardest days" is not a quantity: a number word counts wherever it counts a
# thing, and `one of the` is the article of a whole class, not a count.
FIGURE = re.compile(r"\d|\b(?!one of\b)" + _WORD_NUMBER + r"\b", re.I)
# A price, in the words the reply has. "Nothing" is not a price by itself: "Nothing has to be
# decided today" is a condolence and "nothing on your cats in what I keep" is an empty memory, so
# the word counts only where it is what the person pays.
MONEY = re.compile(
    r"[£$€]|\b(?:pence|pounds?|quid|dollars?|euros?|cents?|free)\b"
    r"|^(?:nothing|nil|nowt)\b|\bnothing (?:at all|extra|much|to pay|else|on top)\b"
    r"|\bcosts? nothing\b", re.I)


def _a_figure(opening):
    return bool(FIGURE.search(opening))


# A how-long question is answered by the figure on its own more often than by any word: "and how
# long for a hard boiled one" gets "9 to 10 for hard boiled", and a bare range at the front of a
# reply to a how-long line is minutes or hours, because that is what the line asked for. It only
# counts as the opening, so a figure further in is not mistaken for the answer.
BARE_RANGE = re.compile(
    r"^[^\w]{0,3}(?:about |around |roughly )?(?:\d{1,3}|" + _WORD_NUMBER + r")"
    r"\s*(?:-|to|or|\u2013)\s*(?:\d{1,3}|" + _WORD_NUMBER + r")\b", re.I)

# A stage rather than a length: "waking at night is normal for the first months", "the first few
# weeks are recovery". A when or a how-long question about a baby, a puppy or a new job is
# answered in stages like these, and none of them carries a figure.
STAGE = re.compile(
    r"\b(?:for|in|over|through|during) the first (?:few |couple of |several )?"
    r"(?:days|weeks|months|year|bit)\b|\bthe first (?:few |couple of )?(?:days|weeks|months)\b"
    r"|\b(?:first|1st) birthday\b|\buntil (?:they|he|she) (?:are|is) \w+\b", re.I)
# "Never" is the time a how-long question asked for: "Salt does not go off at all", "it lasts
# indefinitely". Read as the answer rather than as nothing said.
NEVER = re.compile(
    r"\b(?:indefinitely|(?:does not|doesn't|do not|don't|will not|won't|never) "
    r"(?:go(?:es)? off|expire|spoil|perish)|(?:last|lasts|keep|keeps|stay|stays|good) "
    r"(?:good )?(?:for ever|forever|indefinitely))\b", re.I)

# A reply that opens on how often has answered a different question: "Once a year, and a gas
# boiler service is usually GBP60 to GBP120". The whole phrase is read, because "once a year"
# holds "a year" and the duration pattern would take that for a length.
RATE_PHRASE = re.compile(
    r"^(?:once|twice|(?:three|four|five|six|\d+)\s+times|"
    r"every (?:\w+ )?(?:day|week|month|year|morning|evening|night)|"
    r"daily|weekly|monthly|yearly|nightly)"
    r"(?:\s+(?:a|an|per|each|every)\s+(?:day|week|month|year|morning|evening|night))?", re.I)


# A time is not always a figure. "No honey at all before the first birthday", "Christmas Day is the
# last posting date", "in the morning, before the heat is on" are all times, and only the words
# that name an occasion with a preposition in front, or a day from the short closed list, count:
# "Beans on toast is a good cheap dinner" is not a time for the word dinner in it.
NAMED_TIME = re.compile(
    r"\b(?:before|after|until|till|by|at|on|from|in|over|during)\s+(?:the\s+)?"
    r"(?:first|second|third|next|last|that|their|his|her)?\s*"
    r"(?:birthday|christmas|easter|new year|weekend|weekday|morning|afternoon|evening|night|"
    r"breakfast|lunch|teatime|tea|dinner|supper|bedtime|school|school night|work|the day|"
    r"arrival|takeoff|checkout|check-in)\b", re.I)
DAY_NAME = re.compile(
    r"\b(?:christmas|easter|new year'?s?|bank holiday|birthday|half term|term time|"
    r"the weekend)\b", re.I)

# A count per day is a rate, not a length: "2000 calories a day is about right" answers *how much*
# and is not the answer to "how long will it take to lose a stone". The count and its rate are
# taken off before the duration is read, so "Run 1500 metres in 20 minutes every day" keeps the 20
# minutes. Only a count of what is used or done reads this way; a count of weight or volume in
# front of "a week" is how fast something changes, which is what a how-long line asked for, so kg,
# grams, litres and pounds stay out of the list.
RATE_OF_A_COUNT = re.compile(
    r"\b\d[\d,.]*\s*(?:cal|kcal|calorie|step|rep|unit|mile|km|kilomet|metre|meter)s?\b"
    r"(?:\s+\w+){0,2}\s+"
    r"(?:a|an|per|each|every)\s+(?:day|week|month|year|morning|evening|night)\b", re.I)


# "No fixed time" is an answer to a how-long, not a refusal to give one: "how long do i reheat it
# for" / "No fixed time: reheat it until it is piping hot right through ... A portion takes 2 to 4
# minutes". An apology would not have the "no fixed time" in front of it.
NO_FIXED_TIME = re.compile(
    r"^(?:no|there'?s no|there is no) (?:fixed|set|exact|hard and fast) (?:time|length|deadline)\b",
    re.I)


def _a_time(opening):
    # A time said as a bare hour or a date is a time: "At 8.15", "Your driving test is on the
    # 12th", "by the 3rd of may". NAMED_CLOCK is read here, on the passing side only: a figure
    # with a time word in front is not evidence that a reply to some other question is a clock.
    if NAMED_CLOCK.search(opening):
        return True
    # A frequency is not a length. "Once a year, and a gas boiler service is usually GBP60" holds
    # "a year", which the duration pattern reads as a length; the rate phrase in front says the
    # reply answered *how often*. So the rate phrase is taken off, and what is left has to carry
    # the duration: "every day for ten minutes" still does, "twice a week" does not.
    said = RATE_PHRASE.sub("", opening, count=1) if RATE_PHRASE.match(opening) else opening
    # "2000 calories a day" is a rate, not a length: the figure carries a count with a rate word
    # after it, so the length is taken off before the duration is read.
    said = RATE_OF_A_COUNT.sub(" ", said) if RATE_OF_A_COUNT.search(said) else said
    # A stage ("in the first few days", "until the first birthday") and a never ("does not go off
    # at all", "keeps indefinitely") answer a how-long as plainly as a duration does.
    if NO_FIXED_TIME.match(said):
        return True
    if (DURATION.search(said) or CLOCK.search(said) or BARE_RANGE.match(said)
            or STAGE.search(said) or NEVER.search(said) or NO_FIXED_TIME.match(said)):
        return True
    # The named time is read from the opening clause only, and never from a reply that opens on
    # the job: "leave it in the oven until the morning" is a method that names a time on the way.
    if INSTRUCTS.match(opening):
        return False
    first_clause = re.split(r"[,;:]", said, maxsplit=1)[0]
    return bool(NAMED_TIME.search(first_clause) or DAY_NAME.search(first_clause)
                or DATE.search(first_clause))


def _a_clear_time(opening):
    """The time readings strong enough to fail a reply to a different question.

    A figure with a unit, an hour on the clock, a weekday, a date, the part of a day named as
    "next morning" are all what a reply is *about*. A bare season is not, and neither is a word
    list; see `_CLEAR`.
    """
    return bool(DURATION.search(opening) or CLOCK_SURE.search(opening)
                or BARE_RANGE.match(opening))



# How often is an amount without a figure: "every day if you can", "twice a week", "daily".
RATE = re.compile(
    r"\b(?:every (?:day|week|month|year|morning|evening|night|"
    r"other (?:day|morning|evening|night))|every few (?:days|weeks)|"
    r"most (?:days|mornings|evenings|nights|weekends)|once|twice|"
    r"three times|daily|weekly|monthly|yearly|nightly|\d+ times)\b", re.I)


def _an_amount(opening):
    # An amount is a figure with something to count, or a price. A bare count of things ("three
    # of them") is still a quantity, so the figure alone is enough here; the check says nothing
    # about whether it is the *right* figure, which is the miss a person has to look at.
    return bool(FIGURE.search(opening) or MONEY.search(opening) or RATE.search(opening))

# A figure that counts a thing you would measure - "two mugs", "one hour", "three pounds" - says
# the reply is about an amount. A spelled number that is only the word in front of an ordinary
# noun does not: "One channel going funny is the aerial or the box" is the cause of a blurry
# screen, and "Barcelona for a city and a beach in one trip" is a place. Both were read as
# amounts and the reply was failed for it. Only the evidence keeps this narrow reading; the
# amount check itself keeps the wide one, because "two eggs" answers "how many eggs".
MEASURED = re.compile(
    r"(?:\d|\b" + _WORD_NUMBER + r")\s*-?\s*(?:minutes?|mins?|hours?|hrs?|days?|weeks?|"
    r"months?|years?|seconds?|secs?|mugs?|cups?|tablespoons?|tbsps?|teaspoons?|tsps?|grams?|"
    r"kilograms?|kg|litres?|liters?|ml|pints?|quarts?|per cent|percent|degrees?|miles?|km|"
    r"metres?|meters?|feet|foot|inches?|times?|pence|pounds?|quid|each|people|servings?)\b",
    re.I)


def _an_amount_to_read(opening):
    """The amount only as evidence: a digit, a price or a rate, or a number counting a measure."""
    if re.search(r"\d", opening) or MONEY.search(opening) or RATE.search(opening):
        return True
    return bool(MEASURED.search(opening))


# A figure says what a reply is about only when the reply opens on it. The clear reading above
# is evidence, and evidence has to be the answer rather than a passing number: "Lean forward,
# pinch the soft part of the nose and hold for ten minutes" answers "how do i stop a nosebleed"
# with the method and mentions a duration on the way, and "Match the limit to the age: under
# two, video calls and the odd photo only" answers a screen-time question with a rule. Both were
# read as a time and an amount, and so as misses, on a reply that gave what was asked.
#
# So the fallback reads a figure only from the head of the opening, where a duration or a count
# is the whole of the first words. Five words is the width that keeps the figure that *is* the
# answer ("Two years' service is the line", "£60 to £120 once a year") and drops the ones that
# arrive after the reply has already made its point: at three words 32 turns of a 547-turn sweep
# stopped being named misses, at five 27, at eight 26, all of them misses the check could not
# really name and not one a reply that answered the line.
_FIGURE_HEAD = 5


def _figure_at_the_head(opening, pattern):
    """Whether `pattern` matches within the first `_FIGURE_HEAD` words of `opening`."""
    match = pattern.search(opening)
    return match is not None and len(opening[:match.start()].split()) < _FIGURE_HEAD


def _a_clear_time_at_the_head(opening):
    """`_a_clear_time` as evidence: the time has to be where the reply starts."""
    return (_figure_at_the_head(opening, DURATION)
            or _figure_at_the_head(opening, CLOCK_SURE)
            or bool(BARE_RANGE.match(opening)))


# A number written out is a figure when it counts a measure - "two mugs", "one hour", "three
# pounds" - and the word in front of an ordinary noun otherwise: "One channel going funny is the
# aerial or the box" is the cause of a blurry screen and was read as an amount, so a why-answer
# was failed for it. Only the evidence reads it this way; the amount check itself keeps the wide
# reading, because "two eggs" answers "how many eggs" whether or not "eggs" is a measure.
_MEASURE_AFTER = re.compile(
    r"\s*-?\s*(?:minutes?|mins?|hours?|hrs?|days?|weeks?|months?|years?|seconds?|secs?|mugs?|"
    r"cups?|tablespoons?|tbsps?|teaspoons?|tsps?|grams?|kilograms?|kg|litres?|liters?|ml|pints?|"
    r"quarts?|per cent|percent|centigrade|degrees?|miles?|km|metres?|meters?|feet|foot|inches?|"
    r"times?|pence|pounds?|quid|each|people|servings?)\b", re.I)


def _an_amount_at_the_head(opening):
    """`_an_amount` as evidence: the figure has to be where the reply starts, and a number
    written out has to be counting a measure rather than sitting in front of a noun."""
    if _figure_at_the_head(opening, MONEY) or _figure_at_the_head(opening, RATE):
        return True
    match = FIGURE.search(opening)
    if match is None or len(opening[:match.start()].split()) >= _FIGURE_HEAD:
        return False
    if match.group(0)[0].isdigit():
        return True
    return bool(_MEASURE_AFTER.match(opening, match.end()))


# ------------------------------------------------------------------------------- the things

# A place is a kind of place ("the post office", "any chemist", "the app") or its name ("in
# Bristol"). The named kind is what a where-answer almost always gives, and a capital after a
# preposition is a name far more often than it is anything else in the opening sentence. The
# plural is the same place ("across two or three shops", "the big supermarkets"), so the closing
# word boundary allows one, and the same goes for the roles below.
PLACE_WORD = re.compile(
    r"\b(?:shop|store|supermarket|chemist|pharmac|post office|bank|building society|council|"
    r"\bgp\b|doctor'?s|surgery|dentist|library|garage|station|market|website|web site|site|app|"
    r"online|branch|office|centre|center|clinic|hospital|recycling|tip\b|dump|high street|"
    r"department|service desk|desk|reception|kiosk|counter|aisle|dealer|showroom|garden centre|"
    r"petrol station|airport|bus stop|platform|address|tesco|asda|sainsbury|aldi|lidl|morrisons|"
    r"co-op|boots|argos|screwfix|ikea|amazon|ebay|gov\.uk|passport office|dvla|jobcentre|"
    r"citizens advice|charity shop|car boot|facebook marketplace|freecycle|wherever|"
    r"downstairs|upstairs|outside|indoors|in the garden|in the kitchen|in the loft|in the shed)"
    r"(?:s|es)?\b",
    re.I)
# A name is not always capital-then-lowercase: "You're from the UK", "made in the USA", "the EU
# sets it" name a place too, and an all-capitals short word after a preposition is a name far more
# often than anything else. The all-capitals arm takes "the" or no determiner at all, because "of a
# CEO" in a podcast title is a person and not a place, and so is "in a US study".
# A "where" that introduces a relative clause names no place to go: "should i stay where i am",
# "should i leave it where it is", "should i move where my mum is". The line asks whether, and
# the same word is the place understanding reads, so a verdict was scored a miss for naming no
# place. A line that asks to be told the place keeps it: "can you tell me where it is", "do you
# know where the stop cock is".
WHERE_RELATIVE = re.compile(
    r"\bwhere\s+(?:i|we|you|he|she|they|it|my|your|our|his|her|their)\b[^?.]{0,20}?"
    r"\b(?:am|is|are|was|were|live|lives|stay|stays|sit|sits|work|works|go|goes)\b", re.I)
ASKS_TO_BE_TOLD_WHERE = re.compile(
    r"\b(?:tell (?:me|us)|know|knows|say|says|shows?|explain|remind|remember|any idea|wonder|"
    r"find|check)\b[^?]{0,25}\bwhere\b", re.I)
PLACE_NAME = re.compile(r"\b(?:in|at|to|from|near|of|round|around|towards)\s+"
                        r"(?:(?:the\s+)?[A-Z]{2,4}(?![A-Za-z])|(?:the\s+|a\s+)?[A-Z][a-z]{2,})")
# A list of places offered as the answer itself, with no preposition before any of them: "Pick by
# what you want from a city: Lisbon for food and a short flight, Seville for heat and tapas, Prague
# or Budapest for the Christmas markets". The answer to a where-question is a list of two or more
# names, so two of them after a colon, a semicolon, a comma, an "or" or an "and" is what is counted.
# One capital is not a list: ": Brown the mince", ", Stop it, undo the tangle" and ": Aim for 10%"
# are a recipe, a step and a budget, and the capital that opens a clause is not a place.
PLACE_NAME_ANY = re.compile(r"(?:(?<=[:;,]\s)|(?<=\bor\s)|(?<=\band\s))[A-Z][a-z]{2,}")


# Who to ask: a role is a person in the answer as much as a name is. A who-question about a
# person in the world ("who invented the telephone") wants a name, and the name is a capital in
# the middle of the sentence; the first word of the reply is not counted, because a sentence
# opens with a capital whatever it says.
PERSON_WORD = re.compile(
    r"\b(?:vet|veterinar|doctor|gp|nurse|pharmacist|chemist|dentist|plumber|electrician|"
    r"gas safe|engineer|mechanic|solicitor|lawyer|adviser|advisor|accountant|broker|"
    r"landlord|letting agent|employer|hr|union|citizens advice|council|police|"
    r"someone|somebody|a professional|specialist|consultant|technician|builder|roofer|"
    r"physio|optician|midwife|health visitor|social services|ombudsman|registrar|"
    r"witness|referee|teacher|tutor|your bank|the bank|neighbour|neighbor)(?:s|es)?\b", re.I)
PERSON_NAME = re.compile(r"(?<=[a-z,;(]\s)[A-Z][a-z]{2,}")
# A who is answered with the relation more often than with a name: "whos coming with me" / "A
# friend - that is who you said you were going with", "who is older" / "You're older - 34 to your
# wife's 32". The people in the reply are the answer, whether named as a role or as one of theirs.
PERSON_RELATION = re.compile(
    r"\b(?:mum|mom|mam|dad|mother|father|son|daughter|sister|brother|wife|husband|partner|"
    r"friend|mate|boyfriend|girlfriend|fianc\w*|neighbou?r|boss|colleague|"
    # The person a who is answered with at work is the manager far more often than the boss, and
    # "who do i ask about it" answered "Your manager, in writing" was read as giving no person at
    # all: the role was in none of the words. The words are the roles a manager is named by.
    r"manager|supervisor|team leader|line manager|head of (?:year|department|team)|"
    r"child|kid|baby|"
    r"gran|grandma|grandad|granny|nan|aunt|uncle|cousin|step(?:son|daughter|mum|dad)|"
    r"in-laws?|twins?)\b", re.I)

MEANS = re.compile(
    r"\b(?:means|meaning|stands for|is short for|refers to|is when|is what|"
    r"is (?:a|an|the)\s+\w+|are (?:a|an|the)\s+\w+|is called|called|is basically|"
    r"is just|is simply|is the (?:name|word|yearly|total|amount|cost|price|process))\b"
    # "what does gracias mean" / "That is Spanish for 'thank you'": a word given in another
    # language is a definition too, and it is said about the English word rather than as
    # "<word> is <word>", so the language and the quoted word are what mark it.
    r"|\b(?:is|are|means)\s+(?:\w+\s+)?for\s+[\"'\u201c\u2018]", re.I)


# "where did i decide to go" -> "You settled on spain." A reply that names what the person chose
# is the where, and the name is in their own spelling, so it carries no capital to go by.
SETTLED_ON = re.compile(
    r"\byou (?:settled on|decided on|went for|opted for|chose|picked|plumped for|said|mentioned|"
    r"told me)\b", re.I)


def _a_place(opening):
    return bool(PLACE_WORD.search(opening) or PLACE_NAME.search(opening)
                or len(PLACE_NAME_ANY.findall(opening)) >= 2 or SETTLED_ON.search(opening))


def _a_person(opening):
    if PERSON_RELATION.search(opening):
        return True
    return bool(PERSON_WORD.search(opening) or PERSON_NAME.search(opening))


# The plainest definition in English is "<thing> is <description>", with no article and no
# "means": "Granita is fruit juice or coffee", "Carbohydrates are one of the main food groups",
# "Your mum is vegetarian". A pronoun before the verb is not a definition - "It is fine" is a
# verdict about something already named.
DEFINES = re.compile(
    r"^(?!\s*(?:it|that|this|they|these|those|there|he|she|i|we|you|what|which|here|so|and|but)\b)"
    # A definition is usually the thing and then `is`, but not always: "A cone has one circular base
    # and a curved side that comes to a point", "A solid has a fixed shape and a fixed volume", "A
    # cylinder has two flat circular ends". `has` is how a thing is described by what it carries, and
    # the check read those two answers to "what is a cone" and "what is a solid" as misses. Only
    # when `gives` already knows the line asked for a meaning, so a has-sentence elsewhere is
    # untouched, and the opening cannot be `it has` - the lookahead above drops that. A `has to`
    # or `have to` is an obligation, not a thing's parts: "An odometer has to be working for the
    # MOT" answers a rule about one, and it is not what the thing is.
    r"[\w'\u2019-]+(?:\s+[\w'\u2019-]+){0,4}\s+(?:is|are|has|have)\b(?!\s+to\b)", re.I)


# A thing defined by what it does: "what is a food bank" / "Food banks give a few days of free
# food, and most ask for a referral". The subject and its verb are the opening, so this is read
# from the first few words only - "both give you a crisp base" inside a method is not a meaning.
MEANS_BY_DOING = re.compile(
    r"^(?:\w+ ){0,3}(?:give|gives|provide|provides|let|lets|allow|allows|help|helps|names)\s+"
    r"(?:you|a|an|some|free|people|anyone)\b", re.I)


# A mechanism is a meaning told as the thing's parts and what they do: "A pin-tumbler lock has
# pairs of pins resting across the plug", "A hiccup is a sudden spasm of the diaphragm".
MECHANISM = re.compile(
    r"\bis how\b|\bworks? by\b|\bworks? like\b|\bworks? because\b|"
    r"^(?:(?:the|a|an)\s+[\w'\u2019-]+(?:\s+[\w'\u2019-]+){0,3}\s+|it\s+)"
    # A `has to` is an obligation, not a thing's parts: "An odometer has to be working for the MOT"
    # answers a rule about one, and it is not what the thing is.
    r"(?:has|have)(?!\s+to\b)|(?:uses|consists of|contains|comes from|breaks|pulls|pushes|turns|"
    r"carries|draws|"
    r"sucks|lifts|heats|cools|reacts|sends|absorbs|filters|"
    # what a mechanism is asked about is often told as the thing doing its job: "A fridge moves
    # heat out of the inside and dumps it at the back", "A spring stores energy by bending steel",
    # "It fills the drum, tumbles the clothes through hot water and pumps it away".
    r"moves|moved|stores|dumps|spins|tumbles|bends|drives|releases|fills|pumps|blows|burns|"
    r"melts|freezes|bounces|blocks|traps|spreads|grows|charges|recharges|squeezes|stretches|"
    r"swings|shakes|rotates|grinds|crushes|mixes|separates|holds|held|takes in|gives out)\b",
    re.I)


# A thing's origin told as the source and then what is done with it. See the ORIGIN_ASK arm in
# `gives`. The source is the subject, so `make it` is how the sentence says which thing it is
# about; a colon at the head names the source and opens the process; and a participle after the
# source ("boiled down until", "picked, then wilted") is the same telling.
SOURCE_MAKES = re.compile(
    r"^(?:\w[\w'\u2019-]*[ ,]+){1,6}(?:make|makes|made|lay|lays|laid|grow|grows|produce|produces|"
    r"give|gives)\s+(?:it|them)\b", re.I)
SOURCE_COLON = re.compile(r"^(?!\s*(?:it|that|this|there|they|you|we|i)\b)"
                          r"[\w'\u2019,()/-]+(?:\s+[\w'\u2019,()/-]+){1,7}:\s*\w", re.I)
SOURCE_MADE = re.compile(
    r"^[\w'\u2019,()-]+(?:\s+[\w'\u2019,()-]+){0,12},\s*(?:boiled|crushed|heated|picked|shorn|"
    r"wilted|dried|melted|grown|laid|dug|pressed|cooked|washed|cut|made|then|and then)\b", re.I)


# The source named and then doing its thing is the same telling without the colon or the
# participle: "Rain soaks into the ground and runs into rivers, and your tap water is drawn from
# a river". The verbs are the ones a material's own process is told with.
SOURCE_DOES = re.compile(
    r"^[\w'\u2019-]+(?:\s+[\w'\u2019-]+){0,3}\s+(?:soaks|runs|flows|comes|grows|forms|makes|"
    r"gives|produces|holds|carries|falls|melts|boils|ferments|rots|breaks|builds|lays)\b", re.I)


# "Flour, water, salt and yeast. The yeast gives off gas..." - the list of what the thing is made
# of, with no verb at all, is the answer to what it comes from.
SOURCE_LIST = re.compile(
    r"^(?!\s*(?:it|that|this|there|they|you|we|i)\b)[\w'\u2019-]+(?:,\s*[\w'\u2019-]+){2,}"
    r"(?:\s+and\s+[\w'\u2019-]+)?\b", re.I)


def _an_origin(opening):
    return bool(SOURCE_MAKES.match(opening) or SOURCE_COLON.match(opening)
                or SOURCE_MADE.match(opening) or SOURCE_DOES.match(opening)
                or SOURCE_LIST.match(opening))


def _a_meaning(opening):
    if MECHANISM.search(opening):
        return True
    return bool(MEANS.search(opening) or DEFINES.match(opening)
                or MEANS_BY_DOING.match(opening) or MECHANISM.search(opening))


# ------------------------------------------------------------------------------- the shapes

# A verdict opens on the yes or the no itself: "Yes...", "No need...", "Straight in is fine",
# "It's fine", "You can", "Not worth it". The opening word is read, then a short list of frames
# that answer the yes/no without the words yes or no; anywhere past the opening a "not" or a
# "fine" is usually a detail, so the inside check is the opening's first clause only.
VERDICT_OPEN = re.compile(
    r"^(?:yes|yeah|yep|yup|no|nope|nah|not|never|don'?t|do not|doesn'?t|avoid|skip|sure|"
    r"definitely|absolutely|probably|usually|generally|normally|often|mostly|sometimes|"
    r"better|best|fine|safe|okay|ok|"
    r"it'?s|it is|that'?s|that is|they'?re|there'?s no|you'?re|you (?:can|could|should|don'?t|"
    r"do not|does not|did not|won'?t|can'?t|shouldn'?t|need|want|have to|must)|"
    # A no is often the other action named instead: "i left my chicken out overnight can i still
    # cook it" / "Bin it, I'm afraid."
    r"bin|throw|chuck|toss|dump|discard|refrain|"
    r"none|nothing|straight|warm|cold|plain|just)\b", re.I)
# A verdict said in the first person: "I would. Switch it off and leave it off", "I wouldn't
# bother with a new one", "I'd wait until the spring". The bot answers a should-I question this
# way a lot, and the yes or the no is in the first two words, so the rest of the sentence can be
# the reason or the method. Not "I would only repeat myself", which says nothing about the doing.
FIRST_PERSON_VERDICT = re.compile(
    r"^i (?:would|wouldn'?t|do|don'?t|will|won'?t)\b(?!\s+(?:only|just|rather|say that))"
    r"|^i'?d (?:say|skip|wait|hold off|bother|not bother|avoid|keep|leave|go for|get|change|"
    r"stick with|try)\b", re.I)


# The verdict said by confirming the figure or the plan the person restated: "Still right: lid
# on, bring it to the boil", "That's right", "Exactly". The confirmation is the yes, and a reply
# that opens on it has answered the "is 12 minutes right" it was asked. A bare "Right," is left
# out: it opens a new subject as often as it agrees, and a check that reads it as a yes hides
# the turns that have no answer.
ECHO_VERDICT = re.compile(
    r"^(?:(?:still|that'?s|that is|you'?re|you are|absolutely|dead) right|correct|exactly|"
    r"spot on)\b", re.I)
# A judgement is a verdict without the words yes or no: "Spotting blood for the first day is
# normal", "it suits most kitchens", "the cheap one works". The first clause only, because a
# "fine" in the second half is a detail rather than the answer.
VERDICT_INSIDE = re.compile(
    r"\b(?:yes|no need|not really|not worth|worth it|isn'?t worth|a bad idea|a good idea|"
    # "A washing machine is worth repairing while the quote is under half the price of a new one",
    # "Worth having it looked at today". The worth is said about the doing rather than as "worth
    # it", and it is still the verdict the person asked for.
    r"\bworth (?:repairing|fixing|doing|buying|getting|having|paying|spending|keeping|servicing|"
    r"replacing|renewing|hiring|installing|the money|the effort|a go)\b"
    # "A non-refundable rate usually means no cash back" answers "can I get a refund" with the
    # verdict inside the rule rather than at the front of it.
    r"|\bmeans (?:no|yes|not)\b|"
    # "Marmite keeps for years", "an unopened tub keeps about a week past the date": the answer
    # to "does it go off" is how long it keeps, so the keeping is the verdict.
    r"\b(?:keeps?|lasts?) (?:for|until|about|roughly|easily|well|a couple|a few|a good|\d)\b|"
    # The two quality arms stay out of this list: a quality word names whatever noun is nearest,
    # so both need the line as well as the reply. See `_the_quality_answers`.
    r"harmless|safe|fine|okay|avoid|go ahead|of course|by law|make sure|only|"
    r"is (?:normal|common|usual|typical|expected|fine|safe|okay|harmless|allowed|legal)|"
    # "Lisbon is good with children if you take the trams": a verdict said about a fit.
    r"is (?:good|fine|ok|okay|great|safe|bad) (?:with|at|for|in)\b|"
    r"is (?:usually|normally|generally|probably|often) (?:just |fine|normal|harmless|safe|okay)|"
    # "is it cheaper to buy a whole chicken than pieces" / "A whole chicken is nearly always the
    # cheaper way to buy chicken": the verdict is which side comes out better, named as the
    # quality the line asked about. It is the yes, said as a comparison.
    r"\bis (?:almost |nearly )?(?:always |usually )?the (?:cheaper|cheapest|better|best|quicker|"
    r"quickest|easier|easiest|safer|safest|simpler|simplest) (?:way|option|choice|bet|buy|route|"
    r"one)\b|\b(?:works? out|comes? out|turns? out) (?:cheaper|cheapest|better|best|quicker|"
    r"easier|safer)\b|"
    r"suits|works well|works fine|no harm|nothing wrong|nothing to worry|"
    r"you'?ll be fine|it depends|not (?:a problem|necessary|needed|allowed)|"
    # The verdict often comes after the condition it applies to: "Under an hour you do not need to
    # carry anything", "for a week, you don't need to do anything". It is one clause, so the answer
    # is in it.
    r"(?:do not|does not|don'?t|doesn'?t) need\b|"
    # A no is often the verb of the question negated rather than the word "no": "does vinegar go
    # off" / "Vinegar does not go off: it keeps for years", "would a voucher be lazy" / "A voucher
    # is not a cop out". Present tense only, and no bare imperatives: "Don't crowd the pan" is
    # advice rather than a verdict and stays unread.
    r"(?:is|are|does) not\b|\b(?:isn'?t|aren'?t|doesn'?t)\b|"
    # A judgement said with the adjective instead of a yes: "smoked cannabis is harmful", "it
    # is unhealthy, but", "salt is fine in small amounts". The bot answers "is it bad for me"
    # with the verdict word itself far more often than with "yes", and the verdict is there.
    r"harmful|unhealthy|healthy|bad for|good for|not good for|risky|dangerous|unsafe|not safe|"
    r"a lot|too much|too late|not enough|plenty|worth (?:a go|doing)|the one to (?:pick|avoid))\b",
    re.I)
# A judgement of the thing asked about, said with the quality the line asked for instead of a
# yes: "is google maps free" / "Google Maps is free", "is new york good with children" / "New York
# is great with children who can keep going". Both this and `IT_HELPS` name whatever noun is
# nearest - "is it worth appealing the ticket" / "The form is free to download" is about the form
# - so both are read against the line in `_the_quality_answers` rather than counted on their own.
QUALITY_IS = re.compile(
    r"\bis (?:really |very |always |usually )?(?:great|good|fine|perfect|brilliant|lovely|ideal|"
    r"free|cheap|easy|worth it|worthwhile)\b", re.I)
# "does white noise work for babies" / "so it helps most in a shared or noisy room", "should i use
# a white noise machine" / the same reply: the pronoun stands for the thing asked about, and it is
# the yes when the line is asking whether that thing is any good.
IT_HELPS = re.compile(r"\b(?:it|this) (?:really |usually |often )?(?:helps?|works?)\b", re.I)
_WORKING = re.compile(r"\b(?:work|works|working|worked|help|helps|helping|use|using|used|worth|bother|good)\b", re.I)
# The subject of a quality said without naming the thing again: "so it is fine", "they are cheap".
_PRONOUN_SUBJECT = frozenset(("it", "this", "that", "they", "these", "those", "he", "she"))


def _the_quality_is_about_the_thing(clause, line):
    """True when the subject of "is great/free/cheap" is the thing the line asks about.

    A quality word is a verdict about whatever noun is nearest, and the nearest noun is often the
    wrong one: "is it worth appealing the ticket" / "The form is free to download, but the appeal
    usually loses" answers with a quality of the form. So the subject of the quality has to be the
    thing the line named, or the pronoun standing in for it ("so it is fine" after "is it ok").
    """
    found = QUALITY_IS.search(clause)
    if not found:
        return False
    subject = clause[:found.start()].strip()
    if not subject:
        # "Fine for a week in the fridge": the quality opens the sentence with nothing before it.
        return True
    words = _words(subject)
    if words and words[-1] in _PRONOUN_SUBJECT:
        return True
    said = _line_text(line)
    if not said:
        return True
    named = {w for w in words if len(w) >= 4 and w not in _EMPTY}
    return not named or any(w in said for w in named)


def _the_tail_says_what_it_is_about(clause, line):
    """True when the verdict in the setup's tail is said about the thing the line asked about.

    A tail verdict counts when the clause says what it judges: "is my mince gone off" / "Red meat
    is more forgiving than chicken: a grey-brown colour on the outside of a chop is just air and it
    is fine". "should i pop it" / "A smooth lump on the back of the wrist is usually a ganglion
    cyst: harmless, often smaller after a few weeks" says a quality of nothing - the thing is
    harmless, but the reply never says the blister is - and that is a wrong reply, not a verdict
    (young-latch's find).

    A named subject is not enough on its own, because the tail is often a detail rather than the
    verdict: "can i put my glasses in the washing machine" / "... load it so a hand fits flat on
    top of the pile - a packed drum does not rinse" matched the negation in "a packed drum does
    not rinse", "is it worth buying a diesel now" / "There is no fixed figure: the forecourt sign
    is the only price that matters" matched "only", and "is that normal" / "... quotes ... tell
    you whether a figure is normal" matched "is normal" while naming a test rather than giving
    one. So the subject has to be the pronoun standing in for the line's thing, or a word the line
    named, the same reading the quality arms use.
    """
    found = VERDICT_INSIDE.search(clause)
    if not found:
        return False
    subject = clause[:found.start()].strip()
    if not subject:
        return False
    words = _words(subject)
    if words and words[-1] in _PRONOUN_SUBJECT:
        return True
    said = _line_text(line)
    if not said:
        return True
    named = {w for w in words if len(w) >= 4 and w not in _EMPTY}
    return bool(named) and any(w in said for w in named)


def _the_quality_answers(clause, line):
    """The two quality arms, read against the line: see `QUALITY_IS` and `IT_HELPS`."""
    if _the_quality_is_about_the_thing(clause, line):
        return True
    return bool(IT_HELPS.search(clause) and _WORKING.search(_line_text(line)))


# A hedge is not an answer of any kind. These openings borrow the words of a shape ("it is...",
# "the steps...") while saying that the bot has nothing, so no check may count them.
PUNT = re.compile(
    r"^(?:i'?m not sure|i am not sure|i don'?t know|i do not know|i can'?t|i cannot|can'?t call|"
    r"that'?s beyond|that is beyond|that'?s all|that is all|there is no more|"
    r"beyond what i know|not mine to|not a call|not one i can call|a quick search|searching for|"
    r"i'?d rather not|"
    r"you haven't told me|that'?s a good question|good question|no idea|not something i|"
    # "No figure from me on that, sorry: it moves with where you are and when you go" says the bot
    # has nothing, and it opens on "No", so it read as a verdict on every yes/no line and as a
    # method on every "how do i" one. Whatever shape word it borrows is the same shrug.
    r"no (?:figure|number|price|answer|idea) from me|"
    r"i'?m not sure (?:what|how|which|whether|where) to|i'?m not sure without)", re.I)
# The same shrug in the shape's own clothes: a hand-off, or an admission that there is nothing more
# to say. These open the way a verdict does - "That's ...", "It's ..." - so `VERDICT_OPEN` counted
# them as one, though none of them says what to do. "That's your call, not mine" answers a
# "should i ..." with no verdict at all, "That's one for your GP rather than me" hands the question
# to somebody else, and "That is everything I have on that one, so I would only repeat myself" says
# the bot is out of things to say. The trick is not to add a word to the verdict list but to say
# that no shape may be read out of them, which is what `PUNT` is for.
HANDOFF = re.compile(
    r"^(?:(?:that'?s|that is|it'?s|it is) (?:your|a) call(?![a-z])|"
    r"not (?:a )?call (?:i|we) (?:can|could|would)|"
    r"(?:that'?s|that is) (?:one|a question|something) for (?:your|a|the)\b|"
    r"(?:that'?s|that is) (?:everything|all) i (?:have|know)\b|"
    r"i would only repeat myself|nothing more i can (?:say|add|tell)\b|"
    r"(?:that'?s|that is) not for me to|"
    r"(?:i'?ll|i will) leave (?:that|this|it) to (?:your|a|the|somebody|someone)\b)", re.I)


def is_a_punt(opening):
    """True when the reply's opening says the bot has nothing to give, in whatever clothes.

    Every shape check asks this first, so a hand-off is never a figure, a place, a method or a
    verdict, whatever words follow it.
    """
    return bool(PUNT.match(opening) or HANDOFF.match(opening))
# A line that asks what will happen if the person does something ("will it come back if i just
# wipe it", "if i set off at 5 will i miss my flight") wants the outcome of that action, so doing
# the action for them is not the answer. A line that says what it will do and then asks whether
# ("can i send it back if i change my mind", "should i get a dog if i work full time") is still
# asking whether to, and the job is the answer to that one.
HYPOTHETICAL = re.compile(r"\bif (?:i|we|you)\b", re.I)
OUTCOME_ASK = re.compile(r"^(?:and )?(?:will|would|does|do|did)\b|^if\b", re.I)


def _an_outcome_of_their_own_doing(line):
    """True for "will it break if i leave it", False for "can i send it back if i change my mind"."""
    said = str(line or "")
    return bool(HYPOTHETICAL.search(said) and OUTCOME_ASK.search(said))


# A test is a verdict: "are my scones done" / "They are risen and browned on top, and a skewer
# in the middle comes out clean". The test can sit past the first clause, so it is read from the
# whole opening - unlike the judgement words above, which are only the answer when they are the
# first thing said.
# The verdict is sometimes said after the reason for it, and the reason is what the first clause
# reads: "That one is the ordinary kind, so no", "It is a part and a few pounds, so yes". Only a
# connector plus a bare verdict counts, so a judgement in a later clause ("..., and if it smells
# fine you are okay") is still not read as the answer.
TRAILING_VERDICT = re.compile(
    r"[,\-\u2013\u2014]\s*(?:so|then|but|which means|that means|meaning)\s+"
    r"(?:no|yes|nope|not really|definitely not|probably not|of course|not worth it)\b", re.I)

TEST_IS_THE_VERDICT = re.compile(
    r"comes? out clean|is done when|is ready when|is cooked when|"
    r"when it'?s? (?:firm|golden|clean|set|done)|"
    r"if it (?:looks|feels|comes|smells) (?:done|cooked|firm|golden|clean|set|right)", re.I)


# A permission said as a rule is the yes: "Anything bought online, by phone or by post can be
# cancelled within 14 days of it arriving" answers "can I cancel an order I just placed", and "it
# costs nothing to apply" answers "do i get free bus travel if im disabled". A modal in front of a
# passive is about what may be done, so it is the verdict even when the rule takes most of the
# sentence to reach it - which is why this one is read over the whole opening and not its first
# clause like the rest of `VERDICT_INSIDE`.
PERMISSION_RULE = re.compile(
    r"\b(?:can|cannot|can'?t|could|couldn'?t|may|must|should|need(?:s)? to) be [a-z]+ed\b"
    r"|\bcosts? nothing\b", re.I)

# A decision that turns on the person's own facts is answered by the test that settles it: "Fix it
# if it is a part and a few pounds; bin it if the repair is half the price of new", "Repair it if
# it is under five years old and the fault is the battery, the drive...". The two sides of the rule
# are the two answers, so whichever way the person's case falls they have theirs - that is the yes
# and the no together, and it is what "is it worth fixing" is asking for. Both sides have to be
# said about the same thing, which is why each verb carries its "it": "fix it" and "bin it" are a
# decision, while "keep the room cool" and "throw the water away" are two jobs.
RULE_CONDITION = re.compile(
    r"\b(?:if|when|while|once|until|unless|over about|under about|more than about|"
    r"less than about|half (?:of )?the price)\b", re.I)
RULE_KEEP_IT = re.compile(r"\b(?:fix|repair|keep|mend|service)\s+it\b", re.I)
RULE_DROP_IT = re.compile(r"\b(?:bin|replace|scrap|chuck|throw)\s+it\b", re.I)


# A yes said by echoing the question's own verb: "will it get better" / "It does, and the change is
# in the sleep rather than in the work". Only the auxiliaries that answer a yes/no, because "It was
# 40 pounds" is a figure and "It matters" is not a verdict.
VERDICT_ECHO = re.compile(
    r"^(?:it|that|this|they|these|those|he|she) "
    r"(?:does|do|did|will|would|can|could|should|doesn'?t|don'?t|didn'?t|won'?t|can'?t|"
    r"shouldn'?t)\b"
    # A negative is a verdict whichever person it is said in: "is it too late" / "You would not be
    # late".
    r"|^(?:you|we) (?:would|will|do|did|can|could|should) not\b", re.I)
# travel" / "In England you apply for the older person's bus pass through your council once you
# reach the state pension age", "i live alone, do i get money off" / "Living alone gets 25 per cent
# off the bill", "do you tip at a bar" / "In a pub, nothing ... there is no table service to tip".
# Only phrases that answer a yes or a no on their own are read here.
VERDICT_RULE = re.compile(
    # what the person is entitled to, and how they get it
    r"\byou (?:qualify|are owed|are entitled|can claim|claim|can apply|apply for|are covered|"
    r"do not need|don't need|get it|can get one|can have one)\b"
    # the rule told as what the thing gets or costs: "Living alone gets 25 per cent off the bill"
    r"|\bgets? (?:\d[\d,.]*|a|the|half|a third|one) (?:per cent|percent|%)\b"
    # the thing is the wrong one to choose: "so it is the wrong choice if yours are already poor"
    r"|\bis the wrong (?:choice|one|thing|call)\b"
    # nothing is owed: "In a pub, nothing: you order and pay at the bar, so there is no table
    # service to tip"
    r"|\bthere is no (?:table service|need|charge|fee|cost)\b"
    r"|\bnothing to (?:tip|pay|declare|owe|worry about)\b", re.I)
# The verdict often comes after the case it is about: "For running, yes: a proper pair makes a
# real difference", "In this weather, no", "On balance, yes". The person asked whether, and the
# reply says which once it has named the situation. Only the strong half of `VERDICT_OPEN` is read
# after the comma, because a case followed by "warm" or "just" is a step ("In the pan, warm the oil
# first"), not a verdict.
VERDICT_AFTER_A_CASE = re.compile(
    r"^(?:for|in|on|with|at|if|when|unless|after|before)\b[^,.;:!?]{1,40},\s*"
    r"(?:yes|yeah|yep|yup|no|nope|nah|not|never|definitely|absolutely|probably|usually|generally|"
    r"normally|mostly|it'?s|it is|that'?s|that is|you'?re|you (?:can|could|should|don'?t))\b", re.I)
# A comparison answered by naming the winner: "Washing up by hand is the cheaper one", "the dried
# version is the better bet". The person asked which, and the reply says which.
THE_WINNER_NAMED = re.compile(
    r"\bis the (?:cheaper|better|worse|cheapest|best|worst|safer|safest|healthier|healthiest|"
    r"stronger|weaker|easier|harder) (?:one|option|choice|bet|buy|of the two)\b", re.I)


# A verdict said about the thing, in words `VERDICT_INSIDE` does not hold: a comparison against
# the other one ("is the better everyday loaf", "is one of the kinder things for knees", "is a good
# way to save 30 to 50%"), or the yes behind a condition ("If you can make it, go", "if the quote is
# more than the car is worth, let it go"). Both are read over the whole opening and only beside the
# line - see the credit in `gives`. Every arm names the verdict rather than describing the thing:
# "is a decent everyday food" on its own is left unread, since a description with no comparison in
# it is not the answer to a yes/no.
VERDICT_ABOUT_IT = re.compile(
    r"\b(?:is|are|was|were) (?:the|one of the|a) (?:better|best|safest|kindest|cheapest|healthiest|"
    r"easiest|simplest|nicest|worst|strongest|tastiest|kinder|safer|cheaper|healthier|easier)\b"
    r"|\bis a good (?:way|idea|choice|bet|pick|option|buy|start|investment)\b"
    r"|\bis the one (?:to|for|that|you)\b"
    r"|\bworth (?:reading|knowing|having|checking|watching|visiting|seeing|a look|a read)\b"
    r"|\b(?:if|unless|when)\b[^.;]{0,90},\s*(?:then\s+)?(?:go|go ahead|go for it|yes|no|fine|okay|"
    r"safe|skip|skip it|leave it|let it go|do it|take it|avoid it|worth it|try it|"
    r"it'?s (?:fine|okay|safe|worth it)|that'?s (?:fine|okay|safe)|you'?re (?:fine|okay|safe))\b",
    re.I)
# A word long enough to be the thing a line is about rather than a joining word. The naming guard
# below asks whether the reply used one of the line's own words, so a word nearly every line and
# nearly every reply share - "with", "have", "that", "time", "good" - cannot count as the name.
_NAMING_WORD = re.compile(r"[a-z]{4,}")
NAMING_STOP = frozenset("""
that this with have your them when what just like then than also make need from into over been
were will would could should about there their some more most much very only even still well
good best fine time times day days year years work works thing things home back down know want
take keep give goes going said says here where while which whose these those being does doing
done made many each both after before again always never often sometimes usually really quite
rather around without within because since until during other another same different little
small large""".split())


def _names_what_the_line_named(opening, said):
    """True when the reply's first clause uses a word of its own that the line also used.

    The words a line and a reply share because both are English say nothing, so they are dropped
    before the comparison; what is left is the name of the thing that was asked about. The name has
    to sit in the clause that carries the verdict, because that is what the verdict is said about:
    "is a peace lily safe for cats" / "Lilies are the worst plant for cats" names its subject,
    while a word met further along the sentence ("... a year of rent tax free" answering a council
    tax question) is a coincidence of subject matter, not an answer about it.
    """
    words = set(_NAMING_WORD.findall(said.lower())) - NAMING_STOP
    if not words:
        return False
    first_clause = re.split(r"[,;:]", opening, maxsplit=1)[0]
    return bool(words & set(_NAMING_WORD.findall(first_clause.lower())))


def _the_rule_names_both_sides(reply):
    """True when the reply settles the decision for each side of a condition.

    "Fix it if it is a part and a few pounds; bin it if the repair is half the price of new" is
    the answer to "is it worth fixing": the person's own case falls one way or the other, and the
    reply has said what to do in both. Read over the whole reply, because the second side is often
    the second sentence ("Rule of thumb: fix it while the part is a few pounds and you can fit it
    yourself. Replace it once the repair costs more than about half of a new one").
    """
    if not reply or not RULE_CONDITION.search(reply):
        return False
    return bool(RULE_KEEP_IT.search(reply) and RULE_DROP_IT.search(reply))


def _a_yesno(opening, line=None):
    if is_a_punt(opening):
        return False
    if FIRST_PERSON_VERDICT.match(opening) or VERDICT_OPEN.match(opening) \
            or ECHO_VERDICT.match(opening) or VERDICT_AFTER_A_CASE.match(opening):
        return True
    if PERMISSION_RULE.search(opening):
        return True
    if VERDICT_ECHO.match(opening) or VERDICT_RULE.search(opening):
        return True
    first_clause = re.split(r"[,;:]", opening, maxsplit=1)[0]
    if VERDICT_INSIDE.search(first_clause) or TEST_IS_THE_VERDICT.search(opening) \
            or TRAILING_VERDICT.search(opening) or THE_WINNER_NAMED.search(first_clause):
        return True
    if _the_quality_answers(first_clause, line):
        return True
    # A verdict often comes after the setup that leads to it, and the setup is not the answer:
    # "Red meat is more forgiving than chicken: ... it is fine", "A steady, even sound covers the
    # small noises ..., so it helps most in a shared or noisy room". Only the clause the colon or
    # the `so` introduces is read, not the whole sentence, and only for this shape.
    tail = ""
    if ":" in opening:
        tail = opening.split(":", 1)[1]
    else:
        found = re.search(r",?\s+so\b", opening)
        if found:
            tail = opening[found.end():]
    tail = re.split(r"[,;]", tail, maxsplit=1)[0] if tail else ""
    return bool(tail and (_the_tail_says_what_it_is_about(tail, line)
                          or _the_quality_answers(tail, line)))


# A no often comes as the line's own verb, denied: "does vinegar go off" / "Vinegar does not go
# off", "is it worth it" / "It isn't worth it", "do i need to preheat" / "You don't need to". The
# reply names the question back and denies it, which is the no however the sentence is built.
NEGATED_AUX = re.compile(
    r"\b(?:is|are|was|were|do|does|did|have|has|had|can|could|will|would|should|must|need|"
    r"needs|kills?|harm|hurt|matter|work|works)\s*(?:not|n'?t)\b|\b(?:isn'?t|aren'?t|wasn'?t|"
    r"weren'?t|don'?t|doesn'?t|didn'?t|haven'?t|hasn'?t|can'?t|cannot|won'?t|wouldn'?t|"
    r"shouldn'?t)\b", re.I)


def _an_echoed_no(opening, line):
    """True when the first sentence denies the line's own words: "Vinegar does not go off".

    The reply has to do both things - carry a denial, and name something the line named - or it
    is not an answer to this line. "It isn't cooked until the skewer comes out clean" denies
    nothing of "are my scones done", so the test-reading is what settles that one.
    """
    said = _line_text(line)
    if not said or not NEGATED_AUX.search(opening):
        return False
    words = set(re.findall(r"[a-z][a-z']*", said))
    named = {w for w in words if len(w) >= 4 and w not in _EMPTY}
    return any(w in opening for w in named)


def _the_job_answers(opening, line):
    """True when the reply does the thing the person asked whether to do.

    A yes/no about doing something is often answered by doing it: "Slice it first, then bag it"
    is the yes to "can i freeze bread", "Strap them in every time" the yes to "do i need to
    strap my toddler in". This is a yes and never a miss: the reply is only counted when it
    opens on a job and the line is asking whether, so a reply this cannot read stays the
    "words cannot tell" it was before.

    Not when the line asks what happens if it does something itself: then the outcome is the
    answer, and "Wipe it off with a mould spray" is no answer to "will it come back if i just
    wipe it". That one is a miss the clear-shape test below makes, on the method it names.

    The price of reading any verb and not a list of them: an instruction about something else
    passes too. "is my butter out of date" / "Rub washing-up liquid into the grease mark", and
    "did you see the match last night" / "Dip your headlights as soon as another car is in sight"
    are misses this calls a fit (rugged-tuna's find in review). Both narrowings I measured cost
    more good replies than they save: requiring the reply to name a word from the line turns 7
    fits into faults ("should he dye it" / "Colour the new growth every four to six weeks"), and
    requiring `PERMISSION` in the line turns 5 ("is it rude to leave a group chat" / "Mute it
    first", "am i getting enough water each day" / "Fill a bottle in the morning"). At 612 shaped
    turns the wide reading takes misses from 150 to 134 and the narrow ones to 137 and 139, so it
    is kept, and the error left is the one that hides a miss rather than the one that invents one.
    """
    if not line or _an_outcome_of_their_own_doing(line):
        return False
    if JOB.match(opening):
        return True
    # The doing is the yes whichever verb says it. JOB carries the verbs the cue list knows, and
    # the deck answers "do i need to see a physio" with "See a physio if the pain has lasted more
    # than a fortnight", and "hotel room was filthy can i get a refund" with "Photograph it and
    # complain at reception". The shape of the opening - a verb and the thing it acts on - is
    # what makes it the job, not the verb being on a list.
    if _imperative(opening):
        return True
    return _the_job_named(opening, _line_text(line))


# A pick names a side or says which one to take. A paragraph that describes one side and stops
# has not picked, and neither has a card that names both things without preferring one.
PREFERS = re.compile(
    # A pick also names the side it took and starts with it: "Replace the dishwasher", "Repair
    # it while the quote is under half". The verb is at the front, so it is what is chosen rather
    # than a step in a method.
    r"^(?:replace|repair|rebuild|service|swap|install|keep|buy|rent|hire|book|order|get|go for|"
    r"go with|take|choose|pick|stick with|read|watch|visit|try|start with|hold off|wait)\b"
    r"|\b(?:better|best|rather|instead|go for|go with|opt for|choose|pick|stick with|"
    r"you (?:mentioned|said|named|had)|you'?re on|"
    r"\b(?:buy|get|fit|install|replace|repair|swap|go for|go with) (?:the|a|an|one|it)\b|"
    r"i'?(?:d| would) (?:go|do|make|cook|have|take|get|pick|choose|suggest|recommend|buy|wear|"
    r"watch|read|order|book|serve|use|say|stay|leave|keep|skip|cancel|wait|ring|call)|"
    r"worth (?:the extra|it)|"
    r"either .{0,40}\bor\b|"
    # A pick said with what it is worth doing: "A dishwasher is worth repairing while the quote is
    # under half the price of a new one" has taken the repair without naming it first.
    r"\bworth (?:repairing|replacing|fixing|doing|keeping|buying|getting|upgrading|waiting|"
    r"swapping|having|sticking with)\b|"
    r"both are|both work|depends on|for (?:a|the) .{0,30}\band\b.{0,30}\bfor\b)\b", re.I)


# A pick can be one noun with no verb at all: "The heat pump.", "Oat milk for coffee", "Lisbon."
# It is a pick only when it is short, opens on a thing rather than on a verdict, and is not a
# hedge; "Nope." and "Can't call that one." are the two ways a short opening is not a pick.
BALD = re.compile(r"^(?:the|a|an|this|that|[A-Z][a-z]+)\b")
# A finite verb makes an opening a statement rather than a bare name: "Small cars hold their
# value well." opens on a thing but says something about it, and that is not a pick.
BALD_VERB = re.compile(
    r"\b(?:is|are|was|were|has|have|holds?|works?|comes?|goes?|keeps?|takes?|lasts?|costs?|"
    r"means|does|do|will|can)\b", re.I)


# The thing a reply names before its colon: "Day trips from Dublin: ...". The head is read on its
# own, because it is the pick; the rest is detail.
def _undecorated(head):
    """A head without the asterisks or quotes that set it off: "*Note*" and "Note" are one label."""
    return head.strip().strip("*_\"\u201c\u201d'").strip()


NAMED_HEAD = re.compile(r"^(.{2,70}?):\s", re.S)
# A head that asks, instructs, or labels a list is not a thing named: "How to clean a mattress:
# ...", "Steps to follow: ...", "First: ...".
ASKS_HEAD = re.compile(r"^(?:how|what|why|when|where|which|who|steps?|first|firstly|then|next|to|"
                       r"tldr|quick tips?)\b", re.I)
# A label on its own introduces several things rather than naming one: "Quick: tuna pasta in 15, a
# stew in 25", "Cheap: beans on toast", "While you cook: three albums", "Best: ...". The colon
# there is a heading over a list, so the head is not the answer. sleek-shark found these in PR 7875
# and the two rules are the same rule; a label with words after it is still a thing named ("Cheap
# weeks come from the same eight things: ..."), so only the bare label is refused.
LABEL_HEAD = re.compile(r"^(?:quick|best|cheapest|easiest|fastest|faster|fast|simplest|simple|"
                        r"cheap|easy|options?|ideas?|while you [a-z]+|bonus|top|also|first|firstly|"
                        r"then|next|tip|tips|note|tl;?dr|answer|short answer|in short|verdict|"
                        r"my pick|worth it)\s*$", re.I)
# A label over a list is a pick only when the label names something. "Ten-minute dinners:" and
# "For laughs:" name a thing, so the colon is the reply saying "here is the answer". "Quick:",
# "Cheap:" and "While you cook:" name a hurry, a price or a moment, so what follows is a menu of
# options and none of them is picked: "Quick: tuna pasta in 15, macaroni cheese in 25, or a
# sausage traybake" answers "any ideas for dinner" and not "what should i cook tonight".
# lilac-bell ruled it, as the lane that owns the want. A label that declares the answer itself
# ("my pick", "short answer", "the verdict") does name it, so those are left out of this list and
# keep the pick they open on: "Short answer: the Corolla, or a Civic if you want it to last".
SET_LABEL = re.compile(
    r"^(?:quick|best|cheapest|easiest|fastest|faster|fast|simplest|simple|cheap|easy|options?|"
    r"ideas?|while you [a-z]+|bonus|top|also|first|firstly|then|next|tip|tips|note|worth it)\s*$",
    re.I)
# A head that points back at the last answer names nothing new: "Same as before: About 40 minutes
# start to finish" is the earlier answer repeated, not a pick, and it was the last false pass left
# in a 547-turn sweep. It is the follow-up answering itself, so the reply is a reminder of a shape
# rather than that shape given again.
ECHO_HEAD = re.compile(r"^(?:same as (?:before|last time)|as (?:before|above)|like before|"
                       r"as i said|same|same again|still|unchanged|no change)\s*$", re.I)
# A head that talks about the earlier answer names no thing either: "You've got it:", "I like
# them:", "That's the one:". The label arm already refused these and the *head* arm was the way
# round it, so the two rules are now the same rule: the words after the colon are a comment on the
# last answer rather than a thing picked. "It depends:" is not one of them - a Fiesta for town and
# a Focus for the motorway is still a choice.
BACK_HEAD = re.compile(
    r"^(?:you'?ve got it|you got it|i (?:like|liked|love|prefer) (?:it|them|that|those)|"
    r"that'?s (?:it|right|the one)|this one|as i said|like before|"
    r"same as (?:before|last time))\b", re.I)
# A head that *states* something names no pick: "An air fryer is a small oven: it sits on the
# counter", "It is worth it: bin it". A copula in the head makes it a description, a verdict or a
# comparison, and the pick is the thing before the colon - which is not there. tidy-chalk found
# five of these in review (8195); "It depends: a Fiesta for town" states nothing, so it stays.
STATES_HEAD = re.compile(r"\b(?:is|are|was|were|means|sounds?|seems?)\b|"
                         r"\b(?:it|that|here|there|what)'s\b", re.I)
# ...and a head that frames the answer is not a thing named either: "Here's the thing: you have to
# decide", "Think of it as a sponge: it soaks up the water". The short answer, my pick and best
# bet are different: they say "the answer comes next" without stating anything of their own.
FRAME_HEAD = re.compile(r"^(?:here'?s|think of it|imagine|to be fair|the (?:truth|thing|point|"
                        r"trick|catch|problem|issue|trouble|trouble is)|honest\w*|"
                        r"the way i see it|what you want)\b", re.I)


# A which-question is answered by saying what the difference is: "A marathon is 26.2 miles and a
# half is 13.1, so the full race is exactly twice as far", "40 is the setting for uniform". The
# reply names the side that wins by comparing it, with no "better" anywhere, so the comparative
# itself is the pick.
PICKS_BY_COMPARISON = re.compile(
    r"\b(?:is|are|was|were) (?:the )?(?:longer|shorter|bigger|smaller|taller|wider|deeper|"
    r"heavier|lighter|faster|slower|quicker|cheaper|dearer|pricier|warmer|colder|hotter|newer|"
    r"older|nicer|easier|harder|safer|stronger|thicker|thinner)\b"
    r"|\b(?:is|are) (?:exactly |about |nearly |roughly )?twice as\b"
    r"|\bis the (?:one|answer|pick|choice|setting|winner|default)\b"
    r"|\bare the thing\b|\bthe thing to (?:get|buy|have|do|go for)\b", re.I)
# "I'd do a frittata", "I'd keep the old one": what the bot would do is a pick, whichever verb it
# is about the thing in the line.
WOULD = re.compile(
    r"\bi'd (?:do|make|cook|have|wear|say|keep|buy|book|order|get|take|go|try|use|put)\b", re.I)

# A pick often says who or when it is for first and colons into the list: "Quick: tuna pasta in 15,
# a frittata in 20, or a sausage traybake", "For laughs: *What We Do in the Shadows*...", "Kids,
# about 15 minutes: pasta with butter and cheese, fish fingers or a small roast". The bot's own
# answer to "what should I cook tonight" is written this way, so reading only the part after the
# colon is the difference between a miss and a plain pick. The lead has to be a label rather than
# a fact about the thing ("Hard water is the reason: it carries dissolved calcium" is a why-answer)
# and a frame that points back ("You've got it:", "Same as before:") is not a label either.
LABEL = re.compile(r"^([^:]{1,90}):\s+(\S.+)$")
NOT_A_LABEL = re.compile(
    r"\b(?:is|are|was|were|means?|reason|cause|because|depends?|you'?ve got|same as|as before|"
    r"good question|it'?s|that'?s|there'?s|here'?s|"
    r"^i (?:like|liked|love|prefer) (?:it|them|that|those)|^both|^same)\b", re.I)


def _listed_after(label_lead):
    """True when the words after a lead's colon are a list of things to pick from."""
    if re.search(r"\bor\b", label_lead, re.I) or ";" in label_lead:
        return True
    # "For laughs: *What We Do in the Shadows* (a daft vampire mockumentary), *The Nice Guys*" is
    # a list too, so two commas between named things count; one comma is a sentence in two halves.
    return len(re.findall(r",\s+\S", label_lead)) >= 2


def _marked_things(opening):
    """How many things the opening marks out as things: a title in asterisks or in quotes. The
    reply is pointing at named things rather than describing a method."""
    return len(re.findall(r"\*[^*\n]{2,60}\*", opening)) + len(
        re.findall(r"\u201c[^\u201d\n]{2,60}\u201d|\B\"[^\"\n]{2,60}\"", opening))


# A pick that sets the thing it chose in emphasis: "*Understanding Exposure* by Bryan Peterson".
# The title is the answer, and the words after it say why rather than what the thing is. `_marked_things`
# above counts two or more marked things as a list; this is the same reading for the one thing a pick
# names, so it has to sit on the pick and not on the list. A colon straight after the emphasis is the
# other way a label looks: "*Note*: warm the pan first" sets off what comes next rather than naming a
# thing chosen, so the emphasised span stops counting there.
NAMES_IN_EMPHASIS = re.compile(
    r"^\*{1,2}[^*\n]{2,70}\*{1,2}(?!\*)(?!\s*(?:is|are|was|were|means|refers|describes|comes)\b)"
    r"(?!\s*:)")


def _a_pick(opening):
    if PREFERS.search(opening) or PICKS_BY_COMPARISON.search(opening) or WOULD.search(opening):
        return True
    lead = LABEL.match(opening)
    if lead and not NOT_A_LABEL.search(lead.group(1)) \
            and not SET_LABEL.match(lead.group(1).strip()) and _listed_after(lead.group(2)):
        return True
    # A pick often names the winner instead of preferring it: "A cremation with no service is the
    # cheapest", "Showering wins on time and water". Any superlative does that job, not only the
    # ones on a list, so the shape is the ending: "London City is the closest to the centre", "the
    # second bedroom is the quietest", "a slow cooker is the most forgiving". The word before it
    # may be an adverb of habit ("is usually the cheapest") and it changes nothing. A word that
    # ends in "est" without judging anything - a request form, the west wing, an earnest try - is
    # kept out by name, and a figure cannot reach this path, so a name that is a time is unaffected.
    if re.search(r"\bis (?:almost |nearly |usually |often |always |generally |probably |still |"
                 r"quite |about )?(?:the )?(?:(?!(?:request|interest|honest|guest|test|rest|nest|"
                 r"west|east|forest|harvest|protest|suggest|arrest|contest|digest|invest|earnest|"
                 r"chest|crest|tempest|midwest|northwest|southwest|northeast|southeast)\b)"
                 r"[a-z]{3,}est|most [a-z]+|least [a-z]+)\b|"
                 r"\bis the (?:cheapest|dearest|worst|easiest|quickest|safest|hardest|"
                 r"cheaper|better)\b|\bwins?\b(?: on| over| for| by)\b|"
                 # The question asked for a superlative and the reply names the thing that holds
                 # it: "India has the most people", "Lisbon has the cheapest beds".
                 r"\b(?:has|have|holds|gets) (?:the )?(?:most|highest|lowest|fewest|best)\b",
                 opening, re.I):
        return True
    if NAMES_IN_EMPHASIS.match(opening):
        return True
    if is_a_punt(opening) or VERDICT_OPEN.match(opening):
        return False
    # A pick often names the thing and then says why: "Day trips from Dublin: Howth for the cliff
    # walk, Malahide castle, and Glendalough", "Something that makes a day in bed easier: a flask
    # of soup with bread", "*Flour Water Salt Yeast* by Ken Forkish for bread: four ingredients".
    # The colon is the reply saying "here is the answer", and the head before it is a thing
    # rather than an instruction or a question: "Fix the wake-up time first: the same hour every
    # day" is advice, "How to clean a mattress: vacuum it" is a method, and both stay misses.
    head = NAMED_HEAD.match(opening)
    if head:
        # The head is read without the marks that set it off: a label is a word, so "*Note*:" and
        # "**Note**:" are the same label as "Note:" and introduce what follows rather than naming
        # a thing chosen.
        named = _undecorated(head.group(1).strip())
        # A head that points back, states, frames or measures is not the thing picked: "Same as
        # before: About 40 minutes start to finish", "An air fryer is a small oven: ...", "Here's
        # the thing: you have to decide", "About 40 minutes start to finish: fry the mince".
        # `BACK_HEAD` is here too, so the head arm and the label arm read the same heads the same
        # way. "Same as before: About 40 minutes start to finish" was already a miss, and
        # "You've got it:" - the same words in a friendlier frame - was still a pick.
        if (ECHO_HEAD.match(named) or BACK_HEAD.match(named) or STATES_HEAD.search(named)
                or FRAME_HEAD.match(named)
                or (bool(re.search(r"\d", named)) and (_a_time(named) or _an_amount(named)))):
            return False
    if (head and not INSTRUCTS.match(_undecorated(head.group(1)))
            and not ASKS_HEAD.match(_undecorated(head.group(1)))
            and not SET_LABEL.match(_undecorated(head.group(1)).strip())):
        return True
    words = opening.rstrip(".!").split()
    return (len(words) <= 6 and bool(BALD.match(opening))
            and not BALD_VERB.search(opening))


# The words that make an opening a method: an ordinal step, a verb doing something to a thing,
# or an instruction with no "first" and no "then" ("Open a Lifetime ISA and put a standing
# order in"). The verb at the very front is the instruction; the same word later is a detail.
DOES = re.compile(
    r"\b(?:first|firstly|then|next|after that|afterwards|finally|lastly|start by|start with|"
    r"begin by|once (?:it|that|you)|step one|step 1|before you|while you|leave it|put it|"
    r"take it|turn it|give it|run it|use a|use the|you (?:could|can|should|need to) (?:try|use|"
    r"start|put|take|run|give|leave|set|check))\b", re.I)
INSTRUCTS = re.compile(
    r"^(?:open|book|ring|call|phone|top|wipe|soak|give|leave|put|take|turn|run|use|set|check|"
    r"clean|wash|rinse|melt|stir|mix|fry|boil|bake|roast|grill|simmer|add|pour|spread|cut|chop|"
    r"slice|peel|grate|whisk|beat|knead|roll|press|heat|cook|drain|freeze|cool|cover|store|keep|"
    r"throw|bin|recycle|replace|repair|fit|fix|install|service|bleed|flush|tie|wrap|apply|ask|tell|"
    r"send|email|visit|go|start|finish|stop|avoid|make|buy|order|measure|weigh|label|file|"
    r"register|report|complain|sign|write|read|watch|listen|carry|hold|stand|sit|wait|test|"
    r"taste|smell|look|choose|pick|swap|follow|keep|get|bring|put|note|note down|squeeze|rub|"
    r"scrape|buff|dab|blot|scoop|trim|mist|sweep|pat|fold|split|delay|aim|try|hook|wedge|prop|"
    r"secure|tape|glue|batch|preheat|defrost|pick over|sort out|go through|block|treat|air|"
    r"cancel|renew|practise|practice)\b",
    re.I)
# An instruction can also be told as what not to do: "Don't wear white or cream to a wedding".
DOES_NOT = re.compile(r"^(?:don'?t|do not|never|avoid|skip|stop|no need to)\b", re.I)
# The verbs an answer about what to do can open on. INSTRUCTS is the short list a method is read
# by; this is that list plus the everyday body, money and device ones, because a yes/no is just as
# often answered by "Strap them in every time" or "Pay a little each month" as by "Slice it first",
# and widening the method list itself would make every reply that opens on one of them a step.
# "See a GP if it lasts more than a week" is the yes to "should i see someone", and the seeing of
# somebody is the one job `INSTRUCTS` did not carry: it had `visit` and `ring`, not `see`.
JOB = re.compile(INSTRUCTS.pattern.replace(
    r")\b", r"|see|strap|warm|wear|feed|water|brush|rest|drink|eat|sleep|walk|save|pay|spend|charge|"
    r"plug|reset|update|download|print|scan|iron|sand|paint|screw|seal|glue|tape|hang|fold|dry|"
    r"find|"
    r"air|bath|shower|talk|say|reply|text|answer|freeze|chill|cool|defrost|thaw|soak|rinse|"
    r"change|adjust|"
    r"scrub|boil|bake|roast|fry|cook|chop|slice|peel|stir|mix|whisk|season)\b"), re.I)
# A statement opens on the same verb a method does and then says what the thing does: "Rest is what
# it needs", "Warm weather makes it worse", "Dry air helps a lot" all read as a method once the
# opening can be a verb, and none of them tells the person what to do. The words just after the verb
# tell the two apart. Only finite verbs are listed: "Drink plenty of water", "Eat more fibre" and
# "Rest 10 minutes" are methods whose object is a quantity, so a determiner list would lose them.
SAYS_WHAT_IT_DOES = frozenset((
    "is", "are", "was", "were", "am", "makes", "make", "made", "helps", "help", "needs",
    "need", "seems", "happens", "takes", "gives", "keeps", "does", "comes", "goes", "looks",
    "sounds", "stops", "starts", "works", "hurts", "depends", "matters", "causes", "means",
    "prevents", "beats", "lowers", "raises", "reduces", "improves", "eases", "dries", "warms",
    "cools", "stays", "gets",
    # The third person and the base form of the same verbs: a plural subject's verb is as often the
    # one that turns a statement into a statement ("Rest days matter more than you think", "Sleep
    # debt builds up over weeks") and only the forms on the list were refused, so three statements
    # read as methods again. None of these can follow a method's verb before its object - "Rest
    # days" is not the object of "Rest" - so they cost no method.
    "matter", "build", "builds", "vary", "varies", "cost", "costs", "change", "changes",
    "depend"))
# A method does not always open with a verb: "A damp cloth with washing-up liquid takes off most
# marks" is the instruction, and so is anything after a colon that opens on a verb.
# A method told as the routes to it: "Three routes: a council bulky waste collection (usually
# charged), the tip if you can drive it there, or a charity that collects". The head names the
# means and the list after the colon is the way, so the reply answers a how question with no
# instruction verb anywhere. A set of facts about a thing is not one of these, so the head has
# to carry the word for a means.
MEANS_NAMED = re.compile(
    r"^[^:]{0,40}\b(?:routes?|ways?|options?|methods?|approaches?|choices?)\b\s*:", re.I)

MEANS_OF = re.compile(
    r"\b(?:with|using) (?:a|an|some|the)\b.{0,40}\b(?:takes? (?:off|out|away)|lifts?|removes?|"
    r"cleans?|works|does it|gets? (?:rid of|it off))\b"
    r"|:\s*(?:follow|put|take|give|get|ask|ring|call|send|keep|check|book|use|do|start|run|"
    r"leave|try|add|make|go)\b", re.I)


# A method often puts its reason first and the instruction after it: "Streaks are an uneven coat,
# not a bad paint: roll in strips a roller wide and lap the last strip while it is still wet",
# "Sticking is nearly always a wet dough meeting a dry surface, so the fix is less water and more
# flour where the two meet. Chill the pastry 20 to 30 minutes before rolling." Reading only the
# opening clause called both of those a definition, so a how-to answered with its own cause was
# scored as a question the bot had not answered. The instruction after a colon or a semicolon, and
# the sentence after a one-clause reason, are part of the same answer.
#
# A request for information is not one of those instructions: "Happy to. Tell me what's going on
# and we'll take it from there" opens on a nod, and the telling is the person's job, not a step.
WANTS_INFO = re.compile(r"\?|^(?:tell me|say which|let me know|say more)\b", re.I)
# A step is an instruction, and an instruction has no subject: the verb comes first and the thing
# it acts on comes straight after - "Chill the pastry 20 to 30 minutes", "Lift it back between the
# posts", "Pump to the range printed on the tyre". A statement puts something else there ("Nuts
# keep 3 to 6 months", "Radiators that are hot", "Sticking is nearly always"), which is how the
# two are told apart without a list of every verb in the kitchen.
NOT_A_VERB = frozenset((
    "the", "a", "an", "this", "that", "these", "those", "it", "its", "it's", "they",
    "you", "your", "we", "our", "i", "my", "me", "he", "she", "his", "her", "there",
    "here", "what", "which", "who", "why", "how", "when", "where", "if", "once", "after",
    "before", "for", "with", "on", "in", "to", "of", "at", "by", "from", "so", "but",
    "and", "or", "also", "then", "never", "always", "most", "some", "all", "every", "any",
    "no", "not", "one", "two", "both", "each", "few", "many", "more", "less", "very"))
IMPERATIVE = re.compile(
    r"^([A-Za-z']+)\s+(?:a|an|the|your|their|its|it|them|these|those|some|one|two|each|every|"
    r"both|all|him|her|me|us|my|out|in|up|down|off|on|away)\b", re.I)


# A verb that hands the person a list of things rather than a job to do: "Take a notebook, a pen,
# your ID and the paperwork they asked for" is the list of things asked for, said as an
# instruction. A step is still a step ("Chop the onions, garlic and ginger" is one job with three
# parts), so only the verbs that introduce things are let through.
THINGS_VERB = re.compile(r"^[^\w]*(?:take|bring|pack|get|buy|grab|carry|put in)\b", re.I)


def _an_instruction(sentence):
    """True when the sentence tells the person to do something that is not fetching things."""
    return bool(_imperative(sentence)) and not bool(THINGS_VERB.match(sentence or ""))


def _imperative(sentence):
    """True when `sentence` is shaped like an instruction: a verb and the thing it acts on."""
    m = IMPERATIVE.match(sentence or "")
    if not m:
        return False
    word = m.group(1).lower().strip("'")
    # "Opening it lets the air out" is a statement about the doing, not an instruction to do it.
    return word not in NOT_A_VERB and not word.endswith("ing")


def _opens_on_a_job(sentence):
    """True when `sentence` is an instruction and not a statement that opens on a verb.

    "Look, it happens" is an aside however the verb list reads it, so an opening that is only the
    verb and then punctuation is not one, and a finite verb within the first few words is the
    sentence's own subject rather than something to act on.
    """
    m = JOB.match(sentence or "")
    if not m:
        return False
    first = re.split(r"[,;:]", (sentence or "")[m.end():], 1)[0]
    words = re.findall(r"[A-Za-z']+", first)[:3]
    if not words:
        return False
    return not any(word.lower() in SAYS_WHAT_IT_DOES for word in words)


def _steps(opening, after=""):
    # A method is one instruction as often as a list, and the verb a person would use is not
    # always on INSTRUCTS: "Find the plasterboard screws instead of hunting for timber" answers
    # "how do i find a stud in a wall" and was read as a reply about something else, because
    # INSTRUCTS is a short list and "find" is not on it. `JOB` is that list plus the everyday
    # verbs, and `_opens_on_a_job` keeps a statement that happens to open on one of them out.
    if (DOES_NOT.match(opening) or DOES.search(opening) or MEANS_OF.search(opening)
            or MEANS_NAMED.match(opening) or _opens_on_a_job(opening)):
        return True
    for part in re.split(r"[:;]", opening)[1:]:
        part = part.strip()
        if part and (INSTRUCTS.match(part) or DOES.search(part) or _imperative(part)):
            return True
    if after and not WANTS_INFO.match(after):
        if INSTRUCTS.match(after) or DOES.search(after) or _imperative(after):
            return True
    return False


# The same verb where the reply starts a new clause: "A dripping tap is nearly always a worn
# washer: turn the water off", "The sun does the fading, so block the light", "If it is still
# worrying you, get it looked at today". A step in a written method starts after a full stop, a
# colon or a comma with "then"/"so"/"and" in front, and often nowhere near the opening.
INSTRUCTS_CLAUSE = re.compile(
    r"(?:^|[.:;!?]\s+|,\s+(?:then|so|and|but|just|or)\s+|,\s+)(?P<verb>be|"
    + INSTRUCTS.pattern.split("(?:", 1)[1], re.I)


def _instruction_after_a_clause(text):
    """True when some clause of `text` after the first starts on a method's verb.

    A clause that asks the person for the information is not one of them: "Tell me what's going
    on", "Say which one you are on" is the person's next move, not a step of the answer.
    """
    for m in INSTRUCTS_CLAUSE.finditer(text):
        if WANTS_INFO.match(text[m.start("verb"):]):
            continue
        if m.start() == 0 and not _opens_on_a_job(text):
            # The opening is not a clause after the first one, and a statement that happens to
            # open on a verb is not a method: "Look, it happens", "Rest is what it needs".
            continue
        return True
    return False


def _steps_in(reply):
    """True when the reply gives a method, read over the whole reply and not only its opening.

    Every other shape is the first sentence, because STYLE.md asks for the answer there and a
    figure three paragraphs down is not the reply the person got. A method is the exception: the
    answer to a how question *is* the sequence, so "A dripping tap is nearly always a worn washer:
    turn the water off at the isolating valve" and "Most veg keeps about a week: keep it in the
    fridge drawer" are a method told over two sentences, and the instruction often starts a later
    clause ("Lower eggs into already boiling water: 6 minutes for a runny yolk"). Reading only the
    opening called 114 of 294 good step replies a miss on the deck. A list of dishes with their
    times ("Quick: tuna pasta in 15, a frittata in 20") is a few ideas, not a method, and is left
    to `_options`.
    """
    text = " ".join(str(reply or "").split())
    if not text:
        return False
    if _steps(first_sentence(text), second_sentence(text)):
        return True
    return _instruction_after_a_clause(text)


# A few ideas is more than one: an "or" between two, a numbered list, or two commas and an "and".
# One idea on its own is a pick if anything, and a card that names one thing has not answered
# "any ideas".
# The second idea named as one: "something else that works is a potato curry", "another one is a
# walk round the block", "the other option is a traybake".
NEXT_IDEA = re.compile(
    r"\b(?:something|anything) else\b|\banother (?:one|option|idea|way|approach|thing)\b"
    r"|\balternatively\b|\botherwise\b|\bthe other (?:option|idea|one)|\boption (?:two|2)\b"
    r"|\bsecond option\b", re.I)
# A colon that hands over a list is a few ideas: "In Rome: the Colosseum, the Pantheon, and
# Trastevere". A plan for one evening is not, and what tells them apart is the order: "a film, a
# walk and a call at 8pm, then tea" is one thing after another, so a sequencing word takes it out.
LIST_AFTER_COLON = re.compile(r":\s*\w[^:]*,\s*\w")
# Two things each named with what it is for, with no "or" and no colon to hand the list over:
# "*The Money To The Masses Podcast* is the plain-English one, *Meaningful Money* for pensions and
# savings, and *Moneybox* for news you can use". Each item carries its own use, which is what makes
# it a list of ideas rather than one idea with a long tail. A method that gives a time for one step
# and another for the next ("simmer for 10 minutes, then the beans for 5") is a sequence, so a
# sequencing word takes it out, the same way it takes out a list after a colon.
FOR_A_LIST = re.compile(r"\bfor\b[^,.;:]{2,70},\s*[^,.;:]{0,70}\bfor\b", re.I)
# A "for" that hands out a length of time belongs to a step, not to a thing's use: "firm it for a
# minute, and water it for ten" is a method with a duration on each step. The same "for" in
# "*Meaningful Money* for pensions" says what the thing is good for.
FOR_A_TIME = re.compile(
    r"\bfor\s+(?:about\s+|around\s+|roughly\s+|just\s+|another\s+|a good\s+|"
    r"at least\s+|up to\s+|half an?\s+)?"
    r"(?:\d+|one|two|three|four|five|six|seven|eight|nine|ten|fifteen|twenty|thirty|forty|"
    r"fifty|sixty|ninety|a|an|each|every)\s*-?\s*"
    r"(?:seconds?|secs?|minutes?|mins?|hours?|hrs?|days?|nights?|weeks?|months?|years?|"
    r"while|bit|moment|spell)\b", re.I)
SEQUENCES = re.compile(r"\b(?:then|after that|afterwards|next|finally|once|first)\b", re.I)


# What a comparison says: one side set against the other. The words are the ones people use for
# it - a contrast ("whereas", "unlike", "but"), both of them at once ("both", "either"), or one side
# judged against the other ("cheaper", "quieter", "lasts longer") - and never a bare "and", which
# joins two things in any reply at all.
CONTRAST = re.compile(
    r"\b(?:whereas|unlike|both|either|but|while|the difference|differs?|compared|comparison|"
    r"on the other hand|the other way|instead|rather than)\b"
    r"|\b(?:cheaper|dearer|quieter|louder|faster|slower|easier|harder|bigger|smaller|"
    r"longer|shorter|better|worse|more|less|stronger|weaker|heavier|lighter)\b"
    r"|\bthan\b", re.I)


def _a_comparison(opening):
    """One side of a pair set against the other, in the reply's own words."""
    return bool(CONTRAST.search(opening))


def _options(opening):
    if re.search(r"\b(?:1\.|1\)|first option|option one|one idea)\b", opening, re.I):
        return True
    # An "or" is the difference between two ideas and the parts of one plan: "a film, a walk and
    # a call at 8pm, then tea" is one evening, and it has no "or".
    if re.search(r"\bor\b", opening, re.I):
        return True
    if ";" in opening:
        return True
    # A second idea handed over as one, and a colon that opens a list: "something else that works
    # is a potato curry", "In Rome: the Colosseum, the Pantheon, and Trastevere". Both are two or
    # more ideas said out loud with no "or" in them.
    if NEXT_IDEA.search(opening):
        return True
    if (FOR_A_LIST.search(opening) and not FOR_A_TIME.search(opening)
            and not SEQUENCES.search(opening)):
        return True
    return bool(LIST_AFTER_COLON.search(opening) and not SEQUENCES.search(opening))


# A reason is a cause in the opening: "because", "that's why", "the reason", "so that", "due to".
CAUSE = re.compile(
    r"\b(?:because|that'?s why|which is why|the reason|reason is|since|so that|due to|"
    r"comes? from|caused by|it happens|the cause|as a result|is down to|thanks to|"
    r"which means|means that|at which|stems? from|leads? to|that'?s what|"
    r"that is what|this is what|is what makes)\b|, so\b"
    # A why-answer names the cause as the thing itself: "Minced meat goes tough and grainy when it
    # is cooked too long", "Brown, crisp tips are usually the water", "the sun lights up the air
    # so brightly that their faint light is drowned out".
    r"|\b(?:goes?|gets?|turns?|becomes?|comes? out|feels?)\b.{0,40}\b(?:when|if|because)\b"
    r"|\b(?:is|are) (?:usually|often|nearly always|mostly|generally|really|just) the\b"
    r"|\bso\b.{0,40}\bthat\b"
    # A cause can be named as the thing itself rather than by a joining word: "The colour is the
    # soil rather than the plant", "The green ring is iron from the yolk meeting sulphur ...,
    # which happens when an egg is cooked too long".
    r"|\b(?:is|are|was|were) (?:the|a|an) .{0,50}\b(?:rather than|not)\b"
    r"|\b(?:which |that )?happens? (?:when|if|because)\b"
    # and the cause named as the occasion with the emphasis on it: "That is normal, especially in
    # the first few days or when something new has arrived" answers why a cat hides and was read
    # as no answer. Only the emphasis: a plain "or when you get home" is a method, not the cause.
    r"|\b(?:especially|particularly) (?:when|if|in)\b"

    # The cause named as the process the effect went through, set against what it was not:
    # "Soggy roast potatoes were steamed rather than roasted".
    r"|\b(?:is|are|was|were)\s+\w+ed\s+rather than\b"
    # A change of state named as the effect, and what brings it on: "Food sticks when there is not
    # enough heat or fat", "Wifi fades with distance".
    r"|\b(?:sticks?|stuck|smells?|smelt|tastes?|fades?|squeaks?|clicks?|wobbles?|sags?|leaks?|"
    r"cracks?|burns?|turns?|goes?|gets?|comes? out|feels?|looks?|sounds?|happens?|builds? up|"
    r"collects?|gathers?|settles?|clings?|pools?|spreads?|grows?|stops?|dies?|fails?|drops?|"
    r"floats?|sinks?|rises?|falls?|heats?|cools?|shrinks?|expands?|swells?|warps?|splits?|"
    r"melts?|freezes?|curdles?|separates?|wears?|rots?|wilts?|droops?|curls?)\b"
    r".{0,25}\b(?:when|if|because|with|from)\b"
    # A cause named by its condition needs no joining word at all: "Dense bread is usually
    # under-proved or over-kneaded", "a starter that has stopped rising is usually hungry, cold
    # or both", "the reason is too much water" - the condition itself is the cause.
    r"|\b(?:is|are|was|were|has|have|had)\s+(?:usually|often|normally|mostly|generally|probably|"
    r"most likely|nearly always|just|really|only|simply)?\s*(?:(?:under|over|un)\w+|"
    r"\btoo\b|\bnot\b)\s*\w*\b"
    # "A doughy loaf has not had long enough in the oven, or it did not prove enough": a shortfall
    # said as a plain statement is the cause.
    r"|\b(?:has|have|had|did|does|do|is|are|was|were)\s+not\s+\w+\s+(?:long\s+)?enough\b"
    # A cause told after a comma: "A loaf that collapses rose and then fell back, which is a prove
    # that ran too long".
    r"|,\s*which\s+(?:is|was|means)\b"
    # The cause said as a list of conditions: "is usually hungry, cold or both".
    r"|\b(?:is|are|was|were)\s+(?:\w+\s+)?\w+\s*,\s*\w+\s+or\s+(?:both|so|else)\b"
    # A comparison names the cause by naming what it is not: "most constant tiredness is dull
    # rather than medical", "a musty smell is usually damp rather than dirt".
    r"|\b(?:is|are|was|were)\b[^.;:!?]{0,40}\brather than\b"
    # The cause named as the thing itself, with the ground after it: "Cloudy tea is the minerals
    # in hard water binding with the tannin", "An allergy is the immune system mistaking something
    # harmless for a threat". A noun phrase with a participle on the back of it is the mechanism.
    # The participle has to be the noun's, not an infinitive that happens to end in "-ing":
    # "It is a good idea to ring them first" is advice, and "ring" is not the mechanism.
    r"|\b(?:is|are|was|were)\s+(?:the|a|an)\s+\w+(?:\s+\w+){0,4}\s+(?:(?<!to )\w+ing|\w+ed)\b"
    # "Stale bread is dry, not spoilt", "most of it is habit, not hunger": a condition set beside
    # the one it is not.
    r"|\b(?:is|are|was|were)\s+(?:\w+ly\s+)?\w+\s*,\s*not\b"
    # A cause told as what the thing does to something else: "The Moon's gravity pulls the sea
    # towards it, making a bulge on the near side", "a food - for a threat and releasing
    # histamine, which causes the itch". A participle or a which-clause after a comma is the
    # effect that explains it.
    r"|,\s*(?:making|leaving|causing|giving|sending|turning|setting|which\s+(?:makes|causes|leaves|gives))\b"
    r"|\b(?:which|that)\s+causes?\b"
    # A reason handed over as a numbered set: "Three things keep a fried coating crisp: a dry
    # surface, oil that is hot enough, and air under it". The set has to be named - a word follows
    # the count - because "Two things:" on its own is a label, and what is behind the colon is the
    # method ("Two things: grind it coarser and use cooler water"), which `_head_explains` reads.
    r"|\b(?:one|two|three|four|five|\d+)\s+(?:things|reasons|causes|factors|suspects)\s+\w"
    # Two causes offered side by side name the cause without a joining word: "One channel going
    # funny is the aerial or the box, and every channel is the set".
    r"|\b(?:is|are|was|were)\s+(?:the|a|an)\s+\w+(?:\s+\w+)?\s+or\s+(?:the|a|an)\b"
    # A condition stated flatly after the verb, with the ground after a dash: "Waking in the night
    # is normal - sleep runs in cycles of about ninety minutes".
    r"|\b(?:is|are|was|were)\s+(?:\w+\s+)?\w+\s+[-\u2013\u2014]\s+\w"
    # Two causes beside each other name the cause with no joining word at all: "A suddenly louder
    # exhaust is nearly always a hole or a blown joint", "A smell from a kettle is nearly always
    # scale or water left standing in it".
    r"|\b(?:is|are|was|were)\s+(?:nearly always|usually|often|mostly|always|almost always)?\s*"
    r"(?:the|a|an)?\s*\w+(?:\s+\w+){0,2}\s+or\s+(?:the|a|an)\b"
    # The cause named as what it is instead of, or what it points at: "They take oxygen out of the
    # water instead of the air", "the best evidence points at flies and heat".
    r"|\binstead of\b|\bpoints? (?:at|to)\b"
    # The mechanism named as what the thing is doing, and what it is doing it from: "A cactus that
    # has gone soft is rotting from too much water".
    r"|\b\w+ing\s+(?:from|off|through)\b|\bfrom\s+(?:too|not|lack of|a lack)\b", re.I)


# The commonest why-answer names the cause as what the effect *is*, with no connective at all:
# "The smell is a film of food and bacteria in the overflow", "Lumps are flour that met hot liquid
# without being spread through fat", "A whirr with no cranking is the starter turning". The cause is
# a thing, so the rule asks for a copula and then a word that ties the thing to the effect ("a film
# of", "flour that", "the starter turning", "water at the roots"), three words of slack for "the
# slow build-up of".
#
# This one is read with the line, not the reply alone: on its own it credits a sentence that shares
# nothing with the question ("A whirr with no cranking is the starter turning" is not the cause of a
# sore throat), so the opening has to name a thing the line named. A preposition on the far side of
# a comparison is the other side of it, not the cause: "once it is cooler outside than in" is not a
# why-answer either.
CAUSE_IS = re.compile(
    r"\b(?:is|are|was|were)\s+(?:usually\s+|often\s+|mostly\s+|nearly always\s+|generally\s+)?"
    r"(?:(?:a|an|the)\s+)?[a-z][a-z-]*(?:\s+[a-z][a-z-]*){0,3}\s+"
    r"(?:of|that|which|from|turning|sitting|going|coming|leaving|building|"
    r"(?<!than )(?<!more )(?<!less )\b(?:in|on|at|under))\b", re.I)


# A cause is also told as a plain statement about the thing, with the condition after the verb:
# "A cake sinks when it's underbaked", "The sauce splits if it boils", "Bread goes stale when it is
# kept cold". The verb is any finite one, and the words after the "when" are the cause.
CAUSE_WHEN = re.compile(
    r"\b(?:\w+s|\w+ed|is|are|was|were|gets?|got|goes|go|came|comes)\b\s+(?:when|if|because)\b",
    re.I)

# The point of a thing said as its purpose: "the point of it is to pull the water out of the air",
# "its job is to keep the damp down", "the purpose is to keep the noise in". A purpose is the
# reason a thing is done, and it holds no cause word at all.
PURPOSE = re.compile(
    r"\bthe point of (?:it |them |this |that )?(?:is|was)\b"
    r"|\b(?:its|their|his|her) (?:job|point|purpose|use) is\b"
    r"|\bthe (?:point|purpose|job|use) is (?:to|that)\b", re.I)
# The purpose said as the opening clause of the reply: "To be useful with the ordinary things",
# "For keeping the damp down in a cellar". An instruction opens on a verb and is not this.
PURPOSE_TO = re.compile(r"^(?:it is |its |the )?(?:to|for) [a-z]+", re.I)
# Whether a thing is worth its cost or its trouble, said as the merit of it: "worth it if the roof
# faces south", "worth having in any home", "usually yes - spaying cuts the risk".
MERIT = re.compile(
    r"\bworth it\b|\bworth having\b|\bworth doing\b|\bworthwhile\b|\bworth the\b"
    r"|\b(?:usually|generally|probably|mostly) (?:yes|no|worth)\b"
    r"|\b(?:yes|no)\b[^.!?]{0,40}\b(?:if|when|unless|for|in a|as long as)\b", re.I)


def _a_reason(opening, line=None):
    if CAUSE.search(opening):
        return True
    # A purpose answers the point of a thing and a merit answers whether it is worth it: neither
    # carries a cause word, and a description of the thing carries neither.
    if PURPOSE.search(opening) or PURPOSE_TO.match(opening) or MERIT.search(opening):
        return True
    # A method that names its moment in a "when" is not a cause: "Take it out when the timer goes",
    # "Add the eggs when the water boils". The instruction at the *front* is what tells them apart -
    # not a method further in, because a why-answer often gives the cause and the remedy after it:
    # "A creamy soup curdles when it gets too hot: keep it under a simmer and stir the cream in off
    # the heat". The cause is in the first clause and the remedy does not take it away.
    if INSTRUCTS.match(opening) or DOES_NOT.match(opening):
        return False
    # A head that sends the person on names no cause: "A headache that has gone on for three days
    # or more is one to have looked at: book a GP appointment" is an identification of the thing,
    # and the cause is never said. The same guard already stands on the head before a colon.
    if SENDS_THEM_ON.search(opening):
        return False
    if CAUSE_WHEN.search(opening):
        return True
    # The effect-is-the-cause form is the one that needs the line: without something named in both
    # it is a sentence about anything. Without a line to compare with, the shape is all there is.
    return bool(CAUSE_IS.search(opening)) and (line is None or _names(opening, line))


# The head of a reply before its colon, when that head is a statement rather than a label. A
# cause said as an identification - "<symptom> is <cause>" - is the shape of most why-answers,
# and the fix behind the colon is not a different answer to the same question.
EXPLAINS = re.compile(
    r"\b(?:is|are|was|were|means?|comes? from|happens? (?:when|if|because)|because|"
    r"the reason)\b", re.I)


# "<thing> is one to have looked at" is an "is" and not a cause. The head of a why-answer that
# sends the person on ("A headache that has gone on for three days or more is one to have looked
# at: book a GP appointment") reads as an identification of the thing, and the cause is never
# said, so it is not a reason.
SENDS_THEM_ON = re.compile(
    r"\b(?:one|something|a thing|the kind of thing)\s+(?:to have|to get|to see|to|worth)\b|"
    r"\b(?:book|ring|call|see|visit)\s+(?:a|the|your)\s+(?:gp|doctor|vet|dentist|nurse)\b|"
    r"\bappointment\b|\blooked at\b|\bchecked out\b", re.I)


def _head_explains(opening):
    """True when what comes before the colon states the cause, so a method after it is the fix."""
    head = opening.split(":", 1)
    if len(head) < 2:
        return False
    if SENDS_THEM_ON.search(head[0]):
        return False
    return bool(EXPLAINS.search(head[0])) and not _imperative(head[0])


# The readings strong enough to fail a reply for. A duration or a figure, a method, a named kind
# of place, a role, a definition, a verdict frame and a named side are what a reply is *about*,
# so one of them in a reply to a different question is a fault the check can name. The weaker
# readings that pass a reply - a capital after a preposition, a name in the middle of a
# sentence, a "fine" inside the sentence, a bare noun - are left out: "Rome." passes as a place
# and is not evidence that a reply to a how-long question is about a place.
#
# The distinction is not cosmetic. Every widening of a reading makes replies pass, and a wide
# reading used as evidence makes good replies fail: `<thing> is <description>` passes as a
# definition ("On an iPhone it is Settings > Mobile Data..."), but as evidence it failed the
# steps reply that says it, and a why-answer ("The green ring is iron from the yolk..."), and a
# yes/no ("Apples are picked ripe and keep, so judge by feel"). So `_CLEAR` keeps the narrow
# reading of the shape and the checks keep the wide one - the same asymmetry as `_FIGURES`.
_CLEAR = (
    (TIME, _a_clear_time_at_the_head),
    (AMOUNT, _an_amount_at_the_head),
    (STEPS, _steps),
    (PLACE, lambda opening: bool(PLACE_WORD.search(opening))),
    (PERSON, lambda opening: bool(PERSON_WORD.search(opening))),
    (MEANING, lambda opening: bool(MEANS.search(opening))),
    (YESNO, lambda opening: bool(VERDICT_OPEN.match(opening))),
    (PICK, lambda opening: bool(PREFERS.search(opening))),
)
# A method opens with its own figure as often as not - "About 50 minutes start to finish. Cook a
# sliced aubergine...", "Lower eggs into boiling water: 6 minutes for a runny yolk" - so a
# duration or a figure says nothing about whether a steps reply is a method. The other way round
# it does: a how-long answered with a method and no figure at all has not given the time.
_FIGURES = frozenset((TIME, AMOUNT))

_CHECKS = {
    TIME: _a_time,
    COMPARE: _a_comparison,
    AMOUNT: _an_amount,
    PLACE: _a_place,
    PERSON: _a_person,
    MEANING: _a_meaning,
    YESNO: _a_yesno,
    PICK: _a_pick,
    STEPS: _steps,
    OPTIONS: _options,
    REASON: _a_reason,
}


def fits(reply, want, line=None):
    """`gives` under the name the lane plan used, for callers that read it that way."""
    return gives(reply, want, line)

# ------------------------------------------------------------------ the readings that need the line
#
# The reply's own words settle most shapes. A few do not, and are read from the question as well
# when `gives` is passed the line: a yes/no answered by doing the job, and a pick that names one
# of two sides. The helpers here take the line as plain text - lower case, one space.

# Words that are in every line and name nothing, so a match on one is not the reply naming the
# thing the person asked about.
_EMPTY = frozenset((
    "about", "after", "again", "before", "being", "could", "doing", "first", "going", "have",
    "just", "like", "make", "much", "need", "only", "really", "should", "still", "than", "that",
    "their", "them", "then", "there", "these", "they", "thing", "this", "those", "want", "what",
    "when", "where", "which", "while", "will", "with", "would", "your", "yours", "from", "into",
))
# A line that asks leave, or asks what it needs to do, is answered by the doing.
PERMISSION = re.compile(
    r"\b(?:can|could|should|shall|may|do|does|did|is it|are they|am i) (?:i|we|you|it|they|my|"
    r"i have to|i need to|we need to)\b|\bdo i need\b|\bis it ok\b|\bis it safe\b|"
    r"\bam i allowed\b|\bi (?:should|must|need to|have to)\b", re.I)
# The same verbs as INSTRUCTS, anywhere in the opening: a reply can put two words in front of the
# verb, or say the job as a purpose first ("To double a recipe double every weight").
JOB_ANY = re.compile(INSTRUCTS.pattern.replace("^(?:", "(?:", 1).replace(
    r")\b", r"|double|halve|split|scale|reheat|refreeze)\b"), re.I)
# The two sides of "a fiesta or a focus": the words either side of the "or", which is the whole of
# what the line offers to choose between.
# A side can be a number: "is 15 or 20 a factor of 30" offers two of them, and a token with a
# digit is a name however short - the same rule the two sides of a comparison are read by.
SIDES = re.compile(r"([a-z0-9']+(?: [a-z0-9']+)?) or ([a-z0-9']+(?: [a-z0-9']+)?)", re.I)
# The same pair said as a comparison rather than a choice: "is porridge better than cereal",
# "would a rescue be better than a puppy". A side is up to three words either side of it.
COMPARATIVE_THAN = re.compile(
    r"([^?.!,;:]{1,40}?)\s+(?:much |a bit |a lot |far |way |any |still )?"
    # The comparative is followed by "than" itself ("cheaper than the oven") or by what it is
    # spent on first ("cheaper to run than a heat pump one", "better value than breasts"), which
    # is how most people say it: two words at most, so a line that merely has an "-er" word and a
    # "than" somewhere later is not read as a pair.
    r"(?:\b(?!rather\b|other\b|fewer\b)\w+er\b|more \w+|less \w+|worse)"
    r"((?:\s+(?!than\b)(?!(?:\w+er|more|less|worse)\b)\w+){0,2})\s+than\b\s*"
    r"([^?.!,;:]{1,40})", re.I)
# "dried beans vs tinned": the same pair with the comparison word between them.
SIDES_VS = re.compile(r"([a-z']+(?: [a-z']+)?)\s+vs\.?\s+([a-z']+(?: [a-z']+)?)", re.I)
# The words that leave a side when the run in front of "better than" is trimmed back: "is a fixed
# rate better than variable" leaves "a fixed rate", and the side is "fixed rate".
SIDE_FILLER = frozenset((
    "a", "an", "the", "is", "are", "was", "were", "would", "will", "do", "does", "did", "which",
    "what", "and", "or", "but", "so", "then", "that", "this", "these", "those", "it", "its",
    "your", "my", "our", "their", "his", "her", "me", "us", "them", "be", "being", "been", "get",
    "gets", "got", "buy", "buying", "have", "has", "had", "should", "shall", "could", "can"))
# What the reply says when it has picked one of the two: the side is better, it wins, take it, or
# it is the one for the person. A reply that says neither of these has not answered the question.
A_SIDE_WINS = re.compile(
    r"\b(?:is|are|was|were) (?:still |usually |often |much |far |a bit )?(?:the )?(?:better|best|"
    r"kinder|healthier|cheaper|safer|stronger|quicker|smarter|more useful)\b"
    r"|\bthe (?:better|best|kinder|healthier|cheaper|safer|stronger|quicker|smarter|easier) "
    r"(?:choice|buy|option|bet|value|start|one|bowl|loaf|plan|pick|of the two)\b"
    r"|\b(?:wins?|won)\b"
    r"|\b(?:take|get|go for|pick|choose|buy|stick with) (?:the|a|an) \w+"
    r"|\bnothing (?:[a-z]+ ){0,4}comes close\b|\bcomes? close\b"
    r"|\bif you (?:want|need|have|are)\b"
    # "Gas is much the cheapest for heat", "A cat, on that one", "the full race is exactly twice as
    # far": the choice said with an intensifier, answered elliptically, or left as the ratio.
    r"|\b(?:much|far|by far|a lot|still|easily) the (?:better|best|cheapest|healthiest|easiest)\b"
    r"|\bon (?:that|this) one\b|\btwice (?:as|the)\b|\bhalf the (?:price|cost|time|weight|size)\b"
    # "A half marathon is 13.1 miles, which is further than a 10k at 6.2 miles": the reply says the
    # comparison itself, between the two sides the line named.
    r"|\b(?:is|are|was|were) (?:much |far )?(?:further|longer|bigger|heavier|lighter|warmer|"
    r"colder|stronger|quicker|faster|cheaper|worse|better) than\b"
    r"|\bthe one (?:to|that|for|I would|id)\b"
    r"|^both\b|\bboth, and\b", re.I)


def _line_text(line):
    """The line as plain text: lower case, one space, curly apostrophes straightened."""
    return " ".join(str(line or "").lower().replace("\u2019", "'").split())


def _words(text):
    return re.findall(r"[a-z']+", str(text or "").lower().replace("\u2019", "'"))


# The subject of a definition ask: "what is a student loan", "what does a food bank do", "whats a
# standing charge". What follows is cut at the first word that starts a new clause, because the
# thing asked about is the head of the line ("what is a student loan and do i pay it back" asks
# about the student loan).
THE_THING_ASKED = re.compile(
    r"^(?:what'?s|what is|what are|what was|what were|what does|what do|what did|"
    r"tell me about|what about)\s+(?:a|an|the)?\s*(.+)$", re.I)
# Words that end the subject: a new clause, a preposition, or the verb the ask put on it.
_ENDS_THE_THING = frozenset("""
    and or but for in on at to with of from about when while if that which who whom whose how
    why where do does did is are was were be been being mean means meant cost costs worth
    make makes made need needs want wants go goes get gets come comes work works help helps
    take takes give gives happen happens feel feels look looks sound sounds include includes
    cover covers contain contains show shows sit sits stand stands say says called call
""".split())
_ARTICLE = re.compile(r"^(?:a|an|the|your|my|his|her|their|our|its|this|that|these|those|"
                      r"any|some)\s+", re.I)


def _the_thing_asked(said):
    """The thing a definition ask is about, as the words the reply would open on: "student loan"
    for "what is a student loan and do i pay it back"."""
    match = THE_THING_ASKED.match(said or "")
    if not match:
        return ""
    words = []
    for word in re.findall(r"[a-z0-9']+", match.group(1).lower().replace("\u2019", "'")):
        if word in _ENDS_THE_THING or word in _EMPTY:
            break
        words.append(word)
        if len(words) == 3:
            break
    # A subject of one short word ("what is a p60", "what is vat") is still a subject.
    if not words or max(len(w) for w in words) < 2:
        return ""
    return " ".join(words)


# A judgement about the thing is a verdict, not what the thing is: "what is porridge" / "Porridge
# is good for you first thing" has not said what porridge is, and the reading below must not pass
# it for a definition just because it opens on the subject.
_JUDGES_THE_THING = re.compile(
    r"^(?:is|are|was|were|should|must|ought|needs?)?\s*(?:be\s+)?(?:not\s+)?(?:good|bad|great|"
    r"fine|okay|ok|"
    r"safe|worth|better|worse|best|worst|useless|rubbish|lovely|nice|amazing|brilliant|terrible|"
    r"awful|really|usually|often|always|never|definitely|probably|a (?:good|bad|great|waste|rip|"
    r"must)|the (?:best|worst|only)|your|a waste|the wrong)\b", re.I)
# Advice about the thing is not what the thing is: "A student loan must be paid back before
# anything else" has said what to do with it, not what it is.
_ADVISES_THE_THING = re.compile(r"^(?:should|must|ought|needs? to|need to)\b", re.I)
# A subject of one short word is a word that starts other things: "what is a gas" / "A gas boiler
# needs servicing once a year" is about a boiler, not about gas. The one-word subject is read
# only when the reply goes straight on to the copula or to a verb that says what the thing does.
_SAYS_WHAT_IT_IS = re.compile(
    r"^(?:is|are|was|were|has|have|had|can|cannot|do|does|did|give|gives|provide|provides|let|"
    r"lets|allow|allows|help|helps|mean|means|refers|comes|runs|works|starts|ends|takes|costs|"
    r"keeps|contains|restarts|pays|holds|covers|makes|sits|stands|forms|happens|moves|lubricates|"
    r"carries|spreads|turns|shows|includes|protects|needs)\b", re.I)


def _defines_the_thing(opening, said):
    """True when the reply opens on the thing the line asked about and then says what it is or
    does: "what is a student loan" / "A student loan pays the tuition fee and the maintenance
    money while you study". The verb is the reply's own - `MEANS_BY_DOING` knows `give` and
    `provide`, and this reads the rest - so what matters is that the subject comes first and
    something is said about it, not the words it is said with."""
    thing = _the_thing_asked(said)
    if not thing:
        return False
    head = _ARTICLE.sub("", opening.strip()).lower()
    if not head.startswith(thing + " ") and not head.startswith(thing + "'"):
        return False
    # The space after the subject is stripped before the guard reads it, or " is good value"
    # never matches a pattern that starts on the word itself.
    rest = head[len(thing):].strip()
    if _JUDGES_THE_THING.match(rest) or _ADVISES_THE_THING.match(rest):
        return False
    # A one-word subject is read only when the reply goes straight on to the copula or to a verb
    # that says what the thing does ("A gas has no fixed shape", "A p60 is the summary"); "A gas
    # boiler needs servicing" is about a boiler, however much it starts with the word.
    if " " not in thing and not _SAYS_WHAT_IT_IS.match(rest):
        return False
    return len(rest.split()) >= 3


def _name_words(text):
    """The words of a line or a reply as names, digits and all: `_words` drops "15", "4g" and "b12"
    with every other figure, and a figure can be one of the two things a line offers."""
    return re.findall(r"[a-z0-9']+", str(text or "").lower().replace("\u2019", "'"))


def _long_enough_a_name(word, least=3):
    """A token with a digit is a name however short: "4g", "5g", "15", "dmp" and "b12" all name
    something, where a short word of letters alone is more likely "it", "or" or "my"."""
    return len(word) >= least or any(ch.isdigit() for ch in word)


def _names(opening, said):
    """True when the reply's opening names a thing the line named, by stem: bread / breads,
    freeze / freezing. A word from the line that is not in `_EMPTY` and is long enough to mean
    something."""
    reply = set(_words(opening))
    for word in set(_words(said)):
        if not _long_enough_a_name(word, 4) or word in _EMPTY:
            continue
        if word in reply or word[:-1] in reply or word[:-2] in reply:
            return True
    return False


def _opens_on_the_lines_verb(opening, said):
    """True for a short opening that is the verb a decision in the line named, and nothing else:
    "should i bin it" / "Bin it." or "does that mean i should bin it" / "Bin it, I'm afraid."."""
    words = opening.split()
    if not words or len(words) > 5:
        return False
    first = _words(opening)
    if not first or len(first[0]) < 3:
        return False
    stem = first[0]
    for match in re.finditer(r"\b(?:should|must|need to|have to)\b\s+(?:i\s+)?([a-z]{3,})",
                             said, re.I):
        verb = match.group(1).lower()
        if verb == stem or (verb.startswith(stem[:-1]) and len(stem) > 3):
            return True
    return False


def _trimmed(words):
    """The words of a side without the filler at either end."""
    start, end = 0, len(words)
    while start < end and words[start] in SIDE_FILLER:
        start += 1
    while end > start and words[end - 1] in SIDE_FILLER:
        end -= 1
    return words[start:end]


def _the_pair_up(text):
    """The two things a line puts up to weigh against each other, or None.

    Three ways people ask it: "is wholemeal better than white" and "does a deep bath use more
    water than a shower" (a comparative and "than"), "dried beans or tinned, which is the better
    value" and "which is better, the train or the coach" (an "or"), "dried beans vs tinned".
    """
    clean = " ".join(str(text or "").split())
    found = COMPARATIVE_THAN.search(clean)
    if found:
        # The words a side may not be: an article, a "have", a "is". They are taken off both ends,
        # because the comparative can stand a couple of words away from "than" ("cheaper to run
        # than") and the words either side of that gap are not part of the thing named - "my
        # payslip has less on it than last month" puts no pair up at all.
        left = _trimmed(_words(found.group(1)))
        right = _trimmed(_words(found.group(3)))
        # What the comparative is spent on ("to run", "value") sits between it and "than", and it
        # is not part of the thing named: "does a deep bath use more water than a shower" puts the
        # bath and the shower up, not the bath and "use".
        spent = set(_words(found.group(2)))
        while left and left[-1] in spent:
            left = left[:-1]
        if not left or not right:
            return None
        return (left[-2:], right[:2])
    found = SIDES.search(clean) or SIDES_VS.search(clean)
    if found:
        return (_words(found.group(1)), _words(found.group(2)))
    return None


def _a_side_said_in_the_reply(side, words):
    """True when the reply's words hold one of the side's own words, by stem: "Showering" is the
    shower, "wholemeal" is not the brown bread the line named.

    A different question from the one below, which asks about one word of a side. The two shared
    a name once, so Python kept the later one and this caller got its arguments read the other way
    about and a `TypeError` for the missing third - see tests/test_no_helper_is_defined_twice.py.
    """
    for word in side:
        if not _long_enough_a_name(word, 4) or word in _EMPTY:
            continue
        if word in words or word + "s" in words or word[:-1] in words:
            return True
    return False


def _the_side_wins(opening, line):
    """True when the line weighed two things up and the reply opened on one of them.

    "is a bath better than a shower" / "Showering wins on time and water" is a yes with a reason,
    and so is "is a plank better than a sit up" / "Both, and they do different jobs". The reply
    has to name one of the two sides and say one of the things a choice says, so a reply that
    describes the pair without choosing stays the "words cannot tell" it was.
    """
    pair = _the_pair_up(_line_text(line))
    if not pair:
        return False
    sides = [side for side in pair if side]
    if not sides:
        return False
    words = set(_words(opening))
    named = any(_a_side_said_in_the_reply(side, words) for side in sides)
    # "Both, and they do different jobs: ..." weighs the pair itself, and that is a verdict too.
    if not (named or re.match(r"^both\b", opening, re.I)):
        return False
    return bool(A_SIDE_WINS.search(opening))


def _names_a_side(opening, said):
    """A pick of one of two named sides, without the words a pick normally uses: the line says
    "a fiesta or a focus" and the reply opens on the fiesta. Only the words either side of the
    "or" are the sides, so the rest of the line is not mistaken for one."""
    sides = SIDES.search(said or "")
    if not sides:
        return False
    # The side has to be what the reply opens on: "A dog needs two walks a day" picks the dog; a
    # paragraph that mentions the boiler later has not picked anything.
    reply = _name_words(opening)[:3]
    for side in sides.groups():
        for word in _name_words(side):
            if not _long_enough_a_name(word) or word in _EMPTY:
                continue
            if word in reply:
                return True
    return False


# The words that are in every line and name nothing: a side is never counted on one of these, so a
# side such as "will" in "the difference between a will and probate" is counted on its own name.
_SIDE_EMPTY = frozenset((
    "the", "and", "but", "not", "for", "with", "your", "you", "our", "its", "it's", "this", "that",
    "these", "those", "what", "which", "from", "into", "than", "then", "are", "was", "were", "has",
    "have", "had", "one", "two", "any", "all", "much", "more", "less", "same",
))


def _a_side_word_is_named(word, ordered, words):
    """True when this one word of a side is said in the reply.

    The same thing is said in the line and in the reply in different shapes, so the match allows
    for the plural (seat/seats), for a verb the reply gives as its stem ("simmering" in the line,
    "a simmer" in the reply, and the other way about), and for a compound the reply spaces out
    ("hayfever" in the line, "hay fever" in the reply). A short name the reply never says, such as
    "dmp", is matched by its initials instead.
    """
    for reply_word in words:
        if reply_word == word:
            return True
        shorter, longer = sorted((reply_word, word), key=len)
        if len(longer) > 4 and longer.startswith(shorter) and shorter[-1:] not in ("s",):
            return True
        if len(shorter) >= 3 and shorter.rstrip("s") == longer.rstrip("s"):
            # The plural either way round: "cats" in the line is "a cat" in the reply.
            return True
    for index in range(len(ordered) - 1):
        if ordered[index] + ordered[index + 1] == word:
            return True
    return _initials_named(word, ordered)


def _initials_named(word, reply_words):
    """A short name spelled out by the reply: "dmp" as "debt management plan", "iva" as "individual
    voluntary arrangement". An acronym is a name the reply may only ever say in full."""
    if not 2 <= len(word) <= 4 or not word.isalpha():
        return False
    for start in range(len(reply_words)):
        pos = 0
        for spoken in reply_words[start:start + len(word)]:
            if pos < len(word) and spoken[:1] == word[pos]:
                pos += 1
        if pos == len(word):
            return True
    return False


def _names_both_sides(reply, said):
    """True when both of the two things the line put together are in the reply, False when one of
    them is missing, None when the missing one is too short to look for.

    The pair is read the way the line words it - "the difference between X and Y", "X vs Y",
    "compare X and Y", "X apart from Y", "X cheaper than Y" - and a side counts when any of its own
    words of three letters or more is in the reply, allowing for the plural (ssd/ssds,
    seater/seats) or for a short name the reply spells out (dmp/debt management plan). The whole
    reply is read rather than the opening, because a comparison is two-part by nature: "An SSD has
    no moving parts ... a hard drive is a spinning disc" is both sides, one in each clause.

    A reply that names one of the two and never the other has answered half the question, but a
    three-letter name is not evidence of anything: "hdd" may be "a hard drive" in the reply, so
    nothing is claimed against the reply on a short name alone.
    """
    said = (said or "").lower().replace("\u2019", "'")
    sides = None
    for pattern in SIDE_PAIRS:
        sides = pattern.search(said)
        if sides:
            break
    # The pair as word lists. A comparative the patterns above do not word ("are cats easier than
    # dogs", "does a deep bath use more water than a shower") is read by the same pair reader that
    # calls the line a comparison in the first place, so every form the reading knows as two
    # things up can be answered here as well - one reader for the reading and for the check.
    pairs = [sides.groups()[:2]] if sides else []
    if not pairs:
        pair = _the_pair_up(said)
        if pair and all(pair):
            pairs = [[" ".join(side) for side in pair]]
    if not pairs:
        # No pair the line words as two things: the reply is not held against anything here.
        return None
    ordered = _words(reply)
    words = set(ordered)
    named, missing = 0, []
    for side in pairs[0]:
        side_words = {word for word in _words(side)
                      if len(word) >= 3 and word not in _SIDE_EMPTY}
        if not side_words:
            continue
        if any(_a_side_word_is_named(word, ordered, words) for word in side_words):
            named += 1
        else:
            missing.append(min(side_words, key=len))
    if named + len(missing) < 2:
        return None
    if named >= 2:
        return True
    if any(len(word) <= 3 for word in missing):
        return None
    return False


def _the_job_named(opening, said):
    """The job the line asked leave for, in a reply whose first word is not one of the verbs the
    cue list knows. Every part is needed: the line asks leave, the reply opens on a job, and the
    reply names the thing the line named. The verb alone answers a question about something else,
    and the name alone is a paragraph that happens to mention it."""
    if not PERMISSION.search(said or ""):
        return False
    if not _names(opening, said):
        # "does that mean i should bin it" / "Bin it, I'm afraid." - the verb is three letters,
        # so the name rule cannot see it, but the line named the verb and the reply opens on it.
        return _opens_on_the_lines_verb(opening, said)
    if _steps(opening):
        return True
    if JOB_ANY.search(" ".join(opening.split()[:12])):
        return True
    # The reply's own first word is the line's verb: "do i need to strap my toddler in" /
    # "Strap them in every time". Short only, because a long paragraph that opens on a word of
    # the line is not an answer by doing.
    if len(opening.split()) > 9:
        return False
    first = _words(opening)
    if not first or len(first[0]) < 4:
        return False
    stem = first[0]
    for word in _words(said):
        if len(word) >= 4 and (word == stem or word.startswith(stem) or stem.startswith(word)):
            return True
    return False

# A method told as a path through a menu: "Windows: Settings > Apps > Installed apps, find it in the
# list and choose Uninstall". The line opens on the path, so no verb list can see it, and it was a
# clear miss on "how do i set my phone to dark mode". One reading: an arrow and, in the same
# sentence, one of the verbs that says what to do when you get there.
PATH_THEN_VERB = re.compile(
    r"(?:>|\u2192|->)\s*\S.{0,120}\b(?:find|choose|select|click|tap|press|open|set|switch|turn|"
    r"tick|untick|check|uncheck|change|remove|delete|add|enable|disable|toggle)\b", re.I)


# The garden and the toolbox: "Sow peas from March to early June, 5cm deep in a wide flat trench"
# and "Prune the roses in late winter, just as the buds start to swell" are methods with no article
# after the verb, so `INSTRUCTS` does not know them. They are read by the method checks alone and
# not added to `INSTRUCTS` itself, because `JOB` - which is `INSTRUCTS` plus the everyday verbs -
# answers a yes/no that opens on any job, and an answer about sowing is not a yes to "is a pension
# better than a savings account": on 2,240 mismatched pairs the wider list invented three.
GARDEN = re.compile(
    r"(?:sow|plant|prune|dig|mow|scarify|weed|mulch|repot|stake|harvest|deadhead|sprinkle|hammer|"
    r"grout|caulk|unblock|unplug)\b", re.I)


# The two openings above are read at the end of the file, and the method check is extended rather
# than edited, so that this change adds lines to `fit.py` instead of rewriting it: the world's
# copy of main moves under every open PR, and an edit lands as a conflict where an addition does
# not. Python resolves both names at call time, so nothing here depends on the order.
_STEPS_IN = _steps_in


def _steps_in(reply):
    """`_steps_in`, and the two methods a verb list cannot see.

    "Sow peas from March to early June, 5cm deep in a wide flat trench" and "Prune the roses in
    late winter, just as the buds start to swell" have no article after the verb, so `INSTRUCTS`
    does not know them; "Windows: Settings > Apps > Installed apps, find it in the list and choose
    Uninstall" opens on a path. All three are methods, and each was a clear miss on a real turn.
    """
    if _STEPS_IN(reply):
        return True
    text = " ".join(str(reply or "").split())
    for sentence in re.split(r"(?<=[.!?])\s+", text):
        if GARDEN.match(sentence) or PATH_THEN_VERB.search(sentence):
            return True
    return False

# A rate: money and a time unit with "a", "an", "per" or "each" between them. "7p an hour",
# "£12 an hour", "$20 per hour", "30p a day" all answer how much, not how long - a budget for a
# car that says "£2,000-£3,000 a year" was read as an answer to "how long does it keep".
_MONEY = (r"(?:[£$€]\s*\d[\d,.]*"
          r"|\b\d[\d,.]*\s*(?:p|pence|pennies|quid|pounds?|bucks?|dollars?|euros?|cents?|gbp)\b)")
MONEY_RATE = re.compile(
    _MONEY + r"(?:\s*(?:to|-)\s*(?:[£$€]\s*)?\d[\d,.]*\s*(?:p|pence)?)?"
    r"\s*(?:a|an|per|each)\s+"
    r"(?:sec\w*|min\w*|hour|hr|hrs|day|week|month|year|night|visit|call|session|unit)s?\b", re.I)


def _a_money_rate(opening):
    """True when the reply says a price for a stretch of time, not a length of time."""
    return bool(MONEY_RATE.search(opening))


def _without_a_money_rate(opening):
    """The reply with its price-per-time phrases taken out, so the time check can be asked again."""
    return MONEY_RATE.sub(" ", opening)


# A yes/no that asks about a quantity rather than a thing: "is that enough", "will that be enough",
# "is that too far", "is that too long", "is 18 hours too much for a cat". The thing it asks about
# is a figure from earlier in the chat and the line does not name it, so a reply cannot be matched
# to the line by naming a thing - and on the deck that left ten answered turns called misses: "15
# minutes is short of the 20 minutes that answer named", "30 minutes is inside the 30 to 60 minutes
# that answer named, so you are fine", "3 times a week is at the three sessions a week that answer
# named, so you are there already".
#
# What answers one is the person's own figure set against the standard, and the shape is the figure
# at the head of the sentence with the relation after it. That head is what tells a verdict from a
# reply that only holds a figure near a word like "under": "up to about 3 or 4 pouches of 85g for a
# 4kg cat" and "under two, video calls and the odd photo only" both answer a how-much and say
# nothing about the person's figure, and neither opens on one.
A_QUANTITY_ASK = re.compile(
    r"\b(?:enough|too (?:much|many|far|often|long|hot|cold|big|small|old|young|late|soon|heavy|"
    r"short|thick|thin|deep|tall|high|low|expensive|dear))\b", re.I)
_A_QUANTITY_NUMBER = (r"(?:\d[\d.,]*|one|two|three|four|five|six|seven|eight|nine|ten|eleven|"
                      r"twelve|fifteen|twenty|thirty|forty|fifty|sixty|ninety|hundred|half|"
                      r"a couple|a few|an|a)")
_A_QUANTITY_UNIT = (r"(?:sec|second|minute|min|hour|hr|day|week|month|year|night|kg|kilo|pound|"
                    r"mile|km|litre|pint|cup|gram|ounce|stone|cm|inch|foot|feet|metre|session|"
                    r"time|portion|serving|slice|step|dose|tablet|degree|celsius|unit|item|"
                    r"episode|page|p)s?\b")
_A_QUANTITY_RELATION = (r"(?:under|over|above|below|inside|within|short of|past|at|less than|"
                        r"more than|on the line|clear of|off the|away from)")
_A_FIGURE_AGAINST_THE_STANDARD = re.compile(
    # A short lead-in is allowed, because the reply may be answering a follow-up: "Same as before:
    # Two hours is over the ninety minutes the recipe gives."
    r"\A\s*(?:[^:]{1,45}:\s*)?(?:about|around|just|only|nearly|almost|well|roughly)?\s*"
    r"(?:£\s*\d[\d.,]*|\$\s*\d[\d.,]*|€\s*\d[\d.,]*|"
    + _A_QUANTITY_NUMBER + r"[\s-]*(?:" + _A_QUANTITY_NUMBER + r"[\s-]*)?-?\s*"
    + _A_QUANTITY_UNIT + r")"
    # "2 sessions a week", "3 times a day": the rate the figure is paid at is part of the figure.
    r"(?:\s+(?:a|an|per|each)\s+(?:week|day|month|year|night|hour|session))?"
    r"\s+(?:is|are|comes|sits|lands)\s+(?:the\s+|well\s+|just\s+|a bit\s+|a little\s+)?"
    + _A_QUANTITY_RELATION + r"\b", re.I)


def _the_figure_against_the_standard(opening, said):
    """The verdict a yes/no about a quantity wants, when the reply sets the figure against it."""
    if not A_QUANTITY_ASK.search(said or ""):
        return False
    return bool(_A_FIGURE_AGAINST_THE_STANDARD.match(opening or ""))
