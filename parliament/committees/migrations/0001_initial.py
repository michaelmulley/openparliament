# encoding: utf-8
import datetime
from south.db import db
from south.v2 import SchemaMigration
from django.db import models

class Migration(SchemaMigration):

    def forwards(self, orm):
        
        # Adding model 'Committee'
        db.create_table('committees_committee', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('name', self.gf('django.db.models.fields.TextField')()),
            ('short_name', self.gf('django.db.models.fields.TextField')()),
            ('slug', self.gf('django.db.models.fields.SlugField')(unique=True, max_length=50, db_index=True)),
            ('parent', self.gf('django.db.models.fields.related.ForeignKey')(blank=True, related_name='subcommittees', null=True, to=orm['committees.Committee'])),
        ))
        db.send_create_signal('committees', ['Committee'])

        # Adding model 'CommitteeInSession'
        db.create_table('committees_committeeinsession', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('session', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['core.Session'])),
            ('committee', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['committees.Committee'])),
            ('acronym', self.gf('django.db.models.fields.CharField')(max_length=5, db_index=True)),
        ))
        db.send_create_signal('committees', ['CommitteeInSession'])

        # Adding model 'CommitteeActivity'
        db.create_table('committees_committeeactivity', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('committee', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['committees.Committee'])),
            ('source_id', self.gf('django.db.models.fields.IntegerField')()),
            ('name_en', self.gf('django.db.models.fields.CharField')(max_length=500)),
            ('name_fr', self.gf('django.db.models.fields.CharField')(max_length=500)),
            ('study', self.gf('django.db.models.fields.BooleanField')(default=False)),
        ))
        db.send_create_signal('committees', ['CommitteeActivity'])

        # Adding model 'CommitteeMeeting'
        db.create_table('committees_committeemeeting', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('date', self.gf('django.db.models.fields.DateField')()),
            ('start_time', self.gf('django.db.models.fields.TimeField')()),
            ('end_time', self.gf('django.db.models.fields.TimeField')(null=True, blank=True)),
            ('committee', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['committees.Committee'])),
            ('number', self.gf('django.db.models.fields.SmallIntegerField')()),
            ('session', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['core.Session'])),
            ('minutes', self.gf('django.db.models.fields.IntegerField')(null=True, blank=True)),
            ('notice', self.gf('django.db.models.fields.IntegerField')(null=True, blank=True)),
            ('evidence', self.gf('django.db.models.fields.related.OneToOneField')(to=orm['hansards.Document'], unique=True, null=True, blank=True)),
            ('in_camera', self.gf('django.db.models.fields.BooleanField')(default=False)),
            ('travel', self.gf('django.db.models.fields.BooleanField')(default=False)),
            ('webcast', self.gf('django.db.models.fields.BooleanField')(default=False)),
            ('televised', self.gf('django.db.models.fields.BooleanField')(default=False)),
        ))
        db.send_create_signal('committees', ['CommitteeMeeting'])

        # Adding M2M table for field activities on 'CommitteeMeeting'
        db.create_table('committees_committeemeeting_activities', (
            ('id', models.AutoField(verbose_name='ID', primary_key=True, auto_created=True)),
            ('committeemeeting', models.ForeignKey(orm['committees.committeemeeting'], null=False)),
            ('committeeactivity', models.ForeignKey(orm['committees.committeeactivity'], null=False))
        ))
        db.create_unique('committees_committeemeeting_activities', ['committeemeeting_id', 'committeeactivity_id'])

        # Adding model 'CommitteeReport'
        db.create_table('committees_committeereport', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('committee', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['committees.Committee'])),
            ('session', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['core.Session'])),
            ('number', self.gf('django.db.models.fields.SmallIntegerField')(null=True, blank=True)),
            ('name', self.gf('django.db.models.fields.CharField')(max_length=500)),
            ('source_id', self.gf('django.db.models.fields.IntegerField')(unique=True, db_index=True)),
            ('adopted_date', self.gf('django.db.models.fields.DateField')(null=True, blank=True)),
            ('presented_date', self.gf('django.db.models.fields.DateField')(null=True, blank=True)),
            ('government_response', self.gf('django.db.models.fields.BooleanField')(default=False)),
            ('parent', self.gf('django.db.models.fields.related.ForeignKey')(blank=True, related_name='children', null=True, to=orm['committees.CommitteeReport'])),
        ))
        db.send_create_signal('committees', ['CommitteeReport'])


    def backwards(self, orm):
        
        # Deleting model 'Committee'
        db.delete_table('committees_committee')

        # Deleting model 'CommitteeInSession'
        db.delete_table('committees_committeeinsession')

        # Deleting model 'CommitteeActivity'
        db.delete_table('committees_committeeactivity')

        # Deleting model 'CommitteeMeeting'
        db.delete_table('committees_committeemeeting')

        # Removing M2M table for field activities on 'CommitteeMeeting'
        db.delete_table('committees_committeemeeting_activities')

        # Deleting model 'CommitteeReport'
        db.delete_table('committees_committeereport')


    models = {
        'committees.committee': {
            'Meta': {'ordering': "['name']", 'object_name': 'Committee'},
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.TextField', [], {}),
            'parent': ('django.db.models.fields.related.ForeignKey', [], {'blank': 'True', 'related_name': "'subcommittees'", 'null': 'True', 'to': "orm['committees.Committee']"}),
            'sessions': ('django.db.models.fields.related.ManyToManyField', [], {'to': "orm['core.Session']", 'through': "orm['committees.CommitteeInSession']", 'symmetrical': 'False'}),
            'short_name': ('django.db.models.fields.TextField', [], {}),
            'slug': ('django.db.models.fields.SlugField', [], {'unique': 'True', 'max_length': '50', 'db_index': 'True'})
        },
        'committees.committeeactivity': {
            'Meta': {'object_name': 'CommitteeActivity'},
            'committee': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['committees.Committee']"}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name_en': ('django.db.models.fields.CharField', [], {'max_length': '500'}),
            'name_fr': ('django.db.models.fields.CharField', [], {'max_length': '500'}),
            'source_id': ('django.db.models.fields.IntegerField', [], {}),
            'study': ('django.db.models.fields.BooleanField', [], {'default': 'False'})
        },
        'committees.committeeinsession': {
            'Meta': {'object_name': 'CommitteeInSession'},
            'acronym': ('django.db.models.fields.CharField', [], {'max_length': '5', 'db_index': 'True'}),
            'committee': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['committees.Committee']"}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'session': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['core.Session']"})
        },
        'committees.committeemeeting': {
            'Meta': {'object_name': 'CommitteeMeeting'},
            'activities': ('django.db.models.fields.related.ManyToManyField', [], {'to': "orm['committees.CommitteeActivity']", 'symmetrical': 'False'}),
            'committee': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['committees.Committee']"}),
            'date': ('django.db.models.fields.DateField', [], {}),
            'end_time': ('django.db.models.fields.TimeField', [], {'null': 'True', 'blank': 'True'}),
            'evidence': ('django.db.models.fields.related.OneToOneField', [], {'to': "orm['hansards.Document']", 'unique': 'True', 'null': 'True', 'blank': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'in_camera': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'minutes': ('django.db.models.fields.IntegerField', [], {'null': 'True', 'blank': 'True'}),
            'notice': ('django.db.models.fields.IntegerField', [], {'null': 'True', 'blank': 'True'}),
            'number': ('django.db.models.fields.SmallIntegerField', [], {}),
            'session': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['core.Session']"}),
            'start_time': ('django.db.models.fields.TimeField', [], {}),
            'televised': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'travel': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'webcast': ('django.db.models.fields.BooleanField', [], {'default': 'False'})
        },
        'committees.committeereport': {
            'Meta': {'object_name': 'CommitteeReport'},
            'adopted_date': ('django.db.models.fields.DateField', [], {'null': 'True', 'blank': 'True'}),
            'committee': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['committees.Committee']"}),
            'government_response': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '500'}),
            'number': ('django.db.models.fields.SmallIntegerField', [], {'null': 'True', 'blank': 'True'}),
            'parent': ('django.db.models.fields.related.ForeignKey', [], {'blank': 'True', 'related_name': "'children'", 'null': 'True', 'to': "orm['committees.CommitteeReport']"}),
            'presented_date': ('django.db.models.fields.DateField', [], {'null': 'True', 'blank': 'True'}),
            'session': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['core.Session']"}),
            'source_id': ('django.db.models.fields.IntegerField', [], {'unique': 'True', 'db_index': 'True'})
        },
        'core.session': {
            'Meta': {'ordering': "('-start',)", 'object_name': 'Session'},
            'end': ('django.db.models.fields.DateField', [], {'null': 'True', 'blank': 'True'}),
            'id': ('django.db.models.fields.CharField', [], {'max_length': '4', 'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
            'parliamentnum': ('django.db.models.fields.IntegerField', [], {'null': 'True', 'blank': 'True'}),
            'sessnum': ('django.db.models.fields.IntegerField', [], {'null': 'True', 'blank': 'True'}),
            'start': ('django.db.models.fields.DateField', [], {})
        },
        'hansards.document': {
            'Meta': {'ordering': "('-date',)", 'object_name': 'Document'},
            'date': ('django.db.models.fields.DateField', [], {'null': 'True', 'blank': 'True'}),
            'document_type': ('django.db.models.fields.CharField', [], {'max_length': '1', 'db_index': 'True'}),
            'downloaded': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'most_frequent_word': ('django.db.models.fields.CharField', [], {'max_length': '20', 'blank': 'True'}),
            'number': ('django.db.models.fields.CharField', [], {'max_length': '6', 'blank': 'True'}),
            'session': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['core.Session']"}),
            'source_id': ('django.db.models.fields.IntegerField', [], {'unique': 'True', 'db_index': 'True'}),
            'wordcloud': ('django.db.models.fields.files.ImageField', [], {'max_length': '100', 'null': 'True', 'blank': 'True'})
        }
    }

    complete_apps = ['committees']
