"""Allow ``python -m godcode <subcommand>``."""
import sys

from godcode.cli import main

if __name__ == "__main__":
    sys.exit(main())
