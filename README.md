# Usage
Either run `poetry install` (see https://python-poetry.org/) or manually install the dependencies
listed in `pyproject.toml` using `pip`.

You will need a recent version of Python (Python 3.8 was used in development).

Run with:
```shell
python deskassign.py DESK_DATA REQUESTS PARAMETERS OUTPUT_FILENAME
```
or
```shell
python deskassign.py -- --help
```
to see more detailed usage information.

`DESK_DATA` must be a CSV file with the header `desk_id,office,x,y`, where `desk_id` is a unique ID
for each desk, `office` is the room number of the office in which the desk is located, and `x` and
`y` are the coordinates of the centroid of the desk in its office.

`REQUESTS` must be a JSON file with a list of objects corresponding to student usage requests. A
student usage request must contain a desk number in the field `"desk"`, a name in the field
`"student_name"`, and a list of time block IDs in the field `"available_times"`, corresponding to
the time blocks in which the student could be at their desk.

`PARAMETERS` must be a YAML file with problem parameters including `safety_distance` (the minimum
allowable distance between occupied desks), `office_occupancy_cap` (the maximum simultaneous
occupants of an office), and `floor_occupancy_cap` (the maximum simultaneous occupants of a floor in
Gates).

`OUTPUT_FILENAME` is the desired filename for the CSV output. There is also a `--make_pdfs` flag
which defaults to `True` and controls whether PDFs for students and offices will be generated.

Examples of the above files are included in this repository.
