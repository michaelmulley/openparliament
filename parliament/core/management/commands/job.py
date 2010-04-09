from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from parliament import jobs

class Command(BaseCommand):
    help = "Runs a job, which is a no-arguments function in the project's jobs.py"
    args = '[job name]'
    
    def handle(self, jobname, **kwargs):
        getattr(jobs, jobname)()
        return True