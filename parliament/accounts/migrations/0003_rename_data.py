# -*- coding: utf-8 -*-


from django.db import migrations, models


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
            field=models.JSONField(default=dict),
        ),
    ]
