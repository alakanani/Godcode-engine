# The Scroll of Appointed Times -- beholding the hour and the day.
# Rites: NOW, TODAY.

DEFINE RITE NOW()
RETURN BEHOLD()
END RITE

DEFINE RITE TODAY()
RETURN SPLIT(BEHOLD(), "T")[0]
END RITE
