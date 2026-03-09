import os
import json
import time
import redis
import psycopg2
from datetime import datetime

# Configuration
REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379")
DATABASE_URL = os.getenv("DATABASE_URL")

def connect_redis():
    while True:
        try:
            r = redis.from_url(REDIS_URL)
            r.ping()
            print(f"Event Processor connected to Redis at {REDIS_URL}")
            return r
        except Exception as e:
            print(f"Event Processor waiting for Redis... {e}")
            time.sleep(2)

def main():
    r = connect_redis()
    
    stream_name = "camera:detections"
    group_name = "event_processor_group"
    consumer_name = "processor_01"

    # Create consumer group
    try:
        r.xgroup_create(stream_name, group_name, id='0', mkstream=True)
    except redis.exceptions.ResponseError:
        pass

    print("Starting event processing loop...")
    while True:
        try:
            # Read detections
            messages = r.xreadgroup(group_name, consumer_name, {stream_name: ">"}, count=5, block=2000)
            
            if not messages:
                continue

            for stream, msgs in messages:
                for msg_id, payload in msgs:
                    data = json.loads(payload[b'data'])
                    camera_id = data['camera_id']
                    detections = data['detections']
                    
                    # Logic: If person is detected, trigger an 'intrusion' event
                    persons = [d for d in detections if d['class'] == 'person']
                    
                    if persons:
                        event = {
                            "camera_id": camera_id,
                            "event_type": "intrusion",
                            "severity": "critical",
                            "timestamp": datetime.fromtimestamp(data['timestamp']).isoformat(),
                            "details": f"Detected {len(persons)} person(s)"
                        }
                        
                        # In a real app, we would write to Postgres here:
                        # db.execute("INSERT INTO events ...")
                        print(f"🚨 EVENT TRIGGERED: {event['event_type']} on {camera_id} - {event['details']}")

                        # Also push to a global events stream for the Frontend (WebSockets)
                        r.xadd("system:events", {"data": json.dumps(event)}, maxlen=1000)

                    # Acknowledge
                    r.xack(stream_name, group_name, msg_id)

        except Exception as e:
            print(f"Error in processor loop: {e}")
            time.sleep(1)

if __name__ == "__main__":
    main()
