# encoding: utf-8
import datetime
from south.db import db
from south.v2 import SchemaMigration
from django.db import models

class Migration(SchemaMigration):

    def forwards(self, orm):
        
        # Adding field 'Statement.wordcount_en'
        db.add_column(u'hansards_statement', 'wordcount_en', self.gf('django.db.models.fields.PositiveSmallIntegerField')(null=True), keep_default=False)


    def backwards(self, orm):
        
        # Deleting field 'Statement.wordcount_en'
        db.delete_column(u'hansards_statement', 'wordcount_en')


    models = {
        u'bills.bill': {
            'Meta': {'ordering': "('privatemember', 'institution', 'number_only')", 'object_name': 'Bill'},
            'added': ('django.db.models.fields.DateField', [], {'default': 'datetime.date.today', 'db_index': 'True'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'institution': ('django.db.models.fields.CharField', [], {'max_length': '1', 'db_index': 'True'}),
            'introduced': ('django.db.models.fields.DateField', [], {'null': 'True', 'blank': 'True'}),
            'law': ('django.db.models.fields.NullBooleanField', [], {'null': 'True', 'blank': 'True'}),
            'name_en': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
            'name_fr': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
            'number': ('django.db.models.fields.CharField', [], {'max_length': '10'}),
            'number_only': ('django.db.models.fields.SmallIntegerField', [], {}),
            'privatemember': ('django.db.models.fields.NullBooleanField', [], {'null': 'True', 'blank': 'True'}),
            'sessions': ('django.db.models.fields.related.ManyToManyField', [], {'to': u"orm['core.Session']", 'through': u"orm['bills.BillInSession']", 'symmetrical': 'False'}),
            'short_title_en': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
            'short_title_fr': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
            'sponsor_member': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['core.ElectedMember']", 'null': 'True', 'blank': 'True'}),
            'sponsor_politician': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['core.Politician']", 'null': 'True', 'blank': 'True'}),
            'status_code': ('django.db.models.fields.CharField', [], {'max_length': '50', 'blank': 'True'}),
            'status_date': ('django.db.models.fields.DateField', [], {'db_index': 'True', 'null': 'True', 'blank': 'True'}),
            'text_docid': ('django.db.models.fields.IntegerField', [], {'null': 'True', 'blank': 'True'})
        },
        u'bills.billevent': {
            'Meta': {'object_name': 'BillEvent'},
            'bis': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['bills.BillInSession']"}),
            'committee_meetings': ('django.db.models.fields.related.ManyToManyField', [], {'to': u"orm['committees.CommitteeMeeting']", 'symmetrical': 'False', 'blank': 'True'}),
            'date': ('django.db.models.fields.DateField', [], {'db_index': 'True'}),
            'debate': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['hansards.Document']", 'null': 'True', 'blank': 'True'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'institution': ('django.db.models.fields.CharField', [], {'max_length': '1'}),
            'source_id': ('django.db.models.fields.PositiveIntegerField', [], {'unique': 'True', 'db_index': 'True'}),
            'status_en': ('django.db.models.fields.TextField', [], {}),
            'status_fr': ('django.db.models.fields.TextField', [], {'blank': 'True'})
        },
        u'bills.billinsession': {
            'Meta': {'object_name': 'BillInSession'},
            'bill': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['bills.Bill']"}),
            'debates': ('django.db.models.fields.related.ManyToManyField', [], {'to': u"orm['hansards.Document']", 'through': u"orm['bills.BillEvent']", 'symmetrical': 'False'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'introduced': ('django.db.models.fields.DateField', [], {'db_index': 'True', 'null': 'True', 'blank': 'True'}),
            'legisinfo_id': ('django.db.models.fields.PositiveIntegerField', [], {'db_index': 'True', 'null': 'True', 'blank': 'True'}),
            'session': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['core.Session']"}),
            'sponsor_member': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['core.ElectedMember']", 'null': 'True', 'blank': 'True'}),
            'sponsor_politician': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['core.Politician']", 'null': 'True', 'blank': 'True'})
        },
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
        u'core.electedmember': {
            'Meta': {'object_name': 'ElectedMember'},
            'end_date': ('django.db.models.fields.DateField', [], {'db_index': 'True', 'null': 'True', 'blank': 'True'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'party': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['core.Party']"}),
            'politician': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['core.Politician']"}),
            'riding': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['core.Riding']"}),
            'sessions': ('django.db.models.fields.related.ManyToManyField', [], {'to': u"orm['core.Session']", 'symmetrical': 'False'}),
            'start_date': ('django.db.models.fields.DateField', [], {'db_index': 'True'})
        },
        u'core.party': {
            'Meta': {'ordering': "('name',)", 'object_name': 'Party'},
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
            'short_name': ('django.db.models.fields.CharField', [], {'max_length': '100', 'blank': 'True'}),
            'slug': ('django.db.models.fields.CharField', [], {'max_length': '10', 'blank': 'True'})
        },
        u'core.politician': {
            'Meta': {'ordering': "('name',)", 'object_name': 'Politician'},
            'dob': ('django.db.models.fields.DateField', [], {'null': 'True', 'blank': 'True'}),
            'gender': ('django.db.models.fields.CharField', [], {'max_length': '1', 'blank': 'True'}),
            'headshot': ('django.db.models.fields.files.ImageField', [], {'max_length': '100', 'null': 'True', 'blank': 'True'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
            'name_family': ('django.db.models.fields.CharField', [], {'max_length': '50', 'blank': 'True'}),
            'name_given': ('django.db.models.fields.CharField', [], {'max_length': '50', 'blank': 'True'}),
            'slug': ('django.db.models.fields.CharField', [], {'db_index': 'True', 'max_length': '30', 'blank': 'True'})
        },
        u'core.riding': {
            'Meta': {'ordering': "('province', 'name')", 'object_name': 'Riding'},
            'current': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'edid': ('django.db.models.fields.IntegerField', [], {'db_index': 'True', 'null': 'True', 'blank': 'True'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '200'}),
            'name_fr': ('django.db.models.fields.CharField', [], {'max_length': '200', 'blank': 'True'}),
            'province': ('django.db.models.fields.CharField', [], {'max_length': '2'}),
            'slug': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '60', 'db_index': 'True'})
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
        },
        u'hansards.oldsequencemapping': {
            'Meta': {'unique_together': "(('document', 'sequence'),)", 'object_name': 'OldSequenceMapping'},
            'document': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['hansards.Document']"}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'sequence': ('django.db.models.fields.PositiveIntegerField', [], {}),
            'slug': ('django.db.models.fields.SlugField', [], {'max_length': '100', 'db_index': 'True'})
        },
        u'hansards.statement': {
            'Meta': {'ordering': "('sequence',)", 'unique_together': "(('document', 'slug'),)", 'object_name': 'Statement'},
            'bills': ('django.db.models.fields.related.ManyToManyField', [], {'to': u"orm['bills.Bill']", 'symmetrical': 'False', 'blank': 'True'}),
            'content_en': ('django.db.models.fields.TextField', [], {}),
            'content_fr': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
            'document': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['hansards.Document']"}),
            'h1_en': ('django.db.models.fields.CharField', [], {'max_length': '300', 'blank': 'True'}),
            'h1_fr': ('django.db.models.fields.CharField', [], {'max_length': '400', 'blank': 'True'}),
            'h2_en': ('django.db.models.fields.CharField', [], {'max_length': '300', 'blank': 'True'}),
            'h2_fr': ('django.db.models.fields.CharField', [], {'max_length': '400', 'blank': 'True'}),
            'h3_en': ('django.db.models.fields.CharField', [], {'max_length': '300', 'blank': 'True'}),
            'h3_fr': ('django.db.models.fields.CharField', [], {'max_length': '400', 'blank': 'True'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'member': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['core.ElectedMember']", 'null': 'True', 'blank': 'True'}),
            'mentioned_politicians': ('django.db.models.fields.related.ManyToManyField', [], {'symmetrical': 'False', 'related_name': "'statements_with_mentions'", 'blank': 'True', 'to': u"orm['core.Politician']"}),
            'politician': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['core.Politician']", 'null': 'True', 'blank': 'True'}),
            'procedural': ('django.db.models.fields.BooleanField', [], {'default': 'False', 'db_index': 'True'}),
            'sequence': ('django.db.models.fields.IntegerField', [], {'db_index': 'True'}),
            'slug': ('django.db.models.fields.SlugField', [], {'db_index': 'True', 'max_length': '100', 'blank': 'True'}),
            'source_id': ('django.db.models.fields.CharField', [], {'max_length': '15', 'blank': 'True'}),
            'statement_type': ('django.db.models.fields.CharField', [], {'max_length': '35', 'blank': 'True'}),
            'time': ('django.db.models.fields.DateTimeField', [], {'db_index': 'True'}),
            'urlcache': ('django.db.models.fields.CharField', [], {'max_length': '200', 'blank': 'True'}),
            'who_context_en': ('django.db.models.fields.CharField', [], {'max_length': '300', 'blank': 'True'}),
            'who_context_fr': ('django.db.models.fields.CharField', [], {'max_length': '500', 'blank': 'True'}),
            'who_en': ('django.db.models.fields.CharField', [], {'max_length': '300', 'blank': 'True'}),
            'who_fr': ('django.db.models.fields.CharField', [], {'max_length': '500', 'blank': 'True'}),
            'who_hocid': ('django.db.models.fields.PositiveIntegerField', [], {'db_index': 'True', 'null': 'True', 'blank': 'True'}),
            'wordcount': ('django.db.models.fields.IntegerField', [], {}),
            'wordcount_en': ('django.db.models.fields.PositiveSmallIntegerField', [], {'null': 'True'}),
            'written_question': ('django.db.models.fields.CharField', [], {'max_length': '1', 'blank': 'True'})
        }
    }

    complete_apps = ['hansards']
