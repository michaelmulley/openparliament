# -*- coding: utf-8 -*-


from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('hansards', '0001_initial'),
        ('bills', '0001_initial'),
        ('committees', '0001_initial'),
        ('core', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='votequestion',
            name='context_statement',
            field=models.ForeignKey(on_delete=django.db.models.deletion.SET_NULL, blank=True, to='hansards.Statement', null=True),
        ),
        migrations.AddField(
            model_name='votequestion',
            name='session',
            field=models.ForeignKey(on_delete=models.CASCADE, to='core.Session'),
        ),
        migrations.AddField(
            model_name='partyvote',
            name='party',
            field=models.ForeignKey(on_delete=models.CASCADE, to='core.Party'),
        ),
        migrations.AddField(
            model_name='partyvote',
            name='votequestion',
            field=models.ForeignKey(on_delete=models.CASCADE, to='bills.VoteQuestion'),
        ),
        migrations.AddField(
            model_name='membervote',
            name='member',
            field=models.ForeignKey(on_delete=models.CASCADE, to='core.ElectedMember'),
        ),
        migrations.AddField(
            model_name='membervote',
            name='politician',
            field=models.ForeignKey(on_delete=models.CASCADE, to='core.Politician'),
        ),
        migrations.AddField(
            model_name='membervote',
            name='votequestion',
            field=models.ForeignKey(on_delete=models.CASCADE, to='bills.VoteQuestion'),
        ),
        migrations.AddField(
            model_name='billtext',
            name='bill',
            field=models.ForeignKey(on_delete=models.CASCADE, to='bills.Bill'),
        ),
        migrations.AddField(
            model_name='billinsession',
            name='bill',
            field=models.ForeignKey(on_delete=models.CASCADE, to='bills.Bill'),
        ),
        migrations.AddField(
            model_name='billinsession',
            name='debates',
            field=models.ManyToManyField(to='hansards.Document', through='bills.BillEvent'),
        ),
        migrations.AddField(
            model_name='billinsession',
            name='session',
            field=models.ForeignKey(on_delete=models.CASCADE, to='core.Session'),
        ),
        migrations.AddField(
            model_name='billinsession',
            name='sponsor_member',
            field=models.ForeignKey(on_delete=models.CASCADE, blank=True, to='core.ElectedMember', null=True),
        ),
        migrations.AddField(
            model_name='billinsession',
            name='sponsor_politician',
            field=models.ForeignKey(on_delete=models.CASCADE, blank=True, to='core.Politician', null=True),
        ),
        migrations.AddField(
            model_name='billevent',
            name='bis',
            field=models.ForeignKey(on_delete=models.CASCADE, to='bills.BillInSession'),
        ),
        migrations.AddField(
            model_name='billevent',
            name='committee_meetings',
            field=models.ManyToManyField(to='committees.CommitteeMeeting', blank=True),
        ),
        migrations.AddField(
            model_name='billevent',
            name='debate',
            field=models.ForeignKey(on_delete=django.db.models.deletion.SET_NULL, blank=True, to='hansards.Document', null=True),
        ),
        migrations.AddField(
            model_name='bill',
            name='sessions',
            field=models.ManyToManyField(to='core.Session', through='bills.BillInSession'),
        ),
        migrations.AddField(
            model_name='bill',
            name='sponsor_member',
            field=models.ForeignKey(on_delete=models.CASCADE, blank=True, to='core.ElectedMember', null=True),
        ),
        migrations.AddField(
            model_name='bill',
            name='sponsor_politician',
            field=models.ForeignKey(on_delete=models.CASCADE, blank=True, to='core.Politician', null=True),
        ),
        migrations.AlterUniqueTogether(
            name='partyvote',
            unique_together=set([('votequestion', 'party')]),
        ),
    ]
