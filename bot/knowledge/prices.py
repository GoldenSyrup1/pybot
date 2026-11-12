"""What an everyday thing costs: the price of a pint, a loaf, a bottle of wine.

The answers lane owns this domain. A price on a shelf moves, so nothing here is a live figure -
but "how much is a pint of beer" and "how much does a loaf cost" had no card at all, and the rows
that took them answered a different question: the 14-units-a-week limit for the pint, a wine
pairing for the bottle, and "Prices move too fast for me to know. A quick look at the seller's own
site will beat any guess" for the milk, which is a shop rather than a price.

What is held here is the ordinary range, the year it was written, and what makes the top of the
range, because that is the part that stays true: a supermarket pint is a third of a pub one and
London is dearer than a small town. A line that asks how much it *weighs*, how much goes *in* a
cake, or how much is *too much* is another domain's question and this one stands down.
"""
import re

from .lookup import entry

ANSWERS = ("money",)

# The prices were last counted in 2025 (UK). One family per line of the table, the item named
# first so "a pint of lager" and "a lager" both find the beer.
_ITEMS = (
    (("pint of beer", "pint of lager", "pint of bitter", "pint of ale", "pint of cider",
      "pint of guinness", "pint of stout", "a pint", "beer", "lager", "bitter", "cider", "ale",
      "stout"),
     "A pint is about £4 to £5.50 in most pubs and £6 to £7.50 in London and the big cities, so "
     "£5.50 is a fair average to budget. A 500ml bottle or can from a supermarket is £1.50 to "
     "£2.50, and a four-pack £5 to £7."),
    (("bottle of wine", "wine", "red wine", "white wine", "rose", "prosecco", "champagne"),
     "A drinkable supermarket bottle is £6 to £8 and a step up is £10 to £15; a pub or restaurant "
     "charges £18 to £26 for the same sort of bottle. A small 187ml bottle is £2.50 to £3.50."),
    (("pint of milk", "milk", "bottle of milk"),
     "About 70p a pint, so a two-pint bottle is £1.25 to £1.45 and a four-pint one £1.70 to £2. "
     "The filtered and the organic sorts cost half as much again, and a corner shop is dearer than "
     "a supermarket."),
    (("loaf", "loaf of bread", "bread", "sliced bread"),
     "£1.20 to £1.60 for a supermarket own-brand white or wholemeal loaf, £2.50 to £4 for a "
     "sourdough or a bakery loaf, and about £1 for the value line."),
    (("eggs", "half a dozen eggs", "dozen eggs", "box of eggs"),
     "£1.50 to £2.20 for six free-range eggs and £2.50 to £3.50 for twelve, with large and organic "
     "at the top of that."),
    (("lentils", "lentil", "red lentils", "bag of lentils", "dried lentils", "split peas",
      "dried beans", "chickpeas", "pulses"),
     "Dry red lentils are £1 to £1.50 for 500g and £2 to £2.50 a kilo, and chickpeas and dried "
     "beans are much the same. That is why a lentil curry is one of the cheapest dinners there "
     "is: a kilo is about ten portions."),
    (("potatoes", "potato", "kilo of potatoes", "bag of potatoes", "new potatoes", "spuds"),
     "About 60p to £1 a kilo for white potatoes, so a 2.5kg bag is £1.50 to £2.50. New potatoes "
     "and the small salad ones are £1.50 to £2.50 a kilo, and a baking potato about 25p to 40p "
     "each."),
    (("whole chicken", "whole chickens", "chicken", "a roasting chicken"),
     "£4 to £6 for a whole chicken of about 1.5kg to 2kg, and £3.50 to £5 for a smaller one. "
     "That is four to six portions of meat plus a pot of stock, which is why it costs less per "
     "meal than the same weight of breasts."),
    (("stamp", "stamps", "first class stamp", "second class stamp", "book of stamps",
      "book of first class stamps"),
     "About £1.70 for a first class stamp and 87p for a second class one in 2025, and a book of "
     "eight first class is about £13.50. A large letter costs more - about £2.70 first class."),
    (("coffee", "flat white", "latte", "cappuccino", "cup of coffee", "takeaway coffee"),
     "£3 to £3.80 for a flat white or a latte in a chain and £3.50 to £4.50 in an independent "
     "cafe, with oat or soya milk often 30 to 50p extra."),
    (("tea", "cup of tea", "pot of tea"),
     "£2.50 to £3.50 for a pot of tea in a cafe, and about 3p a cup made at home from a £2.50 box "
     "of 80 bags."),
    (("cigarettes", "fags", "packet of cigarettes", "pack of cigarettes", "twenty cigarettes"),
     "About £14 to £16 for 20 cigarettes in 2025, and £5 to £6 for a 30g pouch of rolling tobacco."),
    (("punnet", "punnet of strawberries", "strawberries", "raspberries", "blueberries",
      "berries", "punnet of berries"),
     "A 227g punnet of strawberries is £2 to £2.50 in summer and £3 to £4 out of season, and a "
     "punnet of raspberries or blueberries £2 to £3. British berries in June and July are about "
     "half the price of the imported ones in January."),
    (("fish and chips", "fish supper", "chippy", "chip shop", "cod and chips",
      "haddock and chips", "sausage supper"),
     "£9 to £12 for fish and chips from a chip shop and £12 to £16 in London and the big cities, "
     "with a sit-down restaurant a few pounds more than that. A small or pensioner's portion is "
     "£6 to £8, and mushy peas about £1.50."),
    (("takeaway", "takeaway curry", "chinese takeaway", "indian takeaway", "pizza delivery",
      "delivered pizza", "a pizza", "kebab"),
     "£9 to £13 for one takeaway main - a curry, a Chinese dish, a large pizza - and £15 to £25 "
     "for a delivery for two once the sides and the fee are on it. Collecting it yourself saves "
     "the £3 to £5 delivery fee."),
    (("bread and milk", "weekly shop", "food shop", "groceries"),
     "The average household spends about £70 to £80 a week on food shopping, from £40 for one "
     "person cooking from scratch to £150 for a family that buys ready meals."),
)

_PRICE = re.compile(
    r"\b(?:how much (?:is|are|does|do|would)|what (?:does|do|is|are)|price|prices|cost|costs|"
    r"cheaper|cheapest|expensive|going rate|these days|nowadays|average)\b")
# A price is not a quantity, a method or a limit: "how much milk goes in a cake", "how much does a
# pint of milk weigh", "how much beer is safe" are three other questions.
_NOT_A_PRICE = re.compile(
    r"\b(?:weigh|weighs|grams?|g\b|ml\b|millilitres?|litres?|cups?|tablespoons?|teaspoons?|"
    r"recipe|recipes|in a cake|for a cake|per person|serves?|servings?|calories|units?|"
    r"too much|safe|limit|how many|should i drink|drink a week|a day|make|making|grow|"
    r"keep|keeps|last|lasts|freeze|store|storing|goes in|do i need|is in)\b")
# "how much is a pint of milk" is this row; "how much is my water bill" is a bill and belongs to
# the row that reads the meter.
_NOT_AN_ITEM = re.compile(
    r"\b(?:bill|bills|meter|tariff|standing charge|contract|insurance|premium|tax|rent|"
    r"mortgage|salary|wage|wages|pension|fine|postage|delivery|shipping|vets?|"
    r"prescription|ticket|flight|hotel|rental|deposit|lesson|course|subscription|"
    r"mobile|broadband|energy|gas|electric|electricity|water bill|council|"
    # a stamp is a thing on a shelf with a price on it. A parcel, a letter and the post office
    # counter are the posting question, and that row already answers them.
    r"send|sending|sent|parcel|parcels|letter|letters|post office|recorded|tracked|"
    # the price of chicken in a dish or a cut is not the price of a whole bird, and the recipe
    # rows own those lines: "how much is a chicken sandwich" was not a shopping question.
    r"sandwich|sandwiches|soup|curry|pie|nuggets|wings|thighs|breasts|breast|fillet|"
    r"drumsticks|kebab|kiev|kievs|goujons?|burgers?|strips|wrapping?|for dinner|for tea|"
    # the UK figure is the wrong answer to a price asked in another country
    r"ireland|irish|dublin|america|australia|canada|spain|france|germany)\b")


def _the_text(reading):
    """The line as it was said, from the reading every entry is handed."""
    if not isinstance(reading, dict):
        return ""
    text = reading.get("clean") or reading.get("text")
    if not text:
        words = reading.get("words")
        text = " ".join(words) if isinstance(words, (list, tuple)) else ""
    return str(text).lower()


def _a_price_was_asked(reading, memory=None):
    """True when the line asks what an everyday thing costs, and nothing else about it."""
    text = _the_text(reading)
    if not text or not _PRICE.search(text):
        return False
    if _NOT_A_PRICE.search(text) or _NOT_AN_ITEM.search(text):
        return False
    return True


def _the_item_reply(memory, reading):
    """The price of the one item the line names, or the general line when it names several."""
    text = _the_text(reading)
    said = []
    named = []
    for names, reply in _ITEMS:
        hit = [name for name in names if re.search(r"\b" + re.escape(name) + r"\b", text)]
        if hit:
            named.append(hit)
            said.append(reply)
    if not said:
        return None
    # "how much is a pint of milk" names the milk and the bare "a pint" as well, so a name that
    # sits inside a longer name that also matched is not a second item.
    longest = [max(hit, key=len) for hit in named]
    words = [set(name.split()) - {"a", "an", "the"} for name in longest]
    said = [reply for reply, mine in zip(said, words)
            if not any(mine < other for other in words)]
    if not said:
        return None
    if len(said) > 1:
        return "As a rough guide, in 2025: " + " ".join(said[:3])
    return said[0] + " Those are 2025 prices, and they are the sort of thing that moves."


ENTRIES = [
    entry("everyday-prices",
          (("how much is", "how much are", "how much does", "how much do", "price", "prices",
            "cost", "costs", "cheaper", "going rate", "these days", "nowadays"),
           ("a pint", "beer", "lager", "cider", "wine", "prosecco", "milk", "loaf", "bread",
            "eggs", "coffee", "latte", "flat white", "cup of tea", "tea", "cigarettes", "fags",
            "food shop", "weekly shop", "groceries", "strawberries", "berries", "punnet",
            "fish and chips", "fish supper", "chippy", "takeaway", "pizza", "kebab",
            "lentils", "lentil", "chickpeas", "potatoes", "potato", "spuds", "chicken",
            "stamp", "stamps")),
          _the_item_reply,
          # The rows that were answering these lines name the same things for other questions, so
          # this one has to win when it is willing to answer and stand down when it is not.
          bias=3,
          guard=_a_price_was_asked,
          # a drink's units, a wine pairing, a shop's own offer and a bill are four other cards
          avoid=("units", "how many units", "safe", "limit", "too much", "cut down", "reduce",
                 "calories", "goes with", "pair", "pairing", "match", "which wine",
                 "with pizza", "with curry", "with steak", "offer", "offers", "deal", "deals",
                 "supermarket offer", "loyalty", "coupon", "voucher",
                 "weigh", "grams", "ml", "recipe", "in a cake", "for a cake", "per person",
                 "serves", "how many", "make", "bake", "grow", "keep", "freeze",
                 # a stamp is on the shelf with the milk: the word was in this list while the
                 # posting counter owned it, and "how much is a stamp" was left with the punt.
                 "bill", "bills", "meter", "tariff", "rent", "insurance", "tax")),
]
