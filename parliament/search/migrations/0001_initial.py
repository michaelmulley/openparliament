# -*- coding: utf-8 -*-


from django.db import migrations, models
import datetime


class Migration(migrations.Migration):

    dependencies = [
        ('contenttypes', '0002_remove_content_type_name'),
    ]

    operations = [
        migrations.CreateModel(
            name='IndexingTask',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('action', models.CharField(max_length=10)),
                ('identifier', models.CharField(max_length=100)),
                ('timestamp', models.DateTimeField(default=datetime.datetime.now)),
                ('object_id', models.CharField(max_length=20, blank=True)),
                ('content_type', models.ForeignKey(on_delete=models.CASCADE, blank=True, to='contenttypes.ContentType', null=True)),
            ],
        ),
    ]
