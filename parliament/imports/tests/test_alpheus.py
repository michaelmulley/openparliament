import datetime
from pathlib import Path
# from unittest import TestCase
from django.test import TestCase

from parliament.imports import alpheus

def alpheus_generate_html(xml_path: Path) -> str:
    doc = alpheus.parse_bytes(xml_path.read_bytes())
    return doc.as_html()

def write_example_html(xml_path: Path):
    assert xml_path.exists()
    html_path = xml_path.parent / f'{xml_path.stem}.html'
    html = alpheus_generate_html(xml_path)
    html_path.write_text(html, encoding='utf8')

def overwrite_all_example_html():
    examples_dir = Path(__file__).parent / 'alpheus_examples'
    for example_xml_path in examples_dir.glob('*.xml'):
        write_example_html(example_xml_path)

class AlpheusIntegrationTests(TestCase):

    def test_examples(self):
        examples_dir = Path(__file__).parent / 'alpheus_examples'
        for example_xml_path in examples_dir.glob('*.xml'):
            example_html_path = examples_dir / f'{example_xml_path.stem}.html'
            output_html = alpheus_generate_html(example_xml_path)
            assert example_html_path.exists(), f"Missing {example_html_path}"
            self.assertMultiLineEqual(output_html,
                                      example_html_path.read_text(encoding='utf8'),
                                      msg=f"Comparing HTML output of {example_xml_path.stem}")
            

class AlpheusTimestampTests(TestCase):

    EXAMPLE = Path(__file__).parent / 'alpheus_examples' / '12324877-en.xml'  # dated 2023-09-20

    def _parse_with_replaced_timestamp(self, replacement: str):
        xml = self.EXAMPLE.read_bytes()
        original = b'<Timestamp Hr="16" Mn="35">(1635)</Timestamp>'
        assert xml.count(original) == 1
        return alpheus.parse_bytes(xml.replace(original, replacement.encode('utf8')))

    def test_resumed_meeting_hour_offset_rolls_date_forward(self):
        # Committee evidence encodes a meeting resumed on a later day as a large hour value
        doc = self._parse_with_replaced_timestamp('<Timestamp Hr="60" Mn="35">(6035)</Timestamp>')
        timestamps = {s.meta['timestamp'] for s in doc.statements}
        self.assertIn(datetime.datetime(2023, 9, 22, 12, 35), timestamps)
        self.assertNotIn(datetime.datetime(2023, 9, 20, 16, 35), timestamps)

    def test_garbage_timestamp_is_ignored(self):
        # Seen in the wild (evidence 11512279, 2022-02-10): Hr="17716692", i.e. the year 4043.
        # The statements following it should keep the previous timestamp instead.
        doc = self._parse_with_replaced_timestamp(
            '<Timestamp Hr="17716692" Mn="20">(1771669220)</Timestamp>')
        timestamps = [s.meta['timestamp'] for s in doc.statements]
        self.assertTrue(all(t.date() == datetime.date(2023, 9, 20) for t in timestamps), timestamps)
        clean_doc = alpheus.parse_bytes(self.EXAMPLE.read_bytes())
        self.assertEqual(len(timestamps), len(clean_doc.statements))
        for garbled, clean in zip(doc.statements, clean_doc.statements):
            self.assertEqual(garbled.meta['id'], clean.meta['id'])
            if clean.meta['timestamp'] == datetime.datetime(2023, 9, 20, 16, 35):
                self.assertEqual(garbled.meta['timestamp'], datetime.datetime(2023, 9, 20, 16, 30))
            else:
                self.assertEqual(garbled.meta['timestamp'], clean.meta['timestamp'])
