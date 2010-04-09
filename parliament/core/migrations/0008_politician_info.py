# encoding: utf-8
import datetime
from south.db import db
from south.v2 import SchemaMigration
from django.db import models

class Migration(SchemaMigration):
    
    def forwards(self, orm):
        
        # Adding model 'PoliticianInfo'
        db.create_table('core_politicianinfo', (
            ('politician', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['core.Politician'])),
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('value', self.gf('django.db.models.fields.CharField')(max_length=500)),
            ('schema', self.gf('django.db.models.fields.CharField')(max_length=40, db_index=True)),
        ))
        db.send_create_signal('core', ['PoliticianInfo'])

        # Adding index on 'InternalXref', fields ['int_value']
        db.create_index('core_internalxref', ['int_value'])

        # Adding index on 'InternalXref', fields ['text_value']
        db.create_index('core_internalxref', ['text_value'])

        # Adding index on 'InternalXref', fields ['target_id']
        db.create_index('core_internalxref', ['target_id'])

        # Adding index on 'InternalXref', fields ['schema']
        db.create_index('core_internalxref', ['schema'])

        # Deleting field 'Party.colour'
        db.delete_column('core_party', 'colour')
    
    
    def backwards(self, orm):
        
        # Deleting model 'PoliticianInfo'
        db.delete_table('core_politicianinfo')

        # Removing index on 'InternalXref', fields ['int_value']
        db.delete_index('core_internalxref', ['int_value'])

        # Removing index on 'InternalXref', fields ['text_value']
        db.delete_index('core_internalxref', ['text_value'])

        # Removing index on 'InternalXref', fields ['target_id']
        db.delete_index('core_internalxref', ['target_id'])

        # Removing index on 'InternalXref', fields ['schema']
        db.delete_index('core_internalxref', ['schema'])

        # Adding field 'Party.colour'
        db.add_column('core_party', 'colour', self.gf('django.db.models.fields.CharField')(default='', max_length=7, blank=True), keep_default=False)
    
    
    models = {
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
        'core.internalxref': {
            'Meta': {'object_name': 'InternalXref'},
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'int_value': ('django.db.models.fields.IntegerField', [], {'db_index': 'True', 'null': 'True', 'blank': 'True'}),
            'schema': ('django.db.models.fields.CharField', [], {'max_length': '15', 'db_index': 'True'}),
            'target_id': ('django.db.models.fields.IntegerField', [], {'db_index': 'True'}),
            'text_value': ('django.db.models.fields.CharField', [], {'db_index': 'True', 'max_length': '50', 'blank': 'True'})
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
            'site': ('django.db.models.fields.URLField', [], {'max_length': '200', 'blank': 'True'})
        },
        'core.politicianinfo': {
            'Meta': {'object_name': 'PoliticianInfo'},
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'politician': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['core.Politician']"}),
            'schema': ('django.db.models.fields.CharField', [], {'max_length': '40', 'db_index': 'True'}),
            'value': ('django.db.models.fields.CharField', [], {'max_length': '500'})
        },
        'core.riding': {
            'Meta': {'object_name': 'Riding'},
            'edid': ('django.db.models.fields.IntegerField', [], {'null': 'True', 'blank': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '60'}),
            'province': ('django.db.models.fields.CharField', [], {'max_length': '2'}),
            'slug': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '60'})
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
    
    complete_apps = ['core']
