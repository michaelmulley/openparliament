from django.conf import settings
from django.test.simple import DjangoTestSuiteRunner

class TestSuiteRunner(DjangoTestSuiteRunner):
    """By default, runs tests only for our code, not third-party apps."""
        
    def run_tests(self, test_labels, **kwargs):
        if not test_labels:
            test_labels = [app.split('.')[-1] 
                for app in settings.INSTALLED_APPS
                if app.startswith(settings.TEST_APP_PREFIX)]
        print "Running tests for: %s" % ', '.join(test_labels)        
        super(TestSuiteRunner, self).run_tests(test_labels, **kwargs)