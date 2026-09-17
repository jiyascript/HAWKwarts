import banner
semester = 'Fall 2026'

# download all pages for Fall 202pyth6 into a folder named .cache
banner.download_semester(semester)

# scrape all the previously downloaded pages in the .cache folder
courses = banner.parse_semester(semester)

print("\ndone")



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