'''
Copyright 2013 Mark Dredze. All rights reserved.
This software is released under the 2-clause BSD license.
Mark Dredze, mdredze@cs.jhu.edu
'''
import os, sys, csv, re

'''
Author: Mark Dredze (mdredze@cs.jhu.edu)

This script computes statisitcs on reviewer recruitment progress based on a list of emailed reviewers.
Both input files should be in csv format.

The two arguments are:
acl_reviewer_stats_filename- a download of the Google Spreadsheet into csv format. (File -> Download As -> CSV)

reviews_email_list_for_area- a list of reviewers you have contacted. The first line must contain the column headers.
There are two required columns: ''Name'' (the reviewers name) and ''Email'' (the reviwers email). The script will look for exact
case insensitive matches of either of these two fields in the signup spreadhseet. You can supply two additional
columns: ''Decline'' and ''Chair''. If either of these fields contain any text, they will be excluded.
This enables you to track who has declined your offer by email. All other columns will be ignored.

The result of the script is a list of statistics and a list of names and emails of reviewers who haven't responded.
As some reviewers may enter a different name or email when they signup, this list may not be accurate.

'''
def selectAreaName(self, column_names):
	areas = []
	for entry in column_names:
		if entry.startswith('areas ['):
			area_name = re.search('areas \[(.+?) \(', entry).group(1)
			areas.append((entry, area_name))
		
	areas.sort()
	for ii, (entry, area_name) in enumerate(areas):
		print '%d\t%s' % (ii, area_name)
	area_number = input('Select area: ')
	return areas[area_number][0].lower()
		
class ACLCheckReviewers:
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
		return contents, names_to_columns.keys()	
			
	def run(self):
		if len(sys.argv) != 3:
			print 'Usage: %s acl_reviewer_stats_filename reviews_email_list_for_area' % sys.argv[0]
			sys.exit()
			
		acl_reviewer_stats_filename = sys.argv[1]
		acl_reviewer_emails_filename = sys.argv[2]
		
		want_string = 'Want to review (1st Choices)'
		willing_string = 'Willing to review (2nd Choices)'
		will_not_string = 'Will not review'
		
		
		
		acl_reviewer_emails_contents = self.loadCSVFile(acl_reviewer_emails_filename)[0]
		acl_reviewer_stats_contents, column_names = self.loadCSVFile(acl_reviewer_stats_filename)
		
		area_name = self.selectAreaName(column_names)
		
		# Create a list of all the reviewers who signed up.
		names = set()
		emails = set()
		name_to_signup_entry = {}
		email_to_signup_entry = {}
		for entry in acl_reviewer_stats_contents:
			name = entry['name'].lower()
			email = entry['email'].lower()
			if name:
				names.add(name)
				name_to_signup_entry[name] = entry
			if email:
				emails.add(email)
				email_to_signup_entry[email] = entry
		
	
		# Check to see if each reviewer signed up.
		num_missing_reviewers = 0
		num_missing_email = 0
		num_signed_up_reviewers = 0
		num_declined = 0
		num_chair = 0
		num_signed_up_reviewers_first_choice = 0
		num_signed_up_reviewers_second_choice = 0
		num_signed_up_reviewers_no_choice = 0
		
		contacted_names = set()
		contacted_emails = set()
		
		print "Reviewers who haven't signed up yet."
		for entry in acl_reviewer_emails_contents:
			name = entry.setdefault('name', '')
			email = entry.setdefault('email', '')
			
			chair = entry.setdefault('chair', '')
			declined = entry.setdefault('decline', '')
			
			name_lower = name.lower()
			email_lower = email.lower()
			
			if name_lower:
				contacted_names.add(name_lower)
			if email_lower:
				contacted_emails.add(email_lower)
				
			if not email:
				num_missing_email += 1
			elif name_lower not in names and email_lower not in emails and chair == '' and declined == '':
				# This reviewer hasn't signed up, didn't decline and is not a chair.
				print '\t%s\t%s' % (name, email)
				num_missing_reviewers += 1
			elif name_lower in names or email_lower in emails:
				if name_lower in names:
					area_choice = name_to_signup_entry[name_lower].setdefault(area_name, '')
				elif email_lower in emails:
					area_choice = email_to_signup_entry[email_lower].setdefault(area_name, '')
					
				num_signed_up_reviewers += 1
				if area_choice == want_string:
					num_signed_up_reviewers_first_choice += 1
				elif area_choice == willing_string:
					num_signed_up_reviewers_second_choice += 1
				else:
					num_signed_up_reviewers_no_choice += 1
			elif declined:
				num_declined += 1
			elif chair:
				num_chair += 1
		
		print "Reviewers signed up who weren't contacted:"
		not_contacted_signups = []
		not_contacted_signups_first = 0
		not_contacted_signups_second = 0
		for entry in acl_reviewer_stats_contents:
			name = entry['name']
			email = entry['email']
			area_choice = entry.setdefault(area_name, '')
			
			name_lower = name.lower()
			email_lower = email.lower()
			
			choice = None
			if area_choice == want_string:
				choice = 1
			elif area_choice == willing_string:
				choice = 2
			
			if name_lower not in contacted_names and email_lower not in contacted_emails and choice != None:
				not_contacted_signups.append((name, email, choice))
				
				if choice == 1:
					not_contacted_signups_first += 1
				if choice == 2:
					not_contacted_signups_second += 1
		
		not_contacted_signups.sort()
		for name, email, choice in not_contacted_signups:
			print '\t%s\t%s\t%d' % (name, email, choice)
		
		print "Number of people who haven't responded: %d" % num_missing_reviewers
		print "Number of people who are missing an email address: %d" % num_missing_email
		print "Number of signed up reviewers from contact list: %d" % num_signed_up_reviewers
		print '\tListed area as first choice: %d' % num_signed_up_reviewers_first_choice
		print '\tListed area as second choice: %d' % num_signed_up_reviewers_second_choice
		print '\tListed area as no choice: %d' % num_signed_up_reviewers_no_choice
		print 'Number of people who declined: %d' % num_declined
		print 'Number of people who are chairing another area: %d' % num_chair
		print "Number of people who signed up but weren't contacted: %d" % len(not_contacted_signups)
		print '\tFirst choice: %d' % not_contacted_signups_first
		print '\tSecond choice: %d' % not_contacted_signups_second
		print 'Total number of all reviewers who signed up: %d' % (len(names))
		print 'Total number of reviewers in contact list: %d' % (len(acl_reviewer_emails_contents))


if __name__ == '__main__':
	ACLCheckReviewers().run()