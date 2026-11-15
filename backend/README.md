# README
The backend supports three primary functionalities:

- Scheduling Algorithm: Generates semester-by-semester course plans based on academic history, degree requirements, course availability, prerequisites, and enrollment constraints.
- Manual Transcript Entry: Allows students to enter completed, transfer, and in-progress courses through the terminal.
- Transcript Parser: Extracts academic history from an Illinois Tech unofficial transcript PDF and converts it into structured JSON.

## 1. Backend Components
| Component             | Description |
|-----------------------|-------------|
| Scheduling algorithm | Uses ProcessScheduler and Z3 to generate a course schedule based on degree requirements and academic history.| 
| Manual transcript entry | Collects student course information manually and saves it as JSON.| 
| Transcript parser | Reads Illinois Tech unofficial transcript PDFs, extracts academic history, and validates course records. | 
| Transcript Validator | Normalizes course information, validates records, and categorizes academic history.|
| Requirement Resolver | Identifies remaining mandatory courses, elective choices, in-progress requirements, and alternative program pathways. |

## 2. Environment Setup
All commands should be executed from the HAWKwarts project root directory.
- Dependencies: python -m pip install processscheduler z3-solver pymupdf
- Verifying installation: python -c "import processscheduler, z3, pymupdf; print('Dependencies installed successfully')"

## 3. Scheduling Algorithm
- To run the full scheduling algorithm: python -m backend.scheduler.scheduler_poc --program-id <PROGRAM_ID> --academic-level <ACADEMIC_LEVEL> --enrollment-status <ENROLLMENT_STATUS>
    - <> -> replace with your chosen values: 
        - Program-id: any bachelors and masters degrees available at IIT and supported by the banner data
        - Academic-level: undergraduate/graduate
        - Enrollment-status: part_time/full_time

Depending on the constraints and available courses, the output may indicate:
- success: A schedule satisfying the implemented constraints was generated.
- unsatisfiable: No schedule satisfies all configured constraints.
- no_schedulable_courses: No remaining catalog-available courses were identified for the planning window.

The current scheduling window is:
- Fall 2026
- Spring 2027

**The scheduler checks supported prerequisites, course availability, elective selection, and maximum semester credit loads.** 

## 4. Manual Transcript Entry
Students can enter:
- Completed institutional courses
- Transfer courses
- In-progress courses
  
**Each course includes its code, title, credits, status, and optional academic term and level.**

- To run: python backend/transcript/manual_entry.py
- Saves the file to transcript/results.json
- To use the file with the scheduler: python -m backend.scheduler.scheduler_poc --program-id computer-science:bs-bac-ba --academic-level undergraduate --enrollment-status full_time --history transcript/results.json

**Note: Running manual entry again overwrites the same JSON file. The current terminal workflow does not provide student-specific storage.**

## 5. Transcript Parser
- Run the transcript parser: python backend/transcript/transcript_parser.py "<PDF_PATH>" --output "<OUTPUT_JSON_PATH>"
    - <> -> replace with your chosen values: 
        - Pdf: Required path to an Illinois Tech unofficial transcript PDF
        - Output: Optional destination for the extracted JSON
            - If --output is omitted, the parser defaults to: transcript_results.json
- To use the file with the scheduler: python -m backend.scheduler.scheduler_poc --program-id computer-science:bs-bac-ba --academic-level undergraduate --enrollment-status full_time --history backend/transcript/results.json







