import banner
import time
import subprocess

semester = 'Fall 2026'

if __name__ == "__main__":

    start1 = time.time()

    # download all pages for Fall 2026 into a folder named .cache

    # adjust the departments to be scraped here #
    # banner.download_semester(semester) # default: all
    # banner.download_semester(semester, subjects_filters=['CS', 'MATH'])
    banner.download_semester(semester, subjects_filters=['STAT'])

    # scrape all the previously downloaded pages in the .cache folder
    courses = banner.parse_semester(semester)

    end1 = time.time()
    start2 = time.time()

    # runs combine_and_clean to jsonify everything
    subprocess.run(["python", "combine_and_clean.py"], check=True)

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