# encoding: utf-8
import datetime
from south.db import db
from south.v2 import SchemaMigration
from django.db import models

class Migration(SchemaMigration):

    def forwards(self, orm):
        
        # Adding field 'CommitteeMeeting.source_id'
        db.add_column(u'committees_committeemeeting', 'source_id', self.gf('django.db.models.fields.IntegerField')(null=True, blank=True), keep_default=False)


    def backwards(self, orm):
        
        # Deleting field 'CommitteeMeeting.source_id'
        db.delete_column(u'committees_committeemeeting', 'source_id')


    models = {
        u'committees.committee': {
            'Meta': {'ordering': "['name_en']", 'object_name': 'Committee'},
            'display': ('django.db.models.fields.BooleanField', [], {'default': 'True', 'db_index': 'True'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name_en': ('django.db.models.fields.TextField', [], {}),
            'name_fr': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
            'parent': ('django.db.models.fields.related.ForeignKey', [], {'blank': 'True', 'related_name': "'subcommittees'", 'null': 'True', 'to': u"orm['committees.Committee']"}),
            'sessions': ('django.db.models.fields.related.ManyToManyField', [], {'to': u"orm['core.Session']", 'through': u"orm['committees.CommitteeInSession']", 'symmetrical': 'False'}),
            'short_name_en': ('django.db.models.fields.TextField', [], {}),
            'short_name_fr': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
            'slug': ('django.db.models.fields.SlugField', [], {'unique': 'True', 'max_length': '50', 'db_index': 'True'})
        },
        u'committees.committeeactivity': {
            'Meta': {'object_name': 'CommitteeActivity'},
            'committee': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['committees.Committee']"}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name_en': ('django.db.models.fields.CharField', [], {'max_length': '500'}),
            'name_fr': ('django.db.models.fields.CharField', [], {'max_length': '500'}),
            'study': ('django.db.models.fields.BooleanField', [], {'default': 'False'})
        },
        u'committees.committeeactivityinsession': {
            'Meta': {'unique_together': "[('activity', 'session')]", 'object_name': 'CommitteeActivityInSession'},
            'activity': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['committees.CommitteeActivity']"}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'session': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['core.Session']"}),
            'source_id': ('django.db.models.fields.IntegerField', [], {'unique': 'True'})
        },
        u'committees.committeeinsession': {
            'Meta': {'unique_together': "[('session', 'committee'), ('session', 'acronym')]", 'object_name': 'CommitteeInSession'},
            'acronym': ('django.db.models.fields.CharField', [], {'max_length': '5', 'db_index': 'True'}),
            'committee': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['committees.Committee']"}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'session': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['core.Session']"})
        },
        u'committees.committeemeeting': {
            'Meta': {'unique_together': "[('session', 'committee', 'number')]", 'object_name': 'CommitteeMeeting'},
            'activities': ('django.db.models.fields.related.ManyToManyField', [], {'to': u"orm['committees.CommitteeActivity']", 'symmetrical': 'False'}),
            'committee': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['committees.Committee']"}),
            'date': ('django.db.models.fields.DateField', [], {'db_index': 'True'}),
            'end_time': ('django.db.models.fields.TimeField', [], {'null': 'True', 'blank': 'True'}),
            'evidence': ('django.db.models.fields.related.OneToOneField', [], {'to': u"orm['hansards.Document']", 'unique': 'True', 'null': 'True', 'blank': 'True'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'in_camera': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'minutes': ('django.db.models.fields.IntegerField', [], {'null': 'True', 'blank': 'True'}),
            'notice': ('django.db.models.fields.IntegerField', [], {'null': 'True', 'blank': 'True'}),
            'number': ('django.db.models.fields.SmallIntegerField', [], {}),
            'session': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['core.Session']"}),
            'source_id': ('django.db.models.fields.IntegerField', [], {'null': 'True', 'blank': 'True'}),
            'start_time': ('django.db.models.fields.TimeField', [], {}),
            'televised': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'travel': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'webcast': ('django.db.models.fields.BooleanField', [], {'default': 'False'})
        },
        u'committees.committeereport': {
            'Meta': {'object_name': 'CommitteeReport'},
            'adopted_date': ('django.db.models.fields.DateField', [], {'null': 'True', 'blank': 'True'}),
            'committee': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['committees.Committee']"}),
            'government_response': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name_en': ('django.db.models.fields.CharField', [], {'max_length': '500'}),
            'name_fr': ('django.db.models.fields.CharField', [], {'max_length': '500', 'blank': 'True'}),
            'number': ('django.db.models.fields.SmallIntegerField', [], {'null': 'True', 'blank': 'True'}),
            'parent': ('django.db.models.fields.related.ForeignKey', [], {'blank': 'True', 'related_name': "'children'", 'null': 'True', 'to': u"orm['committees.CommitteeReport']"}),
            'presented_date': ('django.db.models.fields.DateField', [], {'null': 'True', 'blank': 'True'}),
            'session': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['core.Session']"}),
            'source_id': ('django.db.models.fields.IntegerField', [], {'unique': 'True', 'db_index': 'True'})
        },
        u'core.session': {
            'Meta': {'ordering': "('-start',)", 'object_name': 'Session'},
            'end': ('django.db.models.fields.DateField', [], {'null': 'True', 'blank': 'True'}),
            'id': ('django.db.models.fields.CharField', [], {'max_length': '4', 'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
            'parliamentnum': ('django.db.models.fields.IntegerField', [], {'null': 'True', 'blank': 'True'}),
            'sessnum': ('django.db.models.fields.IntegerField', [], {'null': 'True', 'blank': 'True'}),
            'start': ('django.db.models.fields.DateField', [], {})
        },
        u'hansards.document': {
            'Meta': {'ordering': "('-date',)", 'object_name': 'Document'},
            'date': ('django.db.models.fields.DateField', [], {'null': 'True', 'blank': 'True'}),
            'document_type': ('django.db.models.fields.CharField', [], {'max_length': '1', 'db_index': 'True'}),
            'downloaded': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'most_frequent_word': ('django.db.models.fields.CharField', [], {'max_length': '20', 'blank': 'True'}),
            'multilingual': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'number': ('django.db.models.fields.CharField', [], {'max_length': '6', 'blank': 'True'}),
            'public': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'session': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['core.Session']"}),
            'skip_parsing': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'source_id': ('django.db.models.fields.IntegerField', [], {'unique': 'True', 'db_index': 'True'}),
            'wordcloud': ('django.db.models.fields.files.ImageField', [], {'max_length': '100', 'null': 'True', 'blank': 'True'})
        }
    }

    complete_apps = ['committees']
