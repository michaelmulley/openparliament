# -*- coding: utf-8 -*-


from django.db import migrations, models
import datetime


class Migration(migrations.Migration):

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='ElectedMember',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('start_date', models.DateField(db_index=True)),
                ('end_date', models.DateField(db_index=True, null=True, blank=True)),
            ],
        ),
        migrations.CreateModel(
            name='InternalXref',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('text_value', models.CharField(db_index=True, max_length=250, blank=True)),
                ('int_value', models.IntegerField(db_index=True, null=True, blank=True)),
                ('target_id', models.IntegerField(db_index=True)),
                ('schema', models.CharField(max_length=15, db_index=True)),
            ],
        ),
        migrations.CreateModel(
            name='Party',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('name', models.CharField(max_length=100)),
                ('slug', models.CharField(max_length=10, blank=True)),
                ('short_name', models.CharField(max_length=100, blank=True)),
            ],
            options={
                'ordering': ('name',),
                'verbose_name_plural': 'Parties',
            },
        ),
        migrations.CreateModel(
            name='Politician',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('name', models.CharField(max_length=100)),
                ('name_given', models.CharField(max_length=50, verbose_name=b'Given name', blank=True)),
                ('name_family', models.CharField(max_length=50, verbose_name=b'Family name', blank=True)),
                ('dob', models.DateField(null=True, blank=True)),
                ('gender', models.CharField(blank=True, max_length=1, choices=[(b'M', b'Male'), (b'F', b'Female')])),
                ('headshot', models.ImageField(null=True, upload_to=b'polpics', blank=True)),
                ('slug', models.CharField(db_index=True, max_length=30, blank=True)),
            ],
            options={
                'ordering': ('name',),
                'abstract': False,
            },
        ),
        migrations.CreateModel(
            name='PoliticianInfo',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('schema', models.CharField(max_length=40, db_index=True)),
                ('value', models.TextField()),
                ('politician', models.ForeignKey(on_delete=models.CASCADE, to='core.Politician')),
            ],
        ),
        migrations.CreateModel(
            name='Riding',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('name', models.CharField(max_length=200)),
                ('name_fr', models.CharField(max_length=200, blank=True)),
                ('province', models.CharField(max_length=2, choices=[(b'AB', b'Alberta'), (b'BC', b'B.C.'), (b'SK', b'Saskatchewan'), (b'MB', b'Manitoba'), (b'ON', b'Ontario'), (b'QC', b'Qu\xc3\xa9bec'), (b'NB', b'New Brunswick'), (b'NS', b'Nova Scotia'), (b'PE', b'P.E.I.'), (b'NL', b'Newfoundland & Labrador'), (b'YT', b'Yukon'), (b'NT', b'Northwest Territories'), (b'NU', b'Nunavut')])),
                ('slug', models.CharField(unique=True, max_length=60, db_index=True)),
                ('edid', models.IntegerField(db_index=True, null=True, blank=True)),
                ('current', models.BooleanField(default=False)),
            ],
            options={
                'ordering': ('province', 'name'),
            },
        ),
        migrations.CreateModel(
            name='Session',
            fields=[
                ('id', models.CharField(max_length=4, serialize=False, primary_key=True)),
                ('name', models.CharField(max_length=100)),
                ('start', models.DateField()),
                ('end', models.DateField(null=True, blank=True)),
                ('parliamentnum', models.IntegerField(null=True, blank=True)),
                ('sessnum', models.IntegerField(null=True, blank=True)),
            ],
            options={
                'ordering': ('-start',),
            },
        ),
        migrations.CreateModel(
            name='SiteNews',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('date', models.DateTimeField(default=datetime.datetime.now)),
                ('title', models.CharField(max_length=200)),
                ('text', models.TextField()),
                ('active', models.BooleanField(default=True)),
            ],
            options={
                'ordering': ('-date',),
            },
        ),
        migrations.AddField(
            model_name='electedmember',
            name='party',
            field=models.ForeignKey(on_delete=models.CASCADE, to='core.Party'),
        ),
        migrations.AddField(
            model_name='electedmember',
            name='politician',
            field=models.ForeignKey(on_delete=models.CASCADE, to='core.Politician'),
        ),
        migrations.AddField(
            model_name='electedmember',
            name='riding',
            field=models.ForeignKey(on_delete=models.CASCADE, to='core.Riding'),
        ),
        migrations.AddField(
            model_name='electedmember',
            name='sessions',
            field=models.ManyToManyField(to='core.Session'),
        ),
    ]
