# encoding: utf-8
import datetime
from south.db import db
from south.v2 import SchemaMigration
from django.db import models

class Migration(SchemaMigration):

    def forwards(self, orm):
        
        # Adding model 'CommitteeActivityInSession'
        db.create_table('committees_committeeactivityinsession', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('activity', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['committees.CommitteeActivity'])),
            ('session', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['core.Session'])),
            ('source_id', self.gf('django.db.models.fields.IntegerField')(unique=True)),
        ))
        db.send_create_signal('committees', ['CommitteeActivityInSession'])

        # Adding unique constraint on 'CommitteeActivityInSession', fields ['activity', 'session']
        db.create_unique('committees_committeeactivityinsession', ['activity_id', 'session_id'])

        # Adding index on 'CommitteeMeeting', fields ['date']
        db.create_index('committees_committeemeeting', ['date'])

        # Adding unique constraint on 'CommitteeMeeting', fields ['session', 'number', 'committee']
        db.create_unique('committees_committeemeeting', ['session_id', 'number', 'committee_id'])

        # Deleting field 'CommitteeActivity.source_id'
        db.delete_column('committees_committeeactivity', 'source_id')

        # Adding unique constraint on 'CommitteeInSession', fields ['session', 'committee']
        db.create_unique('committees_committeeinsession', ['session_id', 'committee_id'])


    def backwards(self, orm):
        
        # Removing unique constraint on 'CommitteeInSession', fields ['session', 'committee']
        db.delete_unique('committees_committeeinsession', ['session_id', 'committee_id'])

        # Removing unique constraint on 'CommitteeMeeting', fields ['session', 'number', 'committee']
        db.delete_unique('committees_committeemeeting', ['session_id', 'number', 'committee_id'])

        # Removing index on 'CommitteeMeeting', fields ['date']
        db.delete_index('committees_committeemeeting', ['date'])

        # Removing unique constraint on 'CommitteeActivityInSession', fields ['activity', 'session']
        db.delete_unique('committees_committeeactivityinsession', ['activity_id', 'session_id'])

        # Deleting model 'CommitteeActivityInSession'
        db.delete_table('committees_committeeactivityinsession')

        # We cannot add back in field 'CommitteeActivity.source_id'
        raise RuntimeError(
            "Cannot reverse this migration. 'CommitteeActivity.source_id' and its values cannot be restored.")


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
            'study': ('django.db.models.fields.BooleanField', [], {'default': 'False'})
        },
        'committees.committeeactivityinsession': {
            'Meta': {'unique_together': "[('activity', 'session')]", 'object_name': 'CommitteeActivityInSession'},
            'activity': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['committees.CommitteeActivity']"}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'session': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['core.Session']"}),
            'source_id': ('django.db.models.fields.IntegerField', [], {'unique': 'True'})
        },
        'committees.committeeinsession': {
            'Meta': {'unique_together': "[('session', 'committee')]", 'object_name': 'CommitteeInSession'},
            'acronym': ('django.db.models.fields.CharField', [], {'max_length': '5', 'db_index': 'True'}),
            'committee': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['committees.Committee']"}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'session': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['core.Session']"})
        },
        'committees.committeemeeting': {
            'Meta': {'unique_together': "[('session', 'committee', 'number')]", 'object_name': 'CommitteeMeeting'},
            'activities': ('django.db.models.fields.related.ManyToManyField', [], {'to': "orm['committees.CommitteeActivity']", 'symmetrical': 'False'}),
            'committee': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['committees.Committee']"}),
            'date': ('django.db.models.fields.DateField', [], {'db_index': 'True'}),
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
            'multilingual': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'number': ('django.db.models.fields.CharField', [], {'max_length': '6', 'blank': 'True'}),
            'public': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'session': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['core.Session']"}),
            'skip_parsing': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'source_id': ('django.db.models.fields.IntegerField', [], {'unique': 'True', 'db_index': 'True'}),
            'wordcloud': ('django.db.models.fields.files.ImageField', [], {'max_length': '100', 'null': 'True', 'blank': 'True'})
        }
    }

    complete_apps = ['committees']
