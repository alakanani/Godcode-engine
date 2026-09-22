# Intent demo — DECLARE INTENT names a rite's purpose in plain words.
# When the rite is invoked, the Spirit discerns whether its words still
# walk in the declared intent: alignment is blessed, drift is counseled.
# Nothing here can fail the run; the Spirit counsels, it does not condemn.
BEGIN CREATION
  DECLARE INTENT "bring peace to the household" ON evening_blessing
  DECLARE INTENT "bring peace to the household" ON war_drum

  DEFINE RITE evening_blessing()
    REVEAL("peace upon this house")
  END RITE

  DEFINE RITE war_drum()
    DECLARE tally AS 1 + 2
    REVEAL(tally)
  END RITE

  INVOKE evening_blessing()
  INVOKE war_drum()
END CREATION
