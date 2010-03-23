# encoding: utf-8
import datetime
from south.db import db
from south.v2 import SchemaMigration
from django.db import models

class Migration(SchemaMigration):
    
    def forwards(self, orm):
        
        # Adding model 'InternalXref'
        db.create_table('core_internalxref', (
            ('int_value', self.gf('django.db.models.fields.IntegerField')(null=True, blank=True)),
            ('text_value', self.gf('django.db.models.fields.CharField')(max_length=50, blank=True)),
            ('target_id', self.gf('django.db.models.fields.IntegerField')()),
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('schema', self.gf('django.db.models.fields.CharField')(max_length=15)),
        ))
        db.send_create_signal('core', ['InternalXref'])

        # Adding model 'Party'
        db.create_table('core_party', (
            ('slug', self.gf('django.db.models.fields.CharField')(max_length=10, blank=True)),
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('name', self.gf('django.db.models.fields.CharField')(max_length=100)),
        ))
        db.send_create_signal('core', ['Party'])

        # Adding model 'Politician'
        db.create_table('core_politician', (
            ('name_given', self.gf('django.db.models.fields.CharField')(max_length=50, blank=True)),
            ('parlpage', self.gf('django.db.models.fields.URLField')(max_length=200, blank=True)),
            ('name', self.gf('django.db.models.fields.CharField')(max_length=100)),
            ('dob', self.gf('django.db.models.fields.DateField')(null=True, blank=True)),
            ('gender', self.gf('django.db.models.fields.CharField')(max_length=1, blank=True)),
            ('site', self.gf('django.db.models.fields.URLField')(max_length=200, blank=True)),
            ('name_family', self.gf('django.db.models.fields.CharField')(max_length=50, blank=True)),
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
        ))
        db.send_create_signal('core', ['Politician'])

        # Adding model 'Session'
        db.create_table('core_session', (
            ('end', self.gf('django.db.models.fields.DateField')(null=True, blank=True)),
            ('name', self.gf('django.db.models.fields.CharField')(max_length=100)),
            ('sessnum', self.gf('django.db.models.fields.IntegerField')(null=True, blank=True)),
            ('start', self.gf('django.db.models.fields.DateField')()),
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('parliamentnum', self.gf('django.db.models.fields.IntegerField')(null=True, blank=True)),
        ))
        db.send_create_signal('core', ['Session'])

        # Adding model 'Riding'
        db.create_table('core_riding', (
            ('province', self.gf('django.db.models.fields.CharField')(max_length=2)),
            ('edid', self.gf('django.db.models.fields.IntegerField')(null=True, blank=True)),
            ('slug', self.gf('django.db.models.fields.CharField')(unique=True, max_length=60)),
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('name', self.gf('django.db.models.fields.CharField')(max_length=60)),
        ))
        db.send_create_signal('core', ['Riding'])

        # Adding model 'ElectedMember'
        db.create_table('core_electedmember', (
            ('member', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['core.Politician'])),
            ('riding', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['core.Riding'])),
            ('session', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['core.Session'])),
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('party', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['core.Party'])),
        ))
        db.send_create_signal('core', ['ElectedMember'])
    
    
    def backwards(self, orm):
        
        # Deleting model 'InternalXref'
        db.delete_table('core_internalxref')

        # Deleting model 'Party'
        db.delete_table('core_party')

        # Deleting model 'Politician'
        db.delete_table('core_politician')

        # Deleting model 'Session'
        db.delete_table('core_session')

        # Deleting model 'Riding'
        db.delete_table('core_riding')

        # Deleting model 'ElectedMember'
        db.delete_table('core_electedmember')
    
    
    models = {
        'core.electedmember': {
            'Meta': {'object_name': 'ElectedMember'},
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'member': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['core.Politician']"}),
            'party': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['core.Party']"}),
            'riding': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['core.Riding']"}),
            'session': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['core.Session']"})
        },
        'core.internalxref': {
            'Meta': {'object_name': 'InternalXref'},
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'int_value': ('django.db.models.fields.IntegerField', [], {'null': 'True', 'blank': 'True'}),
            'schema': ('django.db.models.fields.CharField', [], {'max_length': '15'}),
            'target_id': ('django.db.models.fields.IntegerField', [], {}),
            'text_value': ('django.db.models.fields.CharField', [], {'max_length': '50', 'blank': 'True'})
        },
        'core.party': {
            'Meta': {'object_name': 'Party'},
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
            'slug': ('django.db.models.fields.CharField', [], {'max_length': '10', 'blank': 'True'})
        },
        'core.politician': {
            'Meta': {'object_name': 'Politician'},
            'dob': ('django.db.models.fields.DateField', [], {'null': 'True', 'blank': 'True'}),
            'gender': ('django.db.models.fields.CharField', [], {'max_length': '1', 'blank': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
            'name_family': ('django.db.models.fields.CharField', [], {'max_length': '50', 'blank': 'True'}),
            'name_given': ('django.db.models.fields.CharField', [], {'max_length': '50', 'blank': 'True'}),
            'parlpage': ('django.db.models.fields.URLField', [], {'max_length': '200', 'blank': 'True'}),
            'site': ('django.db.models.fields.URLField', [], {'max_length': '200', 'blank': 'True'})
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
