"""Fruit: getting one out of its skin, one method per fruit.

The answers lane owns this domain. Getting the flesh out of a kiwi, the seeds out of a
pomegranate and the stone out of a peach are three different jobs, so the entries are keyed by
the fruit the line names rather than by the verb: "how do i deseed a pomegranate", "how do i cut a
pomegranate" and "how do i get the seeds out of a pomegranate" are one question.

Why its own domain: these are neither dishes nor cooking methods, and on main they had no home at
all. Nine of them were shrugs, and the two that found an entry found the wrong one - "how do i cut
a pineapple" got the pineapple-on-pizza opinion and "how do i cut an avocado" got the
keeping-a-cut-avocado card. cuisine's table is already at the size ceiling, so this is a file of
its own rather than another append there.
"""
import re

from .lookup import entry

ANSWERS = ("cooking", "food-and-drink")

# The method is different for every fruit, so the table is keyed by the fruit and one row reads
# it: the verbs (cut, peel, stone, deseed, core, segment, open, juice, supreme) do not change the
# answer, only the fruit does.
FRUIT_METHODS = (
    (("pomegranate", "pomegranates", "pomegranate seeds"),
     "Cut the crown off and score the skin down the ridges, then pull it apart over a big bowl of "
     "water: the seeds sink, the white pith floats, and nothing sprays your shirt. For a whole one "
     "in a hurry, hold a half cut-side down over a bowl and whack the back with a wooden spoon and "
     "the seeds drop out in a minute."),
    (("mango", "mangoes", "mangos"),
     "Slice a cheek off each side of the flat stone, score the flesh in a grid without cutting "
     "through the skin, then push the skin inside out and slice the cubes off. The stone and the "
     "flesh round it are the cook's, and a peeler takes the skin off the two cheeks if you would "
     "rather have slices."),
    (("pineapple", "pineapples"),
     "Cut the top and the base off flat so it stands up, then slice the skin off in strips from "
     "top to bottom, following the curve, and take the eyes out with the tip of the knife. Quarter "
     "it lengthways and cut the woody core out of each quarter."),
    (("kiwi", "kiwis", "kiwifruit"),
     "Top and tail it, then either run a vegetable peeler round it or cut it in half and scoop the "
     "flesh out with a teaspoon, which goes round the skin in one movement. A kiwi that is soft "
     "enough to eat peels with a spoon and no knife at all."),
    (("peach", "peaches", "nectarine", "nectarines", "plum", "plums", "apricot", "apricots",
      "cherry", "cherries"),
     "Run the knife round the seam, all the way round rather than through the stone, then twist the "
     "halves apart. A ripe peach or plum gives its stone up with a thumb; a clingstone that will "
     "not, cut it into quarters round the stone and flick it out. A cherry wants a bottle neck or "
     "a paperclip pushed into the dimple."),
    (("lemon", "lemons", "lime", "limes"),
     "Roll it hard on the counter with your palm first to break the cells inside, then cut it "
     "across the middle rather than end to end and squeeze with the cut face out, so the pips stay "
     "in your hand. A fork twisted in the half gets more juice out than a squeeze does, and half a "
     "minute in a microwave gets more again."),
    (("coconut", "coconuts"),
     "Three soft eyes sit at one end: push a screwdriver or a clean nail through the softest, drain "
     "the water into a glass, then hit round the equator with the back of a heavy knife or a "
     "hammer, turning it as you go, until it cracks in two. The flesh comes out with a knife run "
     "between it and the shell."),
    (("avocado", "avocados"),
     "Run the knife round the stone lengthways, twist the two halves apart, then whack the stone "
     "with the blade and twist it out, or push a spoon in behind it. Slip a spoon between the skin "
     "and the flesh to peel a half, and cut it only when you are about to eat it."),
    (("apple", "apples"),
     "Quarter it round the core with a knife and cut the core out of each quarter at an angle, or "
     "push an apple corer straight down over the stalk. A peeled or cut apple browns in minutes, so "
     "toss it in a little lemon juice if it has to wait."),
    (("melon", "melons", "watermelon", "watermelons", "cantaloupe", "honeydew"),
     "Cut it in half through the middle rather than end to end, scoop the seeds out with a spoon, "
     "then stand each half on its flat face and slice the skin off downwards in strips. A melon "
     "baller on a halved one is quicker than cubing, and watermelon gives up its seeds the same "
     "way, with a fork to flick out the stragglers."),
    (("orange", "oranges", "grapefruit", "grapefruits", "tangerine", "tangerines",
      "satsuma", "satsumas", "clementine", "clementines"),
     "Cut the top and the bottom off so it stands, then slice the peel and pith off in strips down "
     "the sides, following the curve, until no white is left. Cut the segments out between the "
     "membranes over a bowl to catch the juice, which beats peeling a grapefruit with your fingers "
     "and still finding pith."),
)

# Juicing is not cutting. A lemon is squeezed and an apple is not, so a line that asks for the
# juice only reaches the citrus row: everything else here is a knife method and would be the wrong
# answer to "how do i juice a pineapple".
JUICE_WORDS = ("juice", "juiced", "juicing", "squeeze", "squeezing", "squeeze it")
# A juice word is a verb in "how do i juice a lemon" and a noun in "can i drink orange juice".
# The noun is a health, price, stain or storage question about a drink, and the citrus-squeezing
# method is a wrong answer to every one of them - "can i drink orange juice", "does orange juice
# count as 5 a day", "is grapefruit juice ok with statins", "orange juice stain on a shirt" and
# "can i freeze orange juice" all got the squeezing card on the old gate. So a juice line needs
# the shape of a method ask before it is a juicing question.
JUICE_ASKS = ("how do i juice", "how do you juice", "how to juice", "how can i juice",
              "how would i juice", "how should i juice", "how do i squeeze", "how do you squeeze",
              "how to squeeze", "how can i squeeze", "how do i get the juice",
              "how do you get the juice", "how to get the juice", "get the juice out",
              "get more juice", "get more juice out", "get the most juice", "get all the juice",
              "get juice out of", "best way to juice", "easiest way to juice", "way to juice", "way to squeeze",
              "juice a", "juice an", "juice the", "juice some", "juice it", "juice them",
              "juicing a", "juicing the", "squeeze a", "squeeze an", "squeeze the", "squeeze it",
              "squeeze them", "squeezing a", "squeezing an", "squeezing the", "no juicer",
              "without a juicer", "by hand")
CITRUS = ("lemon", "lemons", "lime", "limes", "orange", "oranges", "grapefruit", "grapefruits",
          "tangerine", "tangerines", "satsuma", "satsumas", "clementine", "clementines")
JUICING = ("Roll it hard on the counter with your palm first to break the cells inside, then cut "
           "it across the middle rather than end to end and squeeze with the cut face out, so the "
           "pips stay in your hand. A fork twisted in the half gets more out than a squeeze does, "
           "and half a minute in a microwave gets more again. Sieve it if the pips and pith would "
           "spoil what it goes in.")

# The verbs that make it a how-to-cut-it line. A bare fruit name is not one: "mango chutney" and
# "how much is a pineapple" are somebody else's question.
PREP_WORDS = ("cut", "cutting", "peel", "peeling", "core", "coring", "segment", "segments",
              "supreme", "stone", "stoned", "destone", "de-stone", "deseed", "de-seed", "deskin",
              "open", "opening", "prep", "prepping",
              "prepare", "preparing", "slice", "slicing", "chop", "chunks", "wedges", "top and tail",
              "get the seeds out", "take the stone out", "get the stone out")


def _said(understood):
    """The line, with the punctuation taken out, so a word can be looked for on its own.

    A substring is not a word: "plum" sits inside "plumber", "lime" inside "limestone" and "cherry"
    inside "cherry red", and a plumber asking how to cut a pipe should not get a peach.
    """
    text = str(understood.get("clean") or understood.get("text") or "").lower()
    return " " + re.sub(r"[^a-z0-9' ]+", " ", text) + " "


def _holds(line, word):
    return (" " + word + " ") in line


def _fruit_prep(memory, understood):
    """The way to cut, peel, juice or stone the fruit the line names, one method per fruit.

    A juicing line is not a knife line: the citrus rows have a way to get the juice out, and the
    rest stand down, because "quarter it round the core" is not how a pineapple is juiced.
    """
    line = _said(understood or {})
    if any(_holds(line, word) for word in JUICE_WORDS):
        if not any(_holds(line, word) for word in JUICE_ASKS):
            return None
        return JUICING if any(_holds(line, word) for word in CITRUS) else None
    if not any(_holds(line, word) for word in PREP_WORDS):
        return None
    for words, method in FRUIT_METHODS:
        if any(_holds(line, word) for word in words):
            return method
    return None


# "do i need to peel apples for a crumble" was answered "Yes - apple and pear skin is the best
# part of it", which says yes and then argues for no. The word in front of the answer has to be
# the answer, and which word that is depends on the verb the person used: a line that asks
# whether peeling is *needed* wants "no need", and a line that asks whether the skin can be eaten
# wants "yes". The same skin, two questions, two openings.
NEED_TO_PEEL = re.compile(
    r"\b(?:do|does|should|must|need|needs|have|has|ought|would|will)\s+(?:i|we|you|they|it)\s+"
    r"(?:really\s+|actually\s+|even\s+)?(?:need\s+to\s+|have\s+to\s+|has\s+to\s+)?"
    r"(?:be\s+)?peel(?:ed)?\b"
    r"|\bpeel\s+(?:the\s+|my\s+|these\s+|those\s+)?(?:apples?|pears?|plums?|peaches|kiwis?|"
    r"grapes?)\s+(?:before|first|or not)\b"
    r"|\bis it necessary to peel\b|\bnecessary to peel\b|\bworth peeling\b"
    r"|\bmust be peeled\b|\bneeds peeling\b|\bneed peeling\b"
    # the same question asked as a verdict rather than an instruction: "is it better to peel
    # apples" got "Yes - apple and pear skin is the best part of it", a yes and then the opposite
    r"|\b(?:is|is it|isn't it|would it be|is it not)\s+(?:better|best|worth|fine)\s+to\s+peel\b"
    r"|\bbetter to peel\b|\bbest to peel\b|\bstill worth peeling\b"
    r"|\b(?:do|does|would|should)\s+(?:you|people|most people|anyone|everyone)\s+"
    r"(?:usually\s+|always\s+|normally\s+|even\s+|bother to\s+)?peel\b")
# A skin question asked about a dish is a cooking question: the skin softens in a bake and holds
# the fruit together, so the answer is about that dish and not about eating it raw. Only the baked
# and set dishes, where the skin is a texture and not a nuisance in a glass.
SKIN_IN_A_DISH = re.compile(
    r"\b(?:crumble|cobblers?|pies?|pie filling|tarts?|cake|cakes|muffins?|loaf|loaves|bread|"
    r"brownies?|porridge|baked|baking|roast|roasted|stewed|stew|soup)\b")


def _skin_reply(memory, reading):
    """The skin is food, and the answer names the fruit the line names.

    A kiwi is the one people ask about and the one that needs the scrubbing, because of the fuzz
    and because the skin holds more fibre and vitamin C than the flesh does. Peach, plum, apple,
    pear and grape need only washing.
    """
    said = (reading.get("clean") or reading.get("text") or "").lower()
    # the first word is the answer to the verb the person used, not to the fruit
    lead = "No need to peel - " if NEED_TO_PEEL.search(said) else "Yes - "
    in_a_dish = bool(SKIN_IN_A_DISH.search(said))
    dish = (" For a crumble, a pie or a cake, leave it on: the skin softens as it bakes and holds "
            "the fruit together, and peel only if you want the filling perfectly smooth."
            if in_a_dish else "")
    if "kiwi" in said or "kiwifruit" in said:
        body = ("kiwi skin is edible, and it holds more fibre and vitamin C than the green "
                "flesh, so scrub it under the tap and eat it if the fuzz does not put you off: "
                "the skin is thin, and rubbing it under water takes most of the hairiness off. A "
                "ripe kiwi eaten skin and all tastes the same, only tarter near the skin.")
        if lead.startswith("No need"):
            return lead + body
        return "Yes - " + body
    if any(word in said for word in ("grape", "grapes")):
        return (lead + "grape skins are food - that is where the colour, the tannin and much of "
                "the fibre sit - so wash them and eat them, and only peel a grape for a small "
                "child or someone who cannot manage the skin. A white bloom on the skin is "
                "natural yeast, not spoilage, so rinse it rather than peel it.")
    if any(word in said for word in ("peach", "peaches", "plum", "plums")):
        return (lead + "a peach or a plum is eaten with the skin on, and washing it is enough: "
                "the skin holds the colour and much of the fibre, and peeling only matters for a "
                "smooth chutney or for somebody who finds the fuzz unpleasant. Pour boiling water "
                "over a peach for 30 seconds and the skin slips off if you do want it off." + dish)
    return (lead + "apple and pear skin is the best part of it: the fibre, the colour and the "
            "quercetin that gives the skin its job are all in there, so wash the fruit and eat it "
            "as it is. Peeling loses about a third of the fibre and most of the vitamin C, and "
            "the only ones worth peeling are a waxed one if the wax bothers you, or fruit for a "
            "small child who cannot chew the skin." + dish +
            " The one case where the answer is cook it: if raw apple or pear makes your mouth "
            "itch or tingle, heat settles that - stewed, baked or in a crumble the protein that "
            "does it is broken down, and peeled is usually fine too.")


def _bruise_reply(memory, reading):
    """A bruise on fruit is a knock, not a germ, and the fruit is still food.

    The banana is the one people ask about and the one where the bruise makes it sweeter, so it
    gets its own sentence; the rest share the oxidation explanation and the mould line.
    """
    said = (reading.get("clean") or "").lower()
    if "banana" in said:
        return ("A bruised banana is fine to eat: the bruise is the flesh knocked and oxidising, "
                "not rot, and a brown-spotted banana is sweeter because the starch has turned to "
                "sugar, which is why it is the one for banana bread. Cut out a soft black patch "
                "if you do not like the look of it, and bin the fruit only if the skin has split "
                "and it smells fermented or has mould on it.")
    return ("A bruise on fruit is a knock, not spoilage: the cell walls are broken and the flesh "
            "browns as it oxidises, which is why an apple or a peach browns where it was dropped. "
            "Cut the patch out if the texture bothers you, or eat it - the rest of the fruit is "
            "unchanged. Bin it only when the bruise is wet and sour-smelling or there is mould, "
            "because a soft bruise is the way in for rot.")

ENTRIES = [
    # How much juice one fruit gives is a yield question, not a method one: "how much juice is in
    # one lemon" was reaching the squeezing method, and then the sugar-in-juice fact, and neither
    # of those is the number the cook wants.
    entry("juice-yield",
          (("much juice", "juice in", "juice from", "how many lemons",
            "how many limes", "how many oranges", "how many grapefruit", "cup of juice",
            "tablespoons of juice", "ml of juice"),
           CITRUS + ("how much", "how many", "much", "many", "cup", "cups", "tablespoon",
                     "tablespoons", "ml")),
          "A lemon gives about 3 tablespoons of juice, 45ml, and a lime about 2, 30ml. A big "
          "orange gives about half a cup (120ml) and a small one a third of a cup; a grapefruit "
          "gives about two thirds of a cup. So a cup of lemon juice is four or five lemons, and "
          "rolling them hard on the counter before squeezing gets a little more out of each.",
          # the method row is the answer to a line that asks how to get it out, and "how do i get
          # the juice out of a lime" was reaching these numbers instead
          avoid=("get the juice out", "get the juice", "get more juice", "get the most juice",
                 "squeeze", "squeezing", "juice a", "juice an", "juice the", "how do i juice")),
    entry(
        "prepare-fruit",
        (tuple(word for words, _method in FRUIT_METHODS for word in words),
         PREP_WORDS + JUICE_WORDS),
        _fruit_prep,
        # A pineapple on a pizza is an opinion, a coconut shell in a curry is a complaint, and a
        # mango in a chutney, peaches in a crumble and lemons in a cake are somebody else's answer.
        avoid=("pizza", "pizzas", "hawaiian", "curry", "chutney", "crumble", "tart", "cake",
               "shell went in", "shell in", "grow", "growing", "tree", "trees", "plant", "plants",
               "buy", "buying", "price", "cost", "shop", "supermarket", "ripe", "ripen",
               "ripening", "smoothie", "juice bar", "how many calories", "healthy", "frozen",
               # a cherry tomato and a plum tomato are tomatoes, and tomato-peel holds them
               "tomato", "tomatoes",
               # keeping a cut one is avocado-keeping's answer, and "cut" is in both keys.
               # Phrases, not bare words: the matcher reads "stone" as a slip of "store", so a
               # bare "store" in avoid took "how do i stone a peach" off this row.
               "how do i store", "how do i keep", "how do you store", "how do you keep",
               "store a cut", "keep a cut", "keeping it", "store it", "keep it", "goes brown",
               "going brown", "stays green", "stay green",
               # A hardness said with the stone in it is a ripeness complaint, not the method:
               # "my avocado is hard as a stone" and "my mango is hard as a stone" were both the
               # knife answer, because the stone is how hard the fruit is. The stone asked as a
               # method still reaches this row, so "how do i stone a peach" is untouched.
               "hard as a stone", "hard as stone", "hard as stones", "hard as a rock",
               "hard as rocks", "rock hard", "rock-hard", "still hard", "so hard", "too hard",
               "hard as", "unripe", "not ripe", "nowhere near ripe", "sour and hard",
               "firm as a stone", "like a stone"),
        ask=PREP_WORDS + JUICE_WORDS,
        # the cut-avocado-keeping card holds "cut" and "avocado" too, and the method is the answer
        # to a person holding a knife, so this row wins the tie.
        bias=1,
    ),
    # Whether the skin is food is not the method, and "can i eat the skin of a kiwi" was a shrug
    # on main: the peeling row is keyed on how to get the skin off, so the question of leaving it
    # on reached nothing. The fruits whose skin people ask about are the ones with a skin worth
    # asking about - a kiwi, a peach, a plum, an apple, a pear and a grape.
    entry("fruit-skin-edible",
          (("kiwi", "kiwis", "kiwifruit", "peach", "peaches", "plum", "plums", "apple",
            "apples", "pear", "pears", "grape", "grapes"),
           ("skin", "skins", "peel"),
           ("eat", "eating", "edible", "safe", "ok", "okay", "have to", "need to", "should i",
            "can i", "do i", "with the skin", "leave the skin", "unpeeled")),
          _skin_reply,
          # the preparation row answers how to take the skin off, and a line that asks how is
          # asking that, not whether it can be eaten
          # "how do i make apple sauce" was answered here with the goodness of apple skin: the
          # fruit is the word in the line, and the sauce made of it is the sauces table's row
          avoid=("apple sauce", "applesauce", "cranberry sauce", "gooseberry sauce",
                 "how do i peel", "how to peel", "how do i cut", "how to cut", "how do i prepare",
                 # freezing the fruit is the freezer row's question: "can i freeze grapes" and
                 # "can i freeze apple" were both answered with "the skin is food" because the
                 # "can i" in this key scored higher than the freeze row
                 "freeze", "freezer", "freezing", "frozen", "defrost", "defrosting",
                 "cut a", "cut an", "cut the", "slice", "slicing", "deseed", "core",
                 "juicing", "juice", "calories", "how many", "ripe", "ripen", "buy",
                 # "healthy" is not on that list: "are apple skins healthy" was answered with a
                 # banana's calories because the word stood this row down, and the question is
                 # the skin's, which is what this card is about. The calorie and portion rows
                 # still answer "how many calories in an apple" and "are apples healthy", where
                 # no skin or peel is named.
                 # a fruit that is hard or sour is a ripeness question and the skin is not what
                 # was asked: "what can i do with hard peaches" was answered here with the skin
                 "hard", "hard as", "still hard", "rock hard", "unripe", "not ripe", "sour",
                 "tasteless", "no flavour", "no flavor", "soften", "softer",
                 "price", "grow", "growing", "tree", "allergy", "allergic", "reaction",
                 # A mouth that itches or tingles after raw fruit is the oral allergy answer, and
                 # "wash it and eat it as it is" is the opposite of it: "can i eat apples cooked
                 # if they itch raw" was answered here with the case for the skin.
                 "itch", "itches", "itching", "itchy", "tingle", "tingles", "tingling",
                 "rash", "rashes", "hives", "raw", "sore mouth", "mouth is sore",
                 # how long a fruit bakes is a cooking clock, not the skin: "how long do i bake
                 # apples for" was answered "yes, eat the skin" because the row keys "do i" and
                 # the fruit, and a baking line carries both
                 # "bake" as a bare word would also stand this row down for "can i eat the skin
                 # on a baked apple", which is the skin question: the forms below are the ones a
                 # request to cook takes, and "a baked apple" carries none of them
                 "oven", "cook", "cooked", "cooking", "do i bake", "to bake", "bake them",
                 "bake it", "bake a", "bake an", "bake the", "bake for", "how long to bake",
                 "bake at", "roast", "roasted", "roasting", "grill", "grilled", "poach",
                 "poached", "stew", "stewed", "microwave",
                 "how long", "minutes", "temperature", "gas mark",
                 # how long a fruit keeps is the keeping row's question, and this row was
                 # answering "how do i keep apples fresh" with the case for the skin: the fruit
                 # and the "do i" are both in a keeping line.
                 "keep", "keeps", "keeping", "store", "stores", "storing", "storage", "fresh",
                 "fresher", "freshest", "last", "lasts", "lasting", "fridge", "counter",
                 "going off", "gone off", "bruise", "bruised", "bruises",
                 "shrivel", "shrivelled", "wrinkled", "mouldy", "mould", "moldy", "mold",
                 # who is eating it changes the answer: a pregnant person asking about a kiwi
                 # gets the list of foods to avoid, and a grape fed to a dog is the vet's line
                 # and the animal is not always a dog or a cat: "can guinea pigs eat grapes" and
                 # "can rabbits eat apples" were both this card, with the fruit-skin answer, when
                 # the answer belongs to the small-pet food row that knows what shuts a kidney
                 # and what is only sugar. The whole pet list, not the two everybody remembers.
                 "pregnant", "pregnancy", "breastfeeding", "dog", "dogs", "cat", "cats",
                 "kitten", "puppy", "pet", "pets", "vet", "toddler", "baby", "weaning",
                 # How to keep a cut one from browning is the row below, and "apple" plus
                 # "do i" was this one: "how do i stop a cut apple going brown" was answered
                 # with the case for eating the skin.
                 "going brown", "goes brown", "go brown", "gone brown", "turn brown",
                 "turns brown", "turning brown", "brown quickly", "stop it going",
                 "stop them going", "from browning", "from going brown", "not go brown",
                 "rabbit", "rabbits", "bunny", "bunnies", "hamster", "hamsters", "guinea pig",
                 "guinea pigs", "guineapig", "guineapigs", "budgie", "budgies", "parrot",
                 "parrots", "tortoise", "tortoises", "horse", "horses", "pony", "ponies",
                 "chinchilla", "chinchillas", "gerbil", "gerbils", "ferret", "ferrets",
                 # "Apple" the company is not an apple: "how do i change my apple id password"
                 # was answered with the case for eating the skin, because "apple" is in the key
                 # and it beat the apple-account card on row order at the same score. The brand
                 # words stand this row down, so the technology rows answer their own lines and
                 # every question about fruit keeps this one.
                 "apple id", "apple account", "apple watch", "apple pay", "apple music",
                 "apple tv", "apple store", "applecare", "apple care", "apple support",
                 "apple pencil", "apple inc", "icloud", "iphone", "ipad", "macbook",
                 "airpods", "app store", "apple id password", "apple id locked",
                 # and choosing one is the picking row's question, not the skin's: "how do i
                 # pick a good apple" was answered with the case for eating the skin, and that
                 # test is red on main. The skin is not what was asked, and "are apple skins good
                 # for you" carries none of these.
                 "pick a", "pick the", "how do i pick", "how to pick", "which ones", "which one",
                 "which apple", "which apples", "choose", "choosing", "best apple", "best apples",
                 "good apple", "good apples", "ripe one", "ripest",
                 # A fruit asked for as a time in the oven is a cooking question, and the skin
                 # is not what was asked: "how long do i bake apples for" was this card ("apple
                 # and pear skin is the best part of it") while the baked-apples row in
                 # cooking_entries.py holds the 25 to 30 minutes it wanted. The time and the heat
                 # are what make the line a cooking line, so those words stand this row down and
                 # a line about the skin still keeps it: "can i eat the skin on a baked apple" is
                 # still the skin answer.
                 "how long", "how many minutes", "how long in", "how hot", "gas mark",
                 "what temperature", "temperature", "degrees", "180c", "200c", "mins"),
          bias=1),
    # "can i eat a banana with a bruised skin" was answered with the card about a bruise on your
    # own arm: fruit bruises are the fruit domain's, and the answer is that the fruit is food.
    entry("bruised-fruit",
          (("banana", "bananas", "apple", "apples", "pear", "pears", "peach", "peaches", "plum",
            "plums", "avocado", "avocados", "mango", "mangoes", "fruit", "nectarine",
            "nectarines", "tomato", "tomatoes"),
           ("bruised", "bruise", "bruises", "brown spot", "brown spots", "black spot",
            "black spots", "brown patch", "brown patches", "brown inside", "gone brown",
            "went brown", "soft spot", "soft spots", "knocked", "dropped", "dented")),
          _bruise_reply,
          # a bruise on a person is the health answer, and a bruise on a knee or a shin is not a
          # fruit question at all
          avoid=("my leg", "my arm", "my knee", "my shin", "my thigh", "my back", "my ribs",
                 "my hand", "my foot", "my ankle", "my wrist", "my shoulder", "my head",
                 "i fell", "i bumped", "fell over", "bumped into", "after a fall", "hit my",
                 "icing", "ice it", "swollen", "swelling", "child", "toddler", "baby",
                 "bleeding", "nosebleed", "growing", "grow", "tree", "plant", "tree is",
                 # a fruit still on the tree that drops is the tree's own question, not a bruise
                 "dropping", "dropping fruit", "falling off", "falls off", "off the tree",
                 "on the tree", "june drop",
                 "why do i bruise", "bruise easily", "bruises easily", "recipe", "bake",
                 "bread", "muffin", "loaf"),
          # the skin question for the same fruit is the row above, and "can i eat a bruised pear"
          # was landing on it: a line that names a bruise is about the bruise.
          bias=4),
]

