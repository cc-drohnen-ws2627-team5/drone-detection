import psycopg2
from datetime import datetime

DB_CONFIG = {
    "host": "localhost",
    "port": 5432,
    "dbname": "drone_db",
    "user": "drone_user",
    "password": "drone_password",
}

def test_db_connection():
    print("[*] Connecting to the PostgreSQL database...")
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()

    # 1. Insert a mock detection record
    insert_query = """
    INSERT INTO detections (drone_id, confidence, status, image_url, detected_at)
    VALUES (%s, %s, %s, %s, %s)
    RETURNING id, drone_id, confidence, status, detected_at;
    """
    sample_data = ("DRONE-TEST-01", 0.96, "detected", "http://localhost:9000/frames/test.jpg", datetime.utcnow())
    
    cur.execute(insert_query, sample_data)
    row = cur.fetchone()
    conn.commit()
    print(f"[+] Successfully inserted the row ID: {row[0]} | Drone: {row[1]} | Confidence: {row[2]}")

    # 2. Query the table to verify data persistence
    cur.execute("SELECT id, drone_id, confidence, status, detected_at FROM detections ORDER BY id DESC LIMIT 1;")
    fetched = cur.fetchone()
    print(f"[+] Verified the record from the database: {fetched}")

    cur.close()
    conn.close()
    print("[✓] The database test completed successfully.")

if __name__ == "__main__":
    test_db_connection()
