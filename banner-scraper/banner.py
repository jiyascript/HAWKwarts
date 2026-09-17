from bs4 import BeautifulSoup, NavigableString, Tag
import requests
import os
import re
import json

def compare_semesters(a_name, b_name):
    '''
    Takes two semester strings as arguments and behave like the python cmp()
    function. Semester strings start with Spring, Summer, Fall, or Winter and end
    with a year (for example, "Fall 2010"). The cmp(a, b) function returns a
    negative value if a comes before b, zero if a == b, and a positive value if a
    comes after b.
    '''
    seasons = { 'Spring': 0, 'Summer': 1, 'Fall': 2, 'Winter': 3 }
    a_season, a_year = a_name.split()
    b_season, b_year = b_name.split()
    year_cmp = (int(a_year) > int(b_year)) - (int(a_year) < int(b_year))
    season_cmp = (seasons[a_season] > seasons[b_season]) - (seasons[a_season] < seasons[b_season])
    return year_cmp if year_cmp else season_cmp

################################################################################
# class structure
################################################################################

class Course:
    '''Banner is represented as a list of Course objects, which own Semester objects.'''

    def __init__(self):
        self.name = ''
        self.title = ''
        self.attributes = ''
        self.description = ''
        self.semesters = []
        self.syllabus_url = None
        self.restrictions = ''
        self.mutual_exclusion = ''

    def get_semester(self, name):
        '''Returns the semester with the given name, creating it first if needed.'''
        for semester in self.semesters:
            if semester.name == name:
                return semester
        semester = Semester()
        semester.name = name
        self.semesters.append(semester)
        return semester

class Semester:
    '''Semester objects own Section objects and are owned by Course objects.'''

    def __init__(self):
        self.name = ''
        self.sections = []

class Section:
    '''Section objects own Meeting objects and are owned by Semester objects.'''

    def __init__(self):
        self.crn = 0
        self.levels = ''
        self.xlist_data = ''
        self.registration_dates = ''
        self.meetings = []

        self.capacity = None
        self.actual = None
        self.remaining = None
        self.waitlist_capacity = None
        self.waitlist_actual = None
        self.waitlist_remaining = None
        
        self.restrictions = ''
        self.prerequisites = ''
        self.general_requirements = ''
        self.cross_listed_courses = ''

class Meeting:
    '''Meeting objects are owned by Section objects.'''

    def __init__(self):
        self.type = ''
        self.days = ''
        self.time = ''
        self.where = ''
        self.date_range = ''
        self.instructors = ''

################################################################################
# xml output
################################################################################

def _courses_to_xml_helper(doc, parent, obj, name):
    element = doc.createElement(name)
    parent.appendChild(element)
    if isinstance(obj, int) or isinstance(obj, float):
        obj = str(obj)
    if isinstance(obj, str):
        element.appendChild(doc.createTextNode(obj))
    elif isinstance(obj, list):
        for x in obj:
            _courses_to_xml_helper(doc, element, x, x.__class__.__name__.lower())
    else:
        for x in obj.__dict__:
            _courses_to_xml_helper(doc, element, obj.__dict__[x], x)

def courses_to_xml(courses):
    '''Takes a list of Course objects and returns an XML string.'''
    import xml.dom.minidom as xml
    doc = xml.Document()
    _courses_to_xml_helper(doc, doc, courses, 'courses')
    return doc.toxml()

################################################################################
# json output
################################################################################

def _courses_to_json_helper(obj):
    if isinstance(obj, int) or isinstance(obj, float) or isinstance(obj, str):
        return obj
    elif isinstance(obj, list):
        return [_courses_to_json_helper(x) for x in obj]
    else:
        return dict((x, _courses_to_json_helper(obj.__dict__[x])) for x in obj.__dict__)

def courses_to_json(courses):
    '''Takes a list of Course objects and returns a JSON string.'''
    import json
    return json.dumps(_courses_to_json_helper(courses))

################################################################################
# downloading
################################################################################

CACHE_DIR = '.cache'
BASE_URL = 'https://ssb.iit.edu'

SCHEDULE_MAIN_URL = BASE_URL + '/bnrprd/bwckschd.p_disp_dyn_sched'
SCHEDULE_DETAIL_URL = '/bnrprd/bwckschd.p_disp_detail_sched'
SCHEDULE_LINK_REGEX = r'^/bnrprd/bwckschd\.p_disp_detail_sched'
SCHEDULE_DATA_PATH = CACHE_DIR + '/%s/schedule/'

CATALOG_MAIN_URL = BASE_URL + '/bnrprd/bwckctlg.p_disp_dyn_ctlg'
CATALOG_DETAIL_URL = '/bnrprd/bwckctlg.p_display_courses'
CATALOG_LINK_REGEX = r'^/bnrprd/bwckctlg\.p_disp_course_detail'
CATALOG_DATA_PATH = CACHE_DIR + '/%s/catalog/'

def _schedule_term_data(term_code):
    return {
        'p_calling_proc': 'bwckschd.p_disp_dyn_sched',
        'p_term': term_code
    }

def _schedule_listing_data(term_code, subject):
    return [
        ('term_in', term_code),
        ('sel_subj', 'dummy'), ('sel_subj', subject),
        ('sel_day', 'dummy'),
        ('sel_schd', 'dummy'), ('sel_schd', '%'),
        ('sel_insm', 'dummy'), ('sel_insm', '%'),
        ('sel_camp', 'dummy'), ('sel_camp', '%'),
        ('sel_levl', 'dummy'), ('sel_levl', '%'),
        ('sel_sess', 'dummy'),
        ('sel_instr', 'dummy'), ('sel_instr', '%'),
        ('sel_ptrm', 'dummy'), ('sel_ptrm', '%'),
        ('sel_attr', 'dummy'), ('sel_attr', '%'),
        ('sel_crse', ''), ('sel_title', ''),
        ('sel_from_cred', ''), ('sel_to_cred', ''),
        ('begin_hh', '0'), ('begin_mi', '0'), ('begin_ap', 'a'),
        ('end_hh', '0'), ('end_mi', '0'), ('end_ap', 'a'),
    ]

def _catalog_listing_data(term_code, subject):
    return [
        ('term_in', term_code),
        ('call_proc_in', 'bwckctlg.p_disp_dyn_ctlg'),
        ('sel_subj', 'dummy'), ('sel_subj', subject),
        ('sel_levl', 'dummy'), ('sel_levl', '%'),
        ('sel_schd', 'dummy'), ('sel_schd', '%'),
        ('sel_coll', 'dummy'), ('sel_coll', '%'),
        ('sel_divs', 'dummy'), ('sel_divs', '%'),
        ('sel_dept', 'dummy'), ('sel_dept', '%'),
        ('sel_attr', 'dummy'), ('sel_attr', '%'),
        ('sel_crse_strt', ''), ('sel_crse_end', ''),
        ('sel_title', ''),
        ('sel_from_cred', ''), ('sel_to_cred', ''),
    ]

def _save(path, data):
    '''Saves data in the given path after creating directories as needed.'''
    try:
        os.makedirs(path[:path.rfind('/')])
    except OSError:
        pass
    open(path, 'wb').write(data)

def _download_semester_helper(semester, start_url, path_template, term_url, term_data_fn, listing_url, listing_data_fn):
    session = requests.Session()

    response = session.get(start_url)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, 'html.parser')

    term_option = None
    for option in soup.find_all('option'):
        if option.get_text(strip=True).startswith(semester):
            term_option = option
            break

    if term_option is None:
        print('error: could not find semester "%s" on page %s' %
              (semester, start_url))
        return

    term_code = term_option.get('value')
    print('found semester:', semester, '->', term_code)

    # term_url = 'https://ssb.iit.edu/bnrprd/bwckgens.p_proc_term_date'
    # term_url = 'https://ssb.iit.edu/bnrprd/bwckctlg.p_disp_cat_term_date'

    response = session.post(term_url, data=term_data_fn(term_code))
    #     'p_calling_proc': 'bwckschd.p_disp_dyn_sched', 
    #     'call_proc_in': 'bwckschd.p_disp_dyn_sched',
    #     'call_proc_in': 'bwckctlg.p_disp_dyn_ctlg',
    #     'p_term': term_code
    #     'cat_term_in': term_code
    response.raise_for_status()

    soup = BeautifulSoup(response.text, 'html.parser')

    subject_select = soup.find('select', {'name': 'sel_subj'})
    if subject_select is None:
        print('error: could not find subject selector')
        return

    subjects = [o.get('value') for o in subject_select.find_all('option') if o.get('value')]

    # download each department schedule
    for i, subject in enumerate(subjects): # for all courses
    # for i, subject in enumerate(['CS']): # for CS only (quicker test)
        response = session.post(listing_url, data=listing_data_fn(term_code, subject))
        response.raise_for_status()

        _save((path_template % semester) + subject + '.html', response.content)
        print('downloaded department %s' % (subject))

def _download_details(directory, link_regex, id_regex, extract_fn):
    session = requests.Session()
    for filename in os.listdir(directory):
        if not filename.endswith('.html'):
            continue

        data = open(directory + filename, encoding='utf-8').read()
        soup = BeautifulSoup(data, 'html.parser')

        subject_details = {}
        for link in soup.find_all(href=re.compile(link_regex)):
            href = BASE_URL + link['href']
            id_match = re.search(id_regex, href)
            if not id_match:
                continue

            response = session.get(href)
            response.raise_for_status()
            detail_soup = BeautifulSoup(response.content, 'html.parser')
            subject_details[id_match.group(1)] = extract_fn(session, detail_soup)

        details_path = directory + filename.replace('.html', '.json')
        _save(details_path, json.dumps(subject_details, indent=2).encode('utf-8'))
        print('downloaded details for %s' % filename)

def _download_schedule_details(semester):
    def extract(session, detail_soup):
        fields = _extract_schedule_detail_fields(detail_soup)
        if fields.get('syllabus_url'):
            syllabus_response = session.get(fields['syllabus_url'])
            syllabus_response.raise_for_status()
            syllabus_soup = BeautifulSoup(syllabus_response.content, 'html.parser')
            fields.update(_extract_syllabus_fields(syllabus_soup))
        return fields

    _download_details(SCHEDULE_DATA_PATH % semester, SCHEDULE_LINK_REGEX, r'crn_in=(\d+)', extract)

def _download_catalog_details(semester):
    _download_details(CATALOG_DATA_PATH % semester, CATALOG_LINK_REGEX, r'crse_numb_in=(\w+)',
                       lambda session, detail_soup: _extract_catalog_detail_fields(detail_soup))

def download_semester(semester_name):
    '''
    Download the entire semester given by the semester name (example: "Fall 2010")
    and store it in the local cache directory.
    '''
    print('downloading', semester_name)

    print('\ndownloading schedule')
    _download_semester_helper(
        semester_name, SCHEDULE_MAIN_URL, SCHEDULE_DATA_PATH,
        term_url='https://ssb.iit.edu/bnrprd/bwckgens.p_proc_term_date',
        term_data_fn=_schedule_term_data,
        listing_url='https://ssb.iit.edu/bnrprd/bwckschd.p_get_crse_unsec',
        listing_data_fn=_schedule_listing_data,
    )

    print('\ndownloading catalog')
    _download_semester_helper(
        semester_name, CATALOG_MAIN_URL, CATALOG_DATA_PATH,
        term_url='https://ssb.iit.edu/bnrprd/bwckctlg.p_disp_cat_term_date',
        term_data_fn=lambda code: {'call_proc_in': 'bwckctlg.p_disp_dyn_ctlg', 'cat_term_in': code},
        listing_url='https://ssb.iit.edu/bnrprd/bwckctlg.p_display_courses',
        listing_data_fn=_catalog_listing_data,
    )
    
    print('\ndownloading catalog details')
    _download_catalog_details(semester_name)
    print('\ndownloading schedule details')
    _download_schedule_details(semester_name)

################################################################################
# parsing
################################################################################

# get the text in between the nodes
def _to_str(element):
    return ''.join(element.findAll(text=True)).replace('\xa0', ' ').strip()

# get the text in between the nodes, but also convert <br> to '\n'
def _to_str_br(element):
    strings = []
    for current in element.currents:
        if isinstance(current, NavigableString):
            strings.append(str(current))
        elif isinstance(current, Tag) and current.name.lower() == 'br':
            strings.append('\n')
    return ''.join(strings).replace('\xa0', ' ').strip()

# normalize whitespace
def _fix(text):
    return re.sub(' +', ' ', text.strip())

def _extract_labeled_sections(text, labels):
    result = {}
    current_label = None
    current_lines = []

    for line in text.split('\n'):
        if line in labels:
            if current_label:
                result[current_label] = _fix(' '.join(current_lines))
            current_label = line
            current_lines = []

        elif current_label:
            current_lines.append(line)

    if current_label:
        result[current_label] = _fix(' '.join(current_lines))
    return result

def _extract_schedule_detail_fields(soup):
    main = soup.find('td', class_='dddefault')
    if main is None:
        return {}

    fields = {
        'capacity': None,
        'actual': None,
        'remaining': None,
        'waitlist_capacity': None,
        'waitlist_actual': None,
        'waitlist_remaining': None,

        'restrictions': '',
        'prerequisites': '',
        'general_requirements': '',
        'cross_listed_courses': '',

        'syllabus_url': None,
        'learning_objectives': '',
        'required_materials': '',
        'technical_requirements': '',
    }

    syllabus_link = main.find('a', string='Syllabus Available')
    if syllabus_link:
        fields['syllabus_url'] = BASE_URL + syllabus_link['href']

    seats_table = main.find('table')
    if seats_table:
        for row in seats_table.find_all('tr'):
            row_text = row.get_text(' ', strip=True)
            match = re.search(r'(Waitlist Seats|Seats)\s+(\d+)\s+(\d+)\s+(\d+)', row_text)
            
            if not match:
                continue

            label, capacity, actual, remaining = match.groups()
            if label == 'Seats':
                fields['capacity'] = int(capacity)
                fields['actual'] = int(actual)
                fields['remaining'] = int(remaining)
            else:
                fields['waitlist_capacity'] = int(capacity)
                fields['waitlist_actual'] = int(actual)
                fields['waitlist_remaining'] = int(remaining)

    labels = ['Restrictions:', 'Prerequisites:', 'General Requirements:', 'Cross List Courses:', 'Mutual Exclusion:']
    full_text = main.get_text('\n', strip=True)
    found = _extract_labeled_sections(full_text, labels)

    fields['restrictions'] = found.get('Restrictions:', '')
    fields['prerequisites'] = found.get('Prerequisites:', '')
    fields['general_requirements'] = found.get('General Requirements:', '')
    fields['cross_listed_courses'] = found.get('Cross List Courses:', '')

    return fields

def _extract_catalog_detail_fields(soup):
    main = soup.find('td', class_='ntdefault')
    if main is None:
        return {}

    labels = ['Restrictions:', 'Mutual Exclusion:']
    full_text = main.get_text('\n', strip=True)
    found = _extract_labeled_sections(full_text, labels)

    return {
        'restrictions': found.get('Restrictions:', ''),
        'mutual_exclusion': found.get('Mutual Exclusion:', ''),
    }

def _extract_syllabus_fields(soup):
    main = soup.find('td', class_='dddefault')
    if main is None:
        return {}

    labels = ['Learning Objectives:', 'Required Materials:', 'Technical Requirements:', 'View Catalog Entry']
    full_text = main.get_text('\n', strip=True)
    found = _extract_labeled_sections(full_text, labels)

    return {
        'learning_objectives': found.get('Learning Objectives:', ''),
        'required_materials': found.get('Required Materials:', ''),
        'technical_requirements': found.get('Technical Requirements:', ''),
    }

def _parse_semester_schedule(semester_name):
    directory = SCHEDULE_DATA_PATH % semester_name
    # filenames = os.listdir(directory)
    filenames = [f for f in os.listdir(directory) if f.endswith('.html')]
    name_to_course = {}

    for i, filename in enumerate(filenames):
        # if not filename.endswith('.html'):
        #     continue
        data = open(directory + filename, encoding='utf-8').read()
        soup = BeautifulSoup(data, 'html.parser')

        details_path = directory + filename.replace('.html', '.json')
        subject_details = {}
        if os.path.exists(details_path):
            subject_details = json.loads(open(details_path, encoding='utf-8').read())

        for link in soup.findAll(href=re.compile(SCHEDULE_LINK_REGEX)):
            # <table>
            #   <tr><th><a>this link</a></th></tr>
            #   <tr><td>the goods</td></tr>
            # </table>
            # a -> th -> tr -> tr -> td
            element = link.parent.parent.nextSibling.nextSibling

            # extract section information from the link
            section = Section()
            title, crn, name, index = link.text.rsplit('-', 3)
            section.crn = int(_fix(crn))

            detail_fields = subject_details.get(str(section.crn), {})
            section.capacity = detail_fields.get('capacity')
            section.actual = detail_fields.get('actual')
            section.remaining = detail_fields.get('remaining')
            section.waitlist_capacity = detail_fields.get('waitlist_capacity')
            section.waitlist_actual = detail_fields.get('waitlist_actual')
            
            section.waitlist_remaining = detail_fields.get('waitlist_remaining')
            section.restrictions = detail_fields.get('restrictions', '')
            section.prerequisites = detail_fields.get('prerequisites', '')
            section.general_requirements = detail_fields.get('general_requirements', '')
            section.cross_listed_courses = detail_fields.get('cross_listed_courses', '')

            # extract section information from the details
            lines = _to_str(element).split('\n')
            items = {}
            for line in lines:
                if ':' in line:
                    key, value = line.split(':', 1)
                    items[key] = value.strip()
            section.levels = _fix(items.get('Levels', ''))
            section.registration_dates = _fix(items.get('Registration Dates', ''))

            # special-case crosslist data
            xlist_data = _to_str_br(element)
            if 'XLIST' in name and 'Associated Term:' in xlist_data:
                section.xlist_data = xlist_data[:xlist_data.find('Associated Term:')].replace('&nbsp;', ' ').strip()

            # extract meetings (xlists don't have tables)
            table = element.find('table')
            section.meetings = []
            if table:
                rows = table.findAll('tr')
                labels = [_fix(_to_str(cell).lower()).replace(' ', '_') for cell in rows[0].findAll('th')]
                for row in rows[1:]:
                    cells = [_fix(_to_str(cell)) for cell in row.findAll('td')]
                    meeting_dict = dict(zip(labels, cells))
                    meeting = Meeting()
                    meeting.type = meeting_dict['type']
                    meeting.days = meeting_dict['days']
                    meeting.time = meeting_dict['time']
                    meeting.where = meeting_dict['where']
                    meeting.date_range = meeting_dict['date_range']
                    meeting.instructors = meeting_dict['instructors']
                    section.meetings.append(meeting)

            # add section to courses, creating a course if necessary
            name = _fix(name)
            title = _fix(title)
            course = name_to_course.setdefault(name, Course())
            if course.title and course.title != title:
                # print('warning(%s): title "%s" and "%s" differ' % (name, course.title, title))
                pass
            course.name = name
            course.title = title
            course.get_semester(semester_name).sections.append(section)
        print('parsed schedule %s' % (filename))
    return list(name_to_course.values())

def _parse_semester_catalog(semester_name):
    directory = CATALOG_DATA_PATH % semester_name
    filenames = os.listdir(directory)
    courses = []

    for i, filename in enumerate(filenames):
        if not filename.endswith('.html'):
            continue

        data = open(directory + filename, encoding='utf-8').read()
        soup = BeautifulSoup(data, 'html.parser')

        details_path = directory + filename.replace('.html', '.json')
        subject_details = {}
        if os.path.exists(details_path):
            subject_details = json.loads(open(details_path, encoding='utf-8').read())

        for title_cell in soup.find_all('td', class_='nttitle'):
            entry = _parse_catalog_entry(title_cell.parent)
            course = Course()

            course.name = entry['name']
            course.title = entry['title']
            course.description = entry['description']
            course.syllabus_url = entry['syllabus_url']

            detail_fields = subject_details.get(entry['number'], {})
            course.restrictions = detail_fields.get('restrictions', '')
            course.mutual_exclusion = detail_fields.get('mutual_exclusion', '')

            courses.append(course)

        print('parsed catalog %s' % (filename))
    return courses

def _parse_catalog_entry(title_row):
    link = title_row.find('a')
    name, title = link.text.split('-', 1)

    number_match = re.search(r'crse_numb_in=(\w+)', link.get('href', ''))
    number = number_match.group(1) if number_match else None

    detail_row = title_row.find_next_sibling('tr')
    detail_cell = detail_row.find('td', class_='ntdefault')

    lines = _to_str(detail_cell).split('\n')
    description = ''
    reading_description = True
    for line in lines:
        line = _fix(line)
        if line.endswith('Credit hours') or line.endswith('Lecture hours') or line.endswith('Lab hours'):
            reading_description = False
        elif reading_description:
            description += line + '\n'

    syllabus_link = detail_cell.find('a', string='Syllabus Available')
    syllabus_url = BASE_URL + syllabus_link['href'] if syllabus_link else None

    return {
        'name': _fix(name),
        'title': _fix(title),
        'description': _fix(description),
        'syllabus_url': syllabus_url,
        'number': number,
    }

def parse_semester(semester_name):
    '''
    Parse the entire semester given by the semester name (example: "Fall 2010")
    and return a list of Course objects for that semester. Must download the
    semester with download_semester() before parsing.
    '''
    print('\nparsing semester', semester_name)
    schedule_courses = _parse_semester_schedule(semester_name)
    catalog_courses = _parse_semester_catalog(semester_name)

    # make indices for quick access
    schedule_index = dict((course.name, course) for course in schedule_courses)
    catalog_index = dict((course.name, course) for course in catalog_courses)

    # consistency check
    for name in schedule_index:
        if name not in catalog_index:
            print('warning(%s): course in schedule but not in catalog' % name)

    # merge the courses
    courses = []
    for name in set(schedule_index) | set(catalog_index):
        course = catalog_index.get(name) or schedule_index[name]

        if name in schedule_index:
            course.semesters = schedule_index[name].semesters

        if name in schedule_index and name in catalog_index:
            if course.title != schedule_index[name].title:
                # print('warning(%s): title mismatch between catalog "%s" and schedule "%s", keeping catalog title' %
                #     (name, course.title, schedule_index[name].title))
                pass

        courses.append(course)

    return courses

################################################################################
# merging
################################################################################

def merge_courses(old_courses, new_courses):
    '''
    Merge courses with the same name in old_courses and new_courses, returns
    the list of merged courses.
    '''
    courses_index = {}
    old_courses_index = dict((course.name, course) for course in old_courses)
    new_courses_index = dict((course.name, course) for course in new_courses)

    courses_index = old_courses_index
    for name in new_courses_index:
        new_course = new_courses_index[name]
        if name not in courses_index:
            courses_index[name] = new_course
        else:
            old_course = courses_index[name]
            old_course.semesters.extend(new_course.semesters)

            if old_course.title != new_course.title:
                print('warning(%s): title "%s" differs from title "%s", using more recent one' % \
                    (name, old_course.title, new_course.title))

            if old_course.attributes != new_course.attributes:
                print('warning(%s): attributes "%s" differ from attributes "%s", using more recent one' % \
                    (name, old_course.attributes, new_course.attributes))

            if old_course.description != new_course.description:
                print('warning(%s): description "%s" differs from description "%s", using more recent one' % \
                    (name, old_course.description, new_course.description))

            # for conflicts, use more recent info (assuming old_course is older than new_course)
            old_course.title = new_course.title
            old_course.attributes = new_course.attributes
            old_course.title = new_course.title

    return list(courses_index.values())

################################################################################
# unit tests
################################################################################

import unittest

class _Tester(unittest.TestCase):
    def test_semester_cmp(self):
        a, b = 'Spring 2009', 'Spring 2010'
        self.assertTrue(compare_semesters(a, b) < 0 and compare_semesters(b, a) > 0)
        a, b = 'Spring 2010', 'Summer 2010'
        self.assertTrue(compare_semesters(a, b) < 0 and compare_semesters(b, a) > 0)
        a, b = 'Summer 2010', 'Fall 2010'
        self.assertTrue(compare_semesters(a, b) < 0 and compare_semesters(b, a) > 0)
        a, b = 'Fall 2010', 'Winter 2010'
        self.assertTrue(compare_semesters(a, b) < 0 and compare_semesters(b, a) > 0)
        a, b = 'Spring 2010', 'Winter 2010'
        self.assertTrue(compare_semesters(a, b) < 0 and compare_semesters(b, a) > 0)
        a, b = 'Spring 2010', 'Spring 2010'
        self.assertTrue(compare_semesters(a, b) == 0)

if __name__ == '__main__':
    import sys
    if 'test' in sys.argv:
        sys.argv.remove('test')
        unittest.main()
