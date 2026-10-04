import banner
import time
import scrape_to_json

semester = 'Fall 2026' # adjust the semester to be scraped here
subjects_filters = None # to scrape all subjects, or specify like below
# subjects_filters = ['CS']
# subjects_filters = ['CS', 'STAT']

if __name__ == "__main__":

    start1 = time.time()

    # download all pages for Fall 2026 into a folder named .cache
    banner.download_semester(semester, subjects_filters=subjects_filters)
    # parses all the previously downloaded pages in the .cache folder
    courses = banner.parse_semester(semester, subjects=subjects_filters)

    end1 = time.time()
    
    start2 = time.time()
    scrape_to_json.combine_and_clean(semester_filters= [semester], departments_filter=subjects_filters) # turn everything scraped into useable json data
    end2 = time.time()

    print("\nScraping and parsing complete")
    print(f"Time Taken (downloading pages): {end1 - start1:.2f} seconds")
    print(f"Time Taken (converting into JSON): {end2 - start2:.2f} seconds")
    print(f"Overall Execution Time: {end2 - start1:.2f} seconds")


# TO ADD LATER TO README
# TO ADD LATER TO README
# TO ADD LATER TO README
# TO ADD LATER TO README
# TO ADD LATER TO README

# How to use:
# run scrape.py. you can narrow down departments in _download_semester_helper() in banner.py
    # for i, subject in enumerate(subjects): # for all courses
    # for i, subject in enumerate(['CS']): # for CS only (quicker test)
# after running scrape.py, run combine_and_clean.py and JSON files should start appearing in /banner-scraper/data

# TO ADD LATER TO README
# TO ADD LATER TO README
# TO ADD LATER TO README
# TO ADD LATER TO README
# TO ADD LATER TO README