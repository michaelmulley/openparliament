# encoding: utf-8
import datetime
from south.db import db
from south.v2 import SchemaMigration
from django.db import models

class Migration(SchemaMigration):
    
    def forwards(self, orm):
        
        # Adding field 'Bill.number_only'
        db.add_column('bills_bill', 'number_only', self.gf('django.db.models.fields.SmallIntegerField')(default=0), keep_default=False)
    
    
    def backwards(self, orm):
        
        # Deleting field 'Bill.number_only'
        db.delete_column('bills_bill', 'number_only')
    
    
    models = {
        'bills.bill': {
            'Meta': {'object_name': 'Bill'},
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '500'}),
            'number': ('django.db.models.fields.CharField', [], {'max_length': '10'}),
            'number_only': ('django.db.models.fields.SmallIntegerField', [], {}),
            'session': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['core.Session']"})
        },
        'core.session': {
            'Meta': {'object_name': 'Session'},
            'end': ('django.db.models.fields.DateField', [], {'null': 'True', 'blank': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
            'parliamentnum': ('django.db.models.fields.IntegerField', [], {'null': 'True', 'blank': 'True'}),
            'sessnum': ('django.db.models.fields.IntegerField', [], {'null': 'True', 'blank': 'True'}),
            'start': ('django.db.models.fields.DateField', [], {})
        }
    }
    
    complete_apps = ['bills']
