# Reminder to Calendar Service

This FastAPI service creates Google Calendar events from reminder requests.

## Setup

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Set up Google Calendar API:
   - Go to Google Cloud Console
   - Create a new project
   - Enable the Google Calendar API
   - Create a service account
   - Download the service account key JSON file
   - Rename it to `service-account.json` and place it in the root directory
   - Share your Google Calendar with the service account email

## Running the Server

```bash
python main.py
```

The server will start on http://localhost:8000

## Usage

Send a POST request to `/reminder` with a JSON body:

```bash
curl -X POST http://localhost:8000/reminder \
  -H "Content-Type: application/json" \
  -d '{"title": "My Reminder", "due_date": "2024-03-20T15:00:00Z"}'
```

The `due_date` should be in ISO format with timezone information.

## Response

Success response will look like:
```json
{
  "status": "success",
  "message": "Reminder created successfully",
  "event_id": "event_id_from_google_calendar"
}
``` 