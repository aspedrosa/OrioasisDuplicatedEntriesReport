import argparse
import os.path
import pprint
import re
import sys
from math import ceil
from typing import NamedTuple, List, Optional

import requests
from bs4 import BeautifulSoup, Tag

CACHE_RESPONSE_PATH = "cache_response.txt"

class ClubGroup(NamedTuple):
    links: Tag
    thead: Tag
    trs: List[Tag]

class RunnerEntry(NamedTuple):
    club_entries_link: str
    club_nick: str
    runner_name: str
    runner_si: str

def main(args: argparse.Namespace):
    html = fetch_entries_per_club_html_page(args.cache_page, args.event)

    runner_entries = extract_runners_entries_from_html(html, args.event)

    fields_titles = {
        "runner_name": "Duplicates by Name",
        "runner_si": "Duplicates by SI",
    }

    duplicates_fields = [
        ("runner_name", runner_entries),
        ("runner_si", [r for r in runner_entries if r.runner_si != "Aluguer"]),
    ]

    duplicates_by_field_collection = []
    for field_name, runner_entries in duplicates_fields:
        # TODO be able to ignore SIs
        duplicates_by_field = find_duplicates_by_field(runner_entries, field_name, args.runner_names_to_ignore_duplicates)
        #print(f"Total entries by {field_name}: {len(duplicates_by_field)}")

        if not duplicates_by_field:
            continue

        duplicates_by_field_collection.append((field_name, duplicates_by_field))

    if args.skip_send_email:
        for field_name, duplicates in duplicates_by_field_collection:
            print(f"Duplicates by {field_name}:")
            pprint.pprint(duplicates)
        return

    if not duplicates_by_field_collection:
        print("No duplicates found")
        return

    duplicates_tables = []
    for field_name, duplicates in duplicates_by_field_collection:
        #print(field_name)
        #print(duplicates)
        duplicates_tables.append(generate_duplicates_table(duplicates, field_name, fields_titles[field_name]))

    #print(duplicates_tables)
    send_duplicates_email(duplicates_tables)

def _fetch_entries_per_club_html_page(event_id) -> str:
    """Fetches entries per club page from OriOasis"""
    response = requests.get(
        f'https://www.orioasis.pt/oasis/entries.php?eventid={event_id}&action=club_class&order=clubs.nick&task=&sh=&show_details=')

    if response.status_code != 200:
        print(f'Error: {response.status_code}', file=sys.stderr)
        print(f'Response: {response.text}', file=sys.stderr)
        sys.exit(1)

    return response.text

def fetch_entries_per_club_html_page(cache_entries_page, event_id) -> str:
    """Returns cached or fetched event entries html page"""
    if cache_entries_page:
        if not os.path.exists(CACHE_RESPONSE_PATH):
            html = _fetch_entries_per_club_html_page(event_id)

            with open(CACHE_RESPONSE_PATH, "w+") as f:
                f.write(html)

            return html

        with open(CACHE_RESPONSE_PATH) as f:
            return f.read()
    else:
        return _fetch_entries_per_club_html_page(event_id)

def extract_runners_entries_from_html(html, event_id) -> list[RunnerEntry]:
    soup = BeautifulSoup(html, 'html.parser')

    """
    Get all tables on the page. The one we want is the 4th one, which contains runners entries
    1st table clubs
    2nd table classes
    3rd table countries
    4th table runners
    """
    runners_table = soup.find_all("table", attrs={"class": "TableBorderLight"})[3]

    """
    From the table above, lets gather all the information.
    In reality, each club entries is a table within that big table.
    
    Club information is stored in thead elements within these subtables.
    Runners information is stored in tr elements within these subtables.
    At the bottom of each table there are two rows with no border, containing the **row-no-border** class.
    One is just an empty line, with no inner text which we discard.
    The other contains "View entries of other clubs / classes" and "Pay entries" links. For this "Pay entries" link,
     we extract the club id from the href attribute.
    """
    childs = list(runners_table.children)
    childs = [
        child
        for child in childs
        if child.name == 'thead'
           or
            (child.name == 'tr'
                and
                (
                 'row-no-border' not in child.attrs.get('class', [])  # either does no have the class row-no-border
                 or child.text.strip() != ''  # or if it does, it must have inner text
                )
            )
    ]
    childs = childs[1:]  # skip the first tr, it is the runners, big table, table header

    # From the gathered rows, lets group athletes rows per club
    club_groups: List[ClubGroup] = []
    club_links = None
    club_thead = None
    club_runners_trs = []
    i = 0
    while i < len(childs):
        child = childs[i]

        if child.name == 'tr' and 'row-no-border' in child.attrs.get('class', []):
            # a club group starts with a club links element, next is a thead where we can find club's name.
            # thats why we skip 2 later, on this if block

            if club_links is not None:
                club_groups.append(ClubGroup(club_links, club_thead, club_runners_trs))
                club_runners_trs = []

            club_links = child
            club_thead = childs[i + 1]

            #print(club_links.name, club_links.attrs)
            #print(club_thead.name, club_thead.attrs)

            i += 2
        else:
            # otherwise is a runner tr
            #print(child.name, child.attrs)
            club_runners_trs.append(child)

            i += 1

    if club_runners_trs:
        club_groups.append(ClubGroup(club_links, club_thead, club_runners_trs))

    #print(club_groups)

    # now lets create a list of runners, with information of its club (entries link and nick)
    runner_entries: List[RunnerEntry] = []
    for group in club_groups:
        club_info = group.thead.find("b").text.strip()

        club_info = [e.strip() for e in club_info.split(" / ")]  # orioasis separates club name and nick with " / "

        club_name = club_info[0]
        club_name = club_name[club_name.find("]")+1:].strip()  # remove the club license id

        try:
            club_name, club_nick = club_name.split(" - ")
        except ValueError:
            # clubs with "-" in their name [and nick]

            parts = club_name.split(" - ")

            #club_name = " - ".join(parts[:ceil(len(parts) / 2)])
            club_nick = " - ".join(parts[ceil(len(parts) / 2):])

            #print(club_name, "+",  club_nick)
        #print(club_name, "+",  club_nick)

        club_pay_link = group.links.find_all("a")[1].attrs["href"]
        """
        1st link is entries of other clubs
        2st link is pay link of that club, where we can extract club id
        """
        #print(club_pay_link)
        club_id = re.search(r'clubid=(-?\d+)', club_pay_link).group(1)
        #print(club_id)
        club_entries_link = f'https://www.orioasis.pt/oasis/entries.php?action=club_class&eventid={event_id}&clubid={club_id}#et'
        #print(club_entries_link)

        for tr in group.trs:
            tds = tr.find_all("td", recursive=False)
            runner_name = tds[0].text.strip()
            runner_si = tds[4].text.strip()
            runner_entries.append(RunnerEntry(club_entries_link, club_nick, runner_name, runner_si))

    return runner_entries

def find_duplicates_by_field(data: list[RunnerEntry], fild_name, values_to_ignore_duplicates) -> list[RunnerEntry]:
    if not values_to_ignore_duplicates:
        values_to_ignore_duplicates = []
    else:
        values_to_ignore_duplicates = values_to_ignore_duplicates[0].split(",")

    def get_value(runner: RunnerEntry):
        return getattr(runner, fild_name)

    # print(all_data_tuples)
    data.sort(key=lambda x: get_value(x))
    # print(all_data_tuples)
    previous_runner: Optional[RunnerEntry] = None
    duplicates = []
    for current_runner in data:
        if previous_runner and get_value(previous_runner) == get_value(current_runner):
            if get_value(current_runner) not in values_to_ignore_duplicates:
                duplicates.append(previous_runner)
                duplicates.append(current_runner)
            # print(" + ".join(previous_runner))
            # print(" + ".join(current_runner))

        previous_runner = current_runner

    return duplicates

def generate_duplicates_table(duplicates, field_name, field_title):
    remaining_fields = ["club_nick", "runner_name", "runner_si"]
    remaining_fields.remove(field_name)

    # Build HTML Table
    table_rows = ""
    for entry in duplicates:
        table_rows += "<tr>"
        table_rows += f"<td><a href='{entry.club_entries_link}'>Link</a></td>"
        table_rows += f"<td>{getattr(entry, field_name)}</td>"
        for field in remaining_fields:
            table_rows += f"<td>{getattr(entry, field)}</td>"
        table_rows += "</tr>"

    remaining_fields_ths = "\n".join(f"<th>{field}</th>" for field in remaining_fields)

    table_html = f"""
    <h3>{field_title}</h3>
    <table border="1" style="border-collapse: collapse; width: 100%;">
        <thead>
            <tr style="background-color: #f2f2f2;">
                <th>Club Entries Link</th>
                <th>{field_name}</th>
                {remaining_fields_ths}
            </tr>
        </thead>
        <tbody>
            {table_rows}
        </tbody>
    </table>
    """

    return table_html


def send_duplicates_email(tables: list[str]) -> None:
    email_content = "<h2>Duplicated Entries Report</h2>\n"
    email_content += "\n".join(tables)

    mailgun_domain = os.environ['MAILGUN_DOMAIN']

    response = requests.post(
        f"https://api.mailgun.net/v3/{mailgun_domain}/messages",
        auth=("api", os.environ['MAILGUN_API_KEY']),
        data={
            "from": f"Mailgun Sandbox <postmaster@{mailgun_domain}>",
            "to": os.environ['MAIL_TO'],
            "subject": "POM 2026 Daily duplicated entries report",
            "html": email_content,
        }
    )

    print(response.status_code)
    print(response.text)

    if response.status_code != 200:
        sys.exit(1)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--event', required=True, help='Event id to send duplicates report')
    parser.add_argument('--cache-page', action='store_true', default=False, help='Cache the entries per club page')
    parser.add_argument('--skip-send-email', action='store_true', default=False, help='Skip sending email')
    parser.add_argument('--runner-names-to-ignore-duplicates', nargs=1, help='Comma-separated list of runner names to ignore duplicates')

    args = parser.parse_args()

    main(args)
