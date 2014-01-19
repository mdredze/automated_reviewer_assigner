'''
Copyright 2013 Jiang Guo. All rights reserved.
This software is released under the 2-clause BSD license.
Jiang Guo, jguo@ir.hit.edu.cn
'''

import re, csv, sys
import datetime, time
import operator

''' 
Author: Jiang Guo (jguo@ir.hit.edu.cn)

This script extracts the reviewers who registered (accepted) in START,
but not signed up in the Google form.

The three arguments are:
    1. csv_START
        the reviewers list download from START.
    2. csv_Google
        the reviewers list download from Google form.
        (File -> Download As -> CSV)
    3. csv_output
        the reviewers who accepted in START, but not signed up in the Google form.
        It follows the format of csv_Google

Note: you need to concatenate the csv_output and csv_Google
after running this script, in order to obtain a complete reviewers list.
'''

class ReviewerCSVCreater:

    def __init__(self):
        pass

    def mapColumns(self, entry):
        names_to_columns = {}
        columns_to_names = {}
        for ii, name in enumerate(entry):
            names_to_columns[name.lower()] = ii
            columns_to_names[ii] = name.lower()

        return names_to_columns, columns_to_names

    def getColumn(self, entry, names_to_columns, column):
        column_id = names_to_columns[column]
        if column_id >= len(entry):
            return ''
        return entry[column_id]

    def loadCSVFile(self, filename):
        file = open(filename)
        reader = csv.reader(file)

        contents = []

        for ii, entry in enumerate(reader):
            if ii == 0:
                names_to_columns, columns_to_names = self.mapColumns(entry)
                continue
            line = {}
            for jj in range(len(entry)):
                line[columns_to_names[jj]] = entry[jj]
            contents.append(line)

        file.close()
        return contents, names_to_columns

def getAreaNames(column_names):
    ordered_column_names = sorted(column_names.iteritems(),
                                    key=operator.itemgetter(1))
    areas = {}
    for entry in ordered_column_names:
        entry = entry[0]
        if entry.startswith('areas ['):
            area_name = re.search('areas \[(.+?) \(', entry).group(1)
            areas[area_name] = len(areas)

    return areas

def getAccounts(contents, field="username"):
    accounts = []
    for entry in contents:
        accounts.append(entry[field].lower())
    return accounts

def getEmails(contents, field="email"):
    emails = []
    for entry in contents:
        emails.append(entry[field].lower())
    return emails

def parseAreaStr(area_str):
    areas = []
    items = area_str.split(":")
    for item in items:
        if item != "committee" and item != "":
            areas.append(item.lower())
    return areas

def makeRecord(s_account, s_email, s_name,
               s_time, s_affiliation, s_areas,
               area_to_ids):
    record = [s_time,
              s_name,
              s_email,
              s_affiliation,
              "",
              "",
              s_account]

    want_string = 'Want to review (1st Choices)'

    if "" in s_areas:
        print s_account
    area_ids = [area_to_ids[area] for area in s_areas]
    for ii in range(len(area_to_ids)):
        if ii in area_ids:
            record.append(want_string)
        else:
            record.append("")

    return record

if __name__ == '__main__':
    ''' extract those reviewers who accepted 
        but not signed up in the google spreadsheet
    '''

    usage = "Usage: %s csv_START csv_Google csv_output" % (sys.argv[0])
    if len(sys.argv) != 4:
        print >> sys.stderr, usage
        sys.exit()

    start_csv = sys.argv[1]
    google_csv  = sys.argv[2]
    output_csv = sys.argv[3]

    g_info, g_column_names = ReviewerCSVCreater().loadCSVFile(google_csv)
    s_info, s_column_names = ReviewerCSVCreater().loadCSVFile(start_csv)

    g_accounts = getAccounts(g_info, "start account username")
    g_emails   = getEmails(g_info, "email address")

    area_to_ids = getAreaNames(g_column_names)

    for area,id in area_to_ids.items():
        print area, id

    output = csv.writer(open(output_csv, "wb"))

    for entry in s_info:

        s_account  = entry["username"]
        s_email    = entry["email"]
        s_area_str = entry["access"]

        s_name = "%s %s" % (entry["first name"], entry["last name"])
        s_time = time.strftime("%Y/%m/%d %H:%M:%S", time.localtime())

        s_affiliation = entry["affiliation"]

        if s_account.lower() in g_accounts or \
                s_email.lower() in g_emails or \
                s_area_str.find("manager") >= 0:
            continue

        s_areas = parseAreaStr(s_area_str)
        if len(s_areas) == 0: continue

        s_record = makeRecord(s_account,
                              s_email,
                              s_name,
                              s_time,
                              s_affiliation,
                              s_areas,
                              area_to_ids)

        output.writerow(s_record)

