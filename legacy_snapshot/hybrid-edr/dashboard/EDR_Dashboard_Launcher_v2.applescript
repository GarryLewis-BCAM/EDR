#!/usr/bin/osascript
-- BCAM EDR Dashboard Launcher V2 - Robust Edition
-- Launches collector and dashboard with health verification

property edrDir : "/Users/garrylewis/Security/hybrid-edr"
property launchScript : edrDir & "/launch_edr.sh"
property healthScript : edrDir & "/check_health.sh"
property dashboardURL : "http://localhost:5050"
property maxRetries : 3

on run
	-- Check if launch script exists
	try
		do shell script "test -f " & quoted form of launchScript
	on error
		display alert "❌ EDR Launch Script Missing" message "Cannot find launch script at: " & launchScript & return & return & "Please verify EDR installation." as critical buttons {"OK"} default button 1
		return
	end try
	
	-- Make sure scripts are executable
	try
		do shell script "chmod +x " & quoted form of launchScript & " " & quoted form of healthScript
	end try
	
	set launchSuccess to false
	set retryCount to 0
	
	repeat while not launchSuccess and retryCount < maxRetries
		try
			-- Show launching notification
			display notification "Starting EDR system..." with title "🚀 BCAM EDR" sound name "Submarine"
			
			-- Launch the EDR system
			set launchOutput to do shell script launchScript
			
			-- Wait a moment for services to stabilize
			delay 3
			
			-- Verify health using health check script
			try
				set healthOutput to do shell script healthScript
				
				-- Health check passed
				set launchSuccess to true
				
				-- Open dashboard in browser
				open location dashboardURL
				
				-- Success notification
				display notification "All systems operational" with title "✅ BCAM EDR Started" sound name "Glass"
				
				-- Show brief success dialog (auto-dismiss after 2 seconds)
				display dialog "✅ BCAM EDR System Started Successfully!" & return & return & "📊 Dashboard: " & dashboardURL & return & "🔍 Collector: Running" & return & "📡 Network Tracker: Active" buttons {"OK"} default button 1 with title "EDR Dashboard" with icon note giving up after 2
				
				return
				
			on error healthError
				-- Health check failed
				set retryCount to retryCount + 1
				
				if retryCount < maxRetries then
					-- Retry
					display notification "Health check failed, retrying... (" & retryCount & "/" & maxRetries & ")" with title "⚠️ BCAM EDR" sound name "Funk"
					delay 2
				else
					-- Max retries reached
					display alert "⚠️ EDR Startup Issues" message "The EDR system started but health checks indicate problems:" & return & return & healthError & return & return & "Dashboard may still be accessible at:" & return & dashboardURL buttons {"Open Dashboard Anyway", "View Logs", "Cancel"} default button 1 as warning
					
					set buttonReturned to button returned of result
					
					if buttonReturned is "Open Dashboard Anyway" then
						open location dashboardURL
					else if buttonReturned is "View Logs" then
						do shell script "open -a Console " & quoted form of (edrDir & "/logs/collector.out")
					end if
					
					return
				end if
			end try
			
		on error errMsg number errNum
			set retryCount to retryCount + 1
			
			if retryCount < maxRetries then
				-- Retry on error
				display notification "Startup failed, retrying... (" & retryCount & "/" & maxRetries & ")" with title "⚠️ BCAM EDR" sound name "Funk"
				delay 2
			else
				-- Max retries reached, show error
				display alert "❌ EDR Startup Failed" message "Failed to start EDR system after " & maxRetries & " attempts:" & return & return & "Error: " & errMsg & return & "Code: " & errNum & return & return & "Possible causes:" & return & "• Python environment not configured" & return & "• Missing dependencies" & return & "• Port conflicts" & return & return & "Check logs for details." as critical buttons {"View Logs", "OK"} default button 2
				
				set buttonReturned to button returned of result
				
				if buttonReturned is "View Logs" then
					try
						do shell script "open -a Console " & quoted form of (edrDir & "/logs/collector.out")
					end try
				end if
				
				return
			end if
		end try
	end repeat
	
end run
