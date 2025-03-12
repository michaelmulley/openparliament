from django.contrib import admin

from parliament.bills.models import *

class BillOptions(admin.ModelAdmin):
    search_fields = ['number']
    raw_id_fields = ('sponsor_member','sponsor_politician','similar_bills')
    list_display = ('number', 'name', 'session', 'privatemember', 'sponsor_politician', 'added', 'introduced', 'latest_debate_date')
    list_filter = ('institution', 'privatemember', 'added', 'session', 'introduced', 'status_date', 'latest_debate_date')
    ordering = ['-introduced']

class BillTextOptions(admin.ModelAdmin):
    list_display = ['bill', 'docid', 'created']
    search_fields = ['bill__number', 'bill__name_en', 'docid']
    
class VoteQuestionOptions(admin.ModelAdmin):
    list_display = ('number', 'date', 'bill', 'description', 'result')
    raw_id_fields = ('bill', 'context_statement')
    
class MemberVoteOptions(admin.ModelAdmin):
    list_display = ('politician', 'votequestion', 'vote')
    raw_id_fields = ('politician', 'member')
    
class PartyVoteAdmin(admin.ModelAdmin):
    list_display = ('party', 'votequestion', 'vote', 'disagreement')
    

admin.site.register(Bill, BillOptions)
admin.site.register(BillText, BillTextOptions)
admin.site.register(VoteQuestion, VoteQuestionOptions)
admin.site.register(MemberVote, MemberVoteOptions)
admin.site.register(PartyVote, PartyVoteAdmin)
