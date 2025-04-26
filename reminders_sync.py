import subprocess
import json
import datetime
import pytz
import requests

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
            print("Raw AppleScript output:", result.stdout)  # Debug output
            try:
                reminders = json.loads(result.stdout)
                return reminders
            except json.JSONDecodeError as e:
                print(f"Error parsing JSON: {str(e)}")
                return []
        else:
            print(f"Error getting reminders: {result.stderr}")
            return []
    except Exception as e:
        print(f"Error accessing Reminders: {str(e)}")
        return []

def create_calendar_event(title, start_time):
    """Create a calendar event using our existing API."""
    url = "http://localhost:8000/reminder"
    data = {
        "title": title,
        "due_date": start_time.isoformat()
    }
    
    try:
        response = requests.post(url, json=data)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"Error creating calendar event: {str(e)}")
        return None

def suggest_time_for_task(task_title, task_notes, existing_events):
    """Simple logic to suggest a time for a task based on its title and notes."""
    # Start with tomorrow at 9 AM Brisbane time
    brisbane_tz = pytz.timezone('Australia/Brisbane')
    tomorrow = datetime.datetime.now(brisbane_tz) + datetime.timedelta(days=1)
    suggested_time = tomorrow.replace(hour=9, minute=0, second=0, microsecond=0)
    
    # For now, just space tasks 1 hour apart starting at 9 AM
    return suggested_time + datetime.timedelta(hours=len(existing_events))

def main():
    print("Fetching reminders from ToDo list...")
    reminders = get_reminders_from_todo()
    
    if not reminders:
        print("No incomplete reminders found in ToDo list.")
        return
    
    print(f"Found {len(reminders)} reminders to process.")
    scheduled_events = []
    
    for reminder in reminders:
        title = reminder['title']
        notes = reminder.get('notes', '')
        
        # Suggest a time for this task
        suggested_time = suggest_time_for_task(title, notes, scheduled_events)
        
        print(f"\nProcessing: {title}")
        print(f"Suggested time: {suggested_time}")
        
        # Create the calendar event
        result = create_calendar_event(title, suggested_time)
        if result and result.get('status') == 'success':
            print(f"Successfully scheduled: {title}")
            print(f"Event link: {result.get('event_link')}")
            scheduled_events.append({
                'title': title,
                'time': suggested_time,
                'event_id': result.get('event_id')
            })
        else:
            print(f"Failed to schedule: {title}")

if __name__ == "__main__":
    main() 