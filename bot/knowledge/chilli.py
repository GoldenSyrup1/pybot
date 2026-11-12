"""Chillies as a vegetable: what to do with a glut, how hot the thing is, and what stands in.

The answers lane owns this domain. A chilli is a dish as well as a vegetable, and the dish
answers every way of asking for the recipe, so these are the questions the recipe is the wrong
answer to: keeping a box of them, freezing them, drying them, chopping them, how hot one is and
what to use when there are none. Each row is keyed by the chilli names plus the words that name
the job or the property, so "how hot is a jalapeno" and "how spicy is a chilli" reach the same
answer without either of them naming a chilli variety.
"""
import re

from .lookup import entry

ANSWERS = ("cooking", "food-and-drink")

# A dish made with chillies is the recipe's question, not the vegetable's, and it is named in
# one of these words rather than by the chilli. Every row below carries them: "can i freeze
# chilli con carne" was answered by the box-in-the-fridge-drawer row.
DISH = ("con carne", "con carni", "bolognese", "chilli beef", "stew", "recipe", "dish",
        "saucepan", "in a curry")
# A pot of it is the other thing again: "how long is a pot of chilli good for" was answered by the
# box-in-the-drawer card, and "can i freeze leftover chilli" with "freeze them whole in a bag and
# slice them still frozen", which is nonsense for a stew. These words name the cooked dish, so
# the cooked-dish row below answers instead. "leftover" is not here: it is a key word above.
COOKED = (" pot ", "pot of", "a pot", "batch", "cooked", "already made", "made it")
# The verbs that name a pan. A chilli in a pan is the dish, and the keeping row is about a box in
# the drawer: "how long should i simmer a chilli for" got the box.
HEAT_WORDS = ("simmer", "simmering", "simmered", "cook", "cooking", "boil", "boiling", "fry",
              "frying", "fried", "roast", "roasting", "roasted", "bake", "baking", "baked",
              "oven", "hob", "pan", "minutes", "stir fry", "grill", "steam")


# A dish on a takeaway menu is asked about by its heat far more often than about how to make it:
# "how spicy is a korma", "how hot is a jalfrezi", "which curry is mildest". The kitchens have an
# order they all roughly keep, so it is one table read weakest first, and the answer is the dish's
# place on it. "hot" is a weather word to the forecast card, which is what "how hot is a jalfrezi"
# got, so the row carries a point of bias and both answers name a dish.
CURRY_HEAT = (
    (("korma", "pasanda", "butter chicken", "makhani"),
     "mildest on the menu, creamy and with no chilli heat at all"),
    (("tikka masala", "tikka", "masala"),
     "mild, a tomato and cream sauce with a little warmth"),
    (("rogan josh", "dhansak", "balti"),
     "medium, warming rather than burning"),
    (("madras",),
     "the first properly hot one on most menus, hot without being punishing"),
    (("jalfrezi",),
     "hot, with green chillies and peppers left in"),
    (("vindaloo",),
     "very hot, and hotter in some kitchens than others"),
    (("phal", "naga", "tindaloo"),
     "the hottest thing on the menu, and past the point where most people taste anything else"),
)

# What the line calls the dish, so the reply can name it back: a person who typed "jalfrezi" is
# asking about a jalfrezi, and "the dish" reads as a shrug.
CURRY_NAMES = {name: name for names, _ in CURRY_HEAT for name in names}

# The order as one sentence, for the line that asks which is mildest rather than about one dish.
CURRY_ORDER_LINE = "korma, pasanda, butter chicken, tikka masala, rogan josh, balti, dhansak, madras, jalfrezi, vindaloo, phaal"

_HEAT_WORDS = ("spicy", "spice", "spicier", "hot", "hotter", "hottest", "mild", "milder",
               "mildest", "heat", "strength", "how strong", "scoville", "burn", "burning",
               "too spicy", "too hot", "which is mildest", "least spicy")


# A dish in front of the person that is too hot to eat is the rescue question, not the menu's
# scale: "my curry is way too spicy, what can i do" was answered with the korma-to-phal order,
# when cooking.py's chilli-heat card has the answer and its own words ("too hot", "too spicy")
# score the same here. A fault in the food is not a place on the menu, so the fault stands this
# row down and the rescue card answers. The menu's own questions - "how hot is a jalfrezi",
# "which curry is mildest", "how spicy is a korma" - name no fault and keep their answer.
_A_FAULT_IN_THE_DISH = (
    "too spicy", "too hot to eat", "too hot for me", "too hot for the kids", "way too hot",
    "way too spicy", "far too spicy", "far too hot", "cool it down", "cool the heat",
    "cool this down", "make it milder", "make it less spicy", "less spicy", "not so spicy",
    "too much chilli", "too much chili", "blow your head off", "burning my mouth",
)


def _curry_heat(memory, understood):
    """The dish's place on the menu's scale, or the whole order when the line names no dish."""
    words = [str(word).lower() for word in (understood.get("words") or [])]
    said = " ".join(words)
    flat = " " + str(understood.get("clean") or understood.get("text") or "").lower() + " "
    flat = re.sub(r"[^a-z0-9' ]+", " ", flat)
    if any(phrase in flat for phrase in _A_FAULT_IN_THE_DISH):
        return None
    for index, (names, place) in enumerate(CURRY_HEAT):
        for name in names:
            if name in said:
                return ("A %s is %s. Mildest to hottest the usual menu runs %s, so ask for it mild "
                        "and the kitchen leaves the chilli out - and if you want heat with flavour, "
                        "step one up the list rather than two."
                        % (name, place, CURRY_ORDER_LINE))
    return ("Mildest to hottest the usual takeaway menu runs %s. A korma or pasanda has no chilli "
            "heat at all, a tikka masala is mild, and a jalfrezi and up are the hot end; ask for "
            "any of them mild and the kitchen makes it without the chilli."
            % CURRY_ORDER_LINE)


ENTRIES = (
    # "how do i use up chillies", "how do i store chillies" and "how long do chillies last" were
    # answered by the chilli con carne method, and "how do i keep chillies fresh" by a keeping row
    # about something else: a dish and a vegetable are one word.
    entry("chilli-keep",
          (("chilli", "chillies", "chilli pepper", "jalapeno", "jalapenos", "habanero",
            "scotch bonnet"),
           ("use up", "keep", "keeping", "store", "storage", "how long", "last", "left over",
            "leftover", "glut", "plenty of")),
          "Loose in the fridge drawer they keep a week or two, and longer in a paper bag than in "
          "plastic: the bag holds the moisture that turns them soft. A glut is better frozen or "
          "dried than left to go wrinkly - both keep the heat - and a handful also becomes chilli "
          "oil, which is the fastest way to use up twenty at once.",
          # "my chilli is too dry" is a fault in the dish, not a question about keeping them:
          # the state word is what tells the two apart. Freezing and drying have their own rows,
          # because each is asked on its own and the first sentence has to be about that.
          # A pan of them is the cooking question, not the drawer: "how long should i simmer a
          # chilli for" was answered with "loose in the fridge drawer they keep a week or two",
          # because "how long" is a keeping word and the row had no heat verb to stand it down.
          avoid=DISH + HEAT_WORDS + ("too spicy", "too hot", "less spicy", "too dry", "is dry",
                                     "tastes dry",
                        "came out dry", "too wet", "plant", "grow", "growing", "sow", "seedling",
                        "powder", "flakes", "paste", "freeze", "frozen", "drying", "dry them",
                        "instead of", "substitute", "swap", "replace", "oil") + COOKED,
          bias=1),
    # A pot of it is a cooked dish with its own keeping answer: "how long is a pot of chilli good
    # for" reached the box-in-the-drawer card, and with that card stood down it reached the
    # recipe's "about 40 minutes start to finish". The dish words are asked for, so a line naming
    # chillies on their own still gets the vegetable.
    entry("chilli-pot-keep",
          (("chilli", "chillies", "chilli con carne", "chilli beef"),
           ("keep", "keeps", "keeping", "good for", "last", "lasts", "how long", "store",
            "fridge", "freezer", "freeze", "leftover", "left over")),
          "A pot of chilli keeps 3 days in the fridge, in a sealed box, once it has cooled within "
          "two hours of cooking; it freezes for 3 months and it is better the next day anyway. "
          "Reheat it once, until it is piping hot right through, and don't leave it out on the "
          "hob overnight.",
          ask=(" pot ", "pot of", "a pot", "batch", "cooked", "made", "leftover", "left over",
               "con carne"),
          # "chilli con carne" has its own keeping row, which says the same thing in one line.
          avoid=("plant", "grow", "growing", "seedling", "sow", "powder", "flakes", "paste",
                 "how hot", "too spicy", "too dry", "instead of", "con carne", "con carni"),
          # cooking.py's cooked-mince row carries "chilli" too and asks for "leftover", so a
          # leftover chilli keeps the mince answer, which is the same clock and the same box.
          bias=1),
    # the dish's heat is its own question, and it is the one a menu line asks
    entry("curry-heat",
          (("korma", "pasanda", "butter chicken", "tikka masala", "tikka", "rogan josh", "dhansak",
            "balti", "madras", "jalfrezi", "vindaloo", "phal", "naga", "tindaloo", "curry",
            "curries"),
           _HEAT_WORDS),
          _curry_heat,
          # the recipe, the calories, the drink and the heartburn have their own cards
          avoid=("recipe", "how do i make", "how to make", "calories", "sugar", "healthy",
                 "wine", "beer", "drink", "side", "sides", "goes with", "naan", "rice",
                 "hangover", "heartburn", "reflux", "indigestion", "stomach", "baby", "toddler",
                 "child", "kids", "plant", "grow", "seedling", "powder", "flakes", "paste"),
          # "how hot is a jalfrezi" was answered with the week's weather
          bias=1),
    # "can i freeze fresh chillies" was answered by the storage row, whose second sentence is
    # about freezing: the answer has to start with the thing that was asked.
    entry("chilli-freeze",
          (("chilli", "chillies", "chilli pepper", "jalapeno", "jalapenos", "habanero",
            "scotch bonnet"),
           ("freeze", "frozen", "freezing", "bag up", "ice cube")),
          "Freeze them whole in a bag and slice them still frozen: they go soft, so they are for "
          "cooking rather than for a salad, but the heat survives a few months. Chopped into an "
          "ice-cube tray with a little oil is the other way, one cube per curry, and there is no "
          "need to blanch them first.",
          avoid=DISH + ("too spicy", "too hot", "too dry", "is dry", "plant", "grow", "growing",
                        # not "freezer": word forms fold it onto "freeze", this row's own key
                        "sow", "not working", "broken", "instead of", "oil") + COOKED,
          # cooking.py's freeze-cooked row carries the bare word "chilli", so it scores the same
          # on this line: the nudge decides it, and freeze-cooked keeps every cooked dish
          bias=1),
    # the same for drying: "how do i dry chillies" was answered by the fridge drawer.
    entry("chilli-dry",
          (("chilli", "chillies", "chilli pepper", "jalapeno", "jalapenos", "habanero",
            "scotch bonnet"),
           ("dry", "dried", "drying", "dehydrate", "dehydrator", "dry them out")),
          "Thread them on cotton and hang the string by a sunny window until they are leathery "
          "and rattle when you shake one, which takes two to three weeks in a warm room, or split "
          "them and dry them in a low oven at 60C with the door ajar for six to eight hours. Dry "
          "them whole and they keep a year in a jar; grind them for flakes once they are crisp.",
          avoid=DISH + ("too spicy", "too hot", "too dry", "is dry", "tastes dry", "came out dry",
                        "too wet", "plant", "grow", "growing", "sow", "tumble dryer",
                        "washing", "instead of", "oil"),
          # the "too dry" fault row and the dry-dish advice score on "dry" as readily as this
          # one does, and the chilli names say which is meant
          bias=1),
    # "how hot is a jalapeno" was answered by the weather fallback and "how do i chop a chilli"
    # by the chilli con carne method. The seed question has its own row in cooking.py; this one is
    # the vegetable's heat and knife work, and the variety names are what tell it from a dish.
    entry("chilli-vegetable",
          (("chilli", "chillies", "chilli pepper", "jalapeno", "jalapenos", "habanero",
            "scotch bonnet", "birds eye", "bird's eye"),
           ("chop", "chopped", "slice", "prepare", "prep", "how hot", "hot", "heat", "spicy",
            "strength", "how strong")),
          "Heat is in the variety before it is in the size: a jalapeno is mild enough to eat raw, "
          "a bird's eye or a scotch bonnet will heat a whole curry, and the same kind varies from "
          "one to the next, so taste a sliver before you commit to two. Chop them small and add "
          "them early for a rounded heat, or late and sliced for a sharp one; the white pith and "
          "the seeds carry most of it, so scraping them out takes the edge off without making it "
          "mild. Wash your hands straight after and keep them off your eyes, or wear gloves for "
          "the very hot ones: the oil stays on skin for hours and soap barely shifts it.",
          # the seed question, the fault, the products and the substitutions have their own rows
          avoid=DISH + ("deseed", "de-seed", "seed", "seeds", "pith", "too spicy", "too hot",
                        "less spicy", "mild", "milder", "cool down", "cool it", "flakes",
                        "powder", "paste", "plant", "grow", "growing", "sow", "seedling")),
    # The oil that burns a mouth burns an eye, and "rubbed my eye after chopping chillies" was
    # answered by the variety card (it owns "chop") while "chilli in my eye" got an echo. The
    # subject is the chilli and the job is the eye, so this row keys on both and the eye words are
    # deliberately narrow: the variety row's advice to keep them off your eyes is not the answer
    # to having got some in one.
    entry("chilli-eye",
          (("chilli", "chillies", "chili", "chillis", "jalapeno", "jalapenos", "habanero",
            "scotch bonnet", "chilli oil", "chilli juice"),
           ("in my eye", "in the eye", "in my eyes", "my eye", "my eyes", "eyeball",
            "eye is", "eyes are", "eye hurts", "eyes hurt", "stinging", "stings", "rubbed my eye",
            "rubbing my eye",
            # somebody else's eye: "my baby got chilli in her eye" is the same injury as the
            # person's own, and "her eye" is how it is said.
            "in her eye", "in his eye", "in their eye", "his eye", "her eye", "their eye")),
          "Don't rub it: rinse the eye with milk if you have some, then clean, cool water or "
          "saline for ten to fifteen minutes with the lid held open, and blink it through. The "
          "burn fades over an hour or so and the redness can last a day. Ring 111 or go to an eye "
          "casualty the same day if the pain is getting worse rather than better, if your sight is "
          "blurred, or if you wear a contact lens - take it out first. Wash your hands and the "
          "knife before you touch your face again, because the oil sits on skin for hours and soap "
          "barely shifts it.",
          avoid=DISH),

    # "what can i use instead of chilli flakes" was answered by the dandruff card, because
    # "flakes" belongs to a scalp, and "i have no chillies" got nowhere at all.
    entry("chilli-substitute",
          (("chilli", "chillies", "chilli flakes", "chilli powder", "chilli sauce", "chili",
            "chilli paste", "cayenne", "paprika", "gochujang", "sriracha"),
           ("instead of", "substitute", "substitution", "swap", "replace", "alternative",
            "no chillies", "run out", "ran out", "out of", "stand in", "same as")),
          "Paprika plus a pinch of cayenne is the closest thing to chilli powder: about four parts "
          "paprika to one of cayenne, and smoked paprika if you want the depth back. For flakes, a "
          "teaspoon is roughly one fresh chilli, so half a teaspoon of cayenne or a chopped red "
          "pepper does the job, and a spoon of sriracha, gochujang or hot sauce adds heat and a "
          "little sweetness. Without any of those, black pepper and a little ginger give the bite "
          "even though the flavour is different.",
          avoid=DISH + ("deseed", "de-seed", "pith", "how hot", "how spicy", "too spicy",
                        "too hot", "plant", "grow", "growing", "sow", "seedling", "store",
                        "freeze", "keep", "dry them", "drying", "make chilli oil")),
    # "how do i make chilli oil" got "That is everything I have on that one", and
    # "how do i store chilli oil" got the box-in-the-fridge-drawer row.
    entry("chilli-oil",
          # the oil has to be named: "chilli" plus "how do i" is every chilli question there is
          (("chilli oil", "chili oil"),
           ("make", "recipe", "how do i", "store", "keep", "last", "shelf life", "infuse",
            "chillies in", "with dried")),
          "Warm 200ml of a plain oil with four sliced chillies and a crushed garlic clove over the "
          "lowest heat for five minutes - it should barely bubble, because burnt chilli turns "
          "bitter - then let it cool completely before you bottle it. Keep it in the fridge and use "
          "it within a fortnight, since fresh garlic and fresh chilli in oil will grow things at "
          "room temperature; dried flakes in oil keep far longer, up to three months cold.",
          # "make" and "how do i" are on every line, so the chilli oil phrase is what decides it
          # and the vegetable questions are kept out
          avoid=DISH + ("chop", "deseed", "seed", "pith", "how hot", "how spicy", "too spicy",
                        "less spicy", "store chillies", "freeze", "instead of", "substitute",
                        "plant", "grow", "sow")),
)
