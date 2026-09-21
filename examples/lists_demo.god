# Lists Demo — the scroll of lists: SUM, AVG, CONTAINS.
BEGIN CREATION
  IMPORT "lists"
  DECLARE numbers AS [3, 7, 7, 12]
  REVEAL(SUM(numbers))
  REVEAL(AVG(numbers))
  REVEAL(CONTAINS(numbers, 7))
  REVEAL(CONTAINS(numbers, 99))
  ASCEND
END CREATION
