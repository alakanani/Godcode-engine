# Rites Demo — define a named blessing with parameters,
# RETURN a value from it, and INVOKE it.
BEGIN CREATION
  DEFINE RITE BLESSING(name)
    RETURN "grace upon " + name
  END RITE
  INVOKE BLESSING("seeker")
  DECLARE word AS BLESSING("seeker")
  REVEAL(word)
  ASCEND
END CREATION
