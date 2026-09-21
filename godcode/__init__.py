"""God Code v2.0 — the language of divine computation."""

__version__ = "2.0.0"


def run_source(source, source_name="<creation>"):
    """Lex, parse, and run God Code source; return the interpreter.

    The returned interpreter carries `.output` (every REVEAL line) and
    `.env` (the root environment) for inspection.
    """
    from godcode.interpreter import Interpreter

    interpreter = Interpreter()
    interpreter.run_source(source, source_name=source_name)
    return interpreter
