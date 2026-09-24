# God Code Language Specification (Draft 1)

This document describes the God Code language as it is implemented in the godcode-engine tree-walking interpreter. Where the older language reference and the implementation disagree, the implementation wins, and every claim below has been checked against the code or against small probe scrolls run through it. God Code is pre-1.0, so this specification will grow as the language does.

## 1. Overview and design goals

### 1.1 What God Code is

God Code is a small, readable programming language written in plain English. Programs are called scrolls and live in `.god` files. Reusable pieces of logic are called rites, which is the God Code word for functions. A scroll reads almost like prose: you DECLARE things, you REVEAL them, you walk through lists with FOR, and you shelter risky work inside TRY.

### 1.2 Design goals

Readability comes first. A person who has never programmed should be able to read a scroll and follow what it does. Errors are gentle: they name the line, say what went wrong in plain words, and often suggest what was meant. Safety is the default: scrolls run inside a guarded sandbox unless the creator asks otherwise, so a creation cannot touch the filesystem, the network, or subprocesses without permission. The language is small on purpose. A handful of statements, a few dozen built-in rites, and nothing that needs a computer science degree to understand.

## 2. Lexical structure

### 2.1 Keywords and names

Keywords are case-insensitive. `begin creation`, `Begin Creation`, and `BEGIN CREATION` are all accepted. The canonical style, and the style this specification uses, is UPPER. Identifiers (the names you give things) preserve their case, so `seeker` and `Seeker` are two different names. A name starts with a letter or an underscore and continues with letters, digits, or underscores.

### 2.2 Comments

A comment starts with `#` and runs to the end of the line. The newline itself is still lexed, so a comment never swallows the line break. A `#` inside a double-quoted string is just a character, not a comment. There are no multi-line comments.

### 2.3 Whitespace and line structure

Spaces and tabs separate tokens and are otherwise ignored. Each line break becomes a NEWLINE token, and the language is line-oriented: one statement per line. The exceptions are the inline forms described later (a one-line IF, a one-line FOR, a one-line WHILE, a one-line rite body). A blank line is simply an empty line; it ends nothing and starts nothing.

### 2.4 Numbers

Numbers are integers or floats. `3` and `007` are integers (leading zeros are accepted; `007` is the number 7). `4.5` is a float. A decimal point must be followed by digits: `5.` is rejected by the lexer with a malformed-number error, and `.5` is rejected because `.` is not a character the language recognizes. There is no scientific notation: `1e5` lexes as the number `1` followed by the name `e5`, which the parser then rejects. Negative numbers are written with the unary minus operator applied to a number literal, as in `-5`.

### 2.5 Strings

Strings use double quotes only. Inside a string, four escapes are recognized: `\"` for a quote, `\\` for a backslash, `\n` for a newline, and `\t` for a tab. Any other escape, such as `\q`, is a lexer error. A string cannot span lines: if the closing quote never arrives before the line ends, the lexer rejects it and names the line and column where the string opened. A string whose closing quote never arrives at all is rejected the same way.

### 2.6 Interpolation and brace escaping

Any expression wrapped in braces inside a double-quoted string has its revealed value breathed into the string. `"grace upon {name}"` reveals `grace upon seeker` when `name` holds `"seeker"`. The braces may hold any expression: arithmetic like `{2 + 3}`, comparisons, and calls to built-in rites like `{UPPER(name)}`. To write a plain brace, double it: `"{{"` becomes `{` and `"}}"` becomes `}`. A lone `}` with no partner stays a plain brace. An opening `{` that is never closed is a parse error that names the line and column. Empty braces `{}` are a parse error. Braces nest correctly, and braces inside quoted text within the expression do not confuse the parser.

### 2.7 Booleans and void

`TRUE` and `FALSE` are boolean literals (they are keywords, so they work in any letter case). `VOID` is the literal for the absence of a value. `REVEAL(TRUE)` reveals `true`, `REVEAL(FALSE)` reveals `false`, and `REVEAL(VOID)` reveals `void`. Comparisons also produce booleans, as in `1 < 2`.

### 2.8 Lists

A list is written with square brackets and holds an ordered sequence of values of any mixed types: `[1, two, "three"]`. An empty list is `[]`. Declaring several comma-separated values also builds a list: `DECLARE prophets AS Isaiah, Elijah, Jeremiah` binds `prophets` to a list of three symbols.

### 2.9 Symbols

A bare word that is bound to nothing evaluates to a Symbol carrying its own name, instead of raising an error. This is the founding idiom of the language: `DECLARE seeker AS worthy` works with no prior binding of `worthy`, and `IF seeker IS worthy` then holds true. In practice a Symbol behaves like a small piece of text: it reveals as its own name, and it compares equal by text to the same word written as a string, so `"worthy" IS worthy` is true. Two facts set Symbols apart from plain strings. First, Symbols are always truthy, even in positions where an empty string would be falsy. Second, a FOR loop refuses to walk through a bare Symbol and raises a runtime error naming it, asking for a list or a word instead. The type name of a Symbol, as reported by `TYPE`, is `"symbol"`.

## 3. Program structure

### 3.1 BEGIN CREATION ... END CREATION

Every scroll is a creation. It opens with `BEGIN CREATION` on its own line and closes with `END CREATION` on its own line. Nothing runs outside those two lines, and a scroll holds exactly one creation: anything after `END CREATION` is rejected. (The parser also accepts bare fragments with no creation wrapper, which is how imported scrolls are read, but a scroll you write and run yourself always uses the wrapper.)

### 3.2 Top-level statements run in order

Between the two lines, statements run from top to bottom, one after another, in the order they are written. Each statement is executed for its effect before the next one begins. `ASCEND` ends the creation immediately and in peace; reaching `END CREATION` ends it naturally.

### 3.3 Rites as the unit of reuse

The unit of reuse is the rite. A rite is defined once with `DEFINE RITE name(params)` ... `END RITE` and called many times, either as a statement with `INVOKE name(args)` or as an expression with `name(args)` wherever a value is expected. Rite definitions are ordinary statements: they may appear at the top level of a scroll or inside other blocks, and the rite's name is bound in the scope where the definition appears.

## 4. Declarations and scoping

### 4.1 DECLARE

`DECLARE name AS value` binds a name to the value of an expression, evaluated in the current scope. The name is created if it does not exist. Several comma-separated values become a list, as shown in 2.8. `DECLARE` always defines in the current scope. It never reaches outward to rebind a name in an enclosing scope.

### 4.2 The update idiom

Because there is no separate assignment statement, the way to change a variable is to declare it again with an expression that mentions it: `DECLARE count AS count + 1`. The old value is read, the new value is computed, and the name is rebound in the same scope. This is the language's only way to update a variable, and the linter treats it as legitimate rather than as a mistake (see 4.6).

### 4.3 Rite parameters

A rite's parameters are declared in its header: `DEFINE RITE BLESSING(name)`. When the rite is called, each argument value is bound to its parameter name in a fresh child scope. Parameters are positional only. There are no default values and no named arguments.

### 4.4 Scope rules as implemented

Names resolve outward through enclosing scopes: the innermost binding wins, and a name bound nowhere evaluates to a Symbol (see 2.9). The scopes work as follows.

* The top level of a scroll is the root scope.
* An IF body and an ELSE body run in the enclosing scope. There is no new scope.
* A WHILE body runs in the enclosing scope. There is no new scope. This is why `DECLARE count AS count - 1` inside a WHILE loop updates the very name the loop condition watches: it rebinds the name in the same scope. A probe confirms it: a `WHILE` loop that counts from 10 to 13 leaves the outer name holding 13 afterward.
* A FOR body runs in one child scope that lasts for the whole loop, and the loop variable lives in that child scope. Names declared inside a FOR body shadow the outer scope for the rest of the loop but do not touch it. A probe confirms it: declaring `x` as `x + 1` inside a FOR loop leaves the outer `x` still holding 10 after the loop ends.
* A rite call runs in a fresh child scope of the environment where the rite was defined. Rites are closures: they remember where they were born. A probe confirms it: a rite defined inside another rite can read the outer rite's names when called.

### 4.5 Closures

Because a rite's call scope is a child of its definition scope, a rite carries its birthplace with it. A rite defined inside another rite sees the outer rite's names. A rite defined at the top level sees the top-level names as they were when it was defined.

### 4.6 Shadowing and re-declaration

Declaring a name in an inner scope that is already visible from an outer scope is allowed at runtime. It creates (or updates) the name in the inner scope and leaves the outer binding untouched. The linter flags it as rule GC003, shadowing, as a gentle warning that the reuse may be accidental. It fires for a FOR loop variable or a rite parameter that reuses an outer name, and for a DECLARE inside a FOR body or a rite body that reuses one.

Declaring the same name twice in the same scope is also allowed at runtime: the second declaration simply rebinds the name. The linter flags it as rule GC006, re-declaration, with one exception: the update idiom. A re-declaration whose value expression mentions the name being declared, like `DECLARE count AS count + 1`, is not flagged, because that is the language's sanctioned way to update a variable. A re-declaration whose value does not mention the name, like `DECLARE seed AS 2` after `DECLARE seed AS 1`, is flagged. Note that the linter's scope model mirrors the interpreter exactly: IF and WHILE bodies count as the current scope, while FOR bodies and rite bodies count as inner scopes. So redeclaring a name inside a WHILE loop is GC006 (same scope), while redeclaring it inside a FOR loop body is GC003 (shadowing).

## 5. Control flow

A condition is any expression. It is weighed by truthiness: `FALSE`, `0`, `0.0`, `""`, `[]`, the empty map, and `void` are falsy. Symbols are always truthy. Everything else is truthy.

### 5.1 IF

The block form, for many statements, closes with `ENDIF`:

```godcode
IF heart IS pure THEN
  REVEAL("the way is open")
ELSE
  REVEAL("wait and be still")
ENDIF
```

The inline form puts one statement per branch on a single line: `IF seeker IS worthy THEN REVEAL("heaven") ELSE REVEAL("test")`. The ELSE may be omitted in either form. There is no `ELSE IF` keyword. Chained conditions are written as a nested IF inside the ELSE branch, and each nested IF needs its own ENDIF. IFs nest freely, and an ELSE always belongs to the nearest IF. The IF body and the ELSE body run in the enclosing scope (see 4.4).

### 5.2 FOR

`FOR name IN expression` ... `ENDFOR` walks a list, or the characters of a string:

```godcode
FOR prophet IN prophets
  REVEAL(prophet)
ENDFOR
```

The expression after IN must evaluate to a list or a string. Walking a bare Symbol, a number, or anything else is a runtime error: for a number it reads "FOR cannot walk through number, only lists and words", and for a bare Symbol it names the spirit and asks for a list or a word instead. The loop variable is bound anew for each turn in the loop's child scope (see 4.4). The inline form puts the single body statement on the same line. The grammar also still accepts the legacy v1 form, where a FOR body with no ENDFOR runs to `END CREATION`, `END RITE`, or the end of the scroll; new scrolls should always close the loop with ENDFOR.

### 5.3 WHILE

`WHILE condition DO` ... `ENDWHILE` cycles while its condition holds:

```godcode
DECLARE count AS 10
WHILE count > 0 DO
  REVEAL(count)
  DECLARE count AS count - 1
ENDWHILE
```

The body runs in the enclosing scope (see 4.4), which is what lets the update idiom drive the condition. The inline form is `WHILE count > 0 DO REVEAL(count)`. A cycle that will not end is stopped after 100,000 turns with the runtime error "the cycle is endless".

### 5.4 BREAK and CONTINUE

`BREAK` releases the innermost enclosing loop at once. `CONTINUE` skips to the next turn of the innermost enclosing loop. Both work in FOR and WHILE alike, and in the inline form (`IF n IS 0 THEN BREAK`). In nested loops, BREAK releases only the innermost one; the outer cycle keeps turning. Spoken with no loop around them, both are rejected when the scroll is read, at parse time: "BREAK can only be used inside a loop." A rite is a boundary for these signals: a BREAK inside a rite answers only to loops within that rite, and a rite body parsed with no loop of its own rejects a BREAK at parse time even if the rite is later invoked inside a loop.

### 5.5 TRY ... CATCH ... ENDTRY

A sheltered work. The TRY block runs first, and if a runtime error rises anywhere inside it, execution jumps to the CATCH block:

```godcode
TRY
  DECLARE share AS harvest / workers
CATCH trouble
  REVEAL("no harvest today: {trouble}")
ENDTRY
```

Only runtime errors (GodRuntimeError) are caught. Parse and lexer errors fail before the creation ever runs, so TRY cannot shelter them. The error's plain message is bound for the CATCH block to speak of, without any line or location suffix: `CATCH` alone binds it to `ERROR`, and `CATCH name` binds it to a name of your choosing. A probe confirms the binding carries exactly the plain message, such as "Division by nothing is not permitted", even though the same error printed outside a TRY would carry its line. Three things pass through uncaught. RETURN inside a TRY still returns from its rite. ASCEND still ends the run in peace. Sandbox violations, which are a different kind of error from runtime errors, rise straight through any TRY. TRY blocks nest freely, with the innermost CATCH handling the innermost error. An error raised inside a CATCH block rises outward normally. If no error rises, the CATCH block is skipped and the creation continues after ENDTRY.

## 6. Rites

### 6.1 Defining rites

A rite is defined with `DEFINE RITE`, a name, a parenthesized parameter list, a body, and `END RITE`:

```godcode
DEFINE RITE BLESSING(name)
  RETURN "grace upon " + name
END RITE
```

The parameter list may be empty: `DEFINE RITE BLESSING()`. A single-statement body may sit on the same line as the header. Defining a rite binds its name in the current scope to a rite value, alongside the parameter names and the body it will run.

### 6.2 Parameters and arguments

Arguments bind to parameters by position, in order. There are no default values and no named arguments: the parser reads a plain comma-separated list of expressions. Calling with the wrong number of arguments is a runtime error that names both counts, for example "Rite 'add' asks for 2 offerings, but 1 was brought." Extra arguments and missing arguments are both rejected this way.

### 6.3 RETURN

`RETURN expression` evaluates the expression and sends the value back to the caller, ending the rite at once. `RETURN` with no value returns void. A rite that runs to the end of its body without meeting a RETURN also returns void. RETURN belongs inside a rite: spoken at the top level of a scroll it is not caught and ends the run with an internal error.

### 6.4 Call semantics

A rite is called as a statement with `INVOKE name(args)`, or as an expression with `name(args)` wherever a value is expected; both forms evaluate the arguments first, left to right, then bind them to the parameters. The call runs the rite body in a fresh child scope of the rite's definition scope (see 4.4 and 4.5), so each call gets its own parameters and its own local names. When the name in a call is resolved, the interpreter searches in this order: the special `contract(name)` form, then a rite bound in scope (yours or imported), then a built-in rite. Calling a name bound to something that is not a rite is a runtime error naming the value's type. Calling a name bound to nothing at all is a runtime error, "There is no rite named 'X'", with a "Did you mean ...?" suggestion when a close name exists.

### 6.5 Recursion

A rite may call itself. Each recursive call gets a fresh scope, so recursion works exactly as in other languages. A probe confirms it: a `factorial` rite calling itself returns 120 for an input of 5.

### 6.6 The TEST_* convention

Rites whose names begin with `TEST_` are ordinary rites with a naming convention. The test runner discovers them by name and runs each one as a test case. The full rules of the test runner live in section 10; here it is enough to know that the prefix is only a convention, and the rites themselves behave like any other rites.

## 7. Built-in rites (standard library)

A built-in rite is always present. No `IMPORT` is needed. When a call
`NAME(args)` is made, the engine searches in this order: the special form
`contract("name")`, then rites you defined or imported, then the built-ins
below. Anything else is an error naming the unknown name.

The engine defines exactly these names. Note the spelling: the length rite
is `LEN`, not `LENGTH`. There is no `TRIM`, `POP`, `CONTAINS`, `KEYS`,
`VALUES`, `ROUND`, or `TRUNC` builtin. What follows is the complete list,
with the exact signatures as implemented.

### Core built-ins (godcode/interpreter.py)

| Rite | Signature | Returns |
|---|---|---|
| `LEN` | `LEN(x)` | length of a list or string; anything else is an error |
| `STR` | `STR(x)` | the value rendered as a string |
| `NUM` | `NUM(s)` | a string parsed to a number; an error if it cannot |
| `TYPE` | `TYPE(x)` | one of `"number"`, `"string"`, `"symbol"`, `"list"`, `"contract"`, `"rite"`, `"boolean"`, `"void"`, `"map"` |
| `RANDOM` | `RANDOM(n)` | an integer from `0` to `n-1` |
| `RANGE` | `RANGE(n)` / `RANGE(a, b)` | a list like Python's `range` (`RANGE(1, 4)` gives `[1, 2, 3]`) |
| `PUSH` | `PUSH(list, x)` | a **new** list with `x` appended; the old list is unchanged |
| `UPPER` / `LOWER` | `UPPER(s)` | the word in upper / lower case |
| `SPLIT` / `JOIN` | `SPLIT(s, d)` / `JOIN(list, d)` | `"a,b"` becomes `["a", "b"]`, and back again |
| `ASK` | `ASK(prompt)` | the human's answer; the prompt may be omitted |
| `BEHOLD` | `BEHOLD()` | the current moment, as an ISO datetime string |
| `REVERSE` | `REVERSE(x)` | a string or list, backwards |
| `SUMMON` | `SUMMON("plugin.verb", args...)` | the result of calling a plugin verb through the FFI |
| `ANCHOR` | `ANCHOR(x)` / `ANCHOR(x, chain)` | a receipt map `{chain, anchor_hash, height, timestamp, payload_hash}` |
| `CONSULT` | `CONSULT("question")` | two to three sentences of counsel from the local Spirit oracle |

### The vault: JSON and the filesystem (godcode/stdlib_vault.py)

**`JSON_PARSE(text)`** takes a JSON word and returns God Code values.
Objects become maps, arrays become lists, `null` becomes `void`. An
unreadable word is a runtime error naming the JSON problem.

```godcode
DECLARE tribes AS JSON_PARSE("[\"Judah\", \"Reuben\"]")
REVEAL(tribes[0])     # Judah
```

**`JSON_STRING(value)`** renders a value as compact JSON. Only words,
numbers, booleans, lists, and maps have a JSON shape. Symbols, rites,
contracts, non-word map keys, and numbers like infinity are refused with
a plain error.

```godcode
REVEAL(JSON_STRING([1, 2]))     # [1,2]
```

**`READ_FILE(path)`** returns a file's text as a word. If the file cannot
be read, the OS reason is carried in the error.

```godcode
DECLARE psalm AS READ_FILE("psalm.txt")
```

**`WRITE_FILE(path, text)`** writes the text and returns the character
count. It writes the file named, nothing more: it does not create parent
directories, so a missing directory fails with a plain runtime error.

```godcode
DECLARE count AS WRITE_FILE("note.txt", "peace")
REVEAL(count)     # 5
```

**`FILE_EXISTS(path)`** returns `true` when the path exists, `false`
otherwise.

```godcode
IF FILE_EXISTS("note.txt") THEN REVEAL("the note remains")
```

**`LIST_DIR(path)`** returns the directory's entry names, sorted. A path
that is not a directory is refused with a plain error.

```godcode
REVEAL(LIST_DIR("."))     # the sorted entry names
```

### Time and the web (godcode/stdlib_times.py)

**`DATE_TODAY()`** returns today's local date as a word: `"2026-09-24"`.

**`TIME_NOW()`** returns the current local time as an ISO 8601 word.

**`FORMAT_DATE(date, pattern)`** shapes a `"YYYY-MM-DD"` word with a
strftime-style pattern. The date must be written `YYYY-MM-DD`, and both
arguments must be words.

```godcode
REVEAL(FORMAT_DATE("2026-09-24", "%A"))     # Thursday
```

**`HTTP_GET(url)`** fetches the body of an HTTP GET and returns it as a
word. It follows redirects, waits up to ten seconds, and answers every
network failure the same plain way: the web did not answer. Under
`godcode run --sandbox` it is withheld: the sandbox denies network power,
so the rite raises a `SandboxViolation` instead of reaching out.

A note on braces in source: inside a double-quoted string, a single `{`
opens interpolation, so a JSON word written literally in source must
double its braces. `{{` and `}}` become plain `{` and `}`.

```godcode
DECLARE j AS "{{ \"a\": 1 }}"     # the word is { "a": 1 }
DECLARE m AS JSON_PARSE(j)
REVEAL(m["a"])                    # 1
```

## 8. Error model

God Code errors come in two families, and the language treats them very
differently.

**Compile-time errors** are found by `godcode check`, which lexes and
parses without running anything. A `LEXER_ERROR` means bad characters or
an unterminated string. A `PARSE_ERROR` means a grammar violation, such
as a missing `END CREATION` or an unclosed block. Exit codes: `0` when
the scroll is pure, `1` when diagnostics were found, `2` on usage error.
In `--json` mode each diagnostic carries `line`, `col`, `code`,
`severity`, `message`, and `hint`.

**Runtime errors** rise while the creation runs. Anything can raise them:
a failed `TESTIFY`, division by nothing, an unknown rite, an index past
the ends. Only runtime errors can be caught by `TRY`/`CATCH`; parse and
lexer errors always fail before the creation runs.

### The gentle format

Every error names the line, says what went wrong in plain words, and
never mocks the creator. The human CLI (`run`, `run --sandbox`, `check`,
`fmt`) prints the offending source line beneath the message, with a caret
at the column when one is known:

```text
The heavens do not recognize the character '{'; it has no place in the holy tongue (line 2, col 22)
  2 |   REVEAL(JSON_STRING({{ "a": 1 }}))
                           ^
```

A misspelled name is answered with a suggestion, not scorn. Verified with
a probe:

The engine answered that there is no rite named `BLESSIN`, that the heavens
do not know it, and suggested `LEN` instead. The message named line 2, and
the offending source line was printed beneath it for the creator to see.

Suggestions cover unknown rites (including builtins), `BREATHE LIFE
INTO` / `BLESS` / `ANOINT` targets, and missing map keys. The suggestion
also rides in the `message` field of `check --json` and `run --json`
diagnostics, so agents see it too.

### Call traces for uncaught errors

When a runtime error escapes every `TRY` and rises through rite calls,
the human CLI prints the call stack beneath the gentle error, oldest call
first and most recent call last:

```text
Division by nothing is not permitted (line 3)
  3 |     DECLARE x AS 1 / 0
Called by outer at line 11
Called by middle at line 9
Called by innermost at line 6
(most recent call last)
```

Each line names the rite and the line where it was called. An error
raised at the top level, with no rite calls above it, shows no trace
section.

In `run --json`, the same stack rides on the error object as a `trace`
array of `{"rite", "line"}` objects, oldest call first. Verified shape:

```json
"error": {
  "line": 3, "col": null, "code": "RUNTIME_ERROR",
  "severity": "error", "message": "...", "hint": "...",
  "trace": [
    {"rite": "outer", "line": 11},
    {"rite": "middle", "line": 9},
    {"rite": "innermost", "line": 6}
  ]
}
```

### What TRY catches, and what it does not

`TRY`/`CATCH` catches only runtime errors. It does not catch parse or
lexer errors, and it never catches `RETURN` (which still returns from its
rite) or `ASCEND` (which still ends the run in peace). Verified by probe:
a `SandboxViolation` rises straight through `TRY`/`CATCH` untouched, so
a denied power can never be silently swallowed.

**Division by zero** is a runtime error, never a crash and never a silent
value. The engine answers: division by nothing is not permitted.

## 9. Linter rules

`godcode lint` (the `godcode/linter.py` pass) walks the parsed scroll
with the interpreter's real scope model and reports findings with stable
rule ids. It never changes the scroll.

**GC001: unused variable.** Flags a name `DECLARE`d, or a `FOR` loop
variable, that is never referenced anywhere else. A reference inside a
nested rite body counts as used, because closures capture.

```godcode
DECLARE manna AS 40      # GC001: 'manna' is never read
REVEAL("the way is open")
```

Rationale: a bound name nobody reads is either a forgotten step or a
misspelling waiting to happen.

**GC002: undefined name.** Flags an identifier or rite call naming
something never declared, defined, imported, or provided by a builtin.
Unresolvable imports make the rule hold its peace rather than guess.

```godcode
REVEAL(wanderer)     # GC002: undefined name 'wanderer'
```

Rationale: an unbound name becomes a Symbol instead of raising, so the
linter is the place where a typo is caught before it becomes doctrine.

**GC003: shadowing.** Flags a `DECLARE`, rite parameter, or `FOR` loop
variable that reuses a name already visible from an outer scope. The
language defines in the current scope only, so shadowing is legal, but it
is flagged because it is rarely what the creator meant.

```godcode
DECLARE light AS "dawn"
DEFINE RITE kindle(light)     # GC003: 'light' shadows an outer name
  REVEAL(light)
END RITE
```

Rationale: shadowing makes two different values answer to one name, and
the confusion always surfaces at the worst moment.

**GC004: empty block.** Flags an `IF`, `FOR`, `WHILE`, `DEFINE RITE`,
`TRY`, or `CATCH` body with zero statements. Both the `IF` and the `ELSE`
bodies are checked.

```godcode
IF heart IS pure THEN     # GC004: empty IF body
ENDIF
```

Rationale: an empty block is either unfinished work or a condition whose
branches were never written.

**GC005: unreachable code.** Flags any statement after `RETURN`,
`BREAK`, or `CONTINUE` in the same block.

```godcode
DEFINE RITE early()
  RETURN "peace"
  REVEAL("never spoken")     # GC005: unreachable code after RETURN
END RITE
```

Rationale: code that can never run is dead weight, and its presence
suggests the creator believes it runs.

**GC006: re-DECLARE in the same scope.** Flags the same name `DECLARE`d
twice in one scope. The update idiom is excepted: a re-`DECLARE` whose
value mentions the same name is allowed, because it is the language's
only way to update a variable.

```godcode
DECLARE count AS 1
DECLARE count AS 2          # GC006: declared more than once in the same scope
DECLARE count AS count + 1  # allowed: the update idiom
```

Rationale: redeclaring without reading the old value almost always means
the first declaration was a mistake or a leftover.

## 10. Testing

`godcode test [dir] [--json]` runs the scrolls' own tests. A **test
scroll** is any `.god` file named `test_*.god` or `*_test.god`
(case-insensitive). Inside it, every rite named `TEST_*` is one test
case, and `TESTIFY` is the assertion.

```bash
godcode test            # test the scrolls in the current directory
godcode test tests/     # test the scrolls in tests/
godcode test --json     # machine-readable report
```

The report prints one line per test, then a summary. Verified output:

```text
PASS  test_demo.god :: TEST_pass
FAIL  test_demo.god :: TEST_fail :: the gentle testimony-failed message (line 6)
SKIP  test_demo.god :: TEST_param :: the rite asks for 1 offering, so it was not called.
1 passed, 1 failed, 1 skipped.
```

The rules the runner keeps:

- **Isolation.** Each `TEST_*` rite runs in a fresh interpreter. The
  scroll's top-level words run again before every test, so one test can
  never see another's state, not even across files.
- **One scroll, one parse.** A scroll that cannot be read or parsed is
  reported as a file-level failure under the rite name `(scroll)`, and it
  never crashes the run.
- **A failing TESTIFY fails the test.** Any runtime error fails it too,
  with the error message carried in the report.
- **Parameterized rites are skipped.** A `TEST_` rite that asks for
  offerings is reported as `SKIP`, with the reason, and does not fail
  the run.
- **Discovery is shallow.** Only the given directory's own scrolls are
  read. Subfolders are not entered, and files named anything else are
  left untouched even if they define `TEST_` rites.
- **Quiet runs.** `REVEAL` lines and `[TESTIFY]` notices are swallowed so
  the report stays one line per test.
- **No Spirit, no ledger, no sandbox.** Tests run the way `godcode run`
  does, so only test scrolls you wrote or trust.

Exit codes: `0` when every test passes (skips do not fail the run), `1`
when any test fails, `2` on usage error (for example, a directory that
does not exist). In `--json` mode the report is one document with
`tool`, `command`, `dir`, a `tests` array of `{file, rite, ok, message}`
(`ok` is `true`, `false`, or `null` for skipped), and `passed`, `failed`,
`skipped` counts.

## 11. Sandbox and safety model

`godcode run --sandbox` executes a creation inside a guarded chamber.
The `SandboxPolicy` is **deny-by-default**: every side-effecting power is
withheld unless the policy explicitly grants it. The flags:

| Grant | Default | Meaning |
|---|---|---|
| `allow_write` | denied | filesystem writes |
| `allow_read_paths` | denied | filesystem reads, only under the granted directories |
| `allow_network` | denied | network access |
| `allow_subprocess` | denied | spawning subprocesses |
| `allow_stdin` | denied | the `ASK` rite speaking with the outer world |
| `allowed_import_paths` | empty | directories `IMPORT` may draw scrolls from |
| `timeout_seconds` | 5.0 | wall-clock grant for the whole run |
| `max_steps` | 100,000 | step budget; every statement and expression counts one step |

Builtins are policed by name, and the vault builtins additionally enforce
the granted directories per path inside themselves:

| Rite | Needs |
|---|---|
| `ASK` | `allow_stdin` |
| `WRITE_FILE` | `allow_write` |
| `READ_FILE`, `LIST_DIR`, `FILE_EXISTS` | `allow_read_paths`, and the resolved path must lie under a granted directory |
| `HTTP_GET` | `allow_network` |

`IMPORT` of any scroll outside `allowed_import_paths` is refused. `ANCHOR`
is special: under a policy that denies writes it is answered with an
ephemeral in-memory chain instead of being refused, so creations keep
their meaning without touching the disk. The covenant ledger and the
audit log stay unbound in the sandbox (they write to the host world).
The Spirit is bound read-only, so `CONSULT` and `DECLARE INTENT` work.

A denied power raises `SandboxViolation`, a line-numbered error. Verified
by probe: it rises straight through `TRY`/`CATCH`, so a sandbox boundary
can never be caught and swallowed. Runaway creations are stopped, not
suffered: the step budget and the wall-clock grant each end the run with
a clear message.

**Division by zero** is a runtime error everywhere, sandboxed or not:
division by nothing is not permitted.

The safety promise, stated plainly: a sandboxed scroll cannot touch host
files or the network unless the sandbox options allow it. Pure
creations, numbers, cycles, and revelation, pass through in peace.
Anything reaching for the world outside is refused with a clear,
line-numbered message.

One honest limit, recorded in the implementation: this is an in-process
sandbox, a cooperative audit of the tree-walker, not OS-level isolation.
It cannot contain a hostile program that escapes the interpreter, and it
cannot cap memory.

## 12. Versioning and compatibility promise

God Code is pre-1.0. Breaking changes to the language are possible before
1.0, and they will be communicated in release notes and the changelog
(the repo keeps `CHANGELOG.md` at its root, with an `Unreleased` section
for what is coming). The engine's current release number is 4.0.0; the
1.0 milestone named here is the language-stability milestone, and it has
not been reached yet.

After 1.0 the intent is semantic versioning: patch releases fix without
changing the language, minor releases add without breaking, and major
releases are the only ones allowed to break. The full versioning policy
will be formalized before 1.0.
