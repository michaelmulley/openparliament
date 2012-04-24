import os
import sys

from parliament.core import datautil

reload(sys)

sys.setdefaultencoding('utf8')
sys.stdout = os.fdopen(sys.stdout.fileno(), 'w', 0)  # unbuffered stdout

datautil.parse_all_hansards()
