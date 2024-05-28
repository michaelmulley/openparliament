# -*- coding: utf-8 -*-


from django.db import migrations, models
import datetime


class Migration(migrations.Migration):

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='User',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('email', models.EmailField(unique=True, max_length=254, db_index=True)),
                ('email_bouncing', models.BooleanField(default=False)),
                ('created', models.DateTimeField(default=datetime.datetime.now)),
                ('last_login', models.DateTimeField(null=True, blank=True)),
                ('json_data', models.TextField(default=b'{}')),
            ],
        ),
    ]
