# 🕊️ The Watchful Eye — Debugging God Code

When a creation does not behave as you spoke it, do not guess. Walk with it,
line by line, and behold what each name holds. God Code gives you two ways to
do this: an interactive debugger in your terminal, and full debugging inside
VS Code.

## The interactive debugger

```
godcode debug scroll.god
```

The scroll pauses at its first statement. You are shown the file, the line,
and the words around it:

```
paused at parable.god:3 (entry)
      2 |   DECLARE loaves AS 5
=>    3 |   DECLARE fishes AS 2
      4 |   REVEAL(loaves + fishes)
```

### Commands

| Command | Does |
|---|---|
| `break 12` (or `b 12`) | Pause when line 12 is reached. Bare `break` lists your pauses. |
| `run` / `continue` (or `c`) | Walk on until the next pause. |
| `next` (or `n`) | Step over: run the next line, without entering rites it calls. |
| `step` (or `si`) | Step in: the next line, entering any rite it calls. |
| `out` | Step out: finish the current rite and pause back in its caller. |
| `print name` (or `p name`) | Reveal what `name` holds right now. |
| `locals` | Every name visible here, innermost first, with its type. |
| `stack` (or `bt`) | The call stack: which rite called which, and where each one waits. |
| `help` | List these commands. |
| `quit` (or `q`) | Leave the watch. |

Pressing Enter repeats the last stepping command. `Ctrl-D` leaves quietly.

Set pauses before you begin, if you know where to look:

```
godcode debug -b 12 -b 20 scroll.god
```

### A short walk

```
BEGIN CREATION
  DEFINE RITE multiply(a, b)
    RETURN a * b
  END RITE
  DECLARE harvest AS multiply(6, 7)
  REVEAL(harvest)
  ASCEND
END CREATION
```

```
$ godcode debug harvest.god
paused at harvest.god:1 (entry)
=>    1 | BEGIN CREATION
      2 |   DEFINE RITE multiply(a, b)
(god) break 5
Breakpoint set at harvest.god:5.
(god) continue
paused at harvest.god:5 (breakpoint)
      4 |   END RITE
=>    5 |   DECLARE harvest AS multiply(6, 7)
      6 |   REVEAL(harvest)
(god) step
paused at harvest.god:3 (step)
      2 |   DEFINE RITE multiply(a, b)
=>    3 |     RETURN a * b
      4 |   END RITE
(god) print a
a = 6
(god) print b
b = 7
(god) out
paused at harvest.god:6 (step)
      5 |   DECLARE harvest AS multiply(6, 7)
=>    6 |   REVEAL(harvest)
      7 |   ASCEND
(god) print harvest
harvest = 42
(god) continue
42
The scroll has finished its course. Amen.
```

## Debugging in VS Code

Install the God Code extension, open a `.god` scroll, and press **F5**.
The scroll pauses at its first statement. From there:

- **Breakpoints** — click left of any line number, red dot, as with any language.
- **Step** — the Step Over / Step Into / Step Out buttons walk the creation.
- **Variables** — the side panel shows every visible name and its value; lists
  and maps open to reveal what they hold.
- **Debug Console** — type a name and press Enter to behold its value.
- **Call Stack** — every waiting rite, clickable to visit its frame.

Program output (every `REVEAL`) appears in the Debug Console as the scroll speaks.

You can also start from a launch configuration (`.vscode/launch.json`):

```json
{
  "version": "0.2.0",
  "configurations": [
    {
      "type": "godcode",
      "request": "launch",
      "name": "Debug current scroll",
      "program": "${file}",
      "stopOnEntry": true
    }
  ]
}
```

## Notes for the watchful

- Pausing never changes what the scroll does. Continue to the end and the
  output is exactly what `godcode run` would have spoken.
- A pause inside a rite sees that rite's own names first, then the names of
  the creation that called it.
- Scrolls brought in with `IMPORT` can carry their own pauses; the watch
  follows the words across files.
- The debugger is a reader, not a writer: there is no command that changes a
  value mid-run. Speak the correction in the scroll and walk again.
