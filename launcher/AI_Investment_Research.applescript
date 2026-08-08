use framework "Foundation"
use framework "AppKit"

set launcherScript to "/Users/hankmacmini/Documents/Projects/AI-Investment-Research/launcher/launch_ai_investment_research.sh"

set launcherTask to current application's NSTask's alloc()'s init()
launcherTask's setLaunchPath:"/bin/bash"
launcherTask's setArguments:{launcherScript}
launcherTask's |launch|()
launcherTask's waitUntilExit()

set exitStatus to launcherTask's terminationStatus()
if exitStatus is not 0 then
	set alertMessage to "Launcher script failed with status " & exitStatus & ". Please check ~/Library/Logs/AI-Investment-Research/launcher.log"
	set launchAlert to current application's NSAlert's alloc()'s init()
	launchAlert's setMessageText:"AI Investment Research 無法啟動。"
	launchAlert's setInformativeText:alertMessage
	launchAlert's addButtonWithTitle:"確定"
	launchAlert's runModal()
	error alertMessage
end if
