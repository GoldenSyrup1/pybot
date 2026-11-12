"""The kit for a small plan: a picnic, a gym bag, a spa day, an interview, a barbecue.

"What do i need for a picnic", "what should i take to a barbecue" and the like are the commonest
of the everyday kit questions, and 42 of the 103 deck turns that ask what somebody needs for a
thing were answered with a shrug (answers, #answers 16). Each row is keyed by the plan and asks
for a need word, so "how do i cook on a barbecue" keeps its own answer.
"""
from .lookup import entry

# The plans are days out, a workout, a booking and a job: the topics the base already covers.
ANSWERS = ("food-and-drink", "fitness", "work")

# The kit question, not the plan: "why is a picnic nice" and "how do i join a gym" are not this.
# "wear" is not here on purpose: "what should i wear to an interview" is the dress question.
# "get", "buy" and "first" are not here: "i didn't get the job i interviewed for" holds two of
# them, and it is not asking for the kit (deck row `multi-025`).
_NEEDS = ("need", "needs", "needed", "bring", "brings", "take", "takes", "pack", "packing",
          "kit", "list", "prepare", "prep", "essentials", "supplies")


def _asks_for_the_kit(understood):
    """True when the line is asking what to have with them."""
    words = set((understood or {}).get("words") or ())
    return any(word in words for word in _NEEDS)


ENTRIES = [
    entry("a-picnic-kit",
          (("picnic", "picnics"), _NEEDS),
          ("A rug, a cool bag with a freezer block, plates and cups you do not mind losing, a "
           "bottle opener, napkins, a bin bag and water. Skip anything heavy with mayonnaise "
           "unless it is eaten within the hour: sausage rolls, cheese, fruit and a flask keep for "
           "hours."),
          ask=_NEEDS, guard=_asks_for_the_kit,
          # a picnic somebody eats is the food row's question ("whats a good picnic to take for a
          # day out", deck row `multi-9021`), and so is a blanket or a table
          avoid=("table", "bench", "site", "recipe", "cake", "bread", "sandwich", "blanket",
                 "basket", "hamper", "good", "best", "nice", "ideas", "food", "eat", "something",
                 "lunch", "snack")),
    entry("a-gym-bag-kit",
          (("gym", "gyms", "workout", "workouts"), _NEEDS),
          ("For the gym: trainers you only wear indoors, two towels (one for the floor and "
           "machines), a water bottle, a padlock for the locker, deodorant and a bag for wet kit. "
           "A resistance band and a notebook beat anything else a shop will sell you."),
          ask=_NEEDS, guard=_asks_for_the_kit,
          avoid=("join", "membership", "contract", "cancel", "price", "cost", "cheap", "app")),
    entry("a-spa-day-kit",
          (("spa", "spas"), _NEEDS),
          ("Swimwear, flip-flops, a towel and robe if the place does not lend them, a hair tie, "
           "a bottle of water, and your own shampoo if you are fussy. Leave the phone in the "
           "locker: the pools and steam rooms dehydrate you faster than people expect."),
          ask=_NEEDS, guard=_asks_for_the_kit,
          avoid=("price", "cost", "cheap", "voucher", "book", "booking", "cancel")),
    entry("an-interview-kit",
          (("interview", "interviews"), _NEEDS),
          ("Take the letter or email with the address and time, a printed copy of your CV, a pen "
           "and a notepad, and the name of the person you are meeting. Photo ID for the building, "
           "and ask at the desk for them by name."),
          ask=_NEEDS, guard=_asks_for_the_kit,
          avoid=("questions", "answers", "nervous", "nerves", "salary", "job offer",
                 "thank you letter")),
    entry("a-barbecue-kit",
          (("barbecue", "bbq", "barbeque", "cookout"), _NEEDS),
          ("Charcoal (about 1kg for ten people), a chimney starter and firelighters, long tongs, "
           "a wire brush, a tray for the cooked meat, and a meat thermometer. Put a bucket of "
           "water or sand beside it; a gas one needs a spare bottle instead."),
          ask=_NEEDS, guard=_asks_for_the_kit,
          avoid=("sauce", "marinade", "rub", "recipe", "how long", "temperature", "weather")),
]
