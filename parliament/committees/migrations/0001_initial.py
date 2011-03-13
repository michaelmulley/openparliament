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
            ('acronym', self.gf('django.db.models.fields.CharField')(max_length=4, db_index=True)),
            ('parent', self.gf('django.db.models.fields.related.ForeignKey')(blank=True, related_name='subcommittees', null=True, to=orm['committees.Committee'])),
            ('active', self.gf('django.db.models.fields.BooleanField')(default=False)),
        ))
        db.send_create_signal('committees', ['Committee'])

        # Adding M2M table for field sessions on 'Committee'
        db.create_table('committees_committee_sessions', (
            ('id', models.AutoField(verbose_name='ID', primary_key=True, auto_created=True)),
            ('committee', models.ForeignKey(orm['committees.committee'], null=False)),
            ('session', models.ForeignKey(orm['core.session'], null=False))
        ))
        db.create_unique('committees_committee_sessions', ['committee_id', 'session_id'])


    def backwards(self, orm):
        
        # Deleting model 'Committee'
        db.delete_table('committees_committee')

        # Removing M2M table for field sessions on 'Committee'
        db.delete_table('committees_committee_sessions')


    models = {
        'committees.committee': {
            'Meta': {'object_name': 'Committee'},
            'acronym': ('django.db.models.fields.CharField', [], {'max_length': '4', 'db_index': 'True'}),
            'active': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.TextField', [], {}),
            'parent': ('django.db.models.fields.related.ForeignKey', [], {'blank': 'True', 'related_name': "'subcommittees'", 'null': 'True', 'to': "orm['committees.Committee']"}),
            'sessions': ('django.db.models.fields.related.ManyToManyField', [], {'to': "orm['core.Session']", 'symmetrical': 'False'})
        },
        'core.session': {
            'Meta': {'ordering': "('-start',)", 'object_name': 'Session'},
            'end': ('django.db.models.fields.DateField', [], {'null': 'True', 'blank': 'True'}),
            'id': ('django.db.models.fields.CharField', [], {'max_length': '4', 'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
            'parliamentnum': ('django.db.models.fields.IntegerField', [], {'null': 'True', 'blank': 'True'}),
            'sessnum': ('django.db.models.fields.IntegerField', [], {'null': 'True', 'blank': 'True'}),
            'start': ('django.db.models.fields.DateField', [], {})
        }
    }

    complete_apps = ['committees']
