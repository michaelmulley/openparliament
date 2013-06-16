import re
import urllib2

import lxml.html
from lxml.html.clean import clean

from parliament.imports import CannotScrapeException


def get_bill_text_element(bill_or_url):
    """Given a Bill object or URL to a full-text page on parl.gc.ca,
    returns an lxml Element object for the container div of the full
    bill text."""

    if hasattr(bill_or_url, 'get_billtext_url'):
        bill_or_url = bill_or_url.get_billtext_url(single_page=True)

    resp = urllib2.urlopen(bill_or_url)
    root = lxml.html.parse(resp).getroot()

    is_two_columns = not root.cssselect('div.HeaderMenuLinks .HeaderLink a')

    div = root.cssselect('div#publicationContent')[0]

    if is_two_columns:
        # Remove the second column of text (the French text)
        # I haven't made this multilingual since it's highly,
        # highly hacky, and it may well be deleting English text
        # anyway in some instances
        for tr in div.xpath('table/tr'):
            cells = tr.xpath('td')
            if len(cells) in (3, 5, 7):
                cells[2].drop_tree()

    return div


def get_plain_bill_text(bill_or_url):
    content = get_bill_text_element(bill_or_url)
    clean(content)
    text = content.text_content()
    text = re.sub(r'\n[\s\n]+', '\n', text.replace('\t', ' ').replace('\r', '')).strip()
    text = re.sub(r'  +', ' ', text)
    if len(text) < 200:
        raise CannotScrapeException
    return text
