from django.contrib.sitemaps import Sitemap
from parliament.core.models import Politician
from parliament.hansards.models import Document
from parliament.bills.models import Bill, VoteQuestion

class PoliticianSitemap(Sitemap):

    def items(self):
        return Politician.objects.elected()

class HansardSitemap(Sitemap):
    
    def items(self):
        return Document.objects.all()
        
    def lastmod(self, obj):
        return obj.date
        
class BillSitemap(Sitemap):
    
    def items(self):
        return Bill.objects.all()
        
class VoteQuestionSitemap(Sitemap):
    def items(self):
        return VoteQuestion.objects.all()
        
    def lastmod(self, obj):
        return obj.date
        
sitemaps = {
    'politician': PoliticianSitemap,
    'hansard': HansardSitemap,
    'bill': BillSitemap,
    'votequestion': VoteQuestionSitemap,
}