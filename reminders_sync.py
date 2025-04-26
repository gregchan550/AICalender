import subprocess
import json
import datetime
import pytz
import requests
from typing import List, Dict, Optional
from dataclasses import dataclass
from datetime import timedelta

@dataclass
class TimeSlot:
    start: datetime.datetime
    end: datetime.datetime
    duration: timedelta

@dataclass
class Task:
    title: str
    notes: str
    priority: int
    due: Optional[str]
    estimated_duration: timedelta = timedelta(minutes=30)  # default 30 min

def get_reminders_from_todo():
    """Get all reminders from the ToDo list using AppleScript."""
    apple_script = '''
    tell application "Reminders"
        set todoList to list "ToDo"
        set reminderItems to reminders in todoList whose completed is false
        set jsonData to "["
        repeat with i from 1 to count of reminderItems
            set reminderItem to item i of reminderItems
            set itemData to "{"
            set itemData to itemData & "\\"title\\": \\"" & (name of reminderItem as string) & "\\""
            
            -- Add notes if they exist
            if body of reminderItem is not missing value then
                set itemData to itemData & ", \\"notes\\": \\"" & (body of reminderItem as string) & "\\""
            else
                set itemData to itemData & ", \\"notes\\": \\"\\"" 
            end if
            
            -- Add due date if it exists
            if due date of reminderItem is not missing value then
                set dueDate to due date of reminderItem
                set dueDateStr to ((year of dueDate) as string) & "-" & ¬
                    ((month of dueDate) as string) & "-" & ¬
                    ((day of dueDate) as string) & " " & ¬
                    ((time string of dueDate) as string)
                set itemData to itemData & ", \\"due\\": \\"" & dueDateStr & "\\""
            else
                set itemData to itemData & ", \\"due\\": null"
            end if
            
            -- Add priority
            set itemData to itemData & ", \\"priority\\": " & (priority of reminderItem as string)
            
            set itemData to itemData & "}"
            
            -- Add comma if not last item
            if i < count of reminderItems then
                set itemData to itemData & ","
            end if
            
            set jsonData to jsonData & itemData
        end repeat
        set jsonData to jsonData & "]"
        return jsonData
    end tell
    '''
    
    try:
        result = subprocess.run(['osascript', '-e', apple_script], 
                              capture_output=True, text=True)
        if result.returncode == 0:
            try:
                reminders = json.loads(result.stdout)
                return [Task(**reminder) for reminder in reminders]
            except json.JSONDecodeError as e:
                print(f"Error parsing JSON: {str(e)}")
                return []
        else:
            print(f"Error getting reminders: {result.stderr}")
            return []
    except Exception as e:
        print(f"Error accessing Reminders: {str(e)}")
        return []

def get_calendar_events(start_date: datetime.datetime, end_date: datetime.datetime) -> List[Dict]:
    """Fetch existing calendar events for the specified date range."""
    url = "http://localhost:8000/events"
    params = {
        "start": start_date.isoformat(),
        "end": end_date.isoformat()
    }
    
    try:
        response = requests.get(url, params=params)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"Error fetching calendar events: {str(e)}")
        return []

def find_available_slots(events: List[Dict], date: datetime.datetime, min_duration: timedelta) -> List[TimeSlot]:
    """Find available time slots in the calendar."""
    brisbane_tz = pytz.timezone('Australia/Brisbane')
    start_of_day = date.replace(hour=9, minute=0, second=0, microsecond=0)  # Start at 9 AM
    end_of_day = date.replace(hour=17, minute=0, second=0, microsecond=0)   # End at 5 PM
    
    # Convert events to busy slots
    busy_slots = []
    for event in events:
        start = datetime.datetime.fromisoformat(event['start']['dateTime'])
        end = datetime.datetime.fromisoformat(event['end']['dateTime'])
        busy_slots.append((start, end))
    
    # Sort busy slots
    busy_slots.sort(key=lambda x: x[0])
    
    # Find free slots
    free_slots = []
    current_time = start_of_day
    
    for busy_start, busy_end in busy_slots:
        if current_time < busy_start:
            duration = busy_start - current_time
            if duration >= min_duration:
                free_slots.append(TimeSlot(current_time, busy_start, duration))
        current_time = max(current_time, busy_end)
    
    # Add final slot if there's time left
    if current_time < end_of_day:
        duration = end_of_day - current_time
        if duration >= min_duration:
            free_slots.append(TimeSlot(current_time, end_of_day, duration))
    
    return free_slots

def estimate_task_duration(task: Task) -> timedelta:
    """Estimate how long a task might take based on its title and notes."""
    # Default duration is 30 minutes
    duration = timedelta(minutes=30)
    
    # Keywords that might indicate longer tasks
    long_task_keywords = ['meeting', 'workshop', 'study', 'research', 'write', 'develop', 'create']
    short_task_keywords = ['call', 'check', 'review', 'reply', 'email', 'quick', 'brief']
    
    title_lower = task.title.lower()
    notes_lower = task.notes.lower()
    
    # Adjust duration based on keywords
    for keyword in long_task_keywords:
        if keyword in title_lower or keyword in notes_lower:
            duration = timedelta(hours=1)
            break
    
    for keyword in short_task_keywords:
        if keyword in title_lower or keyword in notes_lower:
            duration = timedelta(minutes=15)
            break
    
    # Adjust for priority
    if task.priority > 5:  # High priority tasks might need more time
        duration *= 1.5
    
    return duration

def schedule_tasks(tasks: List[Task], date: datetime.datetime) -> List[Dict]:
    """Schedule tasks intelligently based on available slots and task properties."""
    # Get existing calendar events
    events = get_calendar_events(
        date.replace(hour=0, minute=0, second=0),
        date.replace(hour=23, minute=59, second=59)
    )
    
    # Estimate duration for each task
    for task in tasks:
        task.estimated_duration = estimate_task_duration(task)
    
    # Sort tasks by priority and due date
    tasks.sort(key=lambda x: (-x.priority, x.due or "9999-12-31"))
    
    # Find available time slots
    available_slots = find_available_slots(events, date, timedelta(minutes=15))
    
    scheduled_events = []
    
    for task in tasks:
        # Find suitable slot for this task
        for slot in available_slots:
            if slot.duration >= task.estimated_duration:
                # Schedule the task
                event_data = {
                    "title": task.title,
                    "start_time": slot.start,
                    "end_time": slot.start + task.estimated_duration
                }
                
                # Create the calendar event
                result = create_calendar_event(
                    task.title,
                    event_data["start_time"],
                    event_data["end_time"]
                )
                
                if result and result.get('status') == 'success':
                    print(f"Successfully scheduled: {task.title}")
                    print(f"Time: {event_data['start_time']} - {event_data['end_time']}")
                    print(f"Event link: {result.get('event_link')}")
                    scheduled_events.append(event_data)
                    
                    # Update available slots
                    slot.start = event_data["end_time"]
                    slot.duration = slot.end - slot.start
                    if slot.duration.total_seconds() <= 0:
                        available_slots.remove(slot)
                    break
        else:
            print(f"Could not find suitable time slot for: {task.title}")
    
    return scheduled_events

def create_calendar_event(title: str, start_time: datetime.datetime, end_time: datetime.datetime = None):
    """Create a calendar event using our existing API."""
    if end_time is None:
        end_time = start_time
    
    url = "http://localhost:8000/reminder"
    data = {
        "title": title,
        "due_date": start_time.isoformat(),
        "end_date": end_time.isoformat()
    }
    
    try:
        response = requests.post(url, json=data)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"Error creating calendar event: {str(e)}")
        return None

def main():
    print("Fetching reminders from ToDo list...")
    tasks = get_reminders_from_todo()
    
    if not tasks:
        print("No incomplete reminders found in ToDo list.")
        return
    
    print(f"Found {len(tasks)} tasks to process.")
    
    # Get tomorrow's date
    brisbane_tz = pytz.timezone('Australia/Brisbane')
    tomorrow = datetime.datetime.now(brisbane_tz) + datetime.timedelta(days=1)
    
    # Schedule tasks
    scheduled_events = schedule_tasks(tasks, tomorrow)
    
    print("\nScheduling Summary:")
    print(f"Successfully scheduled {len(scheduled_events)} out of {len(tasks)} tasks.")
    
    # Handle unscheduled tasks
    unscheduled = len(tasks) - len(scheduled_events)
    if unscheduled > 0:
        print(f"\nWarning: {unscheduled} tasks could not be scheduled.")
        print("These tasks will be carried forward to the next available day.")

if __name__ == "__main__":
    main() 