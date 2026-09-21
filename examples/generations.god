# Generations — the first 12 numbers of the Fibonacci sequence,
# begotten one from another in a WHILE cycle.
BEGIN CREATION
  DECLARE a AS 0
  DECLARE b AS 1
  DECLARE count AS 0
  WHILE count < 12 DO
    REVEAL(a)
    DECLARE next AS a + b
    DECLARE a AS b
    DECLARE b AS next
    DECLARE count AS count + 1
  ENDWHILE
  ASCEND
END CREATION
