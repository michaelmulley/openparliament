from decimal import Decimal
import re
import urllib.request, urllib.error, urllib.parse

from django.db import transaction
import requests

from parliament.core import parsetools
from parliament.core.models import Riding, Party, Politician, ElectedMember, Session
from parliament.elections.models import Candidacy, Election

class PreliminaryResultsError(Exception):
    pass

@transaction.atomic
def import_ec_results(election, url="http://enr.elections.ca/DownloadResults.aspx",
        allow_preliminary=False):
    """Import an election from the text format used on enr.elections.ca
    (after the 2011 general election)"""

    preliminary_results = {}
    validated_results = {}

    for line in requests.get(url).text.split('\n'):
        line = line.split('\t')
        edid = line[0]
        if not edid.isdigit():
            continue
        result_type = line[3]
        if result_type == 'preliminary':
            preliminary_results.setdefault(edid, []).append(line)
        elif result_type == 'validated':
            validated_results.setdefault(edid, []).append(line)
        else:
            raise Exception("%s not an acceptable type" % result_type)

    if (not allow_preliminary) and len(preliminary_results) > len(validated_results):
        raise PreliminaryResultsError("Some results are only preliminary, stopping")

    if len(validated_results) > len(preliminary_results):
        raise Exception("Huh?")

    for edid in preliminary_results:
        if edid in validated_results:
            lines = validated_results[edid]
        elif allow_preliminary:
            lines = preliminary_results[edid]
        else:
            assert False

        riding = Riding.objects.get(current=True, edid=edid)

        for line in lines:
            last_name = line[5]
            first_name = line[7]
            party_name = line[8]
            votetotal = int(line[10])
            votepercent = Decimal(line[11])

            try:
                party = Party.objects.get_by_name(party_name)
            except Party.DoesNotExist:
                print("No party found for %r" % party_name)
                print("Please enter party ID:")
                party = Party.objects.get(pk=input().strip())
                party.add_alternate_name(party_name)
                print(repr(party.name))
                
            Candidacy.objects.create_from_name(
                first_name=first_name,
                last_name=last_name,
                party=party,
                riding=riding,
                election=election,
                votetotal=votetotal,
                votepercent=votepercent,
                elected=None
            )

    election.label_winners()

def load_byelection():
    """
    Interactive script to load a by-election from the Elections Canada results
    """
    print("Enter the date of the by-election (YYYY-MM-DD):")
    eldate = input().strip()
    el, _ = Election.objects.get_or_create(date=eldate, byelection=True)
    try:
        import_ec_results(el)
    except PreliminaryResultsError:
        print("Some results are preliminary, continue? (y/n)")
        if input().strip().lower() == 'y':
            import_ec_results(el, allow_preliminary=True)
        else:
            raise
    
    return el.create_members(Session.objects.current())


PROVINCES_NORMALIZED = {
    'ab': 'AB',
    'alberta': 'AB',
    'bc': 'BC',
    'b.c.': 'BC',
    'british columbia': 'BC',
    'mb': 'MB',
    'manitoba': 'MB',
    'nb': 'NB',
    'new brunswick': 'NB',
    'nf': 'NL',
    'nl': 'NL',
    'newfoundland': 'NL',
    'newfoundland and labrador': 'NL',
    'nt': 'NT',
    'northwest territories': 'NT',
    'ns': 'NS',
    'nova scotia': 'NS',
    'nu': 'NU',
    'nunavut': 'NU',
    'on': 'ON',
    'ontario': 'ON',
    'pe': 'PE',
    'pei': 'PE',
    'p.e.i.': 'PE',
    'prince edward island': 'PE',
    'pq': 'QC',
    'qc': 'QC',
    'quebec': 'QC',
    'sk': 'SK',
    'saskatchewan': 'SK',
    'yk': 'YT',
    'yt': 'YT',
    'yukon': 'YT',
    'yukon territory': 'YT',
}        

