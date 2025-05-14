# Imports
import datetime
import time

import requests
import pandas as pd
import plotly.express as px
from datetime import datetime, timezone
from clickup_client import ClickUpClient
import clickup_client
import streamlit as st

# streamlit page header
st.title("ClickUp Time Tracking by Tag")

# ----------------------- Get ClickUp API Token & Date Range on sidebar -----------------------
st.sidebar.header("Configuration")

user_token = st.sidebar.text_input("ClickUp API Token")
team = 'x'
client = 'x'

if user_token:
    client = ClickUpClient(api_token=user_token)
    # Get 'MMS' team id (only team)
    team = client.get_team()
else:
    st.error("Invalid ClickUp API Token")


# ------------------------- Get ClickUp Team attributes -------------------------
team_id = team['id']
team_name = team['name']
team_members = team['members']

st.write(f"Found team: {team_name} :)")

# Extract assignee user IDs from the team object
assignee_ids = [str(member['user']['id']) for member in team_members if member.get('user') and member['user'].get('id')]

# Join them into a comma-separated string
assignees = ",".join(assignee_ids)

# ------------------------------- Get Date Range ----------------------------------
# User input start date
start_date = st.sidebar.date_input("Start Date", datetime.today())
end_date = st.sidebar.date_input("End Date", datetime.today())
# Convert to datetime.datetime
#start_date = datetime.combine(start_date, datetime.min.time())
#end_date = datetime.combine(end_date, datetime.min.time())

# Convert to UTC timestamps in milliseconds
START_DATE = int(datetime.combine(start_date, datetime.min.time()).replace(tzinfo=timezone.utc).timestamp() * 1000)
END_DATE = int(datetime.combine(end_date, datetime.max.time()).replace(tzinfo=timezone.utc).timestamp() * 1000)

# ------------------------- Get ClickUp Data for Time Tracking ----------------------------------
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

# -------------------------- Specify & Search by Tags ----------------------------------------
#tag_input = input("Enter tags to filter by (separated by commas): ")
tag_input = st.text_input("Tags (comma-separated)")
search_tags = [tag.strip() for tag in tag_input.split(",") if tag.strip()]

# ----------------------- Get Time Tracking Analysis by Tags ----------------------------------------
# Filter entries with specified tags
acid_df = df[df["tags"].apply(
    lambda tags: any(tag["name"] in search_tags for tag in tags) if isinstance(tags, list) else False
)].copy()

# Explode for tag-level analysis
acid_exploded = acid_df.explode("TagName")
acid_exploded = acid_exploded[acid_exploded["TagName"].isin(search_tags)]

# Group by tag and billable status
tag_summary = acid_exploded.groupby(["TagName", "Billable"])["Duration (hours)"].sum().unstack(fill_value=0)
tag_summary["Total Hours"] = tag_summary.sum(axis=1)
tag_summary["% Billable"] = (tag_summary["Billable"] / tag_summary["Total Hours"]) * 100
tag_summary = tag_summary.round(2)

# Deduplicated total row
dedup_total = acid_df.drop_duplicates(subset="id").copy()
total_row = {
    "Billable": dedup_total[dedup_total["Billable"] == "Billable"]["Duration (hours)"].sum(),
    "Non-Billable": dedup_total[dedup_total["Billable"] == "Non-Billable"]["Duration (hours)"].sum()
}
total_row["Total Hours"] = total_row["Billable"] + total_row["Non-Billable"]
total_row["% Billable"] = (total_row["Billable"] / total_row["Total Hours"]) * 100 if total_row["Total Hours"] > 0 else 0

tag_summary.loc["Total"] = pd.Series(total_row).round(2)
st.write(tag_summary)