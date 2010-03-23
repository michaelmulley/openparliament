import re, unicodedata, decimal
import datetime

from BeautifulSoup import NavigableString

def countWords(text):
    # very quick-n-dirty for now
    return text.count(' ') + int(text.count("\n") / 2) + 1

def time(hour, minute):
    if hour >= 24:
        hour = hour % 24 # no, really. the house of commons is so badass they meet at 25 o'clock
    return datetime.time(hour=hour, minute=minute)

def normalizeHansardURL(u):
    docid = re.search(r'DocId=(\d+)', u).group(1)
    parl = re.search(r'Parl=(\d+)', u).group(1)
    ses = re.search(r'Ses=(\d+)', u).group(1)
    return 'http://www2.parl.gc.ca/HousePublications/Publication.aspx?Language=E&Mode=1&Parl=%s&Ses=%s&DocId=%s' % (parl, ses, docid)

def removeAccents(str):
    nkfd_form = unicodedata.normalize('NFKD', unicode(str))
    return u"".join([c for c in nkfd_form if not unicodedata.combining(c)])
    
def stripHonorific(s):
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
    
def slugify(s):
    s = re.sub(r'[^a-zA-Z]', '-', removeAccents(s.strip().lower()))
    return re.sub(r'--+', '-', s)

def normalizeName(s):
    return tameWhitespace(removeAccents(stripHonorific(s).lower()))

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