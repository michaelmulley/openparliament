"""Import the House of Commons sitting schedule from ourcommons.ca.

Two sources. The sitting calendar gives the planned days for the year: it
marks each one as a table cell whose class attribute carries the date
(YYYY-MM-DD, or M/D/YYYY in older pages) plus either "chamber-meeting"
or, for the following year's calendar before it's finalized under
S.O. 28(2)(b), "subject-to-change".
The calendar gets revised after the fact (e.g. after a prorogation), but
it doesn't reflect ad hoc changes like adjourning a week early or being
recalled. For those, the "In the House" box on the ourcommons.ca homepage
says "The House is adjourned until <date>", which is the same date the
Journals record at the end of each sitting.
"""
import datetime
import logging
import re

from django.db import transaction

import lxml.html
import requests

from parliament.core.models import SittingDay

logger = logging.getLogger(__name__)

CALENDAR_URL = 'https://www.ourcommons.ca/en/sitting-calendar/{year}'
HOUSE_STATUS_URL = 'https://www.ourcommons.ca/en'
# How many years, starting with the current one, to try fetching
MAX_YEARS = 4

# The site switched from M/D/YYYY to ISO dates in 2026; accept either
DATE_CLASS_RES = [
    re.compile(r'^(?P<year>\d{4})-(?P<month>\d{2})-(?P<day>\d{2})$'),
    re.compile(r'^(?P<month>\d{1,2})/(?P<day>\d{1,2})/(?P<year>\d{4})$'),
]
ADJOURNED_UNTIL_RE = re.compile(r'adjourned until (\w+, \w+ \d{1,2}, \d{4})', re.I)


class CalendarParseError(Exception):
    pass


def parse_calendar(html) -> tuple[int, dict[datetime.date, bool]]:
    """Parse a sitting-calendar page.

    Returns (year, days), where days maps each scheduled sitting date to
    whether it's still marked as subject to change."""
    root = lxml.html.fromstring(html)

    year_els = root.xpath('//*[contains(concat(" ", normalize-space(@class), " "), " hoc-selectedDate ")]')
    if not year_els or not year_els[0].text_content().strip().isdigit():
        raise CalendarParseError("Couldn't find the calendar year on the page")
    year = int(year_els[0].text_content().strip())

    days = {}
    for td in root.xpath('//table[contains(concat(" ", normalize-space(@class), " "), " chamber-calendar ")]//td[@class]'):
        classes = td.get('class').split()
        if 'chamber-meeting' in classes:
            tentative = False
        elif 'subject-to-change' in classes:
            tentative = True
        else:
            continue
        match = next((m for cls in classes for regex in DATE_CLASS_RES
                      if (m := regex.match(cls))), None)
        if not match:
            raise CalendarParseError("Sitting-day cell without a date: %r" % td.get('class'))
        cell_year, month, day = (int(match.group(g)) for g in ('year', 'month', 'day'))
        if cell_year != year:
            raise CalendarParseError("Cell dated %s on the %s calendar" % (match.group(0), year))
        days[datetime.date(cell_year, month, day)] = tentative

    # The legend gives a total we can check ourselves against
    legend = re.search(r'Sitting days \((\d+) in total\)', root.text_content())
    if legend and int(legend.group(1)) != len(days):
        logger.warning("Calendar legend for %s says %s sitting days; we found %s",
            year, legend.group(1), len(days))

    return year, days


def fetch_calendar(year: int) -> tuple[int, dict[datetime.date, bool]]:
    resp = requests.get(CALENDAR_URL.format(year=year))
    resp.raise_for_status()
    return parse_calendar(resp.content)


@transaction.atomic
def save_calendar_year(year: int, days: dict[datetime.date, bool]) -> None:
    """Make our stored sitting days for the year match the calendar.

    Days that have dropped off the calendar (the House revises it, e.g.
    after an election) are deleted."""
    existing = {sd.date: sd for sd in SittingDay.objects.filter(date__year=year)}
    for date, sd in existing.items():
        if date not in days:
            sd.delete()
        elif sd.tentative != days[date]:
            sd.tentative = days[date]
            sd.save()
    SittingDay.objects.bulk_create([
        SittingDay(date=date, tentative=tentative)
        for date, tentative in days.items() if date not in existing
    ])


def import_sitting_calendar(start_year: int | None = None) -> list[int]:
    """Fetch and save the calendars for the current year and any later
    years that ourcommons.ca has published. Returns the years imported."""
    if start_year is None:
        start_year = datetime.date.today().year
    imported = []
    for year in range(start_year, start_year + MAX_YEARS):
        page_year, days = fetch_calendar(year)
        if page_year != year:
            # The site serves some other year's calendar when asked for one
            # that doesn't exist yet
            break
        if not days:
            # Years the House hasn't scheduled yet get an empty calendar page
            if not imported:
                logger.warning("No sitting days found on the %s calendar; leaving it alone", year)
            break
        save_calendar_year(year, days)
        imported.append(year)
    if not imported:
        raise CalendarParseError("Couldn't import a sitting calendar for %s" % start_year)
    return imported


def parse_house_status(html) -> str:
    """Return the status line from the "In the House" box on the ourcommons.ca
    homepage, e.g. "The House is adjourned until Monday, September 21, 2026." """
    root = lxml.html.fromstring(html)
    for el in root.xpath('//*[@id="in-the-house-content-sync"]'
            '//*[contains(concat(" ", normalize-space(@class), " "), " now-in-the-house-subtitle ")]'):
        text = ' '.join(el.text_content().split())
        if text:
            return text
    raise CalendarParseError("Couldn't find the House status on the ourcommons.ca homepage")


def parse_adjourned_until(status: str) -> datetime.date | None:
    """The date the House is adjourned until, if that's what the status says."""
    match = ADJOURNED_UNTIL_RE.search(status)
    if not match:
        return None
    return datetime.datetime.strptime(match.group(1), '%A, %B %d, %Y').date()


def fetch_house_status() -> str:
    resp = requests.get(HOUSE_STATUS_URL)
    resp.raise_for_status()
    return parse_house_status(resp.content)


@transaction.atomic
def apply_house_status(status: str, today: datetime.date | None = None) -> datetime.date | None:
    """Reconcile our sitting days with the House's current status.

    If the House is adjourned until a date, any calendar days before then
    aren't happening, and that date is a sitting day whether or not the
    calendar planned one. Returns the adjourned-until date, if any."""
    if today is None:
        today = datetime.date.today()
    until = parse_adjourned_until(status)
    if until is None:
        logger.info("House status not an adjournment: %r", status)
        return None
    if until < today:
        logger.warning("House status is stale: %r", status)
        return None
    skipped = SittingDay.objects.filter(date__gte=today, date__lt=until)
    if skipped.exists():
        logger.info("Removing %s sitting days before %s: %r", skipped.count(), until, status)
        skipped.delete()
    SittingDay.objects.get_or_create(date=until)
    return until


def import_house_schedule() -> None:
    """Import the calendar, then apply the current House status on top."""
    import_sitting_calendar()
    apply_house_status(fetch_house_status())
