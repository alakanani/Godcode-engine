# The Scroll of JSON -- encoding and decoding the tongue of machines.
# Written in pure God Code (stdlib builtins only); a community scroll.
# Rites: JSON_ENCODE, JSON_DECODE, JSON_ESCAPE.
# Objects decode into lists of [key, value] pairs, for the tongue of
# God Code knows no dictionaries.

DEFINE RITE JSON_ESCAPE(s)
DECLARE out AS ""
DECLARE i AS 0
WHILE i < LEN(s) DO
DECLARE c AS s[i]
IF c == "\"" THEN
DECLARE out AS out + "\\\""
ELSE
IF c == "\\" THEN
DECLARE out AS out + "\\\\"
ELSE
IF c == "\n" THEN
DECLARE out AS out + "\\n"
ELSE
IF c == "\t" THEN
DECLARE out AS out + "\\t"
ELSE
DECLARE out AS out + c
ENDIF
ENDIF
ENDIF
ENDIF
DECLARE i AS i + 1
ENDWHILE
RETURN out
END RITE

DEFINE RITE JSON_ENCODE(value)
DECLARE t AS TYPE(value)
IF t == "string" THEN
RETURN "\"" + JSON_ESCAPE(value) + "\""
ENDIF
IF t == "list" THEN
DECLARE parts AS []
DECLARE i AS 0
WHILE i < LEN(value) DO
DECLARE parts AS PUSH(parts, JSON_ENCODE(value[i]))
DECLARE i AS i + 1
ENDWHILE
RETURN "[" + JOIN(parts, ",") + "]"
ENDIF
IF t == "boolean" THEN
IF value THEN
RETURN "true"
ENDIF
RETURN "false"
ENDIF
IF t == "void" THEN
RETURN "null"
ENDIF
RETURN STR(value)
END RITE

DEFINE RITE JSON_SKIP(text, pos)
DECLARE n AS LEN(text)
WHILE pos < n DO
DECLARE c AS text[pos]
IF c == " " THEN
DECLARE pos AS pos + 1
ELSE
IF c == "\n" THEN
DECLARE pos AS pos + 1
ELSE
IF c == "\t" THEN
DECLARE pos AS pos + 1
ELSE
RETURN pos
ENDIF
ENDIF
ENDIF
ENDWHILE
RETURN pos
END RITE

DEFINE RITE JSON_IS_DIGIT(c)
IF c == "0" OR c == "1" OR c == "2" OR c == "3" OR c == "4" OR c == "5" OR c == "6" OR c == "7" OR c == "8" OR c == "9" THEN
RETURN true
ENDIF
RETURN false
END RITE

DEFINE RITE JSON_PARSE_STRING(text, pos)
DECLARE out AS ""
DECLARE i AS pos + 1
DECLARE n AS LEN(text)
WHILE i < n DO
DECLARE c AS text[i]
IF c == "\"" THEN
RETURN [out, i + 1]
ENDIF
IF c == "\\" THEN
DECLARE e AS text[i + 1]
IF e == "\"" THEN
DECLARE out AS out + "\""
ELSE
IF e == "\\" THEN
DECLARE out AS out + "\\"
ELSE
IF e == "n" THEN
DECLARE out AS out + "\n"
ELSE
IF e == "t" THEN
DECLARE out AS out + "\t"
ELSE
DECLARE out AS out + e
ENDIF
ENDIF
ENDIF
ENDIF
DECLARE i AS i + 2
ELSE
DECLARE out AS out + c
DECLARE i AS i + 1
ENDIF
ENDWHILE
RETURN [out, i]
END RITE

DEFINE RITE JSON_SLICE(text, start, stop)
DECLARE out AS ""
DECLARE i AS start
WHILE i < stop DO
DECLARE out AS out + text[i]
DECLARE i AS i + 1
ENDWHILE
RETURN out
END RITE

DEFINE RITE JSON_PARSE_NUMBER(text, pos)
DECLARE i AS pos
DECLARE n AS LEN(text)
WHILE i < n DO
DECLARE c AS text[i]
IF JSON_IS_DIGIT(c) THEN
DECLARE i AS i + 1
ELSE
IF c == "." OR c == "-" OR c == "+" OR c == "e" OR c == "E" THEN
DECLARE i AS i + 1
ELSE
RETURN [NUM(JSON_SLICE(text, pos, i)), i]
ENDIF
ENDIF
ENDWHILE
RETURN [NUM(JSON_SLICE(text, pos, i)), i]
END RITE

DEFINE RITE JSON_EXPECT(text, pos, word)
DECLARE i AS 0
WHILE i < LEN(word) DO
IF text[pos + i] == word[i] THEN
DECLARE i AS i + 1
ELSE
RETURN -1
ENDIF
ENDWHILE
RETURN pos + LEN(word)
END RITE

DEFINE RITE JSON_PARSE_VALUE(text, pos)
DECLARE i AS JSON_SKIP(text, pos)
DECLARE c AS text[i]
IF c == "\"" THEN
RETURN JSON_PARSE_STRING(text, i)
ENDIF
IF c == "[" THEN
RETURN JSON_PARSE_ARRAY(text, i)
ENDIF
IF c == "{" THEN
RETURN JSON_PARSE_OBJECT(text, i)
ENDIF
IF c == "t" THEN
RETURN [true, JSON_EXPECT(text, i, "true")]
ENDIF
IF c == "f" THEN
RETURN [false, JSON_EXPECT(text, i, "false")]
ENDIF
IF c == "n" THEN
RETURN [void, JSON_EXPECT(text, i, "null")]
ENDIF
RETURN JSON_PARSE_NUMBER(text, i)
END RITE

DEFINE RITE JSON_PARSE_ARRAY(text, pos)
DECLARE items AS []
DECLARE i AS JSON_SKIP(text, pos + 1)
IF text[i] == "]" THEN
RETURN [items, i + 1]
ENDIF
WHILE true DO
DECLARE valres AS JSON_PARSE_VALUE(text, i)
DECLARE items AS PUSH(items, valres[0])
DECLARE i AS JSON_SKIP(text, valres[1])
IF text[i] == "," THEN
DECLARE i AS i + 1
ELSE
RETURN [items, i + 1]
ENDIF
ENDWHILE
END RITE

DEFINE RITE JSON_PARSE_OBJECT(text, pos)
DECLARE pairs AS []
DECLARE i AS JSON_SKIP(text, pos + 1)
IF text[i] == "}" THEN
RETURN [pairs, i + 1]
ENDIF
WHILE true DO
DECLARE i AS JSON_SKIP(text, i)
DECLARE keyres AS JSON_PARSE_STRING(text, i)
DECLARE key AS keyres[0]
DECLARE i AS JSON_SKIP(text, keyres[1] + 1)
DECLARE valres AS JSON_PARSE_VALUE(text, i)
DECLARE pairs AS PUSH(pairs, [key, valres[0]])
DECLARE i AS JSON_SKIP(text, valres[1])
IF text[i] == "," THEN
DECLARE i AS i + 1
ELSE
RETURN [pairs, i + 1]
ENDIF
ENDWHILE
END RITE

DEFINE RITE JSON_DECODE(text)
DECLARE res AS JSON_PARSE_VALUE(text, 0)
RETURN res[0]
END RITE
