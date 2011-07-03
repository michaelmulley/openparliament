from collections import defaultdict
from heapq import nlargest
from operator import itemgetter
import random
import re
from cStringIO import StringIO
import subprocess

from django.conf import settings

r_punctuation = re.compile(r"[^\s\w0-9'-]", re.UNICODE)
r_whitespace = re.compile(r'\s+')

def text_token_iterator(text, statement_separator=None):
    text = r_punctuation.sub('', text.lower())
    for word in r_whitespace.split(text):
        yield word
    if statement_separator:
        yield statement_separator

def statements_token_iterator(statements, statement_separator=None):
    for statement in statements:
        for x in text_token_iterator(statement.text_plain(), statement_separator):
            yield x

            
STOPWORDS = frozenset(["i", "me", "my", "myself", "we", "our", "ours", "ourselves", "you", "your", "yours", "yourself", "yourselves", "he", "him", "his", "himself", "she", "her", "hers", "herself", "it", "its", "itself", "they", "them", "their", "theirs", "themselves", "what", "which", "who", "whom", "this", "that", "these", "those", "am", "is", "are", "was", "were", "be", "been", "being", "have", "has", "had", "having", "do", "does", "did", "doing", "a", "an", "the", "and", "but", "if", "or", "because", "as", "until", "while", "of", "at", "by", "for", "with", "about", "against", "between", "into", "through", "during", "before", "after", "above", "below", "to", "from", "up", "down", "in", "out", "on", "off", "over", "under", "again", "further", "then", "once", "here", "there", "when", "where", "why", "how", "all", "any", "both", "each", "few", "more", "most", "other", "some", "such", "no", "nor", "not", "only", "own", "same", "so", "than", "too", "very", "s", "t", "can", "will", "just", "don", "should", "now", # this is the nltk stopwords list
"it's", "we're", "we'll", "they're", "can't", "won't", "isn't", "don't", "he's", "she's", "i'm", "aren't",
"government", "house", 'committee', 'would', 'speaker', 'motion', 'mr', 'mrs', 'ms', 'member', 'minister', 'canada', 'members',
'time', 'prime', 'one', 'parliament', 'us', 'bill', 'act', 'like', 'canadians', 'people', 'said', 'want', 'could', 'issue',
'today', 'hon', 'order', 'party', 'canadian', 'think', 'also', 'new', 'get', 'many', 'say', 'look', 'country', 'legislation',
'law', 'department', 'two', 'one', 'day', 'days', ])
            
class WordCounter(dict):
    
    def __init__(self, stopwords=STOPWORDS):
        self.stopwords = stopwords
        super(WordCounter, self).__init__(self)
    
    def __missing__(self, key):
        return 0
        
    def __setitem__(self, key, value):
        if key not in self.stopwords:
            super(WordCounter, self).__setitem__(key, value)

    def most_common(self, n=None):    
        if n is None:
            return sorted(self.iteritems(), key=itemgetter(1), reverse=True)
        return nlargest(n, self.iteritems(), key=itemgetter(1))
        
class WordAndAttributeCounter(object):
    
    def __init__(self, stopwords=STOPWORDS):
        self.counter = defaultdict(WordAttributeCount)
        self.stopwords = stopwords
        
    def add(self, word, attribute):
        if word not in self.stopwords and len(word) > 2:
            self.counter[word].add(attribute)
        
    def most_common(self, n=None):    
        if n is None:
            return sorted(self.counter.iteritems(), key=lambda x: x[1].count, reverse=True)
        return nlargest(n, self.counter.iteritems(), key=lambda x: x[1].count)
        
class WordAttributeCount(object):
    
    __slots__ = ('count', 'attributes')
    
    def __init__(self):
        self.attributes = defaultdict(int)
        self.count = 0
        
    def add(self, attribute):
        self.attributes[attribute] += 1
        self.count += 1
        
    def winning_attribute(self):
        return nlargest(1, self.attributes.iteritems(), key=itemgetter(1))[0][0]
        
def most_frequent_word(qs):
    counter = WordCounter()
    for word in statements_token_iterator(qs):
        counter[word] += 1
    try:
        return counter.most_common(1)[0][0]
    except IndexError:
        return None

PARTY_COLOURS = {
    'liberal': 'f51c18',
    'bloc': '18d7f5',
    'cpc': '1883f5',
    'alliance': '1883f5',
    'canadian-alliance': '1883f5',
    'conservative': '1883f5',
    'progressive-conservative': '1883f5',
    'pc': '1883f5',
    'reform': '3ae617',
    'ndp': 'f58a18',
}
def statements_to_cloud_by_party(qs):
    counter = WordAndAttributeCounter()
    for statement in qs:
        if statement.member and not statement.procedural:
            party = statement.member.party.slug.lower()
        else:
            party = None
        for word in text_token_iterator(statement.text_plain()):
            counter.add(word, party)
    result = [(x[0], unicode(x[1].count), PARTY_COLOURS.get(x[1].winning_attribute(), '777777'))
        for x in counter.most_common(100)]
    return _call_wordcloud_generator(result)

CLOUD_COLOURS = ['870920', 'CF3A16', 'FF8420', '87731F', '0F5C54']
def statements_to_cloud(statements):
    counter = WordCounter()
    for word in statements_token_iterator(statements):
        counter[word] += 1
    result = [(x[0], unicode(x[1]), random.choice(CLOUD_COLOURS))
        for x in counter.most_common(60)]
    return _call_wordcloud_generator(result)

def _call_wordcloud_generator(rows):
    """Each row should be a tuple of word, weight, color."""
    cmd_input = "\n".join(["word\tweight\tcolor"] + [u"\t".join(x) for x in rows]).encode('utf8')
    p = subprocess.Popen(settings.PARLIAMENT_WORDCLOUD_COMMAND, stdin=subprocess.PIPE, stdout=subprocess.PIPE)
    return p.communicate(cmd_input)[0]
    