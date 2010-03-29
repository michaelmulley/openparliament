# encoding: utf-8
import datetime
from south.db import db
from south.v2 import DataMigration
from django.db import models

from parliament.hansards.models import Statement

class Migration(DataMigration):
    
    def forwards(self, orm):
        sessionsequence = {}
        sessions = {}
        sessquery = orm.Session.objects.all().order_by('start')
        for i in range(len(sessquery)):
            sessionsequence[sessquery[i].id] = i
            sessions[sessquery[i].id] = sessquery[i]
            
        def update_member(member):
            print "UPDATING,"
            sess = sessions[member.session_id]
            member.start_date = sess.start
            member.end_date = sess.end
            member.save()
            member.sessions.add(sess.id)
            return member
            
        def merge_members(master, merger):
            print "MERGING,"
            sess = sessions[merger.session_id]
            master.end_date = sess.end
            master.session_id = merger.session_id
            master.save()
            master.sessions.add(sess.id)
            Statement.objects.filter(member=merger).update(member=master)
            merger.delete()
            return master
        
        for pol in orm.Politician.objects.all().annotate(electedcount=models.Count('electedmember')).filter(electedcount__gte=1):
            print pol.name,
            # For each politician who's been elected
            members = orm.ElectedMember.objects.filter(politician=pol).order_by('session__start')
            last = None
            for member in members:
                if (last
                        and last.party == member.party
                        and last.riding == member.riding
                        and sessionsequence[member.session_id] == (sessionsequence[last.session_id] + 1)):
                    last = merge_members(master=last, merger=member)
                else:
                    last = update_member(member)
                
    
    
    def backwards(self, orm):
        "Write your backwards methods here."
    
    models = {
        'core.electedmember': {
            'Meta': {'object_name': 'ElectedMember'},
            'end_date': ('django.db.models.fields.DateField', [], {'null': 'True', 'blank': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'party': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['core.Party']"}),
            'politician': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['core.Politician']"}),
            'riding': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['core.Riding']"}),
            'session': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['core.Session']"}),
            'sessions': ('django.db.models.fields.related.ManyToManyField', [], {'related_name': "'sessionstmp'", 'to': "orm['core.Session']"}),
            'start_date': ('django.db.models.fields.DateField', [], {})
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
            'headshot': ('django.db.models.fields.files.ImageField', [], {'max_length': '100', 'null': 'True', 'blank': 'True'}),
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
