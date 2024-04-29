# -*- coding: utf-8 -*-


from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='Activity',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('date', models.DateField(db_index=True)),
                ('variety', models.CharField(max_length=15)),
                ('payload', models.TextField()),
                ('guid', models.CharField(unique=True, max_length=50, db_index=True)),
                ('active', models.BooleanField(default=True, db_index=True)),
                ('politician', models.ForeignKey(on_delete=models.CASCADE, to='core.Politician')),
            ],
            options={
                'ordering': ('-date', '-id'),
                'verbose_name_plural': 'Activities',
            },
        ),
    ]
