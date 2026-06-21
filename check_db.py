import sqlite3
conn = sqlite3.connect('tunnels.db')
cursor = conn.cursor()
cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
print("Tables:", cursor.fetchall())
cursor.execute("PRAGMA table_info(tunnels);")
print("Tunnels Schema:", cursor.fetchall())
conn.close()
