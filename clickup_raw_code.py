import os
import logging
import datetime
import time

import requests
import pandas as pd
import plotly.express as px
from google.colab import userdata
from datetime import datetime, timezone

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    force=True
)

class ClickUpClient:
    """A read-only client for the ClickUp API."""

    def __init__(self, api_token: str):
        """Initialize the ClickUp client.
        Args:
            api_token (str): ClickUp API token. Must be provided explicitly.
        """
        if not api_token:
            raise ValueError("Invalid or missing ClickUp API token")

        self.api_token = api_token
        self.base_url = 'https://api.clickup.com/api/v2/'
        self.headers = {
            'Authorization': self.api_token,
            'Content-Type': 'application/json'
        }

    # um, should actually not be a class function, but we'll fix that later
    def fetch_clickup_data(self, start_date, end_date, team_id, assignees):
        """Fetch data from the ClickUp API for a given date range, team, and assignees."""

        url = f"https://api.clickup.com/api/v2/team/{team_id}/time_entries?start_date={start_date}&end_date={end_date}&assignee={assignees}"
        headers = {"Authorization": self.api_token}
        response = requests.get(url, headers=headers)

        if response.status_code == 200:
            return response.json().get("data", [])
        else:
            print(f"API Error: {response.status_code}")
            return []

    def get_space_tags(self, space_id):
        """
        Get all tags associated with a given ClickUp space.
        Args:
            space_id (str or int): The ID of the space to retrieve tags from.
        Returns:
            list: A list of tag dictionaries, or an empty list if none found.
        """
        url = f"{self.base_url}/space/{space_id}/tag"
        headers = {
            "Authorization": self.api_token
        }

        response = requests.get(url, headers=headers)

        if response.status_code == 200:
            return response.json().get("tags", [])
        else:
            print(f"Failed to fetch tags. Status code: {response.status_code}")
            return []

    def _get(self, endpoint: str, params: dict | None = None) -> dict:
        """Make a GET request to the ClickUp API.

        Args:
            endpoint (str): API endpoint to call
            params (dict, optional): Query parameters for the request

        Returns:
            dict: JSON response from the API
        """
        response = requests.get(
            f"{self.base_url}{endpoint}",
            headers=self.headers,
            params=params
        )
        response.raise_for_status()
        return response.json()

    def get_teams(self) -> list[dict]:
        """Get all teams accessible to the authenticated user."""
        response = self._get('team')
        return response['teams']

    def get_team(self) -> dict:
        """Get single team (assumes only one team exists)."""
        teams = self.get_teams()
        if len(teams) == 1:
            logging.info(f'Found team: {teams[0]["name"]}')
            return teams[0]
        raise ValueError(f'Expected exactly one team, got {len(teams)}')

    def get_spaces(self, team_id: str) -> list[dict]:
        response = self._get(f'team/{team_id}/space')
        logging.info(f"spaces: {[(ix, space['name']) for ix, space in enumerate(response['spaces'])]}")
        return response['spaces']

    def get_folders(self, space_id: str, archived: bool = False) -> list[dict]:
        response = self._get(f'space/{space_id}/folder', params={'archived': archived})
        logging.info(f"folders: {[(ix, folder['name']) for ix, folder in enumerate(response['folders'])]}")
        return response['folders']

    def get_lists(self, folder_id: str, archived: bool = False) -> list[dict]:
        response = self._get(f'folder/{folder_id}/list', params={'archived': archived})
        logging.info(f"lists: {[(ix, list['name']) for ix, list in enumerate(response['lists'])]}")
        return response['lists']

    def get_folderless_lists(self, space_id: str, archived: bool = False) -> list[dict]:
        response = self._get(f'space/{space_id}/list', params={'archived': archived})
        return response['lists']

    def get_tasks(self, list_id: str, **params) -> list[dict]:
        response = self._get(f'list/{list_id}/task', params=params)
        logging.info(f"Tasks found: {len(response['tasks'])}")
        return response['tasks']

    def get_all_tasks(self, list_id: str, **params) -> list[dict]:
        """Get all tasks from a list, handling pagination."""
        all_tasks = []
        page = 0

        while True:
            params['page'] = page
            table_view = self.get_table_view(list_id) # returns DoNotAlter table
            tasks = self.get_view_tasks(table_view['id'], params)
            all_tasks.extend(tasks)

            logging.info(f"Page: {page} (Tasks: {len(tasks)})")

            if len(tasks) < 30:
                break  # Last page reached
            page += 1

        logging.info(f"Total tasks retrieved from list {list_id}: {len(all_tasks)}")
        return all_tasks

    def get_task(self, task_id: str) -> dict:
        return self._get(f'task/{task_id}')

    def get_task_time_tracking(self, task_id: str) -> list[dict]:
        """Get time tracking entries for a task."""
        response = self._get(f'task/{task_id}/time')
        return response['data']

    def get_team_time_tracking(self, team_id: str, **params) -> list[dict]:
        """Get time tracking entries for an entire team."""
        response = self._get(f'team/{team_id}/time_entries', params=params)
        return response['data']

    def get_required_views(self, list_id):
        """
        Retrieve specific ClickUp view.

        :param view_id: The ID of the ClickUp view.
        :return: A list of tasks in the specified view.
        """
        url = f'{self.base_url}list/{list_id}/view'
        response = requests.get(url, headers=self.headers)
        if response.status_code == 200:
            return response.json().get('required_views', [])
        else:
            response.raise_for_status()

    def get_views(self, view_id):
        """
        Retrieve specific ClickUp view.

        :param view_id: The ID of the ClickUp view.
        :return: A list of tasks in the specified view.
        """
        url = f'{self.base_url}list/{list_id}/view'
        response = requests.get(url, headers=self.headers)
        if response.status_code == 200:
            return response.json().get('views', [])
        else:
            response.raise_for_status()

    def get_list_view(self, list_id):
        """
        Retrieve specific ClickUp view.

        :param view_id: The ID of the ClickUp view.
        :return: A list of tasks in the specified view.
        """
        list_view = client.get_required_views(list_id).get('list', {})

        return list_view

    def get_table_view(self, list_id):
        """
        Retrieve specific table from a ClickUp view.

        :param list_id: The ID of the ClickUp list.
        :return: The 'DoNotAlter' table view dictionary.
        """
        views = self.get_views(list_id)  # Assuming get_views is defined and returns the list of views
        for view in views:
            if view['name'] == 'DoNotAlter':  # Find the view by name
                return view  # Return the view dictionary
        return None  # Return None if 'DoNotAlter' view is not found

    def get_view_tasks(self, view_id, params: dict):
        """
        Retrieve task and page views available for a List from a specific
        ClickUp view.
        Views and required views are separate responses.

        :param view_id: The ID of the ClickUp view.
        :return: A list of tasks in the specified view.
        """
        url = f'{self.base_url}/view/{view_id}/task'
        response = requests.get(url, headers=self.headers, params=params)
        if response.status_code == 200:
            return response.json().get('tasks', [])
        else:
            response.raise_for_status()

# Define methods to extract custom fields
def extract_cf_info(cf):
    """Extracts name, type, type_config, value, and value_richtext from a custom field dictionary."""
    return {
        "name": cf.get("name"),
        "type": cf.get("type"),
        "type_config": cf.get("type_config"),
        "value": cf.get("value"),
        "value_richtext": cf.get("value_richtext"),
    }

def extract_all_cf_info(row):
    """Extracts all custom field information for a row."""
    cf_data = {}
    for cf in row['custom_fields']:
      extracted_info = extract_cf_info(cf)
      cf_data[extracted_info['name']] = extracted_info['value']  # Store using CF name as key

    return cf_data

# Define methods for time tracking processing
def format_timestamp(unix_ms):
    """Convert Unix timestamp in milliseconds to 'YYYY-MM-DD HH:MM'."""
    return datetime.fromtimestamp(int(unix_ms) / 1000).strftime('%Y-%m-%d %H:%M')

def extract_tracked_time(client, tasks):
    records = []

    for task in tasks:
        task_id = task['id']
        task_name = task['name']

        try:
            time_entries = client.get_task_time_tracking(task_id)

            for entry in time_entries:
                assignee = entry.get('user', {}).get('username', 'Unknown')
                for interval in entry.get('intervals', []):
                    start = interval.get('start')
                    end = interval.get('end')
                    duration_ms = int(interval.get('time', 0))
                    tags = ', '.join(tag['name'] for tag in interval.get('tags') or [])

                    records.append({
                        'Task ID': task_id,
                        'Data Team Assignee': assignee,
                        'Time Tracked (Duration) [hours]': round(duration_ms / 3600000, 2),
                        'Time Tracked (Start)': format_timestamp(start),
                        'Time Tracked (End)': format_timestamp(end),
                        'Tag Names': tags
                    })

        except requests.exceptions.HTTPError as err:
            if err.response.status_code == 429:
                  # Wait for 30 seconds before retrying - modify if needed
                  print(f"Rate limit hit! Waiting for 60 seconds before retrying task {task_id}...")
                  time.sleep(60)
                  # Retry fetching the time entries
                  time_entries = client.get_task_time_tracking(task_id)

            else:
                  # Raise other exceptions as usual
                  print(f"Error processing task {task_id}: {e}")

    df_time_tracked = pd.DataFrame(records)
    return df_time_tracked

# Create client index to name map for table labelling
def create_client_map(tasks):
    """Creates a mapping from client ID to client name.

    :param: tasks: A list of tasks retrieved from the ClickUp API.
    :return: A dictionary mapping client ID to client name. """

    # Get custom fields from the first task
    task1 = tasks[0]
    custom_fields = task1.get('custom_fields', [])

    # Create an empty dictionary to store the mapping
    client_id_to_name = {}

    # Iterate over the custom fields and extract the mapping
    for field in custom_fields:
        if field.get('name') == 'Client':
            options = field.get('type_config', {}).get('options', [])
            for idx, option in enumerate(options):
                client_id_to_name[idx] = option.get('name')

    return client_id_to_name

# Create root cause index to name map for table labelling
def create_root_cause_map(tasks):
    """Creates a mapping from root cause ID to root cause name.

    :param: tasks: A list of tasks retrieved from the ClickUp API.
    :returns: A dictionary mapping root cause ID to root cause name. """

    # Get custom fields from the first task
    task1 = tasks[0]
    custom_fields = task1.get('custom_fields', [])

    # Create an empty dictionary to store the mapping
    rcause_id_to_name = {}

    # Iterate over the custom fields and extract the mapping
    for field in custom_fields:
        if field.get('name') == 'Root cause':
            options = field.get('type_config', {}).get('options', [])
            for idx, option in enumerate(options):
                rcause_id_to_name[idx] = option.get('name')

    return rcause_id_to_name


def get_user_date(prompt):
    while True:
        user_input = input(prompt)
        try:
            return datetime.strptime(user_input, "%Y-%m-%d")
        except ValueError:
            print("Invalid date format. Please use YYYY-MM-DD.")

# Instantiate ClickUp Client using provided ClickUp token (change accordingly)
# user_token = input("Enter ClickUp API Token: ")
user_token = userdata.get('CLICKUP_API_TOKEN')
client = ClickUpClient(api_token=user_token)

#client = ClickUpClient()

# Get 'MMS' team id (only team)
team = client.get_team()
team_id = team['id']
team_name = team['name']
team_members = team['members']

# Extract assignee user IDs from the team object
team_members = team['members']
assignee_ids = [str(member['user']['id']) for member in team_members if member.get('user') and member['user'].get('id')]

# Join them into a comma-separated string
assignees = ",".join(assignee_ids)

# Ask user for date range
#start_date = get_user_date("Enter the start date (YYYY-MM-DD): ")
#end_date = get_user_date("Enter the end date (YYYY-MM-DD): ")
# temporary use:
start_date = datetime(2025, 4, 1)
end_date = datetime(2025, 4, 30)

# Convert to UTC timestamps in milliseconds
START_DATE = int(datetime.combine(start_date, datetime.min.time()).replace(tzinfo=timezone.utc).timestamp() * 1000)
END_DATE = int(datetime.combine(end_date, datetime.max.time()).replace(tzinfo=timezone.utc).timestamp() * 1000)

data = client.fetch_clickup_data(START_DATE, END_DATE, team_id, assignees)

if data:
    df = pd.DataFrame(data)

    # Clean timestamps
    df["start"] = pd.to_numeric(df["start"], errors="coerce")
    df["end"] = pd.to_numeric(df["end"], errors="coerce")
    df["StartDate"] = pd.to_datetime(df["start"], unit="ms", utc=True)
    df["EndDate"] = pd.to_datetime(df["end"], unit="ms", utc=True)

    # Duration and Labels
    df["Duration (hours)"] = pd.to_numeric(df["duration"], errors="coerce") / (1000 * 60 * 60)
    df["Billable"] = df["billable"].apply(lambda x: "Billable" if x else "Non-Billable")
    df["UserName"] = df["user"].apply(lambda x: x["username"] if isinstance(x, dict) else None)
    df["TagName"] = df["tags"].apply(lambda tags: [tag["name"].lower() for tag in tags] if isinstance(tags, list) else [])

tag_input = input("Enter tags to filter by (separated by commas): ")
search_tags = [tag.strip() for tag in tag_input.split(",") if tag.strip()]

search_tags

# === Filter entries with Acid & Anode tags ===
acid_df = df[df["tags"].apply(
    lambda tags: any(tag["name"] in search_tags for tag in tags) if isinstance(tags, list) else False
)].copy()

# === Explode for tag-level analysis ===
acid_exploded = acid_df.explode("TagName")
acid_exploded = acid_exploded[acid_exploded["TagName"].isin(search_tags)]

# === Group by tag and billable status ===
tag_summary = acid_exploded.groupby(["TagName", "Billable"])["Duration (hours)"].sum().unstack(fill_value=0)
tag_summary["Total Hours"] = tag_summary.sum(axis=1)
tag_summary["% Billable"] = (tag_summary["Billable"] / tag_summary["Total Hours"]) * 100
tag_summary = tag_summary.round(2)

# === Deduplicated total row ===
dedup_total = acid_df.drop_duplicates(subset="id").copy()
total_row = {
    "Billable": dedup_total[dedup_total["Billable"] == "Billable"]["Duration (hours)"].sum(),
    "Non-Billable": dedup_total[dedup_total["Billable"] == "Non-Billable"]["Duration (hours)"].sum()
}
total_row["Total Hours"] = total_row["Billable"] + total_row["Non-Billable"]
total_row["% Billable"] = (total_row["Billable"] / total_row["Total Hours"]) * 100 if total_row["Total Hours"] > 0 else 0

tag_summary.loc["Total"] = pd.Series(total_row).round(2)
display(tag_summary)

