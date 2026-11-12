import io
from minio import Minio
from minio.error import S3Error

def test_s3_storage():
    # 1. Initialize the client targeting the local MinIO container
    client = Minio(
        "localhost:9000",
        access_key="minioadmin",
        secret_key="minioadmin",
        secure=False
    )

    bucket_name = "drone-snapshots"
    object_name = "test_frame.jpg"

    print("[*] Connecting to the MinIO service...")

    # 2. Create the target bucket if it does not already exist
    if not client.bucket_exists(bucket_name):
        client.make_bucket(bucket_name)
        print(f"[+] Successfully created the bucket: '{bucket_name}'")
    else:
        print(f"[*] The bucket '{bucket_name}' already exists.")

    # 3. Create a mock JPEG binary payload in memory
    mock_image_data = b"\xFF\xD8\xFF\xE0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00\xFF\xDB\x00C\x00"
    data_stream = io.BytesIO(mock_image_data)

    # 4. Upload the binary payload
    client.put_object(
        bucket_name=bucket_name,
        object_name=object_name,
        data=data_stream,
        length=len(mock_image_data),
        content_type="image/jpeg"
    )
    print(f"[+] Successfully uploaded the object '{object_name}' to the bucket '{bucket_name}'.")

    # 5. Verify the uploaded object
    stat = client.stat_object(bucket_name, object_name)
    print(f"[✓] Object verified: size = {stat.size} bytes, content_type = {stat.content_type}")

if __name__ == "__main__":
    try:
        test_s3_storage()
    except S3Error as err:
        print(f"[-] S3 operation failed: {err}")
