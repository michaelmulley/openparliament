
from parliament.committees.models import Committee
from parliament.core.generic import ListView
from parliament.core.models import Session

committee_list = ListView.as_view(
    template_name="committees/committee_list.html",
    title="Parliamentary Committees",
    queryset=Committee.objects.filter(active=True, parent__isnull=True)
)

def committee(request, commitee_id=None, acronym=None):
    pass
    
def activity(request, committee_id, activity_id):
    pass
    
