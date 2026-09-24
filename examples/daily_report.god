# A dated daily report generator.
#
# Run from the repo root: godcode run examples/daily_report.god
#
# It prints a headline with today's human-readable date, formats a short
# list of tasks with a rite (done vs pending), and closes with a summary of
# the counts. Demonstrates rites, WHILE loops, string interpolation, and
# the DATE_TODAY and FORMAT_DATE builtins.
#
# Verified 2026-09-24: printed "Daily summary for September 24, 2026.",
# listed all 5 tasks, and closed with the correct 3-done / 2-pending counts.

BEGIN CREATION
  DEFINE RITE task_line(name, done)
    IF done IS 1 THEN
      RETURN "[x] " + name
    ELSE
      RETURN "[ ] " + name
    ENDIF
  END RITE

  DECLARE today AS DATE_TODAY()
  DECLARE pretty AS FORMAT_DATE(today, "%B %d, %Y")
  REVEAL("Daily summary for {pretty}.")
  REVEAL("")

  DECLARE task_names AS ["Walk the garden rows", "Water the seedlings", "Write the market list", "Call the seed supplier", "Review the harvest notes"]
  DECLARE task_dones AS [1, 1, 0, 1, 0]

  DECLARE i AS 0
  DECLARE done_count AS 0
  DECLARE pending_count AS 0
  WHILE i IS NOT LEN(task_names) DO
    DECLARE tname AS task_names[i]
    DECLARE tdone AS task_dones[i]
    REVEAL(task_line(tname, tdone))
    IF tdone IS 1 THEN
      DECLARE done_count AS done_count + 1
    ELSE
      DECLARE pending_count AS pending_count + 1
    ENDIF
    DECLARE i AS i + 1
  ENDWHILE

  REVEAL("")
  REVEAL("{done_count} tasks done, {pending_count} still pending. The day is blessed.")
END CREATION
