"""Runs the understanding engine (bot/understanding) before any module proposes a reply."""
from ..memory import the_thing_it_is
from ..understanding import understand

PRIORITY = 10000  # observes first, so every other module reads memory["understood"]


def observe(text, memory):
    read = understand(text, memory)
    # A pronoun in a short ask stands for a thing the store already holds: "how often should I
    # walk it" straight after "I have a dog" is the dog entry, and the reading is where every
    # module looks first ("what should I feed it" reached nothing and fell to a search hedge
    # with the cat food one entry away). Only the reading changes: the line as typed is what
    # every fact and every quote is kept from.
    filled = the_thing_it_is(read, memory)
    memory["understood"] = filled if filled is not None else read
