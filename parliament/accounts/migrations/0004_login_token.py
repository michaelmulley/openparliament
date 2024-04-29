# -*- coding: utf-8 -*-


from django.db import migrations, models
import datetime
import parliament.accounts.models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0003_rename_data'),
    ]

    operations = [
        migrations.CreateModel(
            name='LoginToken',
            fields=[
                ('token', models.CharField(default=parliament.accounts.models._random_token, max_length=40, serialize=False, primary_key=True)),
                ('email', models.EmailField(max_length=254)),
                ('created', models.DateTimeField(default=datetime.datetime.now)),
                ('requesting_ip', models.GenericIPAddressField()),
                ('used', models.BooleanField(default=False)),
                ('login_ip', models.GenericIPAddressField(null=True, blank=True)),
                ('post_login_url', models.TextField(blank=True)),
            ],
        ),
    ]
