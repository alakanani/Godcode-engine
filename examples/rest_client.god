# A REST API client that fetches a public user directory and lists it.
#
# Run from the repo root: godcode run examples/rest_client.god
# (plain run, NOT `godcode run --sandbox`: the sandbox withholds network by design).
#
# This scroll needs internet access. It calls HTTP_GET on the public
# JSONPlaceholder test API and reveals one line per user: name and email.
# If the network is unreachable, the TRY/CATCH degrades gracefully to an
# offline summary, so the scroll always ends peacefully.
#
# Verified 2026-09-24: ran against the live JSONPlaceholder API and listed all
# 10 users. If the network were down, the TRY/CATCH would take the offline
# path instead and the scroll would still exit 0.

BEGIN CREATION
  TRY
    DECLARE body AS HTTP_GET("https://jsonplaceholder.typicode.com/users")
    DECLARE users AS JSON_PARSE(body)
    DECLARE total AS LEN(users)
    REVEAL("The registry of users is open. {total} souls were found.")
    DECLARE i AS 0
    WHILE i IS NOT total DO
      DECLARE user AS users[i]
      DECLARE uname AS user["name"]
      DECLARE umail AS user["email"]
      REVEAL("{uname} <{umail}>")
      DECLARE i AS i + 1
    ENDWHILE
  CATCH err
    REVEAL("The network was not reachable ({err}). Showing the offline path instead.")
    REVEAL("Offline summary: 0 users fetched, nothing written, the scroll ends in peace.")
  ENDTRY
END CREATION
