"""Find the knowledge entry a line is about, by meaning rather than by wording.

Every domain module in bot/knowledge/ exposes ENTRIES, a list of Entry built with
entry(). An Entry says what it is about with `key` (single words or short phrases,
optionally a tuple of alternatives) and how to answer with `reply`. The matcher finds
the entry whose key words the line actually contains, so one fact answers every way
of asking for it: "how long do I roast a chicken", "chicken cooking time" and
"2kg chicken, how long?" all reach the same entry.

    entry("roast-chicken", ("chicken", ("roast", "oven", "cook", "time")),
          "About 20 minutes per 500g at 190C (170C fan), plus 20 minutes: ...")

Matching is deliberately strict. Words match loosely (eggs/egg, cooking/cook), a
phrase matches a short run of words, a phrase scores 3 and a single word 2, and a
line needs MIN_SCORE (4) to be answered at all. So two signals are needed, and a line
that only mentions a topic in passing ("my chicken pox") falls through to a module
that can help, or to "I don't know", instead of getting the wrong canned answer.

The one exception is a misspelt key word. People type "chiken" and "radiatior", so a
line word that is no key word at all and is a single slip (one letter wrong, missing,
extra, or swapped with its neighbour) away from exactly one key word is read as that
key word. Three things keep that from turning a real word into a fact: the word must be
one the engine does not already read, in any of its forms ("leaving" is a form of
"leave", so a charging phone does not become a changing leaf), the slip must lead to a
single word family ("radiaters" is one answer, "lips" is not), and a slip never lifts a
line past the entry's avoid list, not even an ambiguous one ("brest" is a whole-bird
question neither way).
"""
import re
import string

# Misspellings a domain lists as key words on purpose, mapped to the entries that list them, so its
# own answer can be reached from the misspelling itself ("how do i spell definately"). A word is
# only left out of the vocabulary below when the entries that use it are exactly the ones that
# registered it: then it is a misspelling and nothing else, and the slip reader keeps reading it as
# the right word. Without that, listing "adress" quietly stopped "who do i tel about my new adress
# after moving" from reaching the address answer, because a key word is never read as a slip.
SLIPS = {}

from ..understanding import lexicon
from ..understanding.normalize import LEXICON as COMMON_WORDS
from ..understanding.normalize import TIME_WORDS

# A sentence with a hole in it is filled with words out of the person's own line, and only the
# words that name something should go in. "is it ok to give water" hands the heartburn card the
# phrase "ok to" before the verb "give", and "Cut ok to out for a fortnight" is not a sentence
# anybody wrote: it is word salad in the middle of an answer. One content word is the whole test,
# so no list of foods, cities or machines has to be kept up to date.
GRAMMAR_ONLY = frozenset((
    "a", "an", "the", "and", "or", "but", "if", "so", "as", "at", "by", "for", "from", "in",
    "into", "of", "on", "onto", "over", "under", "to", "up", "with", "without", "about",
    "after", "before", "than", "then", "that", "this", "these", "those", "it", "its", "is",
    "are", "was", "were", "be", "been", "being", "am", "do", "does", "did", "doing", "done",
    "can", "could", "should", "would", "will", "shall", "may", "might", "must", "not", "no",
    "yes", "ok", "okay", "alright", "just", "also", "too", "very", "really", "quite", "more",
    "most", "much", "many", "any", "all", "some", "none", "every", "each", "i", "me", "my",
    "mine", "we", "us", "our", "you", "your", "he", "him", "his", "she", "her", "they",
    "them", "their", "there", "here", "when", "where", "what", "which", "who", "how", "why",
    "have", "has", "had", "having", "get", "gets", "getting", "got", "go", "goes", "going",
    "went", "give", "gives", "gave", "giving", "take", "takes", "took", "taking", "make",
    "makes", "made", "making", "eat", "eats", "ate", "eating", "eaten", "drink", "drinks",
    "drank", "drinking", "drunk", "again", "still", "always", "never", "sometimes", "often",
    "now", "today", "tonight", "yesterday", "tomorrow", "lot", "lots", "loads", "bit", "kind",
    "sort", "one", "ones", "thing", "things", "time", "times", "day", "week", "month", "year",
))


def names_a_thing(phrase):
    """Whether a phrase that fills a hole in a sentence names something.

    Used where the phrase came out of the person's own line. A phrase of grammar alone ("ok to",
    "not", "is it") fills no hole: the card says its plain answer instead of a broken sentence.
    A number is not a thing either - "Cut 3 out for a fortnight" is the same salad.
    """
    words = [word for word in re.split(r"[^a-z0-9']+", str(phrase or "").lower()) if word]
    return any(word not in GRAMMAR_ONLY and not word.isdigit() for word in words)

WORD = re.compile(r"[a-z0-9]+(?:'[a-z]+)?")

# The table `re` keeps of compiled patterns holds 512 entries, and one turn asks for far more
# distinct ones than that: a knowledge row builds its bounds around its own key words ("\\b" +
# re.escape(word) + "\\b" for every food a meal idea rules out, every word of a word list, every
# row that looks for the thing it names), and each of those is a pattern the engine has not seen.
# Past 512 the table is thrown away whole, so the next call compiles its pattern from scratch:
# a five-line chat made `re` build 9,682 patterns, and the same chat run again built 8,976 more
# because the table had gone in between. A conversation is one process with a fixed vocabulary,
# so the table can hold every pattern a chat can build; with it held, that chat builds its
# patterns once and nothing on the second time round. Nothing a person hears depends on it - a
# compiled pattern matches exactly the lines its string did - and tests/test_lookup_speed.py
# holds that.
try:
    re._MAXCACHE = max(getattr(re, "_MAXCACHE", 512), 16384)
except Exception:  # noqa: BLE001 - a stdlib that keeps its table another way is not our crash
    pass

# The words a line asks with, never a thing a line is about. A key that names one of these as
# its subject ("can", "cans") would otherwise take every line that asks the question, since the
# form of "cans" includes "can": "can i still travel" was answered by the cool-bag card.
ASKING_MODALS = frozenset("can could would should may might must shall will".split())
# The words that follow a modal in a question and never follow a can of drink: "can i still
# travel", "can you keep it cold", "can we take it on the plane".
ASKING_SUBJECTS = frozenset("i you we they he she it u".split())


def _asking_with(typed, at):
    """True when the word at `at` is the line's own question word, not a thing in it."""
    if typed[at] not in ASKING_MODALS:
        return False
    return at + 1 < len(typed) and typed[at + 1] in ASKING_SUBJECTS

MIN_SCORE = 4          # below this the line is not really about the entry

# "will", "can" and "should" are mostly verbs. An avoid word is matched loosely, so a bare one in an
# avoid list stands the row down for every "can I ...", "will my ..." or "should I ..." line - which
# is the commonest way a person opens a question. `avoid=("will",)` on the death-and-funeral rows
# meant "will my funeral cost" and "will i lose my photos" got a hedge, and `avoid=("can",)` on the
# tomato row meant "can i keep tomatoes in the fridge" got the generic fridge card. A bare modal in
# an avoid list was never meant as the verb: it is the noun, and these are the phrasings.
MODAL_PHRASES = {
    # the document, not the verb
    "will": ("a will", "my will", "the will", "in the will", "their will", "write a will",
             "will and testament"),
    # a tin, not the modal, and the plural is the same tin
    "can": ("can of", "cans of", "a can", "the can"),
    "cans": ("cans of", "some cans", "two cans", "three cans"),
}

# A feeling said out loud is the subject of the line, not the place it happens in or the thing
# it happens on. The entries keyed on a place are the ones that get this wrong, and the words are
# shared here so each of them can name the same list rather than grow its own: "i keep panicking
# at my desk" is a panic line that says where, and the posture answer ("most bad posture is the
# chair and the sitting still") misreads it as a question about the chair. Only feelings and moods
# belong here - a symptom is a subject of its own ("my back aches at my desk" is a posture line and
# must stay one), and so is a thing ("my chest hurts when i run").
FEELING_WORDS = (
    "panic", "panics", "panicking", "panicky", "panic attack", "panic attacks",
    "anxious", "anxiety", "worried", "worry", "worrying", "worries", "nervous", "on edge",
    "stressed", "stress", "stressing", "overwhelmed", "overwhelming", "freaking out",
    "depressed", "depression", "low mood", "feel low", "feeling low", "feels low", "feeling flat",
    "miserable", "crying", "cry", "tearful", "upset", "dreading", "dread", "hopeless",
    "exhausted", "drained", "burnt out", "burned out", "burnout", "fed up", "cant cope",
    "can't cope", "breaking down", "angry", "anger", "frustrated", "irritable", "snappy",
)

# The words of a question that asks what to do, shared by the entries that answer one. A line
# like "what can i do about my dandruff" says the subject once and spends the rest of the line
# on the ask, so an entry that lists the subject and none of these words never reached it: the
# line scored 2, under MIN_SCORE, and the person got a hedge. These are the ask's own words and
# they name no subject, which is what makes them safe to share between domains: the subject
# still comes from the entry's first key part.
ASK_ABOUT = ("what", "how", "do", "can", "should", "help", "anything", "advice", "tips",
             "get rid", "rid", "stop", "treat", "treatment", "cure", "relief", "relieve", "ease",
             "prevent", "best", "works", "work", "deal with", "cope", "worse", "helps")
# A tooth that has just come out is a wound in the mouth, and almost every word around it is
# another answer's: "cold" is the cold (and the weather), "drink" is the units, "bleeding" is the
# gums, "eat" is when to eat, "jaw" is the click, "dentist" is the complaint about one. On today's
# main "i had a tooth out on tuesday and the gap still aches when i drink anything cold" was
# answered "A cold usually peaks in two or three days", and the person had a hole in their gum.
# So the rows either side stand down on these words and complaints.after-a-tooth-out answers.
# "Where does X come from" asks about the origin of the thing it names, and it is a shape of its
# own: the subject arrives once and the rest of the line is "does it come from". A row that lists
# only the "why/happen/cause" side of a question never reached one - "where does thunder come from"
# scored 2, the subject and nothing else, and went under MIN_SCORE, while "why does it thunder"
# reached the same row. These phrases are the shape and they name no subject, so a row can share
# them without becoming a question about anything else; the subject still comes from the row's own
# first key part. "where does electricity come from" was answered from the consumer unit before
# there was a row keyed on the origin at all.
ORIGIN_ASK = ("come from", "comes from", "came from", "come out of", "comes out of",
              "made from", "made of", "made out of", "made with", "where from",
              "is grown", "grown in", "grows on", "is mined", "is produced")

# A nose that is blocked is not a panic: "my baby cant breathe through her nose" is a cold, and
# the panic rows key on "cant breathe" and would take it. The phrases are the ones a parent
# types, and they say the breath is a nose rather than a lung.
NOT_A_NOSE = ("through my nose", "through your nose", "through his nose", "through her nose",
              "through their nose", "through the nose", "blocked nose", "blocked up nose",
              "stuffy nose", "bunged up nose", "nose is blocked", "nose is stuffy",
              "nose is bunged", "congested nose")


TOOTH_OUT = ("tooth out", "teeth out", "tooth removed", "teeth removed", "tooth pulled",
             "tooth extraction", "extractions", "tooth taken out", "teeth taken out",
             "had a tooth", "had my tooth", "had two teeth", "gap where", "where my tooth",
             "where the tooth", "the socket", "dry socket", "wisdom tooth out",
             "wisdom teeth out", "wisdom tooth removed", "after the extraction",
             "after my extraction", "after a tooth")

# A mouth line is a dental one even when its other words are a cold's: "my teeth hurt when i have
# a cold drink" and "my filling hurts when i drink something cold" were answered by the run-down
# colds row and the eating-when-ill row. Any row whose key carries "cold", "drink" or "eat" stands
# down on these, so the tooth answers keep their own lines.
TOOTH_OR_GUM = ("tooth", "teeth", "toothache", "filling", "fillings", "gum", "gums", "molar",
                "molars", "dentist", "dentists", "dental", "denture", "dentures", "enamel",
                "wisdom tooth", "wisdom teeth", "braces", "mouth ulcer", "gumline")

WORD_WEIGHT = 2
PHRASE_WEIGHT = 3

# A holiday somebody is saving for is a trip they are paying for, not the allowance they are owed
# at work and not a claim against the company that sold it. The two rows that own "holiday" answer
# the other two questions, and both took the saving one: "how much should i save for a holiday" got
# the 5.6 weeks of statutory leave, and "i need 2000 for a holiday how long will it take to save"
# got the 28-day package-travel deadline. The money row that answers a sum by a date says the
# right thing, so these rows stand down on the frame and it answers.
_SAVING_VERB = re.compile(
    r"\b(?:save|saves|saving|saved|put\s+away|putting\s+away|put\s+by|putting\s+by|"
    r"set\s+aside|setting\s+aside|afford|affords|affording)\b", re.I)
# "for a holiday" and not "for the summer": the thing the money is going towards. A number of
# days is not this ("i saved three days of holiday"), which is why the verb alone is not enough.
_SAVING_FOR_A_TRIP = re.compile(
    r"\bfor\s+(?:a|an|the|my|our|their|your|his|her|this|next)?\s*"
    r"(?:holiday|holidays|trip|trips|break|weekend\s+away|city\s+break|getaway)\b", re.I)


# "can i afford a holiday this year" says the paying without a "for": the verb and the trip are
# next to each other and nothing else is being weighed.
_AFFORD_THE_TRIP = re.compile(
    r"\bafford\b[^.;!?]{0,25}?\b(?:holiday|holidays|trip|breaks?|getaway)\b", re.I)


def saving_for_a_trip(understood):
    """False when the holiday in the line is one they are paying for, not one they are owed."""
    line = (understood or {}).get("clean") or (understood or {}).get("text") or ""
    if _AFFORD_THE_TRIP.search(line):
        return False
    return not (_SAVING_VERB.search(line) and _SAVING_FOR_A_TRIP.search(line))

# The improving verb in front of a subject is the ask, not a topic. People say "how do i get
# better at interviews", "how do i improve my mood", "how do i sort out my taxes", "how do i
# interview better" - the subject is named once and the rest of the line is spent on the verb,
# so an entry that lists the subject and none of these answered a line with nothing in it and
# the person got a hedge over an answer that exists.
#
# It goes in the entry's SECOND key part, next to the ask words, so the subject still has to be
# named: "which interview outfit is better" stays the outfit entry's, because the subject there
# is the outfit and "better" is the comparison, and a line naming no subject at all ("how do i
# get better at things") reaches nothing. That is also why `better` on its own is safe here: a
# second part credits one covered word, and this part is only ever read next to a subject part.
# A present asked for is a shopping question, not a how-to. "what can i buy my dad who likes
# fishing" was answered "A new fish needs the tank ready before it goes in", and "idk what to get my
# dad for his 60th, he likes fishing and old films" with the same fish card, because a gift line and
# a hobby line meet at the hobby word and the row that answers how to start the hobby scored first.
# The rows that teach an activity or how to look after an animal take this in their `avoid`, the way
# they already fend off the kitchen and the vet; the shopping rows own the present.
#
# Only the asking shapes, never a bare "get" or "buy": "i bought a new fish what do i need" is a
# care question with a purchase in it, and "how do i get into fishing" is not a present either.
PRESENT_ASK = (
    "gift", "gifts", "present", "presents", "gift idea", "gift ideas", "present idea",
    "present ideas", "christmas present", "christmas gift", "birthday present", "birthday gift",
    "what should i get", "what can i get", "what do i get", "what to get",
    "what should i buy", "what can i buy", "what do i buy", "what to buy",
    "what should i give", "what can i give", "what do i give", "what to give",
    "what would you get", "what would you buy", "what would you give",
    "get him", "get her", "get them", "buy him", "buy her", "buy them", "give him", "give her",
    "for his birthday", "for her birthday", "for their birthday",
    "for his christmas", "for her christmas", "for their christmas",
)

IMPROVE = ("get better at", "better at", "get better", "better", "improve", "improving",
           "improve my", "improvement", "sort out", "sort out my", "sort myself out",
           "work on", "work on my", "get good at", "good at", "get the hang of", "brush up on",
           "practise", "practice", "sharpen up")

# How a person states a complaint as a plain fact about themselves: "im stuffy", "i've got a
# cough", "i feel dizzy". These lines say the subject once and nothing else, so they score 2 and
# stop under MIN_SCORE, and a whole symptom that the knowledge base already answers was going to
# the chat module, which can only sympathise: "im constipated" was answered "Sorry to hear it - go
# easy on yourself today" while the constipation entry sat one word away.
#
# A phrase covers two words of the line, so a report phrase is enough of a second signal. It goes
# in the entry's subject part, next to the subject word, because a part credits only its best
# alternative: the longer wordings ("my nose is stuffy", "how do i stop feeling breathless")
# score exactly as they did before, and only the bare report is added.
# A line can ask the same job two ways and want two different things: "how do i clean the oven"
# is the method and "how often should i clean the oven" is the interval. The rows that hold both
# answers read these words to tell which was asked, so the second sentence of a method card is
# never the answer to a frequency question and the method is never the answer to "how often".
# They live here, in one place, because the tables in cleaning, cars and family all ask it the same
# way, and a row that spelled its own list differently answered some of the lines and not others.
HOW_OFTEN_WORDS = ("how often", "how frequently", "how regularly", "how many times", "often",
                   "frequently", "regularly", "how long between", "every how long", "frequency")


def the_line(understood):
    """The line as the readers read it, lowercased: what a reply callable checks its ask against."""
    understood = understood or {}
    return " ".join(str(understood.get(key) or "")
                    for key in ("clean", "norm_text", "plain")).lower()


def asks_how_often(understood):
    """True when the line asks the interval rather than the method.

    Takes the reading (`memory["understood"]`) or the line already flattened by `the_line`.
    """
    said = understood if isinstance(understood, str) else the_line(understood)
    return any(word in said for word in HOW_OFTEN_WORDS)


SAID_LEADS = ("im", "i am", "im really", "im so", "im very", "im all", "ive been", "ive got", "i have",
              "i have been", "i feel", "feel", "i keep getting", "i keep being", "i get")


def said(*words, leads=SAID_LEADS):
    """The phrases that make a one-word report of `words` reach an entry.

        entry("blocked-nose", (("nose", "sinuses") + said("stuffy", "bunged up"), (...)),
              "A blocked nose is swollen lining and mucus, so ...")

    so "im stuffy" and "i am bunged up" reach the answer that "my nose is stuffy" already had.
    """
    return tuple(f"{lead} {word}" for word in words for lead in leads)


# The frame around an advice ask: "what should i do about the lawn", "any tips for a hangover",
# "what helps a sore throat", and the same ask put after its subject ("i have a cold sore on my
# lip what helps"). The frame spends the line on the asking, so the subject inside it is the whole
# subject: read on its own, a subject that names an answer outright ("the mould on the ceiling")
# reaches that answer instead of an entry that shares one of the asking words, which is how "what
# can i do about the mould on the ceiling" reached the football boots.
_WRAPPED = (
    re.compile(r"^(?:and |so |ok |okay |hi |hello )?(?:what|anything|something)\s+"
               r"(?:should|can|could|would|do|will|shall)\s+i\s+"
               r"(?:do|use|try|take|put|buy)\s+(?:about|for|on)\s+(?P<subject>\S.*?)\s*\??$"),
    re.compile(r"^(?:and |so )?(?:what|anything)\s+(?:helps|works|is good)\s+"
               r"(?:for\s+|with\s+)?(?P<subject>\S.*?)\s*\??$"),
    re.compile(r"^(?:and |so )?(?:any|some|got any|have you got any|do you have any)\s+"
               r"(?:tips|advice|suggestions|ideas)\s+(?:for|on|with|about)\s+(?P<subject>\S.*?)\s*\??$"),
    re.compile(r"^(?P<subject>\S.*?)[,;:]?\s+(?:what|anything)\s+(?:helps|works)\s*\??$"),
)
# Words that say nothing about what the ask is about, so a wrapper that carries only these has no
# subject to look up ("what should i do about it" is a follow-up, and the conversation has it).
_NOT_A_SUBJECT = frozenset(
    "a an the my your our their his her its it that this these those me us him them someone "
    "anyone everyone something anything nothing more less best good now then here there".split())
# A wrapper whose subject is really an idiom: "what do i do for a living" asks about their job,
# and "what helps for good" asks nothing at all.
_NOT_A_THING = frozenset(("a living", "a go", "a bit", "a while", "a change", "the best",
                          "my best", "a start", "the same", "a look", "a hand", "a try",
                          "a break", "a rest", "for good", "the day", "the weekend",
                          "it", "that", "this", "them", "anything"))

# The entries whose subject is one everyday noun and nothing else - a lawn, slugs, limescale, the
# condensation, snoring - and whose line therefore spends its other words on the asking. They are
# named here, in one place, because being asked about is a property of the entry, not of the
# domain it sits in: the ask around the subject is the second signal the one word cannot give.
# Any other entry keeps the two-word rule, so a word that only brushes past a key ("fly" for a
# fruit fly in "my fear of flying") can never answer on the strength of the ask.
ASK_FRAME_IDS = frozenset("""
    condensation damp limescale slug-control snoring snore-less hangover sore-throat
    sleep-trouble
    """.split())

# The words that turn the word after them into a description of the thing wanted rather than a
# name for a subject of its own: "im after something light" asks for a light film, not for the
# physics of light. Every one of them is an indefinite pronoun, which stands in front of an
# adjective and nothing else, so a subject that appears only behind one is not what the line is
# about. "what should i watch tonight, something light" was answered with photons, and "any good
# films out, something light" with the lighting circuit at the consumer unit.
AS_A_KIND = frozenset("something anything nothing everything".split())

MIN_TYPO_LENGTH = 4    # a three-letter word is a slip away from half the language

# "Ring" is a verb as well as a noun, and the verb is the commoner of the two by a long way. Every
# card keyed on the noun - a ring stuck on a finger, a ring on a hob, a ring that has gone dull -
# shares this list, because the same two words mean a phone call: "my ring is stuck" is the finger
# and "should i ring in sick" is work. Two of the shapes stood no chance of a guard on their own:
# the verb with no object after it ("ring in", "ring ahead"), and a line that carries its subject
# over from the turn before, which is how "i have a cold sore" then "should i ring in sick" got
# soap and dental floss - the carry-over met the two-signal rule with "cold sore".
# Read with loose forms, so "ringing the dentist" and "i rang the bank" are the same shape.
RING_AS_A_CALL = (
    "ring the", "ring my", "ring him", "ring her", "ring them", "ring you", "ring me",
    "ring someone", "ring somebody", "ring anyone", "ring anybody", "ring people",
    "ringing someone", "ringing somebody", "ringing people", "rang someone", "rang somebody",
    "ring a", "ring an", "ring about", "ring back", "ring up", "ring round", "ring around",
    "ring for", "ring to", "ring at", "ring and", "ring later", "ring tomorrow",
    "ring in", "ring sick", "ring ahead", "ring work", "ring first thing",
    "ring first", "ring instead", "ring again", "to ring", "should ring", "will ring",
    "can ring", "could ring", "would ring", "might ring", "must ring", "need to ring",
    "have to ring", "give a ring", "give her a ring", "give him a ring", "give them a ring",
    "give me a ring", "a ring round")

# The endings that make one word a form of another, so "radiaters" is one answer
# ("radiator", "radiators") rather than two, and a slip is not called ambiguous.
ENDINGS = ("iness", "iest", "ings", "ing", "ies", "ied", "ier", "ers", "est", "er",
           "es", "ed", "ly", "s", "y", "ness", "ful")
MIN_FORM = 3           # a loose form shorter than this is not the same word (weeing -> we)


class Entry:
    """One fact or piece of advice, keyed by the meaning of a line."""

    __slots__ = ("id", "key", "reply", "avoid", "bias", "ask", "slips", "domain", "fault",
                 "report", "guard", "shape", "explain", "lead")

    def __init__(self, id, key, reply, avoid=(), bias=0, ask=(), slips=(), fault=False,
                 report=False, guard=None, shape=(), explain=False, lead=""):
        self.id = id
        self.key = tuple(key)
        self.reply = reply
        self.avoid = tuple(avoid)
        self.bias = bias
        self.ask = tuple(ask)
        self.slips = tuple(slips)
        self.domain = ""
        # True when the answer is about the appliance itself rather than a dish cooked in it.
        # "My oven will not heat up" says the oven is not working, and a cooking answer that
        # needs an oven is no use to it - but the oven's own repair answer is exactly right,
        # so it is not held out by the same check.
        self.fault = fault
        # True when naming the complaint in the first person is the whole question. A symptom
        # is not asked about: "i have tinnitus", "ive got heartburn", "i have a bunion" say the
        # subject once and nothing else, so they score on one position and get a chat nod
        # ("Noted: you have tinnitus") while the answer sits one word away. Only rows that
        # answer a complaint opt in, because "i have a dog" is not a question about keeping one.
        self.report = report
        # An optional test of the whole reading, for an entry that is only an answer when
        # something in the line is not what its own key says: "the table leg is cracked" has
        # a skin state beside a body part, but the part belongs to the table, so the dry-skin
        # entry must stand aside for the repair. The test is a function of `understood`, so
        # the words stay in the knowledge base and the reading comes from the understanding
        # engine, the way `thing_state` reads `state_owner`.
        self.guard = guard
        # True when a figure in the line, read as a shape rather than as a word, is the second
        # signal the entry needs. Some keys are a list of the figures people type - the phone on
        # 2%, 1%, 5% - and the list can never hold every number: "my phone is on 4%" reached no
        # entry at all and was acknowledged back at the person. A shape says what the figure is
        # (a percentage at or below 20%), so one row answers the whole family. Only the entries
        # whose subject is already named count on it, and it is worth exactly one key word, like
        # `report`, so a figure alone still never answers a line.
        self.shape = tuple(shape)
        # True when a plain request to explain the subject is a question the row answers. The
        # plainest way people ask for a fact names it and asks nothing else - "what is sepsis",
        # "tell me about gout", "explain shingles" - so the line has one word of the row's key
        # and the row never comes within reach of it (the scorer wants two signals) and a chat
        # nod or a search hedge takes the turn. A row that answers a named thing opts in,
        # because "what is the best way to clean a sofa" is not a request to explain a sofa and
        # only a row whose subject is the thing asked about can read it as one.
        self.explain = explain
        # The sentence this row owes a line that asks a question of one shape, in the row's own
        # words: "Usually, yes" for the side-effects card, which opens on the leaflet and reaches
        # the verdict two sentences later. `bot/compose/lead.py::answer_first` puts it in front
        # when the line wants the shape it gives, and leaves the row alone on every other line,
        # so one field serves every shape and every domain without a word of the card changing.
        self.lead = lead

    def __repr__(self):
        return f"<Entry {self.id}>"


# "my back fence", "the back door", "back garden": a fence, a door and a garden are all "back"
# something, and "back" is the house far more often than it is a spine. A key that needs two
# signals can take one from the line above - and a turn that carries the last line along says
# both at once: "the dog keeps digging under it, my back fence is rotten on one side" was answered
# with the manual-handling card ("Bend at the hips and knees rather than the waist..."). The row
# is right about a spine and wrong about a fence, so the place words are the fence.
PLACES_AFTER_BACK = (r"door|doors|fence|fences|gate|gates|gatepost|gateposts|garden|gardens|"
                     r"room|rooms|seat|seats|window|windows|wall|walls|yard|porch|lawn|path|"
                     r"pathway|step|steps|stairs|packet|packets|pocket|pockets|burner|burners|"
                     r"boiler|panel|panels|bed|beds|alley|bridge|road|lane|field|fields|"
                     r"paddock|plot|car|van|shed|garage|drive|driveway|garden")
BACK_OF_THE_HOUSE = re.compile(r"\bback\s+(?:%s)\b" % PLACES_AFTER_BACK)
# A back spoken about as a back: "my back", "the lower back", "a bad back", "his back".
THE_BACK_ITSELF = re.compile(
    r"\b(?:my|your|his|her|their|our|the|lower|upper|sore|stiff|aching|aching|bad|old)\s+"
    r"back\b(?!\s+(?:%s)\b)" % PLACES_AFTER_BACK)


# The household appliances whose own name can contain the name of one of their parts. "Heat pump"
# is the thing in the garden and the thing inside a tumble dryer; "fan" is an oven's, a car's and a
# desk's; "pump" is a pool's and a shower's. A row that answers the part, or the house system, has
# to stand down when the appliance's own name swallows the row's name, and the appliance's row then
# answers: "how much does a heat pump dryer cost" is a dryer's price, not a heat pump's. The test is
# the appliance phrase against the row's own names, so a plumber fitting a dishwasher is untouched.
APPLIANCE_NAMES = (
    "tumble dryer", "washer dryer", "heat pump dryer", "condenser dryer", "vented dryer",
    "washing machine", "fridge freezer", "fish tank", "pool pump", "shower pump", "fan oven",
    "microwave", "dishwasher", "dryer", "fridge", "freezer", "oven", "cooker", "hob", "kettle",
    "toaster", "vacuum", "hoover", "mower", "lawnmower", "strimmer", "radiator", "boiler",
    "car", "van", "motorbike", "bike", "bicycle", "aquarium", "hot tub")


def the_appliance_swallows_the_name(understood, names):
    """True when a named appliance contains one of `names` in its own name.

    "how much does a heat pump dryer cost" names the appliance `heat pump dryer`, which holds the
    row's name `heat pump`: the dryer's price is the question. "how much does a plumber charge to
    fit a dishwasher" names an appliance the row's names are not inside, so the plumber's price
    keeps its line.
    """
    parts = [str((understood or {}).get(part) or "") for part in ("clean", "text", "norm")]
    said = " " + " ".join(parts).lower() + " "
    names = [str(name).lower() for name in (names or ()) if str(name or "").strip()]
    if not names:
        return False
    for appliance in APPLIANCE_NAMES:
        if not re.search(r"(?<![a-z0-9])" + re.escape(appliance) + r"(?![a-z0-9])", said):
            continue
        # The row's own name has to be a part of the appliance's name, not the whole of it: a
        # boiler is the boiler and must keep its price, while "heat pump" inside "heat pump dryer"
        # is a dryer's part.
        if any(name in appliance and len(name) < len(appliance) for name in names):
            return True
    return False


def the_back_is_a_body_part(understood):
    """False when every "back" in the two lines is part of the house or the car.

    "my back fence is rotten" then "the dog keeps digging under it" is a fence question, and the
    manual-handling card is the wrong answer to it. A line that names the back itself - "my back
    hurts", "the lower back", "a bad back" - keeps its answer whatever came before.
    """
    said = str((understood or {}).get("text") or "").lower()
    above = str(((understood or {}).get("leans_on") or {}).get("text") or "").lower()
    both = said + " " + above
    if not BACK_OF_THE_HOUSE.search(both):
        return True
    return bool(THE_BACK_ITSELF.search(both))


def _avoid_words(parts):
    """The avoid list as a flat tuple of words.

    A module often shares these as a constant ("INFANT_RED_FLAGS"), and dropping that tuple into
    avoid= instead of adding it made an entry whose words were a tuple, which no word of a line
    can ever equal; the matcher only broke when it reached for the text of one. Flatten at the
    door, so a shared constant works whether it is added or nested, and so nothing that is not a
    word can reach the matcher.
    """
    flat = []
    for part in parts:
        if isinstance(part, str):
            # See MODAL_PHRASES: a bare modal is the noun, so it is expanded here rather than in
            # every domain that listed one, and a row added tomorrow is right without anyone
            # remembering to write the phrasing down.
            flat.extend(MODAL_PHRASES.get(part, (part,)))
        elif isinstance(part, (list, tuple, set, frozenset)):
            flat.extend(_avoid_words(part))
    return tuple(flat)


# --- he, she or they -------------------------------------------------------------------
# Some answers are about a second person: a present being chosen for someone, a cat that pushes
# things off the shelf. Writing "he" or "she" into the reply means the entry says the wrong word
# for half the people who reach it, and an entry is chosen by the thing it is about (the hobby, the
# animal), not by the person: "a present for my dad who's into gardening" was answered "She has
# told you what she likes", and "my tom cat keeps knocking things off the table" was answered
# "She is not being naughty". A reply built by about_them() reads the person off the line instead.
PEOPLE_MALE = ("dad", "father", "grandad", "grandpa", "grandfather", "stepdad", "brother",
               "husband", "boyfriend", "son", "uncle", "nephew", "bloke", "fella", "guy",
               "he", "him", "his")
PEOPLE_FEMALE = ("mum", "mother", "mam", "nan", "nana", "gran", "granny", "grandma",
                 "grandmother", "stepmum", "sister", "wife", "girlfriend", "daughter", "aunt",
                 "niece", "she", "her", "hers")


def about_them(template, male=PEOPLE_MALE, female=PEOPLE_FEMALE):
    """An Entry reply that says he, she or they according to the line.

    template uses {they} {them} {their} for the words and {has} {is} {likes} {loves} {self} for
    the verb and reflexive forms, so the same sentences work for one person, for a man, for a
    woman, and for a line that names nobody ("a present for someone into gardening" is "they").
    The first letter is capitalised so a template can be written the way it reads.
    """
    def reply(memory, reading):
        words = reading.get("words") or ()
        they = "they"
        for word in words:                      # a relation beats a stray pronoun
            if word in male:
                they = "he"
                break
            if word in female:
                they = "she"
                break
        plural = they == "they"
        fills = (("{they}", they),
                 ("{them}", "them" if plural else ("him" if they == "he" else "her")),
                 ("{their}", "their" if plural else ("his" if they == "he" else "her")),
                 ("{self}", "themselves" if plural else ("himself" if they == "he" else "herself")),
                 ("{has}", "have" if plural else "has"),
                 ("{is}", "are" if plural else "is"),
                 ("{likes}", "like" if plural else "likes"),
                 ("{loves}", "love" if plural else "loves"))
        out = template
        for token, word in fills:
            out = out.replace(token, word)
        return out[:1].upper() + out[1:]
    return reply


# --- the shape of the ask ------------------------------------------------------------------
# The ways people ask where to get a thing that carry no question word of their own. "cheapest
# place to buy a freezer" and "best place to buy a kettle" name no place in the matcher's sense
# and ask nothing the reading calls `where`, but a place is what they want. This is not the
# shopping domain's key list, which is wider on purpose: that row also answers "cheapest
# freezer" and "best price on a fridge", where the person is comparing prices and a place is a
# reasonable answer. The guard below is narrower, because it stands a row aside: only the
# phrases that ask for a place count, so "which dishwasher is the cheapest to run" is left to
# the running-cost row.
WHERE_PHRASES = ("where to buy", "where can i buy", "where should i buy", "where do i buy",
                 "where to get", "where can i get", "where should i get", "where do i get",
                 "cheapest place", "cheapest shop", "best place to buy", "which shop",
                 "what shop", "who sells", "where sells")


# The things the price-comparison answer is written for: something sold as a model, with a
# warranty and a price history to compare. `shopping.where-to-buy-cheapest` builds its thing arm
# from this list and the verdict rows below stand aside from a place question about one of them,
# so the answer and the stand-aside cannot drift apart. A thing that is not here keeps its verdict
# rather than being left with nothing: the generic advice ("refurbished or graded stock", "ex
# display") is written for a machine, and a weighted blanket is not one.
PRICE_COMPARED = ("fridge", "freezer", "fridge freezer", "washing machine", "washer dryer",
                  "tumble dryer", "dishwasher", "oven", "hob", "microwave", "kettle", "toaster",
                  "hoover", "vacuum", "tv", "television", "laptop", "phone", "tablet", "sofa",
                  "bed", "mattress", "wardrobe", "pram", "pushchair", "car seat", "bike",
                  "boiler", "mower", "lawnmower")


def asks_where(understood):
    """True when the line asks where to get something, which is a place and not a verdict.

    "Where can i buy a cheap freezer" and "cheapest place to buy a tumble dryer" ask the same
    question as "where can i buy a kettle", and the shopping domain's `where-to-buy-cheapest`
    answers all three. The verdict rows never saw them: an appliance name and the bare word
    "buy" are all those need, so a freezer was told it is worth it if you use it three times a
    week, and a dryer the trade on dryers. A place is what the person asked for, so this is
    what stands a verdict aside - the reading's own `where`, and the buying-place phrases for
    the people who ask it without saying where.
    """
    if "where" in tuple((understood or {}).get("asks") or ()):
        return True
    words = (understood or {}).get("words") or ()
    text = " " + " ".join(str(word) for word in words).lower() + " "
    return any(phrase in text for phrase in WHERE_PHRASES)


# The pieces of a machine that are sold on their own: a door seal, a filter, a basket, an element.
# The price answer is written for the machine ("compare the exact model ... refurbished or graded
# stock with a real warranty"), and none of that is advice about a part. The part rows answer these
# where they exist, and where they do not, the verdict on owning the thing is what main says, and a
# verdict is no worse than advice about a warranty.
WHERE_PART_WORDS = ("spare", "spares", "part", "parts", "replacement", "door", "doors", "seal",
                    "seals", "gasket", "filter", "filters", "basket", "baskets", "tray", "trays",
                    "drawer", "drawers", "shelf", "shelves", "handle", "handles", "hinge",
                    "hinges", "lid", "lids", "element", "elements", "drum", "drums", "belt",
                    "belts", "pump", "pumps", "motor", "motors", "fan", "fans", "blade", "blades",
                    "brush", "brushes", "hose", "hoses", "pipe", "pipes", "knob", "knobs", "bulb",
                    "bulbs", "thermostat", "compressor", "descaler", "descale", "limescale")


def asks_where_a_shop_answers(understood):
    """True when the line asks where to get one of the things the price answer is written for.

    This is the guard the verdict rows use, and it is the same test the buying row applies to
    itself, so a verdict only steps aside when a better answer really takes the line. Asking where
    is not enough on its own: standing a verdict aside for a thing the buying row does not name
    left the person with a shrug, or with whatever unrelated row scored next ("where can i buy a
    coffee machine" was told to compare the price per kilo).

    A part is not the thing: "where can i buy a hoover filter" and "where do i get a new oven
    element" are pieces, and advice about comparing models, warranties and ex-display stock is
    written for the machine. The same goes for a bare follow-up: "where do i get one" three turns
    into a fridge door seal is the seal, so what the reading resolved it to has to end in one of
    these things - "tumble dryer" does, "fridge door" does not.
    """
    if not asks_where(understood):
        return False
    words = [str(word).lower() for word in ((understood or {}).get("words") or ())]
    if any(word in WHERE_PART_WORDS for word in words):
        return False
    text = " " + " ".join(words) + " "
    if any(thing in text for thing in PRICE_COMPARED):
        return True
    ref = str((((understood or {}).get("ref") or {}).get("it")) or "").strip().lower()
    if not ref:
        # "where do i get one" on its own names nothing at all: the buying row cannot know what
        # "one" is, so the rows that read the conversation keep the line
        return False
    return any(ref == thing or ref.endswith(" " + thing) for thing in PRICE_COMPARED)


# --- the thing that is broken ----------------------------------------------------------
# A repair answer is reached by the words landlord and broken whatever is broken, so the thing
# itself has to come off the line: "my washing machine is broken and the landlord wont fix it" was
# answered with a letter reading "The boiler has been broken since Tuesday and we have no hot
# water", and a toilet and a shower got that boiler too. A letter that names the wrong thing is
# worse than no letter, because it is the one message the person copies and sends. The words here
# are the faults people bring to a landlord, longest first, so "washing machine" does not become
# "machine" and "hot water" is not read as a shower.
THE_FAULT = (("washing machine", "washing machine"), ("tumble dryer", "tumble dryer"),
             ("tumble drier", "tumble dryer"), ("spin dryer", "tumble dryer"),
             ("dishwasher", "dishwasher"), ("fridge freezer", "fridge freezer"),
             ("fridge", "fridge"), ("freezer", "freezer"), ("microwave", "microwave"),
             ("cooker", "cooker"), ("oven", "oven"), ("hob", "hob"),
             ("central heating", "central heating"), ("heating", "heating"),
             ("hot water", "hot water"), ("radiators", "radiators"),
             ("radiator", "radiator"), ("boiler", "boiler"),
             ("shower", "shower"), ("bath", "bath"), ("toilet", "toilet"), ("loo", "toilet"),
             ("extractor fan", "extractor fan"), ("smoke alarm", "smoke alarm"),
             ("front door", "front door"), ("letterbox", "letterbox"),
             ("intercom", "intercom"), ("window frame", "window"), ("window", "window"),
             ("roof", "roof"), ("guttering", "gutter"), ("gutter", "gutter"),
             ("chimney", "chimney"), ("damp patch", "damp"), ("damp", "damp"),
             ("mould", "mould"), ("mold", "mould"), ("condensation", "condensation"),
             ("leak", "leak"), ("electrics", "electrics"), ("electric", "electrics"),
             ("plug socket", "socket"), ("socket", "socket"), ("lights", "lights"),
             ("light", "light"), ("tap", "tap"), ("sink", "sink"), ("drains", "drain"),
             ("drain", "drain"), ("pipes", "pipes"), ("pipe", "pipe"),
             ("stairs", "stairs"), ("ceiling", "ceiling"), ("floor", "floor"),
             ("wall", "wall"), ("fence", "fence"), ("lock", "lock"), ("garden", "garden"),
             ("garage", "garage"))


# A pattern that finds a phrase as a whole word, compiled once for each phrase it is asked
# about. `re.search` compiles and caches its own patterns, but the cache is 512 entries and the
# knowledge base asks about thousands of phrases, so every other question re-compiled the
# pattern: on a random deck turn that was a fifth of the reply. The patterns are built from
# module-level words, so the card holds a few thousand and never grows with a conversation.
_BOUNDED = {}
_BOUNDED_KEEP = 40000


def _bounded(name):
    """The compiled pattern finding `name` as a whole word, worked out once for the phrase."""
    got = _BOUNDED.get(name)
    if got is not None:
        return got
    got = re.compile(r"(?<![a-z0-9])" + re.escape(name) + r"(?![a-z0-9])")
    if len(_BOUNDED) >= _BOUNDED_KEEP:
        _BOUNDED.clear()        # a card of patterns, not a leak; the next turn fills it again
    _BOUNDED[name] = got
    return got


def the_fault(template, when_unnamed, table=THE_FAULT):
    """An Entry reply that names the broken thing the person actually said.

    template carries {fault}, which becomes the noun from `table` that the line names, so a
    letter, a first check or a "who to call" answer can be about the person's own problem.
    `when_unnamed` is used instead when the line names no thing at all ("the landlord is ignoring
    me about repairs"). The generic words are deliberately not in the table: "repair", "fault" and
    "everything" are longer than "damp" and "oven", so they would win on a line that names both,
    and a letter about "the repairs" is the vagueness the person already had. Longest word first, and only the first fault named, because the
    letter quotes one and the person adds the rest.
    """
    wanted = [(re.compile(r"\b" + re.escape(word) + r"\b"), noun)
              for word, noun in sorted(table, key=lambda pair: len(pair[0]), reverse=True)]

    def reply(memory, reading):
        line = str(reading.get("text") or reading.get("clean") or "").lower()
        for pattern, noun in wanted:
            if pattern.search(line):
                return template.replace("{fault}", noun)
        return when_unnamed
    return reply



# A "how long" line can be about three different clocks: the appliance's life ("how long does a
# boiler last"), the appliance's own minute or two ("how long does a kettle take to boil"), or the
# job ("how long does a boiler repair take"). The job's words live here because every clock-asking
# entry was answering a repair question with its own numbers - a boiler's ten to fifteen years, a
# kettle's three minutes, and the fridge's three to four days for "how long does a fridge repair
# take" (urban-orange, quality). An entry whose key is a clock adds this to its avoid, and the job
# has the row that answers it.
# --- a food named in the line is a food question ----------------------------------------
# The words below are the food a line talks about, for the rows that are not about food at
# all: a nail row, a tin of paint. "my sourdough starter smells like nail varnish remover"
# carries nail, varnish and remover, so the nail-art row taught it two thin coats, and the
# paint-smell row answered it next. Both now stand down when the line names a food, which is
# what every real nail and every real painted wall is missing.
FOOD_SUBJECT = ("sourdough", "starter", "kombucha", "kefir", "ferment", "fermented",
                "fermenting", "hooch", "dough", "bread", "beer", "wine", "vinegar", "pickle",
                "yoghurt", "yogurt", "milk", "cheese", "butter", "meat", "chicken", "fish",
                "rice", "pasta", "potato", "potatoes", "food", "foods", "drink", "drinks",
                "juice", "curry", "stew", "soup", "cake", "biscuit", "biscuits")

# "my kettle has gone" is the same fault as "my kettle is broken": the thing is dead and the
# person has not said how. "Gone" is also what a colour, a picture or a smell does - "the telly
# has gone black", "the milk has gone off", "the soup went cold" - so the word is the thing's
# fault only where it is the whole of what the thing did, with nothing describing after it.
# The words after it that describe rather than name the fault: they hand the line back to the
# colour, the picture, the food and the heating rows, which are the ones that answer them.
HAS_GONE = re.compile(r"\b(?:has|have|had|'s|s|is|was)\s+(?:gone|went)\b(.*)$")
# A word that only says how much: "the kettle's gone all white inside" is the scale, not the
# element, and "gone really quiet" is a fan. The word after it is the one that decides.
GONE_INTENSIFIER = frozenset("""all a an really very so quite proper totally completely kind sort
    bit little lot bit too pretty well""".split())
GONE_STATE = frozenset("""black white blue green grey gray red pink yellow orange purple brown
    rusty fuzzy blurry funny fuzzy quiet noisy loud silent still cold hot warm cool dark dim
    blank off bad worse flat dead solid hard soft sticky lumpy dry wet sour mouldy stale numb
    bright pale gold silver cracked wet""".split())


def the_thing_has_gone(understood):
    """Whether "gone"/"went" is what the thing did, rather than the state it went into.

    True for "my washing machine has gone and it is not a year old", "the seal on my fridge door
    has gone" and "my kettle's gone"; false for "the telly has gone black", "the milk has gone
    off", "the soup went cold" and "the picture has gone funny", which name what came after, and
    false for "we went out and left the stew on the hob", which is nobody's fault.
    """
    reading = understood if isinstance(understood, dict) else {}
    said = [str(word).lower() for word in (reading.get("words") or [])]
    line = " " + " ".join(said) + " "
    if not said:
        line = " " + str(reading.get("clean") or reading.get("text") or "").lower() + " "
    after_gone = [found.group(1) for found in HAS_GONE.finditer(line)]
    for tail in after_gone:
        words = [word.strip("'.,!?") for word in tail.split()]
        words = [word for word in words if word]
        while words and words[0] in GONE_INTENSIFIER:
            words.pop(0)
        if not words or words[0] not in GONE_STATE:
            return True
    return False


# --- the food is what has gone off -----------------------------------------------
# "my chicken smells a bit, can i cook it" is a food-safety question, and the answers that were
# given were the ones that read the smell, not the food: the kitchen-smell row opened a window and
# simmered a pan of lemon ("cooking" and "smells" are two of its key words), and the chicken
# nutrition row answered "is my chicken still ok to eat" with what is in a chicken. Both are good
# answers to other lines. The rule they were missing is one sentence - when the line says the food
# it names has gone off, it is asking whether that food is still all right - and it belongs to the
# food, so it is written once here and `bot/knowledge/still_ok.py`'s rows answer it.
FOOD_NAMED = FOOD_SUBJECT + (
    "ham", "bacon", "sausage", "sausages", "beef", "pork", "lamb", "mince", "steak",
    "turkey", "salmon", "cod", "haddock", "tuna", "prawn", "prawns", "egg", "eggs",
    "tofu", "beans", "lentils", "leftover", "leftovers", "fruit", "berries", "veg",
    "vegetables", "salad", "gravy", "stew", "curry", "soup", "rice", "pasta",
    "noodles", "sandwich", "mayo", "mayonnaise", "cream", "custard", "pie", "quiche",
    "dinner", "lunch", "supper")

# How a food that has gone off is said to be gone, in two parts, because the verb alone does not
# say which way it went: "my chicken smells" is a complaint and "my roast chicken smells great" is
# not. So a smell is only the first half of it - the second half is what is said of the smell (or
# that nothing is said at all, which is the complaint: "my chicken smells, can i cook it").
SMELL_VERBS = frozenset(("smell", "smells", "smelled", "smelt", "smelling", "smelly",
                         "stink", "stinks", "stank", "stinking"))
# Said of the food itself, the state words are the whole question: "the milk has gone sour", "the
# ham looks slimy".
OFF_SAID_OF_FOOD = frozenset((
    "sour", "soured", "souring", "slimy", "slime", "tacky", "sticky", "mouldy", "moldy",
    "rancid", "curdled", "curdling", "rotten", "putrid", "funny", "bad", "dodgy", "grey",
    "fizzy", "bubbling", "discoloured", "discolored", "off"))

# A smell said to be a good one, or a comparison rather than a fault: "my roast chicken smells
# great", "my curry smells amazing", "my chicken smells of garlic". None of them is a question
# about whether the food is still all right, and a spoilage card given to one is an insult to
# dinner.
A_GOOD_SMELL = frozenset((
    "great", "good", "amazing", "lovely", "nice", "delicious", "fine", "wonderful",
    "fantastic", "incredible", "tasty", "better", "perfect", "heavenly", "divine", "ok",
    "okay", "alright", "lush", "yummy", "appetising", "appetizing", "gorgeous", "brilliant",
    "of", "like"))

# The few words a line puts between a food and how it has gone: "the milk has gone sour", "the
# chicken looks a bit grey". Anything else ends the search, so "chicken and rice smells" is the
# rice's smell and not the chicken's.
BEFORE_OFF = frozenset((
    "has", "have", "had", "is", "was", "are", "were", "been", "be", "being", "got",
    "gets", "getting", "gone", "went", "go", "goes", "going", "looks", "looked",
    "looking", "tastes", "tasted", "the", "my", "a", "an", "bit", "little",
    "now", "and", "just", "really", "very", "so", "still", "quite", "definitely",
    "starting", "to", "on", "properly", "seriously"))

# The same question asked without a word for a smell: "is my chicken still ok to eat", "has the
# ham gone off", "is this beef out of date". Each of these is a phrase rather than a word, and a
# food word still has to be in the line, so "is the wifi still ok" reaches nothing here. A bare
# "ok to eat" is not on this list on purpose: "is it ok to eat 2 eggs a day" is a diet question.
OFF_STATE_ASKS = ("still ok", "still okay", "still good", "still fine", "still safe",
                  "still alright", "still all right", "still edible", "gone off",
                  "going off", "gone bad", "went off", "gone past", "gone sour",
                  "gone mouldy", "gone slimy", "out of date", "past its date",
                  "past the date", "past their date", "use by", "best before",
                  "is off", "smells off", "are off", "smell off")


def food_has_gone_off(understood):
    """Whether the line says the food it names has gone off.

    "my chicken smells a bit, can i cook it", "the milk has gone sour", "is my chicken still ok
    to eat". The rows that are about something else - a smell in the room, what is in a food -
    stand down on it, and `bot/knowledge/still_ok.py` answers.
    """
    if not isinstance(understood, dict):
        return False
    text = str(understood.get("plain") or understood.get("clean") or understood.get("text")
               or "").lower()
    words = tokens(text)
    if not words or not any(word in FOOD_NAMED for word in words):
        return False
    for phrase in OFF_STATE_ASKS:
        if phrase in text:
            return True
    for pos, word in enumerate(words):
        if word not in FOOD_NAMED:
            continue
        at = pos + 1
        while at < len(words) and words[at] in BEFORE_OFF:
            at += 1
        if at >= len(words):
            continue
        said = words[at]
        # "is ham processed meat bad for you" is a diet question: "bad" said *of* the food is a
        # smell, "bad for you" is the verdict a nutrition row gives.
        if said == "bad" and words[at + 1:at + 2] == ["for"]:
            continue
        if said in OFF_SAID_OF_FOOD:
            return True
        if said in SMELL_VERBS:
            after = words[at + 1:at + 2]
            if not after or after[0] not in A_GOOD_SMELL:
                return True
    return False


JOB_GUARD = ("repair", "repairs", "repaired", "repairing", "fix", "fixes", "fixed", "fixing",
             "install", "installs", "installed", "installing", "installation", "fit", "fits",
             "fitted", "fitting", "engineer", "engineers", "plumber", "plumbers", "callout",
             "call out", "call-out", "come out", "coming out", "swap", "swapping")


# "flat" is the word for a home and the word for a bake, a head of hair, a tyre and a note of
# music, and every row that keys one of those answers the others when the line is about where
# somebody lives: "my flat gets damp in winter" was the volume card (dry the hair upside down),
# "the flat gets baking in summer" the flat-bake card and "my flat gets cold" the run-of-colds
# card. The determiner is the difference - "my flat", "the flat", "in a flat" is a home, while a
# bare "flat" after hair, scone or tyre is not.
#
# It is a guard and not a word in the avoid list because an avoid phrase is read loosely: the
# words only have to be in the line, in any order and apart, so "my flat" in an avoid list threw
# away "my scones came out flat" and "my hair looks flat" - the very lines these rows are for.
# The guard reads the line itself, where the two words have to be next to each other.
#
# A verb of moving, renting or buying in front of the bare word is the same signal as the
# determiner: "we want to move flat before winter" has no "the" in it and still names a home,
# and it reached the seasonal-mood card while "we want to move the flat" did not - one word
# apart, opposite answers. "get my flat sorted" is the same home said as a job to do.
_FLAT_YOU_LIVE_IN = re.compile(
    r"\b(?:my|the|our|this|that|their|his|her|a|one)\s+"
    r"(?:tiny\s+|small\s+|little\s+|new\s+|old\s+|top\s+floor\s+|ground\s+floor\s+|"
    r"second\s+floor\s+|studio\s+)?flat\b"
    # a verb of moving, renting or buying takes the bare word as well as the determiner
    r"|\b(?:move|moves|moved|moving|rent|rents|rented|renting|let|letting|buy|buys|bought|"
    r"buying|sell|sells|selling|sold|view|viewing|sort|sorting|sorted|decorate|decorating|"
    r"refurbish|refurbishing)\s+(?:(?:a|an|the|my|our|this|that|his|her)\s+)?"
    r"(?:tiny\s+|small\s+|little\s+|new\s+|old\s+)?flat\b"
    # a verb that is also about a bake needs the determiner: "heat my flat", never "heat flat"
    r"|\b(?:heat|heating|clean|cleaning)\s+(?:a|an|the|my|our|this|that)\s+"
    r"(?:tiny\s+|small\s+|little\s+)?flat\b"
    r"|\bflats\b|\bflat\s?mates?\b|\bbedsit\b", re.IGNORECASE)


# "Heated" of people is an argument, not warmth. "my husband got heated at the table last night"
# was the hot-night card ("Cool the room rather than the bed") and "things got heated at dinner"
# the quick-dinner row, both on the word alone: a row is a different subject with its own card
# (row-escalating), and no temperature row is about it. "got heated up" is left out, because a
# radiator and a plate of food do heat up.
_THE_HEAT_OF_AN_ARGUMENT = re.compile(
    r"\b(?:got|get|gets|getting|bit|a bit|so|very|really|quite|all)\s+heated\b(?!\s+up)"
    r"|\bheated\s+(?:with|at|about|over|argument|arguments|discussion|discussions|row|rows|"
    r"debate|debates|exchange|exchanges|words|moment|moments|conversation)\b",
    re.IGNORECASE)


def not_the_heat_of_an_argument(understood):
    """True unless the line's "heated" is people or a row rather than a room or a night.

    A guard for the rows that read a temperature, so the words stay in the knowledge base: the
    reading of the line comes from the understanding engine, and this only asks whether the
    word in this line is the warmth the row is about.
    """
    if not isinstance(understood, dict):
        return True
    said = understood.get("text") or understood.get("clean") or ""
    if not said:
        said = " ".join(understood.get("words") or ())
    return not _THE_HEAT_OF_AN_ARGUMENT.search(str(said))


def not_the_flat_you_live_in(understood):
    """True unless the line's "flat" is the home, for a row that keys flat as a bake or a hair."""
    if not isinstance(understood, dict):
        return True
    said = understood.get("text") or understood.get("clean") or ""
    if not said:
        said = " ".join(understood.get("words") or ())
    return not _FLAT_YOU_LIVE_IN.search(str(said))


# "flat" of a thing somebody made is how it turned out, not what the ground is: "the bread came
# out flat" was answered with a canal towpath ("a flat riverside path"), and so were a cake, a
# pizza, a Yorkshire pudding and an omelette. The bake rows key their own names (bread-rise has
# "flat" in its key), so this only has to stand a walking row aside where the flat thing came out
# of an oven or a pan - either named, or read from the verb that says it turned out that way.
_A_BAKE_OR_A_PAN = re.compile(
    r"\b(?:bread|breads|loaf|loaves|cake|cakes|sponge|scones?|pastry|pastries|tarts?|buns?|"
    r"rolls?|pizza|pizzas|pancakes?|omelettes?|omelets?|yorkshires?|puddings?|meringues?|"
    r"souffles?|biscuits?|cookies?|brownies?|crumpets?|dough|naan|pittas?|pita|ciabatta|"
    r"focaccia|baguette|batter|sourdough|flatbread|chapatis?|tortillas?|waffles?|loaf tin)\b",
    re.IGNORECASE)

# The same reading without naming the food: "came out flat", "turned out flat" are about what was
# being made, unless the line is about the ground underfoot ("the path looked flat on the map").
_CAME_OUT_FLAT = re.compile(
    r"\b(?:came|come|comes|coming|turned|turns|turning|went|gone|goes|going)\s+"
    r"(?:out\s+)?(?:a\s+bit\s+|a\s+little\s+|really\s+|so\s+|rather\s+|too\s+)?flat\b",
    re.IGNORECASE)

_THE_GROUND_UNDERFOOT = re.compile(
    r"\b(?:walk|walks|walking|walked|stroll|strolls|hike|hikes|route|routes|path|paths|"
    r"towpath|trail|trails|terrain|ground|fields?|park|parks|promenade|seafront|beach|"
    r"miles?|kilometres?|outing|day out|somewhere to go|wheelchair|buggy|pram|pushchair)\b",
    re.IGNORECASE)


def not_the_flat_of_something_made(understood):
    """True unless the line's "flat" is how a thing somebody made turned out.

    A guard for the row that reads flat as the ground: "the bread came out flat" is the loaf, and
    the bake rows have their own answers for it.
    """
    if not isinstance(understood, dict):
        return True
    said = understood.get("text") or understood.get("clean") or ""
    if not said:
        said = " ".join(understood.get("words") or ())
    said = str(said)
    if not re.search(r"\bflat\b", said, re.IGNORECASE):
        return True
    if _A_BAKE_OR_A_PAN.search(said):
        return False
    if _CAME_OUT_FLAT.search(said) and not _THE_GROUND_UNDERFOOT.search(said):
        return False
    return True


def entry(id, key, reply, avoid=(), bias=0, ask=(), slips=(), fault=False,
          report=False, guard=None, shape=(), explain=False, lead=""):
    """Build an Entry. key: words, phrases, or tuples of alternatives for one key.

    bias: a nudge when two entries fit a line equally well, for the more specific one
    (a named dish or ingredient beats a general technique). Use 1, rarely 2.
    ask: optional words or phrases that must also appear, for an entry that is only
    an answer when the line is actually asking (a factual "how many weeks in a year"
    should not fire on "I'm away for three weeks in a year", let alone on a month
    named in passing). Empty means the key alone is enough.
    slips: key words that are misspellings of another key word, not words of their own.
    A table of hard spellings has to hold "adress" next to "address", and if both count as
    words then the slip repair around them sees two near-miss neighbours in two families and
    gives up: "who do i tel about my new adress after moving" stopped reaching the address
    entry and got the shrug. A slip still matches its own entry; it is only kept out of the
    vocabulary that decides what is a word and what is a misspelling.
    report: the complaint this answer is about can be *stated* as well as asked about, so a
    line that is nothing but "i have <subject>", "ive got <subject>" or "i keep getting
    <subject>" is a request for it. Opt in only on rows where naming the complaint is the
    question (a symptom in your own body), never on a row whose subject is a thing somebody
    might own or want: "i have a dog" is not a question about looking after one.
    guard: optional `fn(understood) -> bool`; the entry answers only when it returns true.
    Use it where the reading, not a word in the line, says the key means something else.
    shape: callables given the line's words as one string, each True when the line holds a
    figure of the kind this row is about ("4%" for a phone's charge). A shape that matches is
    one signal - the same weight as a key word - so the row still needs its subject in the
    line, and a row with no shape is read exactly as before.
    lead: the sentence the row owes a line that wants one shape of answer, in the row's own words
    ("Usually, yes", "About 20 minutes"). `bot/compose/lead.py` puts it in front when the line's
    `wants` is the shape the sentence gives and the card does not already open with it; a card
    that opens with the answer, and every other shape of line, is left exactly as it is. Use it
    on a card that is written for the harder question and has the plain one to answer as well.
    explain: the row answers a named thing, so a plain request to explain it is its question:
    "what is sepsis", "tell me about gout", "explain shingles". The ask has to sit in front of
    the subject with nothing but the ask's own words between ("what is the best way to clean a
    sofa" is a request for a method, not for a sofa), and the subject counts as one signal the
    way a stated complaint does.
    """
    return Entry(id, key, reply, _avoid_words(avoid), bias, ask, slips, fault, report, guard,
                 shape, explain, lead)


# The "-'s" words that are contractions of "is" or "has", never a possessive.
_CONTRACTION = frozenset((
    "it's", "what's", "that's", "there's", "here's", "he's", "she's", "who's", "where's",
    "when's", "why's", "how's", "let's", "this's", "one's", "everyone's", "someone's",
    "nothing's", "everything's", "nobody's",
))

# Plurals that are not made by adding "s": the singular ends in -f or -fe instead. Stripping
# the "s" from these gives a different word that people use all day - "leave" from "leaves",
# "lif" from "lives" - so a key of "leaves" was answered by "leave my phone charging".
IRREGULAR_PLURALS = {
    "leaves": "leaf", "loaves": "loaf", "sheaves": "sheaf", "thieves": "thief",
    "wolves": "wolf", "shelves": "shelf", "selves": "self", "elves": "elf",
    "halves": "half", "calves": "calf", "scarves": "scarf", "wharves": "wharf",
    "hooves": "hoof", "knives": "knife", "wives": "wife", "lives": "life",
}


# A curly apostrophe is what a phone writes by default, so "isn’t eating" has to read as
# the same line as "isn't eating". Without this the word split in two ("isn", "t") and a key
# holding "isnt eating" could never match.
_CURLY = str.maketrans({"’": "'", "‘": "'", "ʼ": "'"})
_CURLY_ANY = ("’", "‘", "ʼ")


def _doubles_for_an_ending(stem):
    """True when the final doubled consonant of a stem comes from the ending, not from the word.

    "stopp" in "stopping" and "runn" in "running" are one letter short of the word, so the
    doubled "p" and "n" go and "stop"/"run" can still meet a key. "hiss", "add" and "egg"
    already are words: dropping a letter invents a different one - "hissing" was handing "his"
    to every key that said hissing, so "my dad is tired of his job" reached the puncture
    instructions, and "passed" handed "pas". A doubled "s" is always the word's own, and the
    doubling an ending makes always sits on a consonant after a vowel ("stop", "run", "plan").
    """
    if len(stem) < 4 or stem[-1] != stem[-2] or stem[-1] in "aeiou" or stem[-1] == "s":
        return False
    # a doubled "l" is a spelling variant, not a doubled consonant of the inflection:
    # "misfuelled" is "misfuel" and "travelled" is "travel", whatever comes before it
    if stem[-1] == "l":
        return True
    # a vowel then a consonant in front of the pair: "st-o-pp", "r-u-nn", "pl-a-nn". The "u"
    # of "qu" is a consonant here: "quitting" is "quit", not "quitt" left alone.
    if stem[-3] not in "aeiou":
        return False
    return _is_consonant(stem, len(stem) - 4)


def _is_consonant(word, index):
    """True for the letter at index, reading the "u" of "qu" as the consonant it sounds."""
    if index < 0:
        return False
    letter = word[index]
    if letter not in "aeiou":
        return True
    return letter == "u" and index > 0 and word[index - 1] == "q"


def _forms(word):
    """The loose forms of a word, so eggs/egg and cooking/cook match each other.

    Two rules keep a loose form honest. A stem has to keep at least MIN_FORM letters to count
    (short stems are not words of their own: "weeing" strips to "we", and that one form made
    the cat litter entry answer "we had to put our cat down"). And a form is only handed out
    when the strip is a real ending of the word and the leftover is not a different word of its
    own: "bites" is not "bit", "cares" is not "car", "biting" is not "bit". Those reached a key
    word that has nothing to do with the line ("bit of a mad day" was answered as the
    sibling-hitting entry), and the person's real word still matches its own key, which lists
    the spelling it answers.

    The result comes from a cache and is a frozenset. The matcher asks for the same key word
    thousands of times a turn (once per entry that says it), and the forms of a word depend on
    nothing but the word, so working them out again was most of what a reply cost. A frozenset
    is returned because `find` writes the typo forms onto a line word with `|=`; on a cached set
    that would edit the copy for the rest of the conversation, on a frozenset the same line makes
    a new set.
    """
    got = _FORMS_CACHE.get(word)
    if got is not None:
        return got
    forms = _work_out_forms(word)
    frozen = frozenset(forms)
    if len(_FORMS_CACHE) >= _FORMS_CACHE_KEEP:
        _FORMS_CACHE.clear()     # a card of words, not a leak; the next turn fills it again
    _FORMS_CACHE[word] = frozen
    return frozen


_FORMS_CACHE = {}
# How many words the card holds before it is cleared. A reply asks for about 10,000 of them and
# a whole conversation adds a handful at a time: six long deck conversations, 48 turns between
# them, left the card at 10,013 with 104,749 questions already answered from it. So 50,000 is
# five times what a real conversation reaches, and it is what stops a very long one from holding
# a frozenset for every word it has ever seen.
_FORMS_CACHE_KEEP = 50000


def _work_out_forms(word):
    """The forms of one word, worked out from the endings and the tables (see _forms)."""
    # The understanding layer supplies the words, so the curly-apostrophe repair has to
    # happen here too, not only in tokens().
    word = word.translate(_CURLY)
    forms = {word}
    # The same word in the other spelling: "why does my bread go moldy so fast" reads as
    # "mouldy" (bot/understanding/lexicon.py, US_SPELLINGS) but the matcher had only the word
    # the person typed, so the entry keyed on "mouldy" never met the line and a mouldy loaf was
    # answered with a cooking-time entry - "Eggs are the fastest dinner there is". Nothing was
    # misspelt, so both spellings are the same word here and the reply still says the one they
    # used.
    other = lexicon.US_SPELLINGS.get(word)
    if other:
        forms.add(other)
    # A city and cities, a curry and curries: the plural is not an "s" on the end, so the
    # key word "city" never met "the best cities to visit" before. Only from six letters up:
    # "flies" would hand "fly" to the fruit flies, and "flying east" is jet lag, not a gnat.
    if word.endswith("ies") and len(word) > 5:
        forms.add(word[:-3] + "y")
    if word.endswith("y") and len(word) > 3 and word[-2] not in "aeiou":
        forms.add(word[:-1] + "ies")
    if word in IRREGULAR_PLURALS:
        # Only the real singular. The key word itself still matches a line that says it.
        forms.add(IRREGULAR_PLURALS[word])
        return forms
    # A possessive is the same thing: "my sister's birthday" is about a sister. Without this a
    # key only ever matched the plain form, so every possessive line fell through.
    # "-'s" after a pronoun or wh-word is a contraction ("what's", "it's", "there's"), not a
    # possessive: stripping it turned "What's one you'd love to see?" into the word "what", which
    # is in a few keys, and it answered a bird-feeding line in a conversation about herons.
    if word.endswith("'s") and len(word) > 3 and word not in _CONTRACTION:
        forms.add(word[:-2])
    elif word.endswith("s'") and len(word) > 3:
        # "the sisters' kitchen": the plural possessive is the plural.
        forms.add(word[:-2])
        forms.add(word[:-1])
    if len(word) > 3:
        if word.endswith("s") and not word.endswith("ss") and word not in NOT_A_WORD_WITH_AN_S:
            _add(forms, word[:-1])
        # "-es" is only a plural ending after a sibilant or an o: boxes, wishes, tomatoes. After
        # anything else the "e" belongs to the stem, and stripping both letters invents a word
        # nobody wrote: "bites" -> "bit", "notes" -> "not", "cares" -> "car", "stares" -> "star".
        # An "i" before the "-es" is the same plural: chillies, curries, berries, cookies,
        # countries. Every one of them lost its singular when the sibilant rule came in, and a
        # key on "chilli" stopped answering "the chillies are too hot". The invented forms the
        # rule exists to keep out (bites, notes, cares, stares) have a consonant there.
        if (word.endswith("es") and len(word) > 4
                and (word[-3] in "sxzi" or word[-4:-2] in ("ch", "sh") or word[-3] == "o")):
            _add(forms, word[:-2])
        if word.endswith("ed") and len(word) > 4:
            # "hated" is "hate" and a "d", not "hat", but dropping both letters handed a real word
            # to the entry all the same: a line asking "how do i knit a hat" met the two rows about
            # hating a job and was answered "Do the boring things first and most strict teachers
            # stop being a problem", "cared" handed "car" to a line about looking after a parent
            # and "moped" handed "mop". Only where the two letters less are a word of their own
            # does the e go back, and only for a word that is one: "replaced" keeps its old stem,
            # because "replac" is nothing and adding "replace" to the rows about a replaced knee
            # is what answered "how do i replace a shower head" with the washing-a-new-joint card.
            if _engine_reads(word[:-2]) and _engine_reads(word[:-1]):
                _add(forms, word[:-1])
            else:
                _add(forms, word[:-2])
            # Only a doubled consonant loses three letters: "stopped" -> "stop". Without this
            # guard "forced" also yields "for" and "started" yields "star", so a key would
            # match an ordinary word that has nothing to do with it.
            if len(word) > 5 and _doubles_for_an_ending(word[:-2]):
                _add(forms, word[:-3])
        if word.endswith("ing") and len(word) > 5:
            stem = word[:-3]
            _add(forms, stem + "e")
            # The same trap as above: "biting" is "bite", not "bit", and "caring" is "care",
            # not "car". A verb whose base really has that short shape doubles its consonant
            # before "-ing" ("stopping"), and that doubled stem is stripped below, so nothing is
            # lost by keeping the bare stem out of it.
            # A stem that ends in "y" never doubles it before "-ing" ("staying", "praying"),
            # so the bare stem is always the word: "stay" is not a short closed syllable with
            # a consonant stuck on the end, it is the word itself. Without this, `staying`
            # reached only `stay e`, and `saying`, `praying`, `worrying` lost their own word.
            if (word not in NOT_THE_STEM and stem not in NOT_A_BASE
                    and (not _cvc(stem) or (len(stem) > 2 and stem.endswith("y"))
                         or _bare_is_the_word(stem))):
                _add(forms, stem)
            # "stopping" -> "stop" and "running" -> "run", but a doubled "s" is the word's
            # own: dropping a letter from "hiss" invented "his", and any key that said hissing
            # then matched every line with "his", which is how "my dad is tired of his job"
            # reached the puncture instructions.
            if _doubles_for_an_ending(stem):
                _add(forms, stem[:-1])
    return forms


# A few "-ing" words are not their stem with an ending on it. "teething" is "teethe", and the
# "teeth" a matcher finds at the front of it is the plural noun of a different word: the card
# for caring for teeth answered "teething problems with the new puppy" with brushing steps, and
# the dentist entry answered "teething problems with the new car" with how to register with a
# practice. Only the bare stem is held back; "teething" and "teethe" still read.
# "Sugaring" is the same shape: the "sugar" at the front of it is the sweetener. The hair-removal
# card keys on "sugaring", so its "sugar" form was on that card too, and the card's own "how do i"
# topic word was the second signal it needed: "how do i cut down on sugar" and "best way to cut
# down on sugar" were answered with the shave. The card keeps "sugaring", "how to do sugaring at
# home" included; it loses only the bare stem.
# "Stuffing" is the same and the commonest of them all: "stuff" is how people say things they
# have not named ("can i make it with stuff from a corner shop", "how do i sell stuff on ebay"),
# so the stuffing recipe answered a corner-shop question with sage and onion. The row already
# stands down for the selling words; the plain "stuff" is the same slip and cannot be listed as a
# key word, because a key word is a word the line is about.
# "Evening" is the same shape and the most expensive of them: the "even" at the front of it is
# one of the commonest words in English ("even when i use it", "even though"), so a key on
# "evening" answered every line with an "even" in it. The phone-battery card never got its turn:
# "my phone keeps going flat even when i barely use it" was the bedtime-scrolling answer, and
# "my phone keeps going flat when i barely use it" was right, which is what a stray "even" costs.
NOT_THE_STEM = frozenset(("teething", "sugaring", "evening", "stuffing",
                          # "Skirting" is the same shape once more, and it cost a whole question:
                          # the "skirt" at the front of it is a cut of beef as far as the matcher
                          # could tell, so "how do i dust skirting boards" was a plain steak
                          # question - salt, acid, slice across the grain - and the skirting-board
                          # card, which keys on "skirting", never got its turn on "how do i hem a
                          # skirt" either. Only the bare stem is held back; "skirting" still reads.
                          "skirting",
                          # "Outing" is the same shape, and "out" is one of the commonest words
                          # there is: the walking row keys on "outing", so the "out" of "my
                          # sourdough keeps coming out flat" was that row's own subject, and a
                          # flat loaf was answered with a canal towpath - three separate lines
                          # ("the bread keeps coming out flat", "the loaf came out flat again").
                          # The row keeps "outing" and "outings"; it loses only the bare stem.
                          "outing"))

# A word that ends in "s" whose shorter form is a different word, which no key means to meet.
# "ages" is how long it has been - "i havent cooked in ages", "its been ages since i went out" -
# and the "age" inside it is the noun for growing old, so the ageing fact answered a person who
# had not cooked for months with what happens to cells, and any row keying "age" beside "when"
# or "how old" answered them as well. Every other plural still strips: this is a list of the
# words where the strip invents a meaning, not of plurals in general.
NOT_A_WORD_WITH_AN_S = frozenset(("ages",))


# The same shape as NOT_THE_STEM, but for a whole class of word rather than one at a time: a
# particle is never the base of the "-ing" word in front of it. "Outing" is a trip out, and
# "out" is not what it means, but the bare stem went onto it because the stem is not a short
# consonant-vowel-consonant shape and the only other test for it was `_bare_is_the_word`, which
# holds a list of 85 of the commonest words and "out" is not one of them. So "out" was a form
# of the easy-walk card's "outing", and it is one of the commonest words in an everyday line:
# "the cake came out flat" carried the card's own "flat" and its "out", which is the two
# signals every entry needs, and a bake that sank was answered with a canal towpath. The same
# stem reaches a phone that keeps "going" flat, a hinge that came "off", and anything a person
# says came "up".
# The verbs are left out on purpose: "go" and "work" are inside the same kind of word as
# "going" and "working", so a key on "go" has to answer a line that says "going", and the
# damage above is done by the particles, which are never the thing a sentence is about.
NOT_A_BASE = frozenset(
    "about above across after against along among around at before behind below beneath "
    "beside besides between beyond by down for from in into near of off on onto out over "
    "past since through till to toward towards under until up upon with within without".split())


def _add(forms, form):
    """Keep a derived form only when it is long enough to be a word in its own right."""
    if len(form) >= MIN_FORM:
        forms.add(form)

# A question about this chat is the memory store's turn, never a fact's. The understanding layer
# carries the words of the last few lines along with the new one, so "how did we start?" after a
# chat about saving read as "how do I start saving" and a knowledge entry answered it. The check
# runs on the words the person typed, not on those the memory adds.
_CHAT_PHRASES = (
    r"how did we (?:start|begin|get started|meet)"
    r"|how did (?:this|our|the) (?:chat|conversation) (?:start|begin|go)"
    r"|(?:start|beginning) of (?:this|our|the) (?:chat|conversation)"
    r"|what did (?:i|we) (?:say|ask|tell you) (?:first|at the start|at the beginning)"
    r"|what was (?:the first thing|my first (?:question|line|message))"
    r"|first (?:thing|question|line|message) (?:i|we) (?:asked|said|sent)(?: you| him| her)?"
    r"|do you (?:remember|recall) what (?:i|we) (?:said|asked|told)(?: you)?(?: first)?"
    r"|what have we (?:talked|spoken) about"
    r"|what did we talk about"
)
# Only the chat's own words may follow: "how did we start?" is about the chat, and "how did we
# start saving for a house" is about the house.
_CHAT_TAIL = (r"(?:\s+(?:out|then|here|it|this|that|chat|conversation|talking|off|again|"
              r"everything))*\s*")
_ABOUT_THE_CHAT = re.compile(r"(?:^|\s)(?:" + _CHAT_PHRASES + r")" + _CHAT_TAIL + r"$")


def about_the_chat(own_line):
    """True when the line asks about this conversation rather than about the world.

    This runs on the words the person typed ("text"), not on the reading's words: a follow-up is
    re-read with the memory's topic words added ("how did this chat start save car"), and those
    are exactly what made a fact answer a question about the chat.
    """
    return bool(_ABOUT_THE_CHAT.search(" ".join(tokens(str(own_line or "")))))


def _bare_is_the_word(stem):
    """Whether a short consonant-vowel-consonant stem may stand for the word that was written.

    "opening" -> "open" yes: the stem is a word the understanding engine reads and adding an
    "e" to it makes a word nobody writes. "biting" -> "bit" no: both are words, and the person
    meant "bite". "hating" -> "hat" no, for the same reason. A function word is never the base
    of a longer word. When the engine cannot read the stem at all ("stares" -> "star") it is not
    a base either, because nobody wrote it. The cost is that a word the engine does not know
    loses that one reading; the entry that answers it lists the spelling, as a key always can.
    """
    return (_engine_reads(stem) and not _engine_reads(stem + "e")
            and stem not in _FUNCTION_WORDS)


# Words that carry grammar rather than meaning: a longer word never has one of these as its base.
_FUNCTION_WORDS = frozenset(lexicon.CORE.split())


def _cvc(stem):
    """Whether a short stem is consonant-vowel-consonant: "bit", "car", "hat", "hop".

    A short word of that shape after stripping "-ing" is nearly always a different word of its
    own ("bit" for "biting", "car" for "caring") rather than the base of the word that was
    written, so it needs a second look before it is handed out. Longer stems are left alone:
    "gardening" is "garden", and its last three letters being consonant-vowel-consonant says
    nothing.
    """
    if not 3 <= len(stem) <= 4:
        return False
    vowels = "aeiou"
    return stem[-1] not in vowels and stem[-2] in vowels and stem[-3] not in vowels


def tokens(text):
    """The loose words of a line, lower case, for matching against keys."""
    return WORD.findall(text.translate(_CURLY).lower())


# The throat-clearing in front of a hand-off: "and", "oh", "so", "sorry," before "one more thing".
_THROAT = re.compile(
    r"^(?:(?:and|oh|ooh|ok|okay|so|but|right|ah|er|um|umm|hmm|sorry|also|just|plus|hey|ta|"
    r"anyway|anyways|then|actually|well)\b[\s,:-]*)+")
# What carries a line from the hand-off to what it is about, and goes with it: "one more thing
# about the boiler" is a line about the boiler, and so is "the other thing is my back hurts".
# Only punctuation or one of these makes the lead-in an announcement: "the last thing i need is
# another bill" is one sentence and every word of it counts.
_BRIDGES = tuple(lexicon.HANDOFF_BRIDGES) + ("is", "was")
_BRIDGE = re.compile(r"^\s*(?:" + "|".join(re.escape(one) for one in
                                            sorted(_BRIDGES, key=len, reverse=True))
                     + r")\b[\s,.:;\-\u2013\u2014]*")
_PUNCTUATION = re.compile(r"^\s*[,.:;\-\u2013\u2014]+[\s,.:;\-\u2013\u2014]*")


def _past_a_handoff(clean):
    """The line after a hand-off at its front, or None when it does not open with one.

    "one more thing about the boiler" and "quick question, how do i descale a kettle" announce a
    question and then ask it. The announcement is not what the line is about: nothing in "one
    more thing" should be matched against a key, or an entry keyed on "one" and "thing" answers a
    line that was about the boiler. Only a hand-off that is followed by what it announces is
    dropped, so a bare "one more thing" keeps every word it typed and is answered by whoever
    reads the line itself (bot/compose/handoff.py).
    """
    text = _THROAT.sub("", " ".join(str(clean or "").lower().split()))
    for lead in sorted(lexicon.HANDOFF_LEADS, key=len, reverse=True):
        if not text.startswith(lead):
            continue
        rest = text[len(lead):]
        after = None
        punctuation = _PUNCTUATION.match(rest)
        if punctuation:
            after = rest[punctuation.end():]
        else:
            bridge = _BRIDGE.match(rest)
            if bridge:
                after = rest[bridge.end():]
        if after is None:
            continue  # "the last thing i need is another bill" is one sentence
        bridge = _BRIDGE.match(after)  # "one more thing, about the boiler"
        if bridge:
            after = after[bridge.end():]
        return after.strip(" ,.:;\t\u2013\u2014") or None
    return None


# A line about somebody the person looks after, and what is wrong with them: "my daughter has
# head lice", "our baby's got conjunctivitis", "my son caught chickenpox". The person is not asking
# about the child, they are asking what to do about the thing - and the card that answers it is
# keyed on the thing ("head lice", "conjunctivitis"), never on the child. Read as typed the line
# reached no entry, so the composer's line for a carer answered it: "Being the one looking after
# them is its own kind of tiring. What have you noticed so far?" while "Wet-comb the whole head
# with a fine-tooth lice comb..." was one word away.
CARER_FRAME = re.compile(
    r"^\s*(?:my|our|the)\s+(?:poor\s+|little\s+|eldest\s+|youngest\s+|old\s+|new\s+)?"
    r"(?:son|sons|daughter|daughters|child|children|kid|kids|baby|boy|girl|toddler|teen|"
    r"teenager|mum|mam|mom|mother|dad|father|wife|husband|partner|boyfriend|girlfriend|"
    r"sister|brother|niece|nephew|grandson|granddaughter|grandchild|grandchildren|"
    r"friend|mate)\s*(?:'s|s')?\s+"
    r"(?:has|have|had|got|caught|come down with|came down with|is|are|was|were|"
    r"keeps getting|came out in|is covered in|has come out in)\s+"
    r"(?:(?:an?|the|some)\s+)*", re.I)


# What makes the thing wrong with somebody an illness rather than an event: a part of the body
# (`lexicon.BODY_PARTS`), the everyday symptom, or a condition with a name. "my son has a birthday
# next week" and "my wife has a job interview" are not this, and reading them as an ask about the
# thing answered a party and an interview with a card about the thing named in them.
AN_ILLNESS = re.compile(r"\b(?:" + "|".join(sorted(lexicon.BODY_PARTS)) + r"|" + "|".join("""
ill unwell poorly sick sickness bug bugs virus infection infected cold flu fever temperature
cough coughing sneeze sneezing wheeze wheezing breath breathing rash itchy itching itch spot
spots lump lumps sore pain painful ache aching hurt hurts injury injured wound cut gash burn
scald scab bruise bruised swelling swollen stiff sprain strain break broken fracture
dislocated dizzy fainting faint vomit vomiting diarrhoea diarrhea constipation dehydrated
dehydration allergy allergic reaction hives eczema psoriasis asthma croup colic teething
chickenpox measles mumps rubella tonsillitis thrush nits lice worms threadworms ringworm
verruca verrucas wart warts boil boils abscess stye conjunctivitis earache toothache headache
migraine migraines pneumonia bronchitis covid shingles gout sciatica arthritis cystitis uti
scabies impetigo meningitis quinsy coldsore epilepsy seizure
seizures dementia alzheimers diabetes anaemia thyroid tumour leukaemia cancer stroke
""".split()) + r")(?:s|es)?\b", re.I)


def _past_the_carer(clean):
    """The thing wrong with the person they look after, or None when the line is not that shape.

    "my daughter has head lice" is a question about head lice; whoever types it wants the comb and
    the conditioner, not a word about how hard caring is. Only the words that name the child and
    the having are dropped, so a line that also says what they want - "my son has chickenpox and
    wont eat" - is read on its own remaining words like any other line. A state of somebody's life
    is not an illness and is left to the reader that knows it (`AN_ILLNESS`).
    """
    text = " ".join(str(clean or "").lower().split())
    found = CARER_FRAME.match(text)
    if not found:
        return None
    left = text[found.end():].strip(" ,.:;\t")
    words = [word.strip(_MARKS) for word in left.split() if word.strip(_MARKS)]
    if not words:
        return None
    # The thing named is the head of the phrase, so an illness word at the end of it is the thing
    # ("a bad back", "sore throat", "head lice"), and a short phrase may name it first ("a rash that
    # doesnt fade"). An illness word anywhere in a long phrase is not the thing: "my brother was
    # hanging back at the party" has "back" in it and is a party.
    if AN_ILLNESS.fullmatch(words[-1]) or (
            len(words) <= 3 and any(AN_ILLNESS.fullmatch(word) for word in words)):
        return left
    return None


# "the pub was dead quiet last night": before a describing word, "dead" says how it felt. It is
# not a symptom ("my hand has gone dead" is one), so it is not a word to match a key against -
# the numb-hands entry keyed on it answered the pub with carpal tunnel syndrome. The words after
# it stay, so a line about being tired is still about being tired. The composer reads the same
# word the same way (bot/compose/trouble.py, DEAD_AS_VERY_AFTER).
DEAD_AS_VERY_AFTER = frozenset((
    "quiet", "tired", "easy", "good", "bad", "cheap", "slow", "boring", "cheerful", "glad",
    "lucky", "proud", "keen", "jealous", "happy", "sure", "tricky", "hard", "funny", "rude",
    "straight", "wrong", "serious", "certain", "ahead", "silent", "knackered", "shattered",
    # the same idiom with the describing word after "and": "it was dead easy and dead quick" is
    # two ways of saying the same easy, so the second word has its own description in front
    # "dead" before a describing word says how much, and the composer's trouble panel was reading
    # it as a broken thing: "my trainers are dead comfy" -> "Annoying. Is it every time, or only
    # now and then?", "my new bed is dead comfortable" -> "Right. What have you tried so far?",
    # "the sofa is dead soft" -> the same panel. The adjectives people actually put it in front of:
    "comfy", "comfortable", "soft", "cosy", "cozy", "warm", "cold", "nice", "sweet", "pretty",
    "smooth", "strong", "fussy", "broke", "skint", "fun", "obvious", "scary", "gentle", "relaxed",
    "bright", "dark", "loud", "chuffed", "mint", "annoying", "embarrassing",
    "quick", "fast", "clean", "simple", "smart", "friendly", "heavy",
))


def _without_a_dead_that_only_means_very(words):
    """The line's words with a "dead" that describes the next word taken out."""
    kept = []
    for index, word in enumerate(words):
        following = words[index + 1] if index + 1 < len(words) else ""
        if (str(word).lower() == "dead"
                and str(following).lower().strip(_MARKS) in DEAD_AS_VERY_AFTER):
            continue
        kept.append(word)
    return kept


_MARKS = string.punctuation + "\u2019"


# The food nouns that make a "cooking" in front of them part of a name: "cooking oil" and
# "cooking apples" are things in a cupboard, not food that has been cooked.
COOKING_AS_A_NAME = frozenset(("oil", "oils", "apple", "apples", "chocolate", "bacon", "fat",
                               "sauce", "wine", "salt", "cream", "onions", "onion", "ham"))


def _without_a_cooking_that_is_a_name(words):
    """The line's words with a "cooking" that names a food taken out.

    "Cooking oil" is the name of what is in the bottle, not a statement that something was
    cooked. Read as the verb it made a shelf-life question into a cooked-food one: the
    cooked-food table in bot/knowledge/cooking.py keys on "cook" and on a keeping word, so
    "how do i store cooking oil" matched it twice and the oil's own keeping row lost the line,
    while "how do i store olive oil" reached the right answer. The participle that says a food
    was cooked is "cooked", which is not a word anyone wears in a name.
    """
    kept = []
    for index, word in enumerate(words):
        following = words[index + 1] if index + 1 < len(words) else ""
        if (str(word).lower() == "cooking"
                and str(following).lower().strip(_MARKS) in COOKING_AS_A_NAME):
            continue
        kept.append(word)
    return kept


# A child named by their place in the family names no son or daughter. "my youngest is up at
# five every morning" says which child it is, and every entry that keys on a child word (early
# waking, teething, a temperature, being sick, two children rowing) passed the line over: the
# everyday word for a child does the same. "my lad has a temperature" was answered "I'm
# listening" while "my son has a temperature" got the 111 line, and "my lad wont sleep" got a
# nagging line where "my son wont sleep" got the sleep answer. Both are read the same way, in
# the same place, so every entry that keys on a child reads them without naming them: the
# person's problem was written down and not answered, and the follow-up after it had nothing to
# read from. The word the entries key on is added to the line's own words instead, so all of
# them read it the same way, and only where the place word is the subject of the line.
CHILD_BY_PLACE = re.compile(
    r"\b(?:my|our|the|his|her|their)\s+(?:youngest|eldest|oldest|little\s+one|middle\s+one|"
    r"lad|lass|kiddo|laddie|un)\b"
    # A size word between the possessive and the child does not stop it being the child, and
    # "my little lad wont sleep" was answered "Right. What have you tried so far?" where "my lad
    # wont sleep" got the sleep card: the phrase above wanted the two words side by side. The
    # size word is also what makes the plain words for a child safe to read - "my little boy" and
    # "my little man" are a child, while "my boy" on its own can be a grown man or a partner, so
    # those are left alone.
    r"|\b(?:my|our|the|his|her|their)\s+(?:little|small|wee|big|older|elder|younger|poor)\s+"
    r"(?:youngest|eldest|oldest|one|lad|lass|kiddo|laddie|un|boy|girl|man)\b",
    re.I)
# The words the phrase above is made of, which become the child word.
CHILD_PLACE_WORDS = frozenset(("youngest", "eldest", "oldest", "little", "middle"))
# The size word in "my little lad" is not the child, so it is dropped rather than read as one:
# "my child child wont sleep" still matches, but the line reads cleaner as "my child wont sleep".
CHILD_SIZE_WORDS = frozenset(("little", "small", "wee", "big", "older", "elder", "younger",
                              "poor"))
# A plain word for a child, which is only a child after a size word: "my little boy" and "my wee
# girl" are children, and "my boy" or "my girl" on their own may be a partner, so they stay out of
# EVERYDAY_CHILD.
CHILD_AFTER_A_SIZE = frozenset(("boy", "girl", "un", "man"))
# The everyday word for a child, which is the same child: "my lad has a temperature" was answered
# "I'm listening" while "my son has a temperature" got the 111 line, and "my lad wont sleep" got a
# nagging line where "my son wont sleep" got the sleep answer.
EVERYDAY_CHILD = frozenset(("lad", "lass", "kiddo", "laddie"))
# A size word makes a plain word for a child ("my little girl") safe to read, and it says nothing
# about how old the child is: a parent writes "my little girl is 12" about a twelve-year-old, and
# she was walked back to bed like a two-year-old. Eleven is where the toddler rows stop being the
# answer, and the words for a secondary school child say the same thing without a number.
# The phrase as it was before the size word was allowed: the possessive and the word for the
# child side by side. "my lad is 14" was always read as a child and then left alone by A_TEEN,
# and that path is unchanged; the size word is the new one, and it is what stands down here.
A_CHILD_WORD_BY_ITSELF = re.compile(
    r"\b(?:my|our|the|his|her|their)\s+(?:youngest|eldest|oldest|little\s+one|middle\s+one|"
    r"lad|lass|kiddo|laddie)\b", re.I)
A_CHILD_GETTING_OLDER = re.compile(
    r"\b(?:teenager|teenagers|teen|teens|teenage|teenaged|secondary\s+school|high\s?school|"
    r"senior\s+school|year\s+(?:7|8|9|10|11))\b"
    # "is 11 months" and "is 18 months" are babies, and the number alone cannot tell them apart
    # from a child of eleven, so a count in months or weeks is not an age in years.
    r"|\b(?:is|are|aged?|turned|turns|turning|now|nearly|just)\s+"
    r"(?:1[1-9]|eleven|twelve|thirteen|fourteen|fifteen|sixteen|seventeen|eighteen|nineteen)\b"
    r"(?!\s*(?:months?|mths?|weeks?|mos?)\b)"
    r"|\b(?:1[1-9]|eleven|twelve|thirteen|fourteen|fifteen|sixteen|seventeen|eighteen|nineteen)"
    r"\s*(?:year|yr)s?\s*old\b", re.I)
# ...unless the line names a teenager, who is not the small child these rows are for: "my lad is
# 14 and he wont get out of bed in the morning" keeps the answer "my son is 14 ..." gets, and the
# age is written without "year old" as often as with it.
A_TEEN = re.compile(
    r"\b(?:teenager|teenagers|teen|teens|teenage|teenaged)\b"
    # the age as written and as the reading spells it: "my lad is 14" reaches here as "fourteen"
    r"|\b(?:is|are|aged?|turned|turns|turning|now)\s+"
    r"(?:1[3-9]|thirteen|fourteen|fifteen|sixteen|seventeen|eighteen|nineteen)\b"
    r"(?!\s*(?:week|weeks|month|months|day|days|hour|hours|stone|stones|kilos?|kg|lbs?|pounds?))",
    re.I)
# ...unless the line names what is being counted, which is the other half of every "the little
# one": "the little one of the two dogs" is a dog, and "the youngest" in a line about a husband
# is not a child either. The word is only added when nothing here says otherwise.
NOT_A_CHILD_SAID = frozenset("""dog dogs puppy puppies cat cats kitten kittens rabbit rabbits
    hamster hamsters guinea bird birds parrot parrots fish horse horses pony ponies ferret
    pet pets husband wife partner boyfriend girlfriend fiance fiancee friend friends mate mates
    boss colleague colleagues flatmate flatmates housemate housemates neighbour neighbours
    tenant tenants mum mother dad father nan nanna gran granny grandad grandpa sister brother
    aunt uncle cousin nephew niece""".split())


# "Me and my lad want to grow some veg this year" is the person and their child doing something
# together, not a question about the child. Read as a child line it reached the entry for a
# child's growth ("a child who is losing weight or not growing") and lost the grow-your-own
# answer it used to get, so a line that puts the person first names no child by itself.
# "and" is typed "n" as often as it is typed at all ("me n my little lad"), and the size word is
# what put this line inside the phrase above: "me n my little lad want to grow some veg" lost the
# grow-your-own answer to the growth card. The joiner is the whole of the test, so every way of
# typing it belongs here.
TWO_OF_US = re.compile(r"\A\s*(?:me|i|us)\s*[,&]?\s*(?:and|an|nd|n)\s+(?:my|our|mine)\b", re.I)


def _with_the_animal_in_hand(words, understood):
    """The line's words with the animal it only points at, named where the pronoun stands.

    A follow-up after a turn about a pet is about that pet: "she's been drinking a lot more
    water", "how much should he eat", "hes getting slow on walks". Nothing in those lines says
    which animal, so every entry keyed on a cat or a dog missed them and the answer for a person's
    own body took the turn - the daily figure for drinking water went to a cat, and a dog with a
    sore ear got the ear card for a person. The understanding engine has already worked out what
    the pronoun points at (`animal_in_hand`), so the animal goes where the pronoun stands: an
    entry that matches spans of positions still reads the line as it was typed.
    """
    animal = (understood or {}).get("animal_in_hand") or ""
    if not animal:
        return words
    kept = []
    for piece in words:
        low = str(piece).lower().strip(_MARKS).split("'")[0]
        kept.append(animal if low in _THE_PRONOUNS else piece)
    return kept if kept != list(words) else words


# The pronouns a follow-up points back at an animal with, as typed and without the apostrophe.
_THE_PRONOUNS = frozenset("""it its itself he him his himself hes hed she her hers herself shes
    shed they them their theirs theyre theyd this these those""".split())


def _the_animal_rules_out_that_card(item, understood):
    """True when the animal the line only points at is a word the card that took the turn avoids.

    A card carries in its avoid list the words that make it the wrong answer - the figure for a
    person's water says "cat", "dog", "puppy", "litter tray" - so a card whose avoid list holds
    the animal is a card written for somebody else and reached only because the line says "she"
    rather than "the cat".
    """
    animal = (understood or {}).get("animal_in_hand") or ""
    if not animal:
        return False
    stood_down_for = {str(word).lower() for word in getattr(item, "avoid", ()) or ()}
    return animal in stood_down_for or animal + "s" in stood_down_for


def _with_the_child_by_place(words, clean):
    """The line's words with the child it names by place or by an everyday word, when it does.

    The added word goes at the end: an entry has already matched spans of positions into this
    list (see `_frame_masked`), so nothing may move. A line that names an animal or a grown-up
    is left exactly as it came, which is also what keeps "the little one" about a dog the dog's
    question.
    """
    line = str(clean or "")
    if not CHILD_BY_PLACE.search(line) or TWO_OF_US.match(line):
        return words
    small = not A_TEEN.search(line)
    said = {str(word).lower().strip(_MARKS) for word in words}
    if said & NOT_A_CHILD_SAID:
        return words
    # The place word becomes the child word where it stands, so the line reads exactly as it
    # would had they said "my child": "my youngest has a temperature" is answered by the entry
    # "my child has a temperature" is answered by, rather than by whichever entry a spare word
    # at the end happens to favour.
    kept = []
    skipping = 0
    # The size word is what reads a plain word for a child ("my little girl"), and it says nothing
    # about how old that child is: "my little girl is 12 and wont go to bed" was a two-year-old's
    # bedtime handed to a twelve-year-old, and "my little lad is 14 and he wont get out of bed"
    # lost the answer main had. Where the size word is the only reason the phrase matched, an
    # older child stands the reading down and keeps the line it had.
    if A_CHILD_GETTING_OLDER.search(line) and not A_CHILD_WORD_BY_ITSELF.search(line):
        return words
    for at, word in enumerate(words):
        low = str(word).lower().strip(_MARKS)
        if skipping and (low == "one" or not low):
            skipping = 0
            continue
        skipping = 0
        child_word = low in CHILD_PLACE_WORDS or (small and low in EVERYDAY_CHILD)
        if low in CHILD_SIZE_WORDS:
            # "my little lad" is "my lad": the size word goes and the word after it is read as
            # the child. That word goes too when the line names a teenager, so "my little boy is
            # 14 and wont get up" stays the teenager's line instead of becoming a toddler's.
            after = next((str(word2).lower().strip(_MARKS) for word2 in words[at + 1:]
                          if str(word2).lower().strip(_MARKS)), "")
            if after in CHILD_PLACE_WORDS or after in CHILD_AFTER_A_SIZE or (
                    small and after in EVERYDAY_CHILD):
                continue
        if child_word or (small and low in CHILD_AFTER_A_SIZE
                          and at and str(words[at - 1]).lower().strip(_MARKS)
                          in CHILD_SIZE_WORDS):
            kept.append("child")
            skipping = 1 if low in ("little", "middle") else 0
            continue
        kept.append(word)
    return kept


def _one_edit(shorter, longer):
    """True when the two words are one slip apart: a letter wrong, missing, extra, or two
    neighbours swapped."""
    if shorter == longer:
        return True
    if abs(len(shorter) - len(longer)) > 1:
        return False
    if len(shorter) > len(longer):
        shorter, longer = longer, shorter
    i = 0
    while i < len(shorter) and shorter[i] == longer[i]:
        i += 1
    if len(shorter) < len(longer):
        return shorter[i:] == longer[i + 1:]        # one letter missing or extra
    rest, tail = shorter[i:], longer[i:]
    if rest[1:] == tail[1:]:
        return True                                 # one letter wrong
    return (len(rest) > 1 and rest[0] == tail[1] and rest[1] == tail[0]
            and rest[2:] == tail[2:])               # two neighbours swapped ("rubbrey")


def _stem(word):
    """The word a form belongs to, so radiator/radiators and tomato/tomatoes are one."""
    for ending in ENDINGS:
        if word.endswith(ending) and len(word) - len(ending) >= 3:
            return word[: -len(ending)]
    return word


_COMMON = frozenset(lexicon.COMMON.split()) | frozenset(lexicon.CORE.split())
# ... and the word each of them comes from, so "charging" counts as read when "charger" does.
_STEMS = frozenset(_stem(word) for word in _COMMON) | _COMMON


def _engine_reads(word):
    """True when the understanding engine already reads this word, as English or chat-speak.

    Such a word is not a typo, however close a key word looks: "park" is one letter from
    "pack", and it stays "park". The normaliser's own tables count too, so a chat form
    ("whats") is left to it. The word's family counts as well: "charging" is a form of an
    English word the engine knows a relative of ("charger"), so it is a word, not a slip
    from "changing", and a phone charging overnight stays out of the leaves fact.

    `lexicon.every_word()` is the rest of the reading's own vocabulary - the personal names, the
    topic and kind words, the parts of the body - gathered from those tables instead of listed
    again. The list this replaces was rebuilt one word at a time: "kate" was read as "kale",
    "preston" as "presto", "unfit" as "unit", "hiya" as "hoya", each found on the deck after it
    had already answered a line. A name bent into a key word is worse than a shrug, because the
    answer is confident and about another question: "enid", "elsie" and "esther" were read as
    "end", "else" and "either" ("my friend enid" got the after-a-breakup card), and "fella" and
    "bloke" as "fell" and "broke", so a line about who takes the credit at work was answered by
    the falls card for an elderly parent.
    """
    return (word in _COMMON or word in COMMON_WORDS or word in lexicon.CHAT
            or word in lexicon.EXPAND or _stem(word) in _STEMS
            or word in lexicon.every_word())


def _typo_forms(word, vocabulary):
    """The forms of the key word a misspelt line word is one slip away from, or nothing when
    the slip is ambiguous ("htis" could be two words, "lips" could be "lies" or "lids"), the
    word is too short to be sure, or the engine already reads the word as it is.

    Two key words of one family are one candidate, so a misspelt word still reaches an
    entry keyed on both "radiator" and "radiators"; two different families are none, so a
    slip that could be either of two meanings ("lips" for "lies" or "lids") says nothing.
    """
    if len(word) < MIN_TYPO_LENGTH or _engine_reads(word):
        return set()
    close = [other for other in vocabulary
             if other[:1] == word[:1] and abs(len(other) - len(word)) <= 1
             and _one_edit(word, other)]
    families = {_stem(other) for other in close}
    if len(families) != 1:
        return set()
    forms = set()
    for other in close:
        forms |= _forms(other)
    return forms


def _wanted(phrase):
    """The forms of each word of a key phrase, worked out once for every entry that says it."""
    got = _WANTED_CACHE.get(phrase)
    if got is None:
        got = tuple(_forms(word) for word in phrase.lower().split())
        if len(_WANTED_CACHE) >= _FORMS_CACHE_KEEP:
            _WANTED_CACHE.clear()
        _WANTED_CACHE[phrase] = got
    return got


_WANTED_CACHE = {}


def _shape(phrase):
    """(the words of a key phrase, its weight), worked out once for every entry that says it.

    _part_matches reads the words and the weight of every alternative of every key part it is
    asked about, and a line asks thousands of times: a phrase is a module-level constant, so
    its shape is worked out once instead of being lower-cased and split each time.
    """
    got = _SHAPE_CACHE.get(phrase)
    if got is None:
        words = tuple(phrase.lower().split())
        got = (words, PHRASE_WEIGHT if len(words) > 1 else WORD_WEIGHT)
        if len(_SHAPE_CACHE) >= _FORMS_CACHE_KEEP:
            _SHAPE_CACHE.clear()
        _SHAPE_CACHE[phrase] = got
    return got


_SHAPE_CACHE = {}


_WHERE = object()
_LINE_FORMS = object()
_PHRASE_SPANS = object()
_WANTING = object()
_ASK_ABOUT_SOMEONE = object()


def _line_forms(forms, seen):
    """Every form any word of the line has, worked out once for the line.

    A key phrase whose words are not all here cannot be in the line, so the answer is no before
    any of the positional work: the test is one set intersection per word, in C, and most of the
    8,900 key parts of the knowledge base are not about the line in front of them.
    """
    if seen is not None:
        got = seen.get(_LINE_FORMS)
        if got is not None and got[0] is forms:
            return got[1]
    every = set()
    for word_forms in forms:
        every |= word_forms
    every = frozenset(every)
    if seen is not None:
        seen[_LINE_FORMS] = (forms, every)
    return every


def _where(forms, seen):
    """{form: the positions in the line that have it}, worked out once for the line.

    Every entry the line reaches asks _phrase_span about its own key words, and each of those
    answers is a question about the same line, so the line is read into this map once instead of
    being walked again for every word of every key. `seen` is the line's memo (see _part_matches).
    The second map is where each form first appears: a single key word only needs the earliest
    position, and that is the question a line asks thousands of times.
    """
    if seen is not None:
        got = seen.get(_WHERE)
        if got is not None and got[0] is forms:
            return got[1], got[2]
    where = {}
    for index, word_forms in enumerate(forms):
        for form in word_forms:
            at = where.get(form)
            if at is None:
                where[form] = [index]
            else:
                at.append(index)
    firsts = {form: at[0] for form, at in where.items()}
    if seen is not None:
        seen[_WHERE] = (forms, where, firsts)
    return where, firsts


def _phrase_span(forms, phrase, seen=None):
    """The positions in the line this phrase covers, or () when it is not there.

    One position for a single word, several for a phrase, so score() can tell a line
    that mentions two different key words from one that repeats the same word twice.

    The answer is kept on the line's memo by the phrase itself. The same words are key phrases
    of many entries - "how long", "how do i", "without" - and every entry the line reaches asks
    about its own copy, so the answer was worked out thousands of times a turn.
    """
    spans = None
    if seen is not None:
        got = seen.get(_PHRASE_SPANS)
        if got is not None and got[0] is forms:
            spans = got[1]
        else:
            spans = {}
            seen[_PHRASE_SPANS] = (forms, spans)
        if phrase in spans:
            return spans[phrase]
        end = _phrase_span_work(forms, phrase, seen)
        spans[phrase] = end
        return end
    return _phrase_span_work(forms, phrase, None)


# The breathers people put in the middle of a phrase: "my phone just died", "the battery has
# finally gone", "the car nearly died on me". An avoid phrase is the pair of words that says what
# the line is about ("phone died"), and a word between them does not make it a different line -
# so the death-and-bills row stood down for "my phone died" and answered "my phone just died"
# with its bereavement team, which is the coldest reply in this file.
#
# Only an avoid list reads across a breather. A key phrase is the thing the row answers, and
# loosening a key would let a row answer a line it does not fit.
# "much" is gone from this list on purpose. It was read as a breather, so a fence of "how to"
# matched "how much to install a wood burner" and "how much to get a room decorated": the span
# allowed the "much" between the two words, and every price row that disowns "how to" (the fence
# that keeps a DIY answer off a price) then disowned the price question too. The person asking
# what a job costs got the method, a shopping list or a shrug. "how much" asks what it costs or
# how of it there is; it is not a softer "how", and the quantity is what the line is about. So a
# measure word is not a breather: the pair has to be about the same thing it always was.
_SAID_BETWEEN = frozenset("""
    just only nearly almost practically finally already still again now then even really
    actually suddenly completely totally literally basically quite very so too
    has have had is was were been being keeps kept
""".split())
_A_BREATH = 2


_ASK_FRAME_FORMS = None


def _ask_frame_forms():
    """The forms of ASK_FRAME, worked out once."""
    global _ASK_FRAME_FORMS
    if _ASK_FRAME_FORMS is None:
        _ASK_FRAME_FORMS = frozenset().union(*(_forms(word) for word in ASK_FRAME))
    return _ASK_FRAME_FORMS


def _phrase_span_between(forms, phrase, seen=None):
    """The span of an avoid phrase where a breather may sit between its words, or ().

    Two words at most may sit between any two words of the phrase, and each of them has to be a
    breather: "my phone has just died" is the same line as "my phone died", and "the phone rang
    and the cat died" is not.

    A phrase that opens on an asking word keeps its words together. The phrase is a way of asking
    there - "how do i", "how to", "what is", "is it" - and the asking words of two different
    questions sit next to each other across a line that asks one of them for a price: "how much
    to hire a breaker" has "how" and "to" with "much" between them, and every price row that
    stands down on "how to" (the whole cost table does) then refused the line, so the commonest
    way of asking what a hire costs had no answer at all. "my phone has just died" is what the
    breathers are for, and no asking phrase needs one.
    """
    if not isinstance(phrase, str):
        return ()
    wanted = _wanted(phrase)
    if not wanted:
        return ()
    if len(wanted) == 1:
        return ()
    if wanted[0] & _ask_frame_forms():
        return ()
    key = ("between", phrase)
    spans = None
    if seen is not None:
        got = seen.get(_PHRASE_SPANS)
        if got is not None and got[0] is forms:
            spans = got[1]
        else:
            spans = {}
            seen[_PHRASE_SPANS] = (forms, spans)
        if key in spans:
            return spans[key]

    def walk(at, next_word, span):
        if next_word == len(wanted):
            return tuple(span)
        gaps = 0
        while at < len(forms) and gaps <= _A_BREATH:
            if forms[at] & wanted[next_word]:
                got = walk(at + 1, next_word + 1, span + [at])
                if got:
                    return got
            if not (forms[at] & _SAID_BETWEEN):
                return ()
            gaps += 1
            at += 1
        return ()

    answer = ()
    for start in range(len(forms)):
        if forms[start] & wanted[0]:
            answer = walk(start + 1, 1, [start])
            if answer:
                break
    if spans is not None:
        spans[key] = answer
    return answer


def _phrase_span_work(forms, phrase, seen):
    """The phrase's span on this line, with no phrase memo in front of it."""
    wanted = _wanted(phrase)
    if not wanted:
        return ()
    n = len(wanted)
    if seen is not None:
        line = _line_forms(forms, seen)
        for word_forms in wanted:
            if not (word_forms & line):
                return ()
    if seen is None:
        # No line memo (a test calling score() on one line): walk the line itself, which is
        # what this did before the map, rather than building the map for a single question.
        if n == 1:
            for i, word_forms in enumerate(forms):
                if word_forms & wanted[0]:
                    return (i,)
            return ()
        for i in range(len(forms) - n + 1):
            if all(forms[i + j] & wanted[j] for j in range(n)):
                return tuple(range(i, i + n))
        return ()
    where, firsts = _where(forms, seen)
    if n == 1:
        # The earliest position of any form of the key word, found by letting the line's own
        # forms and the key word's forms meet in one set operation rather than one lookup each.
        if not wanted[0].isdisjoint(firsts):
            return (min(firsts[form] for form in wanted[0] if form in firsts),)
        return ()
    hits = []
    for word_forms in wanted:
        found = set()
        for form in word_forms:
            found.update(where.get(form, ()))
        if not found:
            return ()
        hits.append(found)
    # Every word of the phrase has to be in the line, in order, so only a position where the
    # first word sits can start it. Reading those in order gives the earliest span, which is
    # what walking the whole line found, without asking the other positions anything.
    for start in sorted(i for i in hits[0] if i + n <= len(forms)):
        if all(start + j in hits[j] for j in range(1, n)):
            return tuple(range(start, start + n))
    return ()


def _phrase_found(forms, phrase):
    return bool(_phrase_span(forms, phrase))


_PART_FORMS = {}
_PART_FORMS_KEEP = 20000


def _part_forms(part):
    """Every form of every word any alternative of this part says, worked out once per part."""
    got = _PART_FORMS.get(id(part))
    if got is not None and got[0] is part:
        return got[1]
    alternatives = part if isinstance(part, tuple) else (part,)
    every = None
    for alternative in alternatives:
        if not isinstance(alternative, str) or not alternative.strip():
            continue
        for word_forms in _wanted(alternative):
            if every is None:
                every = set()
            every |= word_forms
    if every is None:
        return None if not alternatives else frozenset()
    every = frozenset(every)
    if len(_PART_FORMS) >= _PART_FORMS_KEEP:
        _PART_FORMS.clear()
    _PART_FORMS[id(part)] = (part, every)
    return every


def _part_matches(part, forms, seen=None):
    """Every matching alternative of one key part: [(weight, its words, its span), ...].

    `seen` is this line's memo, a dict from the part's id to the answer. score() asks a part
    about the line and _rank() asks the same part again, and the answer does not depend on
    anything else, so the second question is not asked. The part belongs to a module-level
    entry, so it outlives the call and its id cannot be reused inside it.
    """
    if seen is not None:
        got = seen.get(id(part))
        if got is not None:
            return got
    every = _part_forms(part)
    if every is not None and not (every & _line_forms(forms, seen)):
        # not one word of any alternative is in the line, so no alternative can match, and the
        # answer needs no reading of the line: one set intersection instead of a phrase search
        # per alternative. The line reaches 700 entries and asks about 3 parts of each, so most
        # of what a scan used to do was this test, one alternative at a time.
        if seen is not None:
            seen[id(part)] = []
        return []
    alternatives = part if isinstance(part, tuple) else (part,)
    found = []
    for alternative in alternatives:
        if not isinstance(alternative, str) or not alternative.strip():
            continue
        span = _phrase_span(forms, alternative, seen)
        if span:
            words, weight = _shape(alternative)
            found.append((weight, words, span))
    found.sort(key=lambda hit: (hit[0], not _only_the_frame(hit[1])), reverse=True)
    if seen is not None:
        seen[id(part)] = found
    return found


def _part_match(part, forms, covered=(), seen=None):
    """The best matching alternative of one key part: (weight, its words, its span).

    An alternative that says something new about the line beats one that reuses a word
    already counted by another part, so ("rain", ("raining", "why")) scores on "why does
    it rain" from the "why", not from a second reading of "rain".
    """
    found = _part_matches(part, forms, seen)
    if not found:
        return (0, (), ())
    for weight, words, span in found:
        if not covered or not set(span) <= set(covered):
            return (weight, words, span)
    return found[0]


def _part_score(part, forms, seen=None):
    return _part_match(part, forms, seen=seen)[0]


def _own_words(item):
    """The single words this entry's own key already names, from its phrases as well.

    "self employed" is one key phrase, and "employed" inside it is a word the entry has
    already claimed: a row that keys it cannot then stay away from "employee" because the
    line says "self employed". `_misspelt_avoid` uses this to tell a slip from a subject.
    """
    words = set()
    for part in item.key or ():
        if isinstance(part, str):           # a part may be one phrase, not a list of them
            part = (part,)
        for key in part:
            if not isinstance(key, str):
                continue
            for word in key.strip().lower().split():
                if len(word) >= MIN_TYPO_LENGTH:
                    words.add(word)
    return words


def _misspelt_avoid(item, typed, own=None):
    """True when a line word is one slip from a word this entry stays away from.

    The forms of a repaired word already reach the avoid list, but a slip that two key
    words could explain ("brest" is "breast" or "best") is never used to read a line, and
    must still not be answered as the entry that disowns that word ("how long do i cook a
    chiken brest" is not a whole-bird question).

    A word the entry's own key names is not a slip, whatever the avoid list says: "self
    employed" is in start-a-business's key, "employee" is in its avoid, and "employed" was
    read as a slip of "employee", so "im thinking of going self employed" and "should i go
    self employed" were both refused by the one row that answers them.
    """
    if own is None:
        own = _own_words(item)
    for word in item.avoid:
        if not isinstance(word, str):       # an Entry built by hand, not through entry()
            continue
        key = word.strip().lower()
        if len(key) < MIN_TYPO_LENGTH or " " in key:
            continue
        for typed_word in typed or ():
            if typed_word in own:           # the entry's own subject, not a slip
                continue
            # a real word is never a slip of the avoid word: "does" is not "dogs", and the
            # sauce that does not need dog food still needs its seasoning answer
            if typed_word in own:
                continue
            if (len(typed_word) >= MIN_TYPO_LENGTH and not _engine_reads(typed_word)
                    and typed_word[:1] == key[:1] and _one_edit(typed_word, key)):
                return True
    return False


# A want is an ask. "i want to make a cake" and "i fancy making a curry" ask for the recipe as
# plainly as "how do i make a cake" does, and an entry that already keys the dish and the verb
# knows the line is about making one. Without this the ask guard below throws the line away, and
# the turn goes to a chat question ("Make a cake - fair enough. What's stopped it happening so
# far?") where the recipe belongs. The words are the ones that turn a thing into a request; a
# bare "i want cake" still reaches nothing, because the entry's own key needs the verb too.
WANTING = ("want to", "wants to", "wanted to", "wanting to", "would like to",
           "would love to", "feel like making", "feel like doing", "feel like baking",
           "feel like cooking", "fancy making", "fancy doing", "fancy baking",
           "fancy cooking", "fancied making", "fancied doing", "thinking of", "planning to",
           "keen to", "hoping to", "in the mood for",
           # A need is a want. "i need to sort the garage" asks for the how as plainly as "i want
           # to sort the garage" does, and without these words the line reached no entry at all:
           # nine of twenty-eight typed "i need to sort X" lines were answered by the chat module
           # with a plan to start the job ("Then start with the smallest version of it") where the
           # base has a card for it. The entry still has to key the verb and the thing, so a need
           # the base knows nothing about reaches nothing, as before.
           "need to", "needs to", "needing to", "have to", "has to", "got to", "gotta")


# The words of the want phrases that carry no subject: a key that matched one of these has not
# matched the thing the line is about, so the want cannot stand in for the ask. "i want to help
# but i'm exhausted too" is not a question about the difference between to and too, and an entry
# keyed on "to" must not read it as one.
WANT_FILLER = frozenset("to like of in for would feel the mood keen hoping planning thinking love "
                        "plan plans planned".split())

# A want to *know* is a question, not a want of the thing: "i want to know how long to boil an
# egg" asks about the times, and the entry that keys them carries a keeping `ask` for exactly
# that line. Reading the want as the ask would hand it the boiled-egg keeping row instead.
WANT_KNOWING = ("want to know", "wants to know", "wanted to know", "wanting to know",
                "would like to know", "want to find out", "want to check", "want to ask",
                "want to learn", "like to find out", "need to know", "needs to know",
                "need to find out", "need to check", "need to ask", "need to learn")


# A row's `ask` is almost always written in the first person - "can i", "should i", "is it ok
# to", "how do i" - because that is how the person would ask about themselves. A line asking
# the same thing about someone else said the ask and never met it: "my wife is pregnant" then
# "can she fly" reached the flying row on its own words and was turned away at the ask
# ("can i" is not in "can she fly"), so a question the row answers got a shrug; "my dad has
# arthritis" then "can he take ibuprofen" went the same way. The ask is a kind of question,
# not a person, so the pronoun in it is read as any person and every other word of it still
# has to be said.
ASK_PEOPLE = frozenset("""
he him his she her hers they them their theirs we us our ours you your yours
son daughter wife husband partner mum dad mother father child children kids baby boy girl
brother sister nan grandad grandma
""".split())
ASK_PERSON_PRONOUNS = ("he", "she", "they", "we", "you")
ASK_PERSON_POSSESSIVES = ("his", "her", "their", "our", "your")


def _about_someone_else(phrase):
    """The ask phrase said about someone other than the speaker, or () when it cannot be."""
    words = phrase.split()
    if not any(word.lower() in ("i", "me", "my") for word in words):
        return ()
    out = []
    for person in ASK_PERSON_PRONOUNS:
        out.append(" ".join(person if word.lower() in ("i", "me") else word for word in words))
    for person in ASK_PERSON_POSSESSIVES:
        out.append(" ".join(person if word.lower() == "my" else word for word in words))
    return tuple(out)


def _said_about_someone(ask, forms, seen=None):
    """True when one of the entry's asks is said about a person other than the speaker."""
    line = _line_forms(forms, seen)
    if not any(word in line for word in ASK_PEOPLE):
        return False        # no person in the line, so nothing here changes
    for part in ask or ():
        # The ask parts belong to module-level entries, so the id is the part and the answer is
        # the same whichever entry asks: kept on the line's memo like every other part answer.
        if seen is not None:
            got = seen.get((_ASK_ABOUT_SOMEONE, id(part)))
            if got is not None and got[0] is forms:
                if got[1]:
                    return True
                continue
        said = False
        for phrase in ((part,) if isinstance(part, str) else part):
            if not isinstance(phrase, str):
                continue
            for variant in _about_someone_else(phrase):
                if _phrase_span(forms, variant, seen):
                    said = True
                    break
            if said:
                break
        if seen is not None:
            seen[(_ASK_ABOUT_SOMEONE, id(part))] = (forms, said)
        if said:
            return True
    return False


def _ask_about_someone_only(ask, forms, seen=None):
    """True when the entry's ask is met only by its somebody-else reading.

    The line asked the row's question, and it asked it about a person rather than about the
    speaker: no phrase of the ask is said as written.
    """
    if not ask:
        return False
    if any(_part_score(part, forms, seen) for part in ask):
        return False
    return _said_about_someone(ask, forms, seen)


def _the_subject_it_avoids(item, forms, carried, seen=None):
    """True when the row asks about someone else on the very subject its own avoid list rules out.

    "my mums got a chest infection" then "should she see a doctor": the ask is the see-somebody
    row's, said about her instead of about the speaker, and that row's avoid list names a chest,
    a cough, the flu and a mum - all words of the line this one leans on, so the row stands down
    when the speaker asks it about themselves. Reached through the somebody-else reading the test
    was never made, and two to six weeks was said of a chest infection.

    The earlier line is read for the avoid list only when the ask is met through that reading and
    not through a phrase of the entry's own, so a line the entry reaches as typed never turns on
    this.
    """
    if not carried:
        return False
    if not _ask_about_someone_only(item.ask, forms, seen):
        return False
    memo = {}
    for word in item.avoid:
        if isinstance(word, str) and word.strip() and _part_score(word, carried, memo):
            import os, sys
            return True
    return False


def _the_subject_the_line_leans_on(understood):
    """The forms of the words the line leans on, or [] when it leans on nothing.

    The person the earlier line is about is left out. "husband", "wife" and "mum" are in the
    avoid list of nearly every card about a part of somebody else, because the speaker's own
    part is what those cards hold, and asking about that somebody is the reading this test is
    for - so a card would be ruled out for saying who the person was.
    """
    leans = understood.get("leans_on")
    if not isinstance(leans, dict):
        return []
    words = leans.get("words") if isinstance(leans.get("words"), list) else []
    return [_forms(word) for word in words
            if isinstance(word, str) and word.strip().lower() not in ASK_PEOPLE][:CONTEXT_WORDS]


def _the_ask_said(ask, forms, seen=None):
    """True when the line asks what the entry's `ask` says, about the speaker or someone else."""
    if not ask:
        return True
    if any(_part_score(part, forms, seen) for part in ask):
        return True
    return _said_about_someone(ask, forms, seen)


def _wanting(forms, seen=None):
    """True when the line asks for the thing as a want rather than as a question.

    Read from the line, so the line's memo keeps it: this is asked once for every entry whose
    ask the line did not say, and the answer does not depend on the entry.
    """
    if seen is not None:
        got = seen.get(_WANTING)
        if got is not None and got[0] is forms:
            return got[1]
    if _part_score(WANT_KNOWING, forms, seen) > 0:
        answer = False
    else:
        answer = _part_score(WANTING, forms, seen) > 0
    if seen is not None:
        seen[_WANTING] = (forms, answer)
    return answer


def _only_the_want(item, forms, seen=None):
    """True when the want rule, and not the entry's own ask, is why this entry reached the line.

    The want rule is a reading of an entry the line names but does not ask about: "i want to make
    a cake" names the cake and the making, so the recipe's ask ("how long", "how do i") does not
    have to be said. It is not a licence for an entry whose own ask is about something the line
    never mentions: "i want to lose weight" reached the cycling entry this way, because its key
    holds "weight" and "lose" and only its ask ("bike", "cycle", "pedals") says it is about riding
    a bike, so the line got the calories-in-an-hour answer instead of the losing-weight one. An
    entry whose ask the line does say is a better fit than one let in by the want alone, so the
    two are ranked apart.
    """
    return not _the_ask_said(item.ask, forms, seen) if item.ask else False


def _key_on_the_want(item, forms, seen=None):
    """True when a key word this line matched is one of the want phrase's filler words."""
    for part in item.key:
        for alternative in (part if isinstance(part, tuple) else (part,)):
            if not isinstance(alternative, str):
                continue
            if set(alternative.lower().split()) & WANT_FILLER and _part_score(
                    alternative, forms, seen):
                return True
    return False


# A line that rules a state out is not about that state: "im not having a panic attack" is not
# the panic entry, and "im not in any pain" is not the pain one. Only the person saying what
# they are not in the middle of counts - the speaker, the copula and a word that carries a state
# ("not having", "not getting", "not in", "not being") - because the same shape elsewhere is a
# qualifier or a problem the entry answers: "a film thats not too long", "i dont have yeast",
# "my air con is not very cold", "the washing machine is not draining". A negator the entry's
# own key already holds ("not working", "not eating") is the key, not a denial of it.
DENY_SAID_OF = frozenset("""i im ive we were he hes she shes they theyre it its there am is are
    was were""".split())
DENIERS = frozenset("""not no dont doesnt didnt isnt arent wasnt werent aint""".split())
STATES_AFTER = frozenset("having getting being been in".split())
DENY_BETWEEN = frozenset("""really still even any more all at very too quite a an the""".split())


def _denier_inside(covered, forms, index):
    """True when a denier between the subject and this word is inside the phrase that matched.

    A key phrase can carry its own "not": "not getting any interviews" is what the entry asks
    for, and "im not getting any interviews" is the same line with a subject in front of it.
    Reading the key's own not as the speaker ruling the state out answered both of those with a
    shrug, because the subject "im" made "getting" the state after it.
    """
    back = 2
    while back <= 4 and index - back >= 0:
        at = index - back
        if at not in covered:
            return False      # the matched phrase stops before the denier
        if forms[at] & DENIERS:
            return True
        back += 1
    return False


def _denied(forms, covered):
    """True when the speaker rules out the state a key word names."""
    for index in covered:
        if index - 1 in covered and forms[index - 1] & DENIERS:
            continue          # "not working" is the entry's own key, not a denial of it
        if _denier_inside(covered, forms, index):
            continue          # "not getting any interviews" is the entry's key as well
        back = 1
        while back <= 4 and index - back >= 0:
            before = forms[index - back]
            if before & DENIERS:
                subject = index - back - 1
                if subject < 0 or not forms[subject] & DENY_SAID_OF:
                    break
                between = forms[index - back + 1:index]
                if any(word & STATES_AFTER for word in between) and all(
                        word & (STATES_AFTER | DENY_BETWEEN) for word in between):
                    return True
                break
            if not before & DENY_BETWEEN and not before & STATES_AFTER:
                break
            back += 1
    return False


_FRAME_MASK = object()

# The words that turn the rest of a line into something the person wants left out: "how do i
# sleep without pills" is about sleeping, not about pills. The words after the frame still
# reach an entry that asks for the frame itself - "how do i cook without an oven" has an answer
# of its own, and "what can i use instead of butter" is a swap entry that names both things - so
# the mask is only applied to an entry whose key does not name the frame word.
ASK_FRAME = frozenset("""
    how hows what whats which who whom whose when where why
    is are was were am be been can could should would will shall may might must
    do does did doing i im get gets got getting
    """.split())
# A time word says when a thing happens, not what the line is about, and the understander already
# keeps the days, the months and the parts of the day in one place: a row that reached a line on
# one of these alone has not named the subject either. The plural is here because a key says
# "nights" as often as "night", and "bedtime" because the hour before bed is asked about by the
# name of the hour ("what should i do at bedtime") rather than by the word "night".
WHEN_WORDS = frozenset(TIME_WORDS | {word + "s" for word in TIME_WORDS} | {"bedtime"})
# A mark taken off a thing: "how do i get tar off a jacket", "how do i get ink out of a shirt".
# The words of that phrase are the ask's, not the thing's, and an entry must not reach MIN_SCORE
# on them alone - see `_only_the_frame`.


def _only_the_frame(words):
    """True when every word of a matched key part is one the line is wrapped in, not about."""
    return bool(words) and all(word in ASK_FRAME for word in words)


_TAKE_OFF = None


def _says_removal(forms):
    """True when the line says something is to be taken off something else."""
    global _TAKE_OFF
    if _TAKE_OFF is None:
        _TAKE_OFF = (_forms("off"), _forms("out"), _forms("of"))
    off, out, of = _TAKE_OFF
    for index, word in enumerate(forms):
        if not word:
            continue
        if word & off:
            return True
        if out and of and index + 1 < len(forms) and word & out and forms[index + 1] & of:
            return True
    return False


FRAME_WORDS = ("without",)
# A frame covers the rest of its clause and no more: "a sauce without flour and a cheap pan" is
# two things and only the first is left out. Punctuation is gone by this point, so these are
# the words a new clause starts with.
FRAME_ENDS = frozenset(("and", "but", "or", "so", "then", "when", "if", "because", "while",
                        "which", "that", "to", "for", "with", "plus", "except", "besides"))
# A "without" clause that starts with a pronoun, or with a verb whose object is a pronoun, is
# not a thing left out: it is what the thing in hand does wrong. "how do i fry eggs without them
# sticking" is a question about eggs sticking, and the fault is the subject of the answer.
# "how do i sleep without pills" leaves pills out, and the pills are not what the line is about.
# The mask still goes on (an entry that counts the clause as words outranks the subject of the
# line on plenty of other lines), and what a clause like this buys is a second look in `_best`:
# the whole line may win without its margin, but only where the rest of the line has no answer of
# its own (`_the_subjects_own_row`).
FRAME_PRONOUNS = frozenset("it its them they this that those these he she him his her".split())
_FRAME_PRONOUN_FORMS = None


def _frame_pronoun_forms():
    """The forms of the pronouns above, worked out once."""
    global _FRAME_PRONOUN_FORMS
    if _FRAME_PRONOUN_FORMS is None:
        got = frozenset()
        for word in FRAME_PRONOUNS:
            got |= _forms(word)
        _FRAME_PRONOUN_FORMS = got
    return _FRAME_PRONOUN_FORMS


def _the_subjects_own_clause(here):
    """True when the words at `here` say what the thing in hand does, not what is left out."""
    if not here or not here[0]:
        return False
    mine = _frame_pronoun_forms()
    if here[0] & mine:
        return True
    # "without drying it out", "without scratching them": the gerund's object is the thing.
    if not any(str(form).endswith("ing") for form in here[0]):
        return False
    return any(word and word & mine for word in here[1:3])


def _a_clause_about_the_thing(forms):
    """True when one of the line's frame clauses is about the thing in hand, not a thing left out.

    "how do i roll out pastry without it cracking" has one; "how do i sleep without pills" and
    "can i make pesto without pine nuts" have none, and nothing about them changes.
    """
    starts, _end_forms = _frame_starts()
    for index, here in enumerate(forms):
        if not here:
            continue
        for first_forms, words in starts:
            if not here & first_forms:
                continue
            span = forms[index:index + len(words)]
            if len(span) == len(words) and all(
                    word and word & _forms(wanted) for word, wanted in zip(span, words)):
                after = index + len(words)
                if _the_subjects_own_clause(forms[after:after + 3]):
                    return True
    return False


def _frame_starts():
    """[(the first word's forms, the phrase, how many words it is)], worked out once."""
    global _FRAME_STARTS
    if _FRAME_STARTS is None:
        starts = []
        for phrase in FRAME_WORDS:
            words = phrase.split()
            starts.append((_forms(words[0]), tuple(words)))
        end_forms = frozenset()
        for word in FRAME_ENDS:
            end_forms |= _forms(word)
        _FRAME_STARTS = (starts, end_forms)
    return _FRAME_STARTS


_FRAME_STARTS = None


def _frame_masked(forms):
    """The line with its frame clauses emptied, and the frame words it uses.

    Positions stay in place - a span is a tuple of positions into this list, so emptying a
    position rather than removing it keeps every span an entry has already matched valid.
    """
    starts, end_forms = _frame_starts()
    found = set()
    dead = set()
    index = 0
    while index < len(forms):
        here = forms[index]
        hit = None
        if here:
            for first_forms, words in starts:
                if not here & first_forms:
                    continue
                span = forms[index:index + len(words)]
                if len(span) == len(words) and all(
                        word and word & _forms(wanted) for word, wanted in zip(span, words)):
                    hit = words[0]
                    index += len(words) - 1
                    break
        if hit is None:
            index += 1
            continue
        found.add(hit)
        index += 1
        while index < len(forms):
            if forms[index] and forms[index] & end_forms:
                break
            dead.add(index)
            index += 1
    if not found:
        return forms, frozenset()
    return [frozenset() if at in dead else word for at, word in enumerate(forms)], frozenset(found)


def _key_names(frame_words, item):
    """True when this entry's key asks for the frame word itself."""
    for part in item.key:
        for alternative in (part if isinstance(part, tuple) else (part,)):
            if isinstance(alternative, str) and set(alternative.lower().split()) & frame_words:
                return True
    return False


def _unframed(forms, seen):
    """(the forms to read, the memo to read them with, the frame words the line uses).

    An entry that names the frame keeps the whole line. The others read the masked line with a
    memo of its own: the per-part memo is keyed by the part alone, so the same part asked about
    two different readings of one line would answer the first reading twice.
    """
    if seen is not None:
        got = seen.get(_FRAME_MASK)
        if got is not None and got[0] is forms:
            return got[1], got[2], got[3]
    masked, frame_words = _frame_masked(forms)
    memo = seen if masked is forms else {}
    if seen is not None:
        seen[_FRAME_MASK] = (forms, masked, memo, frame_words)
    return masked, memo, frame_words


# "What's the best way to clean a shower screen" is a request for a method, and "best" and
# "way" there are the asking, not the thing. A row that stays away from "best" - the soap-scum
# row does, so that "which is best, a bath or a shower" reaches the bath-or-shower card - also
# refused the commonest how-to phrasing: the screen answer, the shower answer and about 280
# other avoid lists sit behind this word. An avoid word is matched loosely wherever it appears,
# so the two words of the ask phase are blanked for the avoid test only: the rest of the line,
# and the row's own key, still read exactly as they did. "how best do i ..." is the same ask.
ASK_PHRASE_WORDS = frozenset(("best", "way", "ways"))
_ASK_PHRASE_MASK = object()


def _without_ask_phrase(forms, seen):
    """(the forms to read an avoid word against, the memo to read them with).

    The line with "best way", "best ways" or "how best" blanked, so a row that disowns "best"
    or "way" is not stood down by the asking itself. A memo of its own, for the same reason
    `_unframed` keeps one: the part memo is keyed by the part alone.
    """
    span = ()
    for phrase in ("best way", "best ways", "how best"):
        span = _phrase_span(forms, phrase, seen)
        if span:
            break
    if not span:
        return forms, seen
    if seen is not None:
        got = seen.get(_ASK_PHRASE_MASK)
        if got is not None and got[0] is forms:
            return got[1], got[2]
    masked = list(forms)
    for at in span:
        masked[at] = frozenset()
    masked = tuple(masked)
    memo = {} if seen is not None else None
    if seen is not None:
        seen[_ASK_PHRASE_MASK] = (forms, masked, memo)
    return masked, memo


# How a person states a complaint about themselves and asks nothing: "i have tinnitus", "ive
# got heartburn", "i keep getting cystitis". The words below are the whole grammar of such a
# line; anything else in it means the line says more than the complaint, and then the entry has
# to earn the turn on two positions of its key like every other line.
REPORT_LEADS = frozenset((
    "i", "im", "ive", "am", "have", "has", "had", "got", "get", "gets", "getting", "keep",
    "keeps", "keeping", "feel", "feels", "felt", "feeling", "been", "was", "suffer", "suffering",
    "think", "thought", "reckon", "suspect", "probably", "maybe", "definitely", "sure"))
# A complaint reported about somebody else is the same line as the complaint about themselves.
# "i have head lice" was answered and "my daughter has head lice" was not - not a search hedge, a
# shrug: the person named in front of the complaint is not one of the words a report is made of,
# so the subject scored 2 and the answer that was one word away never ran. A parent writing about
# a child is the commonest way these lines arrive, and the whole family is the same shape.
REPORT_PERSON = frozenset((
    "son", "sons", "daughter", "daughters", "child", "children", "kid", "kids", "boy", "girl",
    "baby", "toddler", "little", "youngest", "eldest", "oldest", "teen", "teenager", "lad",
    "lass", "he", "she", "him", "her", "they", "them", "husband", "wife", "partner",
    "boyfriend", "girlfriend", "fiance", "fiancee", "friend", "friends", "mate", "mates",
    "mother", "mum", "mom", "father", "dad", "nan", "nana", "grandma", "grandad", "granny",
    "brother", "brothers", "sister", "sisters", "parent", "parents", "boss", "carer",
    "his", "her", "their", "our", "one"))

REPORT_FILLER = REPORT_LEADS | REPORT_PERSON | frozenset((
    "a", "an", "the", "my", "me", "really", "very", "so", "too", "just", "still", "also",
    "suddenly", "quite", "bit", "lot", "of", "with", "and", "at", "in", "on", "today", "now"))


# The words a complaint carries when it is the second time of asking: "my hay fever again",
# "eczema is back", "the asthma keeps coming back". A recurrence after the subject is the
# statement the report leads ("i have hay fever") are when the subject comes first, and without
# it a row that answers a stated complaint answered only the one word order.
HAPPENING_AGAIN = frozenset((
    "again", "back", "still", "already", "anyway", "now", "once", "twice", "more", "every",
    "year", "season", "spring", "summer", "autumn", "winter", "time", "times", "keeps", "keep",
    "kept", "coming", "come", "came", "going", "goes", "went", "on", "round", "around", "at",
    "as", "usual", "this", "same", "the", "it", "its", "is", "are", "was", "were", "has", "have",
    "had", "here", "today", "tonight", "morning", "night", "week", "month", "of", "in", "and",
    "so", "but", "though", "now", "first", "before", "like", "last"))


def _said_again(forms, covered, typed=None):
    """True when the words after the entry's subject are only the news that it has come back.

    "hay fever again", "eczema is back" and "my asthma keeps coming back" state the complaint
    and ask nothing, the same way "i have hay fever" does, and the order of the two is the only
    difference: a report in front of the subject is `_bare_report`'s, and one behind it is this.
    Only a row that has taken `report=True` asks this, so the list is the whole of the freedom
    it gives: nothing in it can name a thing the line is asking about.
    """
    if not covered:
        return False
    if isinstance(typed, (list, tuple)) and len(typed) == len(forms):
        words = [str(word).lower() for word in typed]
    else:
        words = []
        for group in forms:
            forms_of_word = sorted(str(form).lower() for form in group) if group else []
            words.append(forms_of_word[0] if forms_of_word else "")
    last = max(covered)
    after = words[last + 1:]
    if not after:
        return False
    return all(word in HAPPENING_AGAIN or word in REPORT_FILLER for word in after)


def _bare_report(forms, covered, typed=None):
    """True when the line reports the entry's subject about themselves and asks nothing.

    "i have tinnitus" and "ive got hay fever that keeps coming back" both start with the report
    and then name the subject: what comes before the subject is only the report ("i", "have",
    "got", "think"), so the person is telling you about themselves and the entry is the answer.
    A line that puts anything else before the subject is asking or telling something else -
    "do i have hayfever" carries its question word in front, "my hayfever is bad" names the
    subject first - and keeps the two-position rule like every other line.
    """
    if not covered:
        return False
    if isinstance(typed, (list, tuple)) and len(typed) == len(forms):
        words = [str(word).lower() for word in typed]
    else:
        words = []
        for group in forms:
            forms_of_word = sorted(str(form).lower() for form in group) if group else []
            words.append(forms_of_word[0] if forms_of_word else "")
    first = min(covered)
    lead = False
    person = False
    for index in range(first):
        word = words[index]
        if word in REPORT_LEADS:
            lead = True
            continue
        if word in REPORT_PERSON:
            person = True
            continue
        if word in REPORT_FILLER:
            continue
        return False
    # the complaint about a child or a partner needs the verb that says it is theirs ("my son has
    # head lice"), because the person alone in front of the subject is not a report of it
    if person and not lead:
        return False
    return lead


# The words a request to explain a thing is made of, and the words of that request that carry no
# subject of their own. "what is sepsis", "what's gout", "tell me about shingles" and "explain
# sciatica" are the same question, and the thing asked about sits behind nothing but those.
EXPLAIN_LEADS = frozenset((
    "what", "whats", "explain", "explained", "definition", "define", "meaning", "describe",
    "tell", "info", "information", "basics", "overview"))
EXPLAIN_FILLER = EXPLAIN_LEADS | frozenset((
    "s", "is", "are", "was", "does", "do", "did", "a", "an", "the", "of", "about", "on", "in",
    "for", "me", "us", "my", "mean", "means", "meant", "by", "symptom", "symptoms", "sign",
    "signs", "cause", "causes", "treatment", "exactly", "actually", "please", "and", "more"))


def _asks_to_explain(forms, start, typed=None):
    """True when the words in front of the entry's subject are a request to explain it.

    The subject is `start`, the first word of the part of the key that was matched; everything
    before it has to be one of the ask's own words. "what is sepsis" and "what are the symptoms
    of shingles" pass; "what is the best way to clean a sofa" does not, because "best", "way",
    "clean" are not words of a request to explain the sofa, and the row that names a sofa is not
    the row the line wants.
    """
    if not start or start > 12:
        return False
    if isinstance(typed, (list, tuple)) and len(typed) == len(forms):
        words = [str(word).lower() for word in typed]
    else:
        words = []
        for group in forms:
            forms_of_word = sorted(str(form).lower() for form in group) if group else []
            words.append(forms_of_word[0] if forms_of_word else "")
    lead = False
    for index in range(start):
        word = words[index]
        if word in EXPLAIN_LEADS:
            lead = True
            continue
        if word in EXPLAIN_FILLER:
            continue
        return False
    # "tell me about it" names no thing, and "what is it" is the follow-up question: the thing
    # asked about has to be a word of its own, which the caller has already found in its key.
    return lead


def _only_as_a_kind(forms, span, covered, item, typed=None):
    """True when the entry's subject is only ever said as a description of something else.

    "something light", "anything sweet" - the word is an adjective where it stands, and a row
    that names it as the subject of its own has nothing to answer. The row that explains light
    was the answer to "what should i watch tonight, something light" and to "whats on tonight,
    something light".

    A single word is the whole of the shape. The description is one word and the row reads that
    one word as its subject; a key phrase of several words is a clause the row reads for itself,
    and the pronoun in front of it is the subject of that clause, which names the thing the row
    is about ("everything tastes of metal", "nothing wakes my baby").

    A row whose subject is a qualifier it was built for keeps the line, and so does one whose
    other words are the ask itself: "light" is the subject group of the light-dinner row, so
    "something light for lunch" is exactly its question, and the mood row asks "something" of
    its own. What tells the rows apart is whether anything beside the subject is a word this row
    answers with: the definition rows have nothing but their own ask words there ("what"), the
    others have "lunch", or the "something" their key names.

    Read on the words the person typed, and on the forms otherwise, exactly as
    `_asks_to_explain` does, so a reading built without `typed` still matches.
    """
    if len(span) != 1:
        # One word is the whole of a description: "something light", "anything sweet". A key
        # phrase of several words next to the pronoun is the row's reading of the clause
        # instead, and the pronoun is that clause's subject, not a word in front of a
        # description: "everything tastes of metal" and "nothing wakes my baby" both name a
        # taste and a waking, and their rows answer them.
        return False
    start = min(span)
    if start < 1:
        return False
    if isinstance(typed, (list, tuple)) and len(typed) == len(forms):
        words = [str(word).lower() for word in typed]
    else:
        words = []
        for group in forms:
            forms_of_word = sorted(str(form).lower() for form in group) if group else []
            words.append(forms_of_word[0] if forms_of_word else "")
    if start - 1 >= len(words):
        return False
    if words[start - 1] not in AS_A_KIND:
        return False
    asked = set()
    for part in (item.ask or ()):
        for alternative in ((part,) if isinstance(part, str) else part):
            for word in str(alternative).lower().split():
                asked.add(word)
                asked |= {str(form).lower() for form in _forms(word)}
    said = set()
    for index in covered:
        if index in span or index >= len(words):
            continue
        said.add(words[index])
    said.discard("")
    # Nothing said beside the subject is what the line is about, only the asking and the words
    # the row asks with: nothing of this row's own is in the line, so the subject was a
    # description.
    return all(word in asked or word in EXPLAIN_FILLER for word in said)


def _says_a_shape(shapes, typed, forms):
    """True when the line, as the person typed it, holds a figure of the kind a row is about.

    The shapes are given the line's own words joined by spaces ("its on 4% and the charger is at
    work"), because a shape reads a figure rather than a word and the word forms of "4%" say
    nothing: this is the one signal in the matcher that is not a key word, so it is handed the
    line and answers for itself. Words are taken from `typed` when it lines up with the forms and
    from the forms otherwise, exactly as `_bare_report` does, so a reading built without `typed`
    still matches.
    """
    if isinstance(typed, (list, tuple)) and len(typed) == len(forms):
        words = [str(word).lower() for word in typed]
    else:
        words = []
        for group in forms:
            forms_of_word = sorted(str(form).lower() for form in group) if group else []
            words.append(forms_of_word[0] if forms_of_word else "")
    line = " ".join(word for word in words if word)
    if not line:
        return False
    for shape in shapes:
        try:
            if shape(line):
                return True
        except Exception:  # noqa: BLE001 - a shape that cannot read the line is not a signal
            continue
    return False


def score(item, forms, typed=None, seen=None, frame=True, framed=False):
    """The entry's score for a line, or 0 when it is not about the entry.

    Two different words of the key have to be in the line. Without that, a part like
    ("rain", ("raining", "why")) scores 4 from "it rained" alone, because raining and
    rain are loose forms of the same word; one passing mention would then answer the
    line. The same rule keeps "freeze" from a freezer fact out of a call that freezes.

    The first part is the subject and it has to be said. An entry written as
    (subject) x (what is said about it) x (how it is asked) can otherwise reach the
    total from the last two parts alone: "im thinking of getting a bike to cycle to
    work" brought "work" and "get" and was answered by the bank-holidays entry, and
    "how do i unblock a slow kitchen sink without calling a plumber" reached the
    cupboard clear-out on "kitchen" and "how do i". Both lines name a thing the entry
    never mentions.

    That only holds where the key is written that way. An entry whose key is a flat
    list of phrasings - `water-in-ear` is "water in my ear", "water is stuck in my ear",
    "swimmers ear", and twenty more, each a whole subject - has no first part to insist
    on, and reading its first phrasing as the subject took "i have swimmers ear" off
    its own answer: "Noted: you have swimmers ear." So the rule is applied to every key
    that has a group in it, which is what (subject) x (about) x (ask) looks like.

    A key that is only partly grouped still has a first part: `email-to-teacher` is
    ('teacher', 'childs', 'school', ('email', 'write', 'message')), and with the rule
    read off the first part alone it answered "how do i choose a school for my child"
    on the bare word "school" - the school was named, the email never was. So the test
    is whether any part is a group, not whether the first one is.

    framed: the line is the subject inside an advice ask ("what should i do about the
    condensation"), which spends its other words on the asking. Only for the entries in
    ASK_FRAME_IDS, whose subject is one everyday noun, the ask around it is the second signal
    and one word of the subject part is enough.
    """
    if not forms:
        return 0
    if typed and _under_their_own_hands(item, typed):
        # The row would tell them how to do it themselves; they asked whether the bot can do it.
        return 0
    masked, memo, frame_words = _unframed(forms, seen) if frame else (forms, seen, frozenset())
    if frame_words and not _key_names(frame_words, item):
        # "how do i sleep without pills" is about sleeping: the entry that answers the pills
        # (a pharmacy takes them back) must not take the line. Only the frame words, though -
        # the rest of the line still reads as it did.
        forms, seen = masked, memo
    # An explaining row reads a line that names its subject once, so it is exempt from the
    # two-position pre-filter for the same reason a stated complaint is: the ask in front of
    # the subject is the second signal, and `explained` below is what enforces it.
    # The framed reading is the exception to the two-position pre-filter for the same reason a
    # stated complaint is: the ask around the subject is the second signal, and only the
    # entries in ASK_FRAME_IDS whose subject is the whole of what the ask is about read it.
    framed_one = bool(framed and item.key and getattr(item, "id", "") in ASK_FRAME_IDS
                      and _the_whole_subject(item.key[0], forms, seen))
    if not item.report and not item.explain and not framed_one and not item.shape \
            and not _two_positions(forms, item):
        # A shape is a second signal in its own right - "4%" says a figure, and one word of a
        # dish says the dish - so a row that carries one is not dropped here for holding a
        # single position of the line. Whether the figure is really there is asked below, where
        # the shape answers, so a row whose shape does not match still scores 0.
        return 0
    if item.ask and not _the_ask_said(item.ask, forms, seen):
        if not _wanting(forms, seen) or _key_on_the_want(item, forms, seen):
            return 0
    total = 0
    covered = []
    first = ()
    removal = _says_removal(forms)
    grouped = any(isinstance(part, (tuple, list, frozenset, set))
                  for part in (item.key or ()))
    for index, part in enumerate(item.key):
        weight, words, span = _part_match(part, forms, covered, seen)
        if index == 0 and typed and len(span) == 1 and span[0] < len(typed) \
                and _asking_with(typed, span[0]):
            # The question's own modal is not the thing the line is about, so it cannot be the
            # subject the key is built on: "can i still travel" was answered by the cool-bag card,
            # whose subject group is "can" (a can of drink). The one word is dropped and the rest
            # of the line still scores, which is what keeps "can you keep it cold" on the drinks
            # row (the "cold") and "what can i do with it" on the dish the previous turn named (the
            # phrase "can i do" is two words and a phrase is not a bare modal, so it is untouched).
            # No memo here: `seen` answers per part, so the cached match would hand the modal
            # straight back. This is one part of one entry on a line that asks with a modal.
            bare = list(forms)
            bare[span[0]] = frozenset()
            weight, _, span = _part_match(part, bare, covered)
        elif (index and removal and weight > 1 and _only_the_frame(words)
              # ... but not where the subject part was itself a phrase: "how do i get out of
              # debt" names a thing of two words, and the second part could only be reached
              # through the ask ("get out", "how do i"), so the rule took the whole answer away
              # and the line scored 3 - under MIN_SCORE - while "get out of debt" answered.
              # A one-word subject is what the rule was written for ("tar" on a jacket).
              and len(first) < 2):
            # "how do i get tar off a jacket" names tar and jacket; "get" is how the person
            # asks. A later key part that the line only reaches through those words is the
            # ask, not a second thing about the entry: one of them can be an accident of how
            # the line is phrased and counts for one, and a phrase of them ("how do i", "do i")
            # is the frame itself and counts for nothing. Without that, `coat-worth` read
            # "jacket" and "get" and answered a tar mark with the coat-buying row, and
            # `paving-slab` read "paving slab" and "how do i" and answered cement on a slab
            # with the row about laying one.
            #
            # The part may also have matched a real word of the line: the second part of
            # `child-off-school` is "should i" and "child" on "should i keep my child off
            # school", and a phrase outweighs a word, so the ask won the part and the frame rule
            # then took it away, and the school question lost its own card to the kitchen. Where
            # the same part reaches a word that is not the ask, that word is what the line is
            # about and it counts at its own weight.
            # A word the earlier key part already used still counts here: "how do i tell my
            # kid off" reaches this row through "tell my kid off" (3) and its "kid" (2), but
            # "kid" is the word the first part matched, and the frame rule then took the whole
            # part away, so the line scored 3 and reached nothing while the same line without
            # "how do i" was answered. The overlap is one signal matched twice, not a second
            # thing about the entry, so it is worth what a word is worth.
            spare = [hit for hit in _part_matches(part, forms)
                     if not _only_the_frame(hit[1])]
            if spare:
                weight, words, span = spare[0]
            else:
                weight = 1 if len(words) == 1 else 0
        total += weight
        covered.extend(span)
        if index == 0:
            first = span
    if grouped and not first:
        return 0
    # A stated complaint is one signal: "i have tinnitus" names the subject and asks nothing,
    # so the entry that answers it never came within reach of the line and a chat nod ("Noted:
    # you have tinnitus") took the turn. A row that says the complaint is worth answering when
    # it is only stated counts the report itself as the second signal, which is also what lifts
    # a two-word subject ("i have hay fever" scored 3) over MIN_SCORE. The subject check above
    # is what keeps a bare "bad" - a word of the eczema row's second part - out of a knee.
    bare = bool(item.report) and (_bare_report(forms, covered, typed)
                                  or _said_again(forms, covered, typed))
    shaped = bool(item.shape) and bool(first) and _says_a_shape(item.shape, typed, forms)
    explained = bool(item.explain) and bool(first) and _asks_to_explain(forms, min(first), typed)
    if first and not explained and _only_as_a_kind(forms, first, covered, item, typed):
        # The subject of this row is the word that describes the thing asked for, and the line
        # says nothing else about it: see AS_A_KIND.
        return 0
    one_word = len(set(covered)) < 2
    if one_word and not bare and not explained:
        # The ask around a one-noun subject is its second signal, and only for the
        # entries whose subject is that kind of everyday noun (see ASK_FRAME_IDS),
        # and only where that word names one thing. The subject still has to be the
        # whole of what the ask is about: "what should i do about the damp patch" is
        # a patch.
        if not framed_one and not shaped:
            return 0
    if bare or shaped or explained:
        total += WORD_WEIGHT
    if _denied(forms, covered):
        return 0
    if not one_word and total < MIN_SCORE:
        return 0
    ask_forms = ask_seen = None
    for word in item.avoid:
        key = word.strip().lower() if isinstance(word, str) else ""
        if key in ASK_PHRASE_WORDS:
            if ask_forms is None:
                ask_forms, ask_seen = _without_ask_phrase(forms, seen)
            if _part_score(word, ask_forms, ask_seen):
                return 0
        elif _part_score(word, forms, seen) or _phrase_span_between(forms, word, seen):
            return 0
    if typed and _misspelt_avoid(item, typed):
        return 0
    failing_at = _keeps_failing_at(forms, seen)
    if failing_at is not None and _keeping_row(item) and (
            not first or min(first) != failing_at + 1):
        # The row answers how long a thing keeps, and the line says the thing keeps going wrong
        # ("my bread keeps coming out flat", "my fridge keeps beeping", "my coffee keeps tasting
        # bitter"): the fault is what is wanted, not the shelf life. The one exception is a row
        # whose own words start on the word straight after the verb, because then they are what
        # the person keeps doing rather than the thing that keeps going wrong: in "i keep running
        # to the loo" the row is "running to the loo", so "keep" is only how the complaint is
        # phrased. "my son keeps losing his jumper at school" is not that - his jumper begins
        # later in the line - and neither is "my coffee keeps tasting bitter", where the row's
        # subject is the coffee before the verb.
        return 0
    return total


# A line that asks what to cook with a thing names a dish, and no other kind of row can answer
# it: "what can i make with a bag of carrots" is not a question about how deep the bag is, and
# "what can i do with a punnet of raspberries" is not a question about what a punnet weighs. Rows
# about growing a crop or weighing a measure put this in their `avoid`, so the dish table answers
# the dish and the row still answers "can i grow potatoes in a bag" and "how much is a punnet".
# "Is it ok to eat this past the date" is a keeping question about the food named, and it is how
# most people ask it: the words that say the day on the pack rather than the food are kept here so
# the freshness rows, the keeping rows and the nutrition rows all read the same phrase the same
# way. A nutrition row that answered it told the person about fibre, and a shelf-life row that is
# not about the food they named told them about dried fruit.
PACK_DATE = ("past the date", "past its date", "past their date", "past the use by",
             "use by date", "use by", "sell by", "best before", "out of date",
             "after the date", "after its date", "after their date", "date on it",
             "date on the", "date says", "date said")

# The day the food is going to be eaten is the same question as the date on the pack, and people
# say it as often: "can i eat the chicken tomorrow" is "is the chicken ok the next day". The words
# live here, once, because every freshness row reads them the same way: the spoilage tests in
# still_ok, the milk card, and the diet plan's stand-down list. "tomorrow" was missing from them
# for a long time, so a whole family of lines was a shrug while its twin was answered.
DAY_WORDS = ("next day", "the next day", "the day after", "day after", "yesterday",
             "tomorrow", "tomorow", "tmrw", "tomoz")

# A row that says how to do something on the person's own machine - sign a PDF, merge two files,
# fill in a form - is instructions for their hands. "can you fill in this form", "can you sign this
# for me" is not asking for those instructions: it is asking whether the bot can do it, and the
# honest answer is that nothing here can see the form, so the composer's reader for a thing on the
# person's side has the line. Without this, "can you fill in this form" and "help me fill in this
# form" reached the PDF-signing row and were told which menu to use.
ASKS_FOR_THE_HANDS = re.compile(
    r"\b(?:can|could|would|will|are|do)\s+(?:you|u)\b|\b(?:for|help)\s+(?:me|us)\b")
# The verbs a hand or an eye would do to a thing on their side: filling, signing, printing,
# scanning, reading. Reading is on the list because "can you read this letter from the council" is a
# person handing the bot a thing it cannot see, but it is the one verb that is also a real job for
# the knowledge base ("what does this letter mean", see `ASKS_WHAT_IT_SAYS` below), so that shape
# stands the reading down and the row keeps the line.
A_HAND_OR_EYE_DOES_IT = re.compile(
    r"\b(?:fill|fills|filling|sign|signs|signing|print|prints|printing|scan|scans|scanning|"
    r"open|opens|opening|read|reads|reading|check|checks|checking|complete|completes|"
    r"completing|translate|translates|translating|look\s+(?:at|through|over))\b")
# The same line can ask for a hand or for the meaning, and only the meaning is a job for the
# knowledge base: "can you read this letter and tell me what it means" is answered by the row that
# says what to look for in a letter, so it keeps that row. "can you read this letter from the
# council" names no question about the content and is asking the bot to see it.
ASKS_WHAT_IT_SAYS = re.compile(
    r"\b(?:what|whether|if)\b|\b(?:means?|meaning|says?|explain|explains|explaining|"
    r"understand|summar\w+|translate\w*|about\s+it)\b")
# The thing has to be one of theirs, said as theirs: "the documents i need for a passport" is a
# question about a rule and keeps its answer, and only "my form", "this pdf", "the letter" is the
# thing on their side that nothing here can see.
OWN_THING_ON_THEIR_SIDE = re.compile(
    r"\b(?:my|our|this|that|these|those|the)\s+(?:[a-z']+\s+){0,2}"
    r"(?:form|forms|pdf|pdfs|file|files|document|documents|paperwork|scan|scans|"
    r"screenshot|screenshots|photo|photos|letter|letters|invoice|invoices|contract|"
    r"application|applications|cv|questionnaire|questionnaires)\b")
THEIR_OWN_HANDS_THINGS = frozenset("""form forms pdf pdfs file files document documents paperwork
    scan scans screenshot screenshots photo photos letter letters invoice invoices contract
    application applications cv questionnaire questionnaires""".split())


def _under_their_own_hands(item, typed):
    """True when the line asks the bot to do something to a thing of the person's own.

    Only the rows about that thing stand down, and only when the line is an ask to the bot with a
    verb a hand or an eye would do: "can you fill in this form", "could you print my cv".
    """
    line = " ".join(str(word).lower() for word in typed)
    if not ASKS_FOR_THE_HANDS.search(line) or not A_HAND_OR_EYE_DOES_IT.search(line):
        return False
    if ASKS_WHAT_IT_SAYS.search(line):
        return False   # "what does this letter mean" is the knowledge base's line
    if not OWN_THING_ON_THEIR_SIDE.search(line):
        return False
    said = set()
    for part in (item.key or ()):
        for alternative in ((part,) if isinstance(part, str) else part):
            said |= {piece for piece in str(alternative).lower().split()}
    return bool(said & THEIR_OWN_HANDS_THINGS)


# A line that asks what the sky is doing is asking for today's reading, which the bot cannot look
# up, and it is the commonest kind of line there is: "what is the weather like today", "whats the
# weather like this weekend", "is it cold outside", "is it warm enough to sit outside". Those are
# not plans, nor a note on cold air and lungs, nor a note on what to wear - on today's main the
# first was a weekend plan ("pick two things and put them in the diary by Friday"), the third was
# "cold air does not damage healthy lungs", and the fourth was "dress for ten minutes in". Each of
# those rows is keyed on a weather word or a day word, which is what let the line in: "today" and
# "what" is enough for the plans row, "cold" and "outside" for the lungs row, "warm" and "outside"
# for the clothes note. So the rows that key on those words stand down on this list, and the live
# information note answers with the kind of answer it is ("No live weather here - a forecast app
# will tell you in one tap"), which is what "is it cold today" already got.
#
# These are phrases and not the bare words, on purpose. "the weather" as a noun is far too common
# in a line that wants something else ("what can i do this weekend, the weather looks bad" is a
# plan), and the bare word would stand the useful answer down. What is left is the shapes that ask
# for the reading itself: the thing named as a question, or "enough" said of it.
A_WEATHER_ASK = ("weather like", "weather doing", "weather going to be", "weather forecast",
                 "what is the weather", "whats the weather", "what's the weather",
                 "wether like", "whats the forecast", "what's the forecast", "the forecast for",
                 "is it cold outside", "is it cold today", "is it cold out", "is it cold enough",
                 "is it warm outside", "is it warm today", "is it warm enough",
                 "is it hot outside", "is it hot today", "is it hot enough",
                 "is it freezing", "is it raining", "is it snowing",
                 "warm enough to", "cold enough to", "how cold is it", "how hot is it",
                 "how warm is it", "what is it like outside", "whats it like outside",
                 "what's it like outside")

# A food a person keeps in the house, and asks about keeping. It is a short table on purpose: a
# row that stands down for it is standing down for a line that is plainly about the food, so the
# word has to be one nobody keeps anything else in. "Why does bread go mouldy in a plastic bag"
# is a loaf and a bag it came in, not a carrier bag to pay for, and "why does bread go mouldy
# faster in a bag" is not a garment to air; "is it better to keep bread in the fridge" is not
# which carbohydrate is better for you. Each of those rows answered the wrong half of the line,
# and the word that decides it is the food.
KEPT_FOODS = ("bread", "loaf", "loaves", "rolls", "bagels", "milk", "butter", "cheese",
              "yoghurt", "yogurt", "cream", "eggs", "egg", "meat", "chicken", "beef",
              "pork", "lamb", "bacon", "ham", "sausages", "sausage", "fish", "salmon",
              "prawns", "rice", "pasta", "noodles", "potatoes", "potato", "flour", "oats",
              "cereal", "soup", "stew", "sauce", "gravy", "cake", "biscuits", "cookies",
              "chocolate", "fruit", "apples", "bananas", "berries", "strawberries", "salad",
              "lettuce", "spinach", "carrots", "mushrooms", "tomatoes", "onions", "peas",
              "beans", "leftovers", "leftover", "sandwich", "sandwiches", "hummus", "nuts")

# The words that say the line is about keeping a thing rather than about the thing itself. A
# keeping question has one of these and a food, and it is the food's own rows that answer it.
# A keeping question says what has happened to the food or where it is put, not just the verb
# "keep" - "how do i keep my bread habit" is a habit line and names bread. So the bare verb is not
# here: "how do i keep bread fresh" is ("fresh"), "how long can i keep cooked rice" is ("how
# long"), and "should i keep bread in the fridge" is ("fridge").
KEEPING_WORDS = ("store", "stores", "stored",
                 "storing", "storage", "last", "lasts", "lasted", "fresh", "fresher",
                 "freshness", "stale", "staler", "stales", "staleness", "mould", "moulds",
                 "mouldy", "mold", "molds", "moldy", "mildew", "mildewy", "goes off",
                 "go off", "gone off", "going off", "goes bad", "gone bad", "goes hard",
                 "gone hard", "goes soggy", "gone soggy", "fridge", "freezer", "freeze",
                 "freezing", "bin", "shelf life", "cold", "warm", "damp", "how long",
                 "longer", "longest", "keep fresh", "use by", "best before")


def a_food_is_being_kept(understood):
    """True when the line asks about keeping a food: it names a food and a keeping word.

    A row about something else that shares a word with such a line answers the wrong half of it.
    The container in "why does bread go mouldy in a plastic bag" is packaging, the bag in "why
    does bread go mouldy faster in a bag" is where the loaf was kept, and the fridge in "is it
    better to keep bread in the fridge" is where it is kept - so the garment rows, the carrier
    bag charge and the which-carbohydrate-is-better row all stand down and the bread rows answer.
    "My coat smells of curry" names no keeping word and no food, so nothing here touches it.
    "How do i keep my gym bag smelling fresh" names a garment and a keeping word but no food.
    """
    if not isinstance(understood, dict):
        return False
    text = " " + str(understood.get("norm_text") or understood.get("clean") or "").lower() + " "
    if not any(word in text for word in KEEPING_WORDS):
        return False
    words = understood.get("words") or ()
    said = {str(word).lower() for word in words}
    for food in KEPT_FOODS:
        if " " in food:
            if food in text:
                return True
        elif food in said or (" " + food + " ") in text:
            return True
    return False


# What a thing is kept in, or kept on. A row whose own words include one of these can be handed a
# line about the food inside it - a loaf in a plastic bag, a joint in a drawer - and that line is
# the food's question. `only_a_container` is the test such a row puts beside
# `a_food_is_being_kept` to tell its own container from somebody else's.
CONTAINERS = ("bag", "bags", "bin bag", "bin bags", "bin", "bins", "box", "boxes",
              "packet", "packets", "pack", "packs", "tin", "tins", "jar", "jars", "tub",
              "tubs", "container", "containers", "lunchbox", "lunch box", "sack", "sacks",
              "suitcase", "suitcases", "rucksack", "rucksacks", "backpack", "backpacks",
              "handbag", "handbags", "luggage", "basket", "baskets", "crate", "crates",
              "tray", "trays", "drawer", "drawers", "cupboard", "cupboards", "shelf",
              "shelves", "fridge", "freezer")


def only_a_container(understood, names):
    """True when every word of `names` the line says is a container a thing is kept in.

    "Why does bread go mouldy in a plastic bag" says "bag" and nothing else of the garment table,
    so the garment rows stand down for the loaf. "My gym bag smells musty" has no food in it, so
    `a_food_is_being_kept` is already false and this is never asked. "My leather jacket smells of
    cheese" says two words of that table and leather is not a container, so the jacket keeps its
    answer.
    """
    if not isinstance(understood, dict):
        return False
    text = " " + " ".join(str(word).lower() for word in (understood.get("words") or ())) + " "
    found = [one for one in names if " " + one + " " in text]
    return bool(found) and all(one in CONTAINERS for one in found)


# A line that asks when a place opens or shuts is asking for the venue's hours, which the bot
# cannot look up, and the fallback says so ("I can't check today's opening hours, sorry"). Three
# rows keyed on a day word were taking those lines instead, because "today" and a question word
# is all they need: "what time does the post office on hill road close today" was a weekend plan
# ("pick two things and put them in the diary by Friday") and "what time does the tip close
# today" the same. The shape is what makes it an hours ask, so it is the phrases and not the bare
# words: "what time ... close", "opening hours", "shut today". A line that asks what to do with
# a free day keeps its plan.
A_HOURS_ASK = ("what time does", "what time do", "what time is the", "what time are the",
               "opening hours", "opening times", "opening time", "closing time",
               "closes at", "closes today", "closes tonight", "shuts at", "shuts today",
               "close today", "close tonight", "close on", "open today", "open now",
               "open on", "is it open", "is it shut", "open until", "open till",
               "till what time", "until what time", "last entry", "last orders")

DISH_ASK = ("make with", "made with", "make using", "make from", "make out of",
            "what can i make", "what can i cook", "what should i make", "what can i do with",
            "what should i do with", "cook with", "cooking with", "do with", "using up",
            "for dinner", "for tea", "for lunch", "for supper", "for breakfast", "tonights tea",
            "something with", "dish with")


# --- "keeps" as a fault verb, not a shelf-life word -------------------------------------
#
# "How long does bread keep" and "my bread keeps coming out flat" share the word that decides
# which row answers, and the shelf-life rows win both: the storage line ("It keeps 3 days in a
# paper bag") is what somebody whose baking keeps failing was told, and the same for a roast
# chicken that comes out dry and a marble run that keeps falling over. The fault is the verb
# itself - "keeps" with another verb right after it - so the shape is what stands the keeping rows
# down, not a list of the verbs, which is every verb there is.
#
# Two shapes are the keeping question still. "My herbs keep wilting" and "my cake keeps going
# dry" are spoilage, which is what a shelf-life answer is for, so a word of rot after the verb
# keeps the keeping row in. And "coming out" is the cook reporting a result ("keeps coming out
# dry" is a roast chicken, not a mouldy one), so that shape is a fault even when the word after
# it is a spoilage word.
_KEEPING_VERB = frozenset(("keep", "keeps", "kept", "keeping"))
_RESULT_VERB = frozenset(("coming", "comes", "come", "turning", "turns", "turn"))
# The verbs of rot, in the forms people write them. Bounded on purpose: a state that is not here
# is a behaviour to fix, which is the reading the fault has.
_SPOILING = frozenset((
    "mouldy", "moldy", "mould", "mold", "moulding", "molding", "slimy", "slimy", "soggy",
    "mushy", "sour", "soured", "souring", "rancid", "stale", "wilted", "wilting", "wilt",
    "limp", "off", "bad", "rotten", "rotting", "rot", "brown", "browned", "browning",
    "discoloured", "discolored", "curdled", "curdling", "curdle", "smelly", "smelling",
    "stinking", "sprouting", "sprouted", "spotted", "furry", "fuzzy", "blue", "green",
    "shrivel", "shrivelled", "shriveling",
))
# A word that ends in -ing and is a thing rather than a verb: "it keeps the evening quiet" is
# not a fault, and a key of "keep" plus one of these is the keeping row's own line.
_ING_NOUNS = frozenset((
    "evening", "evenings", "morning", "mornings", "ceiling", "building", "feeling", "feelings",
    "meeting", "meetings", "wedding", "pudding", "stuffing", "dressing", "filling", "parking",
    "clothing", "bedding", "writing", "painting", "drawing", "reading", "heating", "lighting",
    "awning", "herring", "sterling", "seedling", "sibling", "dumpling", "spring", "springs",
    "string", "strings", "thing", "things", "ring", "rings", "king", "wing", "wings",
))

# The keeping rows themselves, found by the words they are keyed on, so a row added tomorrow is
# covered without anyone remembering to hold it out of a fault line. A keeping row holds the
# keeping word *and* one of the life words, both as alternatives of their own: "keeps" on its own
# is the word for a repeated fault as well ("my friend keeps cancelling", "he keeps interrupting
# me"), and a row that answers that complaint must keep answering it.
_KEEPING_KEY = frozenset(("keep", "keeps", "kept", "keeping"))
_LIFE_KEY = frozenset(("how long", "shelf life", "shelf-life", "store", "stores", "storing",
                       "stored", "storage", "last", "lasts", "lasted", "lasting", "fresh",
                       "fresh for", "still good", "gone off", "out of date", "use by"))
_KEEPING_ROWS = {}


def _keeping_row(item):
    """True when this row answers a "how long does it keep" question."""
    known = _KEEPING_ROWS.get(id(item))
    if known is None:
        keeps = False
        lives = False
        for part in item.key:
            for alternative in (part if isinstance(part, tuple) else (part,)):
                if not isinstance(alternative, str):
                    continue
                shaped = alternative.strip().lower()
                if shaped in _KEEPING_KEY:
                    keeps = True
                elif shaped in _LIFE_KEY:
                    lives = True
        known = keeps and lives
        _KEEPING_ROWS[id(item)] = known
    return known


def _gerund(forms, index):
    """The -ing verb at this position of the line, or "" when the word is a thing."""
    for form in forms[index]:
        if form in _ING_NOUNS or len(form) < 5 or not form.endswith("ing"):
            continue
        return form
    return ""


def _later_words(forms, index, reach=3):
    """The words after a position, for the state a "keeps going ..." line names."""
    seen = set()
    for step in range(index, min(index + reach, len(forms))):
        seen |= forms[step]
    return seen


# A verb after "keeps" that says the thing comes round again rather than that it goes wrong: "why
# do i keep getting cold sores" and "i keep getting cystitis" are the subject recurring, so what is
# wanted is the cause and how to keep it off, which is the subject's own row. A keeping row that
# read these as faults stood itself down and the line got nothing ("why do i keep getting cold
# sores" got a sympathy card) or the wrong row ("why do cold sores keep coming back" reached the
# joints-in-cold-weather card on "cold" and "back"). The verbs of having a condition are enough on
# their own; "coming", "going" and "giving" are verbs of anything, so they count only with the
# word that places a recurrence ("keeps coming back", "keeps going on"). "my son keeps losing his
# jumper at school" is still a fault: what he keeps doing has the jumper as its object, so the
# row about storing a jumper has nothing to say to it. "having" is not here on purpose: "i keep
# having biscuits at about 4pm" is a habit, and the tin they keep in is not the answer to it.
_RECURRING = frozenset((
    "getting", "happening", "happens", "recurring", "returning", "flaring", "cropping"))
_RECURRING_ANYWAY = frozenset(("coming", "going", "giving"))
# The words that place a recurrence rather than a result: it comes *back*, it goes on *again*.
_RECURRING_WITH = frozenset(("back", "again", "around", "round", "on"))


def _keeps_failing_at(forms, seen=None):
    """Where the "keeps" of a fault verb sits, or None when no "keeps" is one.

    "i keep running to the loo" has the shape of "my bread keeps coming out flat" and is the
    opposite case: the thing the row is about comes *after* the verb (what the person keeps
    doing), so the verb is the person's own phrasing of a complaint and not the fault. The
    caller compares this position with where the entry's subject matched.
    """
    if seen is not None:
        got = seen.get("keeps-failing-at")
        if got is not None:
            return None if got is False else got
    failing = None
    for index in range(len(forms) - 1):
        if not (forms[index] & _KEEPING_VERB):
            continue
        gerund = _gerund(forms, index + 1)
        if not gerund:
            continue
        if gerund in _RECURRING:
            continue
        if gerund in _RECURRING_ANYWAY and _later_words(forms, index + 1) & _RECURRING_WITH:
            continue
        result = (_later_words(forms, index + 1) & frozenset(("out",))
                  and (_later_words(forms, index + 1) & _RESULT_VERB
                       or gerund in _RESULT_VERB))
        if result or not (_later_words(forms, index + 1) | {gerund}) & _SPOILING:
            failing = index
            break
    if seen is not None:
        seen["keeps-failing-at"] = False if failing is None else failing
    return failing


def _keeps_failing(forms, seen=None):
    """True when "keeps" is the fault verb, as in "my bread keeps coming out flat"."""
    return _keeps_failing_at(forms, seen) is not None
# The words that only point at a thing ("the condensation", "my snoring") and so say nothing
# about it; the framed reading is right only when the entry's subject part matches the rest.
_SUBJECT_POINTS = frozenset("a an the my your our his her its it of in on at for to".split())


def _the_whole_subject(part, forms, seen=None):
    """True when the entry's subject part matches every word the subject is made of.

    "what should i do about the damp patch" is a patch, not condensation: the entry whose subject
    part holds "damp" matches one word of it, and one word of a two-word subject is not what the
    ask is about.
    """
    span = set()
    for _weight, _words, hit in _part_matches(part, forms, seen):
        span.update(hit)
    wanted = [index for index, word_forms in enumerate(forms)
              if not (word_forms & _SUBJECT_POINTS)]
    return bool(wanted) and all(index in span for index in wanted)


def _rarity(entries):
    """{key word: how many entries use it}, so rare words can count for more."""
    counts = {}
    for item in entries:
        words = set()
        for part in item.key:
            for alternative in (part if isinstance(part, tuple) else (part,)):
                if isinstance(alternative, str):
                    words.update(alternative.lower().split())
        for word in words:
            counts[word] = counts.get(word, 0) + 1
    return counts


def _rank(item, forms, rarity, seen=None):
    """Score plus specificity: a key word only a few entries use says more about the line."""
    total = 0
    says_what = False
    for part in item.key:
        weight, words, _ = _part_match(part, forms, seen=seen)
        total += weight + sum(1 for word in words if rarity.get(word, 0) == 1)
        if any(word not in ASK_FRAME and word not in WHEN_WORDS for word in words):
            says_what = True
    if not says_what:
        # Every word this row reached the line with is how the line was asked or when the thing
        # happens, and neither is what the line is about. "what should i do about the toilet
        # flushing all night" reached the hour-before-bed row on "what should i do" and "night"
        # and was told to switch the screens off, while the row for the toilet scored one point
        # lower on the words it is actually about; "the heating comes on at night for no reason"
        # reached the same row the same way. Asking and when are the wrapping of a line, so a row
        # made only of them is ranked behind every row that names something, and it still answers
        # on its own where the line names nothing else ("what should i do at bedtime").
        # The bias is not counted either: it is there to settle two rows that both name the
        # line's subject, and this one has not named it.
        return 1
    return total + item.bias


# The knowledge base does not change during a conversation, so the rarity of every key word
# and the words it knows are worked out once per entries list and kept for the next turn.
_CACHE = {}
_CACHE_KEEP = 6


def _key_words(item):
    """The words the entry's key asks for, as written in it ("roast chicken" gives two)."""
    words = set()
    for part in item.key:
        for alternative in (part if isinstance(part, tuple) else (part,)):
            if isinstance(alternative, str):
                words.update(alternative.lower().split())
    return words


_KEY_FORMS = {}


def _key_forms(item):
    """Every form of every word the entry's key asks for, worked out once for the entry.

    Read by the two-position test in score(), which is asked about the same few thousand
    entries on every line. The entry is kept beside its forms because the card is keyed by id:
    an Entry a test built and let go must not be read as the one that took its id.
    """
    got = _KEY_FORMS.get(id(item))
    if got is not None and got[0] is item:
        return got[1]
    forms = set()
    for part in item.key:
        for alternative in (part if isinstance(part, tuple) else (part,)):
            if isinstance(alternative, str):
                for word in alternative.lower().split():
                    forms |= _forms(word)
    forms = frozenset(forms)
    if len(_KEY_FORMS) >= _FORMS_CACHE_KEEP:
        _KEY_FORMS.clear()
    _KEY_FORMS[id(item)] = (item, forms)
    return forms


def _two_positions(forms, item):
    """True when the line can have a form of the entry's key in two different places.

    score() answers 0 to an entry that covers fewer than two positions of the line, and an
    entry with one of its key's words in the line covers one position at most. Reading the
    line for the entry's forms is a handful of set tests, while the parts of its key are a few
    dozen phrase questions, so the entries that can only score 0 are dropped here: on a random
    deck turn that is 63% of the entries the line reaches. A phrase of the key needs its words
    side by side, which this does not check, so what it finds is an upper bound: no entry it
    drops could have covered two positions.
    """
    key = _key_forms(item)
    found = False
    for word_forms in forms:
        if not word_forms.isdisjoint(key):
            if found:
                return True
            found = True
    return False


def _word_index(entries):
    """{form: [positions of the entries that ask for it]}, so a line starts from its own words.

    score() gives an entry 0 unless two different words of its key are in the line, so an entry
    that shares no word with the line can never win it. The knowledge base is 2,500 entries and
    a line has six words, so walking every entry a turn cost a reply about a second of processor
    time; looking up the words the line does have cuts the scan to the entries that can answer it
    at all. Positions keep the registry's order, which the tie-break in `_best` needs.
    """
    cached = _INDEX.get(id(entries))
    if cached is not None and cached[0] is entries:
        return cached[1]
    index = {}
    for position, item in enumerate(entries):
        for word in _key_words(item):
            for form in _forms(word):
                at = index.get(form)
                if at is None:
                    index[form] = [position]
                elif at[-1] != position:
                    at.append(position)
    while len(_INDEX) >= _CACHE_KEEP:   # keep the list itself, so its id cannot be reused
        _INDEX.pop(next(iter(_INDEX)))
    _INDEX[id(entries)] = (entries, index)
    return index


_INDEX = {}


def _reaching(entries, forms):
    """The entries that share a word with the line, in the registry's order, or all of them.

    A line of unknown words (a name, "ok then") reaches nothing, and the caller still has to see
    every entry, so an empty answer is passed on as the whole list rather than as no candidates.
    """
    index = _word_index(entries)
    hit = set()
    for word_forms in forms:
        for form in word_forms:
            positions = index.get(form)
            if positions:
                hit.update(positions)
    if not hit:
        return entries
    return [entries[position] for position in sorted(hit)]


def _domain_rarity(entries):
    """({domain: {key word: how many of its entries use it}}, every key word once)."""
    by_domain, every = {}, {}
    owners = {}
    for item in entries:
        domain = getattr(item, "domain", "") or ""
        counts = by_domain.setdefault(domain, {})
        words = set()
        for part in item.key:
            for alternative in (part if isinstance(part, tuple) else (part,)):
                if isinstance(alternative, str):
                    words.update(alternative.lower().split())
        for word in words:
            counts[word] = counts.get(word, 0) + 1
            owners.setdefault(word, set()).add(getattr(item, "id", None) or id(item))
    for word in owners:
        if owners[word] <= SLIPS.get(word, set()):
            continue                    # a misspelling only the spelling answers list
        every[word] = len(owners[word])
    return by_domain, every


def _vocabulary(entries):
    """Per-domain rarity, every key word, and the forms the knowledge base knows."""
    cached = _CACHE.get(id(entries))
    if cached is not None and cached[0] is entries:
        return cached[1], cached[2], cached[3]
    by_domain, every = _domain_rarity(entries)
    slips = {slip.lower() for item in entries for slip in getattr(item, "slips", ())}
    # `every` keeps its counts, it does not become a set of words: it is the rarity of the whole
    # knowledge base, and it is what `_rank` falls back on when an entry's own domain has no
    # counts. A domain is set on an entry when the registry collects it, so an entries list can be
    # read before its domains exist; handing `_rank` a set there raised on `rarity.get` and took
    # the whole turn down with it.
    every = {word: count for word, count in every.items() if word.lower() not in slips}
    known = set()
    for word in every:
        known |= _forms(word)
    if all(getattr(item, "domain", "") for item in entries):
        # Only a list whose entries already know their domain. The registry sets the domain on
        # every entry the first time it is built, so a list cached before that would keep the
        # per-domain counts of the empty domain and rank a "family" line against no words.
        while len(_CACHE) >= _CACHE_KEEP:  # keep the list itself, so its id cannot be reused
            _CACHE.pop(next(iter(_CACHE)))
        _CACHE[id(entries)] = (entries, by_domain, every, known)
    return by_domain, every, known


# A "-y" word whose stem is a different everyday word of its own, so the stem is not what the
# person meant: "are you ready" is not reading, "i'm busy" is not a bus, a "handy" shelf is not
# a hand, "a birthday party" is not a part, and "my belly" is not a bell. Everything else that
# ends this way is the same thing said as an adjective, which is what the rule below reads.
NOT_THE_ADJECTIVE = frozenset("""
    ready busy handy party army belly copy body study lady fully funny pity cosy policy every
    bully tally holy early rally holly jelly apply battery cheeky dicky factory fairy gravy
    irony kindly multiply pasty silly shiny story whisky clammy telly chilly watery shivery
    sticky
""".split())


def _y_word_stems(word):
    """The thing a "-y" word describes, as the word under the adjective.

    "my tap is leaky" is the leak entry's line, "a creaky gate" the creak one's, "a scaly
    kettle" the scale one's, "squeaky brakes" the squeak one's. The matcher only ever handed
    these the plural-looking "leakies", so an adjective the person typed never met a key that
    lists the noun or the verb behind it: "how do i fix a leaky tap" was answered while "the
    garden gate is creaky", "my kettle is scaly" and "my car brakes are squeaky" all got "Got
    it. Is there anything you'd like a hand with?".

    English builds the adjective two ways - on the word itself (leak, smell, creak, rust) and on
    an "e" the adjective drops (noise, grease, scale, taste) - so both are offered. Only those
    two shapes: the doubled consonant of "muddy" or "runny" is not chased, because the short
    word under it is as often a different one ("runny nose" is not a run, "sorry" is not sore).
    A stem shorter than MIN_FORM, or one from a word whose stem is an everyday word of its own
    (NOT_THE_ADJECTIVE), is not offered either.
    """
    if len(word) < 5 or not word.endswith("y") or word[-2] in "aeiouy":
        return ()
    if word in NOT_THE_ADJECTIVE:
        return ()
    stem = word[:-1]
    return tuple(form for form in (stem, stem + "e") if len(form) >= MIN_FORM)


def _a_word_itself(word):
    """True when the understanding engine holds this exact word, not only a relative of it."""
    return (word in _COMMON or word in COMMON_WORDS or word in lexicon.CHAT
            or word in lexicon.EXPAND)


def _read_the_adjective(words, forms, vocabulary):
    """Add the thing each "-y" line word describes, where the knowledge base asks for it.

    Only a stem some entry already keys as a word counts, so the rule cannot reach anything the
    knowledge base does not ask about. It is a second read of a line that reached no entry as
    typed: the words are the same, and the row that keys the adjective itself has already had
    its turn, so "my rice came out really sticky again" stays with the sticky rice row rather
    than being pulled to a pan-sticking one by the "stick" inside it.
    """
    gave = False
    for index, word in enumerate(words):
        # A word that is a word of its own is not the adjective over a noun: "footy" is how
        # half the country says football, and read as "foot" it put "watched the footy last
        # night" on the swollen-ankles card, because that entry keys "foot" and "night" and the
        # line held both. Only a word the engine holds is left alone, not one it knows a
        # relative of: "squeaky" and "creaky" are the brake and the hinge, and the stems are
        # exactly the words those rows ask for.
        if _a_word_itself(word):
            continue
        for stem in _y_word_stems(word):
            if stem in vocabulary and stem not in forms[index]:
                forms[index] |= {stem}
                gave = True
    return gave


def _read_typos(words, forms, vocabulary, known):
    """Add the key word each misspelt line word is a single slip away from, in place.

    Only a word that is not a word of its own is read as a slip. A key word the knowledge base
    knows is left alone, and so is any ordinary English word, in any of its forms: "charging"
    is a form of one, so a slip of "changing" cannot be invented out of it, and "write" and
    "leave" are words themselves.
    """
    for index, word in enumerate(words):
        if forms[index] & known or _engine_reads(word):
            continue
        if "'" in word:                 # a contraction or possessive is never a slip
            continue
        forms[index] |= _typo_forms(word, vocabulary)


# Adverbs that turn "what do I say" into "what do I actually say" without changing what is
# asked. They are dropped only for a second read of a line that reached no entry as typed.
_FILLER = frozenset(("actually", "really", "honestly", "literally", "genuinely", "basically"))


def _without_possessive(word):
    """The word without a possessive on the end: "earth's" and "earths" are "earth"."""
    for tail in ("'s", "\u2019s"):
        if word.endswith(tail):
            return word[:-2]
    return word


# A feeling about a thing makes the line a line about the person: "my son looks sad about his
# bike" is not a question about the size of a bike, and "my mum is upset about her garden" is not
# a how-to about a garden. The thing is only the occasion of the feeling, so the words that name
# it are taken out of what the knowledge base reads, and the rest of the line is read as usual:
# "my back hurts and im worried about work" still reaches the back, because the words that match
# it sit outside the phrase. "bored" is not here on purpose - bored children do want the thing
# that fills an afternoon, and that answer is a good one.
FEELING_ABOUT_A_THING = FEELING_WORDS + (
    "sad", "sadness", "unhappy", "scared", "frightened", "lonely", "gutted", "devastated",
    "heartbroken", "annoyed", "annoying", "furious", "cross", "upsetting", "fuming",
)

FEELING_ABOUT = frozenset("about of with over at by".split())

# What ends the thing a feeling is about: a new clause, another person, or a word that is a time
# rather than a thing.
FEELING_ENDS = frozenset("""
    and but because so then when if that which who whom whose or also plus after before since
    till until while though although yet today tomorrow tonight now yesterday again too as
    i im ive id we they he she them us
""".split())

# A bare pronoun names nothing to take away: "upset about it" keeps its words.
FEELING_NAMES_NOTHING = frozenset("""
    it them everything nothing anything something all
""".split())

# The domains whose cards answer a person's feeling rather than a thing: a line that reaches one
# of these keeps every word, because "my son is scared of the dark" wants the card about a
# child's fear, not a line about a dark room, and "worried about my rent" wants the rent card.
FEELING_DOMAINS = frozenset(("family", "friends", "study", "health", "sleep", "pregnancy",
                             "money", "work", "lifeadmin",
                             # A card about a thing the feeling is about is not a card about the
                             # feeling, whichever module it lives in: "worried about my knee pain"
                             # is a knee question, "my daughter is upset about her friend" wants
                             # what to say to the friend, and "worried about my flight tomorrow"
                             # wants the flight. Stripping the words that name the thing left
                             # those lines with nothing, so the modules they are filed in are
                             # listed here. This is the module name, not a list of subjects.
                             "body", "wording", "complaints", "travel", "home"))

# A broken thing is the subject of the line even when the line also says how it feels: "im
# worried about my washing machine leaking" wants the water off, not sympathy.
FEELING_FAULT_WORDS = frozenset("""
    leak leaks leaked leaking drip drips dripping burst bursts bursting broken broke breaks
    blocked blocking stopped stops smoking sparking smells smelly smell damp mould mold
    flooded flooding flood loose wobbles wobbling snapped cracked clicking noisy
""".split())


def _names_a_fault(occasion):
    """Whether the thing a feeling is about is a thing that is broken."""
    return bool(FEELING_FAULT_WORDS.intersection(str(word).lower() for word in occasion))


# A fear the person speaking has is a question about the thing feared: "im scared of the dentist"
# wants the dentist card, "im scared of flying" the one about flying. The same words about someone
# else are the occasion of their feeling: "my son is worried about football practice" does not
# want a page about practice. So when the line has the speaker's own feeling, every word stays.
FEELING_SPEAKER = frozenset(("i", "im", "ive", "i'm", "i've", "id", "me", "myself"))


def _speaker_is_feeling(words):
    """Whether the speaker is the one with the feeling, not somebody the line is about."""
    low = [str(word).lower() for word in words]
    for pos, word in enumerate(low):
        if word not in FEELING_ABOUT_A_THING \
                and not (word == "fed" and low[pos + 1:pos + 2] == ["up"]):
            continue
        for back in low[max(0, pos - 6):pos]:
            if back in FEELING_SPEAKER:
                return True
    return False


# Some things are not the occasion of a feeling but the thing itself: people are frightened of a
# short list of things as a class, and the card about that thing is the answer. "my son is scared
# of the dentist" wants the dentist card, not sympathy, and "im scared of flying" the one about
# the first flight - while "my son is worried about football practice" is a boy's afternoon.
FEARED_THINGS = frozenset("""
    dentist dentists dentistry dental flying plane planes flight flights needles needle
    injections injection jab jabs spiders spider snakes snake heights height lifts lift
    escalators dark thunder lightning storms storm blood vomit sick wasps bees mice rats
    clowns hospitals hospital doctors doctor dentists surgery operation operations
    presentations public presentations interviews interview exams exam tests test motorways
    motorway driving flying ferries tunnels enclosed spaces crowds dentists darkness
    water swimming swim pool pools
""".split())


def _names_a_feared_thing(occasion):
    """Whether the thing a feeling is about is a thing people are afraid of as a class."""
    return bool(FEARED_THINGS.intersection(str(word).lower() for word in occasion))


def _feeling_occasion(words):
    """The words naming the thing a feeling is about, or None.

    "how do i stop feeling anxious about my exams" leaves the ask and the feeling itself, so the
    anxiety card keeps the line.
    """
    low = [str(word).lower() for word in words]
    for pos, word in enumerate(low):
        if word not in FEELING_ABOUT_A_THING \
                and not (word == "fed" and low[pos + 1:pos + 2] == ["up"]):
            continue
        at = pos + 1
        if at < len(low) and low[at] in ("up", "off"):
            at += 1
        if at >= len(low) or low[at] not in FEELING_ABOUT:
            continue
        got = []
        for word_after in low[at + 1:at + 6]:
            if word_after in FEELING_ENDS or not word_after.isalpha():
                break
            got.append(word_after)
        if not [word for word in got if word not in FEELING_NAMES_NOTHING]:
            continue
        return got
    return None


# A thing that has been put down and cannot be found is not a fact about the thing. "where did i
# put the nappy cream" was answered with which barrier cream to buy and "where is my nappy bag"
# with what to pack in one, and the right reply to both is somewhere to look. That answer does
# not depend on what the thing is, so no row can be better at it than another: the whole base
# stands down and the composer's loss reading takes the line. Only the asking, not the naming: a
# row that says where a thing is kept ("where do i keep my passport") is answering a different
# line and is untouched.
_WHERE_I_PUT = re.compile(r"\bwhere\s+(?:did|have|has|had)\s+i\s+(?:put|leave)\b")


def find(understood, entries=None, reject=None, use_context=False):
    """The best Entry for this reading of a line, or None when nothing fits.

    understood: memory["understood"], with "clean" and/or "words".
    entries: an explicit list (tests); by default every domain in bot/knowledge.
    reject: a callable given an Entry; when it says True the entry is passed over and the next
    best is returned. An entry whose reply turns a line down ("how long do i cook it for" after
    mince) should not eat the turn that a lower entry can still answer.
    use_context: also search the line this one leans on, and only when the line alone reached
    nothing. Off by default, because a line that finds its own entry must be answered from its
    own words; the module that has read the conversation turns it on for a follow-up, which
    names no subject of its own ("How long in the oven?", "And if I stuff it?"), so the words
    the understanding engine hands on in `leans_on` are searched as well.

    The line is read as it was typed first, and every entry either line can reach is kept. Only
    when the typed line reaches nothing, and it is a line about somebody the person looks after,
    is it read again as the ask about that thing: "my daughter has head lice" is a question about
    head lice, and the comb is the answer - while a line that already has its card ("my baby is
    teething" is the teething card) is answered by it exactly as before.
    """
    if entries is None and _WHERE_I_PUT.search(
            " ".join(tokens(understood.get("clean") or understood.get("text") or ""))):
        # The answer is the composer's loss pool, and it is the same for every thing.
        return None
    found = _the_best_entry(understood, entries, reject, use_context)
    if found is not None:
        return found
    for again in _what_is_wrong_with_them(understood):
        found = _the_best_entry(again, entries, reject, use_context)
        if found is not None:
            return found
    for again in _a_thing_that_has_not_gone(understood):
        found = _the_best_entry(again, entries, reject, use_context)
        if found is not None:
            return found
    return None


# A thing reported as not gone is a thing still there, and it is the commonest way people say a
# symptom has not shifted: "the cough has not gone", "the rash hasnt gone", "my knee hasnt got any
# better". Cards are keyed on the ask ("still there", "wont go", "how do i treat"), so the report
# reached nothing and the person got a nod. The clause saying it has not gone is the news, not the
# subject, so the rest of the line is read again as the ask about the thing it named.
_NOT_GONE = re.compile(
    r"\b(?:has|have|had|is|are|was|were|does|did)?\s*(?:not|n't|never)\s+"
    r"(?:gone|gone away|shifted|cleared|cleared up|eased|settled|improved|any better|got any better|"
    r"got better|better)\b|\bno better\b|\bwont\s+go\b|\bwon't\s+go\b|\bwould\s+not\s+go\b",
    re.I)

_SUBJECT_LEAD = re.compile(r"^(?:and|but|so|well|ok|okay|hi|hello|um|er)\b[,\s]*", re.I)
_POSSESSIVE = re.compile(r"^(?:the|my|his|her|their|our|your|a|an|this|that|these|those)\s+", re.I)


def _a_thing_that_has_not_gone(understood):
    """The same line read as the ask about the thing said not to have gone.

    Only the report is reshaped: the words before "has not gone" are the thing. Two openers are
    tried for the same reason `_what_is_wrong_with_them` tries two - a card is keyed on one ask
    and not the other ("a rash that wont go away" finds the rash card, "how do i treat a rash"
    finds it too, while a bare "the rash" is not an ask).
    """
    if not isinstance(understood, dict):
        return []
    clean = understood.get("clean") or understood.get("text") or ""
    said = _NOT_GONE.search(clean)
    if not said:
        return []
    thing = _SUBJECT_LEAD.sub("", clean[:said.start()].strip(" ,.;:!?"))
    thing = _POSSESSIVE.sub("", thing).strip()
    if not thing or len(thing.split()) > 5:
        return []
    again = []
    for said_so in ("a %s that wont go away" % thing,
                    "how do i treat %s" % thing,
                    "%s still there" % thing):
        shaped = dict(understood)
        shaped["clean"] = said_so
        shaped["words"] = tokens(said_so)
        again.append(shaped)
    return again


def _what_is_wrong_with_them(understood):
    """The same reading with a carer's line read as the ask about the thing named, or it back.

    "my daughter has head lice", "our baby's got conjunctivitis", "my son caught chickenpox": the
    child and the having are the shape of the sentence, not what it is about, and no card is keyed
    on them. A bare "head lice" is not an ask either, so the rest of the line is read as the ask
    it is - "how do i deal with head lice" - and the words of that ask are ones every card ignores.
    Two openers are tried, because a card that answers a condition is keyed on the condition and the
    opener it expects is not the same everywhere ("how do i treat shingles" finds it, "how do i deal
    with shingles" does not). A blunt "what do i do for <thing>" is not among them: it answered a
    water infection with the dry-eye card.
    """
    if not isinstance(understood, dict):
        return []
    cared = _past_the_carer(understood.get("clean") or understood.get("text") or "")
    if not cared:
        return []
    again = []
    for opener in ("how do i deal with ", "how do i treat "):
        said = opener + cared
        shaped = dict(understood)
        shaped["clean"] = said
        shaped["words"] = tokens(said)
        again.append(shaped)
    return again


# The words a line spends on the refusal itself: with these and the ruled-out thing gone there is
# no subject left in the line for a card to be about.
_OF_THE_RULE_OUT = dict.fromkeys("""not a an the rather than instead of and but or please really
actually just so though although is are was were be been do does did""".split(), True)


def _without_the_ruled_out(understood):
    """The same reading with the words of the thing the line rules out taken out.

    "for a holiday not a house" is read as "for a holiday": the house-left-empty card opens on
    "house" and closes on "holiday", and the person had just said it was not a house. Only the
    reading a card is chosen from loses the words; the line itself is untouched, so every other
    module is still told what they said.
    """
    gone = [str(word).strip().lower() for word in understood.get("ruled_out") or []
            if str(word).strip()]
    if not gone:
        return understood
    clean = understood.get("clean") or ""
    words = understood.get("words")
    if not isinstance(words, list) or not words:
        words = tokens(clean)
    wanted = list(gone)
    left = []
    for word in words:
        key = word.lower() if isinstance(word, str) else ""
        if key and key in wanted:
            wanted.remove(key)
            continue
        left.append(word)
    if not [word for word in left if _OF_THE_RULE_OUT.get(str(word).lower()) is None]:
        # The line is the refusal and nothing else ("not a series", after the film list). There
        # is nothing left to choose a card from, so the line stays whole and the readers that
        # answer a refusal ("not a series" narrows the list they have) get it as typed.
        return understood
    read = dict(understood)
    read["words"] = left
    read["clean"] = " ".join(word for word in left if isinstance(word, str))
    return read


def _the_best_entry(understood, entries=None, reject=None, use_context=False):
    """The best Entry for this reading of a line, or None when nothing fits."""
    if not isinstance(understood, dict):
        return None
    understood = _without_the_ruled_out(understood)
    clean = understood.get("clean") or ""
    words = understood.get("words")
    # The understanding layer splits on the curly apostrophe a phone writes, so "doesn’t"
    # arrives here as "doesn" and "t" and no key can match it. The clean text still has it,
    # so take the words from there whenever the line carries one.
    if not isinstance(words, list) or any(ch in clean for ch in _CURLY_ANY):
        words = tokens(clean)
    past = _past_a_handoff(clean)
    if past:
        # The hand-off in front of the line is not what it is about. "one more thing about the
        # boiler" reached the study entry on the words "one" and "thing".
        words = tokens(past)
    # Only the half of the surprise the line still holds: "the hell" is in the line, "on earth"
    # was taken out of it before the reading, and dropping "earth" as well lost the planet from
    # "what on earth is the earth made of".
    left = understood.get("intensifier_left")
    intensifier = understood.get("intensifier") if left is None else left
    if isinstance(intensifier, list) and intensifier:
        # "on earth" and "the hell" name nothing the line is about, so an entry keyed on one of
        # those words must not answer it - not even when the line names a subject of its own.
        # "what on earth is wrong with my boiler" is about the boiler, and the planet's layers
        # were the answer to it. Unlike `background`, this is dropped either way.
        going = {}
        for word in intensifier:
            if isinstance(word, str):
                going[word.lower()] = going.get(word.lower(), 0) + 1
        kept = []
        for word in reversed(words):
            key = word.lower() if isinstance(word, str) else ""
            # The typed word carries the possessive the reading has already taken off: "what on
            # earth's going on" hands over "on earth" and types "earth's", and the planet's
            # layers answered it because the drop compares whole words.
            stem = _without_possessive(key)
            hit = key if going.get(key) else (stem if going.get(stem) else "")
            if hit:
                going[hit] -= 1
                continue
            kept.append(word)
        words = kept[::-1]
    background = understood.get("background")
    if isinstance(background, list) and background and not understood.get("topic_own"):
        # A word that only says WHEN or WHERE it happened is not what the line is about: "it
        # started at work in the garden centre" is about whatever started, and no entry keyed
        # on "garden" answers it. Only a line that names no subject of its own is read this
        # way: a line with one keeps every word of its clause ("i was in the garden when the
        # garden flooded" still reaches the flood), and a line that carries a topic over from
        # the turn before is still answered by the words it typed.
        drop = {}
        for word in background:
            if isinstance(word, str):
                drop[word.lower()] = drop.get(word.lower(), 0) + 1
        kept = []
        for word in reversed(words):
            key = word.lower() if isinstance(word, str) else ""
            if drop.get(key):
                drop[key] -= 1
                continue
            kept.append(word)
        words = kept[::-1]
    if understood.get("kind") == "empty":
        return None
    occasion = _feeling_occasion(words)
    if occasion and not understood.get("asks") and understood.get("topic") != "pets" \
            and not _names_a_fault(occasion) and not _speaker_is_feeling(words) \
            and not _names_a_feared_thing(occasion):
        # "my son looks sad about his bike" is about the son, and the bike is the occasion: the
        # words that name it are taken out of what the knowledge base reads. An ask keeps every
        # word ("how do i stop feeling anxious about my exams" is the anxiety card), and a line
        # whose other words still reach a card keeps that card ("my back hurts and im worried
        # about work" is still the back). Four things keep every word as typed, because the
        # card is about the feeling already: the speaker's own feeling ("im scared of the
        # dentist", "im scared of flying"), a card from a domain about people ("my son is
        # scared of the dark", "worried about her rent"), a thing that is broken ("worried
        # about the washing machine leaking"), and an animal ("my dog is scared of fireworks"
        # wants the fireworks night planned).
        if entries is None:
            from . import entries as all_entries  # the registry, to avoid an import cycle
            entries = all_entries()
        seen_in, known_words, _ = _vocabulary(entries)
        here = _best(understood, words, clean, [_forms(word) for word in words],
                     [word.lower() for word in words if isinstance(word, str)],
                     entries, seen_in, known_words, reject)
        if here is None or here.domain not in FEELING_DOMAINS:
            gone = {}
            for word in occasion:
                gone[word] = gone.get(word, 0) + 1
            kept_words = []
            for word in reversed(words):
                key = word.lower() if isinstance(word, str) else ""
                if gone.get(key):
                    gone[key] -= 1
                    continue
                kept_words.append(word)
            words = kept_words[::-1]
    original = words
    stripped = False
    if "dead" in [str(word).lower() for word in words]:
        words = _without_a_dead_that_only_means_very(words)
        stripped = len(words) != len(original)
    if "cooking" in [str(word).lower() for word in words]:
        words = _without_a_cooking_that_is_a_name(words)
        stripped = stripped or len(words) != len(original)
    words = _with_the_child_by_place(words, clean)
    forms = [_forms(w) for w in words]
    if entries is None:
        from . import entries as all_entries  # the registry, to avoid an import cycle
        entries = all_entries()
    by_domain, every, known = _vocabulary(entries)
    typed = [word.lower() for word in words if isinstance(word, str)]
    if about_the_chat(understood.get("text") or clean):
        return None      # "how did this chat start" is the memory store's line, not a fact
    _read_typos(typed, forms, every, known)
    # An advice ask names its subject once and spends the rest of the line asking, so the subject
    # is the whole subject and is read first: "what should i do about slugs" was answered with the
    # tablespoons card, because "slug" is also how a cook says a small splash.
    wrapped = _wrapped_subject(clean, understood.get("norm_text"))
    whole = _best(understood, words, clean, forms, typed, entries, by_domain, every, reject)
    whole = _the_answer_the_colour_dragged_in(
        whole, understood, words, clean, entries, by_domain, every, reject)
    item = None
    if wrapped:
        item = _the_ask_it_wraps(understood, wrapped, whole, entries, by_domain, every, reject)
    if item is None:
        item = whole
    # The adverbs people put between the words that matter ("what do I actually say?", "how
    # does it really work") are the person leaning in, not a subject, and no keyed phrase holds
    # one: a line that reached nothing as typed is read once more without them. Only then, so a
    # key that wants the word keeps it.
    filler = _FILLER.intersection(typed)
    kept = [word for word in words if str(word).lower() not in _FILLER] if filler else []
    bare = None
    if filler:
        bare = dict(understood)
        bare["clean"] = " ".join(str(word) for word in kept)
    if item is None and bare is not None:
        item = _best(bare, kept, bare["clean"], [_forms(word) for word in kept],
                     [word.lower() for word in kept if isinstance(word, str)],
                     entries, by_domain, every, reject)
    # Taking the "dead" out is a reading, not a deletion. "the car is dead slow to start" says
    # the car is very slow to start, and the car's own answer is keyed on the word that was
    # taken out, so with the word gone the line reaches nothing and a thing with a known fault
    # gets a shrug. A line that reaches nothing without it is read once more with it, which is
    # the same second look the filler words above get, and only then: an entry that a describing
    # word could drag in must not get in front of a line that had an answer of its own.
    if item is None and stripped:
        item = _best(understood, original, clean, [_forms(word) for word in original],
                     [word.lower() for word in original if isinstance(word, str)],
                     entries, by_domain, every, reject)
    # A line that reached nothing as typed is read once more with the thing each "-y" word
    # describes: "the garden gate is creaky", "my kettle is scaly", "my car brakes are squeaky".
    # A second look and not a wider first one, because the words are otherwise the same and an
    # entry keyed on the adjective itself has already had its turn at them ("my rice came out
    # really sticky again" is the sticky rice row, not a pan-sticking one).
    if item is None:
        described = list(forms)
        if _read_the_adjective(typed, described, every):
            item = _best(understood, words, clean, described, typed, entries, by_domain, every,
                         reject)
    # A follow-up may only search the line before it when it really leans on it: a question that
    # left its subject out, or one that points back at the thing ("is that bad", "i feed it twice
    # a day"). A statement that names its own subject does not - see `leans_on_a_subject`.
    if item is None and use_context and understood.get("leans_on") \
            and leans_on_a_subject(understood):
        item = _following_on(understood, entries, forms, typed, by_domain, every, known, reject)
        if item is None and bare is not None:
            # The phrase the follow-up is keyed on carries a filler too: "what do i actually
            # say?" after a friend line is the same ask as "what do i say?".
            item = _following_on(
                understood, entries, [_forms(word) for word in kept],
                [word.lower() for word in kept if isinstance(word, str)],
                by_domain, every, known, reject)
        # An advice ask that names a subject of its own has changed the subject, so the answer the
        # last turn was about does not stand in for it: after two turns about the lawn, "what
        # should i do about my ex" was a mowing question. The carry-over is right only when the new
        # subject is the old entry's own language ("what should i do about the smell" after a
        # fridge turns on "smell", which the fridge entry holds).
        if item is not None and wrapped and not about(item, wrapped):
            item = None
    if item is not None and _the_animal_rules_out_that_card(item, understood):
        # The card that took the turn is one the animal the line points at stands down for, so
        # the animal is the word the line is missing: "she's been drinking a lot more water"
        # after a cat reached the figure for a person's own water, and the same line with the cat
        # said is the cat's own answer. A card that holds no such word reached the line on its own
        # words and keeps the turn - after an answer about a cat hunting, "she's brought in two
        # this week" is that answer's continuation, not a fresh card that fits the animal too.
        pointed = _with_the_animal_in_hand(words, understood)
        if pointed is not words:
            better = _best(understood, pointed, clean, [_forms(word) for word in pointed],
                           [word.lower() for word in pointed if isinstance(word, str)],
                           entries, by_domain, every, reject)
            if better is not None:
                item = better
    if item is None:
        # "what is a semicolon for" is a definition, and a definition names one thing and asks
        # nothing else: it fails the two-signal rule for the row that knows the thing, and every
        # row that answers the how-to got a shrug. See `_the_thing_asked_about`.
        item = _defines(understood, forms, typed, entries, reject)
    if item is None:
        # A line that is only the name of a thing is that thing raised, and the card that
        # answers the thing said in a sentence answers it too. After the definition ask,
        # because a line that is only a name is also what a definition is and the older reader
        # keeps first claim on the lines it already answered; last of all, so a line with an
        # answer of its own keeps it.
        item = _the_name_alone(_the_name_card([str(word).lower() for word in words],
                                             entries, reject,
                                             _topic_domains(understood, entries)),
                               entries, reject, _topic_domains(understood, entries),
                               understood, words, use_context)
    return item


# "what is a semicolon for" and "what is a deductible" name one thing and ask nothing else. That
# is a definition, and a definition is the commonest way a person asks about a word. The rows are
# written for the asks around a thing ("how do i use a semicolon", "is a warranty worth it"), and
# a definition line covers one position of such a key, so it fails the two-signal rule and the
# person got "I'm not sure about that one" about a thing the knowledge base already answers.
# These are the shapes of the definition ask; the thing is the rest.
_DEFINITION_ASK = re.compile(
    r"^\s*(?:so\s+|ok\s+|okay\s+|and\s+|but\s+)?"
    r"(?:"
    r"what\s*(?:'s|\u2019s|s)?\s+(?:is|are|was|were)\s+(?P<thing>[^?.!,;:]{1,60}?)"
    r"|what\s*(?:'s|\u2019s|s)\s+(?P<thing2>[^?.!,;:]{1,60}?)"
    r"|what\s+(?:does|do)\s+(?P<thing3>[^?.!,;:]{1,60}?)\s+mean"
    r"|define\s+(?P<thing4>[^?.!,;:]{1,60}?)"
    r")\s*(?:\?)?\s*$", re.I)
# The words of the ask that are not the thing asked about, including the tail a person puts after
# it ("what is a semicolon for", "what is an isa exactly", "whats an isa please").
_DEFINITION_TAIL = frozenset("""
    for mean means meant exactly then again please called thats it its in simple terms
    supposed to do stand stands actually really even anyway though
""".split())
# Words too empty to be the thing asked about, so "what is it" and "what is that" stay a punt.
# A thing that opens with one of these is pointing at something said a turn ago, or asking what
# there is to do somewhere, and no key names it.
_DEFINITION_POINTERS = frozenset("""
    there it that this these those he she they we you i someone anyone somebody nobody
""".split())
# A trouble word in the thing means the line is a diagnosis, not a definition: "what is wrong with
# my knee" asks what is the matter, and the row that knows about knees says where the saddle goes.
# None of these can be part of the name of a thing somebody wants defined, so the line is left to
# the readers that answer a problem.
_DEFINITION_TROUBLE = frozenset("""
    wrong matter happening pain painful hurts hurt hurting ache aches aching smell smells smelling
    leak leaks leaking noisy noise broken stuck faulty fix
""".split()) | {"going on", "up with", "up to"}

_DEFINITION_EMPTY = frozenset("""
    a an the my your our their his her its some any this that these those of in on at to and or
    for with from about it that this there here one ones thing things stuff kind sort type
    what which who whom whose how why when where right best good
    going happening wrong up on around next
""".split())


def _the_thing_asked_about(clean):
    """The thing a definition line asks about, as its words, or () when it is not one."""
    if not isinstance(clean, str) or not clean.strip():
        return ()
    found = _DEFINITION_ASK.match(clean.strip().lower())
    if not found:
        return ()
    thing = next((part for part in found.groups() if part), "")
    opening = (thing.split() or [""])[0].strip("'\"-")
    if opening in _DEFINITION_POINTERS:
        # "what is there to do in hastings" asks what a place has to offer, not what a word
        # means, and the battle of Hastings would answer it.
        return ()
    raw = thing.lower().replace("\u2019", "'")
    if any(word in _DEFINITION_TROUBLE for word in _words_of(raw)) \
            or any(phrase in " %s " % raw for phrase in ("going on", "up with", "up to")):
        # "what is wrong with my knee", "what is going on with my car", "what is up with my dog"
        # all ask what is the matter: a diagnosis belongs to the row that knows the thing, and a
        # card about the knee is the wrong answer to it.
        return ()
    words = []
    for word in thing.replace("\u2019", "'").split():
        word = word.strip("'\"-")
        if not word or word in _DEFINITION_EMPTY or word in _DEFINITION_TAIL:
            continue
        if len(word) < 2 and not word.isalpha():
            continue
        words.append(word)
    while words and words[-1] in _DEFINITION_TAIL:
        words.pop()
    return tuple(words[:3])


def _words_of(text):
    """The words of a phrase, lowercased and stripped of punctuation."""
    return [word.strip("'\"-?!.,;:") for word in text.split() if word.strip("'\"-?!.,;:")]


def _asks_what_it_is_for(clean):
    """True when the definition line asks what the thing is for, not what it is.

    "what is a semicolon for" is answered by what the thing does ("Use a semicolon to join two
    full sentences"), and "what is a warranty" by what the thing is ("A warranty is a bonus on
    top of your rights"). The two shapes are not interchangeable: a use is not a definition, and
    a definition is not an answer to what something is for.
    """
    if not isinstance(clean, str):
        return False
    return bool(re.search(r"\bfor\b\s*\??\s*$|\bused for\b|\bdo(?:es)? (?:it|that|this) do\b",
                          clean.strip().lower()))


# The verbs a definition of a thing runs on: "A warranty is a bonus on top of your rights",
# "Food banks give a few days of free food". A thing the opening sentence only mentions on the way
# to something else is not being defined by it.
_DEFINING_VERBS = frozenset("""
    is are was were means mean refers gives give costs cost covers cover keeps keep works work
    helps help makes make takes take needs need holds hold comes come runs run lets let stops stop
    protects protect lets replaces replace counts count serves serve
""".split())


# The verbs that make a sentence say what something is, and the words that show a thing is
# only part of a phrase about something else.
_BE_VERBS = frozenset("is are was were".split())
# How many words may come before the thing in a defining sentence: "In the UK, a warranty is..."
# is a definition, "a cup of tea or coffee is mostly water" is not.
_SUBJECT_AT_MOST = 6
_DEFINITION_ARTICLES = frozenset("a an the".split())
_BEFORE_THE_THING = frozenset("""
    of in on with at from your my our their its his her
    cup mug glass slice piece bit bowl plate packet tin can bottle spoon teaspoon tablespoon
    handful pinch taste sip bite
""".split())


def _a_number(word):
    """True for a word with a digit in it ("4pm", "2nd", "500ml")."""
    return any(char.isdigit() for char in word)


def _the_thing_in(sentence, thing):
    """Where the whole thing is said as one phrase in the sentence, or None."""
    words = [word.lower() for word in tokens(sentence) if isinstance(word, str)]
    wanted = [_forms(word) for word in thing]
    for start in range(len(words) - len(wanted) + 1):
        run = words[start:start + len(wanted)]
        if all(_forms(word) & want for word, want in zip(run, wanted)):
            return start, words
    return None


def _the_reply_defines(reply, thing, purpose=False):
    """True when the reply's opening sentence defines the thing, so a definition ask is answered.

    Every word of the thing has to be said as one phrase: the row that answers an abnormal smear
    result says "An abnormal smear means some cells looked a little different", which names half
    of "smear test" and answers a different question, and the shower row says "the wet air stays
    in the room" about a wet room.
    Then the phrase has to be doing the defining - what it is ("A warranty is a bonus on top of
    your rights") or, when the person asked what it is for, what it does ("Use a semicolon to
    join two full sentences"). A row that merely mentions the thing while answering something
    else stays out: "Who owns a boundary fence is in the deeds" is about a fence.
    """
    if not isinstance(reply, str) or not reply.strip():
        return False
    opening = re.split(r"(?<=[.!?])\s", reply.strip(), maxsplit=1)[0]
    found = _the_thing_in(opening, thing)
    if found is None:
        return False
    if found[0] > _SUBJECT_AT_MOST:
        # A definition says what the thing is in its own opening words, so the thing has to be
        # near the front: "No, not in ordinary amounts: a cup of tea or coffee is mostly water"
        # is an answer about whether coffee dehydrates you, and it does not define coffee.
        return False
    if purpose:
        return True
    start, words = found
    if start and words[0] not in _DEFINITION_ARTICLES:
        # The phrase before the thing has to open with an article: "A short nap is worth having"
        # defines a nap, while "Ground coffee is at its best two weeks after opening" is about
        # storage and "Feet that are always cold" is about feet.
        return False
    before = words[:start]
    if any(word in _BE_VERBS for word in before):
        # A be-verb ahead of the thing means the sentence has another subject: "Feet that are
        # always cold are usually circulation" is about feet, and it does not define a cold.
        return False
    if before and (before[-1] in _BEFORE_THE_THING or _a_number(before[-1])):
        # "the top third of your CV", "a 4pm coffee", "the first cup of coffee": the thing sits
        # inside a phrase about a portion or a time, which is an example and not a definition.
        return False
    after = words[start + len(thing):start + len(thing) + 1]
    return bool(after) and after[0] in _DEFINING_VERBS


def _the_key_names_the_thing(item, thing):
    """True when one phrase of the entry's key is the thing itself, word for word.

    "what is a food bank" is the row keyed on "food bank", and the words are read the way every
    other match is read, so "will" reaches "wills" and "boundary" reaches "boundaries". A key
    that only holds the words inside a longer phrase is about that longer phrase - "boundary
    fence" is not a definition of a boundary, "sports wash" is not a sports bra - so the phrase
    has to be as long as the thing.
    """
    wanted = [_forms(word) for word in thing]
    for part in item.key:
        for alternative in (part if isinstance(part, tuple) else (part,)):
            if not isinstance(alternative, str):
                continue
            words = alternative.lower().split()
            if len(words) != len(wanted):
                continue
            if all(_forms(word) & want for word, want in zip(words, wanted)):
                return True
    return False


# --- a line that is only the name of a thing --------------------------------------------------
# "nappy rash", "cradle cap", "heat rash": a person naming what is wrong, with no verb and no
# ask, is asking about it. The card keyed on the name was never reached, because a key wants a
# second signal as well as the subject - so bare "nappy rash" got the health visitor line. A name
# on its own is the whole ask, and only a card whose subject group the line spells out exactly
# will do: nothing is guessed from one word of a two-word name.
NAME_ALONE_DOMAINS = frozenset('''family health body babyfood pregnancy'''.split())
# The words that make a line more than a name: a question, a pointing back, or the speaker in it
# ("i think nappy rash" is a sentence).
NOT_A_NAME_ALONE = frozenset('''what why how when where which who whom whose is are was were
    am do does did can could should would will shall may might i im ive id you your u my mine
    me we our us it its that this these those there they them he she him her his hers the a an
    and or but if so then than about for with on in at to of from not no yes ok okay thanks
    please help huh'''.split())
# A name is a thing. The phrase a person types when they drop themselves out of the sentence is
# not: "gone numb", "went numb", "feel numb" and "burning up" are things said about a body, and a
# bare "gone numb" answered with the cauda-equina warning told somebody to ring 999 about a foot
# that had gone to sleep. A state verb in the phrase means the line is a report, not a name.
# A word a name does not end in: "school closed" and "back open" are clauses about a thing, and
# the card that lists the clause is answering the clause.
A_STATE_AS_A_NAME_END = frozenset('''closed shut blocked swollen broken numb off blocked'''.split())
A_STATE_IN_THE_PHRASE = frozenset('''feel feels feeling felt gone went go goes going get gets
    getting got gotten been being be keep keeps keeping kept start starts started starting
    burn burns burning'''.split())


def _said_as_a_report(understood, words, entries, reject=None):
    """The entry the same name gets inside a sentence, when the line is only a name, or None.

    A card is written for a thing being raised ("i have a nappy rash", "ive got an ear
    infection"), so the bare words of the name reach several cards at once and the nearest one
    is not the one the knowledge base would answer the same person with. Read the name as the
    report it is and let the ordinary search pick: the bare "head ache" opened the migraine
    card, while "i have a head ache" gets the ordinary-headache card, which every longer line
    about a headache already gets.
    """
    if not isinstance(understood, dict):
        return None
    said = "i have a " + " ".join(str(word) for word in words)
    second = dict(understood)
    second["clean"] = said
    second["words"] = ["i", "have", "a"] + [str(word) for word in words]
    # The reading of the bare name is the reading of a remark: what it pointed at, where it
    # happened and what it leaned on are not part of the name, and a search that uses them
    # answers a line nobody typed.
    for key in ("background", "intensifier", "intensifier_left", "leans_on", "topic_own",
                "past", "handoff"):
        second.pop(key, None)
    # The report is not a line the person typed, so it gets no second look at the context and no
    # name-alone reading of its own - which is also what stops this from recurring.
    return _the_best_entry(second, entries, reject, False)


def _the_name_card(typed, entries, reject=None, allowed=None):
    """The entry that is *named* the line, or None.

    The entry's own name is the first alternative of the first part of its key, and only that
    counts: a card lists many ways of saying its subject, and most of them are meant to be
    reached with a second signal, not on their own. "ear infection" and "head ache" are
    alternatives of the swimmer's-ear and migraine cards, and those cards are the right answer
    to a sentence that says the rest; opened on the name alone they answered a question nobody
    asked. The card called "nappy rash" is the card for nappy rash.

    A one-word name is not enough either: "money", "sofa" and "boiler" are the objects of a
    conversation as often as they are a subject to open, and a person answering the bot own
    question meant the pizza, not the pizza card.
    """
    said = set(typed)
    found = []
    for item in entries:
        if getattr(item, "domain", None) not in NAME_ALONE_DOMAINS:
            continue
        if reject is not None and reject(item):
            continue
        if allowed is not None and getattr(item, "domain", None) not in allowed:
            continue
        key = getattr(item, "key", ()) or ()
        if not key:
            continue
        part = key[0]
        alternatives = part if isinstance(part, tuple) else (part,)
        if not alternatives or not isinstance(alternatives[0], str):
            continue
        phrase = set(alternatives[0].lower().split())
        if len(phrase) >= 2 and phrase == said:
            found.append(item)
    if not found:
        return None
    if len(found) == 1:
        return found[0]
    # Two cards can carry the same name, and one of them is usually about the name while the
    # other reaches it: the ear-infection card answers ear infections, and the swimmer's-ear
    # card lists the name among its ways of saying a wet ear after swimming. The card whose own
    # reply opens with its own name is the one that answers the name.
    def _names_itself(item):
        name = (item.key[0][0] if item.key else "")
        reply = (getattr(item, "reply", "") or "").lower()[:140]
        return 0 if isinstance(name, str) and name.lower() in reply else 1
    return min(found, key=_names_itself)


def _the_name_alone(named, entries, reject, allowed=None, understood=None, words=None,
                    use_context=False):
    """The card a line that is only the name of a thing gets, or None.

    `named` is that name's own card - the one whose own name the line spells out. The checks
    here are the ones a name has to pass before it is a name and not a sentence, and they are
    the reading's own: a state in the phrase ("gone numb"), a clause ending ("school closed"),
    a name that is one word, and a card from an area the line is not read as being about.
    """
    typed = [str(word).lower() for word in (words or ())]
    if not 2 <= len(typed) <= 4:
        return None
    if any(word in NOT_A_NAME_ALONE for word in typed):
        return None
    # "gone numb" and "feel numb" are about a body, said with the person dropped: a report, not
    # a name. A card keyed on the words of a report is a card about the words, not the thing.
    if any(word in A_STATE_IN_THE_PHRASE for word in typed):
        return None
    # A name ends in the thing. "school closed" ends in what the thing is doing, and a card that
    # lists that clause answers a question about the closed school, not about a thing named.
    if typed[-1] in A_STATE_AS_A_NAME_END:
        return None
    if named is None:
        return None
    # The name has to be the area the line is already read as being about: "nappy rash" is a
    # health line and its card is a health card, while "late again" is about nothing in
    # particular and its bare words are a remark, which small talk answers better than any
    # card. Only when the reading names a topic at all - no topic, no opinion, no pass.
    if not allowed:
        return None
    if understood is not None:
        allowed = _declared_for(allowed, understood)
    if getattr(named, "domain", None) not in allowed:
        return None
    said = set(typed)
    if len(said) != len(typed):
        return None
    return named


def _declared_for(allowed, understood):
    """The domains in `allowed` that declare one of the topics the line is about.

    `_topic_domains` keeps a domain that declares nothing, because for a search a domain with no
    opinion should not be ruled out. A card answering a bare name is a stronger claim than that,
    so the domain has to say the topic is its own.
    """
    from . import by_topic
    judged = by_topic()
    topics = []
    if isinstance(understood, dict):
        found = understood.get("topics")
        topics = list(found) if isinstance(found, (list, tuple)) else []
        topics.append(understood.get("topic"))
    topics = [topic for topic in topics if isinstance(topic, str) and topic]
    if not topics:
        return set()
    return {name for name in allowed
            if any(topic in (judged.get(name) or ()) for topic in topics)}


def _defines(understood, forms, typed, entries, reject=None):
    """The best entry that defines the thing a definition line asks about, or None.

    Read only when every other reader gave up, so a line with an answer of its own is untouched.
    The entry has to name the thing in its key and in the first sentence of its reply, and its
    fences still hold: a "what is a wet room" line that also says the room smells is a damp
    question and keeps the damp row.
    """
    clean = understood.get("clean") if isinstance(understood, dict) else ""
    said = clean or (understood.get("text") if isinstance(understood, dict) else "") or ""
    thing = _the_thing_asked_about(said)
    if not thing:
        return None
    purpose = _asks_what_it_is_for(said)
    best = None
    best_rank = None
    for item in entries:
        if reject is not None and reject(item):
            continue
        # A guard is a test of the whole reading of the line, so it holds here too: "what is a
        # bridge" is a river crossing as often as a section of a song, and the entry that says
        # which sense it is about was being asked below anyway. A definition line names one
        # thing and asks nothing else, so it is the one reader with no second signal to lean on.
        guard = getattr(item, "guard", None)
        if guard is not None and not guard(understood):
            continue
        if not _the_key_names_the_thing(item, thing):
            continue
        if not _the_reply_defines(getattr(item, "reply", ""), thing, purpose):
            continue
        if any(_part_score(word, forms) for word in item.avoid):
            continue
        rank = -len(_key_forms(item))
        if best_rank is None or rank > best_rank:
            best, best_rank = item, rank
    return best


def _named_things(understood):
    """The names the line gives, which a question is about before it is about its ask words."""
    found = []
    entities = understood.get("entities") if isinstance(understood, dict) else None
    for entity in entities if isinstance(entities, list) else ():
        if not isinstance(entity, dict) or entity.get("type") not in ("place", "name", "title"):
            continue
        name = " ".join(str(entity.get("text") or "").lower().split())
        if len(name) > 2:
            found.append(name)
    return found


PLAN_WORDS = ("plan", "plans", "planning", "organise", "organize", "prepare", "preparing")


def _plans_it(item, forms):
    """True when the line asks to plan something and the entry's key is the planning word.

    "help me plan a trip to Paris" and "i want to plan a weekend in Amsterdam" name a place,
    but the question is the plan, not the place: the city guide names Paris or Amsterdam and
    would take the line on the named-thing tie-break. A key that itself says "plan" is the
    answer to a line that says plan, so it comes before the name.
    """
    if not any(_part_score(word, forms) for word in PLAN_WORDS):
        return False
    return any(word in _key_words(item) for word in PLAN_WORDS)


def _names_one(item, named):
    """True when the entry's own key names one of the things the line names."""
    for part in getattr(item, "key", ()) or ():
        for alternative in (part if isinstance(part, tuple) else (part,)):
            text = " ".join(str(alternative).lower().split())
            for name in named:
                if _bounded(str(name)).search(text):
                    return True
    return False

# The words that point back at the thing already said: a line carrying one of these is about
# that thing whatever else it says ("its 3 years old" after a cat).
POINTS_BACK = frozenset("""it its it's that this these those there them they he she him her""".split())


def leans_on_a_subject(understood):
    """True when the line leans on the subject before it, rather than saying something itself.

    A question left out its subject on purpose ("how long in the oven?"), and a line that
    points back at the thing ("is that bad", "its 3 years old") is about it. A statement that
    names its own subject is not: "i have a cat" then "i work nights" was answered with the
    cats-at-night entry, because the carried subject was searched together with the line's own
    words - "cat" plus "nights" reached an entry neither of them was about, and the person had
    only said what their job was. Nothing else about the night shift was ever said, so the reply
    answered a subject they had not raised.
    """
    if str(understood.get("kind") or "") == "question":
        return True
    if _says_how_the_speaker_handles_it(understood):
        return True
    # Read from the line as typed: the reading's own words have the pronouns taken out, and "i
    # feed it twice a day" after a sourdough is about the sourdough because of the "it".
    line = tokens(str(understood.get("clean") or understood.get("text") or ""))
    return any(word in POINTS_BACK for word in line)


# One reading of one line is scored once, however many times a turn asks about it. The answers
# module asks `find` for the line, then for the same line with one card family after another
# ruled out (`reject`), and each of those asked and answered every entry again: a fallback line
# on the whole 4,300-entry knowledge base walked it eight to thirty times, which was most of
# what a reply cost. What an entry scores depends on the line's words and on nothing else, so
# the answer is the same each time. The key is the reading itself, and the entries list is kept
# with it so a freed list's id cannot be reused for a different knowledge base.
_ROWS_CACHE = {}
_ROWS_KEEP = 40


# A word of the question half that more than this many entries key on is the vocabulary of
# everyday asking - "get" 949, "best" 587, "work" 566, "time" 523, "child" 211, "thing" 58 - and
# not the thing a person asked about. Below it the base treats the word as one name for one
# subject ("railcard" 4, "condensation" 10), and an entry that keys on it is answering what the
# line asked rather than what the line mentioned on the way there.
ASK_NAME_CAP = 40


def _the_names_in_the_ask(understood, every):
    """The words of the question half that the knowledge base treats as a name for something.

    People put the situation first and the question last: "i start a new job monday and the
    commute is an hour, should i get a railcard". The situation half is thick with subject words
    and the question half is thin, so the card for the commute (a house move, a season ticket)
    outscored the card for the railcard that was actually being decided. Nothing in the scan
    knew which half a matched word came from.

    `focus` is the question half, which the reading already hands over. Only the content words
    of it count, and only the ones a card keys on as a name: the ask's own words ("what",
    "should", "get") are the vocabulary of asking and every card in the base keys on some of
    them, so counting those would put the whole base on the ask.

    Only a line split into a situation and a question of its own is read this way (see
    `_two_clauses`); a line that states one thing and asks nothing keeps the reading it had.
    """
    split = _two_clauses(understood)
    if not split:
        return ()
    focus = split
    names = []
    for word in focus:
        if not isinstance(word, str):
            continue
        low = word.lower()
        if len(low) < 3 or low in _NOT_A_SUBJECT or low in ASK_FRAME_WORDS:
            continue
        if every.get(low, 0) > ASK_NAME_CAP or low in names:
            continue
        names.append(low)
    return tuple(names)


def _the_ask_in_order(understood):
    """The words of the question half, in the order the person said them, or ().

    The names `_the_names_in_the_ask` hands back are single words, and a card that keys a phrase
    of two words is not reached by one of them alone: "how do i get more vitamin c" offered
    "vitamin" and the expired-medicines row, which keys on "vitamins", took the line off the row
    that keys on "vitamin c". Read as the words in order, the phrase a card keys on can be found
    for what it is (see `_the_longest_run`).
    """
    said = _two_clauses(understood)
    if not said:
        return ()
    return tuple(word for word in said if isinstance(word, str))


# The words every card in the base may key on because they are how a line asks rather than what
# it asks about. A short list on purpose: the frequency cap above already keeps most of them out.
ASK_FRAME_WORDS = frozenset("""
    what when where which who why how should could would can will shall may might must
    is are was were be been being am do does did done doing have has had having
    get gets got getting need needs want wants like likes make makes made take takes
    go goes going put give gives tell say says know think use uses try tries
    good best better bad worse right wrong sure possible worth
    """.split())


def _two_clauses(understood):
    """(the words of the question half, the loose forms said before it), or None.

    Only a line that puts the situation first and asks after it is read this way: the ask has to
    be there at all (`asks`), and it has to be a clause of its own, so that the words beside it
    are the situation and not the same sentence. A line that states one thing and asks nothing
    ("my nose wont stop running and i keep sneezing") has no question half to prefer, and reading
    its whole line as one put the training-injury card - which keys on "running" - in front of
    the runny nose.

    Compared as loose forms, so "stop" and "stopped" are the same word here. A word of the ask
    that the line says only earlier on means the reading is not split, and the rule stands down.
    """
    if not isinstance(understood, dict) or not understood.get("asks"):
        return None
    focus = understood.get("focus")
    clauses = [clause for clause in (understood.get("clauses") or ())
               if isinstance(clause, (list, tuple)) and clause != ["text"]]
    if not isinstance(focus, (list, tuple)) or not focus or len(clauses) < 2:
        return None
    last = {_forms(str(word)) for word in (clauses[-1] or ()) if isinstance(word, str)}
    earlier = {_forms(str(word)) for clause in clauses[:-1] for word in (clause or ())
               if isinstance(word, str)}
    # The situation has to be a clause somebody would write: "how long do i defrost a chicken
    # for" splits into "how long" and the rest, and the reading is one question, not a
    # situation and a question. Three words of situation is the least that says anything.
    longest = max((len([word for word in (clause or ()) if isinstance(word, str)])
                   for clause in clauses[:-1]), default=0)
    if not last or not earlier or longest < 4:
        return None
    for word in focus:
        if not isinstance(word, str):
            continue
        form = _forms(word)
        if form in last or form not in earlier:
            continue
        return None
    return tuple(word for word in focus if isinstance(word, str))


def _rows_key(forms, typed, named, frame, framed=False, asked=(), ask_said=()):
    """The reading of the line a scan answers, or None when it cannot be written down."""
    try:
        return (tuple(tuple(sorted(str(form) for form in group)) for group in forms),
                tuple(str(word) for word in typed or ()),
                tuple(str(one) for one in named or ()), bool(frame), bool(framed),
                tuple(str(word) for word in asked or ()),
                tuple(str(word) for word in ask_said or ()))
    except TypeError:  # a reading a test built by hand: no memo, just scan
        return None


def _line_rows(forms, typed, entries, by_domain, every, named=(), frame=True,
               stands_down=None, framed=False, ask_names=(), ask_said=()):
    """[(asked, rank, plans it, names the thing named, key parts, entry, on the ask)] reached.

    `stands_down` is a test of the whole reading, not of the entry's own key words, so the entry
    it passes over is left out of what this call returns and not out of what the line reaches:
    the scan is kept as it is and the rows are filtered on the way out.

    framed: the line is the subject inside an advice ask, which spends its other words on the
    asking (see `score`). It changes what an entry scores, so it is part of the memo key.

    ask_names: the names the question half holds (see `_the_names_in_the_ask`). They are a
    column of the row, so they are part of the memo key too.

    ask_said: the question half's words in the order they were said, which is how a card that
    keys a phrase of two of them is reached (see `_the_longest_run`). Also part of the key.
    """
    key = _rows_key(forms, typed, named, frame, framed, ask_names, ask_said)
    ranked_items = None
    if key is not None:
        got = _ROWS_CACHE.get((id(entries), key))
        if got is not None and got[0] is entries:
            ranked_items = got[1]
    if ranked_items is None:
        ranked_items = _scanned_rows(forms, typed, entries, by_domain, every, named, frame,
                                     framed, ask_names, ask_said)
        if key is not None:
            if len(_ROWS_CACHE) >= _ROWS_KEEP:
                _ROWS_CACHE.pop(next(iter(_ROWS_CACHE)))
            _ROWS_CACHE[(id(entries), key)] = (entries, ranked_items)
    if stands_down is None:
        return list(ranked_items)
    return [row for row in ranked_items if not stands_down(row[5])]


def _scanned_rows(forms, typed, entries, by_domain, every, named, frame, framed=False,
                  ask_names=(), ask_said=()):
    """Every entry the line reaches, scored: the work one reading of one line costs."""
    ranked_items = []
    ask_forms = [_forms(word) for word in ask_names]
    # The question half as the person said it, in order, so a card that keys a phrase of two
    # words can be reached by the phrase rather than by one of them (see `_the_longest_run`).
    ask_line = [_forms(word) for word in ask_said]
    # The memo is keyed by id(part), so it is only safe for parts that live on a module-level
    # entry: a part built inside a call could be freed and its id reused within the same line.
    seen = {}
    # A second memo for the question half alone, because a memo says what one part matched in one
    # reading of the line and `seen` is about the whole line.
    asked_seen = {}
    for item in _reaching(entries, forms):
        value = score(item, forms, typed, seen, frame, framed)
        if not value:
            continue
        domain = getattr(item, "domain", "") or ""
        ranked = _rank(item, forms, by_domain.get(domain) or every, seen)
        # an entry the line actually asked reaches ahead of one the want rule let in
        asked = 0 if _only_the_want(item, forms, seen) else 1
        # ...and one that answers the question half reaches ahead of one that answers the
        # situation half. A separate column on purpose: the score of the wrong card is usually
        # higher, because its half of the line is the wordy half, so a bonus inside the score
        # would have to be bigger than any score difference we can justify.
        run = _the_longest_run(item, ask_line, ask_forms, asked_seen)
        ranked_items.append((asked, ranked, _plans_it(item, forms),
                             _names_one(item, named), len(item.key), item, run))
    # The question half is about the card that accounts for the most of it. Crediting every card
    # that answers one of its words put the expired-medicines row - which keys on "vitamins" -
    # ahead of the row that keys on the phrase "vitamin c" for "how do i get more vitamin c",
    # because one loose word of the ask beat a card that answers two of them.
    longest = max((row[6] for row in ranked_items), default=0)
    if longest:
        ranked_items = [row[:6] + (1 if row[6] == longest else 0,) for row in ranked_items]
    return ranked_items


def _the_longest_run(item, ask_line, name_forms, asked_seen):
    """How many words of the question half one key part of this entry accounts for, or 0.

    A name of the question half has to be in what matched: the ask's own words ("what", "get",
    "should") are the vocabulary of asking and a card that keys one of them is not on the ask.
    Past that, the length of the run is the whole reading, because a card that keys a phrase of
    two words of the ask is more about it than one that keys a single word of it.

    The memo of matches is the caller's and holds no entry yet: `seen` in the scan is keyed by
    id(part) alone, so reusing it would hand back the matches found in the whole line, which is
    every part that reached the line at all.
    """
    wanted = set()
    for forms in name_forms:
        wanted |= forms
    best = 0
    for part in item.key or ():
        for weight, words, span in _part_matches(part, ask_line, asked_seen):
            if not weight or len(span) <= best:
                continue
            if not any(_forms(str(word)) & wanted for word in words):
                continue
            best = len(span)
    return best


def _row_order(row):
    """The order two entries compete in: asked, on the ask, score, plan, the named thing, parts."""
    return (row[0], row[6], row[1], row[2], row[3], row[4])


PLAIN_MARGIN = 3


def _plainer(plain, framed, margin=PLAIN_MARGIN):
    """True when the whole line reaches a clearly better entry than the line without its clause.

    A margin, not a straight comparison: reading the left-out thing as the subject beats the
    rest of the line by one rank point in plenty of lines where it is wrong ("how do i stop my
    baby crying without picking him up" reaches the skin-picking entry that way), and the entry
    that wins here has to win by more than that to be believed.
    """
    better = max(row[:2] for row in plain)
    other = max(row[:2] for row in framed)
    return better[0] > other[0] or better[1] >= other[1] + margin


# The words an entry's key uses when the entry is there to name what can go in place of something
# else. A line that leaves an ingredient out ("can i make pesto without pine nuts") wants that
# entry, not the entry that answers the dish with the ingredient still in it.
SUBSTITUTE_WORDS = frozenset(("substitute", "substitutes", "substitution", "instead", "swap",
                              "alternative", "alternatives", "replace", "replacement"))


def _the_subjects_own_row(forms, item, rows):
    """True when the whole line's fault row is the answer, not a card about a different question.

    The whole line beats the line with its "without" clause emptied by one rank point on plenty
    of lines where reading the clause as the subject is wrong, which is what the margin in
    `_plainer` is for. A clause that names a fault of the thing in hand is the question, so the
    whole line may win by that one point, but only where the rest of the line has no answer of
    its own. Two things have to hold.

    The row the whole line reaches is in the same domain as a row the rest of the line reaches:
    a clause that buys a row from another domain has changed the subject, not answered the line
    ("how do i say sorry without it sounding fake" is an apology, not a phishing warning).

    And the row the rest of the line reaches is a stand-in list rather than an answer: an entry
    whose key is what to use instead of something is not the how-to the person asked for, so the
    fault card beside it is better. "how do i fry eggs without them sticking" reached the egg
    swap ("one egg becomes 60g of yoghurt") and wanted the pan.

        how do i fry eggs without them sticking   -> egg swap (a stand-in list) / fix-sticking
        how do i cook salmon without it sticking  -> the salmon method: the answer, not a card
        how do i paint a door without it dripping -> the door how-to: not a ceiling stain card
        how do i iron a shirt without it shining  -> the shirt how-to, not the scorch card

    Measured on the deck's "without it" lines: the salmon, door, shirt and puppy lines keep the
    how-to they had, and the egg line gets the pan.
    """
    domain = getattr(item, "domain", None)
    if not domain or not _a_clause_about_the_thing(forms):
        return False
    if not any(getattr(row[5], "domain", None) == domain for row in rows):
        return False
    return _offers_a_substitute(max(rows, key=_row_order)[5])


def _offers_a_substitute(item):
    """True when this entry exists to say what can stand in for something else."""
    for part in item.key:
        for alternative in (part if isinstance(part, tuple) else (part,)):
            if isinstance(alternative, str) and set(alternative.lower().split()) & SUBSTITUTE_WORDS:
                return True
    return False


# The words a "back" says nothing about the body after: the thing came back, or somebody went
# back to something. "my knee pain is back again" is the knee, "my hip pain is back" is the hip,
# and "I'm going back to study at 38" is a course - but each of them reached the back entry and
# answered "Most back pain is muscular and settles in two to six weeks", a part the person never
# named. A verb in front is what tells the two apart: the back that is a part has no verb there
# ("my back", "lower back pain"), while every return and every going back is "<verb> back".
RETURNED_AFTER = frozenset("""
    is are was were be been am
    im i'm youre you're hes he's shes she's theyre they're were we're
    come comes came coming
    go goes going went gone
    get gets getting got gotten
    walk walks walking walked
    drive drives driving drove driven
    fly flies flying flew flown
    run runs running ran
    head heads heading headed
    move moves moving moved
    travel travels travelling traveled
    carry carries carrying carried
    bring brings bringing brought
    take takes taking took taken
    send sends sending sent
    call calls calling called
    write writes writing wrote written
    put puts putting
    hand hands handing handed
    pay pays paying paid
    give gives giving gave given
    kick kicks kicking kicked
    sit sits sitting sat
    lie lies lying lay lain
    step steps stepping stepped
    look looks looking looked
    turn turns turning turned
    think thinks thinking thought
    bounce bounces bouncing bounced
""".split())
# The parts a line can name and an entry can be keyed on, as both are written: the entry keys
# use the singular and the plural of the same word, and a line may say either.
BODY_WORDS = lexicon.BODY_PARTS
# Parts that are everywhere: a rash on the knee is still the skin entry, and a keyed "skin" is
# not a different part from the one the line names.
GENERAL_BODY = frozenset(("skin", "muscle", "muscles"))
# How many parts an entry's key can name and still be about one of them: "knee" and "kneecap"
# is the same joint twice, while a key listing the arm, the leg and the chest is a key for
# anywhere.
SPECIFIC_PARTS = 2
# A part that sits inside another is not a different part: new trainers rubbing the heel are
# still the entry about feet, so a keyed "foot" keeps the line that says "heel". The other
# way round is not the same thing - "my leg hurts" is not the knee - and nothing here makes the
# neck a back or the back a neck, which is what the guard is for.
PART_INSIDE = {
    "heel": "foot", "ankle": "leg", "knee": "leg", "hip": "leg",
    "thumb": "hand", "finger": "hand", "knuckle": "hand",
    "wrist": "hand", "elbow": "arm", "shoulder": "arm",
    "jaw": "head", "tooth": "head", "ear": "head", "eye": "head",
    "rib": "chest", "belly": "stomach",
}


def _inside(part, other):
    """True when this part is the other one, or a part of it."""
    seen = 0
    while part and seen < 4:
        if _forms(part) & _forms(other):
            return True
        part = PART_INSIDE.get(part, "")
        seen += 1
    return False


def _body_parts(words):
    """The body parts the line names, without a "back" that only says the thing returned."""
    parts = set()
    for index, word in enumerate(words or ()):
        word = str(word).lower()
        if word not in BODY_WORDS:
            continue
        if word == "back" and index and str(words[index - 1]).lower() in RETURNED_AFTER:
            continue
        if word in GENERAL_BODY:
            continue
        parts.add(word)
    return parts


def _key_body_parts(item):
    """The body parts this entry's key is written on.

    Read with the same eye as the line: a key that says "keeps coming back" names no part, and
    the entry that answers a rash which returns is still the answer to ``the rash on my knee
    keeps coming back``.
    """
    parts = set()
    for part in getattr(item, "key", ()) or ():
        for alternative in (part if isinstance(part, tuple) else (part,)):
            if isinstance(alternative, str):
                parts |= _body_parts(alternative.lower().split())
    return parts


def _another_part(item, line_parts):
    """True when the entry is keyed on a body part the line does not have.

    A line that names one part is about that part: an entry keyed on a different one answers a
    question nobody asked, however well its other words fit ("pain" is in most of them). Only
    entries whose key names a part are held to it, so a row about a return ("keeps coming
    back") or a place is untouched, and a line that names no part at all is untouched too - the
    filter narrows what a body word may reach, and never widens it.

    A key that names many parts is not about one of them: `rash` lists the arm, the leg, the
    chest and the back because a rash can be on any of them, and holding it to those words took
    "the rash on my knee keeps coming back" off its own answer. Only a key written on one part,
    or a part and its other name (`sore-knee` is "knee" and "kneecap"), says what the entry is
    about. The words are compared by their loose forms, because the line says "my knees ache"
    and the key says "knee".
    """
    if not line_parts:
        return False
    parts = _key_body_parts(item)
    if not parts or len(parts) > SPECIFIC_PARTS:
        return False
    said = list(line_parts)
    # the line's part may be a part of the entry's: a heel is a foot, a thumb is a hand
    return not any(_inside(other, part) for part in parts for other in said)


# A thing that has already been kept somewhere and a question about whether it is still good is
# one question, and it is a keeping question: "is it ok to eat rice thats been in the fridge 3
# days", "can i eat leftover rice after 3 days", "cooked pasta in the fridge 5 days ok". The
# reading says so (`understood["kept"]`: the place it sat in and how long), and the rows that
# answer something else read one of the same words as their own - the fried-rice recipe takes
# "leftover rice", the warm-pot row takes "rice" and "in the fridge", the date-on-the-bag row
# takes "rice" and "ok to eat", and the chicken-nutrition row takes "chicken" and "eat". On main
# each of them answered that question. So when the line says a thing has been kept a while and
# asks if it is still good, only the rows that answer keeping are left to answer it.
_STILL_GOOD_ASHERS = frozenset((
    "ok", "okay", "safe", "eat", "eats", "eating", "drink", "use", "still", "good", "gone",
    "off", "bin", "throw", "edible", "risky"))
# The words a keeping row is keyed on. A row whose key holds one of them answers how long a thing
# lasts, what to do with it once it has lasted, or whether it is still fit to eat.
# What a keeping answer says, in the row's own words. A key word will not do: `babyfood-cheese` is
# keyed partly on keeping ("how long can i keep cheese for a baby") and answered a grown-up's
# "can i eat cheese thats been in the fridge for a month" with a weaning verdict the moment the
# appliance row stood down. The answer itself is the surest sign of the question it answers - it
# says how long the thing keeps, where to keep it, or to bin it - so that is what is read.
# The words a keeping row that builds its reply is keyed on.
_KEEPING_WORDS = frozenset((
    "keep", "keeps", "kept", "keeping", "last", "lasts", "store", "stored", "storage", "freeze",
    "frozen", "reheat", "reheated", "mouldy", "sour", "slimy", "stale", "gone", "date", "bin",
    "throw", "overnight", "left"))

_KEEPING_ANSWER = (
    " keeps ", " keep it ", " keep them ", " keeping it ", " in the fridge", " in the freezer",
    " in a sealed", " in an airtight", "bin it", "bin them", "throw it", "throw them",
    "no more than", "shelf life", "hours", "days in the", "a day in the", "day in the fridge",
    "within a day", "within the hour", "goes off", "gone off", "until the date", "use-by",
    "use by", "best before", "cold box", "cool it", "cool it fast")


def _asks_if_it_is_still_good(typed):
    """True when the line asks whether a thing is still fit to eat, drink or use."""
    if not typed:
        return False
    return bool(_STILL_GOOD_ASHERS.intersection(str(word).lower() for word in typed))


def _a_keeping_row(item):
    """True when the entry answers how long a thing keeps, where to keep it, or if it is fit."""
    reply = getattr(item, "reply", "") or ""
    if not isinstance(reply, str):
        # a reply built at the turn ("a bowl of X is ...") says what it says in `key`, and the
        # rows that keep are the ones keyed on a keeping word.
        return _a_keeping_key(item)
    if not reply:
        return False
    reply = " " + " ".join(reply.lower().split()) + " "
    return any(phrase in reply for phrase in _KEEPING_ANSWER)


def _a_keeping_key(item):
    """The key-word test, used only for a row whose reply is built at the turn."""
    words = set()

    def collect(part):
        if isinstance(part, str):
            words.update(part.lower().split())
        elif isinstance(part, (tuple, list, frozenset, set)):
            for inner in part:
                collect(inner)

    collect(getattr(item, "key", ()) or ())
    return bool(_KEEPING_WORDS.intersection(words))


# A word can name a colour and a thing at once - "orange" a fruit, "green" a vegetable, "brown" a
# way of cooking, "plum" a fruit - and an entry keyed on the thing is reachable from a line that
# only used the colour. "the sky was orange last night" was answered with the citrus keeping card,
# "Keep them a week or two in the bowl and a month in the fridge", because "orange" was the whole
# of what the line and that entry had in common. A shared word is not a subject, so a colour the
# line used as a colour is not one of the line's subject words.
COLOUR_WORDS = frozenset("""red orange yellow green blue indigo violet purple pink brown black white
    grey gray beige cream tan navy gold golden silver amber turquoise lilac mauve crimson scarlet
    burgundy maroon olive khaki teal cyan magenta peach coral rust blonde fair plum cherry lemon
    lime salmon rose chestnut copper ochre ebony ivory pearl""".split())
# A colour used as a colour is one a copula or a verb of changing puts in front of you: "the sky
# was orange", "the leaves have gone brown", "it turned green". In front of a noun the colour is
# part of that thing's name and the thing is what the line is about - "green beans for dinner" is
# the beans, "orange juice" is the juice - so only this shape is read as a colour word.
A_COLOUR_USED = re.compile(
    r"\b(?:is|are|was|were|am|be|been|being|looks?|looked|seems?|seemed|got|gets|getting|goes|"
    r"going|went|gone|turn(?:s|ed|ing)?|becom(?:e|es|ing)|became|keep|keeps|kept|painted|paint|"
    r"dyed|dye|stained?)\s+(?:very\s+|really\s+|so\s+|too\s+|quite\s+|a bit\s+|a little\s+|"
    r"all\s+|still\s+|now\s+)?(?P<colour>[a-z]+)\b", re.IGNORECASE)


def _the_words_without_a_colour(clean, words):
    """The line's words with a colour it used as a colour taken out, or None when it used none."""
    said = {match.group("colour").lower() for match in A_COLOUR_USED.finditer(str(clean or ""))}
    said &= COLOUR_WORDS
    if not said:
        return None
    kept = [word for word in words if str(word).lower() not in said]
    if not kept or len(kept) == len(words):
        return None
    return kept


# The words that name nothing, so the check below looks for the line's own subject in an entry's
# key rather than for a word every key holds ("the", "a", "was" are in half the keys in the base).
_BARE_IN_A_KEY = frozenset("""a an the and or but if then than that this these those there here i
    me my mine we us our you your yours he him his she her hers it its they them their is are was
    were am be been being do does did done have has had got get gets getting go goes went gone
    going make makes made just so not no yes very really quite too much many more most some any
    all one two three last next night morning today tonight tomorrow now still also about of to in
    on at for with from by as up down out off over again ever never always thing things bit lot
    kind sort what when where which who how why""".split())


def _the_key_words(entry):
    """Every word an entry is keyed on, flattened, so a line word can be looked for in it."""
    said = set()
    for part in (getattr(entry, "key", ()) or ()):
        if isinstance(part, str):
            said.update(part.lower().split())
        else:
            for one in part:
                said.update(str(one).lower().split())
    return said


def _the_answer_the_colour_dragged_in(found, understood, words, clean, entries, by_domain, every,
                                      reject):
    """The entry the line reaches once a colour it used as a colour is left out, else `found`.

    A colour word is not one of the line's subject words, so the answer that needs it is an answer
    about something else: the line is read once more without it, and that entry answers the line
    when it reaches one. Only an entry that has nothing else of the line in it is given up - an
    entry keyed on the colour and on another word the line says is about that word ("the leaves
    have gone brown" is the leaves entry, keyed on both) - and when the second read reaches
    nothing the line keeps the answer it had, so a colour the knowledge base does answer is not
    taken away from a person who asked about it.
    """
    kept = _the_words_without_a_colour(clean, words)
    if kept is None or found is None:
        return found
    others = {str(word).lower() for word in kept} - _BARE_IN_A_KEY
    if others & _the_key_words(found):
        return found
    again = _best(understood, kept, " ".join(str(word) for word in kept),
                  [_forms(word) for word in kept],
                  [word.lower() for word in kept if isinstance(word, str)],
                  entries, by_domain, every, reject)
    return again if again is not None else found


def _best(understood, words, clean, forms, typed, entries, by_domain, every, reject=None,
          framed=False):
    """The highest-ranked entry the line as typed reaches, or the one another reading reaches.

    framed: the line is the subject inside an advice ask, which spends its other words on the
    asking. Only the entries in ASK_FRAME_IDS read it that way (see `score`).
    """
    # An entry can say a test of the whole reading, not only of its key words: "the table leg is
    # cracked" reaches the dry-skin row on its words, but the part belongs to the table. The
    # guard is asked on the entries the line actually reaches, not on a copy of the whole
    # registry: `_word_index` caches by the list's identity, so a fresh list would rebuild the
    # index on every turn - most of a turn's time - for a filter that only ever excludes a few.
    line_parts = _body_parts(words)

    # A line that says a thing has already been kept a while and asks if it is still good is a
    # keeping question, whatever else its words reach (see _STILL_GOOD_ASHERS).
    kept = understood.get("kept")
    keeping_question = bool(kept) and _asks_if_it_is_still_good(typed)

    # The names the question half holds: what the person was actually asking about, as opposed to
    # the situation they described first (see `_the_names_in_the_ask`).
    ask_names = _the_names_in_the_ask(understood, every)
    ask_said = _the_ask_in_order(understood)

    def rank(reading, filter_keeping):
        """The entries the line reaches, with the keeping-only rule on or off."""

        def stands_down(item):
            guard = getattr(item, "guard", None)
            if guard is not None and not guard(reading):
                return True
            if filter_keeping and not _a_keeping_row(item):
                return True
            return _another_part(item, line_parts)

        named = _named_things(reading)
        reached = _line_rows(forms, typed, entries, by_domain, every, named,
                             stands_down=stands_down, framed=framed, ask_names=ask_names,
                             ask_said=ask_said)
        plain_rows = None
        if _frame_masked(forms)[1]:
            # The line has a "without" clause and two entries want it: the one that answers what
            # is asked and the one that answers the thing left out. Keep both readings: the line
            # with the clause emptied is the answer unless the whole line reaches a clearly
            # better entry ("a main for everyone without doing two dinners" is a dinner you cook
            # once, which only the whole line reaches) or a swap entry ("can i make pesto without
            # pine nuts" is the pine-nut swap, not the recipe that uses them).
            plain_rows = _line_rows(forms, typed, entries, by_domain, every, named, frame=False,
                                    stands_down=stands_down, framed=framed, ask_names=ask_names,
                                    ask_said=ask_said)
            if plain_rows:
                plain_rows.sort(key=_row_order, reverse=True)
                if (not reached or _plainer(plain_rows, reached)
                        or _offers_a_substitute(plain_rows[0][5])
                        or _the_subjects_own_row(forms, plain_rows[0][5], reached)):
                    reached = plain_rows
        return reached, plain_rows

    ranked_items, plain = rank(understood, keeping_question)
    if not ranked_items and keeping_question:
        # Nothing that answers keeping reached the line, so the keeping rule has nothing better
        # to offer and the line keeps the answer it had. The rule narrows the field; when the
        # field is empty it is put back, or a food question with no keeping row would be left
        # with no answer at all (or, worse, whatever the next module makes of it).
        ranked_items, plain = rank({k: v for k, v in understood.items() if k != "kept"}, False)
    if not ranked_items:
        return _other_reading(understood, words, clean, entries, reject)
    # an asked entry before a wanted one; then the best score; on a tie the entry that answers a
    # line asking to plan; then the entry that names the thing the line named; then the more
    # specific key; the rest keep the registry's order. A name is the subject of the question,
    # while an ask word ("how many") is only its shape: "how many steps are there in the Eiffel
    # Tower" is about the tower, not about steps a day, but "help me plan a trip to Paris" is
    # about the plan, not about Paris.
    ranked_items.sort(key=_row_order, reverse=True)
    carried = _the_subject_the_line_leans_on(understood)
    turned_down = set()
    for _asked, _ranked, _plans, _named, _keys, item, _on_ask in ranked_items:
        if reject is not None and reject(item):
            turned_down.add(item.id)
            continue
        if _the_subject_it_avoids(item, forms, carried):
            continue
        return item
    if plain is not None:
        # Every entry the line reached with its frame clause emptied has turned it down, so the
        # answer is in the clause itself: "how do i cut an onion without crying" is about the
        # tears, and the entry that answers it is the one keyed on the words the clause carries.
        # The clause is put back and the line read once more, before any repaired reading, so a
        # person who said what they want to avoid still gets an answer that speaks of it (the
        # module that turns down an answer ignoring the clause still has the last word).
        for _asked, _ranked, _plans, _named, _keys, item, _on_ask in plain:
            if item.id in turned_down:
                continue
            if reject is not None and reject(item):
                continue
            if _the_subject_it_avoids(item, forms, carried):
                continue
            return item
    # Every entry the line as typed reached turned it down, because the conversation says the
    # line is about something else. Another reading of the same line may reach one that can
    # answer: `what shood i cook tonight` reaches the plan entry and nothing else, while the
    # tidied line reaches the dinner ideas.
    return _other_reading(understood, words, clean, entries, reject)


# The same question said for a household rather than for one person. Nearly every key in the
# knowledge base is written in the first person singular ("what should i cook", "how do i stop
# condensation", "should i get a dog"), and people say the same thing with "we", "us" and
# "our": "what should we cook this weekend" got a hedge while "what should i cook this weekend"
# got the dinner list. Reading the line once more with those words in the singular is what makes
# one key answer both. Only whole words are shifted, the contractions are read as the words they
# are ("we've" -> "i've", "we're" -> "i'm"), "were" is left alone because it is as often "we
# were" as it is "we are", and the shift is a reading of last resort, so no answer that stands
# today can change.
HOUSEHOLD_WORDS = {
    "we": "i", "us": "me", "our": "my", "ours": "mine", "ourselves": "myself",
    "weve": "ive", "we'd": "i'd", "we'll": "i'll", "we're": "i'm", "we've": "i've",
}


def _household_reading(words):
    """The same words said for one person, or None when the line says "we" nowhere."""
    shifted = [HOUSEHOLD_WORDS.get(str(word).lower(), word) for word in words]
    return shifted if shifted != list(words) else None


def _other_reading(understood, words, clean, entries, reject):
    """The same line read another way, when the line as typed reached nothing that answers.

    Two readings sit beside the words a line was typed as. `plain` is the line with the words
    that are near a key word repaired in place ("wot shud i get me mum 4 xmas", "my scrambeld
    eggs come out rubbrey"); the understanding layer's `norm` is the line with its chat forms
    and missing apostrophes put right, which reaches a key a repair cannot ("what shood i cook
    tonight" carries no `what should i cook`). Both are tried only after the line as typed has
    found nothing, or found only entries that turned it down, so an answer that stands today
    cannot change.

    A third reading is the line said for one person instead of a household, which is what the
    keys are written in (`_household_reading`). It comes last, after the two repairs, because a
    line that has a word to fix needs the fix more.
    """
    plain = understood.get("plain")
    if isinstance(plain, str) and plain and plain != clean:
        again = {key: value for key, value in understood.items() if key != "plain"}
        again["clean"] = plain
        # The repaired line is read as words of its own: `words` is a list everywhere else, and a
        # guard that asks whether a word is in it ("what is the gulf stream") cannot test None, so
        # the whole answer raised and the turn fell to the composer's hedge - "what is today's
        # date" reached no card and got the search hedge for a date the bot works out itself.
        again["words"] = [word.lower() for word in _words_of(plain)]
        found = find(again, entries, reject)
        if found is not None:
            return found
    tidied = [word for word in understood.get("norm") or [] if isinstance(word, str)]
    typed = [word.lower() for word in words if isinstance(word, str)]
    if tidied and tidied != typed and understood.get("norm"):
        again = {key: value for key, value in understood.items() if key != "plain"}
        again["clean"] = " ".join(tidied)
        again["words"] = tidied
        again["norm"] = []
        # the nested search reads the tidied line as a household one itself, so there is no
        # second reading left to do here: returning its answer keeps the shift to one pass
        return find(again, entries, reject)
    shifted = _household_reading([word for word in words if isinstance(word, str)])
    if shifted:
        again = {key: value for key, value in understood.items()
                 if key not in ("plain", "norm")}
        again["clean"] = " ".join(shifted)
        again["words"] = shifted
        return find(again, entries, reject)
    return None



CONTEXT_WORDS = 8      # how much of the earlier line is searched, at most


SPECIFIC = 3    # a key word this few entries share still says something about the line


def _says_a_key_word(item, forms, rarity=None):
    """True when the line itself names one specific key word of the entry.

    This is narrower than `_touches()`: a phrase that only meets the entry as a phrase
    ("getting on" in "he is getting on a bit") is not the line naming what the entry is
    about, while "bites" in "she says it hurts when she bites" is. The distinction is what
    keeps a comment about a dog's age from taking the dog-introduction answer, while a
    follow-up about the biting itself still gets the biting answer.
    """
    if rarity is None:
        rarity = {}
    for part in item.key:
        for _, words, _ in _part_matches(part, forms):
            if len(words) != 1:
                continue
            if any(ch.isdigit() for ch in words[0]) or rarity.get(words[0], 0) <= SPECIFIC:
                return True
    return False


def _touches(item, forms, rarity=None):
    """True when the entry is reached from the line itself by a phrase or a rare word.

    A carried word that the entry half-matches is not enough: "do I need a cable for that"
    after moving phone photos to a laptop shares only "need" with the laptop-buying entry,
    and "need" is in a dozen keys, so the entry is about something else.
    """
    if rarity is None:
        rarity = {}
    for part in item.key:
        for _, words, _ in _part_matches(part, forms):
            # A figure is specific however many keys hold one: "hes 13" says which child and
            # which answer, and counting "13" as an ordinary word because the knowledge base
            # has entries for five-, eight- and ten-year-olds lost that follow-up.
            if len(words) > 1 or any(ch.isdigit() for ch in words[0]) \
                    or rarity.get(words[0], 0) <= SPECIFIC:
                return True
    return False


def _parts_across(item, carried_forms, forms):
    """True when the two lines between them complete the entry's key, one part from each.

    A key written as (the thing) x (what is asked about it) is specific as a pair, and the two
    halves can arrive a turn apart: "its a garden party" then "what do i wear as a man in his
    50s" is the party-outfit card, the occasion in the line above and the asking in this one.
    The own words alone touch that key only through "wear" and "what", which a hundred keys
    share, so the entry looked like the earlier line's business rather than the person's. It is
    the earlier line's business *and* this one's: different parts, one from each line.
    """
    own, above = set(), set()
    for index, part in enumerate(getattr(item, "key", ()) or ()):
        if _part_matches(part, forms):
            own.add(index)
        if _part_matches(part, carried_forms):
            above.add(index)
    return bool(own - above) and bool(above - own)


def key_words(item):
    """Every word the entry says it is about, singular ("cats" and "cat" count as one)."""
    found = set()
    for part in getattr(item, "key", ()) or ():
        options = (part,) if isinstance(part, str) else part
        for option in options:
            for word in str(option).lower().split():
                found.add(word.rstrip("s") or word)
    return found


def about(item, subject):
    """True when the entry is about the thing, not about a neighbour: a stew is not a steak."""
    head = (str(subject or "").split() or [""])[-1]
    head = head.rstrip("s") or head
    return bool(head) and head in key_words(item)


# The units a weight is said in, as the reading gives them: {"value": 5, "unit": "kg"}.
WEIGHT_UNITS = frozenset(("kg", "kgs", "g", "gram", "grams", "kilogram", "kilograms",
                          "kilo", "kilos", "lb", "lbs", "pound", "pounds", "oz",
                          "ounce", "ounces"))


def a_weight(understood):
    """True when the line gives a weight in kilos, grams or pounds.

    A figure with a unit of mass is what makes a line a kitchen line rather than a question
    about the thing the noun also names: "how long does a 5kg turkey take" is a bird for the
    oven, and it was two full days in Istanbul; "how long does a 5kg chicken take" was the
    lifespan of a pet. A card that answers a country, or how long an animal lives, is not
    asked with a weight in it, so it stands down and the cooking row gets the line.
    """
    for number in (understood or {}).get("numbers") or ():
        if isinstance(number, dict) and str(number.get("unit") or "").lower() in WEIGHT_UNITS:
            return True
    return False


PERSON_PRONOUNS = frozenset("he she they him them".split())


def _refers_to_the_person(understood):
    """True when the line itself speaks of the person: "he is getting on a bit"."""
    words = understood.get("norm")
    if not isinstance(words, list):
        words = str(understood.get("text") or "").lower().split()
    return any(word in PERSON_PRONOUNS for word in words)


SPEAKER_ONLY = ("i", "im", "ive", "id", "ill")
HANDLING_WORDS = ("say", "saying", "said", "tell", "telling", "answer", "answering", "agree",
                  "agreeing", "refuse", "refusing", "nod", "nodding", "smile", "smiling",
                  "laugh", "laughing", "apologise", "apologize", "explain", "explaining",
                  "ask", "asking", "keep", "keeps", "always", "never", "just", "usually")


def _says_how_the_speaker_handles_it(understood):
    """True when the line is the speaker saying how they handle the thing before it.

    "my boss keeps dumping work on me last minute" then "i never say no" is the saying-no
    question, and the line on its own names the behaviour and not the situation: the words it
    has are what the speaker does, and the situation was the line before. A statement that
    names a subject of its own ("i work nights") is not this, so the cats-at-night trap does
    not come back: nothing in it is about handling anything.
    """
    line = tokens(str(understood.get("clean") or understood.get("text") or ""))
    if not line or line[0] not in SPEAKER_ONLY:
        return False
    keys = [word for word in (understood.get("keywords") or []) if isinstance(word, str)]
    if not keys:
        return False
    return all(word in HANDLING_WORDS for word in keys)


def _following_on(understood, entries, forms, typed, by_domain, every, known=(), reject=None):
    """The entry a follow-up reaches with the subject of the line it leans on, or None.

    `reject` is honoured here too: the caller's veto is what stops an entry that declines the
    line from being offered again, so a search that ignored it would loop for ever.
    """
    leans = understood.get("leans_on")
    if not isinstance(leans, dict):
        return None
    words = leans.get("words") if isinstance(leans.get("words"), list) else []
    carried = [word for word in words if isinstance(word, str)][:CONTEXT_WORDS]
    if not carried:
        return None
    carried_forms = [_forms(word) for word in carried]
    _read_typos(carried, carried_forms, every, known)    # a misspelt earlier word too
    together = carried_forms + forms
    together_typed = carried + typed
    allowed = _topic_domains(understood, entries)
    best, best_score, best_domain = None, 0, ""
    seen = {}          # module-level parts only, for the same reason as in _best
    leans_subject = leans.get("subject")
    named_subject = leans_subject if isinstance(leans_subject, str) else ""
    for item in _reaching(entries, together):
        domain = getattr(item, "domain", "") or ""
        if allowed is not None and domain not in allowed:
            continue            # a domain that answers nothing the conversation is about
        if not score(item, together, together_typed, seen):
            continue
        if reject is not None and reject(item):
            continue
        # A guard is a test of the whole reading of the current line, and it holds here too: a
        # row that stands down for the line as typed cannot be brought back by the subject of
        # the line before it. Without this, "he asked me a question" after "she gave me a
        # question to answer" reached the quiz row through the words they share, and a
        # general-knowledge question went to somebody who was talking about someone else.
        guard = getattr(item, "guard", None)
        if guard is not None and not guard(understood):
            continue
        ranked = _rank(item, together, by_domain.get(domain) or every, seen)
        # The subject of the earlier line is what this line leans on, so an entry that names
        # that subject answers the pair before one that only shares its words: "my boss keeps
        # dumping work on me" then "i never say no" is the boundary lesson (the one keyed on
        # the boss), not the timing answer keyed on the work.
        if ranked and named_subject and about(item, named_subject):
            ranked += 100
        if ranked > best_score:
            best, best_score, best_domain = item, ranked, domain
    if best is not None and not _touches(best, forms, by_domain.get(best_domain) or every):
        # The earlier line alone chose it, and the line says nothing about it - unless the two
        # lines complete one key between them, a part each (see `_parts_across`).
        if not _parts_across(best, carried_forms, forms):
            return None
    # The follow-up's own words can name what the entry is about with one specific word:
    # "she says it hurts when it bites" after a wobbly tooth, and "should i raise it with her"
    # after a manager keeps cancelling their one-to-ones. That is not a neighbour of the
    # person in the earlier line, it is the thing being asked about, so it may answer below.
    # A phrase alone is not enough: "he is getting on a bit" meets the dog-introduction entry
    # only through "getting on", and the dog's age is not the introduction question.
    said = best is not None and _says_a_key_word(best, forms,
                                                  by_domain.get(best_domain) or every)
    if best is not None and not _reaches(best, carried_forms):
        return None    # the earlier line has no word of this entry: it is not the subject
    subject = leans.get("subject")
    named = isinstance(subject, str) and bool(subject)
    if best is not None and named and not about(best, subject):
        return None    # an entry about a neighbour of what the earlier line was about
    if (best is not None and named and leans.get("subject_type") == "person"
            and understood.get("kind") not in ("question", "request")
            and _refers_to_the_person(understood) and not said):
        # The follow-up is a statement about the person the earlier line named ("he is getting
        # on a bit" after "my dog is called Rex"), and its own words do not name what the entry
        # is about. An entry that shares only the person is then a neighbour of the subject,
        # not the subject: it is the dog's age, not how to introduce a puppy. A statement about
        # the speaker ("i never say no") is not about the person, and a follow-up whose own
        # words reach the entry ("she says it hurts when it bites") keeps it.
        head = set(_forms(str(subject).split()[-1]))
        other = [forms for forms in carried_forms if not (forms & head)]
        # A word of the earlier line can meet the entry as part of a phrase ("bed" in "gets out
        # of bed"), which _reaches() reads whole, so check the words too before standing down.
        words = set()
        for word in key_words(best):
            words |= _forms(word)
        if (other and not _reaches(best, other)
                and not any(forms & words for forms in other)):
            return None
    # An entry that shares only an ordinary word with the earlier line is not the earlier line's
    # subject, it is a neighbour of it: "my van wont start" and the brake-pedal entry meet on
    # "start", which is in a dozen keys, and "it clicks once and then nothing" then got a lesson
    # on brakes. When the earlier line named a thing, `about()` above has already checked this;
    # when it named nothing to lean on, the entry has to be reached by a phrase or a rare word.
    if best is not None and not named:
        if not _touches(best, carried_forms, by_domain.get(best_domain) or every):
            return None
    if best is not None and not _in_topic(best, understood):
        return None    # a fact from a different part of the knowledge base than the conversation
    return best


# A line that asks what to put on is a clothes question whatever the conversation is about.
# The chat's topic is what held the answer out: "its a garden party" then "what do i wear as a
# man in his 50s" was a gardening conversation, and the outfit cards live in a domain that
# answers shopping, so the clothes were never on the table and the person was told it was
# beyond what the bot knows. A wedding (friends-and-relationships) and a christening
# (family-and-parenting) blocked the same way.
_WEAR_ASK = re.compile(
    r"\b(?:what|which|how)\b[^.?!]{0,40}?\b(?:wear|wearing|put on|dress code)\b"
    r"|\b(?:what|which)\b[^.?!]{0,25}?\boutfit\b")


def asks_what_to_wear(understood):
    """True when the line asks what to put on, so the answer is a clothes one.

    Read from the line as typed: the reading's own words carry the topic along with it, and the
    carried words are what made the conversation about the garden rather than about the party.
    """
    said = ""
    if isinstance(understood, dict):
        said = str(understood.get("text") or understood.get("clean") or "")
        if not said:
            words = understood.get("words")
            said = " ".join(str(word) for word in words) if isinstance(words, (list, tuple)) else ""
    return bool(_WEAR_ASK.search(" ".join(tokens(said))))


def _topic_domains(understood, entries=None):
    """The knowledge domains that answer a topic the line is about, or None for all of them.

    A follow-up borrows the earlier line's words, so it can otherwise land in a domain the
    conversation never touched: "what can i take for it" and "how long before i should see a
    doctor" reach the entry for asking for time off, because that entry lists "doctor" too.
    Understanding already knows what the conversation is about, so a fact from a domain that
    answers none of those topics is not the same conversation's fact.

    None means "no opinion": the line names no topic, or every domain declares nothing, and
    then every entry is a candidate. Working it out before the search also keeps a follow-up
    from scoring a thousand entries in domains the conversation never touched.
    """
    topics = []
    if isinstance(understood, dict):
        found = understood.get("topics")
        topics = list(found) if isinstance(found, (list, tuple)) else []
        topics.append(understood.get("topic"))
        leans = understood.get("leans_on")
        if isinstance(leans, dict):
            topics.append(leans.get("topic"))
    topics = [topic for topic in topics if isinstance(topic, str) and topic]
    if not topics:
        return None
    from . import by_topic    # imported here: bot.knowledge imports this module to build entries
    judged = by_topic()
    allowed = {name for name, answered in judged.items()
               if not answered or any(topic in answered for topic in topics)}
    if entries is not None:
        allowed &= {getattr(item, "domain", "") or "" for item in entries}
    if allowed and asks_what_to_wear(understood):
        allowed.add("clothing")     # the ask is about clothes, whatever the chat is about
    return allowed if allowed else None


def _in_topic(item, understood):
    """Whether `item`'s own domain is one that answers lines about a topic of the line."""
    allowed = _topic_domains(understood)
    if allowed is None:
        return True
    return (getattr(item, "domain", "") or "") in allowed


def about_the_topic(item, understood):
    """True when the entry's domain answers a topic this reading is about.

    The same test a follow-up makes before it takes a fact: a bare ask ("what can i do") leans
    on the words of the line before it, and one of those words sits in other domains too, so
    "my kids wont listen to me" and then "what can i do" reached the music entry off the word
    "listen". A fact from a part of the knowledge base the conversation never touched is not
    the same conversation's fact.
    """
    return _in_topic(item, understood)


def _reaches(item, forms):
    """True when the entry matches at least one word of the line searched for it.

    The earlier line has to be the reason the entry is on the table. When it is not, the words
    carried over are a wish rather than a subject, and the entry answers something the person
    did not say: "it clicks once and then nothing" after "my van wont start" reached the
    brake-pedal entry, which shares no word with the van at all.
    """
    for part in item.key:
        if _part_matches(part, forms):
            return True
    return False


def names_its_own_subject(item, understood):
    """True when the entry's own subject is one this line names for itself.

    The first key part of an entry is its subject (the rest are the ask, the property or the
    setting), so this asks the one question a topic test cannot: does the line say the thing the
    entry is about? "why do we get allergies" says "allergies", which is the subject of the
    allergy entry, whatever the rest of the conversation is on. A domain test on its own cannot
    see that, because an entry lives in the domain that was written for it, and the domain that
    explains allergies is not the one a chat about a pet is in.
    """
    if not isinstance(understood, dict):
        return False
    clean = understood.get("clean") or understood.get("text") or ""
    forms = [_forms(word) for word in tokens(str(clean))]
    key = getattr(item, "key", ()) or ()
    return bool(forms) and bool(key) and bool(_part_matches(key[0], forms))

def _wrapped_subject(clean, norm_text=None):
    """The subject an advice ask wraps, or None when the line is not one.

    The wrapper is looked for in the line as typed and again in its ordinary words, because
    "any tips 4 a hangover" only says "for" once the chat-speak is undone.
    """
    plain = " ".join(word for word in WORD.findall(clean or "") if word not in _FILLER)
    for text in (clean, norm_text, plain):
        text = " ".join((text or "").replace(" | ", " ").split())
        if not text:
            continue
        for pattern in _WRAPPED:
            found = pattern.match(text)
            if not found:
                continue
            subject = found.group("subject").strip(" .,!?;:")
            if subject.lower() in _NOT_A_THING:
                return None
            if not any(word not in _NOT_A_SUBJECT for word in WORD.findall(subject)):
                return None
            return subject
    return None


def _the_ask_it_wraps(understood, subject, whole, entries, by_domain, every, reject):
    """The entry the subject inside an advice ask names, or None.

    The subject read on its own is what the line is about, so it answers when it can: "what
    should i do about slugs" was the tablespoons card, because "slug" is also how a cook says a
    small splash. When the subject on its own reaches nothing, the reading adds nothing and the
    line keeps whatever the whole of it found ("my hay fever is awful this week, what actually
    works" is a line whose subject is not a thing to look up, and its answer stands).
    """
    if not subject:
        return None
    words = [word for word in tokens(subject) if word not in _SUBJECT_POINTS]
    if len(words) == 1:
        # one everyday noun, which is the only subject the ask around it can complete. The noun
        # is read without the words that framed it: "what should i put on for a wedding" wraps
        # the subject "for a wedding", and reading the phrase whole reached the hotel row keyed
        # on "for a wedding" - a block of rooms booked for one - instead of the outfit answer the
        # line had already found. A noun on its own is the thing the ask is about.
        alone = _the_subject_alone(" ".join(words), entries, by_domain, every, reject)
        if alone is not None:
            # A framed entry the whole line reached on its own words keeps the turn: "any tips
            # for snoring" is the snoring explanation, and "what should i do about the damp" is
            # the water found first. The frame is for a subject the whole line could not reach.
            if whole is not None and getattr(whole, "id", "") in ASK_FRAME_IDS:
                return None
            return alone
    if whole is not None:
        # A subject of more than one word is a line in its own right only when the whole line
        # reached nothing. Otherwise the words it was said with are part of what it means:
        # "what should i do about my cat scratching the sofa" is a cat line and the words that
        # make it one are outside the subject, so reading the subject alone lost that.
        return None
    again = {key: value for key, value in understood.items()
             if key not in ("plain", "norm", "norm_text")}
    again["clean"] = subject
    # ... and the subject's own words, never None: a guard that asks whether a word is in
    # `words` raises on None, and the whole turn loses its answer.
    again["words"] = [word.lower() for word in _words_of(subject)]
    found = find(again, entries, reject)
    if found is not None:
        return found
    return _the_subject_alone(subject, entries, by_domain, every, reject)


# A subject word a dozen entries use is a word about other things as well: "kettle" is a scaled
# one, a broken one and a cheap one, so the ask around it says nothing about which is meant.
COMMON_WORD = 12


def names_one_thing(words, every):
    """True when the words of a subject name one thing rather than a dozen.

    A word a dozen entries use is a word about other things as well: "kettle" is a scaled one, a
    broken one and the price of one, and "what can i do about my kettle" asks about whichever it
    is, so the ask around it says nothing and the line is read by its words alone. A word one or
    two entries use - slugs, limescale, snoring - names that thing, so being asked about it is
    the second signal the one word cannot give.
    """
    for word in words:
        counts = [every.get(form) or 0 for form in _forms(word)]
        if not counts or max(counts) > COMMON_WORD:
            return False
    return True


def _the_subject_alone(subject, entries, by_domain, every, reject=None):
    """The entry a one-noun subject inside an advice ask reaches, or None.

    The subject is read with the ask around it kept as a signal, which is what `framed` means:
    "what should i do about the condensation" names one thing and asks about it, so the entry
    that owns that thing answers, while every entry not listed in ASK_FRAME_IDS is still read by
    the ordinary two-word rule. A subject with more words than that is read like any other line
    and finds its answer without this.
    """
    words = tokens(subject)
    if not words:
        return None
    forms = [_forms(word) for word in words]
    typed = [word.lower() for word in words if isinstance(word, str)]
    return _best({"clean": subject, "words": None, "kind": "question"}, words, subject, forms,
                 typed, entries, by_domain, every, reject,
                 framed=names_one_thing(
                     [word for word in words if word not in _SUBJECT_POINTS], every))
