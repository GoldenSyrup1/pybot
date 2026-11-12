"""A yes/no about a figure the bot itself gave: "so is eight weeks still right".

The bot had said "Three runs a week gets most people to 5k in about eight weeks", and then the
person asked whether the eight weeks stood. Nothing in the line names a thing of its own - the
thing it is about is the figure in the bot's own answer - so the knowledge base read the words it
could see and answered from a different entry altogether:

    i want to run 5k
      Three runs a week gets most people to 5k in about eight weeks ...
    how long will it take
      Eight weeks.
    im 52 and a bit overweight
      Got it. Is there anything you'd like a hand with?
    so is eight weeks still right
      Ask in writing and name what you want: a refund, a repair, or money for the trouble. (a
      consumer-complaint entry, reached by the words "eight weeks")

The figure is the answer's, and the question is whether it still stands, so the answer is the
figure with the reason the chat already gave for it: "Still right: Three runs a week gets most
people to 5k in about eight weeks." That is also how a friend answers it - they do not go and
look something up, they say where the number came from.

Narrow on purpose:

* the line has to ask (a question mark, or "is/are/does/will" at the front, or "still"/"right");
* the line has to carry a figure - a number and, where it has one, the unit the answer gave it;
* every other word in the line has to be one that names nothing ("so is eight weeks still
  right"), because "is eight weeks right for a puppy" is a question about a puppy;
* the figure has to be in an earlier answer of this chat, and that answer has to say what the
  figure rests on, or there is nothing to hand back;
* a line that takes issue with the answer ("that cant be right") is `bot/memory/doubt.py`'s, and
  a line that is `not` something is a different question, so both are left alone here.
"""
import re

from ..compose import pick

# The units an everyday answer gives a figure with. A unit is compared with its plural folded, so
# "eight weeks" in the answer matches "eight week" in the line.
UNITS = frozenset("""week month day year hour minute second mile km kilo stone pound percent
    session run portion time glass cup litre pint degree inch cm metre gram ml""".split())

# The numbers people write as words. Past twenty the tens are enough: nobody asks whether
# "seventy three weeks" still stands.
NUMBERS = {word: value for value, word in enumerate(
    "zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen "
    "fifteen sixteen seventeen eighteen nineteen twenty thirty forty fifty sixty seventy eighty "
    "ninety hundred".split())}
NUMBERS["couple"] = 2
NUMBERS["few"] = 3
# How often something is done, which is how people say a figure with no digits at all: "is once a
# week right" after "Change the sheets once a week".
NUMBERS["once"] = 1
NUMBERS["twice"] = 2
NUMBERS["thrice"] = 3

# A figure: a digit run or a number word, and the unit right after it when the line gives one.
FIGURE = re.compile(
    r"\b(\d[\d,]*(?:\.\d+)?|" + "|".join(sorted(NUMBERS, key=len, reverse=True)) + r")"
    r"(?:\s+(" + "|".join(sorted(UNITS, key=len, reverse=True)) + r")s?\b)?", re.I)

# A word that names nothing of its own, so a line of these plus a figure is a line about the
# figure. "not", "wrong" and "sure" are left out on purpose: they take issue with the answer, and
# `bot/memory/doubt.py` owns that reading.
NOTHING_NAMED = frozenset("""so and but or then ok okay right still is are was were am that
    this it they those these the a an of in on at for to do does did will would can could should
    my i me you we our yeah yes no anymore any more both quite really actually true correct
    stand stands work works hold holds apply applies changed change mean means all that's its
    it's again now today currently nowadays even just also too much very bit little""".split())

# The line has to ask. A question mark is one way; the others are the openers and the words that
# only make sense as a question about a figure ("is eight weeks right", "are five a day still ok").
QUESTION_OPENING = re.compile(
    r"^\W*(?:(?:so|and|but|ok|okay|then|right|oh|also|now)\W+)*"
    r"(?:is|are|was|were|does|do|did|will|would|should|can|could)\b", re.I)
ASKING = re.compile(r"\b(?:still|right|correct|true|ok|okay|the same|sure)\b|\?", re.I)

# A line longer than this is carrying something of its own, however much of it reads as filler.
MOST_WORDS = 9

# The answer the chat already gave, and how far back to look for the sentence that says what the
# figure rests on. A figure is often given bare first ("Eight weeks.") and explained a turn or two
# before that, which is where the reason is.
LOOK_BACK = 5
# A sentence this short is the figure on its own and says nothing about why.
SHORTEST_REASON = 6
MOST_REASON_WORDS = 45

SENTENCE = re.compile(r"(?<=[.!?])\s+")

# The figure with the reason the chat gave for it. The reason is the bot's own sentence, because
# the reason is a fact about the world and the bot has already said which one it used.
STANDS = (
    "Still right: {reason}",
    "That has not changed: {reason}",
    "Yes - and that is where it comes from: {reason}",
)

# The same when the chat never said what the figure rests on: the figure is all the answer there
# is, and saying it back is the honest reply rather than a card about something else.
CONFIRMS = (
    "Still right - {figure}.",
    "Yes, {figure} is still the number.",
    "That holds: {figure}, as before.",
)


def _number(word):
    word = str(word or "").strip(".,").lower()
    if not word:
        return None
    if word.replace(",", "").replace(".", "").isdigit():
        return float(word.replace(",", ""))
    return float(NUMBERS[word]) if word in NUMBERS else None


def _figures(text):
    """[(value, unit or "", where it starts, where it ends)] for the figures in a line."""
    found = []
    for match in FIGURE.finditer(str(text or "")):
        value = _number(match.group(1))
        if value is None:
            continue
        unit = (match.group(2) or "").lower().rstrip("s")
        found.append((value, unit, match.start(), match.end()))
    return found


def _names_the_figure(text, value, unit):
    """True when this text gives the same figure, with the same unit where the line names one.

    A line that says "nine hours" is not answered by an answer's bare "9" ("9 to 10 for hard
    boiled"): the unit is what a figure means, and matching the number alone would confirm a
    length the chat never gave.
    """
    for other, other_unit, _, _ in _figures(text):
        if other != value:
            continue
        if unit and unit != other_unit:
            continue
        return True
    return False


def _the_line_asks_about_a_figure_and_elsewhere_nothing(text):
    """The (value, unit) the line asks about, or None when it names something of its own."""
    line = " ".join(str(text or "").lower().replace("\u2019", "'").split())
    if not line or len(line.split()) > MOST_WORDS:
        return None
    if not (QUESTION_OPENING.search(line) or ASKING.search(line)) or not ASKING.search(line):
        return None
    figures = _figures(line)
    if len(figures) != 1:
        # No figure is not this reader's, and two are a comparison ("is eight weeks or twelve
        # closer") rather than a check of the one the answer gave.
        return None
    value, unit, start, end = figures[0]
    rest = (line[:start] + " " + line[end:]).split()
    for word in rest:
        word = word.strip(".,!?;:")
        if word in NOTHING_NAMED or word.rstrip("s") in UNITS or word in ("a", "an", "per",
                                                                          "each", "every"):
            continue
        # A word that names something of its own is the line's subject, and the figure is then a
        # detail of it rather than the thing asked about.
        if word.rstrip("'s") in NOTHING_NAMED:
            continue
        return None
    return value, unit, line[start:end].strip()


def _the_chat_gave_it(memory, value, unit):
    """True when one of the bot's own recent answers gives this figure with this unit."""
    if not isinstance(memory, dict):
        return False
    turns = memory.get("turns")
    if not isinstance(turns, list):
        return False
    return any(_names_the_figure(str(turn.get("bot") or ""), value, unit)
               for turn in turns[-LOOK_BACK:] if isinstance(turn, dict))


def _the_reason_behind(memory, value, unit):
    """The bot's own sentence that gives this figure and says what it rests on, or ""."""
    if not isinstance(memory, dict):
        return ""
    turns = memory.get("turns")
    if not isinstance(turns, list):
        return ""
    for turn in reversed(turns[-LOOK_BACK:]):
        said = str(turn.get("bot") or "") if isinstance(turn, dict) else ""
        if not said or not _names_the_figure(said, value, unit):
            continue
        # The first sentence that carries the figure and enough words to be a reason: the answer
        # leads with the figure and what it rests on, and a sentence later in the paragraph is
        # usually about something else that happens to hold the same number ("the health
        # guideline is 150 minutes ... which is three 50-minute sessions").
        for sentence in SENTENCE.split(said):
            sentence = sentence.strip()
            words = sentence.split()
            if not (SHORTEST_REASON <= len(words) <= MOST_REASON_WORDS):
                continue
            if _names_the_figure(sentence, value, unit):
                return sentence
    return ""


def the_figure_asked_about(text, memory):
    """(value, unit, phrase, reason) when the line asks whether a figure of the chat stands.

    `reason` is "" when the chat gave the figure and never said what it rests on: the answer is
    then the figure itself, said back as the thing that has not changed.
    """
    asked = _the_line_asks_about_a_figure_and_elsewhere_nothing(text)
    if not asked:
        return None
    value, unit, phrase = asked
    if not _the_chat_gave_it(memory, value, unit):
        # The figure is not the chat's: "is nine hours right" after an egg answer is a new
        # question about the world, and the answer to it is not "that holds".
        return None
    return value, unit, phrase, _the_reason_behind(memory, value, unit)


def reply_for(text, memory):
    """The reply to a yes/no about a figure the bot gave, or None for every other line."""
    found = the_figure_asked_about(text, memory)
    if not found:
        return None
    _, _, phrase, reason = found
    line = " ".join(str(text or "").lower().split())
    if not reason:
        return pick(CONFIRMS, memory, line).format(figure=phrase)
    return pick(STANDS, memory, line).format(reason=reason)

