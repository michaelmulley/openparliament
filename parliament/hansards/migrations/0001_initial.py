# -*- coding: utf-8 -*-


from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('bills', '0001_initial'),
        ('core', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='Document',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('document_type', models.CharField(db_index=True, max_length=1, choices=[(b'D', b'Debate'), (b'E', b'Committee Evidence')])),
                ('date', models.DateField(null=True, blank=True)),
                ('number', models.CharField(max_length=6, blank=True)),
                ('source_id', models.IntegerField(unique=True, db_index=True)),
                ('most_frequent_word', models.CharField(max_length=20, blank=True)),
                ('wordcloud', models.ImageField(null=True, upload_to=b'autoimg/wordcloud', blank=True)),
                ('downloaded', models.BooleanField(default=False, help_text=b'Has the source data been downloaded?')),
                ('skip_parsing', models.BooleanField(default=False, help_text=b"Don't try to parse this, presumably because of errors in the source.")),
                ('public', models.BooleanField(default=False, verbose_name=b'Display on site?')),
                ('multilingual', models.BooleanField(default=False, verbose_name=b'Content parsed in both languages?')),
                ('session', models.ForeignKey(on_delete=models.CASCADE, to='core.Session')),
            ],
            options={
                'ordering': ('-date',),
            },
        ),
        migrations.CreateModel(
            name='OldSequenceMapping',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('sequence', models.PositiveIntegerField()),
                ('slug', models.SlugField(max_length=100)),
                ('document', models.ForeignKey(on_delete=models.CASCADE, to='hansards.Document')),
            ],
        ),
        migrations.CreateModel(
            name='Statement',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('time', models.DateTimeField(db_index=True)),
                ('source_id', models.CharField(max_length=15, blank=True)),
                ('slug', models.SlugField(max_length=100, blank=True)),
                ('urlcache', models.CharField(max_length=200, blank=True)),
                ('h1_en', models.CharField(max_length=300, blank=True)),
                ('h2_en', models.CharField(max_length=300, blank=True)),
                ('h3_en', models.CharField(max_length=300, blank=True)),
                ('h1_fr', models.CharField(max_length=400, blank=True)),
                ('h2_fr', models.CharField(max_length=400, blank=True)),
                ('h3_fr', models.CharField(max_length=400, blank=True)),
                ('who_en', models.CharField(max_length=300, blank=True)),
                ('who_fr', models.CharField(max_length=500, blank=True)),
                ('who_hocid', models.PositiveIntegerField(db_index=True, null=True, blank=True)),
                ('who_context_en', models.CharField(max_length=300, blank=True)),
                ('who_context_fr', models.CharField(max_length=500, blank=True)),
                ('content_en', models.TextField()),
                ('content_fr', models.TextField(blank=True)),
                ('sequence', models.IntegerField(db_index=True)),
                ('wordcount', models.IntegerField()),
                ('wordcount_en', models.PositiveSmallIntegerField(help_text=b'# words originally spoken in English', null=True)),
                ('procedural', models.BooleanField(default=False, db_index=True)),
                ('written_question', models.CharField(blank=True, max_length=1, choices=[(b'Q', b'Question'), (b'R', b'Response')])),
                ('statement_type', models.CharField(max_length=35, blank=True)),
                ('bills', models.ManyToManyField(to='bills.Bill', blank=True)),
                ('document', models.ForeignKey(on_delete=models.CASCADE, to='hansards.Document')),
                ('member', models.ForeignKey(on_delete=models.CASCADE, blank=True, to='core.ElectedMember', null=True)),
                ('mentioned_politicians', models.ManyToManyField(related_name='statements_with_mentions', to='core.Politician', blank=True)),
                ('politician', models.ForeignKey(on_delete=models.CASCADE, blank=True, to='core.Politician', null=True)),
            ],
            options={
                'ordering': ('sequence',),
            },
        ),
        migrations.AlterUniqueTogether(
            name='statement',
            unique_together=set([('document', 'slug')]),
        ),
        migrations.AlterUniqueTogether(
            name='oldsequencemapping',
            unique_together=set([('document', 'sequence')]),
        ),
    ]
