import datetime
import enum
import math
import re
from typing import Optional, NamedTuple

from bs4 import BeautifulSoup, Tag


class ClubGroup:
    def __init__(self, links: Tag, thead: Tag, trs: list[Tag], payment_totals: Optional[Tag] = None):
        self.links = links
        self.thead = thead
        self.trs = trs
        self.payment_totals = payment_totals


class EntryState(enum.Enum):
    OK = 0
    AVO = 1
    AVC = 2

class LicenseStatus(enum.Enum):
    NOT_RENEWED = 0
    RENEWED = 1

class StageEntry:
    def __init__(self, class_name: str):
        self.class_name = class_name
        self.date_of_entry: Optional[datetime.date] = None
        self.amount_to_pay: Optional[float] = None
        self.with_discount: Optional[bool] = None

    def set_date_of_entry(self, date_of_entry: datetime.date) -> "StageEntry":
        self.date_of_entry = date_of_entry
        return self

    def set_amount_to_pay(self, amount_to_pay: float) -> "StageEntry":
        self.amount_to_pay = amount_to_pay
        return self

    def set_with_discount(self, with_discount: bool) -> "StageEntry":
        self.with_discount = with_discount
        return self

class Payment(NamedTuple):
    amount: float
    date: datetime.date


class Entry:
    def __init__(
        self,
        name: str,
        birth_year: int,
        state: int,
        license_type: Optional[str] = None,
        license_number: Optional[int] = None,
        SI: int | list[int | None] | None = None,
        stages_classes: list[Optional[StageEntry]] | None = None,
    ):
        self.name = name
        self.birth_year = birth_year
        self.license_type = license_type
        self.license_number = license_number
        self.SI = SI
        self.stages_classes = stages_classes
        self.state = state
        self.license_status: Optional[LicenseStatus] = None
        self.extras: Optional[list[str]] = None
        self.total_extras_to_pay: Optional[float] = None
        self.total_to_pay: Optional[float] = None
        self.amount_paid: Optional[Payment] = None
        self.payment_difference: Optional[float] = None

    def set_license_status(self, license_status: LicenseStatus) -> "Entry":
        self.license_status = license_status
        return self

    def set_extras(self, extras: list[str]) -> "Entry":
        self.extras = extras
        return self

    def set_total_extras_to_pay(self, total_extras_to_pay: float) -> "Entry":
        self.total_extras_to_pay = total_extras_to_pay
        return self

    def set_total_to_pay(self, total_to_pay: float) -> "Entry":
        self.total_to_pay = total_to_pay
        return self

    def set_amount_paid(self, amount_paid: Payment) -> "Entry":
        self.amount_paid = amount_paid
        return self

    def set_payment_difference(self, payment_difference: float) -> "Entry":
        self.payment_difference = payment_difference
        return self

class PaymentTotals(NamedTuple):
    extras: float
    total_to_pay: float
    paid: float
    difference: float

class ClubEntries:
    def __init__(
        self,
        club_license_id: int,
        club_orioasis_id: int,
        club_name: str,
        club_nick: str,
        country: str,
        country_code: str,
    ):
        self.club_license_id = club_license_id
        self.club_orioasis_id = club_orioasis_id
        self.club_name = club_name
        self.club_nick = club_nick
        self.country = country
        self.country_code = country_code
        self.payment_totals: Optional[PaymentTotals] = None
        self.entries: list[Entry] = []

    def set_payment_totals(self, payment_totals: PaymentTotals) -> "ClubEntries":
        self.payment_totals = payment_totals
        return self

    def add_entry(self, entry: Entry):
        self.entries.append(entry)

    def generate_entries_link(self, event_id):
        return f'https://www.orioasis.pt/oasis/entries.php?action=club_class&eventid={event_id}&clubid={self.club_orioasis_id}#et'


def _extract(html):
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
    At the top of each there there is a row with no border, containing the **row-no-border** class. It contains
     the "View entries of other clubs / classes" and "Pay entries" links. From the "Pay entries" link, we extract the
     club id from the href attribute.
    At the bottom of each table there are is another row with no border, containing the **row-no-border** class, with
     no inner text which we discard.
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

    return childs

def _group(childs, detailed_view):
    # From the gathered rows, lets group athletes rows per club
    club_groups: list[ClubGroup] = []
    club_links = None
    club_thead = None
    club_payment_totals = None
    club_runners_trs = []
    i = 0
    while i < len(childs):
        child = childs[i]

        if child.name == 'tr' and 'row-no-border' in child.attrs.get('class', []):
            # a club group starts with a club links element, next is a thead where we can find club's name.
            # We process those two rows here, thats why we skip 2 later, on this if block

            if club_links is not None:
                club_groups.append(ClubGroup(club_links, club_thead, club_runners_trs))
                club_runners_trs = []

            club_links = child
            club_thead = childs[i + 1]

            # print(club_links.name, club_links.attrs)
            # print(club_thead.name, club_thead.attrs)

            i += 2
        elif detailed_view and "Total " in child.text:
            club_payment_totals = child

            i += 1
        else:
            # otherwise is a runner tr
            # print(child.name, child.attrs)
            club_runners_trs.append(child)

            i += 1

    if club_runners_trs:
        club_groups.append(ClubGroup(club_links, club_thead, club_runners_trs, club_payment_totals))

    return club_groups

def _parse(club_groups, event_id: str, detailed_view: bool) -> list[ClubEntries]:
    """
    TODO
    """

    clubs_entries: list[ClubEntries] = []
    for group in club_groups:
        club_info = group.thead.find("b").text.strip()

        club_info = [e.strip() for e in club_info.split(" / ")]  # orioasis separates club name and nick with " / "

        club_name = club_info[0]
        club_license_id = club_name[1:club_name.find("]")]
        club_name = club_name[club_name.find("]")+1:].strip()  # remove the club license id

        try:
            club_name, club_nick = club_name.split(" - ")
        except ValueError:
            # clubs with "-" in their name [and nick]

            parts = club_name.split(" - ")

            #club_name = " - ".join(parts[:math.ceil(len(parts) / 2)])
            club_nick = " - ".join(parts[math.ceil(len(parts) / 2):])

            #print(club_name, "+",  club_nick)
        #print(club_name, "+",  club_nick)

        club_country = [e.strip() for e in club_info[1].split("-")]
        club_country_code = club_country[1]
        club_country = club_country[0]

        club_pay_link = group.links.find_all("a")[1].attrs["href"]
        """
        1st link is entries of other clubs
        2st link is pay link of that club, where we can extract club id
        """
        #print(club_pay_link)
        club_orioasis_id = re.search(r'clubid=(-?\d+)', club_pay_link).group(1)
        #print(club_id)

        if detailed_view:
            # TODO set payment totals
            pass

        club_entries = ClubEntries(club_license_id, club_orioasis_id, club_name, club_nick, club_country, club_country_code)

        for tr in group.trs:
            tds = tr.find_all("td", recursive=False)

            runner_name = tds[0].text.strip()
            birth_year = int(tds[1].text.strip())

            license_type = tds[2].text.strip()
            license_type = license_type if license_type else None

            license_id = tds[3]
            if detailed_view:
                pass  # TODO handle license id and state
            else:
                license_id = license_id.text.strip()
                license_id = int(license_id) if license_id else None

            runner_si = tds[4].text.strip()  # TODO support multiple SI per stages

            stages = []
            for i in range(5, len(tds) - 1):
                stage = tds[i].text.strip()
                stages.append(StageEntry(stage) if stage != "-" else None)

                if detailed_view:
                    pass  # TODO fetch stage information

            state = EntryState.OK.value if tds[-1].text.strip() == "OK" else EntryState.AVO.value  # TODO conversion for other states

            entry = Entry(runner_name, birth_year, state, license_type, license_id, runner_si, stages)

            if detailed_view:
                # TODO
                pass

            club_entries.add_entry(entry)

        clubs_entries.append(club_entries)

    return clubs_entries


def extract_entries(html: str, event_id: str, detailed_view: bool = False) -> list[ClubEntries]:
    childs = _extract(html)

    club_groups = _group(childs, detailed_view)

    entries = _parse(club_groups, event_id, detailed_view)

    return entries