import haikufinder

from django.core.exceptions import ValidationError

from parliament.hansards.models import Statement
from .models import Haiku

def gen_haiku(qs):
    for statement in qs:
        for haiku in haikufinder.find_haikus(statement.text_plain()):
            h = Haiku(line1=haiku[0], line2=haiku[1], line3=haiku[2])
            h.set_statement(statement)
            try:
                h.full_clean()
                h.save()
                try:
                    print(h)
                except:
                    print('unprintable')
            except ValidationError as e:
                print(e)