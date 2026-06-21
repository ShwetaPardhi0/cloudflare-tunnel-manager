import requests
import time

def create_tunnel():
    try:
        url = "http://localhost:1231/api/tunnel"
        payload = {"port": 1231, "alias": "Verification-Tunnel"}
        response = requests.post(url, json=payload)
        print(f"Status: {response.status_code}")
        print(f"Response: {response.json()}")
        
        if response.status_code == 200:
            print("Tunnel requested successfully. Waiting for connection...")
            tunnel_id = response.json().get("tunnel_id")
            # Wait for URL to be generated
            for _ in range(30):
                resp = requests.get(f"http://localhost:1231/api/tunnels")
                tunnels = resp.json()
                for t in tunnels:
                    if t["tunnel_id"] == tunnel_id and t["status"] == "connected":
                        print(f"Tunnel connected! URL: {t['url']}")
                        return
                time.sleep(1)
            print("Timed out waiting for connection.")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    create_tunnel()
