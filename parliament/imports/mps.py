# coding: utf-8

import logging
from parliament.core.models import Politician, Session, Riding, Party
from django.db import transaction
from time import sleep
import hashlib
from urlparse import urljoin

import lxml.html
import requests

logger = logging.getLogger(__name__)


OURCOMMONS_MPS_URL = 'https://www.ourcommons.ca/Members/en/search?caucusId=all&province=all'
IMAGE_PLACEHOLDER_SHA1 = ['e4060a9eeaf3b4f54e6c16f5fb8bf2c26962e15d']

"""
Importers for MP data, from ourcommons.ca or represent.opennorth.ca
"""

def update_mps_from_represent(download_headshots=False, update_all_headshots=False):

    resp = requests.get(
        'https://represent.opennorth.ca/representatives/house-of-commons/?limit=500')
    resp.raise_for_status()
    data = resp.json()

    return _import_mps(data['objects'], download_headshots, update_all_headshots)

def update_mps_from_ourcommons(download_headshots=False, update_all_headshots=False):
    data = scrape_mps_from_ourcommons()
    return _import_mps(data, download_headshots, update_all_headshots)

def _import_mps(objs, download_headshots=False, update_all_headshots=False):
    """
    Updates MP objects from provided list of MP data.
    objs: iterable of dicts in Represent data format
    """

    session = Session.objects.current()

    warnings = []
    errors = []

    pols_seen = set()

    for mp_info in objs:
        try:
            pol = Politician.objects.get_by_name(
                mp_info['name'], session=session, strictMatch=True)
        except Politician.DoesNotExist:
            errors.append(
                "Could not find politician %s in import" % mp_info['name'])
            continue

        pols_seen.add(pol)
        if pol.current_member.party != Party.objects.get_by_name(mp_info.get('party_name')):
            warnings.append("Potential party change for %s: Current %s, potential %s" %
                            (pol, pol.current_member.party, mp_info.get('party_name')))

        def _update(fieldname, value):
            if value == '':
                value = None
            if value == pol.info().get(fieldname):
                return
            if value is None:
                pol.del_info(fieldname)
            else:
                pol.set_info(fieldname, value)

        _update('email', mp_info.get('email'))
        _update('web_site', mp_info.get('personal_url'))

        constituency_offices = []
        for office in mp_info['offices']:
            if office['type'] == 'legislature':
                _update('phone', office.get('tel'))
                _update('fax', office.get(' fax'))
            elif office.get('postal'):
                formatted = office['postal']
                if office.get('tel'):
                    formatted += '\nPhone: %s' % office['tel']
                constituency_offices.append(formatted.replace('\n\n', '\n'))
        if constituency_offices:
            _update('constituency_offices', '\n\n'.join(constituency_offices))

        if (not pol.headshot) and mp_info.get('photo_url'):
            if download_headshots:
                pol.download_headshot(mp_info['photo_url'])
            else:
                warnings.append("Photo available: %s for %s" %
                                (mp_info.get('photo_url'), pol))
        elif mp_info.get('photo_url') and update_all_headshots:
            pol.download_headshot(mp_info['photo_url'])

        if mp_info.get('extra') and mp_info['extra'].get('twitter'):
            screen_name = mp_info['extra']['twitter'].split('/')[-1]
            if not pol.info().get('twitter'):
                pol.set_info('twitter', screen_name)
            elif pol.info().get('twitter') != screen_name:
                warnings.append("Potential twitter change for %s: existing %s new %s" % (
                    pol, pol.info()['twitter'], screen_name))

    missing_pols = set(Politician.objects.current()) - pols_seen
    if missing_pols:
        for p in missing_pols:
            errors.append("Politician %s not seen in import" % p)

    if errors:
        logger.error('\n\n'.join(errors))
    if warnings:
        logger.warning('\n\n'.join(warnings))


@transaction.atomic
def update_ridings_from_represent(boundary_set='federal-electoral-districts'):

    Riding.objects.filter(current=True).update(current=False)

    base_url = 'http://represent.opennorth.ca/'
    riding_list = requests.get(
        urljoin(base_url, '/boundaries/federal-electoral-districts/?limit=500')).json()
    riding_urls = [r['url'] for r in riding_list['objects']]
    for riding_url in riding_urls:
        riding_data = requests.get(urljoin(base_url, riding_url)).json()
        edid = int(riding_data['external_id'])
        name = riding_data['metadata']['ENNAME']
        name_fr = riding_data['metadata']['FRNAME']
        prov = riding_data['metadata']['PROVCODE']
        try:
            riding = Riding.objects.get_by_name(name)
            riding.name = name  # just in case of slight punctuation differences
        except Riding.DoesNotExist:
            riding = Riding(name=name)
        riding.edid = edid
        riding.name_fr = name_fr
        riding.province = prov
        riding.current = True
        riding.save()
        sleep(.1)


# This section of code lifted from
# https://github.com/opencivicdata/scrapers-ca/blob/master/ca/people.py

"""
The CSV at http://www.parl.gc.ca/Parliamentarians/en/members/export?output=CSV
accessible from http://www.parl.gc.ca/Parliamentarians/en/members has no
contact information or photo URLs.
"""

def _scrape_url(url):
    resp = requests.get(url)
    resp.raise_for_status()
    return lxml.html.fromstring(resp.content)

def scrape_mps_from_ourcommons():
    root = _scrape_url(OURCOMMONS_MPS_URL)
    rows = root.xpath(
        '//div[contains(@class, "ce-mip-mp-tile-container")]')
    assert len(rows), "No members found"

    mp_data = (_scrape_ourcommons_row(row) for row in rows)
    return mp_data

def _scrape_ourcommons_row(row):
    d = {}
    d['name'] = row.xpath(
        './/div[@class="ce-mip-mp-name"][1]')[0].text_content()
    d['district_name'] = row.xpath(
        './/div[@class="ce-mip-mp-constituency"][1]')[0].text_content()

    d['province'] = row.xpath(
        './/div[@class="ce-mip-mp-province"][1]')[0].text_content()

    d['party_name'] = row.xpath(
        './/div[@class="ce-mip-mp-party"][1]')[0].text_content()

    url = row.xpath('.//a[@class="ce-mip-mp-tile"]/@href')[0]
    url = urljoin(OURCOMMONS_MPS_URL, url)
    mp_page = _scrape_url(url)
    d['url'] = url

    contact_urls = mp_page.xpath('//*[@id="contact"]/div/p/a/@href')
    emails = [c for c in contact_urls if c.startswith('mailto:')]
    if len(emails) > 1:
        raise ValueError("Too many emails? %s" % emails)
    if emails:
        d['email'] = emails[0].replace('mailto:', '')

    websites = [c for c in contact_urls if c.startswith('http')]
    if len(websites) > 1:
        raise ValueError("Too many websites? %s" % websites)
    if websites:
        d['website'] = websites[0]

    photo = mp_page.xpath(
        './/div[@class="ce-mip-mp-profile-container"]//img/@src')[0]

    if photo:
        photo = urljoin(OURCOMMONS_MPS_URL, photo)
        # Determine whether the photo is actually a generic silhouette
        photo_response = requests.get(photo)
        if (photo_response.status_code == 200 and hashlib.sha1(photo_response.content).hexdigest() not in IMAGE_PLACEHOLDER_SHA1):
            d['photo_url'] = photo

    # Hill Office contacts
    # Now phone and fax are in the same element
    # <p>
    #   Telephone: xxx-xxx-xxxx<br/>
    #   Fax: xxx-xxx-xxx
    # </p>
    offices = [{'type': 'legislature'}]
    phone_el = mp_page.xpath(
        u'.//h4[contains(., "Hill Office")]/../p[contains(., "Telephone")]|.//h4[contains(., "Hill Office")]/../p[contains(., "Téléphone :")]')
    fax_el = mp_page.xpath(
        u'.//h4[contains(., "Hill Office")]/../p[contains(., "Fax")]|.//h4[contains(., "Hill Office")]/../p[contains(., "Télécopieur :")]')

    if phone_el:
        phone = phone_el[0].text_content().strip().splitlines()
        phone = phone[0].replace('Telephone:', '').replace(
            'Téléphone :', '').strip()
        if phone:
            offices[0]['tel'] = phone

    if fax_el:
        fax = fax_el[0].text_content().strip().splitlines()
        fax = fax[0].replace('Fax:', '').replace(
            u'Télécopieur :', '').strip()
        if fax:
            offices[0]['fax'] = fax

    # Constituency Office contacts
    # Some people has more than one, e.g. https://www.ourcommons.ca/Members/en/ben-lobb(35600)#contact
    for i, constituency_office_el in enumerate(mp_page.xpath('.//div[@class="ce-mip-contact-constituency-office-container"]/div')):
        address = constituency_office_el.xpath('./p[1]')[0]
        address = address.text_content().strip().splitlines()
        address = [a.strip() for a in address]

        o = dict(postal='\n'.join(address), type='constituency')

        phone_and_fax_el = constituency_office_el.xpath(
            u'./p[contains(., "Telephone")]|./p[contains(., "Téléphone")]')
        if len(phone_and_fax_el):
            phone_and_fax = phone_and_fax_el[0].text_content(
            ).strip().splitlines()
            # Note that https://www.ourcommons.ca/Members/en/michael-barrett(102275)#contact
            # has a empty value - "Telephone:". So the search / replace cannot include space.
            voice = phone_and_fax[0].replace(
                'Telephone:', '').replace(u'Téléphone :', '').strip()
            if voice:
                o['tel'] = voice
            if len(phone_and_fax) > 1:
                fax = phone_and_fax[1].replace('Fax:', '').replace(
                    u'Télécopieur :', '').strip()
                if fax:
                    o['fax'] = fax
        offices.append(o)
    d['offices'] = offices
    return d
        
