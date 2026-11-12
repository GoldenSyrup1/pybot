"""Kitchen kit: how much water in the kettle, and a pan or a tin with burnt food on it.

Two subjects that are about the thing rather than the food, and that share a fault: both were
answered badly by a neighbour. "how much water in a kettle" had no owner at all - the running-cost
table answers what a boil costs, not how full to fill it, and the brewing entry answers the leaves
- so it was the honest shrug. A cake tin or a baking tray with burnt food on it was read as a burn
on a person ("twenty minutes under cool running water") or as a pan on the hob ("simmer it for ten
minutes"), and neither is a job a tin can do.

Both answers are one fact each, used with what the line already says: a mug is about 300 ml, so
the count on the line sets the water, and a full 1.7-litre kettle is five or six mugs the other way
round. Burnt-on food lifts in a soak, and the sentence is said for the thing that burnt on - a tin
is told why not to scour it, a tray gets baking paper, a shelf gets the bath.

The same file holds what to do about a pan that is burnt on, or whose fat has smoked: the pan's
soak, the burnt dish's rescue and the reason a pan of oil smokes are all about the pan and what is
in it, and the oil entry's key takes a bare "burnt" beside "pan", which is how a pan to clean was
answered with a lecture on smoke points. `_burnt_on_the_pan` is the line between the two.

A domain of its own rather than a part of bot/knowledge/cooking.py, which is at the world's 1 MB
file cap: a domain is one file with ENTRIES (bot/knowledge/__init__.py), and the helpers below are
the ones `cooking` already uses (`_says`, `_words_and_text`, `_FOOD`, the pan and bake word lists
and the vessel phrases), imported rather than copied.
"""
import re

from .cooking import (_BURNT_EATING_REPLY, _BURNT_ON_A_PAN, _FOOD, _PAN_DISH,
                      _REMOVAL_FROM_A_PAN, _VESSEL_PHRASES, _burnt_on_the_pan, _says,
                      _words_and_text)
from .lookup import entry

ANSWERS = ("cooking", "food-and-drink", "home-and-diy")


ML_PER_MUG = 300
# What a person adds for the pot, and the small allowance that keeps the element covered.
_POT_SPLASH = 100


def _ml(value):
    """A millilitre figure as a person would say it: 600 ml, then 1.2 litres."""
    if value >= 1000:
        litres = f"{value / 1000.0:.1f}".rstrip("0").rstrip(".")
        return f"{litres} litres"
    return f"{value} ml"


# A count written in words, for the reading that no longer carries numbers: an entry reached
# through a carried subject is read from a line the module wrote out itself, and the number the
# person typed is not in it. The engine still counts first (memory["understood"]["numbers"]); this
# is the fallback, not a second keyword list.
_COUNT_WORDS = {"a": 1, "an": 1, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6,
                "seven": 7, "eight": 8, "nine": 9, "ten": 10, "eleven": 11, "twelve": 12,
                "a couple": 2, "a couple of": 2, "a few": 3, "a few of": 3, "couple": 2}
_CUPS_SAID = re.compile(
    r"\b(\d{1,2}|a couple of|a few of|a couple|a few|twelve|eleven|ten|nine|eight|seven|six|"
    r"five|four|three|two|one|an|a)\s+(cups?|mugs?|cuppas?|people|persons?|of us)\b")


def _cups_said(text):
    """(count, "cups" or "people") from the line itself, or (0, "cups")."""
    match = _CUPS_SAID.search((text or "").lower())
    if not match:
        return 0, "cups"
    said = match.group(1)
    try:
        count = int(said)
    except ValueError:
        count = _COUNT_WORDS.get(said, 0)
    unit = "people" if match.group(2).startswith(("people", "person", "of us")) else "cups"
    return (count if count > 0 else 0), unit


# How many mugs a full kettle makes: the same 300 ml a mug read the other way round, so the
# person who asks "how many mugs does a full kettle make" gets a count and not the advice to
# count their own. `home.kettle-boil-time` answers how long one takes, so the duration words are
# in `tea-water`'s avoid list and this entry is only ever about the water.
_FULL_KETTLE_ASK = re.compile(r"\bhow many\s+(?:cups|mugs|cupfuls)\b|\bhow many\b[^?.]{0,20}"
                              r"\bkettle\b|\bkettle\b[^?.]{0,20}\bhow many\b")
_FULL_KETTLE = ("A full 1.7-litre kettle makes about five or six mugs of tea, since a mug is "
                "around 300 ml and you lose a little to steam. A 1-litre kettle does three. Boil "
                "only what you are going to drink and it is quicker and cheaper both.")


def _tea_water(memory, understood):
    """How much water to boil, and how long it takes, from the line."""
    count, unit = 0, "cups"
    for number in (understood or {}).get("numbers") or []:
        if not isinstance(number, dict):
            continue
        said = str(number.get("unit") or "")
        try:
            value = int(number.get("value"))
        except (TypeError, ValueError):
            continue
        if value < 1:
            continue
        if said in ("cup", "cups", "mug", "mugs", "cuppa", "cuppas"):
            count, unit = value, "cups"
            break
        if said in ("people", "person", "of us", "guest", "guests"):
            count, unit = value, "people"
            break
    if not count:
        count, unit = _cups_said(str((understood or {}).get("clean")
                                     or (understood or {}).get("text") or ""))
    said = str((understood or {}).get("clean") or (understood or {}).get("text") or "").lower()
    if not count and _FULL_KETTLE_ASK.search(said):
        return _FULL_KETTLE
    if not count:
        return ("A mug of tea is about 300 ml, so count the mugs you are making and fill the kettle "
                "just past that: two cups is 600 ml, and a full 1.7-litre kettle is about five "
                "mugs. Boiling only what you will drink is the cheapest habit in the kitchen.")
    amount = _ml(count * ML_PER_MUG)
    if unit == "people":
        what = f"{count} people, a mug each"
    elif count == 1:
        what = "one cup"
    else:
        what = f"{count} cups"
    return (f"About {amount} for {what}, since a mug holds roughly 300 ml and a splash more covers "
            f"the element. Boiling only what you drink is the cheapest habit in the kitchen.")


# The words that stand in for whatever burnt on: "get burnt food off a baking tray" and "the
# tray has burnt bits on it" name no dish, so they must not hold the tin back from its own answer.
# "baking" is in the food list because a bake that burnt is the food's question, but in front of a
# tray or a sheet it is the vessel's own name, so it comes out with the fillers.
_BLANK_STUFF = re.compile(
    r"\b(?:food|foods|stuff|bits|bit|mess|residue|crud|gunk|grime|grease|leftovers|things|"
    r"patches|marks|spots|remains|baking|baked on|burnt food|burnt bits)\b")


def _burnt_tin(memory, reading):
    """The soak, said for the thing that burnt on.

    A tin, a mould and a springform are scoured at their peril, so the answer says why not. A
    tray or a shelf is flat and takes a scourer, and it lies in the sink instead of being filled;
    the shelf is the one that may not fit, and what stops it coming back is foil under the tin
    rather than baking paper inside it.
    """
    said = _words_and_text(reading)
    words = set()
    for word in (reading or {}).get("words") or ():
        if isinstance(word, str):
            words.add(word.lower())
    # A bake that burnt in the tin is the food's question, not the tin's: "i burnt the roast
    # potatoes on the tray" wants the potatoes, and the soak is for the tin afterwards. What
    # burnt *on* a tray is usually not named at all - "get burnt food off a baking tray", "burnt
    # bits on the tray", "the tray has burnt stuff stuck to it" - and those filler words are in
    # the food list, so they come out before the food is looked for. Without that the tin declined
    # its own cleaning question and the person got a nod.
    baked = _BLANK_STUFF.sub(" ", _VESSEL_PHRASES.sub(" ", said))
    if (_says(baked, _FOOD)
            and not _says(said, _PAN_CLEAN + ("off my tray", "off the tray", "off my tin",
                                             "off the tin", "get the burnt off", "off the sheet"))):
        return ""
    # "will that take the coating off", asked after the soak: it is a question about the tin's
    # surface, and the soak paragraph said again is a wall, so answer it where it is asked.
    if words & {"coating", "coatings", "non", "nonstick", "teflon", "scratch", "scratched",
                "scratches", "scouring", "scour", "scourer", "wool", "scraper"}:
        return ("Bicarbonate and a wooden spoon will not lift a non-stick coating - it is wire "
                "wool and metal scourers that do. If the coating is already scratched through to "
                "the metal, that tin is done for anything that sticks, so line it with baking "
                "paper and keep it for bakes that turn out of the tin anyway.")
    if words & {"shelf", "shelves", "rack", "racks"}:
        return ("Soak it in hot water and two tablespoons of bicarbonate of soda for half an hour "
                "- the bath if the shelf will not fit in the sink - then lift the burnt patches "
                "off with a plastic scourer or a ball of foil. Anything really black takes a paste "
                "of bicarbonate and water left on overnight. Dry it before it goes back in, and "
                "put a sheet of foil on the shelf under the tin next time, which is what catches "
                "the drips.")
    if words & {"tray", "trays", "sheet", "sheets"}:
        return ("Soak it in the sink with hot water and two tablespoons of bicarbonate of soda for "
                "half an hour, then lift the burnt patches off with a wooden spoon or a plastic "
                "scourer. Anything really black takes a paste of bicarbonate and water left on "
                "overnight. Dry it properly before it goes away, and line it with baking paper "
                "next time, which is what stops it coming back.")
    return ("Soak it in the sink with hot water and two tablespoons of bicarbonate of soda for half "
            "an hour, then lift the burnt patches off with a wooden spoon or a plastic scourer: "
            "tins are thin and scouring takes the non-stick off for good. Anything really black "
            "takes a paste of bicarbonate and water left on overnight. Dry it properly before it "
            "goes away, and line it with baking paper next time, which is what stops it coming "
            "back.")



_BURNT_PAN_REPLY = ("Put an inch of water and two tablespoons of bicarbonate of soda in it and "
                    "simmer for ten minutes, then lift the burnt layer with a wooden spoon: "
                    "almost nothing needs scrubbing after that. Stainless steel and enamel can "
                    "take a vinegar soak instead, but never scour a non-stick pan, since it "
                    "takes the coating off for good.")


_PAN_CLEAN = ("clean", "cleaning", "cleaned", "scrub", "scour", "soak", "soaking", "wash",
              "washing", "comes off", "come off", "off the bottom", "off my pan", "off the pan",
              "off the inside", "off the base", "get it off", "gets it off", "still stuck",
              "stuck on", "wont come", "won't come",
              # a tin is cleaned the same way a pan is, and "off the tin" is how people say it:
              # "how do i get the burnt off my cake tin" was answered with butter and flour
              "off the tin", "off my tin", "off the tray", "off my tray", "off the sheet",
              "get the burnt off", "burnt off", "stained") + _REMOVAL_FROM_A_PAN


# The vessels that are not a pot on the hob: a tin, a tray and a shelf are soaked in the sink
# instead, and "simmer it for ten minutes" is an instruction about a pan.
_NOT_A_PAN = ("tin", "tins", "cake tin", "loaf tin", "muffin tin", "baking tin", "roasting tin",
              "pie tin", "tart tin", "springform", "tray", "trays", "baking tray",
              "roasting tray", "baking sheet", "sheet", "sheets", "oven shelf", "shelf",
              "shelves", "rack", "mould", "molds", "mold")


_A_PAN = ("pan", "pans", "pot", "pots", "saucepan", "saucepans", "wok", "woks", "skillet",
          "casserole", "griddle")


# A food that stuck is not a pan that burnt, and the key could not tell them apart: "stuck" and
# "pan" are both in it, so "my hash browns stuck to the pan", "my gyoza stuck to the pan", "my
# plantain stuck to the pan" and "my pierogi stuck to the pan" were told to simmer the pan with
# bicarbonate and lift the burnt layer with a wooden spoon. A pan to clean is a pan line that says
# so - burnt, black, scorched, or a word for getting it off - and a stuck food wants the pan hot
# and the food left alone, which is `fix-sticking`'s answer.
_PAN_STUCK = ("stuck", "sticks", "sticking", "stick")
# What is stuck without a name is the pan to clean: "there is something stuck to the bottom of my
# pan" wants it off, where "my gyoza stuck to the pan" is a food that should have slid.
_PAN_SOMETHING = ("something", "anything", "everything", "stuff", "bits", "whatever")
_PAN_BURNT = ("burnt", "burned", "burn", "burning", "burns", "scorched", "scorching",
              "black", "blackened", "smoke", "smoking", "smoked", "layer", "stain",
              "stained", "charred") + _PAN_CLEAN


# Whether burnt food is bad for you is the eating question, not the pan's: "is burnt food off a
# pan bad for me" was told to simmer the pan with bicarbonate, which answers a question about
# scrubbing to somebody asking about eating.
_BURNT_EATING_SAFETY = ("bad for", "bad for you", "bad for me", "harmful", "dangerous", "cancer",
                        "carcinogen", "carcinogenic", "poison", "poisonous", "toxic",
                        "safe to eat", "ok to eat", "okay to eat", "alright to eat", "can i eat",
                        "can you eat", "should i eat", "still eat", "eat it", "is it safe",
                        "is it ok", "is it okay", "is it bad", "healthy", "unhealthy",
                        "does it matter")


def _burnt_pan(memory, understood):
    """The pan's answer for a pan line, and nothing for a line whose dish is what burnt."""
    said = " ".join(str((understood or {}).get(key) or "")
                    for key in ("clean", "norm_text", "norm")).lower()
    # Whether burnt food is bad for you is the eating question, not the pan's: "is burnt food off
    # a pan bad for me" was told to simmer the pan with bicarbonate, which answers a question
    # about scrubbing to somebody asking about eating.
    if _says(said, _BURNT_EATING_SAFETY):
        return _BURNT_EATING_REPLY
    # A tin, a tray or a shelf with burnt food on it is the tin answer's, not the pot's: the
    # hob is not where it goes, and the coating warning is not what a tray needs.
    if _says(said, _NOT_A_PAN) and not _says(said, _A_PAN):
        return ""
    # "stuck" alone is the food sticking, not the pan needing a soak, so this row stands down and
    # the line goes to the answer that knows why food sticks.
    if (_says(said, _PAN_STUCK) and not _says(said, _PAN_BURNT)
            and not _says(said, _PAN_SOMETHING)):
        return ""
    if _says(said, _PAN_CLEAN):
        return _BURNT_PAN_REPLY
    if _says(said, _PAN_DISH):
        return ""       # a dish is burnt, not the pan: fix-burnt has that line
    return _BURNT_PAN_REPLY


# A burnt top on a cake is not a burnt pan of sauce: nothing is stirred, and the answer is the
# oven and the foil. The pot line stays for everything that is actually in a pan.


# A pan, a pot, a tin, a board or a plate that has cracked, warped or shed its coating is a
# replacement question, and the neighbours each assumed the thing still worked: `my frying pan is
# warped` got the shrug, `my microwave plate cracked` got the chip-in-china answer about bacteria in
# a glaze, and `my slow cooker cracked` got a recipe. A crack is not a cleaning job and a wobble is
# not something to cook in, so the thing and the damage are the two halves of the key and the reply
# follows the material: a glass plate or a cracked pot retires, a board goes only if the split goes
# through, and a warped pan depends on the hob it has to sit on.
_KIT_DAMAGE = ("warped", "warping", "warp", "buckled", "buckling", "bent", "dented", "cracked",
               "crack", "cracks", "cracking", "split", "splits", "splitting", "snapped",
               "flaking", "peeling", "chipped", "chipping", "wobbly", "wobbles", "wobbling",
               "loose", "came off", "come off", "fell off", "fallen off",
               # A pan that no longer sits flat is the same damage said from the hob's side
               # rather than the pan's: "my pan wobbles on the hob" was the loose-handle screw
               # and "my pan rocks on the hob" was a chat nod, and neither is the answer.
               "rocks", "rocking", "spins", "spinning", "doesnt sit flat", "doesn't sit flat",
               "wont sit flat", "won't sit flat", "not flat", "bowed", "dished", "domed",
               "bulging", "bulged")
_KIT_THING = ("pan", "pans", "frying pan", "saucepan", "saucepans", "wok", "skillet", "pot",
              "pots", "stock pot", "casserole", "casserole dish", "slow cooker",
              "slow cooker pot", "insert", "baking dish", "oven dish", "dish", "tin", "tins",
              "tray", "baking tray", "board", "chopping board", "cutting board", "wooden board",
              "kettle", "microwave plate", "turntable", "jug", "blender", "enamel",
              "coating", "non stick", "non-stick", "handle", "lid")


def _kit_damaged(memory, understood):
    """A cracked, warped or worn-out piece of kitchen kit: whether it can be used, fixed or binned.

    The answer follows the material, because that is what decides it: glass and ceramic cannot be
    used with a crack in them, a wooden board can be sanded unless the split goes through, and a
    warped pan is only a problem on a hob that needs a flat base.
    """
    understood = understood or {}
    text = " " + " ".join(str(understood.get(key) or "").lower()
                          for key in ("text", "norm_text", "clean")) + " "

    def has(*phrases):
        return any((" %s" % phrase) in text for phrase in phrases)

    if has("microwave plate", "turntable", "glass plate", "plate in the microwave"):
        return ("Replace the part rather than the machine: a microwave plate or turntable ring is "
                "about \u00a310 to \u00a320 and sold by the model number on the sticker inside the "
                "door, or stamped on the plate itself. A cracked plate can shatter the next time it "
                "heats, so keep it out of the microwave until the new one comes.")
    if has("jug", "blender", "carafe", "glass lid", "lid"):
        return ("A cracked jug, blender jug or glass lid goes: it can let go all at once with "
                "something hot in it, and a crack you cannot scrub out of is not a food surface. "
                "Blenders and kettles take a spare jug or lid by model number, and a jam jar is a "
                "free substitute while you wait.")
    if has("board", "chopping board", "cutting board", "wooden board"):
        return ("Sand it back and oil it if the split is shallow, because that closes the grain "
                "again; a crack that goes right through traps food where you cannot wash it out, "
                "and that board should go. Never soak a wooden board or put it in the dishwasher - "
                "wash it, stand it on edge to dry and oil it once a month.")
    if has("enamel", "enamelled", "chipped", "chipping"):
        return ("A chip on the inside of an enamelled pan will rust and flake into the food, so "
                "that one is finished; a chip on the outside only matters for looks. Enamel repair "
                "paints are not food safe, so do not touch one in, and do not put an enamelled pan "
                "in the dishwasher, which is what chips the rim.")
    if has("coating", "non stick", "non-stick", "teflon", "flaking", "peeling"):
        return ("Once the coating is flaking the pan is done: the flakes come off into the food and "
                "the bare metal scorches what it touches. Re-coating is not a home job, so replace "
                "it - and washing it by hand, never heating it empty and never scouring it are what "
                "make the next one last three to five years.")
    if has("warped", "warping", "buckled", "buckling", "dented", "bent", "wobbles", "wobbling",
           "rocks", "rocking", "spins", "doesnt sit flat", "doesn't sit flat", "wont sit flat",
           "won't sit flat", "not flat", "bowed", "dished", "domed", "bulging", "bulged"):
        if has("tin", "tins", "tray", "trays", "sheet", "springform", "mould", "muffin"):
            return ("Stand it on the worktop and press it flat again with the heel of your hand: a "
                    "baking tin that has bent in the wash still bakes the same, and the only thing "
                    "you notice is the wobble. Set it on a flat baking sheet if the batter runs to "
                    "one side. Replace it when the springform clip or the base no longer seats "
                    "flat, because then it leaks.")
        return ("A warped base only really matters on a flat hob: on gas the pan still heats, but "
                "on induction, ceramic or solid plate it will not sit flat and the heat goes "
                "patchy. Check it against a straight edge on the worktop. It cannot be flat again "
                "for certain, so a heavy-based pan is the replacement - thin ones go in one hot "
                "empty minute or a cold rinse in a hot pan.")
    if has("kettle"):
        return ("A cracked kettle goes: water reaches the element and the connections, which is a "
                "shock risk rather than a leak to mop up. Unplug it and replace it - a new kettle "
                "is \u00a315 to \u00a330, and descaling the next one monthly is what keeps it from "
                "running hot.")
    if has("slow cooker", "casserole", "stoneware", "ceramic", "pot", "pots", "dish", "dish",
           "baking dish", "oven dish"):
        return ("Retire it if the crack is in the pot itself: stoneware fails right through when it "
                "heats, and a crack holds food you cannot wash out of it. Slow cooker inserts and "
                "casserole dishes are sold on their own by model number or size, \u00a310 to \u00a325, "
                "and a lidded oven dish that fits inside will do until the new one comes.")
    return ("If the crack is right through, replace it: a split pot, dish or plate holds food and "
            "bacteria where you cannot wash, and it can fail completely the next time it heats. A "
            "chip or crack on an outside face that never touches food can usually be lived with.")


ENTRIES = [
    entry("tea-water",
          # "kettle" only: "how do i make a cup of tea" is the brew times, and a key that carried
          # "cup of tea" took it. Each count word is named once, because two groups of one word is
          # all `score()` asks for and "how full should the washing machine be" was the kettle.
          (("kettle", "kettles", "cups of tea", "mugs of tea", "mug of tea"),
           ("how much water", "much water", "how full", "how far to fill", "fill the kettle",
            "filling the kettle", "cups of water", "how much to fill", "full to fill",
            "how many cups", "how many mugs", "boil for", "how much in", "should i fill",
            "do i fill",
            # the follow-up a person writes at the kettle names the count and not the question:
            # "and for two cups of tea" after the fill answer is the same sum with a new number,
            # and without these it reached the caffeine limit for the day instead
            "for two cups", "for three cups", "for four cups", "for five cups", "for six cups",
            "for one cup", "for a cup", "for two mugs", "for three mugs", "for four mugs",
            "for five mugs", "for six mugs", "for one mug", "for a mug",
            "for two people", "for three people", "for four people", "for six people",
            "for two of us", "for three of us", "for a couple", "for a few")),
          _tea_water,
          # the follow-up that only names the count is still an ask - "and for two cups of tea",
          # after the fill answer, is the same sum with a new number - so the count phrases are
          # wanted here as well as in the key
          ask=("how much", "how many", "how full", "how far", "how big",
               "should i", "do i need", "do i fill", "much water", "many cups", "many mugs",
               "fill", "full",
               "for one", "for a cup", "for a mug", "for two", "for three", "for four",
               "for five", "for six", "for a couple", "for a few", "for a crowd",
               "for the two of us", "for the three of us", "for the four of us"),
          # "how many calories in a cup of tea" and "how many cups of tea is too many" are a
          # nutrition question and a caffeine one, not how full the kettle goes; a kettle that is
          # faulty, scaled, costly or tastes of something is a fault or a bill, and how long one
          # lasts or takes to descale is neither the fill nor the boil.
          avoid=("descale", "descaling", "descaled", "limescale", "scale", "scaled", "clean",
                 "vinegar", "citric", "broken", "repair", "boil dry", "element", "filter",
                 "hard water", "calorie", "calories", "caffeine", "sugar", "milk", "too many",
                 "too much", "strong", "last", "lasts", "lifetime", "warranty", "keep warm",
                 "switch off", "auto", "day", "days", "drink", "drinking", "drank", "had",
                 "today", "protein", "carbs", "alcohol", "stain", "stains", "teeth",
                 "how do i make", "steep", "brew",
                 # how long a kettle takes is `home.kettle-boil-time`'s question, and two entries
                 # claiming the same line is how a person gets the wrong one: the duration words
                 # stand this entry down, and the fill words do not.
                 "how long", "how many minutes", "take to boil", "long to boil", "minutes",
                 # a kettle that is faulty, costly or tastes of something is not a fill question
                 "cost", "costs", "price", "electricity", "energy", "buy", "buying", "best",
                 "which kettle", "plastic", "taste", "tastes", "tasting", "slow", "leak", "leaks",
                 "switch", "switching", "switches"),
          bias=1),
    # A cake tin, a loaf tin or a baking tray that has burnt food on it is the same cleaning
    # question as a pan, but it cannot be simmered on the hob: it wants a soak in the sink. The
    # bake that caught on top is bake-burning's, so only the cleaning words are keyed here, and
    # `stuck` is left out because a cake stuck to the tin has its own rescue.
    entry("burnt-tin", (("burnt", "burned", "burnt on", "burnt bits", "black bits",
                         "blackened", "scorched", "charred", "crusty", "black"),
                        ("tin", "tins", "cake tin", "loaf tin", "muffin tin", "baking tin",
                         "roasting tin", "pie tin", "tart tin", "springform", "tray", "trays",
                         "baking tray", "roasting tray", "baking sheet", "oven shelf",
                         "oven shelves", "shelf", "rack", "mould")),
          _burnt_tin,
          # the food in a bake that burnt is bake-burning's, and a cake stuck to the tin is
          # cake-out-of-tin's; a line that says what to cook gets the recipe
          avoid=("sticking", "sticks", "using", "use a", "use my", "what size",
                 "what can i make", "recipe", "oven temperature", "what temperature",
                 "how long", "why does", "where do i buy", "how much is", "worth",
                 "springform leaks", "leaks", "rusty", "rust",
                 # black mould on a wall is the damp answer's, not a burnt tin's: the bare word
                 # "black" in the key is what lets it in, so the mould words hold it out.
                 "mould", "mold", "mouldy", "moldy", "mildew", "damp", "dehumidifier"),
          bias=1),
    entry("burnt-pan", (("pan", "pans", "pot", "pots", "saucepan", "saucepans", "wok",
                         "casserole", "skillet"),
                         # the tins and the trays were keyed here while `burnt-tin` did not
                         # exist; they are its lines now, because a tin cannot be simmered on the
                         # hob and a baking tray wants baking paper rather than a wooden spoon.
                        ("burnt", "burned", "burn", "scorched", "scorching", "cleaning", "clean",
                         "scour", "soak", "stuck", "bottom", "black",
                         # "the pan has burnt black on the outside" is a pan to clean and it was
                         # reaching the mould answer on "black" and "outside"
                         "outside", "outside of the pan", "outside bottom", "burnt black",
                         "blackened",
                         # "my pan has burnt stuff stuck on it" names the stuff and not the
                         # removal, and the oil row's bare "burnt" beside "pan" outscored this
                         # one on it: the asked-for thing is the stuck layer, so it is keyed.
                         "stuck on it", "stuck on", "stuck to it", "burnt stuff", "stuff stuck",
                         "burnt bits stuck", "rescue", "salvage", "ruined", "scorched pan",
                         "burnt pan", "burned pan")),
          _burnt_pan,
          # "tray" also covers a baking tray, and a litter tray is not one: the cat's tray got
          # "simmer it with bicarbonate of soda and lift the burnt layer with a wooden spoon".
          # "cake" is not in this list any more: the tin the cake burnt in is a tin to clean, and
          # _burnt_pan already hands a line with a dish burnt in it back to the dish's answer when
          # no cleaning word is there. Bare "cake" also swallowed "how do i clean a burnt cake tin".
          avoid=("my hand", "my finger", "my arm", "my wrist", "my thumb", "myself", "oven",
                 # the mark the pan left behind is the worktop's question, not the pan's
                 "worktop", "worktops", "counter", "countertop", "the table", "work surface",
                 "worksurface", "benchtop", "the floor", "carpet",
                 "roast", "toast", "carpet", "cake recipe", "the cake is burnt", "cake is burnt",
                 "my cake burnt", "my cake is burnt", "my cakes burnt",
                 "litter", "cat", "cats", "kitten", "dog", "dogs", "puppy", "pet", "pets",
                 "rabbit", "hamster", "nappy", "bin", "toilet", "nursery")),

    # A cracked, warped or worn-out piece of kit is a replacement question, and the neighbours
    # here all assume the thing still works. The damage words are the half that makes it a fault:
    # keyed on the thing alone this would take every "which pan" and every "how do i cook in a
    # slow cooker", which have their own rows.
    # No `ask` here on purpose: an entry with one is gated on it, and the lines this answers say
    # what broke, not "can it be fixed" - "my slow cooker cracked" and "the pan is warped" carry no
    # asking phrase at all. The damage word is the second signal the two-part key needs.
    entry("kit-damaged", (_KIT_DAMAGE, _KIT_THING), _kit_damaged,
          # a phone, a window, a wall, a bone and a tooth are not kitchen kit, and each has its own
          # answer; a recipe is not a repair either, which is what "my slow cooker cracked" got.
          # "my pan handle is loose" already has a good answer (one screw and a nut) and this row
          # said it again in other words, so the handle is out of the thing group entirely.
          # "my non stick pan is flaking" already has a good answer that draws the line at
          # scratched-through, and this row said the same thing in other words; "plate" and "mug"
          # are the chip-in-china row's crockery, which answers a cracked piece as well as a chip.
          avoid=("handle", "handles", "rust", "rusty", "rusted", "season", "seasoning",
                 "non stick", "non-stick", "nonstick", "teflon", "scratched", "scratches",
                 "phone", "mobile", "screen", "laptop", "tablet", "window", "windscreen",
                 "wall", "ceiling", "tooth", "teeth", "bone", "skull", "rib", "ankle", "wrist",
                 "mug", "cup", "tea cup", "teacup", "china", "crockery", "teapot",
                 "recipe", "recipes", "what can i cook", "what can i make", "how do i cook",
                 "how long to cook", "cook a", "roast", "bake", "baking a", "season", "seasoning",
                 "buy a", "buying a", "which pan", "best pan", "what pan", "worth it",
                 "warranty", "guarantee"),
          bias=1),

]
