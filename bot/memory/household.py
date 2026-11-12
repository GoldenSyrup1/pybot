"""Who lives with the person: "its just me and my daughter", and the ask that follows it.

The store keeps the people a person names and the plans they make, but not the household itself,
so the two plainest lines about it had nowhere to land:

    i moved here in march
    its just me and my daughter
      -> "Tell them as soon as it is certain, and keep it concrete: which room is theirs..."

The line names a child and the word "just", and the only reading that fitted was the one for
telling a child about a move, so a person saying who they live with was told how to break the
news to their daughter. And the ask about it was answered by the store's place reader, which
looked for a town and found none:

    who lives with us
      -> "You haven't mentioned a place yet."

A friend answers both from what they have been told, and asks when they have not been told.

The household is filed on the chat's own memory as `memory["household"]`, so every module can see
it: {"people": ["daughter"], "alone": False} or {"people": [], "alone": True}. Only the shape
that says who is at home is read - "its just me and my daughter", "the two of us", "just me" -
because "i live with my mum" is also a place ("i live with my mum in leeds") and the store reads
that one.
"""
import re

from ..compose import pick
from . import counts

# The ask. "who lives with you", "who else lives there", "anyone else at home": the words that ask
# for the household and not for a place. Never a where-word on its own - that is the store's.
WHO_LIVES = re.compile(
    r"\bwho (?:else )?(?:lives|live|living|is living) (?:with (?:you|u|us|me)|there|here|at home)\b"
    r"|\bwho (?:do|does) (?:you|u) live with\b|\bwho am i living with\b"
    r"|\bwho (?:do|did) i live with\b"
    r"|\banyone (?:else )?(?:live|living|lives) (?:with (?:you|u|us|me)|there|here|at home)\b"
    r"|\banybody (?:else )?(?:live|living|lives) (?:with (?:you|u|us|me)|there|here)\b"
    r"|\bdoes anyone (?:else )?live with (?:you|u)\b"
    r"|\bwho(?:'s| is| s) (?:at home|there with you|living there)\b"
    r"|\bwho else is (?:at home|there)\b"
    r"|\bhow many of (?:you|us) (?:are|is) there\b", re.I)

# "its just me and my daughter", "me and my son", "just the two of us": the line says who is at
# home and nothing else. A person is named by the relation ("my daughter"), and the frame in front
# of it is what says this is the household rather than a visit or a plan.
JUST_ME_AND = re.compile(
    r"^(?:well |ok |okay |so |and )*(?:its |it's |it is )?(?:just |only )?"
    r"(?:me|us) (?:and|&) (?:my |our )?(?P<who>[a-z]+(?: [a-z]+)?)"
    r"(?: and (?:my |our )?(?P<more>[a-z]+(?: [a-z]+)?))?"
    r"(?: at home| living here| here)?$", re.I)
# The same without the person: "its just me", "just me here", "just the two of us".
JUST_ME = re.compile(
    r"^(?:well |ok |okay |so |and )*(?:its |it's |it is )?(?:just |only )?"
    r"(?:me|the two of us|the three of us|us)(?: at home| here| on my own)?$", re.I)
# Said about living alone, which is the same fact from the other side.
ON_MY_OWN = re.compile(
    r"\bi (?:live|am living|'m living|m living) (?:on my own|by myself|alone)\b"
    r"|\bi (?:live|'m|am) (?:on my own|by myself)\b|\bliving alone\b", re.I)

# What a relation said with "my" is called when it goes back to them: "your daughter".
THEIR = "{who}"

# The ask, answered from what they said.
WITH_SOMEONE = (
    "As far as you've told me, it's you and {who}.",
    "You and {who} \u2014 that's who you've mentioned.",
    "Just you and {who}, the way you told me.",
)
ALONE = (
    "On your own, you told me.",
    "Just you, then \u2014 I'm glad of the company.",
    "You live on your own, as far as I know.",
)
NOT_SAID = (
    "You haven't said who lives with you \u2014 who's there?",
    "I don't know that yet. Who do you live with?",
)

# The line that says who is at home, said back. It is worth one thing of its own, because the
# person has just told the bot something about their everyday life, and a receipt would be the
# second time they have said it to nobody.
THEIR_HOUSE = (
    "Just you and {who}, then \u2014 noted.",
    "You and {who}, then. What's an average evening like there?",
    "{Who} and you, then \u2014 that's the household.",
)


def _who_said(who):
    """The relation as it goes back to them: "daughter" -> "your daughter"."""
    said = " ".join(str(who or "").split()).strip().lower()
    if not said:
        return ""
    return "your " + said


def _held(memory):
    """The household the chat has been told about, or None."""
    held = memory.get("household") if isinstance(memory, dict) else None
    if not isinstance(held, dict):
        return None
    people = [person for person in held.get("people") or [] if isinstance(person, str) and person]
    if not people and not held.get("alone"):
        return None
    return {"people": people, "alone": bool(held.get("alone"))}


def observe(text, memory):
    """File who lives with them, and say nothing: the reply is this module's `respond`."""
    if not isinstance(text, str) or not isinstance(memory, dict):
        return
    said = " ".join(text.lower().split()).strip(" .!,")
    if not said:
        return
    if ON_MY_OWN.search(said):
        memory["household"] = {"people": [], "alone": True, "said": said}
        return
    found = JUST_ME_AND.match(said)
    if found:
        people = [_who_said(found.group("who"))]
        more = found.group("more")
        if more:
            # "me and my daughter and my son": two people, and a word that is already a name of
            # its own is not said twice.
            second = _who_said(more)
            if second and second not in people:
                people.append(second)
        # "me and my kids" is a household and not a relation the store can hold against one
        # person, so the words go in as they were said.
        memory["household"] = {"people": people, "alone": False, "said": said}
        return
    if JUST_ME.match(said):
        memory["household"] = {"people": [], "alone": True, "said": said}


def answer(text, memory):
    """The ask, or the household said back and nothing else, or None."""
    if not isinstance(text, str) or not isinstance(memory, dict):
        return None
    said = " ".join(text.lower().split()).strip(" .!,")
    if not said:
        return None
    if WHO_LIVES.search(said):
        held = _held(memory)
        if held is None:
            # "You haven't said who lives with you" is only honest when the store has nothing that
            # answers the ask. A chat that gave a headcount holds one, and the count reader says it
            # back ("theres 10 of us" / "how many of us are there" was answered "You haven't said
            # who lives with you - who's there?" while memory held ten). This module owns the
            # household, not every number the chat has been told, so it stands down and lets the
            # store's own reader answer.
            if counts.answer(said, memory):
                return None
            return pick(NOT_SAID, memory, seed_text=text)
        if held["alone"]:
            return pick(ALONE, memory, seed_text=text)
        people = held["people"]
        if len(people) == 1:
            who = people[0]
        elif len(people) == 2:
            who = people[0] + " and " + people[1]
        else:
            who = ", ".join(people[:-1]) + " and " + people[-1]
        return pick(WITH_SOMEONE, memory, seed_text=text).format(who=who)
    found = JUST_ME_AND.match(said) or JUST_ME.match(said)
    if found and not (found.groupdict().get("who") or ""):
        return None
    if found:
        who = _who_said(found.groupdict().get("who"))
        if not who:
            return None
        return pick(THEIR_HOUSE, memory, seed_text=text).format(
            who=who, Who=who[:1].upper() + who[1:])
    # "i live on my own" is filed (ON_MY_OWN above) and left to the module that answers it: it is
    # a line about being lonely as much as a line about who is at home, and the advice it gets on
    # main is worth more than a receipt. The ask below is this module's to answer.
    return None


def takes_as_it_comes(text, memory):
    """This line, because the household is the whole of it."""
    if not isinstance(text, str):
        return False
    said = " ".join(text.lower().split()).strip(" .!,")
    if WHO_LIVES.search(said):
        # Same rule as `answer`: a line the count reader can answer is not answered here, so the
        # arbiter does not hand it to a module that would deny the number.
        return not counts.answer(said, memory)
    found = JUST_ME_AND.match(said) or JUST_ME.match(said)
    return bool(found) and bool(found.groupdict().get("who"))
