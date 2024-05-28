# -*- coding: utf-8 -*-


from django.db import migrations, models
import datetime


class Migration(migrations.Migration):

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='Bill',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('name_en', models.TextField(blank=True)),
                ('name_fr', models.TextField(blank=True)),
                ('short_title_en', models.TextField(blank=True)),
                ('short_title_fr', models.TextField(blank=True)),
                ('number', models.CharField(max_length=10)),
                ('number_only', models.SmallIntegerField()),
                ('institution', models.CharField(db_index=True, max_length=1, choices=[(b'C', b'House'), (b'S', b'Senate')])),
                ('privatemember', models.NullBooleanField()),
                ('law', models.NullBooleanField()),
                ('status_date', models.DateField(db_index=True, null=True, blank=True)),
                ('status_code', models.CharField(max_length=50, blank=True)),
                ('added', models.DateField(default=datetime.date.today, db_index=True)),
                ('introduced', models.DateField(null=True, blank=True)),
                ('text_docid', models.IntegerField(help_text=b"The parl.gc.ca document ID of the latest version of the bill's text", null=True, blank=True)),
            ],
            options={
                'ordering': ('privatemember', 'institution', 'number_only'),
            },
        ),
        migrations.CreateModel(
            name='BillEvent',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('date', models.DateField(db_index=True)),
                ('source_id', models.PositiveIntegerField(unique=True, db_index=True)),
                ('institution', models.CharField(max_length=1, choices=[(b'C', b'House'), (b'S', b'Senate')])),
                ('status_en', models.TextField()),
                ('status_fr', models.TextField(blank=True)),
            ],
        ),
        migrations.CreateModel(
            name='BillInSession',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('legisinfo_id', models.PositiveIntegerField(db_index=True, null=True, blank=True)),
                ('introduced', models.DateField(db_index=True, null=True, blank=True)),
            ],
        ),
        migrations.CreateModel(
            name='BillText',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('docid', models.PositiveIntegerField(unique=True, db_index=True)),
                ('created', models.DateTimeField(default=datetime.datetime.now)),
                ('text_en', models.TextField()),
                ('text_fr', models.TextField(blank=True)),
            ],
        ),
        migrations.CreateModel(
            name='MemberVote',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('vote', models.CharField(max_length=1, choices=[(b'Y', b'Yes'), (b'N', b'No'), (b'P', b'Paired'), (b'A', b"Didn't vote")])),
                ('dissent', models.BooleanField(default=False, db_index=True)),
            ],
        ),
        migrations.CreateModel(
            name='PartyVote',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('vote', models.CharField(max_length=1, choices=[(b'Y', b'Yes'), (b'N', b'No'), (b'P', b'Paired'), (b'A', b"Didn't vote"), (b'F', b'Free vote')])),
                ('disagreement', models.FloatField(null=True)),
            ],
        ),
        migrations.CreateModel(
            name='VoteQuestion',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('number', models.PositiveIntegerField()),
                ('date', models.DateField(db_index=True)),
                ('description_en', models.TextField()),
                ('description_fr', models.TextField(blank=True)),
                ('result', models.CharField(max_length=1, choices=[(b'Y', b'Passed'), (b'N', b'Failed'), (b'T', b'Tie')])),
                ('yea_total', models.SmallIntegerField()),
                ('nay_total', models.SmallIntegerField()),
                ('paired_total', models.SmallIntegerField()),
                ('bill', models.ForeignKey(on_delete=models.CASCADE, blank=True, to='bills.Bill', null=True)),
            ],
            options={
                'ordering': ('-date', '-number'),
            },
        ),
    ]
