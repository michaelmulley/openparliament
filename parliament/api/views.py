from django.shortcuts import get_object_or_404

from parliament.hansards.models import Document
from parliament.utils.views import JSONView

class LegacyAPIHansardListView(JSONView):

    wrap = False

    def get(self, request):
        return [{
            'note': "This API is deprecated. Please use the API documented on the openparliament.ca Developers page.",
            'date': str(h.date),
            'id': h.id,
            'number': h.number,
            'api_url': '/api/hansards/%s/' % h.id
        } for h in Document.debates.all()]

hansard_list = LegacyAPIHansardListView.as_view()

def _serialize_statement(s):
    v = {
        'url': s.get_absolute_url(),
        'heading': s.heading,
        'topic': s.topic,
        'time': str(s.time),
        'attribution': s.who,
        'text': s.text_plain()
    }
    if s.member:
        v['politician'] = {
            'id': s.member.politician.id,
            'member_id': s.member.id,
            'name': s.member.politician.name,
            'url': s.member.politician.get_absolute_url(),
            'party': s.member.party.short_name,
            'riding': str(s.member.riding),
        }
    return v

class LegacyAPIHansardView(JSONView):

    wrap = False

    def get(self, request, hansard_id):
        doc = get_object_or_404(Document, document_type='D', id=hansard_id)
        return {
            'date': str(doc.date),
            'url': doc.get_absolute_url(),
            'id': doc.id,
            'original_url': doc.url,
            'parliament': doc.session.parliamentnum,
            'session': doc.session.sessnum,
            'statements': [_serialize_statement(s)
                for s in doc.statement_set.all()
                    .order_by('sequence')
                    .select_related('member__politician', 'member__party', 'member__riding')]
        }

hansard = LegacyAPIHansardView.as_view()