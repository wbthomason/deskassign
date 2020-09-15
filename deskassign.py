'''Create a COVID-19 safe desk use schedule for Cornell CS'''

from collections import defaultdict, namedtuple
from csv import DictReader, DictWriter
from itertools import product
from json import load as load_json
from math import floor, sqrt

from fire import Fire  # type: ignore
from yaml import FullLoader
from yaml import load as load_yaml
from z3 import And, Bool, If, Not, Optimize, Sum, Xor, sat  # type: ignore
from fpdf import FPDF, HTMLMixin

BlockVar = namedtuple('BlockVar', 'b v')


class PDF(FPDF, HTMLMixin):
  pass


def create_schedule(desk_data, requests, problem_parameters):
  '''
  Compute a desk use schedule. Takes as arguments:
        desk_data: A dictionary giving for each desk a unique ID, its office number, and coordinates
        of its centroid
        requests: A list of dictionaries giving each student request with student name, assigned
        desk, and list of available time blocks
        problem_parameters: A dictionary giving the safety distance to be used, the office density
        cap, the floor density cap, and the list of time blocks
     Returns: A dictionary with assignments of students to time blocks and desks, and a dictionary
     with the same information per office
  '''
  # Make variables for each desk at each time block where the corresponding student is available
  print('Creating model...')
  desk_vars = defaultdict(list)
  student_vars = defaultdict(list)
  office_vars = defaultdict(list)
  floor_vars = defaultdict(list)
  print('Creating variables...')
  for request in requests:
    desk = request['desk']
    office = desk_data[desk]['office']
    floor_num = floor(int(office) / 100)
    student = request['student_name']
    block_vars = [
        BlockVar(block, Bool(f'{student}/{desk}/{block}')) for block in request['available_times']
    ]
    desk_vars[desk].extend(block_vars)
    student_vars[student].extend(block_vars)
    office_vars[office].extend(block_vars)
    floor_vars[floor_num].extend(block_vars)

  # Make variables for the number of time blocks assigned to each student
  count_vars = {}
  for student in student_vars:
    count_vars[student] = Sum([If(block_var.v, 1, 0) for block_var in student_vars[student]])

  # Make the solver
  solver = Optimize()

  print('Adding constraints...')
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

    x_1 = float(desk_data[desk_1]['x'])
    y_1 = float(desk_data[desk_1]['y'])
    x_2 = float(desk_data[desk_2]['x'])
    y_2 = float(desk_data[desk_2]['y'])

    dist = sqrt((x_2 - x_1)**2 + (y_2 - y_1)**2)
    if dist < problem_parameters['safety_distance']:
      for block_var_1, block_var_2 in product(desk_vars[desk_1], desk_vars[desk_2]):
        if block_var_1.b == block_var_2.b:
          solver.add(
              Xor(Xor(block_var_1.v, block_var_2.v), And(Not(block_var_1.v), Not(block_var_2.v)))
          )

  # Add office density constraints
  for office, occupancy_vars in office_vars.items():
    office_block_counters = defaultdict(list)
    for occupancy_var in occupancy_vars:
      office_block_counters[occupancy_var.b].append(If(occupancy_var.v, 1, 0))

    for block in office_block_counters.values():
      solver.add(Sum(block) <= problem_parameters['office_occupancy_cap'])

  # Add floor density constraints
  for floor_num, occupancy_vars in floor_vars.items():
    floor_block_counters = defaultdict(list)
    for occupancy_var in occupancy_vars:
      floor_block_counters[occupancy_var.b].append(If(occupancy_var.v, 1, 0))

    for block in floor_block_counters.values():
      solver.add(Sum(block) <= problem_parameters['floor_occupancy_cap'])

  # Solve, optimizing for minimal difference in number of time slots assigned
  def abs(x):
    return If(x >= 0, x, -x)

  avg = Sum(list(count_vars.values())) / len(student_vars)
  diffs = [abs(avg - counter) for counter in count_vars.values()]
  solver.maximize(Sum(list(count_vars.values())) - Sum(diffs))
  print('Attempting to solve model...')
  if solver.check() == sat:
    print('Success! Extracting schedule...')
    model = solver.model()
    # Extract the schedule of assignments
    student_schedules = defaultdict(list)
    office_schedules = defaultdict(list)
    for var_name in model:
      student, desk, block = var_name.name().split('/')
      desk = int(desk)
      block = int(block)
      office = desk_data[desk]['office']
      if model[var_name]:
        student_schedules[student].append((office, desk, block))
        office_schedules[office].append((student, desk, block))
    return student_schedules, office_schedules

  print('Failure! No solution')
  return None


def output(schedule, output_file, make_pdfs):
  '''
  Output a schedule (1) as CSV, (2) as a PDF for each student, and (3) as a PDF for each
  office. Takes as arguments:
    schedule: A desk use schedule computed with create_schedule
    output_file: A file object to which to output the CSV
    make_pdfs: A boolean signifying whether or not to generate (2) and (3)
  '''
  student_schedules, office_schedules = schedule
  output_writer = DictWriter(output_file, fieldnames=['student', 'office', 'desk', 'block'])
  print('Writing full CSV schedule...')
  output_writer.writeheader()
  for office, assignments in office_schedules.items():
    for student, desk, block in assignments:
      output_writer.writerow({'student': student, 'office': office, 'desk': desk, 'block': block})

  if make_pdfs:
    print('Generating student PDFs...')
    for student, assignments in student_schedules.items():
      title = f'Desk use assignments for {student}'
      pdf = PDF()
      pdf.add_page()
      pdf.set_xy(0.0, 0.0)
      pdf.set_font('Arial', 'B', 20)
      pdf.cell(ln=2, w=210.0, h=10.0, align='C', txt=title)
      pdf.set_title(title)
      pdf.set_font('Arial', '', 12)
      desk_blocks = defaultdict(list)
      for office, desk, block in assignments:
        desk_blocks[(office, desk)].append(block)

      for office_desk in desk_blocks:
        office, desk = office_desk
        pdf.cell(
            h=10,
            w=210.0,
            align='C',
            txt=f'You may use your desk ({desk}, in Room {office}) during the following time blocks:'
        )

        block_list = ['<ul>']
        for block in desk_blocks[(office, desk)]:
          block_list.append(f'<li>{block}</li>')

        block_list.append('</ul>')
        pdf.write_html('\n'.join(block_list))

      pdf.output(f'{student}.pdf', 'F')

    print('Generating office PDFs...')
    for office, assignments in office_schedules.items():
      title = f'Desk use assignments for Room {office}'
      pdf = PDF()
      pdf.add_page()
      pdf.set_xy(0.0, 0.0)
      pdf.set_font('Arial', 'B', 20)
      pdf.cell(ln=2, w=210, h=10, align='C', txt=title)
      pdf.set_title(title)
      pdf.set_font('Arial', '', 12)
      block_occupancy = defaultdict(list)
      for student, desk, block in assignments:
        block_occupancy[block].append((student, desk))

      for block in block_occupancy:
        pdf.set_font('Arial', 'B', 12)
        pdf.cell(h=10, w=210, txt=f'Allowed usage for block {block}:')
        pdf.set_font('Arial', '', 12)
        pdf.cell(
            h=10,
            w=210,
            txt=', '.join([f'{student} at desk {desk}' for student, desk in block_occupancy[block]])
        )

      pdf.output(f'{office}.pdf', 'F')


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
    print('Loading data...')
    desk_data = {int(row['desk_id']): row for row in DictReader(desk_data_file)}
    requests = load_json(requests_file)
    parameters = load_yaml(parameters_file, FullLoader)
    schedules = create_schedule(desk_data, requests, parameters)

  if not schedules:
    print('Failed to generate schedule!')
    return

  with open(output_filename, 'w') as output_file:
    output(schedules, output_file, make_pdfs)

  print('All done!')


if __name__ == '__main__':
  Fire(main)
