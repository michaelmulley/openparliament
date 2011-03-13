from django.contrib import admin

from parliament.bills.models import *

class BillOptions(admin.ModelAdmin):
    raw_id_fields = ('sponsor_member','sponsor_politician')
    list_display = ('number', 'name', 'session', 'privatemember', 'sponsor_politician', 'added')
    list_filter = ('institution', 'privatemember', 'added')
    
class VoteQuestionOptions(admin.ModelAdmin):
    list_display = ('number', 'date', 'bill', 'description', 'result')
    raw_id_fields = ('bill',)
    
class MemberVoteOptions(admin.ModelAdmin):
    list_display = ('politician', 'votequestion', 'vote')
    raw_id_fields = ('politician', 'member')
    
class PartyVoteAdmin(admin.ModelAdmin):
    list_display = ('party', 'votequestion', 'vote', 'disagreement')
    

admin.site.register(Bill, BillOptions)
admin.site.register(VoteQuestion, VoteQuestionOptions)
admin.site.register(MemberVote, MemberVoteOptions)
admin.site.register(PartyVote, PartyVoteAdmin)