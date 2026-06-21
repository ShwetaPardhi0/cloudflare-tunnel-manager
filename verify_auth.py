import requests

def verify_auth():
    base_url = "http://localhost:1231/api"
    # Correct token from .env
    token = "super-secret-admin-token-123"
    
    # 1. Test Public Endpoint (Health)
    try:
        resp = requests.get(f"{base_url}/health")
        print(f"Public /health: {resp.status_code}")
    except Exception as e:
        print(f"Error /health: {e}")

    # 2. Test Protected Endpoint (Start Tunnel) - Missing Token
    try:
        resp = requests.post(f"{base_url}/tunnel", json={"port": 8080})
        print(f"Protected /tunnel (No Token): {resp.status_code} (Expected 403 or 401)")
    except Exception as e:
        print(f"Error /tunnel (No Token): {e}")

    # 3. Test Protected Endpoint (Start Tunnel) - Wrong Token
    try:
        headers = {"Authorization": "Bearer wrong-token"}
        resp = requests.post(f"{base_url}/tunnel", json={"port": 8080}, headers=headers)
        print(f"Protected /tunnel (Wrong Token): {resp.status_code} (Expected 401)")
    except Exception as e:
        print(f"Error /tunnel (Wrong Token): {e}")

    # 4. Test Protected Endpoint (Start Tunnel) - Correct Token
    # Note: Payload might be invalid for real tunnel (port 8080 might not be open), but we check Auth first.
    try:
        headers = {"Authorization": f"Bearer {token}"}
        resp = requests.post(f"{base_url}/tunnel", json={"port": 1231, "alias": "Auth-Test"}, headers=headers)
        print(f"Protected /tunnel (Correct Token): {resp.status_code} (Expected 200 or payload error, but not 401/403)")
        print(f"Response: {resp.json().get('status')}")
    except Exception as e:
        print(f"Error /tunnel (Correct Token): {e}")

if __name__ == "__main__":
    verify_auth()
