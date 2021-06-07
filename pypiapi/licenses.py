def licence_classifier_parser(classifier_strings :str) -> str:
	for classifier in classifier_strings:
		if not 'license' in classifier.lower():
			continue
			
		if 'gpl' in classifier.lower():
			non_regex_start = classifier.rfind('(')
			non_regex_ending = classifier.rfind(')')
			return classifier[non_regex_start+1:non_regex_ending].strip().lower()

		elif 'mit' in classifier.lower():
			return 'mit'

		else:
			return 'Unknown license'