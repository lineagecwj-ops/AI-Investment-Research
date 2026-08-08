use scripting additions

set launcherScript to "/Users/hankmacmini/Documents/Projects/AI-Investment-Research/launcher/launch_ai_investment_research.sh"

try
	do shell script (quoted form of launcherScript)
on error errorMessage number errorNumber
	display dialog errorMessage buttons {"OK"} default button "OK" with icon stop
end try
