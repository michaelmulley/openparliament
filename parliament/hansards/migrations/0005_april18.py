# encoding: utf-8
import datetime
from south.db import db
from south.v2 import SchemaMigration
from django.db import models

class Migration(SchemaMigration):
    
    def forwards(self, orm):
        
        # Adding field 'Statement.speaker'
        db.add_column('hansards_statement', 'speaker', self.gf('django.db.models.fields.BooleanField')(default=False, db_index=True, blank=True), keep_default=False)

        # Adding field 'Statement.written_question'
        db.add_column('hansards_statement', 'written_question', self.gf('django.db.models.fields.BooleanField')(default=False, blank=True), keep_default=False)

        # Adding M2M table for field mentioned_politicians on 'Statement'
        db.create_table('hansards_statement_mentioned_politicians', (
            ('id', models.AutoField(verbose_name='ID', primary_key=True, auto_created=True)),
            ('statement', models.ForeignKey(orm['hansards.statement'], null=False)),
            ('politician', models.ForeignKey(orm['core.politician'], null=False))
        ))
        db.create_unique('hansards_statement_mentioned_politicians', ['statement_id', 'politician_id'])
    
    
    def backwards(self, orm):
        
        # Deleting field 'Statement.speaker'
        db.delete_column('hansards_statement', 'speaker')

        # Deleting field 'Statement.written_question'
        db.delete_column('hansards_statement', 'written_question')

        # Removing M2M table for field mentioned_politicians on 'Statement'
        db.delete_table('hansards_statement_mentioned_politicians')
    
    
    models = {
        'bills.bill': {
            'Meta': {'object_name': 'Bill'},
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'law': ('django.db.models.fields.NullBooleanField', [], {'null': 'True', 'blank': 'True'}),
            'legisinfo_url': ('django.db.models.fields.URLField', [], {'max_length': '200', 'null': 'True', 'blank': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '500'}),
            'number': ('django.db.models.fields.CharField', [], {'max_length': '10'}),
            'number_only': ('django.db.models.fields.SmallIntegerField', [], {}),
            'privatemember': ('django.db.models.fields.NullBooleanField', [], {'null': 'True', 'blank': 'True'}),
            'sessions': ('django.db.models.fields.related.ManyToManyField', [], {'to': "orm['core.Session']"}),
            'sponsor_member': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['core.ElectedMember']", 'null': 'True', 'blank': 'True'}),
            'sponsor_politician': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['core.Politician']", 'null': 'True', 'blank': 'True'}),
            'status': ('django.db.models.fields.CharField', [], {'max_length': '200', 'blank': 'True'})
        },
        'core.electedmember': {
            'Meta': {'object_name': 'ElectedMember'},
            'end_date': ('django.db.models.fields.DateField', [], {'db_index': 'True', 'null': 'True', 'blank': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'party': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['core.Party']"}),
            'politician': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['core.Politician']"}),
            'riding': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['core.Riding']"}),
            'sessions': ('django.db.models.fields.related.ManyToManyField', [], {'to': "orm['core.Session']"}),
            'start_date': ('django.db.models.fields.DateField', [], {'db_index': 'True'})
        },
        'core.party': {
            'Meta': {'object_name': 'Party'},
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
            'short_name': ('django.db.models.fields.CharField', [], {'max_length': '100', 'blank': 'True'}),
            'slug': ('django.db.models.fields.CharField', [], {'max_length': '10', 'blank': 'True'})
        },
        'core.politician': {
            'Meta': {'object_name': 'Politician'},
            'dob': ('django.db.models.fields.DateField', [], {'null': 'True', 'blank': 'True'}),
            'gender': ('django.db.models.fields.CharField', [], {'max_length': '1', 'blank': 'True'}),
            'headshot': ('django.db.models.fields.files.ImageField', [], {'max_length': '100', 'null': 'True', 'blank': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
            'name_family': ('django.db.models.fields.CharField', [], {'max_length': '50', 'blank': 'True'}),
            'name_given': ('django.db.models.fields.CharField', [], {'max_length': '50', 'blank': 'True'}),
            'parlpage': ('django.db.models.fields.URLField', [], {'max_length': '200', 'blank': 'True'}),
            'site': ('django.db.models.fields.URLField', [], {'max_length': '200', 'blank': 'True'}),
            'slug': ('django.db.models.fields.CharField', [], {'db_index': 'True', 'max_length': '30', 'blank': 'True'})
        },
        'core.riding': {
            'Meta': {'object_name': 'Riding'},
            'edid': ('django.db.models.fields.IntegerField', [], {'db_index': 'True', 'null': 'True', 'blank': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '60'}),
            'province': ('django.db.models.fields.CharField', [], {'max_length': '2'}),
            'slug': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '60', 'db_index': 'True'})
        },
        'core.session': {
            'Meta': {'object_name': 'Session'},
            'end': ('django.db.models.fields.DateField', [], {'null': 'True', 'blank': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
            'parliamentnum': ('django.db.models.fields.IntegerField', [], {'null': 'True', 'blank': 'True'}),
            'sessnum': ('django.db.models.fields.IntegerField', [], {'null': 'True', 'blank': 'True'}),
            'start': ('django.db.models.fields.DateField', [], {})
        },
        'hansards.hansard': {
            'Meta': {'object_name': 'Hansard'},
            'date': ('django.db.models.fields.DateField', [], {'null': 'True', 'blank': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'number': ('django.db.models.fields.CharField', [], {'max_length': '6', 'blank': 'True'}),
            'sequence': ('django.db.models.fields.IntegerField', [], {'null': 'True', 'blank': 'True'}),
            'session': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['core.Session']"}),
            'url': ('django.db.models.fields.URLField', [], {'max_length': '200'})
        },
        'hansards.hansardcache': {
            'Meta': {'object_name': 'HansardCache'},
            'filename': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
            'hansard': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['hansards.Hansard']"}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'})
        },
        'hansards.statement': {
            'Meta': {'object_name': 'Statement'},
            'bills': ('django.db.models.fields.related.ManyToManyField', [], {'to': "orm['bills.Bill']", 'blank': 'True'}),
            'hansard': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['hansards.Hansard']"}),
            'heading': ('django.db.models.fields.CharField', [], {'max_length': '110', 'blank': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'member': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['core.ElectedMember']", 'null': 'True', 'blank': 'True'}),
            'mentioned_politicians': ('django.db.models.fields.related.ManyToManyField', [], {'related_name': "'statements_with_mentions'", 'blank': 'True', 'to': "orm['core.Politician']"}),
            'politician': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['core.Politician']", 'null': 'True', 'blank': 'True'}),
            'sequence': ('django.db.models.fields.IntegerField', [], {'db_index': 'True'}),
            'speaker': ('django.db.models.fields.BooleanField', [], {'default': 'False', 'db_index': 'True', 'blank': 'True'}),
            'text': ('django.db.models.fields.TextField', [], {}),
            'time': ('django.db.models.fields.DateTimeField', [], {'db_index': 'True', 'null': 'True', 'blank': 'True'}),
            'topic': ('django.db.models.fields.CharField', [], {'max_length': '200', 'blank': 'True'}),
            'who': ('django.db.models.fields.CharField', [], {'max_length': '300'}),
            'wordcount': ('django.db.models.fields.IntegerField', [], {}),
            'written_question': ('django.db.models.fields.BooleanField', [], {'default': 'False', 'blank': 'True'})
        }
    }
    
    complete_apps = ['hansards']
