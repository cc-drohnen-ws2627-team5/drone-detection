from .settings import BUCKET
from .storage import object_store


if __name__ == "__main__":
    object_store().head_bucket(Bucket=BUCKET)
    print(f"Bucket reachable: {BUCKET}")
