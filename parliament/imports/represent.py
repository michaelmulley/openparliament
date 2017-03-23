"""
Update MP biographical data from the lovely Represent API
"""

from urlparse import urljoin
from time import sleep

from django.db import transaction

import requests

from parliament.core.models import Politician, Session, Riding

import logging
logger = logging.getLogger(__name__)

def update_mps_from_represent(download_headshots=False, update_all_headshots=False):

    resp = requests.get('https://represent.opennorth.ca/representatives/house-of-commons/?limit=500')
    resp.raise_for_status()
    data = resp.json()

    session = Session.objects.current()

    warnings = []
    errors = []

    for mp_info in data['objects']:
        try:
            pol = Politician.objects.get_by_name(mp_info['name'], session=session, strictMatch=True)
        except Politician.DoesNotExist:
            errors.append("Could not find politician %s from Represent" % mp_info['name'])
            continue

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
                warnings.append("Photo available: %s for %s" % (mp_info.get('photo_url'), pol))
        elif mp_info.get('photo_url') and update_all_headshots:
            pol.download_headshot(mp_info['photo_url'])

        if mp_info.get('extra') and mp_info['extra'].get('twitter'):
            screen_name = mp_info['extra']['twitter'].split('/')[-1]
            if not pol.info().get('twitter'):
                pol.set_info('twitter', screen_name)
            elif pol.info().get('twitter') != screen_name:
                warnings.append("Potential twitter change for %s: existing %s new %s" % (
                    pol, pol.info()['twitter'], screen_name))
    
    if errors:
        logger.error('\n\n'.join(errors))
    if warnings:
        logger.warning('\n\n'.join(warnings))


@transaction.atomic
def update_ridings_from_represent(boundary_set='federal-electoral-districts'):

    Riding.objects.filter(current=True).update(current=False)

    base_url = 'http://represent.opennorth.ca/'
    riding_list = requests.get(urljoin(base_url, '/boundaries/federal-electoral-districts/?limit=500')).json()
    riding_urls = [r['url'] for r in riding_list['objects']]
    for riding_url in riding_urls:
        riding_data = requests.get(urljoin(base_url, riding_url)).json()
        edid = int(riding_data['external_id'])
        name = riding_data['metadata']['ENNAME']
        name_fr = riding_data['metadata']['FRNAME']
        prov = riding_data['metadata']['PROVCODE']
        try:
            riding = Riding.objects.get_by_name(name)
            riding.name = name # just in case of slight punctuation differences
        except Riding.DoesNotExist:
            riding = Riding(name=name)
        riding.edid = edid
        riding.name_fr = name_fr
        riding.province = prov
        riding.current = True
        riding.save()
        sleep(.1)

