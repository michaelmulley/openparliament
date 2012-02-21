from django.http import HttpResponsePermanentRedirect
from django.shortcuts import get_object_or_404

from parliament.hansards.models import Document, OldSequenceMapping

def hansard_redirect(request, hansard_id, sequence=None):
    doc = get_object_or_404(Document.hansards, pk=hansard_id)
    url = doc.get_absolute_url(pretty=True)

    if sequence:
        try:
            map = OldSequenceMapping.objects.get(document=doc, sequence=sequence)
            sequence = map.slug
        except OldSequenceMapping.DoesNotExist:
            pass
        url += '%s/' % sequence

    return HttpResponsePermanentRedirect(url)