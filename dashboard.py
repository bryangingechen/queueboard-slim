#!/usr/bin/env python3

# This script accepts json files as command line arguments and displays the data in an HTML dashboard

import sys
import json
from datetime import datetime, timezone
from dateutil import relativedelta
from enum import Enum, auto, unique
from typing import List, NamedTuple

@unique
class PRList(Enum):
    '''The different kind of PR lists this dashboard creates'''
    # Note: the tables on the generated page are listed in the order of these variants.
    Queue = 0
    QueueNewContributor = auto()
    StaleReadyToMerge = auto()
    StaleDelegated = auto()
    StaleMaintainerMerge = auto()
    StaleNewContributor = auto()
    # "Ready" PRs without the CI or a t-something label.
    Unlabelled = auto()
    # "Ready" PRs whose title does not start with an abbreviation like 'feat' or 'style'
    BadTitle = auto()

# All input files this script expects. Needs to be kept in sync with dashboard.sh,
# but this script will complain if something unexpected happens.
EXPECTED_INPUT_FILES = {
    "queue.json" : PRList.Queue,
    "queue-new-contributor.json" : PRList.QueueNewContributor,
    "automerge.json" : PRList.StaleReadyToMerge,
    "ready-to-merge.json" : PRList.StaleReadyToMerge,
    "maintainer-merge.json" : PRList.StaleMaintainerMerge,
    "delegated.json" : PRList.StaleDelegated,
    "new-contributor.json" : PRList.StaleNewContributor,
}

def short_description(kind : PRList):
    '''Describe what the table 'kind' contains, for use in a "there are no such PRs" message.'''
    return {
        PRList.Queue : "PRs on the review queue",
        PRList.QueueNewContributor : "PRs by new mathlib contributors on the review queue",
        PRList.StaleMaintainerMerge : "stale PRs labelled maintainer merge",
        PRList.StaleDelegated : "stale delegated PRs",
        PRList.StaleReadyToMerge : "stale PRs labelled auto-merge-after-CI or ready-to-merge",
        PRList.StaleNewContributor : "stale PRs by new contributors",
        PRList.Unlabelled : "ready PRs without a 'CI' or 't-something' label",
        PRList.BadTitle : "ready PRs whose title does not start with an abbreviation like 'feat', 'style' or 'perf'",
    }[kind]

def long_description(kind : PRList):
    '''Explain what each PR list contains: full description, for the purposes of a sub-title
    to the full PR table.'''
    notupdated = "which have not been updated in the past"
    return {
        PRList.Queue : "All PRs which are ready for review: CI passes, no merge conflict and not blocked on other PRs",
        PRList.QueueNewContributor : "All PRs by new contributors which are ready for review",
        PRList.StaleDelegated : f"PRs labelled 'delegated' {notupdated} 24 hours",
        PRList.StaleReadyToMerge : f"PRs labelled 'auto-merge-after-CI' or 'ready-to-merge' {notupdated} 24 hours",
        PRList.StaleMaintainerMerge : f"PRs labelled 'maintainer-merge' but not 'ready-to-merge' {notupdated} 24 hours",
        PRList.StaleNewContributor : f"PR labelled 'new-contributor' {notupdated} 7 days",
        PRList.Unlabelled : "All PRs without draft status or 'WIP' label without a 'CI' or 't-something' label",
        PRList.BadTitle : "All PRs without draft status or 'WIP' label whose title does not start with an abbreviation like 'feat', 'style' or 'perf'",
    }[kind]

def getIdTitle(kind : PRList):
    '''Return a tuple (id, title) of the HTML anchor ID and a section name for the table
    describing this PR kind.'''
    return {
        PRList.Queue : ("queue", "Queue"),
        PRList.QueueNewContributor : ("queue-new-contributors", "New contributors' PRs on the queue"),
        PRList.StaleDelegated : ("stale-delegated", "Stale delegated"),
        PRList.StaleNewContributor : ("stale-new-contributor", "Stale new contributor"),
        PRList.StaleMaintainerMerge : ("stale-maintainer-merge", "Stale maintainer-merge"),
        PRList.StaleReadyToMerge : ("stale-ready-to-merge", "Stale ready-to-merge"),
        PRList.Unlabelled : ("unlabelled", "PRs without an area label"),
        PRList.BadTitle : ("bad-title", "PRs with non-conforming titles"),
    }[kind]

def main():
    # Check if the user has provided the correct number of arguments
    if len(sys.argv) < 3:
        print("Usage: python3 dashboard.py <pr-info.json> <all-ready-prs.json> <json_file1> <json_file2> ...")
        sys.exit(1)

    print_html5_header()

    # Iterate over the json files provided by the user
    dataFilesWithKind = []
    for i in range(3, len(sys.argv)):
        filename = sys.argv[i]
        if filename not in EXPECTED_INPUT_FILES:
            print(f"bad argument: file {filename} is not recognised; did you mean one of these?\n{', '.join(EXPECTED_INPUT_FILES.keys())}")
            sys.exit(1)
        with open(filename) as f:
            data = json.load(f)
            dataFilesWithKind.append((data, EXPECTED_INPUT_FILES[filename]))

    # Process all data files for the same PR list together.
    for kind in PRList._member_map_.values():
        # We generate their table later.
        if kind in [PRList.Unlabelled, PRList.BadTitle]:
            continue
        datae = [d for (d, k) in dataFilesWithKind if k == kind]
        print_dashboard(datae, kind)

    with open(sys.argv[2]) as f:
        all_ready_prs = json.load(f)
        print_bad_unlabelled_prs(all_ready_prs)

    print_html5_footer()

def print_html5_header():
    print("""
    <!DOCTYPE html>
    <html>
    <head>
    <title>Mathlib Review Dashboard</title>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/jquery/3.5.1/jquery.min.js"
			integrity="sha512-bLT0Qm9VnAYZDflyKcBaQ2gg0hSYNQrJ8RilYldYQ1FxQYoCLtUjuuRuZo+fjqhx/qtq/1itJ0C2ejDxltZVFg=="
			crossorigin="anonymous"></script>
    <link rel="stylesheet" type="text/css" href="https://cdn.datatables.net/1.10.22/css/jquery.dataTables.css">
    <script type="text/javascript" charset="utf8" src="https://cdn.datatables.net/1.10.22/js/jquery.dataTables.js"></script>
    <link rel='stylesheet' href='style.css'>
    <base target="_blank">
    </head>
    <body>
    <h1>Mathlib Review Dashboard</h1>""")
    # FUTURE: can this time be displayed in the local time zone of the user viewing this page?
    updated = datetime.now(timezone.utc).strftime("%B %d, %Y at %H:%M UTC")
    print(f"<small>This dashboard was last updated on: {updated}</small>")

def print_html5_footer():
    print("""
    <script>
    $(document).ready( function () {
        $('table').DataTable({
                pageLength: 10,
				"searching": false,
        });
    });
    </script>
    </body>
    </html>
    """)

# An HTML link to a mathlib PR from the PR number
def pr_link(number, url):
    return "<a href='{}'>#{}</a>".format(url, number)

# An HTML link to a GitHub user profile
def user_link(author):
    login = author["login"]
    url   = author["url"]
    return "<a href='{}'>{}</a>".format(url, login)

# An HTML link to a mathlib PR from the PR title
def title_link(title, url):
    return "<a href='{}'>{}</a>".format(url, title)


# The information we need about each PR label: name, colour and URL
class Label(NamedTuple):
    name : str
    '''This label's background colour, as a six-digit hexadecimal code'''
    color : str
    url : str


# An HTML link to a Github label in the mathlib repo
def label_link(label:Label):
    # Function to check if the colour of the label is light or dark
    # adapted from https://codepen.io/WebSeed/pen/pvgqEq
    def isLight(r, g, b):
        # Counting the perceptive luminance
        # human eye favors green color...
        a = 1 - (0.299 * r + 0.587 * g + 0.114 * b) / 255
        return (a < 0.5)

    bgcolor = label.color
    fgcolor = "000000" if isLight(int(bgcolor[:2], 16), int(bgcolor[2:4], 16), int(bgcolor[4:], 16)) else "FFFFFF"
    return f"<a href='{label.url}'><span class='label' style='color: #{fgcolor}; background: #{bgcolor}'>{label.name}</span></a>"


# Function to format the time of the last update
# Input is in the format: "2020-11-02T14:23:56Z"
# Output is in the format: "2020-11-02 14:23 (2 days ago)"
def time_info(updatedAt):
    updated = datetime.strptime(updatedAt, "%Y-%m-%dT%H:%M:%SZ")
    now = datetime.now()

    # Calculate the difference in time
    delta = relativedelta.relativedelta(now, updated)

    # Format the output
    s = updated.strftime("%Y-%m-%d %H:%M")
    if delta.years > 0:
        s += " ({} years ago)".format(delta.years)
    elif delta.months > 0:
        s += " ({} months ago)".format(delta.months)
    elif delta.days > 0:
        s += " ({} days ago)".format(delta.days)
    elif delta.hours > 0:
        s += " ({} hours ago)".format(delta.hours)
    elif delta.minutes > 0:
        s += " ({} minutes ago)".format(delta.minutes)
    else:
        s += " ({} seconds ago)".format(delta.seconds)

    return s


# Basic information about a PR: does not contain the diff size, which is contained in pr_info.json instead.
class BasicPRInformation(NamedTuple):
    number : int # PR number, non-negative
    author : str
    title : str
    url : str
    labels : List[Label]
    # Github's answer to "last updated at"
    updatedAt : str


# Print table entries about a sequence of PRs.
def _print_pr_entries(pr_infos, prs : List[BasicPRInformation]):
    for pr in prs:
        print("<tr>")
        print("<td>{}</td>".format(pr_link(pr.number, pr.url)))
        print("<td>{}</td>".format(user_link(pr.author)))
        print("<td>{}</td>".format(title_link(pr.title, pr.url)))
        print("<td>")
        for label in pr.labels:
            print(label_link(label))
        print("</td>")
        try:
            pr_info = pr_infos[str(pr.number)]
            print("<td>{}/{}</td>".format(pr_info["additions"], pr_info["deletions"]))
            print("<td>{}</td>".format(pr_info["changed_files"]))
            comments = pr_info["comments"] + pr_info["review_comments"]
            print("<td>{}</td>".format(comments))
        except KeyError:
            pr_info = {"additions": -1, "deletions": -1, "changed_files": -1, "comments": -1, "review_comments": -1}
            print("<td>{}/{}</td>".format(pr_info["additions"], pr_info["deletions"]))
            print("<td>{}</td>".format(pr_info["changed_files"]))
            comments = pr_info["comments"] + pr_info["review_comments"]
            print("<td>{}</td>".format(comments))
            print(f"PR #{pr.number} is wicked!", file=sys.stderr)

        print("<td>{}</td>".format(time_info(pr.updatedAt)))
        print("</tr>")


# Print a dashboard of a given list of PRs.
def _print_dashboard(pr_infos, prs : List[BasicPRInformation], kind: PRList):
    # Title of each list, and the corresponding HTML anchor.
    (id, title) = getIdTitle(kind)
    print("<h1 id=\"{}\">{}</h1>".format(id, title))
    # If there are no PRs, skip the table header and print a bold notice such as
    # "There are currently **no** stale `delegated` PRs. Congratulations!".
    if not prs:
        print(f'There are currently <b>no</b> {short_description(kind)}. Congratulations!\n')
        return

    # Explain what each PR list contains.
    # Use a header to make space before the table, but don't make it bold.
    print(f"""<h5 style="font-weight:normal">{long_description(kind)}</h5>
    <table>
    <thead>
    <tr>
    <th>Number</th>
    <th>Author</th>
    <th>Title</th>
    <th>Labels</th>
    <th>+/-</th>
    <th>&#128221;</th>
    <th>&#128172;</th>
    <th>Updated</th>
    </tr>
    </thead>""")

    _print_pr_entries(pr_infos, prs)

    # Print the footer
    print("</table>")


def print_dashboard(datae : List[dict], kind : PRList):
    '''`datae` is a list of parsed data files to process'''

    # Print all PRs in all the data files.
    prs_to_show = []
    for data in datae:
        for page in data["output"]:
            for entry in page["data"]["search"]["nodes"]:
                labels = [Label(label["name"], label["color"], label["url"]) for label in entry["labels"]["nodes"]]
                prs_to_show.append(BasicPRInformation(
                    entry["number"], entry["author"], entry["title"], entry["url"], labels, entry["updatedAt"]
                ))
    # Open the file containing the PR info.
    with open(sys.argv[1], 'r') as f:
        pr_infos = json.load(f)
        _print_dashboard(pr_infos, prs_to_show, kind)


def print_bad_unlabelled_prs(data : dict):
    # Print dashboards of all PRs without a topic label and all PRs with a badly formatted title,
    # among those given in `data`.

    all_prs = []
    for page in data["output"]:
        for entry in page["data"]["search"]["nodes"]:
            labels = [Label(label["name"], label["color"], label["url"]) for label in entry["labels"]["nodes"]]
            all_prs.append(BasicPRInformation(
                entry["number"], entry["author"], entry["title"], entry["url"], labels, entry["updatedAt"]
            ))

    with_bad_title = [pr for pr in all_prs if not pr.title.startswith(("feat", "chore", "perf", "refactor", "style", "fix", "doc"))]
    # Whether a PR has a "topic" label.
    def has_topic_label(pr: BasicPRInformation) -> bool:
        topic_labels = [l for l in pr.labels if l.name == 'CI' or l.name.startswith("t-")]
        return len(topic_labels) >= 1
    prs_without_topic_label = [pr for pr in all_prs if pr.title.startswith("feat") and not has_topic_label(pr)]

    # Open the file containing the PR info.
    with open(sys.argv[1], 'r') as f:
        pr_infos = json.load(f)
        _print_dashboard(pr_infos, with_bad_title, PRList.BadTitle)
        _print_dashboard(pr_infos, prs_without_topic_label, PRList.Unlabelled)


main()
