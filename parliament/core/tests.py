import datetime

from django.test import TestCase

from parliament.core.models import SittingDay
from parliament.core.views import next_sitting_context


class NextSittingContextTest(TestCase):

    def setUp(self):
        for d in (datetime.date(2026, 6, 18), datetime.date(2026, 9, 21),
                  datetime.date(2026, 9, 22), datetime.date(2026, 9, 25),
                  datetime.date(2026, 9, 28),
                  datetime.date(2026, 10, 5)):
            SittingDay.objects.create(date=d)

    def test_long_break(self):
        c = next_sitting_context(datetime.date(2026, 6, 18), today=datetime.date(2026, 9, 7))
        self.assertEqual(c['next_sitting'].date, datetime.date(2026, 9, 21))
        self.assertFalse(c['sitting_today'])
        self.assertTrue(c['next_sitting_far'])
        # Still prominent the day before the House returns
        c = next_sitting_context(datetime.date(2026, 6, 18), today=datetime.date(2026, 9, 20))
        self.assertTrue(c['next_sitting_far'])
        self.assertEqual(c['next_sitting'].when(datetime.date(2026, 9, 20)), 'tomorrow')

    def test_sitting_today_before_hansard_arrives(self):
        for today in (datetime.date(2026, 9, 21), datetime.date(2026, 9, 22)):
            c = next_sitting_context(datetime.date(2026, 6, 18), today=today)
            self.assertEqual(c['next_sitting'].date, today)
            self.assertTrue(c['sitting_today'])
            self.assertFalse(c['next_sitting_far'])

    def test_short_break(self):
        # Weekend: Friday's transcript is in, House is back Monday
        c = next_sitting_context(datetime.date(2026, 9, 25), today=datetime.date(2026, 9, 26))
        self.assertFalse(c['sitting_today'])
        self.assertFalse(c['next_sitting_far'])
        self.assertEqual(c['next_sitting'].when(datetime.date(2026, 9, 26)), 'on Monday')
        # A constituency week counts as a long break
        c = next_sitting_context(datetime.date(2026, 9, 25), today=datetime.date(2026, 9, 30))
        self.assertTrue(c['next_sitting_far'])

    def test_nothing_scheduled(self):
        c = next_sitting_context(datetime.date(2026, 10, 5), today=datetime.date(2026, 10, 6))
        self.assertIsNone(c['next_sitting'])
        self.assertFalse(c['sitting_today'])
        self.assertFalse(c['next_sitting_far'])
