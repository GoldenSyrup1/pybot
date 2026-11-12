"""Drink: which bottle goes with the food that is named.

The answers lane owns this domain. A pairing is a fact about a food, not a sentence about a
person, so the key is the word for wine crossed with the words that ask the pairing question,
and the reply is chosen from the food the line names. The cooking domain already holds a
`wine-with-food` row that answers every pairing question with one paragraph on weight ("a light
white with fish or chicken, a fuller red with red meat"); that rule is right when the line names
no food and useless when it names one, because "what wine goes with pizza" wants a bottle. This
domain therefore answers only the lines that name a food or a meal, and returns None otherwise,
so the cooking row keeps the rest.

Nothing here is ageing or priced: the wine is named by grape or region, which does not go out of
date the way a bottle and a price on a shelf does.
"""
import re

from .lookup import entry

ANSWERS = ("food-and-drink",)

# One pair per family of food, in the order a line usually names them. The first word that
# appears in the line decides, so the list runs from the most specific food to the least:
# "chicken curry" is a curry, and both words are in the line.
_PAIRS = (
    (("fish", "salmon", "trout", "prawn", "prawns", "seafood", "cod", "haddock", "sushi",
      "shellfish", "mussels", "scallops", "whitebait", "sea bass"),
     "A dry white is the safe pair: Sauvignon Blanc, Picpoul, Albarino or a dry Riesling. "
     "Salmon and trout take a light red such as Pinot Noir just as well."),
    (("curry", "curries", "tikka", "masala", "balti", "thai", "korma", "jalfrezi", "madras",
      "chilli con carne", "tacos", "burrito", "mexican", "salsa", "spicy", "hot wings",
      "indian", "biryani", "kebab", "falafel"),
     "An off-dry Riesling or a Gewurztraminer: a little sweetness cools the heat. Lager or a "
     "pale ale work just as well, and a big oaky red is the one to avoid."),
    (("chinese", "stir fry", "stir-fry", "noodles", "szechuan", "sichuan", "dumplings",
      "spring rolls", "sushi rice"),
     "Riesling or a dry rose, or a pale ale with the fried things: sweetness suits the soy and "
     "the spice, and a heavy red fights both."),
    (("steak", "beef", "lamb", "venison", "game", "burger", "burgers", "casserole", "stew",
      "roast beef", "brisket", "ribs"),
     "A red with some grip: Malbec, Cabernet Sauvignon, Syrah or a Rioja. Lamb likes claret, "
     "and a slow-cooked stew likes the same reds."),
    (("chicken", "turkey", "pork", "veal", "roast chicken", "sausage", "sausages", "ham"),
     "Chicken and pork take either: a Chardonnay or white Burgundy, or a light red such as "
     "Pinot Noir or Grenache. Roast chicken with a red is the usual choice in a pub."),
    (("pasta", "pizza", "lasagne", "lasagna", "bolognese", "ragu", "tomato", "tomatoes",
      "meatballs", "parmigiana"),
     "Sangiovese or Chianti: the acidity in the wine meets the tomato, and a heavy oaky red "
     "tastes flat next to it."),
    (("cheese", "cheeses", "cheddar", "brie", "blue cheese", "stilton"),
     "Match the weight: a crisp white with goat's cheese and a soft rind, a red with cheddar, "
     "and port or a sweet wine with blue."),
    (("chocolate", "dessert", "pudding", "cake", "trifle", "ice cream", "fruit tart"),
     "A wine as sweet as the pudding: port or Banyuls with chocolate, and a sweet Riesling or "
     "Muscat with fruit puddings. A dry red turns bitter next to sugar."),
    (("salad", "vegetarian", "veggie", "quiche", "omelette", "soup", "risotto", "pasta salad"),
     "Sauvignon Blanc, a dry rose or a light red served cool: light food wants a light wine."),
)

# A meal with no food named: "what wine with a roast dinner", "which wine with dinner". The
# weight rule is the right answer here, and it is the one the cooking row gives, so this domain
# gives it too and keeps the answer in one place per line.
_MEALS = ("dinner", "dinner party", "meal", "lunch", "supper", "christmas", "barbecue", "bbq",
          "st patricks", "takeaway", "takeout")

_WEIGHT = ("Match the weight of the food: a dry white with fish or a light starter, a red with red "
           "meat and anything tomatoey, and a touch of sweetness with spicy food. If a bottle is "
           "all you have, a dry rose or a medium red sits happily with most things on the table.")


def _named(text, words):
    """Whether the line names one of these foods, as whole words."""
    for word in words:
        pattern = r"(?<![a-z0-9])" + re.escape(word) + r"(?:s|es)?(?![a-z0-9])"
        if re.search(pattern, text):
            return True
    return False


def _wine_pair(memory, understood):
    """The bottle that goes with the food named, or the weight rule for a meal with no food.

    Returns None when the line names neither, so a bottle to buy, a gift, a unit count and a
    wine stain all stay with the rows that answer them.
    """
    text = (understood or {}).get("clean") or (understood or {}).get("text") or ""
    text = str(text).lower()
    if not text:
        return None
    for foods, answer in _PAIRS:
        if _named(text, foods):
            return answer
    if _named(text, _MEALS):
        return _WEIGHT
    return None


# "red or white with chicken" asks the pairing question without ever saying the word wine, and
# "what should i drink with fish" asks it with "drink". Both are here rather than in a second
# row, so one row owns the whole question.
ENTRIES = [
    entry("wine-with-the-food",
          (("wine", "wines", "red or white", "white or red", "drink with", "drinking with"),
           ("goes with", "go with", "goes down", "pair", "pairs", "pairing", "match", "matches",
            "with", "for", "best", "which", "serve", "serving", "have", "have with",
            "should i have", "bring", "take", "bottle", "red or white", "recommend")),
          _wine_pair,
          # The cooking domain's one-paragraph weight rule answers the same lines, so this row
          # has to outrank it when it is willing to answer; when it declines, that row answers.
          bias=4,
          # A bottle to buy, a price, a gift or a party bottle is the shopping side of wine; the
          # open bottle, the units and the health lines are three other rows; and a wine in the
          # pan is a method, not a pairing.
          avoid=("buy", "buys", "buying", "bought", "cheap", "cheaper", "cheapest", "money",
                 "tenner", "tenners", "value", "spend", "budget", "afford", "supermarket",
                 "shop", "shops", "shopping", "offer", "offers", "deal", "deals", "price",
                 "gift", "present", "birthday", "wedding", "bring to",
                 "open", "opened", "unopened", "keep", "keeps", "keeping", "last", "lasts",
                 "how long", "left over", "leftover", "vinegary", "gone off", "corkscrew",
                 "opener", "fridge", "chill", "chilled", "cold", "temperature", "decant",
                 "units", "unit", "limit", "safe", "too much", "a day", "every day", "week",
                 # a medicine named next to a drink is the alcohol-and-medicine question: "is it
                 # ok to drink with paracetamol" was answered with a wine pairing
                 "paracetamol", "ibuprofen", "painkiller", "painkillers", "antibiotic",
                 "antibiotics", "penicillin", "amoxicillin", "metronidazole", "tablets",
                 "medicine", "medication", "pills", "prescription", "antihistamine",
                 "antidepressant", "statins", "codeine",
                 "pregnant", "alcohol free", "alcohol-free", "non alcoholic", "sober",
                 "hangover", "calories", "good for", "bad for", "health", "healthy",
                 "stain", "stains", "spill", "spilled", "spilt", "sofa", "carpet", "shirt",
                 "cook", "cooks", "cooking", "cooked", "recipe", "recipes", "sauce", "stew",
                 "casserole", "marinate", "marinade", "deglaze", "substitute",
                 "instead of", "glaze", "gravy", "oven", "bake")),

# The module answered the pairings and nothing else, so a drink to make at home was a shrug: "how
# do i make lemonade", "how do i make iced tea" and "how do i froth milk for coffee" were all
# "I don't know enough to answer that honestly", "how do i make mulled wine" was "I'm not sure
# about that one", and "how do i make hot chocolate" reached the cut-the-liquid-sugar card, which
# is an answer about a diet. These four rows make the drink; a bottle to buy, a unit count and a
# machine that has broken each stay with the row that answers them.
entry("lemonade-and-iced-tea",
      # iced tea was in this key until #5072 landed its cold-brew answer, which is the better one:
      # the row went back to lemonade and squash, the two drinks nothing else made.
      # a bare "squash" is the vegetable, and "how do i make a squash" is the roast answer;
      # only the fruit ones in front of it are the drink
      (("lemonade", "homemade lemonade", "cordial", "orange squash", "lemon squash",
        "blackcurrant squash", "lime cordial"),
       ("make", "making", "made", "how do i", "how to", "recipe", "homemade", "from scratch",
        "what goes in")),
      "Squeeze three lemons into 100g of sugar dissolved in 100ml of just-boiled water, top it up "
      "with a litre of cold water and taste it - a pinch of salt makes it taste more of lemon, "
      "not less. A squash is the same drink from a bottle of cordial, and a sprig of mint or a "
      "sliced lemon in the jug is what a pub does. It keeps two days in the fridge.",
      # a bottle to buy, the sugar in a fizzy drink and a stain are three other rows
      avoid=("buy", "buys", "shop", "supermarket", "price", "cost", "offer", "brand",
             "calories", "how much sugar", "healthy", "good for", "bad for", "stain",
             "stains", "spill", "carpet", "fizzy", "coke", "cola",
             "wine", "beer", "gin", "vodka", "cocktail", "pint", "alcohol"),
      bias=2),
entry("mulled-wine",
      (("mulled wine", "gluhwein", "mulled cider", "wassail", "mulled"),
       ("make", "making", "recipe", "homemade", "how do i", "how to", "what goes in")),
      "Warm a bottle of red with two tablespoons of sugar, a sliced orange, a cinnamon stick, two "
      "star anise and four cloves: keep it at a bare shiver for 15 minutes and never let it boil, "
      "which takes the alcohol and the fruit out of it. A splash of brandy at the end makes it "
      "stronger, and mulled cider is the same drink made with cider and no sugar.",
      # the bottle to buy, the units and the alcohol-free question are other rows
      avoid=("buy", "shop", "price", "cost", "gift", "present", "units", "unit", "limit",
             "pregnant", "alcohol free", "alcohol-free", "non alcoholic", "sober", "hangover",
             "how long does it keep"),
      bias=2),
entry("hot-chocolate",
      (("hot chocolate", "hot cocoa", "drinking chocolate", "cocoa"),
       ("make", "making", "recipe", "how do i", "how to", "proper", "best", "what goes in")),
      "Warm 200ml of milk and melt 20g of dark chocolate into it, chopped small, stirring until it "
      "is smooth - a pinch of salt makes it taste more of chocolate, not less. Cocoa powder works "
      "too: a teaspoon each of cocoa and sugar made into a paste with a little cold milk first, so "
      "it does not go lumpy. Keep it under a simmer, because milk that boils tastes cooked.",
      # the calories, the caffeine and a stain are three other answers, and a dairy-free drink is
      # a swap rather than a recipe: "how do i make hot chocolate without milk" wants what to use
      # instead, which the dairy-free row already answers
      avoid=("calories", "calorie", "diet", "lose weight", "caffeine", "sleep", "before bed",
             "stain", "stains", "spill", "buy", "brand", "mug", "healthy", "good for",
             "without milk", "no milk", "dairy free", "dairy-free", "oat milk", "plant milk",
             "almond milk", "soy milk", "vegan", "lactose"),
      bias=2),
# Water hardness is a food-and-drink question and no row answered the health half of it: "is
# hard water bad for you" was answered with the descaling recipe (home.limescale-why keys the
# words "hard water"), and "why is my water hard" was the dry-eye card, because "water" is the
# tear film's word.
entry("hard-water",
      (("hard water", "water is hard", "water hard", "water is so hard", "water so hard",
        "water hardness", "hardness", "water is very hard",
        "hard and soft water", "soft water", "chalky water",
        # Not "limescale in my water": this row held the word and it cost `home.limescale` the
        # answer to "what can i do about limescale", which came back as nothing at all
        # (`tests/test_a_plain_limescale_line_keeps_its_answer.py` is red on main `3ae8d520`
        # because of it, bisected to `51211851`). "hard water" and its own phrases carry every
        # line this row gained, so the word goes back to the row that owns it.
        "minerals in the water", "minerals in my water"),
       ("bad for you", "bad for", "safe", "safely", "ok", "okay", "fine", "drink", "drinking",
        "drank", "harmful", "dangerous", "healthy", "health", "kidney", "kidneys", "stones",
        "skin", "eczema", "dry", "why", "cause", "causes", "softener", "soften", "filter",
        "bottled", "baby", "formula", "milk", "boil", "calcium", "safe to drink")),
      ("Not bad for you: the calcium and magnesium that make water hard are minerals you get from "
       "food anyway, mains water is tested to the same standard whatever its hardness, and the "
       "studies find no link between hard water and kidney stones - some find slightly fewer "
       "stones in hard-water areas. It is hard because it has come through chalk or limestone, "
       "which is why the same country has soft water in the west and hard water in the south "
       "east. What it does do is leave a chalky film on taps, kettles and shower glass, lather "
       "soap and shampoo less so you use more of them, and feel drier on the skin - a filter jug "
       "or a scale reducer is enough for most homes. The one to know about is a baby's bottle: a "
       "water softener swaps the calcium for sodium, so make formula with unsoftened mains water, "
       "boiled once and cooled."),
      # the descaling recipe, the kettle and the appliance are other answers, and so is the water
      # bill or the contract for it
      avoid=("kettle", "kettles", "descale", "descaling", "descales", "scale", "scaled",
             "limescale", "shower", "showerhead", "shower head", "taps", "marks", "stains",
             "iron", "steam iron", "washing machine", "dishwasher", "bill", "bills", "meter",
             "supplier", "account", "contract", "cancel", "standing charge", "swimming",
             "pool", "fish", "aquarium", "pond", "plant", "plants", "garden"),
      bias=1),

entry("froth-milk",
      (("froth", "frothed", "frothing", "frother", "frothy milk", "milk foam", "steamed milk",
        "microfoam", "foam on my coffee"),
       ("milk", "coffee", "how do i", "how to", "without", "no machine", "jar", "cafetiere",
        "french press", "latte", "cappuccino")),
      "Cold milk in a jar with a lid, shaken hard for 30 seconds and then 30 seconds in the "
      "microwave, gives a real foam with no machine, and a French press pumped up and down 15 "
      "times does the same. Whole milk froths best because the fat holds the bubbles, and stop "
      "heating at about 60 to 65C - past that the foam collapses and the milk tastes scalded.",
      # a machine to buy, clean or descale is another row, and so is the coffee itself
      # "without a machine" is this row's own question, so the fence is the machine's problems and
      # not the word "machine": a bare `machine` here sent "how do i froth milk without a machine"
      # to the buttermilk substitute, which is what a wet ingredient is for.
      avoid=("coffee machine", "my machine", "machine is", "machine not", "machines", "buy",
             "descale", "limescale", "clean", "cleaning", "broken", "not working",
             "coffee shop", "latte art", "stain", "bean", "beans", "grinder"),
      bias=2),
]
