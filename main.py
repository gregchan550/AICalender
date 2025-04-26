from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from datetime import datetime
from google.oauth2 import service_account
from googleapiclient.discovery import build
from dateutil import parser
import json
import logging
import pytz
from typing import Optional

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()

# Your email address for the calendar
YOUR_EMAIL = "gregchan550@gmail.com"

# Pydantic model for the reminder request
class ReminderRequest(BaseModel):
    title: str
    due_date: str  # ISO format date string
    end_date: Optional[str] = None  # Optional end time

def get_calendar_service():
    """Create and return Google Calendar service instance."""
    try:
        logger.info("Initializing Google Calendar service...")
        credentials = service_account.Credentials.from_service_account_file(
            'service-account.json',
            scopes=['https://www.googleapis.com/auth/calendar']
        )
        service = build('calendar', 'v3', credentials=credentials)
        
        # List available calendars
        calendar_list = service.calendarList().list().execute()
        logger.info("Available calendars:")
        for calendar in calendar_list.get('items', []):
            logger.info(f"- {calendar['summary']} (ID: {calendar['id']}, Access Role: {calendar.get('accessRole', 'unknown')})")
            if calendar.get('primary', False):
                logger.info("  This is marked as the primary calendar")
            logger.info(f"  Owner: {calendar.get('owner', {}).get('email', 'unknown')}")
        
        logger.info("Calendar service initialized successfully")
        return service
    except Exception as e:
        logger.error(f"Failed to initialize calendar service: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to initialize calendar service: {str(e)}")

@app.get("/events")
async def get_events(start: str, end: str):
    """Get calendar events for a specific time range."""
    try:
        service = get_calendar_service()
        
        events_result = service.events().list(
            calendarId=YOUR_EMAIL,
            timeMin=start,
            timeMax=end,
            singleEvents=True,
            orderBy='startTime'
        ).execute()
        
        events = events_result.get('items', [])
        return events
        
    except Exception as e:
        logger.error(f"Failed to fetch events: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch events: {str(e)}")

@app.post("/reminder")
async def create_reminder(reminder: ReminderRequest):
    try:
        logger.info(f"Creating reminder: {reminder.title} for {reminder.due_date}")
        # Parse the due date
        start_time = parser.parse(reminder.due_date)
        end_time = parser.parse(reminder.end_date) if reminder.end_date else start_time
        
        # Convert to Brisbane timezone
        brisbane_tz = pytz.timezone('Australia/Brisbane')
        start_time = start_time.astimezone(brisbane_tz)
        end_time = end_time.astimezone(brisbane_tz)
        logger.info(f"Parsed time range (Brisbane time): {start_time} - {end_time}")
        
        # Create calendar service
        service = get_calendar_service()
        
        # Prepare the event
        event = {
            'summary': reminder.title,
            'start': {
                'dateTime': start_time.isoformat(),
                'timeZone': 'Australia/Brisbane',
            },
            'end': {
                'dateTime': end_time.isoformat(),
                'timeZone': 'Australia/Brisbane',
            },
        }
        
        logger.info(f"Attempting to create event: {json.dumps(event, indent=2)}")
        # Try to create event in your calendar directly
        try:
            event = service.events().insert(calendarId=YOUR_EMAIL, body=event).execute()
            logger.info(f"Event created successfully in your calendar")
        except Exception as e:
            logger.warning(f"Failed to create event in your calendar: {str(e)}")
            # Fallback to primary calendar
            event = service.events().insert(calendarId='primary', body=event).execute()
            logger.info(f"Event created successfully in primary calendar")
        
        logger.info(f"Event created successfully with ID: {event.get('id')} and link: {event.get('htmlLink')}")
        
        return {
            "status": "success",
            "message": "Reminder created successfully",
            "event_id": event.get('id'),
            "event_link": event.get('htmlLink')
        }
        
    except Exception as e:
        logger.error(f"Failed to create reminder: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to create reminder: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
