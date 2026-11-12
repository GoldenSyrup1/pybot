"""Whether a "going to ..." line is going anywhere at all.

Every "going to" line was read as a trip: the words after "to" became the place, and the person
was asked about it as if they were packing.

    im thinking of going back to uni next year  ->  "Uni, lovely. When is it?"
    im going to start a small business          ->  "Start, lovely. When is it?"

Nobody is going anywhere: one is a decision to weigh, and the other is a doing. The place is the
code that happens to follow "to", and both of these are what a noun phrase cannot be:

- a determiner after the first word says that word is a verb - "start a small business" cannot be
  a place called Start, because a place does not put "a" after its own name ("the Lake District"
  keeps its "the" in front, which is where a determiner belongs);
- a particle after it says the same thing. "think about it" and "save up first" are a verb and its
  particle, and the words after "to" are read as a place word for word: "Think About It, lovely.
  When is it?". The particles here are the ones no place name uses - "upon", "on" and "of" are
  absent because Stratford upon Avon, Henley on Thames and the isle of wight are journeys, and
  "in" is absent for "Barton in the Clay";
- a verb of the body or the feelings after "to" is the doing itself, and nobody asks when a
  person is going to cry: "im going to cry", "im going to throw up", "im going to die of
  embarrassment" were answered "Cry, lovely. When is it?" and "Die of Embarrassment - nice.
  When are you going?". A place is never a bare verb, so one word is enough to know;
- a place of ordinary life is not a trip. School, work, the gym and the shops are already known
  here, and uni, college and the nursery are the same errand: going back to one of those is not a
  holiday and nobody wants their month asked about.
"""
DETERMINER = frozenset("""
a an the my your our their his her its this that these those some any another each every no
""".split())
# Leading determiners that belong to the place itself: "the Lake District", "the isle of wight".
BELONGS_TO_THE_PLACE = frozenset("the a an".split())
# Particles that turn the word before them into a verb. A place name does not put one of these
# after its first word, and the prepositions place names do use (upon, on, of, in) are left out on
# purpose, so "stratford upon avon" and "henley on thames" stay the journeys they are.
PARTICLE = frozenset("""
about up down out back off over through around round along into away
""".split())
# The verbs that follow "going to" and name a doing rather than a destination. Every reader of a
# "going to" line needs these, not just the one that formed the sentence: the trip reader asked
# "Wait, lovely. When is it?" of "im going to wait till next year", and the echo asked "What do you
# want to do while you're there?" of the same line, because neither list had the word in it.
#
# A doing is not a place even when a date follows it - "wait till next year", "try again in the
# spring", "hold off till the new year" all read as somewhere to go, and each was answered as a
# trip. The test is the word itself: a verb is a verb whatever comes after it, so this list is the
# one place a doing is named, and both readers ask it rather than keeping a list each.
DOING_AFTER_TO = frozenset("""
wait waits waited waiting hold holds held holding hope hopes hoped hoping plan plans planned
planning think thinks thought thinking save saves saved saving spend spends spent spending
finish finishes finished finishing decide decides decided deciding apply applies applied applying
arrange arranges arranged arranging aim aims aimed aiming avoid avoids avoided avoiding
worry worries worried worrying sort sorted sorting
be been being get gets got getting go goes going do does did doing see sees saw seeing
try tries tried trying have has had having keep keeps kept keeping quit quits quitting
leave leaves left leaving start starts started starting stop stops stopped stopping
manage manages managed managing afford affords afforded affording book books booked booking
lose loses lost losing win wins won winning sell sells sold selling
ask asks asked asking tell tells told telling call calls called calling look looks looked looking
find finds found finding put puts putting buy buys bought buying eat eats ate eating
drink drinks drank drinking work works worked working sleep sleeps slept sleeping
pass passes passed passing faint faints fainted fainting collapse collapses collapsed collapsing
throw throws threw thrown throwing die dies died dying move moves moved moving
""".split())
# Places of ordinary life, in the same family as the school, work and the gym the trip reader
# already knows about: a person goes back to one of these, they do not go away to it.
ORDINARY = frozenset("""
uni university unis college colleges campus nursery nurseries creche childcare playschool
""".split())
# The verbs a person says after "going to" when the going is a doing: what the body does and
# what a feeling does. The trip reader already knows the planning verbs ("start", "see", "get"),
# and these are the family it missed, so "im going to cry" became a place called Cry and the
# person was asked what month they were going. Only words that cannot name somewhere are here:
# a place called Bath, Nice or Split is still a place, so its verb is not in the list.
DOING = frozenset("""
cry cries cried crying sob sobs sobbing weep weeps weeping wail wails wailing
laugh laughs laughed laughing giggle giggles giggling chuckle chuckles chuckling
scream screams screamed screaming shout shouts shouted shouting yell yells yelled yelling
panic panics panicked panicking faint faints fainted fainting
throw throws threw throwing vomit vomits vomited vomiting puke pukes puked puking
sneeze sneezes sneezed sneezing cough coughs coughed coughing hiccup hiccups hiccuping
burp burps burped burping gag gags gagged gagging choke chokes choked choking
die dies died dying explode explodes exploded exploding burst bursts bursting
moan moans moaned moaning groan groans groaned groaning snore snores snored snoring
sweat sweats sweated sweating blush blushes blushed blushing
shiver shivers shivered shivering tremble trembles trembled trembling
wet wee poo splutter splutters spluttering
# The same word twice, once as the doing and once as the idiom it makes: "im going to lose it"
# and "im going to crack up" are the temper, "im going to pass out" is the body, and "im going
# to snap" is both. A place is never one of these on its own, so the second word does not matter.
lose loses losing lost crack cracks cracked cracking snap snaps snapped snapping
pop pops popped popping flip flips flipped flipping pass passes passed passing
break breaks breaking broke broken
""".split())


def a_doing_after_to(going_words):
    """True when the words after "to" are a verb and its object ("start a small business")."""
    kept = [word for word in going_words
            if str(word).strip(" ,.;:!?'\u2019") not in ("",)]
    if kept and kept[0].lower().strip(" ,.;:!?") in BELONGS_TO_THE_PLACE:
        kept = kept[1:]
    if not kept:
        return False
    first = kept[0].lower().strip(" ,.;:!?'\u2019")
    if first in DOING_AFTER_TO or first in DOING:
        # A verb is a doing whatever follows it: "going to wait", "going to wait till next year",
        # "going to cry", "going to throw up". Nothing after it makes it a place.
        return True
    if len(kept) < 2:
        return False
    second = kept[1].lower().strip(" ,.;:!?'\u2019")
    return second in DETERMINER or second in PARTICLE


def a_place_of_ordinary_life(place):
    """True when the place is where the person already goes, not somewhere they are going."""
    words = [word.lower().strip(" ,.;:!?'\u2019") for word in str(place or "").split(" ")]
    words = [word for word in words if word]
    if words and words[0] in BELONGS_TO_THE_PLACE:
        words = words[1:]
    return bool(words) and words[0] in ORDINARY


def not_a_destination(going_words, place):
    """True when a "going to ..." line names a doing or an everyday place, not a trip."""
    return a_doing_after_to(going_words) or a_place_of_ordinary_life(place)
