# -*- coding: utf-8 -*-


from django.db import migrations, models
import datetime


class Migration(migrations.Migration):

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='TextAnalysis',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('key', models.CharField(help_text=b'A URL to a view that calculates this object', max_length=150, db_index=True)),
                ('lang', models.CharField(max_length=2)),
                ('updated', models.DateTimeField(default=datetime.datetime.now)),
                ('expires', models.DateTimeField(null=True, blank=True)),
                ('probability_data_json', models.TextField()),
            ],
            options={
                'verbose_name_plural': 'Text analyses',
            },
        ),
        migrations.AlterUniqueTogether(
            name='textanalysis',
            unique_together=set([('key', 'lang')]),
        ),
    ]
