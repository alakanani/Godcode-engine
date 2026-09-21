# The Seven Seals — a divine counting from 1 to 35.
# Multiples of 7 reveal "seal"; 35 reveals the "seal of seals".
BEGIN CREATION
  FOR n IN RANGE(1, 36)
    IF n % 35 IS 0 THEN
      REVEAL("seal of seals")
    ELSE
      IF n % 7 IS 0 THEN
        REVEAL("seal")
      ELSE
        REVEAL(n)
      ENDIF
    ENDIF
  ENDFOR
  ASCEND
END CREATION
