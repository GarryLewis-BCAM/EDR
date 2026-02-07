#!/usr/bin/env swift
import Cocoa
import Foundation

class AppDelegate: NSObject, NSApplicationDelegate {
    var statusItem: NSStatusItem!
    var timer: Timer?
    
    func applicationDidFinishLaunching(_ notification: Notification) {
        statusItem = NSStatusBar.system.statusItem(withLength: NSStatusItem.variableLength)
        
        if let button = statusItem.button {
            button.title = "🛡️"
            button.action = #selector(openDashboard)
            button.target = self
        }
        
        let menu = NSMenu()
        menu.addItem(NSMenuItem(title: "Open EDR Dashboard", action: #selector(openDashboard), keyEquivalent: ""))
        menu.addItem(NSMenuItem.separator())
        menu.addItem(NSMenuItem(title: "Check Status", action: #selector(checkStatus), keyEquivalent: ""))
        menu.addItem(NSMenuItem.separator())
        menu.addItem(NSMenuItem(title: "Quit", action: #selector(quit), keyEquivalent: "q"))
        
        statusItem.menu = menu
        
        // Update status every 30 seconds
        timer = Timer.scheduledTimer(withTimeInterval: 30.0, repeats: true) { [weak self] _ in
            self?.updateStatus()
        }
        
        updateStatus()
    }
    
    @objc func openDashboard() {
        NSWorkspace.shared.open(URL(string: "http://localhost:5050")!)
    }
    
    @objc func checkStatus() {
        let task = Process()
        task.launchPath = "/usr/bin/lsof"
        task.arguments = ["-ti:5050"]
        
        let pipe = Pipe()
        task.standardOutput = pipe
        task.launch()
        
        let data = pipe.fileHandleForReading.readDataToEndOfFile()
        let output = String(data: data, encoding: .utf8)?.trimmingCharacters(in: .whitespacesAndNewlines) ?? ""
        
        let alert = NSAlert()
        alert.messageText = "EDR Status"
        alert.informativeText = output.isEmpty ? "❌ Dashboard is NOT running" : "✅ Dashboard is running (PID: \(output))"
        alert.alertStyle = .informational
        alert.addButton(withTitle: "OK")
        alert.runModal()
    }
    
    @objc func updateStatus() {
        let task = Process()
        task.launchPath = "/usr/bin/lsof"
        task.arguments = ["-ti:5050"]
        
        let pipe = Pipe()
        task.standardOutput = pipe
        task.launch()
        
        let data = pipe.fileHandleForReading.readDataToEndOfFile()
        let output = String(data: data, encoding: .utf8)?.trimmingCharacters(in: .whitespacesAndNewlines) ?? ""
        
        DispatchQueue.main.async { [weak self] in
            if let button = self?.statusItem.button {
                button.title = output.isEmpty ? "🛡️❌" : "🛡️✅"
            }
        }
    }
    
    @objc func quit() {
        NSApplication.shared.terminate(nil)
    }
}

let app = NSApplication.shared
let delegate = AppDelegate()
app.delegate = delegate
app.run()
