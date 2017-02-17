from django.conf.urls import url, include

from parliament.hansards.views import (index, by_year, by_month, hansard,
    hansard_analysis, hansard_statement, debate_permalink, document_cache)

urlpatterns = [
    url(r'^$', index, name='debates'),
    url(r'^(?P<year>\d{4})/$', by_year, name='debates_by_year'),
    url(r'^(?P<year>\d{4})/(?P<month>\d{1,2})/', include([
        url(r'^$', by_month),
        url(r'^(?P<day>\d{1,2})/$', hansard, name='debate'),
        url(r'^(?P<day>\d{1,2})/text-analysis/$', hansard_analysis, name='debate_analysis'),
        url(r'^(?P<day>\d{1,2})/(?P<slug>[a-zA-Z0-9-]+)/$', hansard_statement, name="debate"),
        url(r'^(?P<day>\d{1,2})/(?P<slug>[a-zA-Z0-9-]+)/only/$',
            debate_permalink, name="hansard_statement_only"),

    ])),
    url(r'^(?P<document_id>\d+)/local/(?P<language>en|fr)/$', document_cache),
]
