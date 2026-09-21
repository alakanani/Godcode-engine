# The Scroll of the Covenant -- making and sealing binding promises.
# Rites: NEW_COVENANT, SEAL_COVENANT.

DEFINE RITE NEW_COVENANT(name)
RETURN contract(name)
END RITE

DEFINE RITE SEAL_COVENANT(c)
SEAL c
END RITE
