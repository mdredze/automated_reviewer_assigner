'''
Copyright 2013 Mark Dredze. All rights reserved.
This software is released under the 2-clause BSD license.
Mark Dredze, mdredze@cs.jhu.edu
'''
# Input- a whitelist for each area, a list of submissions per area, csv file with reviewer signups
# The area must add people to their whitelist that they approve of by using my other script
# Merge reviewer duplicates on input

# Algorithm:
# Find choices for every reviewer that respect the whitelist.
# Find every reviewer with only a single choice overall and assign them to their area
# assume a default of X papers by reviewer
# keep track of the number of reviewers assigned to each area and the number needed by each area
# for reviwers with 2 choices
# round robin between areas- for each area, find a reviewer who wants that area as #1, pick them
# Keep selecting area until it is full
# If no first round, then pick a second choice reviewer
# Once all areas are full, continue assignment but put an area in the round robin list propto the number of reviewers they need
# Start with an assumption of 3 * number of papers / load (4) but load is adjustable
from acl_check_reviewers import selectAreaName

import sys, os, csv, re, glob, random

class CsvLoader:
	def __init__(self, filename):
		self.__loadFile(filename)
		
	def __mapColumns(self, entry):
		self.names_to_columns = {}
		self.columns_to_names = {}
		for ii, name in enumerate(entry):
			self.names_to_columns[name.lower()] = ii
			self.columns_to_names[ii] = name.lower()

	def getColumn(self, entry, column):
		column_id = self.names_to_columns[column]
		if column_id >= len(entry):
			return ''
		return entry[column_id]
	
	def getColumnNames(self):
		return self.names_to_columns.keys()
		
	def __loadFile(self, filename):
		file = open(filename)
		reader = csv.reader(file)
		
		self.contents = []
		
		for ii, entry in enumerate(reader):
			if ii == 0:
				self.__mapColumns(entry)
				continue
			line = {}
			for jj in range(len(entry)):
				line[self.columns_to_names[jj]] = entry[jj]
			self.contents.append(line)

		file.close()
	
	def __iter__(self):
		return self.contents.__iter__()
	
	def __len__(self):
		return len(self.contents)
		
class ACLAssignGreedyReviewers:
	def __init__(self):
		self.want_string = 'Want to review (1st Choices)'
		self.willing_string = 'Willing to review (2nd Choices)'
		self.will_not_string = 'Will not review'
		self.name_field = 'name'
		self.email_field = 'email'
	
		pass
	
	
	def loadReviewerInformation(self, reviewer_csv_filename):
		csv_loader = CsvLoader(reviewer_csv_filename)
		
		
		column_names = csv_loader.getColumnNames()
		if 'name (first last)' in column_names:
			self.name_field = 'name (first last)'
		if 'email address' in column_names:
			self.email_field = 'email address'
		
		area_entry_to_name = {}
		for entry in column_names:
			if entry.startswith('areas ['):
				area_name = re.search('areas \[(.+?) \(', entry).group(1)
				area_entry_to_name[entry] = area_name
				
		
		names = set()
		emails = set()
		reviewer_to_area_choices = {}
		emails_to_reviewer_id_dict = {}
		from_reviewer_id_dict = {}
		reviewer_to_load = {}
		
		num_lines = 0
		for entry in csv_loader:
			num_lines += 1
			if len(entry) == 0:
				continue
			name = entry[self.name_field]
			email = entry[self.email_field].lower().strip()
			load_for_reviewer = entry['reduced review load (optional)']
			
			reviewer_id = name.replace(' ', '_') + '_' + email.replace(' ', '_')
			
				
			# Is this a valid email address.
			if '@' not in email or ' ' in email:
				print 'Warning: Invalid email: %s (%s)' % (name, email)
			

			duplicate_reviewer = False
			if reviewer_id in from_reviewer_id_dict or name in names or email in emails:
				if email in emails_to_reviewer_id_dict:
					reviewer_id = emails_to_reviewer_id_dict[email]
					duplicate_reviewer = True
				else:
					print 'Warning: duplicate reviewer name: ', name
			
			try:
				load_for_reviewer = int(load_for_reviewer)
				reviewer_to_load[reviewer_id] = load_for_reviewer
				print 'Registered load limit for %s (%s): %d' % (name, email, load_for_reviewer)
			except:
				pass
			
			names.add(name)
			emails.add(email)
			
			emails_to_reviewer_id_dict[email] = reviewer_id
			tuple = (name, email)
			
			from_reviewer_id_dict[reviewer_id] = tuple
			area_choices = []
	
			for area_entry, area_name in area_entry_to_name.iteritems():
				if area_entry not in entry:
					continue
				choice = entry[area_entry]
				rating = None
				if choice == self.want_string:
					rating = 1
				elif choice == self.willing_string:
					rating = 2
				
				if rating != None:
					area_choices.append((area_name, rating))
			
			if duplicate_reviewer:
				# Merge the reveiwers choices by always taking their higher choice.
				old_area_choices = reviewer_to_area_choices[reviewer_id]
				new_area_choices = {}
				for area, rating in area_choices:
					new_area_choices[area] = rating
				for area, rating in old_area_choices:
					new_area_choices[area] = max(new_area_choices.setdefault(area, 0), rating)
				area_choices = []
				for area, choice in new_area_choices.iteritems():
					area_choices.append((area, choice))
					
			reviewer_to_area_choices[reviewer_id] = area_choices
		
		print 'Number of lines: %d' % num_lines
		print 'Loaded %d/%d reviewers.' % (len(from_reviewer_id_dict), len(reviewer_to_area_choices))
		return reviewer_to_area_choices, emails_to_reviewer_id_dict, from_reviewer_id_dict, reviewer_to_load
	
	def selectReviewerForArea(self, area, reviewers_per_area_lists, used_reviewers):
		while len(reviewers_per_area_lists[area]) > 0:
			reviewer = reviewers_per_area_lists[area].pop(0)
			if reviewer not in used_reviewers:
				return reviewer
		return None
	
	# To handle differences in number of papers, we want to have some areas get multiple
	# people per round so every area fills up at the same time.
	# This methods computes how many assignments are needed to reach that point.
	def computeNumAreaAssignmentPerRound(self, area_to_load, area_to_num_papers, area_to_paper_load, priority_areas):
		area_to_num_assignments_per_round = {}
		# Compute how many reviewers are needed in each area.
		reviewers_needed_per_area = {}
		min = None
		max = None
		for area in area_to_num_papers.keys():
			reviewers_needed_per_area[area] = (area_to_num_papers[area] * area_to_paper_load[area]) / area_to_load[area]

			if min == None or min > reviewers_needed_per_area[area]:
				min = reviewers_needed_per_area[area]
			if max == None or max < reviewers_needed_per_area[area]:
				max = reviewers_needed_per_area[area]
	
		if max / min < 2:
			# The max isn't even twice the min area, so scale things up.
			print 'Error: max is not greater than twice min. Using 1 for everything.'
		# The min area gets one reviewer per round and every other area gets int(area/min)
		for area, num_reviewers in reviewers_needed_per_area.iteritems():
			area_to_num_assignments_per_round[area] = int(num_reviewers / min)
		
		for area in area_to_num_assignments_per_round.keys():
			if priority_areas != None and area in priority_areas:
				area_to_num_assignments_per_round[area] *= self.increase_priority_factor
			
		return area_to_num_assignments_per_round
	
	def assignReviewers(self, reviewers_per_area_lists, \
						reviewer_load_constraint, area_to_load, area_to_num_papers, \
						area_to_num_assignments_per_round, area_to_paper_load, \
						assign_all_whitelist_reviewers_to_area, forced_reviewer_to_area, \
						min_reviewers_per_area):
		# For each area, we have a list of reviewers who selected that area ordered by first choice,
		# the second choice, then by the number of total areas they picked.
		
		# A dict between area name and the reviewers assigned to that area.
		assignments = {}
		
		areas = area_to_num_papers.keys()
		print 'Assigning to %d areas.' % len(areas)
		area_to_num_reviews_assigned = {}
		for area in areas:
			area_to_num_reviews_assigned[area] = 0
		
		# In each pass, find reviewers who have only n selections. This saves the more flexible
		# reviewers for later.
		assignment_made = False
		full_areas = set()
		used_reviewers = set()
		all_areas_full = False
		all_areas_have_been_filled = False
		
		if assign_all_whitelist_reviewers_to_area:
			for area in assign_all_whitelist_reviewers_to_area:
				# Give everyone to this area that they want.
				while True:
					reviewer = self.selectReviewerForArea(area, reviewers_per_area_lists, used_reviewers)
	
					if not reviewer:
						break
					# Assign the reviewer to the area.
					assignments.setdefault(area, set()).add(reviewer)
					used_reviewers.add(reviewer)
					
					# How many reviews did we just assign to this area?
					if reviewer in reviewer_load_constraint:
						load_constraint = reviewer_load_constraint[reviewer]
						# A reviewer cannot exceed the load for an area.
						this_reviewer_load = min(load_constraint, area_to_load[area])
						if this_reviewer_load != area_to_load[area]:
							print 'LOAD LIMIT for %s: %d instead of %d' % (reviewer, this_reviewer_load, area_to_load[area])
						else:
							# This isn't a constraint for this area. Remove it
							del reviewer_load_constraint[reviewer]
					else:
						this_reviewer_load = area_to_load[area]
					area_to_num_reviews_assigned[area] += this_reviewer_load

					
				# Declare this area full.
				full_areas.add(area)
			
		
		# Assign reviewers to an area if they are forced to that area by special request.
		for (reviewer, area) in forced_reviewer_to_area.iteritems():
			assignments.setdefault(area, set()).add(reviewer)
			used_reviewers.add(reviewer)
			
			# How many reviews did we just assign to this area?
			if reviewer in reviewer_load_constraint:
				load_constraint = reviewer_load_constraint[reviewer]
				# A reviewer cannot exceed the load for an area.
				this_reviewer_load = min(load_constraint, area_to_load[area])
				if this_reviewer_load != area_to_load[area]:
					print 'LOAD LIMIT for %s: %d instead of %d' % (reviewer, this_reviewer_load, area_to_load[area])
				else:
					# This isn't a constraint for this area. Remove it
					del reviewer_load_constraint[reviewer]
			else:
				this_reviewer_load = area_to_load[area]
			area_to_num_reviews_assigned[area] += this_reviewer_load
			
			# Does this area need more reviewers?
			if area_to_num_reviews_assigned[area] >= \
				(area_to_num_papers[area] * area_to_paper_load[area]) \
				and not all_areas_full \
				and min_reviewers_per_area <= len(assignments[area]):

				full_areas.add(area)
	
					
					
					
		while True:
			assignment_made = False
			#random.shuffle(areas)
			for area in areas:
				if area in full_areas and not all_areas_full:
					continue
				
					
				for ii in range(0, int(area_to_num_assignments_per_round[area])):
					# Increase until we find a reviewer. or continue if we cannot.
					reviewer = self.selectReviewerForArea(area, reviewers_per_area_lists, used_reviewers)
					if not reviewer:
						continue # We found no valid reviewer.
						
					# Assign the reviewer to the area.
					assignments.setdefault(area, set()).add(reviewer)
					assignment_made = True
					used_reviewers.add(reviewer)
					
					# How many reviews did we just assign to this area?
					if reviewer in reviewer_load_constraint:
						load_constraint = reviewer_load_constraint[reviewer]
						# A reviewer cannot exceed the load for an area.
						this_reviewer_load = min(load_constraint, area_to_load[area])
						if this_reviewer_load != area_to_load[area]:
							#print 'LOAD LIMIT for %s: %d instead of %d' % (reviewer, this_reviewer_load, area_to_load[area])
							pass
						else:
							# This isn't a constraint for this area. Remove it
							del reviewer_load_constraint[reviewer]
					else:
						this_reviewer_load = area_to_load[area]
					area_to_num_reviews_assigned[area] += this_reviewer_load
					
					# Does this area need more reviewers?
					if area_to_num_reviews_assigned[area] >= \
						(area_to_num_papers[area] * area_to_paper_load[area]) \
						and not all_areas_full \
						and min_reviewers_per_area <= len(assignments[area]):
						full_areas.add(area)
						
						break
	
					
				
			# Do we have enough assignments made?
			if len(full_areas) == len(areas) and not all_areas_full:
				all_areas_full = True
				all_areas_have_been_filled = True
			elif not assignment_made and not all_areas_full:
				# The areas didn't just fill up, but no assignments were made.
				# Start making all remaining assignments anyway.
				all_areas_full = True
			elif not assignment_made and all_areas_full:
				# We can no longer make assignments and we've tried to make any assignment.
				break
		
		print 'Assignments finished.'
		if all_areas_have_been_filled:
			print 'All areas full.'
		else:
			print 'Not all areas full.'
			area_list = []
			for area in areas:
				if area not in full_areas:
					area_list.append(area)
			print 'Needs reviewers: ' + '   |   '.join(area_list)
		
		areas.sort()
		for area in areas:
			coverage = area_to_num_reviews_assigned[area]/area_to_paper_load[area] / float(area_to_num_papers[area]) * 100
			prefix = ''
			if coverage < 100:
				prefix='* '
			print '%s%s (Reviewers: %d, Max review capacity: %d, Actual reviews needed: %d, Coverage: %.0f%%)' % (prefix, area, len(assignments[area]), area_to_num_reviews_assigned[area]/area_to_paper_load[area], area_to_num_papers[area], coverage)
				
		return assignments, area_to_num_reviews_assigned
	
	# Create a map between area and reviewer, with reviewers sorted by choice.
	def createAreaReviewerLists(self, reviewer_to_area_choices, area_to_whitelist, accept_all_reviewers=False):
		reviewers_per_area_lists = {}
		area_to_total_possible_reviewers = {}
		for reviewer, area_choices in reviewer_to_area_choices.iteritems():
			for area, rating in area_choices:
				if accept_all_reviewers or (area in area_to_whitelist and reviewer in area_to_whitelist[area]):
					reviewers_per_area_lists.setdefault(area, []).append((rating, reviewer))
				area_to_total_possible_reviewers[area] = area_to_total_possible_reviewers.setdefault(area, 0) + 1
		
		for area, list in reviewers_per_area_lists.iteritems():
			list.sort(reverse=False)
			new_list = []
			for num, reviewer in list:
				new_list.append(reviewer)
			reviewers_per_area_lists[area] = new_list
		
		print 'Accepted reviewers per area (not including forced reviewers).'
		for area in area_to_whitelist:
			percent = float(len(reviewers_per_area_lists[area])) / float(area_to_total_possible_reviewers[area]) * 100
			print '\t%s %d accepted / %d total (%.2f)' % (area, len(reviewers_per_area_lists[area]), area_to_total_possible_reviewers[area], percent)
		return reviewers_per_area_lists

	def getSecondArgument(self, line):
		line = line.strip()

		split_line = line.split('\t')
		if len(split_line) < 2:
			print 'Error on line: %s' % line
		argument = split_line[1]
		
		return argument
		
	def loadWhitelists(self, whitelist_files, emails_to_reviewer_id_dict, forced_reviewer_to_area):
		whitelists = {}
		area_to_load = {}
		area_to_paper_load = {}
		for filename in whitelist_files:
			print 'Loading whitelist: %s' % filename
			file = open(filename)
			lines = file.readlines()
			file.close()
			
			if not lines[0].startswith('#') and not lines[1].startswith('#') and not lines[2].startswith('#'):
				print 'Error in whitelist file. Missing # on first three lines. ', filename
			
			area_name = self.getSecondArgument(lines[0])
			area_to_load[area_name] = int(self.getSecondArgument(lines[1]))
			area_to_paper_load[area_name] = int(self.getSecondArgument(lines[2]))
			
			num_loaded_reviewers = 0 
			whitelists[area_name] = set()
			for line in lines[3:]:
				line = line.strip()
				if line.startswith('#') or line == '':
					continue
				split_line = line.split('\t')
				if len(split_line) != 2:
					print 'Error on line: "%s"' % line
				reviewer_name = split_line[0].strip()
				reviewer_email = split_line[1].strip().lower()
				
				if reviewer_email not in emails_to_reviewer_id_dict:
					print 'Error: whitelist contains unknown reviewer: "%s" "%s"' % (reviewer_name, reviewer_email)
					sys.exit()
				
				if reviewer_name.startswith('*'):
					reviewer_name = reviewer_name[1:]
					print 'Forcing reviewer %s to area %s' % (reviewer_name, area_name)
					reviewer_id = emails_to_reviewer_id_dict[reviewer_email]
					if reviewer_id in forced_reviewer_to_area:
						print 'Error. %s is being forced to multiple areas.' % reviewer_name
						area_list_to_print = [forced_reviewer_to_area[reviewer_id], area_name]
						print '\tAreas: %s' % '|'.join(area_list_to_print)
						sys.exit()
					else:
						forced_reviewer_to_area[emails_to_reviewer_id_dict[reviewer_email]] = area_name
						num_loaded_reviewers += 1
				else:
					whitelists[area_name].add(emails_to_reviewer_id_dict[reviewer_email])
					num_loaded_reviewers += 1
					
			
			print 'Loaded %d reviewers for area %s.' % (num_loaded_reviewers, area_name)

		print 'Processed %d whitelists.' % len(whitelists)
		return whitelists, area_to_load, area_to_paper_load
	
	def getWhitelistFilenames(self, whitelist_files_prefix):
		return glob.glob(whitelist_files_prefix + '*')
	
	def printFinalAssignmentStats(self, output_filename_prefix, assignments, from_reviewer_id_dict, reviewer_load_constraint):
		output = open(output_filename_prefix + '_all_list.csv', 'w')
		
		output.write('#name\temail\tmax papers to assign\tarea\n')
		for area_name, reviewers in assignments.iteritems():
			filename = area_name.replace(' ', '_').replace('/', '_').replace('&', '_')
			area_output = open(output_filename_prefix + filename + '.csv', 'w')
			area_output.write('#name\temail\tmax papers to assign\n')
			for reviewer in reviewers:
				reviewer_name, reviewer_email = from_reviewer_id_dict[reviewer]
				load_constraint = ''
				if reviewer in reviewer_load_constraint:
					load_constraint = str(reviewer_load_constraint[reviewer])
				output.write('%s\t%s\t%s\t%s\n' % (reviewer_name, reviewer_email, load_constraint, area_name))
				area_output.write('%s\t%s\t%s\n' % (reviewer_name, reviewer_email, load_constraint))
			area_output.close()
		output.close()
	
		
		
	
	# Process a filename of the following format:
	# areaname \t reviewer load (how many papers per reviewer) \t num submissions
	
	def loadAreaStats(self, area_stats_filename):
		file = open(area_stats_filename)
		area_to_num_papers = {}
		total_submissions = 0
		for line in file:
			line = line.strip()
			if line.startswith('#') or line == '':
				continue
			print line
			area_name, submissions = line.split('\t')

			area_to_num_papers[area_name.lower()] = int(submissions)
			total_submissions += int(submissions)
		file.close()
		
		print 'Total submissions: %d' % total_submissions
		return area_to_num_papers
	
	def computeReviewerStats(self, assignments, reviewer_to_area_choices):
		total_choice_scores = 0
		total_assigned = 0
		rating_counts = [0,0]
		assigned_reviewers = set()
		for area_name, reviewer_list in assignments.iteritems():
			for reviewer in reviewer_list:
				assigned_reviewers.add(reviewer)
				area_choices = reviewer_to_area_choices[reviewer]
				for choice, rating in area_choices:
					if choice == area_name:
						total_choice_scores += rating
						total_assigned += 1
						rating_counts[rating-1] += 1 
						break

		print 'Average choice rating: ' + str(float(total_choice_scores) / float(total_assigned))
		print 'Reviewers with first choice: ' + str(rating_counts[0])
		print 'Reviewers with second choice: ' + str(rating_counts[1])
		print 'Assigned reviewers: ' + str(total_assigned)
		print 'Total reviewers: ' + str(len(reviewer_to_area_choices))
		
		# Who wasn't assigned?
		unassigned_reviewers = set()
		for reviewer in reviewer_to_area_choices.keys():
			if reviewer not in assigned_reviewers:
				unassigned_reviewers.add(reviewer)
		print 'Unassigned reviewers: %s' % ', '.join(unassigned_reviewers)
		
				
	def loadReviewerLoadConstraints(self, reviewer_load_constraints_files, email_to_reviewer_id):
		reviewer_load_constraint = {}
		for filename in reviewer_load_constraints_files:
			print 'Loading constraints from file: %s' % filename
			file = open(filename)
		
			for line in file:
				line = line.strip()
				if line.startswith('#') or line == '':
					continue
					
				email, load = line.split('\t')
				email = email.lower()
				
				if email not in email_to_reviewer_id:
					print 'Error: Loaded a constraint for %s but could not find this reviewer.' % email
				else:
					reviewer_id = email_to_reviewer_id[email]
					reviewer_load_constraint[reviewer_id] = int(load)
				
			file.close()
		
		return reviewer_load_constraint
		
	def run(self):
		# Load the acl signup sheet
		# Load a csv file with whitelists. each file should start with the area name on the first line
		# load a reviewer constraint list.
		# A file containing the number of submissions per area
		# An output file to write the assignments
		# A whitelist file should contain the area name on the first line preceeded by a pound. It then contains the email addresses of each reviewer.
		
		# reviewer_to_area_choices- filtered by whitelists. For each reviewer, a list of tuples with area and rating (1,2)
		# area_to_load- the load per reviewer in each area
		# area_to_num_papers- the number of papers in each area.
		# area_to_num_assignments_per_round = {} # In the round robin assignment, give multiple reviewers to each
		# 		area based on the number of reviewers they have total.
		
		if len(sys.argv) != 5:
			print 'Usage: %s reviewer_csv area_stats_filename whitelist_files_prefix output_filename_prefix' % sys.argv[0]
			sys.exit()
		reviewer_csv = sys.argv[1]
		area_stats_filename = sys.argv[2]
		whitelist_files_prefix = sys.argv[3]
		output_filename_prefix = sys.argv[4]
		#reviewer_load_constraints_prefix = sys.argv[5]
		
		accept_all_reviewers = False		

		# Automatically give this area everyone in its whitelist that is available.
		assign_all_whitelist_reviewers_to_area = None#set(['spoken language processing', 'nlp-enabled technology'])
		
		# These areas receive extra reviewers on each round so they fill up.
		priority_areas = set(['spoken language processing', 'nlp-enabled technology', 'multimodal nlp'])
		self.increase_priority_factor = 2
		
		# Small tracks may end up getting a handfull of reviewers. Ensure that there are at least this many
		# reviewers per area
		min_reviewers_per_area = 10
		################################################
		area_to_num_papers = self.loadAreaStats(area_stats_filename)
		
		# Dedpue and normalize reviewer list
		# emails_to_reviewer_id_dict # A dictionary between emails to reviewer ids.
		# from_reviewer_id_dict # A dictionary containing reviewer names and emails (tuple) from reviewer id.
		
		reviewer_to_area_choices, emails_to_reviewer_id_dict, from_reviewer_id_dict, reviewer_load_constraint = self.loadReviewerInformation(reviewer_csv)
		# Load whitelists and normalize reviewers.
		# A dictionary mapping area to a set of reviewer_ids
		
		#reviewer_load_constraints_files = self.getWhitelistFilenames(reviewer_load_constraints_prefix)
		#reviewer_load_constraint = self.loadReviewerLoadConstraints(reviewer_load_constraints_files, emails_to_reviewer_id_dict)
		
		forced_reviewer_to_area = {}
		whitelist_files = self.getWhitelistFilenames(whitelist_files_prefix)
		area_to_whitelist, area_to_load, area_to_paper_load = self.loadWhitelists(whitelist_files, emails_to_reviewer_id_dict, forced_reviewer_to_area)
		# normalize reviewers by unique keys based on email and username so we can match against whitelists
		reviewers_per_area_lists = self.createAreaReviewerLists(reviewer_to_area_choices, area_to_whitelist, accept_all_reviewers=accept_all_reviewers)
		
		# area_to_paper_load- the number of reviewers needed for each paper in each area
		
		area_to_num_assignments_per_round = self.computeNumAreaAssignmentPerRound(area_to_load, area_to_num_papers, area_to_paper_load, priority_areas)
						
						
		assignments, area_to_num_reviews_assigned = \
			self.assignReviewers(reviewers_per_area_lists, reviewer_load_constraint, area_to_load, \
								area_to_num_papers, area_to_num_assignments_per_round, area_to_paper_load, \
								assign_all_whitelist_reviewers_to_area, forced_reviewer_to_area, min_reviewers_per_area)
		
		self.computeReviewerStats(assignments, reviewer_to_area_choices)
		self.printFinalAssignmentStats(output_filename_prefix, assignments, from_reviewer_id_dict, reviewer_load_constraint)

if __name__ == '__main__':
	ACLAssignGreedyReviewers().run()