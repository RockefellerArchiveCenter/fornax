import csv
import datetime
from os import makedirs, path, walk

from csvvalidator import CSVValidator, RecordError, enumeration


class CsvCreator:
    """Creates and validates Archivematica-compliant CSV containing PREMIS rights"""

    def __init__(self):
        self.field_names = ['file', 'basis', 'status', 'determination_date', 'jurisdiction', 'start_date', 'end_date', 'terms', 'citation', 'note', 'grant_act', 'grant_restriction', 'grant_start_date', 'grant_end_date', 'grant_note', 'doc_id_type', 'doc_id_value', 'doc_id_role']

    def run(self, bag_path, rights_statements):
        self.bag_path = bag_path
        self.rights_statements = rights_statements
        self.csv_filepath = path.join(bag_path, 'data', 'metadata', 'rights.csv')
        csvwriter = self.setup_csv_file()
        for (dirpath, dirnames, filenames) in walk(path.join(self.bag_path, 'data', 'objects')):
            for file in filenames:
                rights_rows = self.get_rights_rows(dirpath, file)
                for rights_row in rights_rows:
                    csvwriter.writerow(rights_row)

    def setup_csv_file(self):
        """
        If file already exists, sets mode to append. Otherwise, creates new file and
        writes a header row.
        """
        if not path.isfile(self.csv_filepath):
            if not path.exists(path.dirname(self.csv_filepath)):
                makedirs(path.dirname(self.csv_filepath))
            csvfile = open(self.csv_filepath, 'w')
            csvwriter = csv.writer(csvfile)
            csvwriter.writerow(self.field_names)
        else:
            csvfile = open(self.csv_filepath, 'a')
            csvwriter = csv.writer(csvfile)
        return csvwriter

    def get_rights_rows(self, dirpath, file):
        """Gets rows for each rights statement for a file"""
        path_to_file = path.join(dirpath.split(self.bag_path)[1], file).lstrip('/')
        rights_rows = []
        for rights_statement in self.rights_statements:
            if len(rights_statement.get('rights_granted')) == 0:
                rights_row = []
                rights_row.append(path_to_file)
                for basis_value in self.get_basis_fields(rights_statement):
                    rights_row.append(basis_value)
                rights_row = rights_row[:10] + ([''] * 5) + rights_row[11:]
                rights_rows.append(rights_row)
            else:
                for rights_granted in rights_statement.get('rights_granted'):
                    rights_row = []
                    rights_row.append(path_to_file)
                    for basis_value in self.get_basis_fields(rights_statement):
                        rights_row.append(basis_value)
                    rights_row[10:10] = self.get_grant_restriction(rights_granted)
                    rights_rows.append(rights_row)
        return rights_rows

    def get_basis_fields(self, rights_statement):
        """docstring for get_basis_fields"""
        basis_fields = ['rights_basis', 'status', 'determination_date', 'jurisdiction', 'start_date', 'end_date', 'terms', 'citation', 'note', 'doc_id_type', 'doc_id_value', 'doc_id_role']
        return [rights_statement.get(field, "") for field in basis_fields]

    def get_grant_restriction(self, rights_granted):
        """docstring for get_grant_restriction"""
        grant_restriction = ''
        if rights_granted.get('restriction'):
            grant_restriction = rights_granted.get('restriction')
        elif rights_granted.get('grant_restriction'):
            grant_restriction = rights_granted.get('grant_restriction')
        return rights_granted['act'], grant_restriction, rights_granted.get('start_date', ''), rights_granted.get('end_date', ''), rights_granted.get('note', '')

    def validate_rights_csv(self):
        """Validate a CSV to ensure it complies with Archivematica validation"""
        validator = CSVValidator(self.field_names)

        validator.add_header_check('EX1', 'bad header')
        validator.add_record_length_check('EX2', 'unexpected record length')
        validator.add_value_check('basis', enumeration('copyright', 'Copyright', 'statute', 'Statute', 'license', 'License', 'other', 'Other'), 'EX3', 'invalid basis')
        validator.add_value_check('status', enumeration('copyrighted', 'public domain', 'unknown', ''), 'EX4', 'invalid status')
        for field in ['file', 'note']:
            validator.add_value_check(field, str, 'EX7', 'field must exist')

        def check_dates(r):
            for field in [r['determination_date'], r['start_date'],
                          r['end_date'], r['grant_start_date'], r['grant_end_date']]:
                format = True
                try:
                    datetime.datetime.strptime(field, '%Y-%m-%d')
                except ValueError:
                    format = False
                valid = (format or field == 'OPEN')
            if not valid:
                raise RecordError('EX8', 'invalid date format')
        validator.add_record_check(check_dates)

        def check_restriction(r):
            grant_fields = ["grant_act", "grant_restriction", "grant_start_date", "grant_end_date", "grant_note"]
            if [g for g in grant_fields if r[g]]:
                if r["grant_act"].lower() not in ['publish', 'disseminate', 'replicate', 'migrate', 'modify', 'use', 'delete']:
                    raise RecordError('EX10', 'invalid act')
                elif r["grant_restriction"].lower() not in ["disallow", "conditional", "allow"]:
                    raise RecordError('EX10', 'invalid restriction')
                elif not r['grant_note']:
                    RecordError('EX7', 'field must exist')
        validator.add_record_check(check_restriction)

        with open(self.csv_filepath, 'r') as csvfile:
            data = csv.reader(csvfile)
            problems = validator.validate(data)
            if problems:
                raise Exception(problems)
