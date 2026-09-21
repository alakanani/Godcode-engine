# The Scroll of Blessings -- words of favor for the children of creation.
# A community content pack: the BLESSINGS list and rites to reveal them.
# Rites: REVEAL_BLESSING, BLESSING_COUNT, BLESS_AT.

DECLARE BLESSINGS AS ["May your code compile on the first breath.", "May your loops find rest and your rites return in peace.", "May no scroll be lost, and no promise broken.", "May your errors be loud, your fixes swift, and your tests ever green.", "Blessed are the debuggers, for they shall find the light.", "May your merges be clean and your conflicts few.", "May the Spirit guide your keystrokes and guard your deploys.", "May your data be backed up and your restores untested-never.", "May every edge case be foreseen, and every null be void indeed.", "Go in peace; your creation is good."]

DEFINE RITE REVEAL_BLESSING()
DECLARE i AS RANDOM(LEN(BLESSINGS))
RETURN BLESSINGS[i]
END RITE

DEFINE RITE BLESSING_COUNT()
RETURN LEN(BLESSINGS)
END RITE

DEFINE RITE BLESS_AT(n)
RETURN BLESSINGS[n]
END RITE
