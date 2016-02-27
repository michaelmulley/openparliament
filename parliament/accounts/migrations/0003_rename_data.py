# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models
import jsonfield.fields


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0002_add_name_and_bouncedata'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='user',
            name='json_data',
        ),
        migrations.AddField(
            model_name='user',
            name='data',
            field=jsonfield.fields.JSONField(default={}),
        ),
    ]
