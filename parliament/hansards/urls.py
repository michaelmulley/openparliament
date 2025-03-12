from django.urls import re_path, include

from parliament.hansards.views import (index, by_year, by_month, hansard,
    hansard_analysis, hansard_statement, debate_permalink, document_cache,
    hansard_ourcommons_redirect)

urlpatterns = [
    re_path(r'^$', index, name='debates'),
    re_path(r'^(?P<year>\d{4})/$', by_year, name='debates_by_year'),
    re_path(r'^(?P<year>\d{4})/(?P<month>\d{1,2})/', include([
        re_path(r'^$', by_month),
        re_path(r'^(?P<day>\d{1,2})/$', hansard, name='debate'),
        re_path(r'^(?P<day>\d{1,2})/text-analysis/$', hansard_analysis, name='debate_analysis'),
        re_path(r'^(?P<day>\d{1,2})/(?P<slug>[a-zA-Z0-9-]+)/$', hansard_statement, name="debate"),
        re_path(r'^(?P<day>\d{1,2})/(?P<slug>[a-zA-Z0-9-]+)/only/$',
            debate_permalink, name="hansard_statement_only"),
        re_path(r'^(?P<day>\d{1,2})/(?P<slug>[a-zA-Z0-9-]+)/parl-redirect/$',
                hansard_ourcommons_redirect),            

    ])),
    re_path(r'^(?P<document_id>\d+)/local/(?P<language>en|fr)/$', document_cache),
]
