import http.server
import socketserver
import threading
import sys

def start_server(port, name):
    class Handler(http.server.SimpleHTTPRequestHandler):
        def do_get(self):
            self.send_response(200)
            self.send_header("Content-type", "text/html")
            self.end_headers()
            self.wfile.write(f"<h1>Hello from {name}!</h1><p>Running on port {port}</p>".encode())

        def log_message(self, format, *args):
            return # Silent logs

    with socketserver.TCPServer(("", port), Handler) as httpd:
        print(f"DEBUG: {name} started on port {port}")
        httpd.serve_forever()

if __name__ == "__main__":
    t1 = threading.Thread(target=start_server, args=(3000, "Test Server 3000"), daemon=True)
    t2 = threading.Thread(target=start_server, args=(4000, "Test Server 4000"), daemon=True)
    
    t1.start()
    t2.start()
    
    print("\n--- Test Servers are LIVE! ---")
    print("Port 3000: http://localhost:3000")
    print("Port 4000: http://localhost:4000")
    print("Press Ctrl+C to stop.\n")
    
    try:
        while True:
            import time
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nStopping test servers...")
        sys.exit(0)
