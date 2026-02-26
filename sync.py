#!/usr/bin/env python3
"""
Canvas to Notion Assignment Sync
Syncs assignments from Canvas LMS to a Notion database.
"""

import os
import time
import requests
from datetime import datetime
from zoneinfo import ZoneInfo
from dotenv import load_dotenv

load_dotenv()

# Config from .env
NOTION_KEY = os.getenv("NOTION_KEY")
CANVAS_KEY = os.getenv("CANVAS_KEY")
NOTION_DB = os.getenv("NOTION_DB")
CANVAS_URL = os.getenv("CANVAS_URL")  # e.g., https://canvas.pitt.edu

# Canvas API base URL
CANVAS_BASE = f"{CANVAS_URL}/api/v1"

# Headers
notion_headers = {
    "Authorization": f"Bearer {NOTION_KEY}",
    "Content-Type": "application/json",
    "Notion-Version": "2022-06-28"
}

canvas_headers = {
    "Authorization": f"Bearer {CANVAS_KEY}"
}


def get_canvas_courses():
    """Fetch only favorited courses from Canvas."""
    url = f"{CANVAS_BASE}/users/self/favorites/courses"
    params = {
        "per_page": 50
    }
    
    response = requests.get(url, headers=canvas_headers, params=params)
    response.raise_for_status()
    
    return response.json()


def get_canvas_assignments(course_id):
    """Fetch assignments for a specific course."""
    url = f"{CANVAS_BASE}/courses/{course_id}/assignments"
    params = {
        "per_page": 100,
        "order_by": "due_at"
    }
    
    response = requests.get(url, headers=canvas_headers, params=params)
    response.raise_for_status()
    
    return response.json()


def get_existing_notion_assignments():
    """Get all assignments already in Notion with their page IDs, completion status, and due dates."""
    url = f"https://api.notion.com/v1/databases/{NOTION_DB}/query"

    response = requests.post(url, headers=notion_headers, json={})
    response.raise_for_status()

    existing = {}
    for page in response.json().get("results", []):
        props = page.get("properties", {})
        title_prop = props.get("Assignment", {}).get("title", [])
        course_prop = props.get("Course", {}).get("select") or {}
        due_date_prop = props.get("Due Date", {}).get("date") or {}
        if title_prop:
            title = title_prop[0].get("plain_text", "")
            course = course_prop.get("name", "")
            due_date = due_date_prop.get("start", "")
            completed = props.get("Completed", {}).get("checkbox", False)
            existing[(title, course)] = {
                "page_id": page.get("id"),
                "completed": completed,
                "due_date": due_date,
            }

    return existing


def get_canvas_submission(course_id, assignment_id):
    """Check if an assignment has been submitted."""
    url = f"{CANVAS_BASE}/courses/{course_id}/assignments/{assignment_id}/submissions/self"
    
    response = requests.get(url, headers=canvas_headers)
    response.raise_for_status()
    
    submission = response.json()
    # Check if there's a submission (workflow_state will be 'submitted' or 'graded')
    workflow_state = submission.get("workflow_state", "")
    return workflow_state in ["submitted", "graded", "pending_review"]


def _canvas_due_to_est(due_at):
    """Convert a Canvas UTC due date string to an EST-formatted string for comparison."""
    if not due_at:
        return None
    try:
        dt_utc = datetime.fromisoformat(due_at.replace("Z", "+00:00"))
        return dt_utc.astimezone(ZoneInfo("America/New_York")).strftime("%Y-%m-%dT%H:%M:%S")
    except (ValueError, AttributeError):
        return None


def mark_notion_assignment_completed(page_id):
    """Mark an assignment as completed in Notion."""
    url = f"https://api.notion.com/v1/pages/{page_id}"

    payload = {
        "properties": {
            "Completed": {"checkbox": True}
        }
    }

    response = requests.patch(url, headers=notion_headers, json=payload)
    response.raise_for_status()

    return response.json()


def delete_notion_page(page_id):
    """Archive (soft-delete) a Notion page."""
    url = f"https://api.notion.com/v1/pages/{page_id}"
    response = requests.patch(url, headers=notion_headers, json={"archived": True})
    response.raise_for_status()
    return response.json()


def create_notion_assignment(assignment_name, course_name, due_date, is_submitted=False):
    """Create a new assignment in Notion."""
    url = "https://api.notion.com/v1/pages"
    
    # Build properties
    properties = {
        "Assignment": {
            "title": [{"text": {"content": assignment_name}}]
        },
        "Course": {
            "select": {"name": course_name}
        },
        "Completed": {
            "checkbox": is_submitted
        }
    }
    
    # Add due date if it exists
    if due_date:
        # Parse Canvas date (UTC) and convert to EST
        try:
            dt_utc = datetime.fromisoformat(due_date.replace("Z", "+00:00"))
            dt_est = dt_utc.astimezone(ZoneInfo("America/New_York"))
            properties["Due Date"] = {
                "date": {
                    "start": dt_est.strftime("%Y-%m-%dT%H:%M:%S"),
                    "time_zone": "America/New_York"
                }
            }
        except (ValueError, AttributeError):
            pass  # Skip date if parsing fails
    
    payload = {
        "parent": {"database_id": NOTION_DB},
        "properties": properties
    }
    
    response = requests.post(url, headers=notion_headers, json=payload)
    response.raise_for_status()
    
    return response.json()


def normalize_course_name(canvas_name):
    """
    Map Canvas course names to your Notion Course options.
    UPDATE THESE MAPPINGS to match your courses.
    """
    # Lowercase for easier matching
    name_lower = canvas_name.lower()
    
    mappings = {
        "1652": "CS 1652 DATA COM",
        "data comm": "CS 1652 DATA COM",
        "0355": "ENGFLM 0355 VIS LIT",
        "visual": "ENGFLM 0355 VIS LIT",
        "1503": "CS 1503 MCH LEARNING",
        "machine learning": "CS 1503 MCH LEARNING",
        "1632": "CS 1632 SQA",
        "sqa": "CS 1632 SQA",
        "software quality": "CS 1632 SQA",
    }
    
    for keyword, notion_name in mappings.items():
        if keyword in name_lower:
            return notion_name
    
    # Return original if no mapping found (will create new select option)
    return canvas_name


def sync():
    """Main sync function."""
    print("🔄 Starting Canvas → Notion sync...\n")
    
    # Get existing assignments to avoid duplicates
    print("📋 Fetching existing Notion assignments...")
    existing = get_existing_notion_assignments()
    print(f"   Found {len(existing)} existing assignments\n")
    
    # Get Canvas courses
    print("🎓 Fetching favorited Canvas courses...")
    courses = get_canvas_courses()
    print(f"   Found {len(courses)} favorited courses\n")
    
    added = 0
    skipped = 0
    marked_complete = 0
    
    for course in courses:
        course_name = course.get("name", "Unknown Course")
        course_id = course.get("id")
        notion_course = normalize_course_name(course_name)
        
        print(f"📚 {course_name}")
        print(f"   → Notion: {notion_course}")
        
        # Get assignments for this course
        assignments = get_canvas_assignments(course_id)
        
        for assignment in assignments:
            name = assignment.get("name", "Untitled Assignment")
            due_at = assignment.get("due_at")
            assignment_id = assignment.get("id")
            
            # Check if submitted in Canvas
            try:
                is_submitted = get_canvas_submission(course_id, assignment_id)
            except requests.exceptions.HTTPError:
                is_submitted = False
            
            # Check if already exists in Notion (keyed by title + course)
            key = (name, notion_course)
            canvas_due_est = _canvas_due_to_est(due_at)

            if key in existing:
                entry = existing[key]
                notion_due = entry["due_date"]
                # Due date changed — archive old entry and create a fresh one
                if canvas_due_est and notion_due and canvas_due_est != notion_due:
                    try:
                        delete_notion_page(entry["page_id"])
                        create_notion_assignment(name, notion_course, due_at, is_submitted)
                        print(f"   🔄 Updated (new due date): {name}")
                        added += 1
                        existing[key] = {"page_id": None, "completed": is_submitted, "due_date": canvas_due_est}
                    except requests.exceptions.HTTPError as e:
                        print(f"   ❌ Failed to update: {name} - {e}")
                elif is_submitted and not entry["completed"]:
                    try:
                        mark_notion_assignment_completed(entry["page_id"])
                        print(f"   ✓ Marked complete: {name}")
                        marked_complete += 1
                    except requests.exceptions.HTTPError as e:
                        print(f"   ❌ Failed to mark complete: {name} - {e}")
                else:
                    skipped += 1
                continue

            # Create in Notion
            try:
                create_notion_assignment(name, notion_course, due_at, is_submitted)
                status = "✅ Added (completed)" if is_submitted else "✅ Added"
                print(f"   {status}: {name}")
                added += 1
                existing[key] = {"page_id": None, "completed": is_submitted, "due_date": canvas_due_est}
            except requests.exceptions.HTTPError as e:
                print(f"   ❌ Failed: {name} - {e}")
        
        print()
    
    print("=" * 50)
    print(f"✨ Sync complete! Added {added}, marked complete {marked_complete}, skipped {skipped}.")


if __name__ == "__main__":
    # Validate env vars
    if not all([NOTION_KEY, CANVAS_KEY, NOTION_DB, CANVAS_URL]):
        print("❌ Missing environment variables!")
        print("   Make sure .env contains: NOTION_KEY, CANVAS_KEY, NOTION_DB, CANVAS_URL")
        time.sleep(2)
        exit(1)
    
    sync()
    time.sleep(2)
