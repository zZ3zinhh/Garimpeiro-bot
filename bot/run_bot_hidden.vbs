' Starts run_bot.bat with no window at all (0 = hidden).
' The Windows Task Scheduler runs this file instead of the .bat directly,
' so no black console window pops up every 10 minutes.
Set shell = CreateObject("WScript.Shell")
folder = Replace(WScript.ScriptFullName, WScript.ScriptName, "")
shell.Run """" & folder & "run_bot.bat""", 0, False
