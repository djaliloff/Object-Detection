import sys
import os

# Add backend-api to sys.path
sys.path.insert(0, os.path.abspath("backend-api"))

from database import SessionLocal
from models import Event
from dotenv import load_dotenv

load_dotenv()

def cleanup_speed_anomalies():
    db = SessionLocal()
    try:
        # Delete events with event_type 'speed_anomaly'
        count = db.query(Event).filter(Event.event_type == 'speed_anomaly').delete(synchronize_session=False)
        db.commit()
        print(f"Successfully deleted {count} 'speed_anomaly' events from the database.")
    except Exception as e:
        print(f"Error during cleanup: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    cleanup_speed_anomalies()
