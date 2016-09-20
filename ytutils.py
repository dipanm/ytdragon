
import string

def removeNonAscii(s): return "".join(filter(lambda x: ord(x)<128, s))

# Not allowed characters 
#	filesystem  \ / : * ? " < > | 	other #	@ ? and nonprintable '\t' '\n' '\r'
def pathsafe(s): 
	keepcharacters = (' ','\'','.','_','-','!','%','(',')','+',',',';','[',']','{','}','~')
	return "".join(c for c in s if c.isalnum() or c in keepcharacters).rstrip()

def clean_up_title(title):
	title = title.replace('\n','').strip() 
	title = removeNonAscii(title) 

	printable = set(string.printable)
	title = filter(lambda x: x in printable, title)

	title = pathsafe(title) 

	return title 

def write_to_file(filename,blob): 
	fp = open(filename,"w") 
	if(fp): 
		fp.write(blob) 
		fp.close() 
	return 

# Take a wrappe that will print extra message and lines if you like and move both to the utils 
def print_pretty(logr,key,value,indent=0):
	max_depth = 3; 
	if ( isinstance(value, dict) and (indent < max_depth) ): 
		if(indent == 0): 
			logr.debug(str(key))
		else: 	
			logr.debug('\t' * (indent-1) + "[" + str(key) +"]")
   	   	for k, dval in value.iteritems():
			print_pretty(logr,k,dval, indent+1)
	elif isinstance(value, list): 
		if(indent == 0): 
                	logr.debug(str(key))
		else: 	
			if (isinstance(value[0], list) or isinstance(value[0], dict) ): 
                         	logr.debug('\t' * (indent-1) + "[" + str(key) + "] :")
				for i, lval in enumerate(value) : 
 	 	       			print_pretty(logr,i,lval,indent+1) 
 	 	       	else: 
 	 	       		logr.debug('\t' * (indent-1) + "["+key+"] : ["+",".join(value)+"]") 
	else:
		if(indent == 0): 
        		logr.debug(str(key)+"="+value)
		else:
         		logr.debug('\t' * (indent-1) + "[" + str(key) + "] : " + str(value))


