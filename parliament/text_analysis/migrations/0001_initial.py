# encoding: utf-8
import datetime
from south.db import db
from south.v2 import SchemaMigration
from django.db import models

class Migration(SchemaMigration):

    def forwards(self, orm):
        
        # Adding model 'TextAnalysis'
        db.create_table(u'text_analysis_textanalysis', (
            (u'id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('key', self.gf('django.db.models.fields.CharField')(max_length=150, db_index=True)),
            ('lang', self.gf('django.db.models.fields.CharField')(max_length=2)),
            ('updated', self.gf('django.db.models.fields.DateTimeField')(default=datetime.datetime.now)),
            ('expires', self.gf('django.db.models.fields.DateTimeField')(null=True, blank=True)),
            ('probability_data_json', self.gf('django.db.models.fields.TextField')()),
        ))
        db.send_create_signal(u'text_analysis', ['TextAnalysis'])

        # Adding unique constraint on 'TextAnalysis', fields ['key', 'lang']
        db.create_unique(u'text_analysis_textanalysis', ['key', 'lang'])


    def backwards(self, orm):
        
        # Removing unique constraint on 'TextAnalysis', fields ['key', 'lang']
        db.delete_unique(u'text_analysis_textanalysis', ['key', 'lang'])

        # Deleting model 'TextAnalysis'
        db.delete_table(u'text_analysis_textanalysis')


    models = {
        u'text_analysis.textanalysis': {
            'Meta': {'unique_together': "[('key', 'lang')]", 'object_name': 'TextAnalysis'},
            'expires': ('django.db.models.fields.DateTimeField', [], {'null': 'True', 'blank': 'True'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'key': ('django.db.models.fields.CharField', [], {'max_length': '150', 'db_index': 'True'}),
            'lang': ('django.db.models.fields.CharField', [], {'max_length': '2'}),
            'probability_data_json': ('django.db.models.fields.TextField', [], {}),
            'updated': ('django.db.models.fields.DateTimeField', [], {'default': 'datetime.datetime.now'})
        }
    }

    complete_apps = ['text_analysis']
