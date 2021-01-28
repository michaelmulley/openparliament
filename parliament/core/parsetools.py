import re, unicodedata, decimal
import datetime

from BeautifulSoup import NavigableString

r_politicalpost = re.compile(r'(Minister|Leader|Secretary|Solicitor|Attorney|Speaker|Deputy |Soliciter|Chair |Parliamentary|President |for )')
r_honorific = re.compile(r'^(Mr\.?|Mrs\.?|Ms\.?|Miss\.?|Hon\.?|Right Hon\.|The|A|An\.?|Some|M\.|One|Santa|Acting|L\'hon\.|Assistant|Mme)\s(.+)$', re.DOTALL | re.UNICODE)
r_notamember = re.compile(r'^(The|A|Some|Acting|Santa|One|Assistant|An\.?|Le|La|Une|Des|Voices)')
r_mister = re.compile(r'^(Mr|Mrs|Ms|Miss|Hon|Right Hon|M|Mme)\.?\s+')
r_parens = re.compile(r'\s*\(.+\)\s*$')

def time(hour, minute):
    if hour >= 24:
        hour = hour % 24 # no, really. the house of commons is so badass they meet at 25 o'clock
    return datetime.time(hour=hour, minute=minute)

def time_to_datetime(hour, minute, date):
    """Given hour, minute, and a datetime.date, returns a datetime.datetime.

    Necessary to deal with the occasional wacky 25 o'clock timestamps in Hansard.
    """
    if hour < 24:
        return datetime.datetime.combine(date, datetime.time(hour=hour, minute=minute))
    else:
        return datetime.datetime.combine(
            date + datetime.timedelta(days=hour//24),
            datetime.time(hour=hour % 24, minute=minute)
        )

def normalizeHansardURL(u):
    docid = re.search(r'DocId=(\d+)', u).group(1)
    parl = re.search(r'Parl=(\d+)', u).group(1)
    ses = re.search(r'Ses=(\d+)', u).group(1)
    return 'http://www2.parl.gc.ca/HousePublications/Publication.aspx?Language=E&Mode=1&Parl=%s&Ses=%s&DocId=%s' % (parl, ses, docid)

def removeAccents(str):
    nkfd_form = unicodedata.normalize('NFKD', unicode(str))
    return u"".join([c for c in nkfd_form if not unicodedata.combining(c)])
    
def stripHonorific(s):
    for hon in ('The Honourable ', 'The Right Honourable ', 'The Rt. ', 'The '):
        s = s.replace(hon, '')
    return re.sub(r'^[A-Z][a-z]+\. ', '', s)
    
def isString(o):
    #return not hasattr(o, 'contents')
    return isinstance(o, NavigableString)
    
def titleIfNecessary(s):
    if not re.search(r'[a-z]', s):
        s = s.title()
    return s
    
r_hasText = re.compile(r'\S', re.UNICODE)
def getText(tag):
    return u''.join(tag.findAll(text=r_hasText))

r_extraWhitespace = re.compile(r'\s\s*', re.UNICODE)    
def tameWhitespace(s):
    return re.sub(r_extraWhitespace, u' ', s.replace(u"\n", u' '))
    
def sane_quotes(s):
    return s.replace('``', '"').replace("''", '"')
    
def slugify(s, allow_numbers=False):
    if allow_numbers:
        pattern = r'[^a-zA-Z0-9]'
    else:
        pattern = r'[^a-zA-Z]'
    s = re.sub(pattern, '-', removeAccents(s.strip().lower()))
    return re.sub(r'--+', '-', s)

def normalizeName(s):
    return tameWhitespace(removeAccents(stripHonorific(s).lower())).strip().replace(u"\u2019", "'")

def munge_date(date):
    if date.count('0000') > 0:
        return None
    elif date == '':
        return None
    elif date == u'&nbsp;':
        return None
    else:
        return date

def munge_decimal(num):
    try:
        return decimal.Decimal(num.replace(',', ''))
    except (ValueError, decimal.InvalidOperation):
        return decimal.Decimal(0)

def munge_int(num):
    num = re.sub(r'\D', '', num)
    if num == '':
        return None
    else:
        return int(num)

def munge_time(time):
    match = re.search(r'(\d\d:\d\d:\d\d)', time)
    if match:
        return match.group(1)
    else:
        return None

def munge_postcode (code):
    if code:
        code = code.upper()
        if len(code) == 6: # Add a space if there isn't one
            code = code[:3] + ' ' + code[3:]
        if re.search(r'^[ABCEGHJKLMNPRSTVXYZ]\d[A-Z] \d[A-Z]\d$', code):
            return code
    return None
    
def none_to_empty(s):
    return s if s is not None else ''
    
def etree_extract_text(elem):
    text = ''
    for x in elem.getiterator():
        if text and x.tag in ('Para', 'P', 'p'):
            text += "\n\n"
        text += (none_to_empty(x.text) + none_to_empty(x.tail)).replace("\n", ' ')
    return text