import re
from urllib.parse import urljoin

import lxml.html
import lxml.etree
from lxml.html.clean import clean
import requests

from parliament.imports import CannotScrapeException


def get_bill_text_xml(bill_or_url) -> lxml.etree.ElementBase:
    """Given a Bill object or URL to a full-text page on ourcommons.ca,
    returns an lxml etree of the XML version of the bill text."""

    if hasattr(bill_or_url, 'get_billtext_url'):
        bill_or_url = bill_or_url.get_billtext_url()

    resp = requests.get(bill_or_url)
    html_root = lxml.html.fromstring(resp.content)
    xml_button = html_root.cssselect('a.btn-export-xml')
    if not xml_button:
        raise CannotScrapeException("No XML button found on page")
    xml_url = urljoin(bill_or_url, xml_button[0].get('href'))

    resp2 = requests.get(xml_url)
    return lxml.etree.fromstring(resp2.content)

def get_plain_bill_text(bill_or_url) -> tuple[str, str]:
    bill_el = get_bill_text_xml(bill_or_url)
    body = bill_el.xpath('//Body')
    if not body:
        raise CannotScrapeException("Can't scrape the XML")
    return get_bill_summary(bill_el), ' '.join(body[0].itertext())

def get_bill_summary(bill_el) -> str:
    summary = bill_el.xpath('//Summary')[0]
    texts = []
    def _descend(tag):
        if tag.tag == 'TitleText':
            return
        if tag.tag == 'Provision':
            texts.append('\n')
        if tag.text:
            texts.append(tag.text.replace('\n', ''))
        for sub in tag.iterchildren():
            _descend(sub)
        if tag.tail:
            texts.append(tag.tail.replace('\n', ''))
    _descend(summary)
    return (' '.join(texts)).strip()
