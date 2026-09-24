# File Reporter
#
# Walks the examples/data directory, reads every file, and reveals one line
# per file with its character count. Then it reveals a short summary: the
# number of files, the total characters across all files, and the longest
# file by characters. Accumulation uses WHILE loops, whose bodies share the
# outer scope.
#
# Run from the repo root:
#   godcode run examples/file_reporter.god

BEGIN CREATION
  DEFINE RITE LONGER_NAME(current_name, current_chars, new_name, new_chars)
    IF new_chars > current_chars THEN
      RETURN new_name
    ENDIF
    RETURN current_name
  END RITE

  DEFINE RITE LONGER_CHARS(current_chars, new_chars)
    IF new_chars > current_chars THEN
      RETURN new_chars
    ENDIF
    RETURN current_chars
  END RITE

  DECLARE data_dir AS "examples/data"
  IF FILE_EXISTS(data_dir) THEN
    DECLARE entries AS LIST_DIR(data_dir)
    DECLARE total_files AS 0
    DECLARE total_chars AS 0
    DECLARE longest_name AS ""
    DECLARE longest_chars AS 0
    DECLARE i AS 0
    WHILE i < LEN(entries) DO
      DECLARE name AS entries[i]
      DECLARE text AS READ_FILE(data_dir + "/" + name)
      DECLARE chars AS LEN(text)
      REVEAL("{name} holds {chars} characters.")
      DECLARE total_files AS total_files + 1
      DECLARE total_chars AS total_chars + chars
      DECLARE longest_name AS LONGER_NAME(longest_name, longest_chars, name, chars)
      DECLARE longest_chars AS LONGER_CHARS(longest_chars, chars)
      DECLARE i AS i + 1
    ENDWHILE
    REVEAL("Total files: {total_files}")
    REVEAL("Total characters: {total_chars}")
    REVEAL("Longest file: {longest_name}")
  ELSE
    REVEAL("The data directory is missing. Nothing to report.")
  ENDIF
END CREATION
