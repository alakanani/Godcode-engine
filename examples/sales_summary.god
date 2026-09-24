# Sales Summary
#
# Reads examples/data/sales.json, walks the records with a WHILE loop, and
# computes the number of sales, the total revenue, the average sale value,
# and the item name of the single highest-value sale. It writes a dated,
# human-readable report to examples/data/sales_report.txt and reveals the
# same summary lines to the console. Money values are rounded to the thebe
# by the TRUNC and MONEY rites below.
#
# Run from the repo root:
#   godcode run examples/sales_summary.god

BEGIN CREATION
  DEFINE RITE TRUNC(x)
    DECLARE big AS 0
    WHILE (big + 1) * 10000 <= x DO
      DECLARE big AS big + 1
    ENDWHILE
    DECLARE t AS big * 10000
    DECLARE rest AS x - t
    DECLARE small AS 0
    WHILE small + 1 <= rest DO
      DECLARE small AS small + 1
    ENDWHILE
    RETURN t + small
  END RITE

  DEFINE RITE MONEY(amount)
    DECLARE cents AS TRUNC(amount * 100 + 0.5)
    DECLARE whole AS 0
    WHILE (whole + 1) * 100 <= cents DO
      DECLARE whole AS whole + 1
    ENDWHILE
    DECLARE rem AS cents - whole * 100
    IF rem < 10 THEN
      RETURN "P " + STR(whole) + ".0" + STR(rem)
    ENDIF
    RETURN "P " + STR(whole) + "." + STR(rem)
  END RITE

  DEFINE RITE BEST_NAME(current_name, current_value, new_name, new_value)
    IF new_value > current_value THEN
      RETURN new_name
    ENDIF
    RETURN current_name
  END RITE

  DEFINE RITE BEST_VALUE(current_value, new_value)
    IF new_value > current_value THEN
      RETURN new_value
    ENDIF
    RETURN current_value
  END RITE

  DECLARE sales_path AS "examples/data/sales.json"
  IF FILE_EXISTS(sales_path) THEN
    DECLARE raw AS READ_FILE(sales_path)
    DECLARE sales AS JSON_PARSE(raw)
    DECLARE count AS 0
    DECLARE total AS 0
    DECLARE best_item AS ""
    DECLARE best_value AS 0
    DECLARE i AS 0
    WHILE i < LEN(sales) DO
      DECLARE sale AS sales[i]
      DECLARE value AS sale["qty"] * sale["price"]
      DECLARE count AS count + 1
      DECLARE total AS total + value
      DECLARE best_item AS BEST_NAME(best_item, best_value, sale["item"], value)
      DECLARE best_value AS BEST_VALUE(best_value, value)
      DECLARE i AS i + 1
    ENDWHILE
    DECLARE average AS total / count
    DECLARE today AS DATE_TODAY()
    DECLARE report AS "Sales report for " + today + "\n\nNumber of sales: " + STR(count) + "\nTotal revenue: " + MONEY(total) + "\nAverage sale value: " + MONEY(average) + "\nHighest single sale: " + best_item + " (" + MONEY(best_value) + ")\n"
    DECLARE written AS WRITE_FILE("examples/data/sales_report.txt", report)
    REVEAL("Number of sales: {count}")
    REVEAL("Total revenue: {MONEY(total)}")
    REVEAL("Average sale value: {MONEY(average)}")
    REVEAL("Highest single sale: {best_item} ({MONEY(best_value)})")
    REVEAL("Report written to examples/data/sales_report.txt ({written} characters).")
  ELSE
    REVEAL("Could not find examples/data/sales.json. Nothing to summarize.")
  ENDIF
END CREATION
