import csv
import datetime
from os import makedirs, path, walk

from csvvalidator import CSVValidator, RecordError, enumeration


class CsvCreator:
    """Creates and validates Archivematica-compliant CSV containing PREMIS rights"""

    def __init__(self, am_version):
        self.field_names = [
            'file', 'basis', 'status', 'determination_date', 'jurisdiction',
            'start_date', 'end_date', 'terms', 'citation', 'note', 'grant_act',
            'grant_restriction', 'grant_start_date', 'grant_end_date',
            'grant_note', 'doc_id_type', 'doc_id_value', 'doc_id_role']
        split_version = am_version.split(".")
        self.skip_no_act = True if (int(split_version[0]) <= 1 and int(split_version[1]) < 13) else False

    def create_rights_csv(self, bag_path, rights_statements):
        self.bag_path = bag_path
        self.rights_statements = rights_statements
        self.csv_filepath = path.join(bag_path, 'data', 'metadata', 'rights.csv')
        try:
            csvfile, csvwriter = self.setup_csv_file()
            for (dirpath, dirnames, filenames) in walk(path.join(self.bag_path, 'data', 'objects')):
                for file in filenames:
                    rights_rows = self.get_rights_rows(dirpath, file)
                    for rights_row in rights_rows:
                        csvwriter.writerow(rights_row)
            csvfile.close()
            self.validate_rights_csv()
            csvfile.close()
            return "CSV {} created.".format(self.csv_filepath)
        except Exception as e:
            print(e)

    def setup_csv_file(self):
        """
        If file already exists, sets mode to append. Otherwise, creates new file and
        writes a header row.

        Returns:
            csvfile: file object
            csvwriter csv writer object
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
        return csvfile, csvwriter

    def get_rights_rows(self, dirpath, file):
        """Gets rows (array of arrays) for each rights statement for a file."""

        """Gets rows (array of arrays) for each rights statement for a file."""
        path_to_file = path.join(dirpath.split(self.bag_path)[1], file).lstrip('/')
        rights_rows = []
        for rights_statement in self.rights_statements:
            rights_granted_rows = self.get_grant_restriction_rows(rights_statement['rights_granted'])
            for rights_granted_row in rights_granted_rows:
                if self.skip_no_act is True and rights_granted_row == ['', '', '', '', '']:
                    pass
                else:
                    rights_row = []
                    rights_row.append(path_to_file)
                    for basis_value in self.get_basis_fields(rights_statement):
                        rights_row.append(basis_value)
                    rights_row[10:10] = rights_granted_row
                    rights_rows.append(rights_row)
        return rights_rows

    def get_basis_fields(self, rights_statement):
        """
        Gets values of rights basis fields from a dictionary and returns a list

        Checks for copyright status field to be represented by 'status' or 'copyright_status' key

        """
        copyright_status = ''
        if rights_statement.get('status'):
            copyright_status = rights_statement.get('status')
        elif rights_statement.get('copyright_status'):
            copyright_status = rights_statement.get('copyright_status')
        basis_note = rights_statement.get('basis_note') if rights_statement.get('basis_note') else rights_statement.get('note')
        basis_fields = [
            'rights_basis', 'determination_date', 'jurisdiction', 'start_date',
            'end_date', 'terms', 'citation', 'doc_id_type', 'doc_id_value',
            'doc_id_role']
        basis_values = [rights_statement.get(field, "") for field in basis_fields]
        basis_values.insert(7, basis_note)
        basis_values.insert(1, copyright_status)
        return basis_values

    def get_grant_restriction_rows(self, rights_granted_list):
        """
        Returns a row for each grant or restriction in a rights_granted list. If
        no grants or restrictions are present, returns one row with five empty strings.

        Checks for grant or restriction field to be represented by 'restriction' or 'grant_restriction' key
        """
        if not(len(rights_granted_list)):
            return [[''] * 5]
        rows = []
        for rights_granted in rights_granted_list:
            grant_restriction = rights_granted.get('restriction') if rights_granted.get('restriction') else rights_granted.get('grant_restriction')
            granted_note = rights_granted.get('granted_note') if rights_granted.get('granted_note') else rights_granted.get('note')
            rows.append([rights_granted['act'], grant_restriction, rights_granted.get('start_date', ''),
                         rights_granted.get('end_date', ''), granted_note])
        return rows

    def validate_rights_csv(self):
        """Validate a CSV to ensure it complies with Archivematica validation"""
        validator = CSVValidator(self.field_names)

        validator.add_header_check('EX1', 'bad header')
        validator.add_record_length_check('EX2', 'unexpected record length')
        validator.add_value_check(
            'basis', enumeration(
                'copyright', 'Copyright', 'statute', 'Statute', 'license',
                'License', 'other', 'Other'), 'EX3', 'invalid basis')
        for field in ['file', 'note']:
            validator.add_value_check(field, str, 'EX5', 'field must exist')

        def check_dates(r):
            for field in [r['determination_date'], r['start_date'],
                          r['end_date'], r['grant_start_date'], r['grant_end_date']]:
                if r.get(field):
                    format = True
                    try:
                        datetime.datetime.strptime(field, '%Y-%m-%d')
                    except ValueError:
                        format = False
                    valid = (format or field.lower() == 'open')
                    if not valid:
                        raise RecordError('EX6', 'invalid date format')
        validator.add_record_check(check_dates)

        def check_restriction(r):
            grant_fields = ['grant_act', 'grant_restriction', 'grant_start_date', 'grant_end_date', 'grant_note']
            if [g for g in grant_fields if r[g]]:
                if r['grant_act'].lower() not in ['publish', 'disseminate', 'replicate', 'migrate', 'modify', 'use', 'delete']:
                    raise RecordError('EX7', 'invalid act')
                elif r['grant_restriction'].lower() not in ['disallow', 'conditional', 'allow']:
                    raise RecordError('EX8', 'invalid restriction')
        validator.add_record_check(check_restriction)

        def check_copyright_status(r):
            if r['basis'].lower() == 'copyright':
                if r['status'].lower() not in ['copyrighted', 'public domain', 'unknown']:
                    raise RecordError('EX4', 'invalid copyright status')
        validator.add_record_check(check_copyright_status)

        with open(self.csv_filepath, 'r') as csvfile:
            data = csv.reader(csvfile)
            problems = validator.validate(data)
            if problems:
                raise Exception("{} errors: {}".format(len(problems), problems))
