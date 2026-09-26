"""Entry point for the God Code engine.

With CLI args: delegate to the `godcode` command-line interface.
With no args: run the sample scroll through the new interpreter (legacy
behavior from the original prototype).
"""
import sys
from pathlib import Path


def main() -> None:
    if len(sys.argv) > 1:
        from godcode.cli import main as cli_main
        cli_main()
    else:
        from godcode.interpreter import Interpreter
        sample = Path(__file__).resolve().parent / "sample.godcode"
        Interpreter().run_source(
            sample.read_text(encoding="utf-8"), source_name=str(sample))


if __name__ == "__main__":
    main()
