import logging
import requests
import pandas as pd
from datetime import datetime

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

