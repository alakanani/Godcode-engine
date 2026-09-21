# Sandbox Safe — a pure creation, fit for the sandbox.
#
# Nothing here touches the world outside the program: no files, no network,
# no subprocesses — only numbers, cycles, and revelation. Run it guarded:
#
#   godcode run --sandbox examples/sandbox_safe.god
#   godcode run --sandbox --sandbox-timeout 5 examples/sandbox_safe.god
#
# The sandbox policy denies-by-default, so anything impure would be refused
# rather than executed. Pure creations like this one pass through in peace.

BEGIN CREATION
  REVEAL("the first twelve numbers of fibonacci")
  DECLARE a AS 0
  DECLARE b AS 1
  FOR n IN RANGE(12)
    REVEAL(a)
    DECLARE next AS a + b
    DECLARE a AS b
    DECLARE b AS next
  ENDFOR
  ASCEND
END CREATION
