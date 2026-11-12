"""A line that says the step was already taken is answered with the next turn of the thread.

"someone used my card online" / "i already called the bank" is the most useful thing a person
can say in an advice thread: they did the first thing, and what they want now is what comes
after it. Nothing read the line, so the store kept the words and the composer answered the
shape instead of the person: "Got it. Is there anything you'd like a hand with?", and a bare
"i already called the plumber" got "I'm listening - say more if it helps.", which is what
STYLE.md calls the therapist pattern - a line that would fit any message at all.

So this reads the report and answers the next turn of the thread. Which reply that is depends
on the answer behind it:

* where the answer still has a step after theirs, that step is the reply, read from the answer
  itself: "turn the water off at the isolating valve under the sink, take the handle off, and
  take the old part to a hardware shop" is answered with "take the handle off, and take the old
  part to a hardware shop". A reply of our own there would be one sentence behind the card and
  would ask about a result that cannot exist yet - turning the water off cannot make a dripping
  tap better, and bleeding the radiators does not stop a boiler losing pressure;
* where the answer has nothing left to say, the report gets the one thing a friend asks next:
  how it went. That question is named by the kind of step, because the question that follows a
  call is not the question that follows a repair - "what did they say?" against "is it any
  better since?".

The rule is narrow on purpose:
* the line has to say "already" and then a step that was taken, as a past-tense verb
  ("called", "tried", "bled", "turned"), so "i already have a dog" - a fact about their
  house - is not a report on anything and is left to the store;
* the line must not ask anything of its own ("i already bled the radiators what next" wants
  the next step, not a question about this one), and it must be short: a report, not a story;
* a hard thread is left alone: after a death, "i already told my mum" is about the person who
  died, and a cheerful "what did they say?" would be grotesque.
"""
import re

from . import repeat

# The words a report puts in front of "already": the person, and the "have" that people type as
# "ive" or "i've" or leave out altogether.
SUBJECT = r"(?:i|we|ive|i've|weve|we've|i have|we have|i had|we had)"
ALREADY = re.compile(r"^\W*(?:(?:ok|okay|so|well|yeah|yep|yes|and|but|oh|right|alright|no)\W+)*"
                     r"(?:" + SUBJECT + r"\W+)?already\W+(\w+)", re.I)
# The same report with "did" in front of the step, which is how most people say it when the
# answer told them to do something: "i did ring them though, twice", "i did turn it off", "we did
# call them". Nothing read this shape, so a benefits chat that had just been told to ring the
# decision letter's number was answered with the ceramic-hob card - the line's "ring" and the
# topic's "stopped" met in that entry's key - and every turn after it stayed on the hob.
DID = re.compile(r"^\W*(?:(?:ok|okay|so|well|yeah|yep|yes|and|but|oh|right|alright|no)\W+)*"
                 r"(?:i|we|ive|i've|weve|we've|i have|we have)\W+did\W+(\w+)", re.I)
# A step said after "did" is said in the base form ("ring", not "rang"), and only the steps the
# report list already knows: "i did my back in" is an injury, not a step taken on anything.
# "try" is left out on purpose: "i did try that" is the report `repeat` answers with the rest of
# the answer ("Same as before: the things that work..."), and claiming it here replaced that.
DID_STEPS = frozenset("""call ring phone email text message speak talk ask tell contact write
send pay go see make take put book order buy fix bleed clean reset turn change check clear
tighten replace restart unplug soak scrub defrost hoover paint apply cut start stop give
complain report cancel register fill submit""".split())
# What may follow the step and still leave the line a report: the people it was done to, when, and
# the little words that point back at it. Anything else is the line saying something of its own
# ("i did ring the council about the bins") and is left to the entries, which read it better.
DID_TAIL = frozenset("""that this it them him her me us the a an one ones thing stuff though tho
although again already twice once too well just still even really very much more some any all
and but so oh ok okay yeah yep yes no not yet since yesterday today tomorrow morning afternoon
evening last night week month year now then before after first both either
off out on up down around round through over back away""".split())


def _the_step_after_did(low):
    """The step in a line that says it with "did": "i did ring them though, twice", or None.

    The word after "did" is in the base form ("ring", not "rang"), so it is read against the
    steps this module knows rather than against a past tense: only a step of `DID_STEPS` is
    claimed here, and what follows it has to be one of the little words a report is padded with,
    so "i did ring the council about the bins" keeps its own turn for the entries to read.
    """
    match = DID.search(low)
    if not match:
        return None
    step = match.group(1)
    if step not in DID_STEPS:
        return None
    tail = re.findall(r"[a-z']+", low[match.end():])
    if any(word not in DID_TAIL for word in tail):
        return None
    return step

# The same report said the other way round: "i called them already", "we paid already". The step
# is the word right after the person, and "already" at the end says when.
TRAILING = re.compile(r"^\W*(?:(?:ok|okay|so|well|yeah|yep|yes|and|but|oh|right|alright|no)\W+)*"
                      r"(?:i|we|ive|i've|weve|we've)\W+(\w+)\b.*\balready\W*$", re.I)

# The same report with no "already", for the shapes people type without it ("i did that",
# "ive called them") is the composer's (bot/compose/fallback.py: TRIED_IT); this reader is only
# the word "already", which is what nothing read.
PAST = frozenset("""called rang phoned emailed texted messaged spoke talked asked told contacted
wrote sent paid went seen saw made took put booked ordered bought tried fixed bled
cleaned reset turned changed checked cleared tightened replaced restarted unplugged soaked
scrubbed defrosted hoovered painted applied cut started stopped gave complained reported
cancelled registered filled submitted""".split())
# A step that was taken by talking to somebody: the question after it is what they said. Being
# asked twice is the same step - the answer there is whether an answer came back.
CONTACT = frozenset("""called rang phoned emailed texted messaged spoke talked asked told
contacted wrote complained reported""".split())
# A step that was taken and has nobody on the other end to answer: a booking, an order, a form
# sent off. "what did they say?" is a question nobody can answer about those, so they are asked
# how it went instead. "sent" is on this list rather than the one above because what people send
# is a form or a parcel, not a question.
NOBODY_TO_ANSWER = frozenset("""booked ordered registered submitted cancelled filled sent
paid""".split())
# An apology given is not a question asked: "i already told her sorry" is a step with no answer
# coming, however much "told" usually expects one.
AN_APOLOGY = re.compile(r"\b(?:sorry|apolog\w*)\b", re.I)
# A step that was taken on a thing: the question after it is whether the thing is any better.
REPAIRED = frozenset("""fixed bled cleaned reset turned checked cleared tightened replaced
restarted unplugged soaked scrubbed defrosted hoovered painted applied""".split())
# A step that changes what the person does rather than what a thing is: how it goes is only
# knowable after a while, so the answer is to keep at it and say what happens.
CHANGED = frozenset("""tried started stopped gave paid ordered bought made took put went
changed cut""".split())
# A change made to a thing in the house is a repair on that thing, not a change in the person's
# life: "my washing machine smells of damp" / "i changed the washer already" was answered "Good.
# How are you finding it?", which is the line for somebody who has started at a gym. What makes
# "change" a life change is its object, and those are the person's own doings, so they are named
# here and every other object is a thing that was mended, swapped or fitted. Only "change" moves:
# the other words in `CHANGED` with a thing after them ("cut the grass") are jobs whose next
# question this module has no better answer to, and guessing one is worse than the pool it has.
CHANGED_OF_A_THING = frozenset(("changed",))
A_LIFE_OBJECT = frozenset("""job jobs shift shifts hours routine routines plan plans mind diet
school course habit habits career way ways approach lifestyle life body sleep mood name names
address phone number provider tariff deal supplier gym class club doctor dentist""".split())
# Changing a person, a creature or the washing a person changes is not a repair either: a nappy
# change is not a washer, and "ive changed him already" after "the baby keeps crying and wont
# settle" was answered "Then give it a day and tell me if it settles", which is a sillier line
# than the one it replaced. Anything the person changes rather than mends is named here - a
# person or a creature, and the laundry and the bins - and keeps the pool it had before the
# object decided anything.
CHANGED_NOTHING_BROKEN = frozenset("""baby babies boy girl kid kids child children little one
him her them me you us everyone everybody nappy nappies pad pads sheet sheets bedding bed cot
quilt duvet pillow pillowcase towel towels flannel bag bags bin bins water loo toilet roll tea
dog cat puppy kitten pup hamster rabbit guinea budgie bird birds fish pet pets""".split())
# A word that asks something of its own. "what next" after the report is a different ask, and
# the modules that read asks are better at it than a question about this one.
ASKING = re.compile(r"\b(?:what|whats|what's|how|when|where|which|who|why|should|shall|can|could|"
                    r"will|would|may|might|do|does|did|is|are|any|anything)\b", re.I)
# A report on the bot's own last answer ("i already told you") is a complaint about the repeat,
# and the composer has a line for that; it is not a step that was taken on anything.
TO_THE_BOT = re.compile(r"\b(?:you|u|your|yours|youse)\b", re.I)
# The most a report can be and still be a report: "i already turned the water off" is six.
MOST_WORDS = 9
# A hard thread is not answered with a cheerful question about how it went.
HARD = re.compile(r"\b(?:died|dying|death|passed away|funeral|burial|cremation|miscarriage|"
                  r"stillborn|hospital|hospice|cancer|diagnosis|suicide)\b", re.I)

CONTACT_REPLIES = (
    "Then it's with them now - what did they say?",
    "Right. Did they give you an answer?",
    "Fair enough. What did they say?",
    "Good. Have they said anything back yet?",
)
# The trouble itself is over, so none of the answer's steps is handed back and nothing about the
# steps is asked: what a friend asks is what it took and whether it will hold.
#
# These are for the line that names no thing ("its sorted now", "its fixed", "thats out of the
# way"). A line that does name the thing gets one of the pools below instead, and that is not
# cosmetic: a take that names nothing of the line is not read as having answered it, so the card
# that shares the thing's own word is handed the turn right over it ("my boiler is fixed" got the
# boiler repair card, which is about a boiler that is broken). A friend says "is the boiler
# holding?" too, so naming the thing is both the reading and the wording.
OVER_REPLIES = (
    "Good - that's the job done. Did somebody come out in the end, or did you sort it yourself?",
    "That's a relief. What was it in the end?",
    "Good to hear it. Is it holding, or is it one of those that comes back?",
    "Right - so that's out of the way. What did it take?",
)
# The words that say a job is done rather than a thing mended: the named pool for those is about
# the job ("how long did the bedroom take you"), not about whether the thing holds.
OVER_A_JOB_DONE = frozenset(("done", "finished", "sorted"))

# The same question with the thing named, for a mended thing: whether it holds is the thing a
# friend asks about a thing that has just been fixed, and "what was wrong with it" is the other.
# None of these asks who did the work: "he says the work is done" is somebody else's job, and
# "did you do it yourself, or did somebody come out?" is the wrong question about it.
OVER_NAMED_REPLIES = (
    "Good to hear it. Is the {thing} holding, or is it one of those that comes back?",
    "Good - the {thing} sorted then. What was it in the end?",
    "That's a relief. What was wrong with the {thing}, in the end?",
    "Right - so the {thing} is out of the way. Did it take long?",
)
# A job done rather than a thing mended ("the bedroom is done"): what is left to ask is about the
# job, because "is the bedroom holding" is not a question anyone asks.
OVER_NAMED_JOB_REPLIES = (
    "Right - the {thing} done then. What was the fiddly part?",
    "Good. How long did the {thing} take?",
    "That's the {thing} out of the way. Was it as big a job as it looked?",
    "Nice one. What was the {thing} like to do?",
)
REPAIRED_REPLIES = (
    "Then that's the first thing done. Is it any better since?",
    "Right - has it made a difference?",
    "Good. If it's still the same tomorrow, say and we'll go a step further.",
    "Then give it a day and tell me if it settles.",
)
CHANGED_REPLIES = (
    "Right - has it made any difference yet?",
    "Early days, then - what has changed so far?",
    "Good. How are you finding it?",
)
REPORT_REPLIES = (
    "Right - how did that go?",
    "Good. What happened when you did?",
    "Then what came of it?",
)
# The report of a thing finished where there is nothing left to ask about it: the charger found,
# the booking made, the hall painted. "How did that go?" is the question for a repair that may
# not have worked; a thing that is settled gets the line that closes it, and the next turn of the
# thread is the person's own.
SETTLED_REPLIES = (
    "Good \u2014 that's that sorted, then.",
    "Nice one. One less thing on the list.",
    "Good. That is that one off your mind.",
)


def _a_crisis_line_said(memory, words):
    """True when the bot's own last words in this stretch named a crisis line."""
    turns = [t for t in (memory.get("turns") or []) if isinstance(t, dict)][-2:]
    for turn in reversed(turns):
        said = str(turn.get("bot") or "").lower()
        if said and any(word in said for word in words):
            return True
    return False


def _a_hard_thread(memory):
    """True when the conversation is about a death or an illness, where this reader stands down."""
    turns = [t for t in (memory.get("turns") or []) if isinstance(t, dict)]
    for turn in turns[-2:]:
        if HARD.search(str(turn.get("bot") or "")) or HARD.search(str(turn.get("user") or "")):
            return True
    return False


# The same report with no "already" in it, which is how most people say it once the job is over:
# "ive fixed it", "i've done it", "i did it", "ive found one". Nothing read the shape, so the
# entry that gave the step answered the report as the same ask again - "the tap is dripping" /
# "ive fixed it" got the whole "go underneath and tighten the back nut" card a second time, "i
# want to sort the loft out" / "ive done it" the clearing advice again, and "how do i get rid of
# the smell in the fridge" / "done that, thanks" the hiding-places card. The word "already" is
# what the reading hung on, and the person who has finished the job has no reason to type it.
FINISHED_ACT = re.compile(
    r"^\W*(?:(?:ok|okay|so|well|yeah|yep|yes|and|but|oh|right|alright|no)\W+)*"
    r"(?:i|we|ive|i've|weve|we've|i have|we have)\W+(?:just|already|finally|now|nearly)?\W*(\w+)\W+"
    r"(?:it|them|one|that|this|everything|the lot|all of it)\b", re.I)
# The thing done named as itself, with the doer left out: "its done", "thats sorted", "all done".
FINISHED_ITSELF = re.compile(
    r"^\W*(?:(?:ok|okay|so|well|yeah|yep|yes|and|but|oh|right|alright|no)\W+)*"
    r"(?:it|its|it's|that|thats|that's|all)\W+(?:is\s+|was\s+|were\s+|got\s+|gets\s+|now\s+)?"
    r"(done|sorted|fixed|finished|working|mended|booked|ordered|paid|collected|replaced)\b", re.I)
# Nothing but the word for it, which is how a person closes a job that has just been talked about.
BARE_DONE = re.compile(r"^\W*(?:all\s+)?(done|sorted|finished|fixed)\W*(?:,?\s*(?:thanks|ta))?\W*$", re.I)
# The same word with the job pointed at: "done that, thanks" after the bot has handed the job over.
DONE_THAT = re.compile(r"^\W*(?:(?:ok|okay|so|well|yeah|yep|yes|and|but|oh|right|alright)\W+)*"
                       r"(done|sorted|fixed|finished|tried)\W+(?:that|this|it|them)\b", re.I)
# The steps a completion can be said with. The words in `PAST` are the past tense of an
# instruction; these are the ones a finished job is said with that an instruction never uses:
# "found one" closes a search and "done" says the whole of it is over, and both were left out of
# the "already" reading on purpose ("i already got one" is a fact about their house).
FINISHED_STEPS = frozenset("""
    fixed done finished sorted mended repaired replaced cleaned painted hoovered tidied
    found bought ordered booked returned collected installed cleared changed
    washed rang called emailed texted paid sent submitted filled cancelled cancelled
""".split())
# A step that closes the thing rather than mending it: what is left to ask about a thing that has
# been found or bought is nothing, so the reply there is the sentence a friend says to close it
# instead of the question that follows a repair ("is it any better since?").
SETTLED = frozenset("""
    done finished sorted found bought ordered booked returned collected sent submitted
    filled cancelled canceled paid
""".split())
# The words that say the whole job is over and name no step of it: the answer has nothing after
# them, because what the person is reporting is the end of the job the answer opened.
BARE_COMPLETION = frozenset(("done", "finished"))


def _the_step(low):
    """The step the line says was already taken, or None.

    Only the word after "already" decides that it is a step: a past-tense verb, and not one of
    the ones that only ever says what somebody has ("got", "had", "been"), because "i already
    got one" is a fact about their house and not a report on anything the bot said.
    """
    match = ALREADY.search(low) or TRAILING.search(low)
    if not match:
        return None
    step = match.group(1)
    if step in TELLING and APOLOGY.search(low):
        return APOLOGY_STEP
    if step not in PAST and not step.endswith("ed"):
        return None
    return step


# The words a line may still say after the job is reported finished and still be only that report:
# "ok done that, thanks", "its done now". Anything else is the line saying something more -
# "ok done that, still dripping" reports the job *and* the fault - and the more is the turn.
MORE_PADDING = DID_TAIL | frozenset("""thanks ta cheers brilliant great good nice lovely
perfect out off up properly""".split())
# The advice that is kept up rather than finished: staying active for a bad back, walking half an
# hour a day, sticking to a diet. "done that" after it means "I'm following your advice", not "the
# job is over", and closing it ("Good - that's that sorted, then.") tells somebody with a sore back
# that their back is sorted. So a bare completion is only read when the answer's first sentence
# hands over a job with an end.
KEPT_UP = re.compile(r"\b(?:keep\s+(?:walking|going|doing|at\s+it|it\s+up|an?\s+eye)|"
                     r"carry\s+on|every\s+day|each\s+day|twice\s+a\s+(?:day|week)|"
                     r"a\s+day|a\s+week|stick\s+(?:with|to)|a\s+habit|"
                     r"one\s+day\s+at\s+a\s+time)\b", re.I)


def _nothing_more(low, match):
    """True when the job is all the line says, so the report has no second half to answer."""
    tail = re.findall(r"[a-z']+", low[match.end():])
    return all(word in MORE_PADDING for word in tail)


def _a_job_with_an_end(answer):
    """True when the answer's first sentence hands over a job that finishes, not one kept up."""
    first = re.split(r"(?<=[.!?])\s+", str(answer or "").strip())[0]
    return not KEPT_UP.search(first)


def _the_finished_step(low, memory=None):
    """The step a report of a job finished names, or None.

    The same reading as `_the_step` for the line that says the job is over without the word
    "already": "ive fixed it" names the fix, "ive found one" the search, and "its done" says the
    whole of it is over without naming a step at all, which is why it is read as "done".
    """
    step = None
    match = FINISHED_ACT.search(low)
    if match:
        found = match.group(1)
        if (found in FINISHED_STEPS or found == "did") and _nothing_more(low, match):
            step = "done" if found == "did" else found
    if not step:
        match = FINISHED_ITSELF.search(low) or BARE_DONE.match(low) or DONE_THAT.match(low)
        if match:
            if not _nothing_more(low, match):
                return None
            step = match.group(1).lower()
    # A step named by its own word ("ive fixed it", "its fixed") is a job that was finished; the
    # bare words are the whole job said at once ("done", "its done", "ok ive done that"), and those
    # only close a job when the answer handed one over that ends.
    if step in BARE_COMPLETION and not _a_job_with_an_end(_the_last_answer(memory or {})):
        return None
    return step


# The verbs that can carry an apology, and the step an apology report is read as.
#
# "i already told her sorry" is one step, and it is the apology rather than the telling: an entry
# that teaches an apology says "say sorry" or "I'm sorry" and never "tell", so the report read as
# "told" was not recognised in the reply and the entry read that advice out to somebody who had
# just taken it. Only the words for an apology make this read, so a report of telling somebody
# something else ("i already told the council") keeps its own verb. The verbs are the ones an
# apology is carried by, and "said" is here because it also arrives with no past-tense ending in
# `PAST` - "i already said sorry" is the same report as "i already told her sorry".
TELLING = frozenset(("told", "said", "spoken", "texted", "messaged", "written", "apologised"))
APOLOGY_STEP = "apologise"
APOLOGY = re.compile(r"\b(?:apolog\w*|sorry)\b")


def the_step_they_took(text, memory=None):
    """The word for the step the person says they already took, or None.

    Published so the store and the composer can tell this report from a fact about their house
    with one reading, the same way the other readers in this package are shared.
    """
    low = " ".join(str(text or "").lower().split())
    if not low or "?" in low:
        return None
    words = low.split()
    if len(words) > MOST_WORDS:
        return None
    if TO_THE_BOT.search(low):
        return None
    # The trouble itself is over. It is taken before the asking words are read, because "is" in
    # "my boiler is fixed" is a state and not a question, and the reading above is the one that
    # tells the two apart.
    over = the_trouble_is_over(low)
    if over:
        if _a_hard_thread(memory or {}):
            return None
        return over
    # "did" is on the asking list because "did i leave the oven on" is a question, and after "i"
    # it is the report itself: "i did ring them" asks nothing. What may follow the step is what
    # keeps this a report (`_the_step`), so the ask word is let through only there.
    if ASKING.search(low) and not DID.search(low):
        return None
    step = _the_step(low) or _the_step_after_did(low) or _the_finished_step(low, memory)
    if not step:
        return None
    if _a_hard_thread(memory or {}):
        return None
    return step


# The word the answer gave for the step, so a report can be told from a step the bot never asked
# for. A past tense is put back to the word an answer uses, because an answer says what to do and
# a report says what was done.
IRREGULAR = {"bled": "bleed", "tried": "try", "rang": "ring", "told": "tell", "paid": "pay",
             "made": "make", "took": "take", "went": "go", "saw": "see", "spoke": "speak",
             "wrote": "write", "sent": "send", "bought": "buy", "gave": "give", "put": "put",
             "ran": "run", "came": "come", "did": "do", "said": "say", "fed": "feed",
             "led": "lead", "set": "set", "cut": "cut", "read": "read", "hit": "hit"}


# A report of the outcome rather than of a step: "i already fixed it" says the job the answer was
# for is done, and names no word the answer used ("start with a plunger over the plughole"), so
# there is nothing to match it to. The words here only ever say that work on a thing is finished,
# so they match any answer that handed a move over (see `_gave_a_step`).
AN_OUTCOME = frozenset("""fixed mended repaired sorted done finished""".split())


# A line that reports the trouble itself as over. Everything above is a report of a step the
# person took; this one names no step at all, and the entry that answered before reads it as the
# same ask again. "my boiler is fixed" was answered with the repair card ("Check the pressure
# gauge, the thermostat and the boiler's reset button"), and so was "the boiler man came and it is
# fixed": the thing's own word got the card its turn, and the card is about a boiler that is
# broken. A reply has to be about the line, and a shared word is not enough.
OVER_WORD = re.compile(r"\b(fixed|mended|repaired|sorted|done|working|works)\b", re.I)
# The line says it as a state: a copula in front of the word ("my boiler is fixed", "it's sorted
# now"), or the person as the one who did it ("i sorted it", "we fixed it yesterday").
OVER_STATE = re.compile(r"\b(?:is|are|was|were|'s|been|now|still|its|it's)\b", re.I)
# "all my mates are sorted" is a person who has their life in order, not a thing that was mended.
OVER_PEOPLE = frozenset("""mates friends everyone everybody people kids children family folks
lads girls boys others us them they we i life lives""".split())
# Nothing here is a state of a thing: not the ask, not the wish, not the complaint, and not the
# adjective that sits in front of a noun ("a fixed rate", "fixed nights", "fixed in place").
OVER_NOT = re.compile(
    r"\b(?:not|never|nothing|none|n't|until|till|til|before|when|if|unless|once|still\s+not|"
    r"yet|hasnt|hasn't|didnt|didn't|wont|won't|cant|can't|couldnt|couldn't|should|need|needs|"
    r"want|wants)\b", re.I)
OVER_ADJECTIVE = frozenset("""rate rates price prices term terms fee fees cost costs charge
charges nights night hours hours salary contract deal amount penalty budget rent appointment
time day week month year in up point order place""".split())
# What follows the word can be an adjective ("a fixed rate") and what is in front of it can be a
# person ("all my mates are sorted"); neither is a thing in a state. What neither covered is the
# word itself meaning something else about some kinds of thing, and `_the_thing_said` is what
# those are read against:
#   - an EVENT that is fixed was rigged, not mended ("the match is fixed", "the game was fixed");
#   - a MEAL that is done has finished cooking ("dinner is done", "the roast is done");
#   - HAIR or NAILS that are done have been styled ("my hair is done").
# Each of those reached the pool of lines that say a repair is over, and "That's a relief. What
# was it in the end?" is not an answer to any of them.
OVER_NOT_A_THING_NAMED = frozenset("""match matches game games race races fight fight vote votes
election elections draw draw lottery raffle bet bets trial trials contest competition fixture
competitions tournament score result results odds price prices""".split())
OVER_A_MEAL = frozenset("""dinner tea lunch breakfast supper brunch food meal meals roast cake
cakes bread pastry curry stew soup pizza""".split())
OVER_STYLED = frozenset("""hair hairs nails nail lashes brows eyebrows makeup make-up face
beard fringe colour color dye highlights""".split())
# Words in front of the thing that are not part of its name, and words that mean the line names
# no thing at all, because "it" is what the last turn already said.
OVER_LEAD = frozenset("""my our your his her their its it's the a an this that these those both
whole old new little big other same own""".split())
OVER_NO_THING = frozenset("""i we he she they you me us them it its it's that thats that's this
everything all nothing something anything someone somebody""".split())
# What can sit between the thing and the word and still leave the thing the subject: "my boiler
# is fixed", "the tap was fixed yesterday", "the heating is finally working".
OVER_BETWEEN = frozenset("""is are was were s been got gets get now still finally again just
at last always never""".split())
# The words that end the search backwards for the thing: the subject changes after them.
OVER_STOP = frozenset("""and but so because after when if until since although though while
than then also plus with""".split())


def _the_thing_said(low, at):
    """The thing named in front of the word at `at`, or None when the line names no thing.

    "my boiler is fixed" names the boiler, "the washing machine is repaired" the washing machine,
    and "its sorted now" names nothing at all. Only a thing, not a person or an event: the classes
    in the frozensets above read the word as something else entirely.
    """
    words = low[:at].split()
    while words and (words[-1].strip(".,!'") in OVER_BETWEEN
                     or words[-1].strip(".,!'") in OVER_STOP):
        words.pop()
    if not words:
        return None
    thing = []
    for raw in reversed(words):
        bare = raw.strip(".,!'")
        if not thing and bare in OVER_NO_THING:
            return None
        if bare in OVER_LEAD or bare in OVER_STOP or bare in OVER_BETWEEN:
            break
        if bare in OVER_NO_THING:
            return None
        thing.append(bare)
        if len(thing) == 2:
            break
    if not thing:
        return None
    thing = " ".join(reversed(thing))
    head = thing.split()[-1]
    if head in OVER_NOT_A_THING_NAMED or head in OVER_A_MEAL or head in OVER_STYLED:
        # The word means something else about this kind of thing, and the reading is not about a
        # mended thing at all: "the match is fixed" is rigged and "dinner is done" is cooked.
        return False
    return thing


def the_thing_that_is_mended(text):
    """The thing a line says is fixed, or None. Published so a caller can say it back."""
    word, at, low = _the_over_word(text)
    if not word:
        return None
    thing = _the_thing_said(low, at)
    return thing or None


# A line that opens with an auxiliary or a wh-word is asking, with or without its question mark.
OVER_ASKING = re.compile(r"^\W*(?:is|are|was|were|do|does|did|has|have|had|will|would|shall|"
                         r"can|could|should|may|might|when|what|whats|what's|how|why|where|who|"
                         r"which|if|isnt|isn't|wasnt|wasn't)\b", re.I)


def _the_over_word(text):
    """The accepted word, where it starts, and the line, or (None, -1, "")."""
    low = " ".join(str(text or "").lower().split())
    if not low or "?" in low or len(low.split()) > MOST_WORDS:
        return None, -1, low
    if OVER_ASKING.search(low) or OVER_NOT.search(low):
        return None, -1, low
    words = low.split()
    for match in OVER_WORD.finditer(low):
        word = match.group(1)
        at = len(low[:match.start()].split())
        after = words[at + 1] if at + 1 < len(words) else ""
        if after.strip(".,!") in OVER_ADJECTIVE:
            continue
        window = " ".join(words[max(0, at - 4):at])
        if any(w.strip(".,!") in OVER_PEOPLE for w in window.split()):
            continue
        if OVER_STATE.search(window):
            if _the_thing_said(low, match.start()) is False:
                continue
            return word, match.start(), low
    return None, -1, low


def the_trouble_is_over(text):
    """The word that says the trouble is over, or None.

    Only the state of a thing reads here, and only when the line is a report: short, no question,
    nothing asked of the trouble ("can it be fixed", "how long until it is fixed" are the asks the
    entries answer), and nothing left over of it ("still not fixed", "the landlord hasnt fixed it").
    """
    return _the_over_word(text)[0]


def _gave_a_step(answer):
    """True when the answer handed a move over, whatever the move was.

    The composer's own reading of an answer's first instruction, because the question here is
    only whether there was a step at all: a report of the outcome is about that step, and an
    answer that gave none is a new ask the entries should answer.
    """
    try:
        from ..compose import verdict
        return bool(verdict._an_instruction_sentence(answer))
    except Exception:  # noqa: BLE001 - a reading that fails matches nothing
        return False


def _says_the_step(step, answer):
    """True when the last answer is where the person got the step they have already taken."""
    if step == APOLOGY_STEP or step.startswith("apolog"):
        return bool(SAYS_APOLOGY.search(str(answer or "").lower()))
    if step in AN_OUTCOME:
        return _gave_a_step(answer)
    word = IRREGULAR.get(step, step)
    if len(word) >= 4 and word.endswith("ed"):
        stem = word[:-2]
    elif len(word) >= 4 and word.endswith("e"):
        stem = word[:-1]
    else:
        stem = word
    for other in re.findall(r"[a-z]+", str(answer or "").lower()):
        if other.startswith(stem) or (len(other) >= 4 and word.startswith(other)):
            return True
    return False


def takes_as_it_comes(text, memory):
    """True when this report should be answered as it comes, whatever else proposed.

    A report that the step was already taken is not an ask, and the entry that gave the step
    reads it as the same question again: "my boiler is making a noise" / "i already bled the
    radiators" got the bleeding instructions a second time. So the line is claimed - but only
    when the step is one the last answer itself named. Every other report is a new ask ("my
    landlord wont fix the heating" / "ive already rung the council about it" is still the
    council's answer to give) and is left to the entries.
    """
    try:
        if not reply_for(text, memory):
            return False
        step = the_step_they_took(text, memory)
        if not step:
            return False
        # A report that the trouble itself is over needs no answer of ours behind it: the entry
        # that answered before reads the line as the same ask and hands the repair over again,
        # and the person is told how to mend a thing they have just said is mended.
        if the_trouble_is_over(text):
            return True
        return _says_the_step(step, _the_last_answer(memory or {}))
    except Exception:  # noqa: BLE001 - a reading that fails claims no turn
        return False


# How the steps left are handed over, varied so the same word is not read out twice.
STEPS_LEADS = (
    "Then {said}.",
    "Right - {said}.",
    "Then that part is out of the way: {said}.",
    "Next: {said}.",
)
# The words a line holds that name no part of the step: the report itself, and the small words.
NOT_A_THING_WORD = frozenset("""already i ive we ve have had the a an it them that this those these
and but so oh ok okay well yeah yep no nah right alright then my our your his her their of to in
on at for with off out up down just still even really very much more some any all""".split())
# The words a report is padded with, which say nothing about which step they took: "i did ring them
# though, twice" holds none of the answer's subject, so the step is found by its verb alone. Left
# in, they counted as the thing the step was on, and the answer's step was never located.
REPORT_FILLER = frozenset("""did done do does though tho although again twice once back away around
round through over really actually honestly literally anyway anyways too also even just still
yet since today yesterday tomorrow morning afternoon evening night last week month year now
then before after first both either one ones thing stuff much many lot bits bit little quite
rather sort kind suppose guess think know said says told tell mean meant""".split())
# The most of the answer handed back this way: the step after theirs, the one after that, and the
# condition the answer puts on them ("if it keeps dropping, get a heating engineer out").
MOST_STEPS = 4
# A piece of a sentence is not a step: "a ticket you did not use can be refunded before travel on
# most fares, less an admin fee of up to about £10" splits after "most fares", and "less an admin
# fee" is the other half of that sentence, never an instruction. The words here only ever carry on
# the sentence before them.
NOT_A_STEP_START = frozenset("""less though although but and or so plus with without unless
whereas while which that who also still both either neither than then-as-i""".split())
# A new sentence is the answer moving on, except when it is the condition on the job in hand: "If
# it keeps dropping, there's a leak somewhere" is the next thing to know about the same job.
CONDITION_START = re.compile(r"^(?:if|when|once|should)\b", re.I)


# An answer teaches the apology step in its own words: it says to apologise, or it puts the
# apology in a sentence the person is to use ("Say sorry for the shouting, not for being tired").
SAYS_APOLOGY = re.compile(r"\b(?:apolog\w*|say sorry|says sorry|say you'?re sorry|"
                          r"i'?m sorry|i am sorry|sorry for)\b")


def _the_steps_after(step, answer, line=""):
    """The answer's steps after the one they took, in order, or an empty list.

    The step they took is found by the words they used rather than by its verb alone: "i already
    turned the heating off" holds "turned", and the answer's own "a quarter turn at a time" holds
    it too, so the verb alone picks a step they have not done. The thing and the state ("water",
    "off") say which step it was.
    """
    from . import limit as a_limit
    try:
        steps = [str(one).strip() for one, _ in a_limit._steps(answer) if str(one).strip()]
    except Exception:  # noqa: BLE001 - a reading that fails hands over no step
        return []
    if not steps:
        return []
    word = IRREGULAR.get(step, step).lower()
    if len(word) > 4 and word.endswith("ed"):
        stem = word[:-2]
    elif len(word) > 3 and word.endswith("e"):
        stem = word[:-1]
    else:
        stem = word
    wanted = {other for other in re.findall(r"[a-z']+", str(line or "").lower())
              if other not in NOT_A_THING_WORD and other not in REPORT_FILLER
              and not other.startswith(stem) and len(other) > 1}
    best, best_score = None, 0
    for index, sentence in enumerate(steps):
        words = set(re.findall(r"[a-z']+", sentence.lower()))
        score = len(words & wanted)
        if stem in sentence.lower():
            score += 1
        if score > best_score:
            best, best_score = index, score
    if best is None or (wanted and best_score < 2):
        return []
    after = [_the_instruction_of(one.strip().rstrip(" .,;")) for one in steps[best + 1:]]
    # A step that opens on a capital opens a new sentence, and the steps after it are usually the
    # answer moving on to something else: the remainder of their own job is the run of steps
    # before that. A sentence that opens on a condition ("If it keeps dropping, there's a leak
    # somewhere") is the exception - it is what the step they have just done is for - so it is
    # kept, and the run stops at the next new sentence after it.
    kept = []
    in_condition = False
    for index, one in enumerate(after):
        if not one:
            break
        if not kept and one.split()[0].lower().strip(",:") in NOT_A_STEP_START:
            # Only the first piece is checked: a later "and take the old part to a hardware shop"
            # is the other half of the step before it, which is one instruction said in two parts.
            break
        if one[:1].isupper():
            if in_condition or not CONDITION_START.match(one):
                break
            in_condition = True
        kept.append(one)
        if len(kept) >= MOST_STEPS:
            break
    return kept


def _the_instruction_of(step):
    """A step without the explanation hung on the end of it.

    The steps are cut from the answer at its own punctuation, and an instruction often carries
    its reason after a colon: "ask for an affordable payment plan: most councils will spread the
    arrears over the rest of the year". Handing that back says the whole paragraph again - the
    person asked what to do next, not why - so the step is the part before the colon, and the
    reason stays in the answer they were already given.
    """
    head, colon, tail = str(step or "").partition(":")
    if not colon or len(head.split()) < 2:
        return step
    return head.strip().rstrip(" .,;")


def _with_steps(after, memory):
    """The remaining steps said as what to do next."""
    said = ", ".join(step[0].lower() + step[1:] if step[0].isupper() else step
                     for step in after)
    said = said.rstrip(" .")
    # A step the answer already put in time order ("then put the request in writing") keeps its
    # own "then": the lead below says the same word, and "Then then put the request in writing"
    # was the reply to someone who had just rung them.
    said = re.sub(r"^(?:and\s+)?then\s+", "", said, flags=re.IGNORECASE)
    from ..compose import fallback  # the one place a pool is chosen from, so it varies
    return fallback._choose(STEPS_LEADS, memory or {}, said).format(said=said)


def _the_last_answer(memory):
    """The bot's last reply, which is the answer a report is about.

    When that reply was one step of an answer rather than the answer ("Start with this: Turn the
    water off at the isolating valve under the sink. There are three steps in all."), the answer
    it came from is what is read: the step alone has nothing after it, and "ive already turned the
    water off" would be told there is nothing left to do."""
    turns = [t for t in (memory.get("turns") or []) if isinstance(t, dict) and t.get("bot")]
    last = str(turns[-1].get("bot")) if turns else ""
    from . import plan as plan_steps
    try:
        return plan_steps.the_answer_in_hand(memory) or last
    except Exception:  # noqa: BLE001 - a reading that fails reads the last line as it did before
        return last


def tells_them_the_step_again(reply, text, memory):
    """True when `reply` still tells the person to do the step they have just reported doing.

    Published for the arbiter, which has to decide whether a card on the line's topic has read the
    report or answered the question above it. After "my boiler is making a noise" / "i already
    bled the radiators" the radiators entry read the bleeding instructions out a second time, and
    a card that still says "bleed the radiators" has not seen the line at all: the person has just
    told it they did. The reading is this module's own (`the_step_they_took` is the same reading
    that claims the turn), so the arbiter keeps no vocabulary of its own.
    """
    try:
        step = the_step_they_took(text, memory)
    except Exception:  # noqa: BLE001 - a reading that fails says nothing about the reply
        return False
    if not step:
        return False
    try:
        return _says_the_step(step, reply)
    except Exception:  # noqa: BLE001 - a reading that fails says nothing about the reply
        return False


def _of_a_thing(step, text):
    """True when the step was done to something in the house rather than to the person's life.

    The step words themselves say nothing about it - "changed" is in `CHANGED` for "i changed my
    routine" and it read "i changed the washer" the same way - so the object decides. A life
    object named after the step makes it a life change; anything else ("the washer", "the
    filter", "the bulb") is a thing that got mended, and the question after it is whether it
    is any better since. A person, a creature or the laundry is the third case: nothing was
    broken, so nothing is asked after it (`CHANGED_NOTHING_BROKEN`).
    """
    if step not in CHANGED_OF_A_THING:
        return False
    words = re.findall(r"[a-z']+", str(text or "").lower())
    try:
        at = words.index(step)
    except ValueError:
        return False
    after = words[at + 1:]
    if any(word in CHANGED_NOTHING_BROKEN for word in after):
        # A person changed, a creature changed, a nappy or a set of sheets: nothing was broken,
        # so there is no repair to ask after.
        return False
    return not any(word in A_LIFE_OBJECT for word in after)


def _only_finished(text):
    """True when the finished reading is the only reading of the line, and not the word "already"."""
    low = " ".join(str(text or "").lower().split())
    if _the_step(low) or _the_step_after_did(low):
        return False
    return bool(_the_finished_step(low))


def reply_for(text, memory):
    """The next turn of the thread for a report that the step was already taken, or None."""
    try:
        step = the_step_they_took(text, memory)
    except Exception:  # noqa: BLE001 - a reading that fails just offers no reply
        return None
    if not step:
        return None
    # The question that follows the step is the question that follows *the answer's* step, and a
    # chat with no answer yet has none. "i already called the bank" says which step it was and is
    # answered on its own ("Fair enough. What did they say?"), but the line that only says the job
    # is over - "ive fixed it", "its done", "done that, thanks" - names no step, so with nothing
    # behind it the job would have to be invented: "Then that's the first thing done. Is it any
    # better since?" is about a repair the chat never mentioned. With no answer to hang it on, the
    # line is answered as itself.
    if not _the_last_answer(memory or {}) and _only_finished(text):
        return None
    # The trouble itself is over: the answer's steps are behind them, and handing the next one
    # back tells them to fix a thing that is not broken any more.
    if the_trouble_is_over(text):
        from ..compose import fallback  # the one place a pool is chosen from, so it varies
        # Not in a thread the bot has already answered with a crisis line: "i want to kill myself"
        # / "its sorted" is not the place for "That's a relief. What was it in the end?", which
        # asks a person to go back over the crisis. The word list is the composer's, and it is
        # read off the bot's own last answer, whatever module it came from.
        if _a_crisis_line_said(memory or {}, fallback.CRISIS_WORDS):
            return None
        # The line itself is what the pool is chosen by, not the last answer: in a fresh chat
        # there is no last answer, so every "the trouble is over" line drew the same sentence -
        # the boiler, the damp, the tap and the television all got "Right - so that's out of
        # the way." `_mixed_seed` exists for exactly this: a sum of letter values collides on
        # lines of the same length, so the letters are mixed instead.
        # A line that names the thing is answered with a sentence that names it too. That is not
        # only the better sentence ("Is the boiler holding?"): a take that names nothing of the
        # line is not read as having answered it, so the card that shares the thing's word is
        # handed the turn over it, and the card is about a thing that is broken. See
        # `the_thing_that_is_mended`.
        thing = the_thing_that_is_mended(text)
        if thing:
            job = the_trouble_is_over(text) in OVER_A_JOB_DONE
            pool = OVER_NAMED_JOB_REPLIES if job else OVER_NAMED_REPLIES
            said = fallback._choose(pool, memory or {}, fallback.memory_bot(memory or {}),
                                    seed_text=text)
            return said.replace("{thing}", thing)
        return fallback._choose(OVER_REPLIES, memory or {}, fallback.memory_bot(memory or {}),
                                seed_text=text)
    # Where the answer still has a step they have not tried, that step is the reply and it is
    # `repeat`'s to hand back ("ive tried a hot wash already" gets the drying line, not a
    # question). Asking how it went is for the report the answer has nothing left to say to.
    try:
        # "ive tried the plunger already" is the shape `repeat` already owns: where the answer
        # still has a step they have not tried, that step is the reply, not a question about
        # this one. The other reports - a call made, a thing done - are not asks about the
        # answer's steps, and the answer's later sentences are usually about something else.
        if (step not in BARE_COMPLETION and repeat._tried(text)
                and repeat._later_part(text, _the_last_answer(memory or {}))):
            return None
    except Exception:  # noqa: BLE001 - a reading that fails just answers the step itself
        pass
    # Where the answer still has a step after theirs, that step is the reply: turning the water
    # off cannot make a dripping tap better, and bleeding the radiators of a boiler that keeps
    # losing pressure is not the end of that job either. The answer is the thing that says what
    # comes next, so it is read from the answer itself ("then take the handle off, and take the
    # old part to a hardware shop"). Asking how it went is for the report the answer has nothing
    # left to say to.
    try:
        if step in BARE_COMPLETION:
            after = []
        else:
            after = _the_steps_after(step, _the_last_answer(memory or {}), str(text or ""))
    except Exception:  # noqa: BLE001 - a reading that fails answers from the pool
        after = []
    if after:
        return _with_steps(after, memory)
    if step in NOBODY_TO_ANSWER or (step in CONTACT and AN_APOLOGY.search(str(text or ""))):
        pool = REPORT_REPLIES
    elif step in CONTACT:
        pool = CONTACT_REPLIES
    elif step in REPAIRED or _of_a_thing(step, text):
        pool = REPAIRED_REPLIES
    elif step in CHANGED:
        pool = CHANGED_REPLIES
    elif step in SETTLED:
        pool = SETTLED_REPLIES
    else:
        pool = REPORT_REPLIES
    from ..compose import fallback  # the one place a pool is chosen from, so it varies
    last = fallback.memory_bot(memory or {})
    return fallback._choose(pool, memory or {}, last)
