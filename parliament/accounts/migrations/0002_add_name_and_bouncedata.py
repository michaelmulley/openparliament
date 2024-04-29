# -*- coding: utf-8 -*-


from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='user',
            name='email_bounce_reason',
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name='user',
            name='name',
            field=models.CharField(max_length=250, blank=True),
        ),
    ]
