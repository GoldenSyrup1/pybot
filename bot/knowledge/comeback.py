"""Two "start again" questions: running and cycling, the two people come back to most.

Both had an answer, and both were the wrong one. A line about wanting to run again reached the
coming-back-after-illness rule, so a person asking how to restart was told what to do if they had
flu. A line about wanting to cycle again reached the menstrual-cycle entry, and "start again" on
its own reached a laptop that keeps asking to restart.

  how do i start running again                    the illness rule ("above the neck and no
                                                  temperature")
  i used to run and want to start again           "An update is waiting and will keep asking"
  how do i start cycling again                    nothing at all
  i stopped cycling and want to start again       "An update is waiting and will keep asking"
  i want to get back on my bike                   "What's stopped it happening so far?"

Every one of them is a return, not a first go and not an illness, so the return words in the key
are what the row asks for: without "again", "back" or "used to", a plain "how do i start running"
is the beginner plan that already answers it well.

The answer for both is the same shape: less than you think, every other day, add a little each
week, and no speed for six weeks. That is what makes a comeback stick, and it is what neither the
illness rule nor a laptop update says.
"""

import re

from .lookup import entry

ANSWERS = ("fitness", "sport")

# The words that make a line a return rather than a first go. One of them has to be there, or the
# row stands down for the beginner plans that already answer "how do i start running".
# "start" and "starting" are deliberately not here. A first go is a different question with its
# own plan, and a bare "how do i start running" was being pulled in by them.
RETURN_WORDS = ("again", "back on the bike", "back on my bike", "back on a bike",
                "back in the saddle", "restart", "restarting", "used to", "out of the habit",
                "lapsed", "years off", "havent", "haven't", "not run", "not ridden",
                "not cycled", "stopped running", "stopped cycling", "stopped jogging")

# A return after illness, a fever or an injury is the recovery question, and that answer exists:
# it is the one that says a week of easy effort after the fever has gone.
ILL_OR_HURT = ("ill", "illness", "sick", "sickness", "flu", "fever", "cold", "cough", "virus",
               "bug", "infection", "temperature", "chest", "hospital", "operation", "surgery",
               "hurt", "hurts", "hurting", "pain", "painful", "injury", "injured", "injuries",
               "sprain", "sprained", "tweak", "tweaked", "pulled", "knee", "knees", "shin",
               "ankle", "calf", "achilles", "back pain", "physio", "gp", "doctor", "pregnant",
               "pregnancy", "after the baby", "postnatal",
               # a bone that is cracked is not a comeback from a layoff: the recovery answer
               # belongs to the bone, and "how long till i can run again after a stress fracture"
               # was getting the run-walk plan instead of the six to eight weeks.
               # A cast is not the same word: "how long before i can run again after a cast" is a
               # comeback question, and standing the plan down for it left the cold rule answering
               # a broken leg. The fracture words cover the bone lines without it.
               "fracture", "fractured", "broken bone", "broken foot", "broken leg",
               "broken ankle")

# Things that run and are not a person. "The toilet wont stop running" is the plumbing entry's
# question, and "my phone keeps running out of battery" is none of this row's business: the word
# is the same and the subject is not a return. The row already fenced a tap, a bath, an engine and
# a car one at a time; this is the rest of the family that runs.
RUNS_BUT_IS_NOT_YOU = (
    "toilet", "cistern", "flush", "ballcock", "faucet", "sink", "drain", "plughole",
    "shower", "hose", "sprinkler", "irrigation", "boiler", "radiator", "heater",
    "aircon", "air conditioning", "fridge", "freezer", "dishwasher", "washing machine",
    "tumble dryer", "hoover", "vacuum", "dyson", "generator", "compressor",
    "app", "apps", "software", "update", "updates", "computer", "laptop", "phone",
    "tablet", "printer", "clock", "meter", "nose", "mascara", "makeup", "paint", "ink",
    "glue", "candle", "campaign",
    # A school run is a car journey with children in it, not a person running. "my boss moved my
    # shifts again and i cant do the school run" was getting the run-walk plan because "again" is
    # one of the return words and "school run" carries a "run"; the errand compounds are the same
    # shape, so they are stood down together.
    "school run", "school runs", "nursery run", "errand run", "errand runs",
    "supermarket run", "shop run", "banks run")

# Team sport again: "when can i play football again" was answered by sport.py's taster-session
# card ("look for a club that advertises a beginners' or back-to session"), because that row keys on
# a sport and "again" and its avoid words are injury nouns, so a line that says *when* but names no
# injury landed on the wrong question. Running and cycling already had a comeback card; a team
# sport is the third, and it is the one where the match is the thing people come back to too early.
# Only the sports whose natural return is training-then-match are here: the row is about the order
# of the two, and a swimmer or a runner has no match to hold back from.
TEAM_SPORTS = ("football", "rugby", "netball", "hockey", "basketball", "soccer", "gaelic",
               "lacrosse", "cricket", "squash", "badminton", "five a side", "5 a side")
# The return words the other two rows use, plus the phrases a team-sport line uses in place of
# "run again".
TEAM_RETURN_WORDS = RETURN_WORDS + ("play again", "playing again", "playing football again",
                                    "play football again", "back playing", "back to training",
                                    "training again", "back on the pitch", "back on the field")
# A club search, a match ticket and watching a game are other questions with their own answers,
# and they are what the taster-session card was written for.
CLUB_SEARCH = ("club", "clubs", "join", "joining", "near me", "taster", "trial", "trials",
               "where can i", "find a team", "find a club", "local team", "local club",
               "watch", "watching", "ticket", "tickets", "on telly", "sky sports", "fixture",
               "fixtures", "league table", "how much", "price", "cost")


def _a_return_to_team_sport(reading):
    """True when the line is the person coming back to it, not asking where to play.

    The row and sport.py's taster-session card both fit "when can i play football again" - a sport
    and "again" - and that card is the wrong answer to a when. This keeps the row to the return
    itself: the person has to be the one playing, and nothing in the line can be about finding,
    joining or watching a team.
    """
    reading = reading or {}
    said = " ".join(str(reading.get("clean") or reading.get("text") or "").split()).lower()
    if not said:
        return False
    if any(word in said for word in CLUB_SEARCH):
        return False
    return bool(re.search(r"\b(?:i|im|i'm|ive|i've|we|my)\b", said))


ENTRIES = [
# Running again: the plan is run-walk and a slow build, and the mistake a returning runner makes
# is starting where they left off.
entry("running-again",
      (("running", "run", "jogging", "jog", "5k", "10k", "parkrun", "treadmill"),
       # "running again" is in the second group as well as the ask, because it is the phrase the
       # line usually carries: "how do i start running again", "getting back into running"
       ("again", "back", "back into", "start", "starting", "restart", "restarting", "used to",
        "stopped running", "stop running", "havent run", "haven't run", "not run", "years",
        "years off", "out of the habit", "lapsed", "return", "take it up", "got back",
        "running again", "run again", "jog again", "shoes", "kit")),
      "Come back at about half of what you used to do: run-walk to start, one minute of easy "
      "jogging to two of walking, twenty minutes, three times a week, and add a minute of running "
      "a week for six weeks before you think about pace. Keep every run slow enough to talk, take "
      "a day off between them, and expect the first fortnight to feel harder than the numbers "
      "say. Sort the shoes first if yours have been in a cupboard for years - worn-out cushioning "
      "is what makes a comeback hurt.",
      bias=5,
      ask=RETURN_WORDS,
      # a return after illness or an injury is the recovery answer, and running a bath, a
      # business, a tap or a car is another answer again
      avoid=ILL_OR_HURT + RUNS_BUT_IS_NOT_YOU +
      ("bath", "tap", "water", "engine", "car", "bus", "train", "late",
             "business", "shop", "errand", "machine", "ballot",
             "class", "course", "club", "parkrun time", "marathon", "half",
             "plan", "training plan", "couch to 5k", "dog", "child", "kids")),

# Cycling again: the same shape, and the bike wants ten minutes of attention before the first
# ride, which is the part a returning cyclist does not think of.
entry("cycling-again",
      (("cycling", "cycle", "bike", "bicycle", "pushbike", "riding"),
       ("again", "back", "back into", "start", "starting", "restart", "restarting", "used to",
        "stopped cycling", "stop cycling", "havent ridden", "haven't ridden", "not ridden",
        "not cycled", "years", "years off", "out of the habit", "lapsed", "return",
        "take it up", "got back", "cycling again", "ride again", "get back on")),
      "Ride less than you think: twenty to thirty minutes on a flat, quiet route, every other "
      "day, and add about ten minutes a week rather than going for the ride you used to do. Give "
      "the bike ten minutes first - tyres pumped hard, brakes that stop it, a chain with a drop of "
      "oil - and set the saddle so your knee is almost straight at the bottom of the pedal, "
      "because a saddle too low is what makes a first ride hurt. Stay in an easy gear and spin "
      "rather than push.",
      bias=5,
      ask=RETURN_WORDS,
      # a return after illness, an operation or an injury is the recovery question, and a person
      # with a new knee is not to be told to ride every other day (purple-fox, #4591)
      avoid=ILL_OR_HURT +
      # a menstrual cycle, a wash cycle, a spin class, a motorcycle and the clock cycle of a
      # processor are all other answers, and fixing a bike is bike.py's question, not a comeback one
      ("period", "periods", "menstrual", "monthly", "cycle day", "ovulation", "wash cycle",
             "washing machine", "dishwasher", "spin class", "motorbike", "motorcycle",
             "scooter", "moped", "engine", "puncture", "chain came off", "brakes squeal",
             "gears slip", "fix my bike", "how much is a bike", "which bike", "buy a bike",
             "child", "kids", "toddler", "balance bike",
             # "cycle" is also a clock cycle in a processor: "amd ryzen cycle again" is hardware
             "processor", "cpu", "gpu", "chip", "chips", "ryzen", "intel", "graphics",
             "motherboard", "ram", "memory", "ssd", "hard drive", "charge cycle", "duty cycle",
             "life cycle", "product cycle", "menstrual cycle")),
# Playing again, after a long time out or a knock that has healed: the answer leads with the two
# things that come back at different speeds, because that is what the ask is worth.
entry("team-sport-again", (TEAM_SPORTS, TEAM_RETURN_WORDS),
      "Fitness and touch come back at different speeds, and it is the second one that gets people "
      "hurt. Train twice a week for a fortnight before you play any match at all, then a half, "
      "then a full one - about six weeks from the first session to playing as you did. If it was "
      "an injury that stopped you, the date is the physio's and not the calendar's: the usual guide "
      "is a week of easy training for every week you were out, and nothing at match pace until you "
      "can sprint and turn without thinking about it.",
      bias=3,
      ask=TEAM_RETURN_WORDS,
      guard=_a_return_to_team_sport,
      # an injury with a bone, a cast or a physio in the line is the healing answer, and a club, a
      # ticket or the telly is not a comeback question at all
      avoid=ILL_OR_HURT + CLUB_SEARCH +
      ("kids", "kid", "child", "children", "toddler", "son", "daughter", "school",
             "playstation", "xbox", "video game", "fantasy", "betting", "bet")),
]
