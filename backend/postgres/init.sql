CREATE TABLE IF NOT EXISTS detections (
    id SERIAL PRIMARY KEY,
    drone_id VARCHAR(50) NOT NULL,
    confidence REAL NOT NULL,
    status VARCHAR(50) NOT NULL,
    image_url TEXT,
    detected_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_detections_drone_id ON detections(drone_id);
CREATE INDEX IF NOT EXISTS idx_detections_detected_at ON detections(detected_at);
