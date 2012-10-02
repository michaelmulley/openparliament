# encoding: utf-8
import datetime
from south.db import db
from south.v2 import SchemaMigration
from django.db import models

class Migration(SchemaMigration):

    def forwards(self, orm):
        
        # Adding model 'SeenItem'
        db.create_table('alerts_seenitem', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('topic', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['alerts.Topic'])),
            ('item_id', self.gf('django.db.models.fields.CharField')(max_length=400, db_index=True)),
            ('timestamp', self.gf('django.db.models.fields.DateTimeField')(default=datetime.datetime.now)),
        ))
        db.send_create_signal('alerts', ['SeenItem'])

        # Adding unique constraint on 'SeenItem', fields ['topic', 'item_id']
        db.create_unique('alerts_seenitem', ['topic_id', 'item_id'])

        # Adding model 'Topic'
        db.create_table('alerts_topic', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('query', self.gf('django.db.models.fields.CharField')(unique=True, max_length=800)),
            ('created', self.gf('django.db.models.fields.DateTimeField')(default=datetime.datetime.now)),
            ('last_checked', self.gf('django.db.models.fields.DateTimeField')(null=True, blank=True)),
            ('last_found', self.gf('django.db.models.fields.DateTimeField')(null=True, blank=True)),
        ))
        db.send_create_signal('alerts', ['Topic'])

        # Adding model 'Subscription'
        db.create_table('alerts_subscription', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('topic', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['alerts.Topic'])),
            ('user', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['accounts.User'])),
            ('created', self.gf('django.db.models.fields.DateTimeField')(default=datetime.datetime.now)),
            ('active', self.gf('django.db.models.fields.BooleanField')(default=True)),
            ('last_sent', self.gf('django.db.models.fields.DateTimeField')(null=True, blank=True)),
        ))
        db.send_create_signal('alerts', ['Subscription'])

        # Adding unique constraint on 'Subscription', fields ['topic', 'user']
        db.create_unique('alerts_subscription', ['topic_id', 'user_id'])


    def backwards(self, orm):
        
        # Removing unique constraint on 'Subscription', fields ['topic', 'user']
        db.delete_unique('alerts_subscription', ['topic_id', 'user_id'])

        # Removing unique constraint on 'SeenItem', fields ['topic', 'item_id']
        db.delete_unique('alerts_seenitem', ['topic_id', 'item_id'])

        # Deleting model 'SeenItem'
        db.delete_table('alerts_seenitem')

        # Deleting model 'Topic'
        db.delete_table('alerts_topic')

        # Deleting model 'Subscription'
        db.delete_table('alerts_subscription')


    models = {
        'accounts.user': {
            'Meta': {'object_name': 'User'},
            'created': ('django.db.models.fields.DateTimeField', [], {'default': 'datetime.datetime.now'}),
            'email': ('django.db.models.fields.EmailField', [], {'unique': 'True', 'max_length': '75', 'db_index': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'json_data': ('django.db.models.fields.TextField', [], {'default': "'{}'"}),
            'last_login': ('django.db.models.fields.DateTimeField', [], {'null': 'True', 'blank': 'True'})
        },
        'alerts.politicianalert': {
            'Meta': {'object_name': 'PoliticianAlert'},
            'active': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'created': ('django.db.models.fields.DateTimeField', [], {'default': 'datetime.datetime.now'}),
            'email': ('django.db.models.fields.EmailField', [], {'max_length': '75'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'politician': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['core.Politician']"})
        },
        'alerts.seenitem': {
            'Meta': {'unique_together': "[('topic', 'item_id')]", 'object_name': 'SeenItem'},
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'item_id': ('django.db.models.fields.CharField', [], {'max_length': '400', 'db_index': 'True'}),
            'timestamp': ('django.db.models.fields.DateTimeField', [], {'default': 'datetime.datetime.now'}),
            'topic': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['alerts.Topic']"})
        },
        'alerts.subscription': {
            'Meta': {'unique_together': "[('topic', 'user')]", 'object_name': 'Subscription'},
            'active': ('django.db.models.fields.BooleanField', [], {'default': 'True'}),
            'created': ('django.db.models.fields.DateTimeField', [], {'default': 'datetime.datetime.now'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'last_sent': ('django.db.models.fields.DateTimeField', [], {'null': 'True', 'blank': 'True'}),
            'topic': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['alerts.Topic']"}),
            'user': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['accounts.User']"})
        },
        'alerts.topic': {
            'Meta': {'object_name': 'Topic'},
            'created': ('django.db.models.fields.DateTimeField', [], {'default': 'datetime.datetime.now'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'last_checked': ('django.db.models.fields.DateTimeField', [], {'null': 'True', 'blank': 'True'}),
            'last_found': ('django.db.models.fields.DateTimeField', [], {'null': 'True', 'blank': 'True'}),
            'query': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '800'})
        },
        'core.politician': {
            'Meta': {'ordering': "('name',)", 'object_name': 'Politician'},
            'dob': ('django.db.models.fields.DateField', [], {'null': 'True', 'blank': 'True'}),
            'gender': ('django.db.models.fields.CharField', [], {'max_length': '1', 'blank': 'True'}),
            'headshot': ('django.db.models.fields.files.ImageField', [], {'max_length': '100', 'null': 'True', 'blank': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
            'name_family': ('django.db.models.fields.CharField', [], {'max_length': '50', 'blank': 'True'}),
            'name_given': ('django.db.models.fields.CharField', [], {'max_length': '50', 'blank': 'True'}),
            'slug': ('django.db.models.fields.CharField', [], {'db_index': 'True', 'max_length': '30', 'blank': 'True'})
        }
    }

    complete_apps = ['alerts']
