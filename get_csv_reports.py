"""
Notebook/script to retrieve data from portal for an
organization and generate reports. 
This retrieve personal information.  
It also includes submissions and comments that are hidden or no verified.
This full set of data should only be provided to the
customer through secure channels and with appropriate caveats.

"""

# %%
# from os import environ
from datetime import datetime, timezone
from typing import Any, Dict, Tuple
import pandas as pd
from dotenv import load_dotenv
import sys
import os
import requests
import json

# %%
def fetch_json(url: str, API_KEY: str) -> Dict:
    """
  Retrieve json from a url, passing an AWS API_KEY
  """
    headers = {"X-API-Key": API_KEY}
    r = requests.get(url, headers=headers)
    if r.status_code != 200:
        raise Exception(f"Error retrieving data\n {r.status_code} {r.text}")
    json_struct = json.loads(r.text)
    return json_struct


# %%


def get_portal_data_json(environment: str, organization: str) -> Dict:
    """
  Call portal API api that returns the submission, comments and their tags
  Convert the result to Dataframes
  """
    if f"{environment}_API_KEY" not in os.environ:
        raise Exception(
            f"Please define {environment}_API_KEY environment variable.  Easiest to use a .env file"
        )
    API_KEY = os.getenv(f"{environment}_API_KEY")
    ENDPOINTS = {
        "qa": f"https://ik3ewh40tg.execute-api.us-east-2.amazonaws.com/qa/submissions/star/{organization}",
        "prod": f"https://k61e3cz2ni.execute-api.us-east-2.amazonaws.com/prod/submissions/star/{organization}",
        "main": f"https://o1siz7rw0c.execute-api.us-east-2.amazonaws.com/prod/submissions/star/michigan",
    }
    endpoint = ENDPOINTS[environment]
    # Use paging API to get a bunch of records at a time until
    # we get an empty set of records.
    limit = 1000
    offset = 0
    done = False
    all_records = {"submissions": [], "comments": [], "tags": [], "commenttags": []}
    page = 1
    while not done:
        url = f"{endpoint}?offset={offset}&limit={limit}"
        json = fetch_json(url, API_KEY)
        message = json["message"]
        print(
            f"page {page} submissions {len(message['submissions'])} comments {len(message['comments'])}"
        )
        all_records["submissions"].extend(message["submissions"])
        all_records["comments"].extend(message["comments"])
        all_records["tags"].extend(message["tags"])
        all_records["commenttags"].extend(message["commenttags"])

        if (
            len(message["submissions"]) == 0
            and len(message["comments"]) == 0
            and len(message["tags"]) == 0
            and len(message["commenttags"]) == 0
        ):
            done = True
        else:
            offset = offset + limit
            page = page+1
    return all_records


# %%
def get_portal_data_dataframes(
    environment: str, organization: str
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
  Get data from portal API and convert to Panda Dataframes
  """

    json = get_portal_data_json(environment, organization)
    if organization == "michigan":
        submission_cols = [
            "id",
            "title",
            "type",
            "text",
            "link",
            "salutation",
            "first",
            "last",
            "email",
            "city",
            "state",
            "zip",
            "datetime",
            "verified",
            "key",
            "sourceip",
            "useragent",
            "districttype",
            "profanity",
            "token",
            "emailverified",
        ]
    else:
        submission_cols = [
            "id",
            "title",
            "type",
            "text",
            "link",
            "salutation",
            "first",
            "last",
            "email",
            "city",
            "state",
            "zip",
            "datetime",
            "hidden",
            "emailverified",
            "hasprofanity",
            "districttype",
            "contactable",
            "phone",
            "coalition",
            "language",
            "draft",
        ]

    if organization == "michigan":
        comment_cols = [
            "id",
            "submission",
            "text",
            "salutation",
            "first",
            "last",
            "email",
            "city",
            "state",
            "zip",
            "datetime",
            "emailverified",
            "profanity",
            "draft",
        ]
    else:
        comment_cols = [
            "id",
            "submission",
            "text",
            "salutation",
            "first",
            "last",
            "email",
            "city",
            "state",
            "zip",
            "datetime",
            "emailverified",
            "hidden",
            "hasprofanity",
            "contactable",
            "phone",
            "coalition",
            "language",
            "draft",
        ]

    if len(json["submissions"]) == 0:
        submissions_df = pd.DataFrame(columns=submission_cols)
    else:
        submissions_df = pd.DataFrame(json["submissions"])[submission_cols]

    if len(json["comments"]) == 0:
        comments_df = pd.DataFrame(columns=comment_cols)
    else:
        comments_df = pd.DataFrame(json["comments"])[comment_cols]

    # The Michigan DB lacks a column called 'hidden'
    # For consistency, add it was a false of False
    if "hidden" not in submissions_df.columns:
      submissions_df["hidden"] = False
    if "hidden" not in comments_df.columns:
      comments_df["hidden"] = False

    # The Michigan DB calls the column called 'profanity' instead of 'hasprofanity'
    if "profanity" in submissions_df.columns:
      submissions_df = submissions_df.rename(columns={"profanity": "hasprofanity"})
    if "profanity" in comments_df.columns:
      comments_df = comments_df.rename(columns={"profanity": "hasprofanity"})
      
    return submissions_df, comments_df


def get_portal_data_and_generate_csvs(environment: str, organization: str):
    """
  Get data from portal API and save as CSVs to local disk 
  """
    submissions_df, comments_df = get_portal_data_dataframes(environment, organization)

    ## Informational logging of unverified/hidden entries
    df = submissions_df[
                (submissions_df["hidden"] == True)
                | (submissions_df["emailverified"] == False) & ~submissions_df["type"].isin(["plan", "coi"])
            ]
    print(f"Hidden or unverified submissions {len(df.index)}")
    print(df)
            
    df = comments_df[(comments_df["hidden"] == True) | (comments_df["emailverified"] == False)]
    print(f"Hidden or unverified comments {len(df.index)}")
    print(df)

    ### Write to disk
    datestring = datetime.now(tz=timezone.utc).strftime("%Y-%m-%dT%H:%M")

    file = (
        f"reports/{organization}_{environment}_CumulativeSubmissions_{datestring}.csv"
    )
    submissions_df.sort_values(by="id").to_csv(file,index=False)
    print(f"Wrote {len(submissions_df.index)} to {file}")

    file = f"reports/{organization}_{environment}_CumulativeComments_{datestring}.csv"
    comments_df.sort_values(by="id").to_csv(file, index=False)
    print(f"Wrote {len(comments_df.index)} to {file}")


# %%
def usage():
    print(f"Usage: python get_csv_reports.py ENV ORGANIZATION")
    print(f"Ex:    python get_csv_reports.py qa ohio")
    print(f"Ex:    python get_csv_reports.py prod ohio")
    print(f"Ex:    python get_csv_reports.py main michigan")


# %%
if __name__ == "__main__":
    load_dotenv()
    if "ipykernel" in sys.argv[0]:
        environment = "qa"
        organization = "minneapolis"
    else:
        # Support running as a plain python script
        if len(sys.argv) >= 2:
            environment = sys.argv[1]
            organization = sys.argv[2]

    # At this point, environment and organization should have been set
    if environment and organization:
        get_portal_data_and_generate_csvs(environment, organization)

    else:
        usage()

