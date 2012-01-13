# TODO: Tests, docstrings, get a girlfriend

import logging
import gevent
import json, requests
from difflib import SequenceMatcher as smatcher
from datetime import datetime

GRAPH_API = 'https://graph.facebook.com'


def fql(query, token=None):
    ENDPOINT = 'https://api.facebook.com/method/%s'
    if type(query) == dict:
        method = 'fql.multiquery'
        query_key = 'queries'
    elif type(query) == str:
        method = 'fql.query'
        query_key = 'query'
    params = {
            'format': 'JSON',
            query_key: str(query),
    }
    if token:
        params['access_token'] = token
    res = requests.get(ENDPOINT % method, params=params)
    return json.loads(res.content)


def get_friends_info(token):
    query = {}
    fields = [
            'uid,' 'name',
            'languages', 'locale', 'current_location', 'hometown_location',
            'significant_other_id', 'meeting_sex', 'meeting_for', # for single
            'sex', # filter by sex
            'relationship_status', # relationship
            'birthday_date', # by age: 07/05/1983
            'music', # by music
            'religion', # by religion
            ]

    # first get friends
    query['friends'] = " \
            SELECT %s FROM user WHERE uid IN \
                (SELECT uid1 FROM friend WHERE uid2=me())" % ','.join(fields)
                # AND \
                #   (current_location OR hometown_location OR languages)"

    # then get the corresponding latlongs
    #query['current_latlong'] = "SELECT page_id, latitude, longitude FROM place \
    #        WHERE page_id IN (SELECT current_location.id FROM #friends WHERE current_location)"

    #query['home_latlong'] = "SELECT page_id, latitude, longitude FROM place \
    #        WHERE page_id IN (SELECT hometown_location.id FROM #friends where hometown_location)"

    return fql(query, token)


def is_in(orig, sequence, thresh=0.63):
    """Return true if original is close to an item in sequence"""
    orig = orig.lower()
    sequence = [item.lower() for item in sequence]
    for item in sequence:
        if smatcher(a=orig, b=item, autojunk=False).quick_ratio() > thresh:
            return True
    return False


def match_locales(locales, friends):
    """Filter by locale"""
    locales = locales.replace('_',',')
    locales = set(map(lambda l: l.lower().strip(), locales.split(',')))
    return filter(lambda f: f['locale'].lower().split('_')[0] in locales or
                            f['locale'].lower().split('_')[1] in locales,
                            friends)


def match_countries(countries, friends):
    """Filter by cur_country and home_country (additive)"""
    countries = map(lambda c: c.strip(), countries.split(','))
    return filter(
            lambda f: # check for each friend 'f' if countries match
            (f['current_location'] and \
                    is_in(f['current_location'].get('country'), countries)) or
            (f['hometown_location'] and \
                    is_in(f['hometown_location'].get('country'), countries)),
            friends
            )


def match_languages(languages, friends):
    """Filter by friends by language (additive)"""
    # get normalized list from comma-separated string
    langs = map(lambda x: x.lower().strip(), languages.split(','))
    # include any users that have listed a language from 'langs'
    returnme = []
    for friend in friends:
        if not friend['languages']:
            continue
        friend_langs = map(lambda l: l['name'], friend['languages'])
        for lang in langs:
            if is_in(lang, friend_langs):
                returnme.append(friend)
                break # go to next friend
    return returnme


def match_sex(sex, friends):
    """Filter by sex (exclude rest)"""
    sex = sex.strip()[0].lower()
    returnme = []
    for f in friends:
        f_sex = f.get('sex')
        if f_sex and (f_sex[0].lower() == sex):
            returnme.append(f)
    return returnme


def match_age(age_min, age_max, friends):
    """Filter by age (exclude rest)"""
    age_min = int(age_min) if age_min else 0
    age_max = int(age_max) if age_max else 200
    now = datetime.now()
    returnme = []
    for f in friends:
        birth_str = f.get('birthday_date')
        if not birth_str or len(birth_str) < 10:
            continue
        birth_time = datetime.strptime(birth_str, '%m/%d/%Y')
        age = (now - birth_time).days / 365. # in years
        if (age >= age_min) and (age <= age_max):
            returnme.append(f)
    return returnme


def match_single(friends):
    """Return only singles"""
    return [f for f in friends if f.get('relationship_status', '') == "Single"]


def filter_friends(info,
        locale=None,
        countries=None,
        languages=None,
        sex=None,
        age_min=None,
        age_max=None,
        single=None,
        **kwargs):
    """Filters the friends got from FQL and returns uids

    Arguments:
    Comma-separated strings.

    Return:
    List of uids of matching friends.

    """
    friends_info = filter(lambda r: r['name'] == 'friends',
            info)[0]['fql_result_set']

    result_geolang = []

    if locale:
        result_geolang += match_locales(locale, friends_info)

    if countries:
        result_geolang += match_countries(countries, friends_info)

    if languages:
        result_geolang += match_languages(languages, friends_info)

    # if no filters were active, include all
    if not (locale or countries or languages):
        result_geolang = friends_info

    ## Here the second pass starts, we begin with all friends again
    result_demog = friends_info

    if sex:
        result_demog = match_sex(sex, result_demog)

    if age_min or age_max:
        result_demog = match_age(age_min, age_max, result_demog)

    if single and single.lower() == "on":
        result_demog = match_single(result_demog)

    # get unique IDs from the two filter runs
    ids_geo = set(map(lambda friend: friend['uid'], result_geolang))
    ids_sex = set(map(lambda friend: friend['uid'], result_demog))

    return list(ids_geo.intersection(ids_sex))


def create_friends_list(list_name, uids, token):
    list_name = list_name[:25].strip() # facebook limitation

    res = requests.post(GRAPH_API+'/me/friendlists',
            data={'access_token': token, 'name': list_name})

    if res.ok:
        res = json.loads(res.content)
        list_id = res['id']
        logging.info('List id: %s' % str(list_id))
    elif res.status_code == 400:
        logging.error('Could not create list. Duplicate name?')
        raise Exception(res.content)
    else:
        logging.error('Could not create list for unknown reason.')
        raise Exception(res.content)

    # OK, list exists, now add the users
    # batch requests can have a maximum of 50 single requests[
    max_reqs_per_batch = 50
    start_indices = range(0, len(uids), max_reqs_per_batch)

    jobs = []
    for start_index in start_indices:
        batch = [{'method': 'POST', 'relative_url': '%s/members/%s' % \
                (str(list_id), str(uid))} \
                for uid in uids[start_index:start_index+max_reqs_per_batch]]
        job = gevent.spawn(requests.post, GRAPH_API,
                data={'access_token': token, 'batch': json.dumps(batch)})
        jobs.append(job)

    gevent.joinall(jobs)
    for job in jobs:
        if not job.successful() or not job.value.ok:
            if job.value:
                logging.error(job.value.status_code)
                logging.error(job.value.content)
            raise Exception('Batch request failed')

    return list_id


def del_all_user_created_lists_for_token(token):
    params = {'access_token': token}
    lists = requests.get(GRAPH_API+'/me/friendlists', params=params)
    lists = json.loads(lists.content)['data']
    delme = [li['id'] for li in lists if li['list_type'] == 'user_created']
    return [requests.delete( GRAPH_API + '/' + id, params=params ) \
            for id in delme]
