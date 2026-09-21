# Ascension — count down from 10, then ascend in peace.
BEGIN CREATION
  DECLARE count AS 10
  WHILE count > 0 DO
    REVEAL(count)
    DECLARE count AS count - 1
  ENDWHILE
  REVEAL("it is finished")
  ASCEND
END CREATION
