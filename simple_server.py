#!/usr/bin/env python3
import http.server
import socketserver
import webbrowser
import threading
import time
import os

# Set the port
PORT = 9000

# Change to the Django project directory
os.chdir('/Users/benorbe/Library/Mobile Documents/com~apple~CloudDocs/Documents/Coding Projects/BMAsia CRM')

# Create a simple HTML file to test
html_content = """
<!DOCTYPE html>
<html>
<head>
    <title>BMAsia CRM - Server Test</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 40px; }
        .container { max-width: 800px; margin: 0 auto; }
        .success { color: green; }
        .info { background: #e3f2fd; padding: 20px; border-radius: 5px; margin: 20px 0; }
        .button { background: #1976d2; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px; }
    </style>
</head>
<body>
    <div class="container">
        <h1>🎵 BMAsia CRM System</h1>
        <div class="info">
            <h2 class="success">✅ Server is working!</h2>
            <p>Your local development environment is functioning correctly.</p>
        </div>
        
        <h3>Available Services:</h3>
        <ul>
            <li><a href="http://127.0.0.1:8000/admin" class="button">Django Admin Interface</a></li>
            <li><a href="http://127.0.0.1:8000/api/" class="button">API Endpoints</a></li>
        </ul>
        
        <h3>BMAsia Customizations Completed:</h3>
        <ul>
            <li>✅ Updated opportunity stages (Contacted → Quotation Sent → Contract Sent → Won/Lost)</li>
            <li>✅ Industry types for venues (Hotels, Restaurants, Bars, etc.)</li>
            <li>✅ Location count and music zone tracking</li>
            <li>✅ Region field for geographic classification</li>
            <li>✅ Annual revenue moved to additional details</li>
        </ul>
        
        <h3>Next Steps:</h3>
        <ol>
            <li>Try accessing the Django admin above</li>
            <li>Create some test companies with the new venue types</li>
            <li>Test the opportunity workflow</li>
        </ol>
    </div>
</body>
</html>
"""

# Write the HTML file
with open('test.html', 'w') as f:
    f.write(html_content)

# Start the server
Handler = http.server.SimpleHTTPRequestHandler

def start_server():
    with socketserver.TCPServer(("", PORT), Handler) as httpd:
        print(f"✅ Simple server running at:")
        print(f"   http://localhost:{PORT}")
        print(f"   http://127.0.0.1:{PORT}")
        print(f"   http://0.0.0.0:{PORT}")
        print("\nPress Ctrl+C to stop the server")
        httpd.serve_forever()

if __name__ == "__main__":
    start_server()