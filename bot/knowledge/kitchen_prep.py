"""Kitchen prep: the small things you do to a piece of meat before it goes in the pan.

The answers lane owns this domain. It exists because "room temperature" is two questions: how warm
a bedroom should be, and what to do with a steak before cooking it. Neither cooking's tables nor
sleep's could hold the kitchen half without moving the rarity of a word a dozen other lines are
weighed against - "should I rest a steak" went to a different answer the moment it did - so the
prep rows live in a table of their own, keyed by the cut and the instruction.
"""

from .lookup import entry

ANSWERS = ("cooking", "food-and-drink")

ENTRIES = [
    # "Room temperature" is an instruction in a kitchen, not a bedroom reading. The egg line is
    # already the eggs row's; a steak on the counter is this one, and it was answered with the
    # temperature a bedroom should be.
    # The subject is the meat, not the steak: "should i let chicken come to room temperature" is
    # the same instruction and was reaching the bedroom card, because the sleep stand-down took it
    # off the keeping row and only the cut named here could answer it. Chicken, pork and a joint
    # are cooked the same way - dry it, season it, put it in a hot pan - so the row speaks for all
    # of them and says so in its first sentence.
    entry("meat-room-temperature", (("steak", "steaks", "chicken", "chicken breast", "turkey",
                                    "pork", "lamb", "beef", "fish", "meat", "the meat",
                                    "chops", "sausages"),
                                    ("room temperature", "out of the fridge", "rest out",
                                     "twenty minutes", "an hour before", "come to room",
                                     "warm up before", "before cooking", "before it goes in")),
          "It barely matters: twenty minutes on the counter warms the meat by a couple of degrees "
          "inside, so the middle still cooks the same. Leaving raw meat out for hours is a food "
          "safety risk. What does make a difference is patting it dry and seasoning it just before "
          "it goes in the pan - a dry surface browns, a wet one steams.",
          avoid=("keep", "keeps", "keeping", "how long", "left out", "overnight", "gone off",
                 "still good", "defrost", "thaw", "freeze", "frozen", "wash", "washing",
                 "rinse", "safe", "food poisoning", "pink", "raw in the middle",
                 "is it cooked", "cooked through", "cooked to", "done", "how do i know",
                 "what temperature", "how hot", "oven", "rest a joint", "resting",
                 # a sausage pricked or splitting is the prick-sausages row's question, and
                 # "before cooking" alone was enough to hand it this one instead
                 "prick", "pricking", "pricked", "pierce", "pierced", "split", "splits",
                 "burst", "bursts", "skin", "skins"),
          bias=1),
]
