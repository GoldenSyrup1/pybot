"""A trip already on record, said again with the month they now mean.

    im going to spain in june
    actually we fly in september        ->  Got it - you're going to Spain in September.
    when do we fly                      ->  In September.

The line names how they travel rather than the date alone, so the words are unremarkable - a
trip being told sounds the same. Only the store can tell the two apart, because a date is a
correction just when there is a trip for it to move: with no plan on record the same line is a
trip being told, and a birthday, a dentist appointment or a fear of flying in the same chat is
not the trip the line is about.

The store's own reader cannot be extended for it (its file is at the world's size limit), so the
date is read here, by bot/memory/facts.py, and handed to the store's correction path - which owns
the plan, the acknowledgement and the fact log. This module only decides that the line is a
correction of the trip on record.
"""

from ..memory import facts as extract
from ..memory import trips
from . import memory_store

# Below the store (7000) so this sees what its observer has already kept from the line, and above
# the reply modules so the correction is in memory before anything answers.
PRIORITY = 6900


def _the_trip_it_moves(memory):
    """The plan the date is about, or None when there is no trip for it to move.

    A birthday or an appointment can be the newest plan in the store, so the trip on record has
    to be the plan in hand as well: its own words have to be the ones the chat has up front.
    """
    plan = memory_store._stated_plan(memory) or memory_store.user(memory).get("plan")
    if not isinstance(plan, str) or not plan.strip():
        return None
    trip = trips._the_trip_so_far(memory)
    if not trip:
        return None
    on_record = " ".join(str(trip.get("plan") or "").lower().split())
    if on_record and on_record != " ".join(plan.lower().split()):
        return None
    return plan


def _the_month_taken_back(memory):
    """The month the trip on record says, when the store keeps a plan that says it.

    The store's correction path reads a date before it reads a plan, and a birthday in the same
    chat is a date of its own, so a bare month would be moved in the birthday and not in the
    trip. Naming the month the trip says puts the reader on the plan that says it - and when no
    plan says it, nothing is moved rather than the wrong date.
    """
    trip = trips._the_trip_so_far(memory) or {}
    month = " ".join(str(trip.get("month") or "").lower().split())
    if not month:
        return None
    for said in memory_store.user(memory).get("plans") or []:
        if month in " ".join(str(said or "").lower().split()):
            return month
    return None


def _a_dated_fact_beside_it(memory):
    """Whether someone else's dated fact - a birthday, an appointment - is in the store.

    Such a fact is a date of its own, and the store reads a date before it reads a plan, so a bare
    month can be moved in the birthday rather than in the trip. Only then does the month have to
    be named.
    """
    for other in memory.get("others") or []:
        if not isinstance(other, dict):
            continue
        if any(other.get(key) for key in ("birthday", "appointment", "when", "date")):
            return True
    return False


def observe(text, memory):
    if not isinstance(memory, dict):
        return
    moved = extract.a_trip_date_put_right(text)
    if not moved:
        return
    if not _the_trip_it_moves(memory):
        return
    taken_back = _the_month_taken_back(memory) if _a_dated_fact_beside_it(memory) else None
    memory_store._apply_correction(memory, {"to": moved, "from": taken_back}, text)
