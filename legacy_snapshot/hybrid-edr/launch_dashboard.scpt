-- BCAM EDR Dashboard Launcher
-- Opens dashboard in default browser with status check

on run
	-- Dashboard URL
	set dashboardURL to "http://localhost:5050"
	
	-- Check if dashboard is running
	try
		do shell script "curl -s -o /dev/null -w '%{http_code}' http://localhost:5050"
		set httpCode to result
		
		if httpCode is "200" then
			-- Dashboard is running, open it
			open location dashboardURL
			
			display notification "Dashboard opened successfully" with title "🛡️ BCAM EDR" subtitle "Status: ONLINE"
		else
			-- Dashboard not responding, try to start it
			display notification "Starting EDR Dashboard..." with title "🛡️ BCAM EDR" subtitle "Please wait..."
			
			do shell script "cd /Users/garrylewis/Security/hybrid-edr && nohup python3 dashboard/app.py > /tmp/dashboard.log 2>&1 &"
			delay 3
			
			-- Open browser
			open location dashboardURL
		end if
		
	on error errMsg
		-- Dashboard not running, start it
		display notification "Starting EDR Dashboard..." with title "🛡️ BCAM EDR" subtitle "Initializing..."
		
		do shell script "cd /Users/garrylewis/Security/hybrid-edr && nohup python3 dashboard/app.py > /tmp/dashboard.log 2>&1 &"
		delay 3
		
		-- Open browser
		open location dashboardURL
		
		display notification "Dashboard launched" with title "🛡️ BCAM EDR" subtitle "Loading interface..."
	end try
end run
