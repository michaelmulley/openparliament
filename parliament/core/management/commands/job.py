from optparse import make_option
import traceback
import sys

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.core.mail import mail_admins

from parliament import jobs

class Command(BaseCommand):
    help = "Runs a job, which is a no-arguments function in the project's jobs.py"
    args = '[job name]'
    
    option_list = BaseCommand.option_list + (
        make_option('--pdb', action='store_true', dest='pdb', 
                    help='Launch into Python debugger on exception'),
    )
    
    def handle(self, jobname, **options):
        try:
            getattr(jobs, jobname)()
        except Exception, e:
            try:
                if options.get('pdb'):
                    try:
                        import pudb; pudb.post_mortem()
                    except ImportError:
                        import pdb; pdb.post_mortem()
                else:
                    tb = "\n".join(traceback.format_exception(*(sys.exc_info())))
                    mail_admins("Exception in job %s" % jobname, "\n".join(traceback.format_exception(*(sys.exc_info()))))
            except:
                print tb
            finally:
                raise e