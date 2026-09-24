# Security Policy

If you find a security problem in God Code, thank you for telling us. We take it seriously.

## What counts as a security issue

- A way to escape the sandbox (`godcode run --sandbox`): reading, writing, or touching the host system in a way the sandbox grants do not allow.
- An unsafe builtin: a standard library rite that reaches further than its documentation says it does.
- A dependency with a known vulnerability, or a compromised package in the scroll registry.
- Anything in the debugger, language server, or CLI that could run untrusted code without the user asking.

Regular bugs (wrong output, crashes, confusing errors) are not security issues. Please open a normal GitHub issue for those.

## How to report

Email **hello@getgodcode.com** with the subject "Security report". Include:

- What you found, in plain words.
- Steps to reproduce it, or a small scroll that shows it.
- What you think the impact is.

Please do not publish the details publicly until we have had a chance to fix it.

## What you can expect

- An acknowledgment within 3 days.
- An honest assessment of the severity and a fix timeline.
- Credit in the release notes, if you want it. Just say the word, or ask to stay anonymous.

## Honest scope

The God Code sandbox is deny-by-default and in-process: it confines what a scroll may touch (files, network, time, randomness) through explicit grants. It is a safety net for running scrolls you did not write, not a substitute for operating-system-level isolation. Do not run hostile code in the sandbox and assume the host is untouchable.
