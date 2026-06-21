import sqlite3
import json

def run_query():
    try:
        conn = sqlite3.connect('tunnels.db')
        cursor = conn.cursor()
        query = """
        SELECT id, status, url 
        FROM tunnels 
        ORDER BY created_at DESC 
        LIMIT 5;
        """
        cursor.execute(query)
        rows = cursor.fetchall()
        
        result = []
        for row in rows:
            result.append({
                "id": row[0],
                "status": row[1],
                "url": row[2]
            })
        
        print(json.dumps(result, indent=2))
        conn.close()
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    run_query()
