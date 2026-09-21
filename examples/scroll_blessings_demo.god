# Scroll Blessings Demo — borrow a blessing from the scroll registry.
#
# Install the scroll first:
#   godcode scroll install blessings
# (installs from the local registry into ~/.godcode/scrolls/).
# IMPORT then finds it through the normal resolution order —
# stdlib first, then installed registry scrolls.

BEGIN CREATION
  IMPORT "blessings"
  REVEAL("the registry bestows this blessing")
  REVEAL(REVEAL_BLESSING())
  ASCEND
END CREATION
