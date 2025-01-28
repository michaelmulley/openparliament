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
            