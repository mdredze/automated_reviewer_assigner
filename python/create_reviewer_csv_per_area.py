'''
Copyright 2013 Mark Dredze. All rights reserved.
This software is released under the 2-clause BSD license.
Mark Dredze, mdredze@cs.jhu.edu
'''
import os, sys, csv, re

'''
Author: Mark Dredze (mdredze@cs.jhu.edu)

This script creates CSV files, one per area. 

The two arguments are:
acl_reviewer_stats_filename- a download of the Google Spreadsheet into csv format. (File -> Download As -> CSV)

output path- A directory in which to create the output files.

'''
		
class ACLAreaReviwerCSVCreater:
	name_field = 'name'
	email_field = 'email'
	def getAreaNames(self, column_names):
		areas = []
		for entry in column_names:
			if entry.startswith('areas ['):
				area_name = re.search('areas \[(.+?) \(', entry).group(1)
				areas.append((entry, area_name))
			
		areas.sort()
		
		return areas

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
			print 'Usage: %s acl_reviewer_stats_filename output_path' % sys.argv[0]
			sys.exit()
			
		acl_reviewer_stats_filename = sys.argv[1]
		output_path = sys.argv[2]
		
		want_string = 'Want to review (1st Choices)'
		willing_string = 'Willing to review (2nd Choices)'
		will_not_string = 'Will not review'
		

		acl_reviewer_stats_contents, column_names = self.loadCSVFile(acl_reviewer_stats_filename)
		
		area_names = self.getAreaNames(column_names)
		
		if 'name (first last)' in column_names:
			self.name_field = 'name (first last)'
		if 'email address' in column_names:
			self.email_field = 'email address'
			
		for column_name, area_name in area_names:
			possible_reviewers = []
			for entry in acl_reviewer_stats_contents:
				name = entry[self.name_field]
				email = entry[self.email_field]
				

				# What di this person choose for this area.
				area_choice = entry.setdefault(column_name, '')
				
				if area_choice == want_string or area_choice == willing_string:
					possible_reviewers.append((name, email))
			
			print '%s: %d' % (area_name, len(possible_reviewers))
			output_filename = os.path.join(output_path, area_name.replace(' ', '_').replace('/', '_').replace('&', '_').lower() + '.tsv')
			output = open(output_filename, 'w')
			
			output.write('#Area:\t%s\n' % (area_name))
			output.write('#Area Load:\t4\n') # How many papers each reviewer will review
			output.write('#Paper Load:\t3\n') # The number of reviewers needed for each paper
			for name, email in possible_reviewers:
				output.write('%s\t%s\n' % (name, email))
			output.close()


if __name__ == '__main__':
	ACLAreaReviwerCSVCreater().run()