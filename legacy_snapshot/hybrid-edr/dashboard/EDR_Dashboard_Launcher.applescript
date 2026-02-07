#!/usr/bin/osascript
-- BCAM EDR Dashboard Launcher (HTTP - No Certificate Warnings)
-- Opens dashboard in default browser with status check

set dashboardURL to "http://localhost:5051"

-- Check if dashboard is running
try
	set httpCode to do shell script "curl -s -o /dev/null -w '%{http_code}' " & dashboardURL
	
	if httpCode is "200" then
		-- Dashboard is running, open it
		open location dashboardURL
		display notification "Dashboard opened successfully" with title "✅ BCAM EDR" sound name "Glass"
	else
		-- Dashboard not responding
		display alert "⚠️ Dashboard Not Responding" message "HTTP " & httpCode & " - Please check the service" as warning
	end if
on error errMsg
	display alert "❌ Dashboard Offline" message "Could not connect to dashboard. Error: " & errMsg as critical
end try
