import json
import io
import requests
import re
import sys
import time
from pprint import pprint
from robobrowser import RoboBrowser
from robobrowser.forms.fields import Input
from bs4 import BeautifulSoup
from geniuslogin import GENIUS_LOGIN, GENIUS_PASSWORD

BASE_URL = 'https://weiapplets.sos.wa.gov/MyVote/services/Candidate.ashx?la=1&c={}&r={}&e=62&b={}'

# ID for the 'Law' song tag on Genius
GENIUS_LAW_TAG_ID = '1424'

GENIUS_ALBUM_NAME = 'King County, WA Local Voter\'s Pamphlet 2016-08-02'
GENIUS_ALBUM_INPUT_ID = 'song_album_appearances_attributes_0_album_name'
GENIUS_ALBUM_INPUT_NAME = 'song[album_appearances_attributes][0][album_name]'
GENIUS_ALBUM_INPUT = """
<input id="{}" class="album_autocomplete ac_input" name="{}" size="30" type="text" autocomplete="off">
""".format(GENIUS_ALBUM_INPUT_ID, GENIUS_ALBUM_INPUT_NAME)
GENIUS_PRODUCER = 'King County Elections'

ALREADY_SUBMITTED = set([
    'Philip L. Cornell',
])


class CandidateData(object):
    def __init__(self, name, race, statement):
        self.name = name
        self.race = race
        self.statement = statement


def process_statement(statement_html):
    soup = BeautifulSoup(statement_html, 'lxml')
    for br in soup.findAll('br'):
        br.replace_with('\n')
    return re.sub(r'\n+', '\n\n', soup.get_text())


def genius_login(browser):
    browser.open('http://genius.com/login')
    form = browser.get_form(class_='new_user_session')
    form['user_session[login]'].value = GENIUS_LOGIN
    form['user_session[password]'].value = GENIUS_PASSWORD
    browser.submit_form(form)


def genius_new(browser, candidate_data, count):
    if candidate_data.name.strip() in ALREADY_SUBMITTED:
        return 0
    browser.open('http://genius.com/new')
    # this doesn't seem to work
    # browser.follow_link(browser.select('#add_album_name')[0])

    form = browser.get_form(class_='new_song')
    form['song[primary_artist]'].value = candidate_data.name
    form['song[title]'].value = '{} Candidacy Statement'.format(candidate_data.race)
    form['song[primary_tag_id]'].value = GENIUS_LAW_TAG_ID
    form['song[lyrics]'].value = candidate_data.statement
    form['song[producer_artists]'].value = GENIUS_PRODUCER
    form['song[writer_artists]'].value = candidate_data.name

    # date
    form['song[release_date(1i)]'].value = '2016'
    form['song[release_date(2i)]'].value = '7'
    form['song[release_date(3i)]'].value = '18'

    album_input_soup = BeautifulSoup(GENIUS_ALBUM_INPUT, 'lxml').select('#{}'.format(GENIUS_ALBUM_INPUT_ID))[0]
    form.add_field(Input(album_input_soup))
    # form[GENIUS_ALBUM_INPUT_NAME] = Input(album_input_soup)
    form[GENIUS_ALBUM_INPUT_NAME].value = GENIUS_ALBUM_NAME

    browser.submit_form(form)

    print('Submission {}: {}. Response: {}'.format(count, candidate_data.name, browser.response.status_code))
    if browser.response.status_code >= 300:
        print('Full response:')
        pprint(browser.response.__dict__)
        raise RuntimeError('Submission failed.')

    # Genius only allows one submission every 5 minutes
    print('Waiting for next submission:', end=' ')
    for thirty_second_chunk in range(10):
        print(10 - thirty_second_chunk, '...', sep='', end=' ')
        time.sleep(30)

    return 1


def main():
    with io.open('CandidateData.json') as data:
        candidate_json = json.load(data)

    count = 0

    browser = RoboBrowser()
    genius_login(browser)

    for category in candidate_json:
        for race in category["Races"]:
            for candidate in race["Candidates"]:
                url = BASE_URL.format(race["CountyCode"], race["RaceID"], candidate["BallotID"])
                category_name = category['Name']
                candidate_json = requests.get(url).json()
                candidate_data = CandidateData(
                    candidate['BallotName'].strip(),
                    race['Name'].strip(),
                    process_statement(candidate_json['statement']['Statement'])
                )
                count += genius_new(browser, candidate_data, count)


if __name__ == "__main__":
    sys.exit(main())

