
# God Code Contributor Tasks – GitHub Issues

Welcome to the contributor space for God Code! Below are pre-defined issues to help guide new collaborators in building the divine logic engine.

---

## 🧠 1. Add IF...THEN...ELSE logic to interpreter

**Description**  
Implement conditional logic support in `interpreter.py` so users can write God Code like:

```
IF seeker IS worthy THEN REVEAL("truth") ELSE REVEAL("trial")
```

**Expected Behavior**  
- Evaluate variable in environment
- Execute THEN or ELSE based on truth value
- Add audit entry for decision path taken

**Labels**: `feature`, `logic`, `first-timers`

---

## 🔁 2. Implement FOR loop logic

**Description**  
Enable looping through comma-separated lists in God Code:

```
DECLARE prophets AS Moses,Elijah,Elisha  
FOR prophet IN prophets  
  BREATHE life INTO prophet  
```

**Expected Behavior**  
- Split values into a list
- Iterate and execute inner command
- Support nested execution in future

**Labels**: `feature`, `loop`, `contribution-welcome`

---

## 🕒 3. Add timestamp to each audit log entry

**Description**  
Improve `audit.log` by prefixing every logged command with a timestamp like:

```
[2025-05-06 17:30:21] COMMAND: BREATHE life INTO soul
```

**Expected Behavior**  
- Add timestamp formatting using `datetime.now()`
- Keep logs readable and spiritual

**Labels**: `enhancement`, `logging`, `good-first-issue`

---

## 🔮 4. Expand REVEAL to support conditions

**Description**  
Support revealing different messages based on variable context:

```
IF seeker IS prophet THEN REVEAL("vision") ELSE REVEAL("cloud")
```

**Labels**: `feature`, `expression`, `interpreter`

---

## 🌐 5. Build syntax highlighter or online demo

**Description**  
Create a simple web interface where users can type God Code and see it interpreted live.

**Tools**: `Streamlit`, `React`, `Replit`, `Jupyter`, or `Next.js`

**Labels**: `frontend`, `demo`, `project-help`

---
