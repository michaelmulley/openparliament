import datetime
import logging
import re
import time
import urllib2

from django.db import transaction

from BeautifulSoup import BeautifulSoup
import lxml.html

from parliament.committees.models import (Committee, CommitteeMeeting,
    CommitteeActivity, CommitteeActivityInSession,
    CommitteeReport, CommitteeInSession)
from parliament.core.models import Session
from parliament.hansards.models import Document

logger = logging.getLogger(__name__)

COMMITTEE_LIST_URL = 'http://www2.parl.gc.ca/CommitteeBusiness/CommitteeList.aspx?Language=E&Parl=%d&Ses=%d&Mode=2'
@transaction.commit_on_success
def import_committee_list(session=None):
    if session is None:
        session = Session.objects.current()

    def make_committee(namestring, parent=None):
        match = re.search(r'^(.+) \(([A-Z0-9]{3,5})\)$', namestring)
        (name, acronym) = match.groups()
        try:
            return Committee.objects.get_by_acronym(acronym, session)
        except Committee.DoesNotExist:
            committee, created = Committee.objects.get_or_create(name_en=name.strip(), parent=parent)
            if created:
                logger.warning(u"Creating committee: %s, %s" % (committee.name_en, committee.slug))
            CommitteeInSession.objects.get_or_create(
                committee=committee, session=session, acronym=acronym)
            return committee
    
    soup = BeautifulSoup(urllib2.urlopen(COMMITTEE_LIST_URL %
        (session.parliamentnum, session.sessnum)))
    for li in soup.findAll('li', 'CommitteeItem'):
        com = make_committee(li.find('a').string)
        for sub in li.findAll('li', 'SubCommitteeItem'):
            make_committee(sub.find('a').string, parent=com)
    
    return True

def _docid_from_url(u):
    return int(re.search(r'DocId=(\d+)&', u).group(1))
    
def _12hr(hour, ampm):
    hour = int(hour)
    hour += 12 * bool('p' in ampm.lower())
    if hour % 12 == 0:
        # noon, midnight
        hour -= 12
    return hour
    
def _parse_date(d):
    """datetime objects from e.g. March 11, 2011"""
    return datetime.date(
        *time.strptime(d, '%B %d, %Y')[:3]
    )


def import_committee_documents(session):
    for comm in Committee.objects.filter(sessions=session).order_by('-parent'):
        # subcommittees last
        import_committee_meetings(comm, session)
        import_committee_reports(comm, session)
        time.sleep(1)

COMMITTEE_MEETINGS_URL = 'http://www2.parl.gc.ca/CommitteeBusiness/CommitteeMeetings.aspx?Cmte=%(acronym)s&Language=E&Parl=%(parliamentnum)d&Ses=%(sessnum)d&Mode=1'
@transaction.commit_on_success
def import_committee_meetings(committee, session):

    acronym = committee.get_acronym(session)
    url = COMMITTEE_MEETINGS_URL % {'acronym': acronym,
        'parliamentnum': session.parliamentnum,
        'sessnum': session.sessnum}
    resp = urllib2.urlopen(url)
    tree = lxml.html.parse(resp)
    root = tree.getroot()
    for mtg_row in root.cssselect('.MeetingTableRow'):
        number = int(re.sub(r'\D', '', mtg_row.cssselect('.MeetingNumber')[0].text))
        assert number > 0
        try:
            meeting = CommitteeMeeting.objects.select_related('evidence').get(
                committee=committee, session=session, number=number)
        except CommitteeMeeting.DoesNotExist:
            meeting = CommitteeMeeting(committee=committee,
                session=session, number=number)
        
        meeting.date = _parse_date(mtg_row.cssselect('.MeetingDate')[0].text)
        
        timestring = mtg_row.cssselect('.MeetingTime')[0].text_content()
        match = re.search(r'(\d\d?):(\d\d) ([ap]\.m\.)(?: - (\d\d?):(\d\d) ([ap]\.m\.))?\s\(',
            timestring, re.UNICODE)
        meeting.start_time = datetime.time(_12hr(match.group(1), match.group(3)), int(match.group(2)))
        if match.group(4):
            meeting.end_time = datetime.time(_12hr(match.group(4), match.group(6)), int(match.group(5)))
        
        notice_link = mtg_row.cssselect('.MeetingPublicationIcon[headers=thNoticeFuture] a')
        if notice_link:
            meeting.notice = _docid_from_url(notice_link[0].get('href'))
        minutes_link = mtg_row.cssselect('.MeetingPublicationIcon[headers=thMinutesPast] a')
        if minutes_link:
            meeting.minutes = _docid_from_url(minutes_link[0].get('href'))
        
        evidence_link = mtg_row.cssselect('.MeetingPublicationIcon[headers=thEvidencePast] a')
        if evidence_link:
            evidence_id = _docid_from_url(evidence_link[0].get('href'))
            if meeting.evidence_id:
                if meeting.evidence.source_id != evidence_id:
                    raise Exception("Evidence docid mismatch for %s %s: %s %s" %
                        (committee.acronym, number, evidence_id, meeting.evidence.source_id))
                else:
                    # Evidence hasn't changed; we don't need to worry about updating
                    continue
            else:
                if Document.objects.filter(source_id=evidence_id).exists():
                    raise Exception("Found evidence source_id %s, but it already exists" % evidence_id)
                meeting.evidence = Document.objects.create(
                    source_id=evidence_id,
                    date=meeting.date,
                    session=session,
                    document_type=Document.EVIDENCE)
        
        meeting.webcast = bool(mtg_row.cssselect('.MeetingStatusIcon img[title=Webcast]'))
        meeting.in_camera = bool(mtg_row.cssselect('.MeetingStatusIcon img[title*="in camera"]'))
        if not meeting.televised:
            meeting.televised = bool(mtg_row.cssselect('.MeetingStatusIcon img[title*="televised"]'))
        if not meeting.travel:
            meeting.travel = bool(mtg_row.cssselect('.MeetingStatusIcon img[title*="travel"]'))
        
        meeting.save()
        
        for study_link in mtg_row.cssselect('.MeetingStudyActivity a'):
            name = study_link.text.strip()
            study = get_activity_by_url(study_link.get('href'))
            meeting.activities.add(study)
    
    return True

COMMITTEE_ACTIVITY_URL = 'http://www.parl.gc.ca/CommitteeBusiness/StudyActivityHome.aspx?Stac=%(activity_id)d&Language=%(language)s&Parl=%(parliamentnum)d&Ses=%(sessnum)d'
def get_activity_by_url(activity_url):
    activity_id = int(re.search(r'Stac=(\d+)', activity_url).group(1))
    session = Session.objects.get_from_parl_url(activity_url)
    try:
        return CommitteeActivityInSession.objects.get(source_id=activity_id).activity
    except CommitteeActivityInSession.DoesNotExist:
        pass

    activity = CommitteeActivity()

    url = COMMITTEE_ACTIVITY_URL % {
        'activity_id': activity_id,
        'language': 'E',
        'parliamentnum': session.parliamentnum,
        'sessnum': session.sessnum
    }
    root = lxml.html.parse(urllib2.urlopen(url)).getroot()

    acronym = re.search(r'\(([A-Z][A-Z0-9]{2,4})\)', root.cssselect('div.HeaderTitle span')[0].text).group(1)

    activity.committee = CommitteeInSession.objects.get(acronym=acronym, session=session).committee

    activity_type = root.cssselect('span.StacTitlePrefix')[0]
    activity.study = 'Study' in activity_type.text
    activity.name_en = activity_type.tail.strip()[:500]

    # See if this already exists for another session
    try:
        activity = CommitteeActivity.objects.get(
            committee=activity.committee,
            study=activity.study,
            name_en=activity.name_en
        )
    except CommitteeActivity.DoesNotExist:
        # Get the French name
        url = COMMITTEE_ACTIVITY_URL % {
            'activity_id': activity_id,
            'language': 'F',
            'parliamentnum': session.parliamentnum,
            'sessnum': session.sessnum
        }
        root = lxml.html.parse(urllib2.urlopen(url)).getroot()
        activity_type = root.cssselect('span.StacTitlePrefix')[0]
        activity.name_fr = activity_type.tail.strip()[:500]

        activity.save()

    if CommitteeActivityInSession.objects.exclude(source_id=activity_id).filter(
            session=session, activity=activity).exists():
        logger.warning("Apparent duplicate activity ID for %s %s %s: %s" %
                     (activity, activity.committee, session, activity_id))
        return activity
    
    CommitteeActivityInSession.objects.create(
        session=session,
        activity=activity,
        source_id=activity_id
    )
    return activity

COMMITTEE_REPORT_URL = 'http://www2.parl.gc.ca/CommitteeBusiness/ReportsResponses.aspx?Cmte=%(acronym)s&Language=E&Mode=1&Parl=%(parliamentnum)d&Ses=%(sessnum)d'
@transaction.commit_on_success
def import_committee_reports(committee, session):
    # FIXME rework to parse out the single all-reports page?
    acronym = committee.get_acronym(session)
    url = COMMITTEE_REPORT_URL % {'acronym': acronym,
        'parliamentnum': session.parliamentnum,
        'sessnum': session.sessnum}
    tree = lxml.html.parse(urllib2.urlopen(url))
    
    def _import_report(report_link, parent=None):
        report_docid = _docid_from_url(report_link.get('href'))
        try:
            report = CommitteeReport.objects.get(committee=committee,
                session=session, source_id=report_docid, parent=parent)
            if report.presented_date:
                # We can consider this report fully parsed
                return report
        except CommitteeReport.DoesNotExist:
            if CommitteeReport.objects.filter(source_id=report_docid).exists():
                if committee.parent and \
                  CommitteeReport.objects.filter(source_id=report_docid, committee=committee.parent).exists():
                    # Reference to parent committee report
                    return None
                else:
                    raise Exception("Duplicate report ID %s on %s" % (report_docid, url))
            report = CommitteeReport(committee=committee,
                session=session, source_id=report_docid, parent=parent)
            report_name = report_link.text.strip()
            match = re.search(r'^Report (\d+) - (.+)', report_name)
            if match:
                report.number = int(match.group(1))
                report.name_en = match.group(2).strip()
            else:
                report.name_en = report_name
            report.name_en = report.name_en[:500]
            report.government_response = bool(report_link.xpath("../span[contains(., 'Government Response')]"))
        
        match = re.search(r'Adopted by the Committee on ([a-zA-Z0-9, ]+)', report_link.tail or '')
        if match:
            report.adopted_date = _parse_date(match.group(1))
        match = re.search(r'Presented to the House on ([a-zA-Z0-9, ]+)', report_link.tail or '')
        if match:
            report.presented_date = _parse_date(match.group(1))
        report.save()
        return report
            
    for item in tree.getroot().cssselect('.TocReportItemText'):
        report_link = item.xpath('./a')[0]
        report = _import_report(report_link)
        for response_link in item.cssselect('.TocResponseItemText a'):
            _import_report(response_link, parent=report)
            
    return True
