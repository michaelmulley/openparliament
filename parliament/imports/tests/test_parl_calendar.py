import datetime
import os
from unittest import mock

from django.test import TestCase

from parliament.core.models import SittingDay
from parliament.imports import parl_calendar

FIXTURE = os.path.join(os.path.dirname(__file__), 'sitting_calendar_2027.html')


class ParseCalendarTest(TestCase):

    def test_parse(self):
        with open(FIXTURE, 'rb') as f:
            year, days = parl_calendar.parse_calendar(f.read())
        self.assertEqual(year, 2027)
        self.assertEqual(len(days), 153)
        self.assertEqual(sum(days.values()), 48)
        self.assertIs(days[datetime.date(2027, 1, 25)], True)
        self.assertIs(days[datetime.date(2027, 12, 17)], False)
        # "Adjournment tabling" days aren't sittings
        self.assertNotIn(datetime.date(2027, 8, 20), days)
        self.assertNotIn(datetime.date(2027, 1, 1), days)

    def test_missing_year(self):
        with self.assertRaises(parl_calendar.CalendarParseError):
            parl_calendar.parse_calendar('<div><table class="chamber-calendar"></table></div>')


class SaveCalendarTest(TestCase):

    def test_save_replaces_year(self):
        SittingDay.objects.create(date=datetime.date(2027, 3, 1), tentative=True)
        SittingDay.objects.create(date=datetime.date(2027, 3, 2), tentative=True)
        SittingDay.objects.create(date=datetime.date(2026, 12, 1))
        parl_calendar.save_calendar_year(2027, {
            datetime.date(2027, 3, 1): False,
            datetime.date(2027, 3, 3): True,
        })
        self.assertEqual(
            list(SittingDay.objects.values_list('date', 'tentative')),
            [(datetime.date(2026, 12, 1), False),
             (datetime.date(2027, 3, 1), False),
             (datetime.date(2027, 3, 3), True)])

    def test_import_stops_at_unpublished_year(self):
        def fake_fetch(year):
            # The site serves the last published year for later requests
            return min(year, 2027), {datetime.date(min(year, 2027), 2, 1): False}
        with mock.patch.object(parl_calendar, 'fetch_calendar', fake_fetch):
            self.assertEqual(parl_calendar.import_sitting_calendar(2026), [2026, 2027])
        self.assertEqual(SittingDay.objects.count(), 2)

    def test_import_requires_a_calendar(self):
        with mock.patch.object(parl_calendar, 'fetch_calendar', lambda year: (2026, {})):
            with self.assertRaises(parl_calendar.CalendarParseError):
                parl_calendar.import_sitting_calendar(2026)


class HouseStatusTest(TestCase):

    STATUS = 'The House is adjourned until Monday, September 21, 2026.'

    def test_parse(self):
        html = """<div id="in-the-house-content-sync"><div>
            <span class="now-in-the-house-subtitle">The House is adjourned until
              Monday, September 21, 2026.</span></div>
            <span class="now-in-the-house-subtitle"> </span></div>"""
        self.assertEqual(parl_calendar.parse_house_status(html), self.STATUS)
        self.assertEqual(parl_calendar.parse_adjourned_until(self.STATUS),
            datetime.date(2026, 9, 21))
        self.assertIsNone(parl_calendar.parse_adjourned_until('The House is sitting.'))
        with self.assertRaises(parl_calendar.CalendarParseError):
            parl_calendar.parse_house_status('<div id="in-the-house-content-sync"></div>')

    def test_apply_adjournment(self):
        for d in (datetime.date(2026, 9, 4), datetime.date(2026, 9, 14),
                  datetime.date(2026, 9, 15), datetime.date(2026, 9, 22)):
            SittingDay.objects.create(date=d)
        today = datetime.date(2026, 9, 7)
        self.assertEqual(parl_calendar.apply_house_status(self.STATUS, today),
            datetime.date(2026, 9, 21))
        # Skipped days are gone, the return date is added, the past is untouched
        self.assertEqual(list(SittingDay.objects.values_list('date', flat=True)),
            [datetime.date(2026, 9, 4), datetime.date(2026, 9, 21), datetime.date(2026, 9, 22)])
        self.assertEqual(SittingDay.objects.next(today).date, datetime.date(2026, 9, 21))

    def test_apply_ignores_other_statuses(self):
        SittingDay.objects.create(date=datetime.date(2026, 9, 14))
        today = datetime.date(2026, 9, 7)
        self.assertIsNone(parl_calendar.apply_house_status('The House is sitting.', today))
        # A stale adjournment (page not updated yet) shouldn't delete anything
        self.assertIsNone(parl_calendar.apply_house_status(
            'The House is adjourned until Friday, September 4, 2026.', today))
        self.assertEqual(SittingDay.objects.count(), 1)


class SittingDayTest(TestCase):

    def test_next_and_when(self):
        today = datetime.date(2026, 9, 5)  # a Saturday
        self.assertIsNone(SittingDay.objects.next(today))
        for d in (datetime.date(2026, 9, 4), datetime.date(2026, 9, 21), datetime.date(2026, 9, 22)):
            SittingDay.objects.create(date=d)
        nxt = SittingDay.objects.next(today)
        self.assertEqual(nxt.date, datetime.date(2026, 9, 21))
        self.assertEqual(nxt.days_away(today), 16)
        self.assertEqual(nxt.when(today), 'on Monday, September 21st')
        self.assertEqual(nxt.when(datetime.date(2026, 9, 21)), 'today')
        self.assertEqual(nxt.when(datetime.date(2026, 9, 20)), 'tomorrow')
        self.assertEqual(nxt.when(datetime.date(2026, 9, 16)), 'on Monday')
        self.assertEqual(nxt.when(datetime.date(2026, 9, 14)), 'on Monday, September 21st')
        self.assertEqual(nxt.when(datetime.date(2025, 12, 30)), 'on Monday, September 21st, 2026')
        self.assertEqual(SittingDay.objects.next(datetime.date(2026, 9, 21)).date, nxt.date)
