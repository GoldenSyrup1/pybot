"""The chat-speak people hang off the end of a line, and the line without it.

It is not part of what they told you: the fact is "my sister is called meg", and "you said your
sister is called meg to be honest" says the fact back with a shrug on it. The reply that notes a
line, the summary that quotes it, and the plan the store keeps all read this, so the words that
are only a shrug are dropped in one place rather than three.
"""

# Only pure filler is here, so "as well" ("my knee is bad as well") and "right" stay where the
# person put them.
TAIL_OFF = frozenset("""tho though lol lmao haha ha hehe tbh ngl imo idk innit x xx xxx
    actually""".split())

# The same shrugs, put in the middle of the line rather than on the end: "what can I actually do
# to help her", "is it really that expensive". They are not part of what is asked either, and a
# reader that has to see the question under them - the follow-up read with the topic put back in
# - was reading the shrug as one more word of the subject and reaching nothing.
IN_THE_WAY = frozenset("actually really honestly literally genuinely basically".split())


def without_filler(said):
    """`said` without the chat-speak hanging off the end: "im veggie tho" -> "im veggie"."""
    words = str(said or "").split()
    while len(words) > 1 and words[-1].lower().strip(".,;:!?") in TAIL_OFF:
        words.pop()
    return " ".join(words)


def without_the_shrug(said):
    """`said` without the fillers in the middle of it: "what can i actually do" -> "what can i do".

    One word is always left, so a line that was nothing but a shrug comes back as it was.
    """
    words = str(said or "").split()
    kept = [word for word in words if word.lower().strip(".,;:!?") not in IN_THE_WAY]
    return " ".join(kept) if kept else " ".join(words)
