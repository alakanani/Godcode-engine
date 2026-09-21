# SUMMON Demo — call upon a plugin spirit from the engine.
#
# SUMMON("plugin.verb", args...) reaches through the FFI into an installed
# plugin. Here we greet the clockwork spirit from the example plugin
# `plugins/clockwork.py`. Install it with the plugin's README guidance,
# then `godcode run examples/summon_demo.god`.
#
# This file needs no plugin to parse: `godcode check` is pure lex + parse,
# so it passes whether or not pillar 3's plugins are installed.

BEGIN CREATION
  REVEAL("the seeker lifts their voice to the clockwork")
  DECLARE the_hour AS SUMMON("clockwork.now")
  REVEAL("the clockwork speaks: " + STR(the_hour))
  ASCEND
END CREATION
