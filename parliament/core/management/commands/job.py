import traceback
import sys

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.core.mail import mail_admins

from parliament import jobs

class Command(BaseCommand):
    help = "Runs a job, which is a no-arguments function in the project's jobs.py"
    args = '[job name]'
    
    def handle(self, jobname, **kwargs):
        try:
            getattr(jobs, jobname)()
        except Exception, e:
            try:
                tb = "\n".join(traceback.format_exception(*(sys.exc_info())))
                mail_admins("Exception in job %s" % jobname, "\n".join(traceback.format_exception(*(sys.exc_info()))))
            except:
                print tb
            finally:
                raise e