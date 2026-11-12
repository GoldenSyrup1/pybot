"""The two kinds of question whose answer is nowhere in this bot, said where the answer lives.

What a pass, a warranty or a policy covers, and what somebody else's rules allow, cannot be
answered from here: the small print and the rules are theirs, and a guess would be worse than
none. `bot/compose/routes.py` reads those two kinds and names the one place that holds the answer -
the terms page, the insurer, the operator, the council, Citizens Advice or ACAS.

This module sits just above greeting's honest hedge ("a search should sort you out quickly") and
below every light remark and every card, so it only ever speaks where the bot would otherwise have
told the person to go and search. It asks the composer first and stands down unless the answer
really is a hedge, so a reader in `bot/compose/fallback.py` that has found the right body to ask
(the landlord, the union, the school office) keeps its turn even though this module outranks
greeting.

Nothing here holds a fact about the world, so nothing here can be wrong or go stale, and
`routes.py` stands down on a statement, on a lid rather than a policy, on a child's own permission
and on any line a card answers.
"""
import re

from ..compose import fallback, routes

# The composer's hedge comes in several shapes, and `fallback._is_a_hedge` knows most of them. A
# second family reaches the person in the same clothes without being on that list: the reply that
# offers a search, or a phone call, instead of an answer ("a call beats searching", "the quickest
# route to a straight answer"). Those are placeholders by this lane's definition too, so the
# reading is made here as well: a new hedge wording cannot leave somebody with "go and search"
# while this module stands down and says nothing.
SEARCH_ONLY = re.compile(
    r"\b(?:beats searching|a search (?:should|will)|quick search|searching for it will|"
    r"quickest route to a straight answer|would rather not guess|beyond what i know|"
    r"not sure about that one)\b", re.I)

PRIORITY = -999  # above greeting (-1000), below nudge (-950), urgent, invitation and every card


def respond(text, memory):
    """Name the place, or say nothing and let the composer answer as it did."""
    understood = memory.get("understood") or {}
    clean = fallback._matchable(fallback._plain(understood.get("clean") or text))
    route = routes.options(clean)
    if not route:
        return None
    said = fallback.reply_for(text, memory)
    if not (fallback._is_a_hedge(said) or SEARCH_ONLY.search(said or "")):
        return None  # the composer has an answer of its own; it keeps the turn
    return fallback._choose(route, memory, fallback._matchable(text))
