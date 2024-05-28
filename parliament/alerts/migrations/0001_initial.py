# -*- coding: utf-8 -*-


from django.db import migrations, models
import datetime


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0001_initial'),
        ('core', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='PoliticianAlert',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('email', models.EmailField(max_length=254, verbose_name=b'Your e-mail')),
                ('active', models.BooleanField(default=False)),
                ('created', models.DateTimeField(default=datetime.datetime.now)),
                ('politician', models.ForeignKey(on_delete=models.CASCADE, to='core.Politician')),
            ],
        ),
        migrations.CreateModel(
            name='SeenItem',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('item_id', models.CharField(max_length=400, db_index=True)),
                ('timestamp', models.DateTimeField(default=datetime.datetime.now)),
            ],
        ),
        migrations.CreateModel(
            name='Subscription',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('created', models.DateTimeField(default=datetime.datetime.now)),
                ('active', models.BooleanField(default=True)),
                ('last_sent', models.DateTimeField(null=True, blank=True)),
            ],
            options={
                'ordering': ['-created'],
            },
        ),
        migrations.CreateModel(
            name='Topic',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('query', models.CharField(unique=True, max_length=800)),
                ('created', models.DateTimeField(default=datetime.datetime.now)),
                ('last_checked', models.DateTimeField(null=True, blank=True)),
                ('last_found', models.DateTimeField(null=True, blank=True)),
            ],
        ),
        migrations.AddField(
            model_name='subscription',
            name='topic',
            field=models.ForeignKey(on_delete=models.CASCADE, to='alerts.Topic'),
        ),
        migrations.AddField(
            model_name='subscription',
            name='user',
            field=models.ForeignKey(on_delete=models.CASCADE, to='accounts.User'),
        ),
        migrations.AddField(
            model_name='seenitem',
            name='topic',
            field=models.ForeignKey(on_delete=models.CASCADE, to='alerts.Topic'),
        ),
        migrations.AlterUniqueTogether(
            name='subscription',
            unique_together=set([('topic', 'user')]),
        ),
        migrations.AlterUniqueTogether(
            name='seenitem',
            unique_together=set([('topic', 'item_id')]),
        ),
    ]
