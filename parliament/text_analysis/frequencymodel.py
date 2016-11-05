#coding: utf-8

from collections import defaultdict
from heapq import nlargest
import itertools
from operator import itemgetter
import re

STOPWORDS = frozenset(["i", "me", "my", "myself", "we", "our", "ours", "ourselves",
    "you", "your", "yours", "yourself", "yourselves", "he", "him", "his", "himself",
    "she", "her", "hers", "herself", "it", "its", "itself", "they", "them", "their",
    "theirs", "themselves", "what", "which", "who", "whom", "this", "that", "these",
    "those", "am", "is", "are", "was", "were", "be", "been", "being", "have", "has",
    "had", "having", "do", "does", "did", "doing", "a", "an", "the", "and", "but", "if",
    "or", "because", "as", "until", "while", "of", "at", "by", "for", "with", "about",
    "against", "between", "into", "through", "during", "before", "after", "above",
    "below", "to", "from", "up", "down", "in", "out", "on", "off", "over", "under",
    "again", "further", "then", "once", "here", "there", "when", "where", "why", "how",
    "all", "any", "both", "each", "few", "more", "most", "other", "some", "such", "no",
    "nor", "not", "only", "own", "same", "so", "than", "too", "very", "s", "t", "can",
    "will", "just", "don", "should", "now", # this is the nltk stopwords list
    "it's", "we're", "we'll", "they're", "can't", "won't", "isn't", "don't", "he's",
    "she's", "i'm", "aren't", "government", "house", 'committee', 'would', 'speaker',
    'motion', 'mr', 'mrs', 'ms', 'member', 'minister', 'canada', 'members', 'time',
    'prime', 'one', 'parliament', 'us', 'bill', 'act', 'like', 'canadians', 'people',
    'said', 'want', 'could', 'issue', 'today', 'hon', 'order', 'party', 'canadian',
    'think', 'also', 'new', 'get', 'many', 'say', 'look', 'country', 'legislation',
    'law', 'department', 'two', 'day', 'days', 'madam', 'must', "that's", "okay",
    "thank", "really", "much", "there's", 'yes', 'no'
])


r_punctuation = re.compile(r"[^\s\w0-9'’—-]", re.UNICODE)
r_whitespace = re.compile(r'[\s—]+')

def text_token_iterator(text):
    text = r_punctuation.sub('', text.lower())
    for word in r_whitespace.split(text):
        yield word

def statements_token_iterator(statements, statement_separator=None):
    for statement in statements:
        for x in text_token_iterator(statement.text_plain()):
            yield x
        if statement_separator is not None:
            yield statement_separator

def ngram_iterator(tokens, n=2):
    sub_iterators = itertools.tee(tokens, n)
    for i, iterator in enumerate(sub_iterators[1:]):
        for x in xrange(i + 1):
            # Advance the iterator i+1 times
            next(iterator, None)
    for words in itertools.izip(*sub_iterators):
        yield ' '.join(words)


class FrequencyModel(dict):
    """
    Given an iterable of strings, constructs an object mapping each string
    to the probability that a randomly chosen string will be it (that is, 
    # of occurences of string / # total number of items).
    """

    def __init__(self, items, min_count=1):
        counts = defaultdict(int)
        total_count = 0
        for item in items:
            if len(item) > 2 and '/' not in item:
                counts[item] += 1
                total_count += 1
        self.count = total_count
        total_count = float(total_count)
        self.update(
            (k, v / total_count) for k, v in counts.iteritems() if v >= min_count
        )

    def __missing__(self, key):
        return float()

    def diff(self, other):
        """
        Given another FrequencyModel, returns a FrequencyDiffResult containing the difference
        between the probability of a given word appears in this FrequencyModel vs the other
        background model.
        """
        r = FrequencyDiffResult()
        for k, v in self.iteritems():
            if k not in STOPWORDS:
                r[k] = self[k] - other[k]
        return r

    def item_count(self, key):
        return round(self[key] * self.count)

    def most_common(self, n=None):
        if n is None:
            return sorted(self.iteritems(), key=itemgetter(1), reverse=True)
        return nlargest(n, self.iteritems(), key=itemgetter(1))

    @classmethod
    def from_statement_qs(cls, qs, ngram=1, min_count=1):
        it = statements_token_iterator(qs, statement_separator='/')
        if ngram > 1:
            it = ngram_iterator(it, ngram)
        return cls(it, min_count=min_count)

class FrequencyDiffResult(dict):

    def __missing__(self, key):
        return float()

    def most_common(self, n=10):
        return nlargest(n, self.iteritems(), key=itemgetter(1))

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

