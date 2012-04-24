from django.views import generic


class ListView(generic.ListView):

    title = None

    def get_context_data(self, **kwargs):
        ctx = super(ListView, self).get_context_data(**kwargs)
        ctx['title'] = self.title
        return ctx
