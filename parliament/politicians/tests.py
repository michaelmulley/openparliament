from django.test import TestCase

from parliament.core.models import Politician

class SmokeTests(TestCase):
    
    fixtures = ['parties', 'ridings', 'sessions', 'politicians']
    
    def test_pages(self):
        
        self.assertContains(self.client.get('/politicians/'), 'Current MPs')
        
        assert self.client.get('/politicians/former/').status_code == 200
        
        self.assertContains(self.client.get('/politicians/hedy-fry/'), 'Vancouver Centre')
        
        assert self.client.get('/politicians/frank-mckenna/').status_code == 404
        
        rona = Politician.objects.get_by_name('Rona Ambrose')
        
        self.assertContains(self.client.get('/politicians/%s/rss/statements/' % rona.id), 'Rona ')
        self.assertContains(self.client.get('/politicians/%s/rss/activity/' % rona.id), 'Rona ')