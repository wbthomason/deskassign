'''Create a COVID-19 safe desk use schedule for Cornell CS'''

import logging
from collections import defaultdict
from csv import DictReader, DictWriter
from itertools import product
from json import load as load_json
from math import sqrt, floor
from typing import Dict, Iterable, TextIO

import coloredlogs  # type: ignore
from fire import Fire  # type: ignore
from yaml import load as load_yaml
from z3 import ( # type: ignore
    And,
    Bool,
    If,
    Implies,
    Int,
    Not,
    Optimize,
    Or,
    Real,
    Solver,
    Xor,
    Sum
)

logger = logging.getLogger(__name__)
coloredlogs.install(level='DEBUG')


def create_schedule(desk_data, requests, problem_parameters):
  '''
  Compute a desk use schedule. Takes as arguments:
        desk_data: A dictionary giving for each desk a unique ID, its office number, and coordinates
        of its centroid
        requests: A list of dictionaries giving each student request with student name, assigned
        desk, and list of available time blocks
        problem_parameters: A dictionary giving the safety distance to be used, the office density
        cap, the floor density cap, and the list of time blocks
     Returns: A dictionary with assignments of students to time blocks and desks
  '''
  # Make variables for each desk at each time block where the corresponding student is available
  block_vars = defaultdict(list)
  desk_vars = defaultdict(list)
  student_vars = defaultdict(list)
  office_vars = defaultdict(list)
  floor_vars = defaultdict(list)

  for request in requests:
    desk = request['desk']
    office = desk_data[desk]['office']
    floor_num = floor(int(office) / 100)
    student = request['student_name']
    for block in request['available_times']:
      block_occupancy = Bool(f'{student}_{desk}_{block}')
      block_vars[block].append(block_occupancy)
      desk_vars[desk].append(block_occupancy)
      student_vars[student].append(block_occupancy)
      office_vars[office].append(block_occupancy)
      floor_vars[floor_num].append(block_occupancy)

  # Make variables for the number of time blocks assigned to each student
  count_vars = {}
  for student in student_vars:
    count_vars[student] = Sum(If(block_var, 1, 0) for block_var in student_vars[student])

  # Make the solver
  solver = Optimize()

  # Add constraint that each student is assigned at least one block
  for student, counter in count_vars.items():
    solver.add(counter >= 1)

  # Add mutual exclusion constraints for desks within safety distance of each other
  for desk_1, desk_2 in product(desk_vars.keys(), desk_vars.keys()):
    if desk_1 == desk_2:
      continue

    room1 = desk_data[desk_1]['office']
    room2 = desk_data[desk_2]['office']

    if room1 != room2:
      continue

    x_1 = desk_data[desk_1]['x']
    y_1 = desk_data[desk_1]['y']
    x_2 = desk_data[desk_2]['x']
    y_2 = desk_data[desk_2]['y']

    dist = sqrt((x_2 - x_1)**2 + (y_2 - y_1)**2)
    if dist < problem_parameters['safety_distance']:
      for block_var_1, block_var_2 in zip(desk_vars[desk_1], desk_vars[desk_2]):
        solver.add(Xor(Xor(block_var_1, block_var_2), And(Not(block_var_1), Not(block_var_2))))

  # Add office density constraints
  for office in

  # Add floor density constraints
  # Solve, optimizing for minimal difference in number of time slots assigned
  return False


def output(schedule: Dict[str, Iterable[str]], output_file: TextIO, make_pdfs: bool):
  '''
  Output a schedule (1) as CSV, (2) as a PDF for each student, and (3) as a PDF for each
  office. Takes as arguments:
    schedule: A desk use schedule computed with create_schedule
    output_file: A file object to which to output the CSV
    make_pdfs: A boolean signifying whether or not to generate (2) and (3)
  '''


def main(
    desk_data_filename: str,
    requests_filename: str,
    parameters_filename: str,
    output_filename: str,
    make_pdfs=True
):
  '''
  Main point of entry. Takes as arguments:
      desk_data_filename: Filename for a CSV file giving for each desk a unique ID, its office
      number, and coordinates of its centroid
      requests_filename: Filename for a JSON file giving each student request with student name,
      assigned desk, and list of available time blocks
      parameters_filename: Filename for a YAML file giving the safety distance to be used, the
      office density cap, the floor density cap, and the list of time blocks
      output_filename: Filename to which to output the CSV for a schedule
      make_pdfs: Boolean describing whether the complete (CSV + PDF) output is desired
  '''
  with open(desk_data_filename, newline='') as desk_data_file,\
      open(requests_filename) as requests_file,\
      open(parameters_filename) as parameters_file:
    logger.debug('Loading data')
    desk_data = {row['desk_id']: row for row in DictReader(desk_data_file)}
    requests = load_json(requests_file)
    parameters = load_yaml(parameters_file)
    logger.info('Creating schedule...')
    schedule = create_schedule(desk_data, requests, parameters)

  if not schedule:
    logger.critical('Failed to generate schedule!')
    return

  with open(output_filename, 'w') as output_file:
    output(schedule, output_file, make_pdfs)

  logger.info('All done!')


if __name__ == '__main__':
  Fire(main)
