# Interpolation Demo — breathing values into words: "grace upon {name}".
# {expr} inside a double-quoted string reveals the expression's value.
# {{ and }} write a plain brace.
BEGIN CREATION
  DECLARE name AS "seeker"
  DECLARE loaves AS 5
  DECLARE fishes AS 2

  REVEAL("grace upon {name}")
  REVEAL("{loaves} loaves and {fishes} fishes feed {loaves * 1000 + fishes * 1000}")
  REVEAL("shouted: {UPPER(name)}")

  DEFINE RITE greet(household)
    REVEAL("peace upon the house of {household}")
  END RITE
  INVOKE greet("david")

  REVEAL("a plain {{ brace }} stays a brace")
  ASCEND
END CREATION
