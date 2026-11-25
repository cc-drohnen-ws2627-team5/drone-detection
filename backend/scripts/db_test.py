from .storage import database


if __name__ == "__main__":
    with database() as cursor:
        cursor.execute("SELECT count(*) AS detections FROM detections")
        print(cursor.fetchone())
