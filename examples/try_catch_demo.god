BEGIN CREATION
# Sheltered by Grace — TRY shelters a fragile work, CATCH receives its message,
# and BREAK / CONTINUE guide the cycles.

# A work that stumbles need not end the run.
TRY
    DECLARE share AS 10 / 0
    REVEAL("this line is never reached")
CATCH
    REVEAL("caught: {ERROR}")
ENDTRY

# CATCH can name the binding itself, and shelters rites too.
DEFINE RITE RISKY(n)
    IF n < 0 THEN
        DECLARE oops AS 1 / 0
    ENDIF
    RETURN n * 2
END RITE

TRY
    REVEAL(RISKY(-3))
CATCH trouble
    REVEAL("the rite stumbled: {trouble}")
ENDTRY

REVEAL("the run goes on in peace")

# BREAK releases a loop, CONTINUE turns its wheel again.
FOR n IN [1, 2, 3, 4, 5]
    IF n IS 4 THEN
        BREAK
    ENDIF
    IF n IS 2 THEN
        CONTINUE
    ENDIF
    REVEAL("counted {n}")
ENDFOR
END CREATION
